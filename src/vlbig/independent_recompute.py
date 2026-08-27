from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--grid", type=int, required=True)
    ap.add_argument("--window-fraction", type=float, required=True)
    ap.add_argument("--outlier-factor", type=float, required=True)
    args = ap.parse_args()

    run = Path(args.run_dir)
    threshold = float(json.loads((run / "threshold.json").read_text())["threshold"])
    tr = json.loads((run / "trajectories.json").read_text())

    def calc(filtered):
        def ds(cond):
            d = []
            for t in tr.get(cond, []):
                if not isinstance(t, list) or len(t) < 2:
                    continue
                if filtered:
                    lo, hi = threshold / args.outlier_factor, threshold * args.outlier_factor
                    if not all(lo <= float(x) <= hi for x in t):
                        continue
                g = np.interp(
                    np.linspace(0, 1, args.grid),
                    np.linspace(0, 1, len(t)),
                    np.asarray(t, dtype=float),
                )
                w = max(1, int(round(args.grid * args.window_fraction)))
                d.append((g[-w:].mean() - g[:w].mean()) / threshold)
            return float(np.median(d)) if d else None
        a, b = ds("above_good"), ds("below_good")
        return None if a is None or b is None else a - b

    result = {
        "threshold_read_directly_from_json": threshold,
        "mrf_unfiltered_independent": calc(False),
        "mrf_filtered_independent": calc(True),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
