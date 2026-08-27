from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from pathlib import Path

from value_leakage.judge import TRAJECTORY_JUDGE_PROMPT, parse_trajectory

from .client import FullQueueClient
from .context import required_context
from .registry import get_model
from .server import VLLMServer


def iter_shipped_examples(repo_root: Path):
    for run in sorted((repo_root / "runs").glob("*")):
        tpath = run / "trajectories.json"
        if not tpath.exists():
            continue
        gold = json.loads(tpath.read_text())
        for cond in ("baseline", "below_good", "above_good"):
            raw_path = run / f"{cond}.json"
            if not raw_path.exists():
                continue
            raw = json.loads(raw_path.read_text())
            g = gold.get(cond, [])
            for i, row in enumerate(raw.get("rows", [])):
                if i >= len(g) or g[i] is None:
                    continue
                trace = row.get("reasoning") or ""
                if trace:
                    yield {
                        "run": run.name,
                        "condition": cond,
                        "i": i,
                        "trace": trace,
                        "gold": g[i],
                    }


def lcs_len(a: list[int], b: list[int]) -> int:
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            if x == y:
                cur.append(prev[j - 1] + 1)
            else:
                cur.append(max(prev[j], cur[-1]))
        prev = cur
    return prev[-1]


def score(preds, golds):
    valid_pairs = [(p, g) for p, g in zip(preds, golds) if p is not None]
    parse_rate = len(valid_pairs) / len(golds) if golds else 0.0
    if not valid_pairs:
        return {
            "parse_rate": parse_rate,
            "exact_match": 0.0,
            "last_match": 0.0,
            "length_match": 0.0,
            "median_length_ratio": None,
            "mean_lcs_recall": 0.0,
            "mean_lcs_precision": 0.0,
        }

    exact = sum(p == g for p, g in valid_pairs) / len(valid_pairs)
    last = sum(bool(p) and bool(g) and p[-1] == g[-1] for p, g in valid_pairs) / len(valid_pairs)
    length = sum(len(p) == len(g) for p, g in valid_pairs) / len(valid_pairs)
    ratios = [len(p) / len(g) for p, g in valid_pairs if g]
    lcs = [lcs_len(p, g) for p, g in valid_pairs]
    recalls = [z / len(g) for z, (_, g) in zip(lcs, valid_pairs) if g]
    precisions = [z / len(p) for z, (p, _) in zip(lcs, valid_pairs) if p]
    return {
        "parse_rate": parse_rate,
        "exact_match": exact,
        "last_match": last,
        "length_match": length,
        "median_length_ratio": statistics.median(ratios) if ratios else None,
        "mean_lcs_recall": sum(recalls) / len(recalls) if recalls else 0.0,
        "mean_lcs_precision": sum(precisions) / len(precisions) if precisions else 0.0,
    }


async def run(args):
    repo = Path(args.repo_root)
    rows = list(iter_shipped_examples(repo))
    if not rows:
        raise RuntimeError("No shipped Claude-judged trajectory examples found.")
    if args.limit is not None and args.limit < len(rows):
        import numpy as np
        idx = np.linspace(0, len(rows) - 1, args.limit, dtype=int)
        rows = [rows[int(i)] for i in idx]

    spec = get_model(args.judge)
    judge_prompts = [TRAJECTORY_JUDGE_PROMPT.format(llm_text=r["trace"]) for r in rows]
    context_len = required_context(spec, judge_prompts, args.judge_max_tokens)
    server = VLLMServer(spec, args.port, Path(args.out_dir) / "server_logs", max_model_len=context_len)
    server.start(args.server_timeout)
    try:
        client = FullQueueClient(server.base_url, queue_size=len(rows))

        async def one(k, r):
            prompt = TRAJECTORY_JUDGE_PROMPT.format(llm_text=r["trace"])
            try:
                raw = await client.generate_one(
                    spec,
                    prompt,
                    max_tokens=args.judge_max_tokens,
                    seed=args.seed + k,
                    deterministic=False,
                    disable_thinking=True,
                )
                pred = parse_trajectory(raw["content"])
                return pred, {
                    "content": raw["content"],
                    "reasoning": raw["reasoning"],
                    "trace_source": raw["trace_source"],
                    "finish_reason": raw["finish_reason"],
                    "usage": raw["usage"],
                    "latency_s": raw["latency_s"],
                    "sampling_mode": raw["sampling_mode"],
                    "parse_ok": pred is not None,
                }
            except Exception as e:
                return None, {"error": f"{type(e).__name__}: {e}", "parse_ok": False}

        results = await asyncio.gather(*(one(i, r) for i, r in enumerate(rows)))
        await client.close()
    finally:
        server.stop()

    preds = [x[0] for x in results]
    raw_records = [x[1] for x in results]
    metrics = score(preds, [r["gold"] for r in rows])
    out = {
        "judge_key": args.judge,
        "judge_model": spec.model_id,
        "n_examples": len(rows),
        "selection": "all" if args.limit is None else f"deterministic_evenly_spaced_{args.limit}",
        "purpose": "secondary trajectory-fidelity diagnostic; not the load-bearing forensic result",
        "metrics": metrics,
        "examples": [
            {
                **{k: r[k] for k in ("run", "condition", "i")},
                "gold": r["gold"],
                "pred": p,
                "raw_judge": raw,
            }
            for r, p, raw in zip(rows, preds, raw_records)
        ],
    }
    out_path = Path(args.out_dir) / f"judge_calibration_{args.judge}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("judge_key", "judge_model", "n_examples", "metrics")}, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--judge", required=True)
    ap.add_argument("--out-dir", default="judge_diagnostics_large")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--judge-max-tokens", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--server-timeout", type=int, required=True)
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
