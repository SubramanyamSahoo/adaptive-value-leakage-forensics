from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import norm


def two_proportion_n(p1: float, p2: float, alpha: float, power: float) -> int | None:
    if not (0 < alpha < 1 and 0 < power < 1):
        raise ValueError("alpha and power must be in (0,1).")
    if not (0 <= p1 <= 1 and 0 <= p2 <= 1):
        raise ValueError("probabilities must be in [0,1].")
    effect = abs(p1 - p2)
    if effect == 0:
        return None
    pbar = (p1 + p2) / 2
    z_alpha = norm.ppf(1 - alpha / 2)
    z_power = norm.ppf(power)
    num = (
        z_alpha * math.sqrt(2 * pbar * (1 - pbar))
        + z_power * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    return int(math.ceil(num / effect**2))


def standardized_continuous_n(effect_d: float, alpha: float, power: float) -> int | None:
    d = abs(float(effect_d))
    if d == 0:
        return None
    z_alpha = norm.ppf(1 - alpha / 2)
    z_power = norm.ppf(power)
    return int(math.ceil(2 * ((z_alpha + z_power) / d) ** 2))


def inflate_missing(n: int | None, missing_rate: float) -> int | None:
    if n is None:
        return None
    if not (0 <= missing_rate < 1):
        raise ValueError("missing_rate must be in [0,1).")
    return int(math.ceil(n / (1 - missing_rate)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot-json", required=True,
                    help="JSON with p1,p2,continuous_effect_d,missing_rate.")
    ap.add_argument("--alpha", type=float, required=True)
    ap.add_argument("--power", type=float, required=True)
    args = ap.parse_args()

    d = json.loads(Path(args.pilot_json).read_text())
    n_binary = two_proportion_n(d["p1"], d["p2"], args.alpha, args.power)
    n_cont = standardized_continuous_n(d["continuous_effect_d"], args.alpha, args.power)
    candidates = [n for n in (n_binary, n_cont) if n is not None]
    result = {
        "alpha": args.alpha,
        "power": args.power,
        "binary_n_per_condition": inflate_missing(n_binary, d["missing_rate"]),
        "continuous_n_per_condition": inflate_missing(n_cont, d["missing_rate"]),
        "recommended_n_per_condition": (
            max(inflate_missing(n, d["missing_rate"]) for n in candidates)
            if candidates else None
        ),
        "note": (
            "If recommended_n_per_condition is null, the pilot effect estimate is zero; "
            "do not scale automatically from this pilot."
        ),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
