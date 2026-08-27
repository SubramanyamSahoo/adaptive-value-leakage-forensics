from __future__ import annotations

import argparse
import json
from pathlib import Path

from .metrics import crossing_asymmetry, slack_table, standardized_component_bias


def _coverage(rows, key):
    n = len(rows)
    if n == 0:
        return {"n": 0, "valid": 0, "rate": None}
    valid = sum(1 for r in rows if isinstance(r, dict) and (r.get(key) or []))
    return {"n": n, "valid": valid, "rate": valid / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()
    run = Path(args.run_dir)
    threshold = float(json.loads((run / "threshold.json").read_text())["threshold"])
    estimates = json.loads((run / "estimates.json").read_text())
    components = json.loads((run / "components.json").read_text())

    baseline = components.get("baseline", [])
    above = components.get("above_good", [])
    below = components.get("below_good", [])
    slack = slack_table(baseline)
    usable = {k: v.get("log_iqr") for k, v in slack.items() if v.get("log_iqr") is not None}
    selected = max(sorted(usable), key=lambda k: usable[k]) if usable else None

    out = {
        "headline_scope": "behavioral + component-level model forensics; trajectory MRF is secondary",
        "threshold": threshold,
        "final_behavior": crossing_asymmetry(estimates.get("above_good", []), estimates.get("below_good", []), threshold),
        "neutral_epistemic_slack": slack,
        "predicted_bias_carrier_by_max_neutral_log_iqr": selected,
        "component_bias": {
            k: standardized_component_bias(baseline, above, below, k)
            for k in ("giraffe_population", "spots_per_giraffe")
        },
        "component_extraction_coverage": {
            cond: {
                k: _coverage(components.get(cond, []), k)
                for k in ("giraffe_population", "spots_per_giraffe", "target_total")
            }
            for cond in ("baseline", "below_good", "above_good")
        },
    }
    path = run / "forensic_analysis.json"
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
