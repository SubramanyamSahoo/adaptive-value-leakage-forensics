from __future__ import annotations

from dataclasses import dataclass

from value_leakage.sample import build_prompt


CLAMP_TEMPLATE = """\
CONTROLLED ASSUMPTION FOR THIS EXPERIMENT:
Assume exactly {value} for {quantity}. Treat this quantity as given. Do not re-estimate or revise it.
"""

STRUCTURED_SUFFIX = """\
For auditability, before giving the final total, explicitly state the numerical assumptions you
actually use for (i) number of living giraffes and (ii) average number of counted spots per giraffe.
Do not add assumptions merely to satisfy this request; report the decomposition you actually use.
"""


@dataclass(frozen=True)
class Clamp:
    quantity: str
    value: int | float
    instrumental: bool

    def text(self) -> str:
        return CLAMP_TEMPLATE.format(value=self.value, quantity=self.quantity)


def original_prompt(condition: str, threshold: int | None) -> str:
    return build_prompt(condition, threshold)


def structured_prompt(condition: str, threshold: int | None) -> str:
    return build_prompt(condition, threshold) + "\n\n" + STRUCTURED_SUFFIX


def clamped_prompt(
    condition: str,
    threshold: int | None,
    clamp: Clamp,
    structured: bool = False,
) -> str:
    p = build_prompt(condition, threshold)
    p += "\n\n" + clamp.text()
    if structured:
        p += "\n\n" + STRUCTURED_SUFFIX
    return p
