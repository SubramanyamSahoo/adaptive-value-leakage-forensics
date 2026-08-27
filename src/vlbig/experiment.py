from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from .client import FullQueueClient
from .extract import IRRELEVANT_ESTIMATE_PROMPT, judge_texts
from .metrics import slack_table, select_slack_carrier
from .prompts import Clamp, original_prompt, structured_prompt, clamped_prompt
from .registry import ModelSpec


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def source(rows_obj: dict, field: str) -> list[str | None]:
    out = []
    for r in rows_obj["rows"]:
        if "error" in r:
            out.append(None)
        else:
            v = r.get(field) or ""
            out.append(v if v.strip() else None)
    return out


async def generate_condition(
    client: FullQueueClient,
    target: ModelSpec,
    prompt: str,
    condition: str,
    count: int,
    max_tokens: int,
    seed: int,
) -> dict:
    rows = await client.generate_many(
        target, prompt, count=count, max_tokens=max_tokens, seed_base=seed
    )
    return {
        "model_key": target.key,
        "model_id": target.model_id,
        "condition": condition,
        "prompt": prompt,
        "rows": rows,
    }


def threshold_record(estimates: list[float | None]) -> dict:
    x = [float(v) for v in estimates if v is not None and float(v) > 0]
    if not x:
        raise ValueError("No valid baseline estimates.")
    return {
        "threshold": int(round(float(np.median(x)))),
        "n_total": len(estimates),
        "n_valid": len(x),
        "missing_rate": 1 - len(x) / len(estimates),
        "rule": "rounded median of valid neutral-baseline final estimates",
    }


def clamp_from_slack(baseline_components: list[dict | None]) -> tuple[Clamp, dict]:
    table = slack_table(baseline_components)
    key = select_slack_carrier(table)
    label = {
        "giraffe_population": "the number of currently living giraffes",
        "spots_per_giraffe": "the average number of counted spots per giraffe",
    }[key]
    value = table[key]["median"]
    if value is None:
        raise ValueError("Selected carrier has no median.")

    # Preserve the data-derived neutral median exactly. For an average quantity,
    # a half-integer such as 792.5 is scientifically meaningful.
    clamp_value = float(value)
    if clamp_value.is_integer():
        clamp_value = int(clamp_value)

    return Clamp(quantity=label, value=clamp_value, instrumental=True), {
        "slack_table": table,
        "selected_component": key,
        "selected_neutral_median": value,
        "clamp_value": clamp_value,
        "selection_rule": "max neutral-baseline IQR(log(component))",
        "clamp_value_rule": "exact neutral-baseline median; integer only when median is integral",
    }


def irrelevant_clamp_from_values(values: list[float | None]) -> Clamp:
    x = [float(v) for v in values if v is not None and float(v) > 0]
    if not x:
        raise ValueError("Could not derive neutral irrelevant-clamp value.")
    value = float(np.median(x))
    if value.is_integer():
        value = int(value)
    return Clamp(
        quantity="the average lifespan in years of a giraffe",
        value=value,
        instrumental=False,
    )
