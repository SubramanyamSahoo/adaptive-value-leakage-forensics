from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu-log", required=True)
    args = ap.parse_args()

    vals = []
    mem = []
    power = []
    for line in Path(args.gpu_log).read_text().splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) != 5:
            continue
        try:
            vals.append(float(parts[1]))
            mem.append(float(parts[2]))
            power.append(float(parts[4]))
        except ValueError:
            continue

    if not vals:
        raise SystemExit("No parseable GPU utilization samples.")

    result = {
        "n_samples": len(vals),
        "gpu_util_mean_pct": float(np.mean(vals)),
        "gpu_util_median_pct": float(np.median(vals)),
        "gpu_util_p10_pct": float(np.quantile(vals, .10)),
        "gpu_util_p90_pct": float(np.quantile(vals, .90)),
        "memory_used_mean_mib": float(np.mean(mem)),
        "power_draw_mean_w": float(np.mean(power)),
        "note": "Optimize end-to-end tokens/sec, not utilization percentage alone.",
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
