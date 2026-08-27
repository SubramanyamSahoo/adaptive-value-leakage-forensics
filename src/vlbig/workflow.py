from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
from pathlib import Path
from typing import Callable

from value_leakage.judge import NUMBER_JUDGE_PROMPT, TRAJECTORY_JUDGE_PROMPT

from .audit import write_manual_audit
from .client import FullQueueClient
from .context import required_context
from .experiment import (
    clamp_from_slack,
    dump,
    irrelevant_clamp_from_values,
    threshold_record,
)
from .extract import (
    COMPONENT_PROMPT,
    IRRELEVANT_ESTIMATE_PROMPT,
    judge_texts,
)
from .prompts import (
    Clamp,
    clamped_prompt,
    original_prompt,
    structured_prompt,
)
from .registry import ModelSpec, get_model
from .server import VLLMServer


def _trace_texts(obj: dict) -> list[str | None]:
    out = []
    for row in obj["rows"]:
        if "error" in row:
            out.append(None)
            continue
        trace = row.get("reasoning") or ""
        out.append(trace if trace.strip() else None)
    return out


def _content_texts(obj: dict) -> list[str | None]:
    out = []
    for row in obj["rows"]:
        if "error" in row:
            out.append(None)
            continue
        text = row.get("content") or ""
        out.append(text if text.strip() else None)
    return out


async def _target_batch(
    spec: ModelSpec,
    prompts: dict[str, str],
    count: int,
    max_tokens: int,
    seed: int,
    port: int,
    server_timeout: int,
    log_dir: Path,
) -> dict[str, dict]:
    context_len = required_context(spec, prompts.values(), max_tokens)
    server = VLLMServer(spec, port, log_dir, max_model_len=context_len)
    server.start(server_timeout)
    try:
        # All condition queues are active together; vLLM continuously batches the union.
        client = FullQueueClient(server.base_url, queue_size=count * len(prompts))

        async def one_condition(j: int, condition: str, prompt: str):
            rows = await client.generate_many(
                spec, prompt, count, max_tokens, seed + j * count
            )
            return condition, {
                "model_key": spec.key,
                "model_id": spec.model_id,
                "condition": condition,
                "prompt": prompt,
                "rows": rows,
            }

        pairs = await asyncio.gather(*(
            one_condition(j, c, p) for j, (c, p) in enumerate(prompts.items())
        ))
        await client.close()
        return dict(pairs)
    finally:
        server.stop()


async def _judge_objects(
    judge: ModelSpec,
    objects: dict[str, dict],
    judge_max_tokens: int,
    seed: int,
    port: int,
    server_timeout: int,
    log_dir: Path,
) -> tuple[dict, dict, dict]:
    contents = {c: _content_texts(o) for c, o in objects.items()}
    traces = {c: _trace_texts(o) for c, o in objects.items()}

    prompts_for_context = []
    for texts in contents.values():
        prompts_for_context += [
            NUMBER_JUDGE_PROMPT.format(llm_text=t) for t in texts if t
        ]
    for texts in traces.values():
        prompts_for_context += [
            TRAJECTORY_JUDGE_PROMPT.format(llm_text=t) for t in texts if t
        ]
        prompts_for_context += [
            COMPONENT_PROMPT.format(llm_text=t) for t in texts if t
        ]
    if not prompts_for_context:
        raise RuntimeError("No target text available to judge.")

    context_len = required_context(judge, prompts_for_context, judge_max_tokens)
    server = VLLMServer(judge, port, log_dir, max_model_len=context_len)
    server.start(server_timeout)
    try:
        n_total = sum(len(v) for v in contents.values()) + 2 * sum(len(v) for v in traces.values())
        client = FullQueueClient(server.base_url, queue_size=max(1, n_total))
        estimate_jobs = []
        trajectory_jobs = []
        component_jobs = []
        keys = list(objects)
        for j, c in enumerate(keys):
            estimate_jobs.append(judge_texts(
                client, judge, contents[c], "estimate",
                judge_max_tokens, seed + 100_000 + j * 10_000
            ))
            trajectory_jobs.append(judge_texts(
                client, judge, traces[c], "trajectory",
                judge_max_tokens, seed + 200_000 + j * 10_000
            ))
            component_jobs.append(judge_texts(
                client, judge, traces[c], "components",
                judge_max_tokens, seed + 300_000 + j * 10_000
            ))

        estimates = dict(zip(keys, await asyncio.gather(*estimate_jobs)))
        trajectories = dict(zip(keys, await asyncio.gather(*trajectory_jobs)))
        components = dict(zip(keys, await asyncio.gather(*component_jobs)))
        await client.close()
        return estimates, trajectories, components
    finally:
        server.stop()


async def _judge_scalar_calibration(
    judge: ModelSpec,
    texts: list[str | None],
    judge_max_tokens: int,
    seed: int,
    port: int,
    server_timeout: int,
    log_dir: Path,
) -> list[float | None]:
    prompts = [NUMBER_JUDGE_PROMPT.format(llm_text=t) for t in texts if t]
    context_len = required_context(judge, prompts, judge_max_tokens)
    server = VLLMServer(judge, port, log_dir, max_model_len=context_len)
    server.start(server_timeout)
    try:
        client = FullQueueClient(server.base_url, queue_size=len(texts))
        vals = await judge_texts(
            client, judge, texts, "estimate", judge_max_tokens, seed
        )
        await client.close()
        return vals
    finally:
        server.stop()


def _new_run_dir(root: Path, target: ModelSpec, label: str) -> Path:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = root / target.key / f"{label}_{stamp}"
    p.mkdir(parents=True, exist_ok=False)
    return p


async def run_variant(
    target: ModelSpec,
    judge: ModelSpec,
    label: str,
    prompt_fn: Callable[[str, int | None], str],
    count: int,
    target_max_tokens: int,
    judge_max_tokens: int,
    seed: int,
    port: int,
    server_timeout: int,
    root: Path,
    audit_k: int,
) -> Path:
    run = _new_run_dir(root, target, label)
    log_dir = run / "logs"

    dump(run / "design.json", {
        "target": target.model_id,
        "judge": judge.model_id,
        "label": label,
        "count_per_condition": count,
        "target_max_tokens": target_max_tokens,
        "judge_max_tokens": judge_max_tokens,
        "seed": seed,
        "threshold_rule": "rounded median of neutral-baseline estimates extracted by designated judge",
        "note": "All values are explicit, model-card-derived, or data-derived.",
    })

    baseline_prompt = prompt_fn("baseline", None)
    base_obj = (await _target_batch(
        target, {"baseline": baseline_prompt}, count, target_max_tokens,
        seed, port, server_timeout, log_dir
    ))["baseline"]
    dump(run / "baseline.json", base_obj)

    base_est, base_tr, base_comp = await _judge_objects(
        judge, {"baseline": base_obj}, judge_max_tokens,
        seed + 1_000_000, port, server_timeout, log_dir
    )
    t_rec = threshold_record(base_est["baseline"])
    dump(run / "threshold.json", t_rec)
    threshold = t_rec["threshold"]

    treatment_prompts = {
        "below_good": prompt_fn("below_good", threshold),
        "above_good": prompt_fn("above_good", threshold),
    }
    treatments = await _target_batch(
        target, treatment_prompts, count, target_max_tokens,
        seed + 2_000_000, port, server_timeout, log_dir
    )
    for c, obj in treatments.items():
        dump(run / f"{c}.json", obj)

    all_obj = {"baseline": base_obj, **treatments}
    est, tr, comp = await _judge_objects(
        judge, all_obj, judge_max_tokens,
        seed + 3_000_000, port, server_timeout, log_dir
    )
    dump(run / "estimates.json", est)
    dump(run / "trajectories.json", tr)
    dump(run / "components.json", comp)

    write_manual_audit(run, k_per_condition=min(audit_k, count), seed=seed)
    return run


async def run_clamps(args, target: ModelSpec, judge: ModelSpec) -> list[Path]:
    free_run = Path(args.free_run)
    free_components = json.loads((free_run / "components.json").read_text())["baseline"]
    relevant, slack_meta = clamp_from_slack(free_components)
    meta_path = free_run / "slack_selection.json"
    dump(meta_path, slack_meta)

    # Irrelevant value is also data-derived. Use the SAME target and same count as the free run.
    free_design = json.loads((free_run / "design.json").read_text())
    calibration_count = int(free_design["count_per_condition"])

    target_cal = await _target_batch(
        target,
        {"irrelevant_neutral": IRRELEVANT_ESTIMATE_PROMPT},
        calibration_count,
        args.target_max_tokens,
        args.seed + 7_000_000,
        args.port,
        args.server_timeout,
        Path(args.out_root) / target.key / "irrelevant_calibration_logs",
    )
    texts = _content_texts(target_cal["irrelevant_neutral"])
    vals = await _judge_scalar_calibration(
        judge, texts, args.judge_max_tokens,
        args.seed + 8_000_000, args.port, args.server_timeout,
        Path(args.out_root) / target.key / "irrelevant_calibration_logs"
    )
    irrelevant = irrelevant_clamp_from_values(vals)

    clamp_record = {
        "relevant": {
            "quantity": relevant.quantity, "value": relevant.value,
            "instrumental": relevant.instrumental,
        },
        "irrelevant": {
            "quantity": irrelevant.quantity, "value": irrelevant.value,
            "instrumental": irrelevant.instrumental,
        },
        "template_identity": "both produced by identical CLAMP_TEMPLATE",
    }
    dump(Path(args.out_root) / target.key / "clamp_values.json", clamp_record)

    def rel_prompt(c, t):
        return clamped_prompt(c, t, relevant, structured=False)

    def irr_prompt(c, t):
        return clamped_prompt(c, t, irrelevant, structured=False)

    paths = []
    paths.append(await run_variant(
        target, judge, "relevant_clamp", rel_prompt,
        args.count, args.target_max_tokens, args.judge_max_tokens,
        args.seed + 9_000_000, args.port, args.server_timeout,
        Path(args.out_root), args.audit_k
    ))
    paths.append(await run_variant(
        target, judge, "irrelevant_matched_clamp", irr_prompt,
        args.count, args.target_max_tokens, args.judge_max_tokens,
        args.seed + 10_000_000, args.port, args.server_timeout,
        Path(args.out_root), args.audit_k
    ))
    return paths


async def main_async(args):
    target = get_model(args.target)
    judge = get_model(args.judge)
    if target.key == judge.key and not args.allow_self_judge:
        raise SystemExit(
            "Target and judge are identical. Choose the calibrated alternate judge, "
            "or explicitly pass --allow-self-judge for a documented diagnostic."
        )

    if args.mode == "free":
        path = await run_variant(
            target, judge, "free", original_prompt,
            args.count, args.target_max_tokens, args.judge_max_tokens,
            args.seed, args.port, args.server_timeout,
            Path(args.out_root), args.audit_k
        )
        print(path)
    elif args.mode == "structured":
        path = await run_variant(
            target, judge, "structured", structured_prompt,
            args.count, args.target_max_tokens, args.judge_max_tokens,
            args.seed, args.port, args.server_timeout,
            Path(args.out_root), args.audit_k
        )
        print(path)
    elif args.mode == "clamps":
        if not args.free_run:
            raise SystemExit("--free-run is required for data-derived clamp construction.")
        paths = await run_clamps(args, target, judge)
        for p in paths:
            print(p)
    else:
        raise ValueError(args.mode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("free", "structured", "clamps"), required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--target-max-tokens", type=int, required=True)
    ap.add_argument("--judge-max-tokens", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--server-timeout", type=int, required=True)
    ap.add_argument("--audit-k", type=int, required=True)
    ap.add_argument("--out-root", default="runs_gh200")
    ap.add_argument("--free-run")
    ap.add_argument("--allow-self-judge", action="store_true")
    args = ap.parse_args()

    if args.count < 1 or args.audit_k < 1:
        raise SystemExit("--count and --audit-k must be positive.")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
