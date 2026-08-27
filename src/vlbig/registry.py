from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model_id: str
    release_year: int
    family: str
    reasoning_parser: Optional[str]
    language_model_only: bool
    sampling: dict
    judge_sampling: dict
    server_args: tuple[str, ...]
    source_url: str
    source_note: str


MODELS: dict[str, ModelSpec] = {
    "qwen36_27b": ModelSpec(
        key="qwen36_27b",
        model_id="Qwen/Qwen3.6-27B",
        release_year=2026,
        family="qwen",
        reasoning_parser="qwen3",
        language_model_only=True,
        sampling={
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 0.0,
            "repetition_penalty": 1.0,
        },
        judge_sampling={
            "temperature": 0.7,
            "top_p": 0.80,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
            "repetition_penalty": 1.0,
        },
        server_args=(
            "--reasoning-parser", "qwen3",
            "--language-model-only",
            "--gdn-prefill-backend", "triton",
            "--enforce-eager",
        ),
        source_url="https://huggingface.co/Qwen/Qwen3.6-27B",
        source_note="Primary dense 27B Donation Bet target; thinking kept on for target generations.",
    ),
    "qwen38_27b": ModelSpec(
        key="qwen38_27b",
        model_id="Qwen/Qwen3.8-27B",
        release_year=2026,
        family="qwen",
        reasoning_parser="qwen3",
        language_model_only=True,
        sampling={
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 0.0,
            "repetition_penalty": 1.0,
        },
        judge_sampling={
            "temperature": 0.7,
            "top_p": 0.80,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
            "repetition_penalty": 1.0,
        },
        server_args=(
            "--reasoning-parser", "qwen3",
            "--language-model-only",
            "--gdn-prefill-backend", "triton",
            "--enforce-eager",
        ),
        source_url="https://huggingface.co/Qwen/Qwen3.8-27B",
        source_note="Primary large judge candidate; non-thinking mode when judging.",
    ),
    "granite42_30b": ModelSpec(
        key="granite42_30b",
        model_id="ibm-granite/granite-4.2-30b",
        release_year=2026,
        family="granite",
        reasoning_parser=None,
        language_model_only=False,
        sampling={
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": None,
            "min_p": None,
            "presence_penalty": 0.0,
            "repetition_penalty": 1.0,
        },
        judge_sampling={
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": None,
            "min_p": None,
            "presence_penalty": 0.0,
            "repetition_penalty": 1.0,
        },
        server_args=("--enforce-eager",),
        source_url="https://huggingface.co/ibm-granite/granite-4.2-30b",
        source_note="Dense 30B cross-family judge candidate; released 2026-08-25.",
    ),
}

DEFAULT_TARGETS = ("qwen36_27b",)
DEFAULT_JUDGE_CANDIDATES = ("qwen38_27b", "granite42_30b")
OPTIONAL_ROBUSTNESS_TARGETS = ("qwen38_27b",)


def get_model(key: str) -> ModelSpec:
    if key not in MODELS:
        raise KeyError(f"Unknown large-model key {key!r}; available={tuple(MODELS)}")
    m = MODELS[key]
    if m.release_year != 2026:
        raise ValueError(f"{m.model_id} is not a 2026 model.")
    return m
