from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .metrics import slack_table, select_slack_carrier, standardized_component_bias


def _valid(vals):
    return [float(x) for x in vals if x is not None]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    run = Path(args.run_dir)
    threshold = float(json.loads((run / "threshold.json").read_text())["threshold"])
    estimates = json.loads((run / "estimates.json").read_text())
    components = json.loads((run / "components.json").read_text())

    above = _valid(estimates.get("above_good", []))
    below = _valid(estimates.get("below_good", []))
    if not above or not below:
        raise SystemExit("Missing treatment estimates; cannot form pilot power input.")

    # Binary endpoint: probability of landing above threshold in the two mirrored conditions.
    p1 = sum(x > threshold for x in above) / len(above)
    p2 = sum(x > threshold for x in below) / len(below)

    table = slack_table(components.get("baseline", []))
    carrier = select_slack_carrier(table)
    bias = standardized_component_bias(
        components.get("baseline", []),
        components.get("above_good", []),
        components.get("below_good", []),
        carrier,
    )
    d = bias.get("standardized_bias")
    if d is None:
        raise SystemExit(
            f"Selected carrier {carrier} lacks enough extracted component data for continuous effect."
        )

    total_expected = (
        len(estimates.get("baseline", []))
        + len(estimates.get("above_good", []))
        + len(estimates.get("below_good", []))
    )
    total_valid = (
        len(_valid(estimates.get("baseline", []))) + len(above) + len(below)
    )
    missing_rate = 1 - total_valid / total_expected if total_expected else 0.0

    out = {
        "p1": p1,
        "p2": p2,
        "continuous_effect_d": float(d),
        "missing_rate": missing_rate,
        "carrier": carrier,
        "threshold": threshold,
        "binary_endpoint": "P(final estimate > threshold | above_good) vs P(final estimate > threshold | below_good)",
        "continuous_endpoint": "treatment log-median component difference / neutral-baseline log-IQR",
    }
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
