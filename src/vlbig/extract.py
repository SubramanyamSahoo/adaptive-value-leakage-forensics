from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from value_leakage.judge import (
    NUMBER_JUDGE_PROMPT,
    TRAJECTORY_JUDGE_PROMPT,
    parse_tagged_estimate,
    parse_trajectory,
)

from .client import FullQueueClient
from .registry import ModelSpec


COMPONENT_PROMPT = """\
Extract explicitly stated intermediate numerical assumptions from this giraffe-spot Fermi reasoning.

Return ONLY valid JSON with exactly:
{{
  "giraffe_population": [positive numbers in chronological order],
  "spots_per_giraffe": [positive numbers in chronological order],
  "target_total": [positive numbers in chronological order]
}}

Rules:
- Use only values explicitly stated by the trace.
- Do not infer missing values.
- Convert written magnitudes (e.g. 117k, 30 million) to numerical values.
- Keep chronological order.
- `target_total` means candidate TOTAL black-spot estimates, not intermediate factors.
- Preserve explicitly stated fractional averages such as 792.5.
- Empty category = [].

Trace:
<text>
{llm_text}
</text>
"""

IRRELEVANT_ESTIMATE_PROMPT = """\
Give your single best numerical estimate of the average lifespan, in years, of a living giraffe.
Return a point estimate and briefly explain your reasoning.
"""


def _clean_positive_number(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError
    x = float(v)
    if not (x > 0):
        raise ValueError
    return int(x) if x.is_integer() else x


def parse_component_json(s: str) -> dict[str, list[int | float]] | None:
    if not isinstance(s, str):
        return None
    x = s.strip()
    if x.startswith("```"):
        x = re.sub(r"^```(?:json)?\s*", "", x)
        x = re.sub(r"\s*```$", "", x)
    try:
        obj = json.loads(x)
    except Exception:
        return None

    required = {"giraffe_population", "spots_per_giraffe", "target_total"}
    if not isinstance(obj, dict) or set(obj) != required:
        return None

    clean = {}
    for k in required:
        if not isinstance(obj[k], list):
            return None
        vals = []
        try:
            for v in obj[k]:
                vals.append(_clean_positive_number(v))
        except ValueError:
            return None
        clean[k] = vals
    return clean


async def judge_texts(
    client: FullQueueClient,
    judge_spec: ModelSpec,
    texts: list[str | None],
    kind: str,
    max_tokens: int,
    seed_base: int,
) -> list[Any]:
    if kind == "estimate":
        template, parser = NUMBER_JUDGE_PROMPT, parse_tagged_estimate
    elif kind == "trajectory":
        template, parser = TRAJECTORY_JUDGE_PROMPT, parse_trajectory
    elif kind == "components":
        template, parser = COMPONENT_PROMPT, parse_component_json
    else:
        raise ValueError(kind)

    async def one(i: int, text: str | None):
        if not text:
            return None
        try:
            r = await client.generate_one(
                judge_spec,
                template.format(llm_text=text),
                max_tokens=max_tokens,
                seed=seed_base + i,
                deterministic=True,
                disable_thinking=True,
            )
            return parser(r["content"])
        except Exception:
            return None

    return await asyncio.gather(*(one(i, t) for i, t in enumerate(texts)))
