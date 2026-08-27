from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .metrics import (
    crossing_asymmetry,
    mrf,
    standardized_component_bias,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--grid", type=int, required=True)
    ap.add_argument("--window-fraction", type=float, required=True)
    ap.add_argument("--outlier-factor", type=float, required=True)
    args = ap.parse_args()

    run = Path(args.run_dir)
    threshold = float(json.loads((run / "threshold.json").read_text())["threshold"])
    estimates = json.loads((run / "estimates.json").read_text())
    trajectories = json.loads((run / "trajectories.json").read_text())
    components = json.loads((run / "components.json").read_text())

    out = {
        "crossing": crossing_asymmetry(
            estimates.get("above_good", []),
            estimates.get("below_good", []),
            threshold,
        ),
        "mrf_unfiltered": mrf(
            trajectories, threshold, args.grid, args.window_fraction, None
        ),
        "mrf_filtered": mrf(
            trajectories, threshold, args.grid, args.window_fraction, args.outlier_factor
        ),
        "component_bias": {
            k: standardized_component_bias(
                components.get("baseline", []),
                components.get("above_good", []),
                components.get("below_good", []),
                k,
            )
            for k in ("giraffe_population", "spots_per_giraffe")
        },
    }
    (run / "analysis.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
