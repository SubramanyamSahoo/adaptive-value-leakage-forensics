from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from transformers import AutoTokenizer

from .registry import get_model


def gold_strings(repo_root: Path) -> list[str]:
    out = []
    for path in sorted((repo_root / "runs").glob("*/trajectories.json")):
        data = json.loads(path.read_text())
        for condition in ("baseline", "below_good", "above_good"):
            for traj in data.get(condition, []):
                if isinstance(traj, list) and traj:
                    out.append(",".join(str(int(x)) for x in traj))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--models", required=True, help="comma-separated model keys")
    ap.add_argument("--out", default="judge_calibration/budgets.json")
    args = ap.parse_args()

    gold = gold_strings(Path(args.repo_root))
    if not gold:
        raise SystemExit("No shipped non-null Claude-labelled trajectories found.")

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        raise SystemExit("Set HF_TOKEN first.")

    result = {"n_gold": len(gold), "models": {}}
    for key in [x.strip() for x in args.models.split(",") if x.strip()]:
        spec = get_model(key)
        tok = AutoTokenizer.from_pretrained(
            spec.model_id, token=token, trust_remote_code=True
        )
        lengths = [len(tok.encode(s, add_special_tokens=False)) for s in gold]
        none_len = len(tok.encode("NONE", add_special_tokens=False))
        # Exact empirical longest valid output plus one termination token.
        budget = max(max(lengths), none_len) + 1
        result["models"][key] = {
            "model_id": spec.model_id,
            "max_gold_tokens": max(lengths),
            "none_tokens": none_len,
            "judge_max_tokens": budget,
            "rule": "1 + max(longest shipped gold trajectory, NONE)",
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
