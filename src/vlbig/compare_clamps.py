from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(run_dir: str):
    p = Path(run_dir)
    a = p / "forensic_analysis.json"
    if not a.exists():
        raise SystemExit(f"Missing {a}; run python -m vlbig.forensic_analysis --run-dir {p}")
    return json.loads(a.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--free", required=True)
    ap.add_argument("--relevant", required=True)
    ap.add_argument("--irrelevant", required=True)
    ap.add_argument("--out", default="clamp_comparison.json")
    args = ap.parse_args()
    data = {k: load(v) for k, v in {
        "free": args.free,
        "relevant_clamp": args.relevant,
        "irrelevant_matched_clamp": args.irrelevant,
    }.items()}

    def rate(x):
        return x["final_behavior"].get("mean_good_side_rate")

    free = rate(data["free"])
    rel = rate(data["relevant_clamp"])
    irr = rate(data["irrelevant_matched_clamp"])
    out = {
        "runs": data,
        "headline": {
            "free_good_side_rate": free,
            "relevant_clamp_good_side_rate": rel,
            "irrelevant_matched_clamp_good_side_rate": irr,
            "relevant_minus_free": None if rel is None or free is None else rel - free,
            "irrelevant_minus_free": None if irr is None or free is None else irr - free,
            "relevant_minus_irrelevant": None if rel is None or irr is None else rel - irr,
        },
        "interpretation_rule": (
            "Support for epistemic-slack mediation requires the relevant clamp to change leakage "
            "more than the identically phrased irrelevant clamp; inspect component migration rather "
            "than treating suppression alone as decisive."
        ),
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
