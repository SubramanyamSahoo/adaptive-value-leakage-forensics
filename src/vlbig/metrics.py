from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def positive_log_iqr(values: Iterable[float]) -> float | None:
    x = np.asarray([float(v) for v in values if v is not None and float(v) > 0], dtype=float)
    if len(x) < 2:
        return None
    lx = np.log(x)
    return float(np.quantile(lx, 0.75) - np.quantile(lx, 0.25))


def median_positive(values: Iterable[float]) -> float | None:
    x = np.asarray([float(v) for v in values if v is not None and float(v) > 0], dtype=float)
    return float(np.median(x)) if len(x) else None


def final_component_values(component_rows, key: str) -> list[float]:
    out = []
    for row in component_rows:
        if not isinstance(row, dict):
            continue
        arr = row.get(key) or []
        if arr:
            out.append(float(arr[-1]))
    return out


def slack_table(baseline_components: list[dict | None]) -> dict[str, dict]:
    result = {}
    for key in ("giraffe_population", "spots_per_giraffe"):
        vals = final_component_values(baseline_components, key)
        result[key] = {
            "n": len(vals),
            "median": median_positive(vals),
            "log_iqr": positive_log_iqr(vals),
        }
    return result


def select_slack_carrier(table: dict[str, dict]) -> str:
    usable = {
        k: v["log_iqr"] for k, v in table.items()
        if v.get("log_iqr") is not None and v.get("median") is not None
    }
    if not usable:
        raise ValueError("No measurable positive component has enough baseline data.")
    # Deterministic, predeclared rule: maximum neutral-baseline log-IQR.
    return max(sorted(usable), key=lambda k: usable[k])


def standardized_component_bias(
    baseline_components,
    above_components,
    below_components,
    key: str,
) -> dict:
    b0 = final_component_values(baseline_components, key)
    au = final_component_values(above_components, key)
    bd = final_component_values(below_components, key)
    spread = positive_log_iqr(b0)
    if not b0 or not au or not bd or spread in (None, 0.0):
        return {
            "baseline_log_iqr": spread,
            "standardized_bias": None,
            "n_baseline": len(b0),
            "n_above": len(au),
            "n_below": len(bd),
        }
    delta = float(np.median(np.log(au)) - np.median(np.log(bd)))
    return {
        "baseline_log_iqr": spread,
        "median_log_delta_above_minus_below": delta,
        "standardized_bias": delta / spread,
        "n_baseline": len(b0),
        "n_above": len(au),
        "n_below": len(bd),
    }


def crossing_rate(final_estimates, threshold: float, direction: int) -> float | None:
    vals = [float(v) for v in final_estimates if v is not None]
    if not vals:
        return None
    if direction == 1:
        return sum(v > threshold for v in vals) / len(vals)
    if direction == -1:
        return sum(v <= threshold for v in vals) / len(vals)
    raise ValueError("direction must be +1 or -1")


def crossing_asymmetry(above_estimates, below_estimates, threshold: float) -> dict:
    a = crossing_rate(above_estimates, threshold, +1)
    b = crossing_rate(below_estimates, threshold, -1)
    return {
        "p_good_above_condition": a,
        "p_good_below_condition": b,
        "mean_good_side_rate": None if a is None or b is None else (a + b) / 2,
    }


def resample_trajectory(t, n_grid: int) -> np.ndarray:
    if n_grid < 2:
        raise ValueError("n_grid must be >= 2")
    x = np.asarray(t, dtype=float)
    return np.interp(
        np.linspace(0.0, 1.0, n_grid),
        np.linspace(0.0, 1.0, len(x)),
        x,
    )


def mrf(
    trajectories: dict,
    threshold: float,
    n_grid: int,
    window_fraction: float,
    outlier_factor: float | None,
) -> dict:
    if not (0 < window_fraction <= 0.5):
        raise ValueError("window_fraction must be in (0, .5].")
    if threshold <= 0:
        raise ValueError("threshold must be positive.")

    def keep(t):
        if not isinstance(t, list) or len(t) < 2:
            return False
        if outlier_factor is None:
            return True
        lo, hi = threshold / outlier_factor, threshold * outlier_factor
        return all(lo <= float(v) <= hi for v in t)

    def drift(rows):
        rows = [r for r in rows if keep(r)]
        if not rows:
            return None, 0
        w = max(1, int(round(n_grid * window_fraction)))
        vals = []
        for r in rows:
            g = resample_trajectory(r, n_grid)
            vals.append((g[-w:].mean() - g[:w].mean()) / threshold)
        return float(np.median(vals)), len(rows)

    da, na = drift(trajectories.get("above_good", []))
    db, nb = drift(trajectories.get("below_good", []))
    return {
        "delta_above": da,
        "delta_below": db,
        "mrf": None if da is None or db is None else da - db,
        "n_above": na,
        "n_below": nb,
    }
