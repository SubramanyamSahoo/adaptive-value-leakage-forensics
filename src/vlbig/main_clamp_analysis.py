from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .metrics import final_component_values, positive_log_iqr


def _valid(xs):
    return np.asarray(
        [float(x) for x in xs if x is not None and float(x) > 0],
        dtype=float,
    )


def _q(xs, q):
    if len(xs) == 0:
        return None
    return float(np.quantile(xs, q))


def _directional(estimates, threshold):
    a = _valid(estimates.get("above_good", []))
    b = _valid(estimates.get("below_good", []))
    if len(a) == 0 or len(b) == 0:
        return None
    p_a = float(np.mean(a > threshold))
    p_b = float(np.mean(b > threshold))
    return {
        "p_above_given_above_good": p_a,
        "p_above_given_below_good": p_b,
        "directional_leakage": p_a - p_b,
        "n_above": int(len(a)),
        "n_below": int(len(b)),
    }


def _component_summary(components, key):
    base = np.asarray(final_component_values(components.get("baseline", []), key), dtype=float)
    above = np.asarray(final_component_values(components.get("above_good", []), key), dtype=float)
    below = np.asarray(final_component_values(components.get("below_good", []), key), dtype=float)

    if len(above) and len(below):
        raw_delta = float(np.median(np.log(above)) - np.median(np.log(below)))
        mult = float(math.exp(raw_delta))
    else:
        raw_delta = None
        mult = None

    spread = positive_log_iqr(base)
    standardized = (
        None if raw_delta is None or spread in (None, 0.0)
        else raw_delta / spread
    )
    return {
        "n_baseline": int(len(base)),
        "n_above": int(len(above)),
        "n_below": int(len(below)),
        "baseline_median": None if not len(base) else float(np.median(base)),
        "baseline_log_iqr": spread,
        "above_median": None if not len(above) else float(np.median(above)),
        "below_median": None if not len(below) else float(np.median(below)),
        "above_minus_below_log_median": raw_delta,
        "above_vs_below_multiplicative_ratio": mult,
        "standardized_bias": standardized,
    }


def _load(run_dir):
    p = Path(run_dir)
    return {
        "path": str(p),
        "threshold": float(json.loads((p / "threshold.json").read_text())["threshold"]),
        "estimates": json.loads((p / "estimates.json").read_text()),
        "components": json.loads((p / "components.json").read_text()),
    }


def _bootstrap_directional_diff(rel, irr, reps, seed):
    rng = np.random.default_rng(seed)

    def arrays(x):
        t = x["threshold"]
        a = _valid(x["estimates"].get("above_good", []))
        b = _valid(x["estimates"].get("below_good", []))
        return t, a, b

    rt, ra, rb = arrays(rel)
    it, ia, ib = arrays(irr)
    if min(len(ra), len(rb), len(ia), len(ib)) == 0:
        return None

    vals = np.empty(reps, dtype=float)
    for j in range(reps):
        r_a = rng.choice(ra, len(ra), replace=True)
        r_b = rng.choice(rb, len(rb), replace=True)
        i_a = rng.choice(ia, len(ia), replace=True)
        i_b = rng.choice(ib, len(ib), replace=True)

        r = float(np.mean(r_a > rt) - np.mean(r_b > rt))
        i = float(np.mean(i_a > it) - np.mean(i_b > it))
        vals[j] = r - i

    return {
        "bootstrap_reps": reps,
        "median": float(np.median(vals)),
        "ci95": [_q(vals, 0.025), _q(vals, 0.975)],
        "p_fraction_below_zero": float(np.mean(vals < 0)),
    }


def _bootstrap_component_diff(rel, irr, key, reps, seed):
    rng = np.random.default_rng(seed)

    def arrs(run):
        comp = run["components"]
        a = np.asarray(final_component_values(comp.get("above_good", []), key), dtype=float)
        b = np.asarray(final_component_values(comp.get("below_good", []), key), dtype=float)
        return a, b

    ra, rb = arrs(rel)
    ia, ib = arrs(irr)
    if min(len(ra), len(rb), len(ia), len(ib)) == 0:
        return None

    vals = np.empty(reps, dtype=float)
    for j in range(reps):
        r_a = rng.choice(ra, len(ra), replace=True)
        r_b = rng.choice(rb, len(rb), replace=True)
        i_a = rng.choice(ia, len(ia), replace=True)
        i_b = rng.choice(ib, len(ib), replace=True)

        r = float(np.median(np.log(r_a)) - np.median(np.log(r_b)))
        i = float(np.median(np.log(i_a)) - np.median(np.log(i_b)))
        vals[j] = r - i

    return {
        "bootstrap_reps": reps,
        "median_log_delta_difference_rel_minus_irr": float(np.median(vals)),
        "ci95": [_q(vals, 0.025), _q(vals, 0.975)],
        "p_fraction_above_zero": float(np.mean(vals > 0)),
        "p_fraction_below_zero": float(np.mean(vals < 0)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--free", required=True)
    ap.add_argument("--relevant", required=True)
    ap.add_argument("--irrelevant", required=True)
    ap.add_argument("--design-lock", required=True)
    ap.add_argument("--out", default="main_experiment/main_clamp_analysis.json")
    ap.add_argument("--bootstrap-reps", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=382806405)
    args = ap.parse_args()

    design = json.loads(Path(args.design_lock).read_text())
    carrier = design["predicted_carrier"]
    other = (
        "giraffe_population"
        if carrier == "spots_per_giraffe"
        else "spots_per_giraffe"
    )

    runs = {
        "free": _load(args.free),
        "relevant_clamp": _load(args.relevant),
        "irrelevant_matched_clamp": _load(args.irrelevant),
    }

    for r in runs.values():
        r["behavior"] = _directional(r["estimates"], r["threshold"])
        r["component_summary"] = {
            key: _component_summary(r["components"], key)
            for key in ("giraffe_population", "spots_per_giraffe")
        }
        # Avoid duplicating large raw data in the final report.
        del r["estimates"]
        del r["components"]

    rel = _load(args.relevant)
    irr = _load(args.irrelevant)
    rel_dir = _directional(rel["estimates"], rel["threshold"])["directional_leakage"]
    irr_dir = _directional(irr["estimates"], irr["threshold"])["directional_leakage"]

    out = {
        "design_lock_sha256": design["sha256_before_hash_field"],
        "predicted_carrier": carrier,
        "migration_component": other,
        "primary_endpoint": design["primary_endpoint"],
        "primary_causal_contrast_definition": design["primary_causal_contrast"],
        "runs": runs,
        "primary_causal_contrast": {
            "relevant_directional_leakage": rel_dir,
            "irrelevant_directional_leakage": irr_dir,
            "relevant_minus_irrelevant": rel_dir - irr_dir,
            "prediction_satisfied_point_estimate": (rel_dir - irr_dir) < 0,
            "bootstrap": _bootstrap_directional_diff(
                _load(args.relevant),
                _load(args.irrelevant),
                args.bootstrap_reps,
                args.seed,
            ),
        },
        "carrier_component_rel_minus_irr": _bootstrap_component_diff(
            _load(args.relevant),
            _load(args.irrelevant),
            carrier,
            args.bootstrap_reps,
            args.seed + 1,
        ),
        "migration_component_rel_minus_irr": _bootstrap_component_diff(
            _load(args.relevant),
            _load(args.irrelevant),
            other,
            args.bootstrap_reps,
            args.seed + 2,
        ),
        "interpretation": {
            "H3_support_pattern": (
                "Relevant clamp reduces directional leakage relative to the identically-worded "
                "irrelevant clamp and/or treatment-directed bias increases in the remaining component."
            ),
            "H4_pattern": (
                "Relevant clamp leaves directional leakage largely unchanged while component "
                "treatment shifts remain weak."
            ),
            "do_not_overclaim": (
                "Stage A is an intervention estimate, not automatically a final confirmatory result. "
                "Use the bootstrap interval and raw-trace audit to decide whether a larger replication is needed."
            ),
        },
    }

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
