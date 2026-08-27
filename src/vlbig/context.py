from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import Iterable

from transformers import AutoTokenizer

from .registry import ModelSpec


@lru_cache(maxsize=None)
def tokenizer_for(model_id: str):
    return AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)


def _token_count(ids) -> int:
    if isinstance(ids, Mapping):
        if "input_ids" not in ids:
            raise ValueError(f"Tokenizer mapping lacks input_ids: {ids.keys()}")
        ids = ids["input_ids"]
    if hasattr(ids, "tolist"):
        ids = ids.tolist()
    if isinstance(ids, tuple):
        ids = list(ids)
    if not isinstance(ids, list):
        raise TypeError(f"Unexpected token container: {type(ids)}")
    if not ids:
        return 0
    if isinstance(ids[0], (list, tuple)):
        if len(ids) != 1:
            raise ValueError("Expected exactly one chat example.")
        return len(ids[0])
    return len(ids)


def chat_prompt_tokens(spec: ModelSpec, prompt: str) -> int:
    tok = tokenizer_for(spec.model_id)
    ids = tok.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=True,
        add_generation_prompt=True,
    )
    n = _token_count(ids)
    if n <= 0:
        raise ValueError(f"Computed invalid prompt token count: {n}")
    return n


def required_context(spec: ModelSpec, prompts: Iterable[str], max_new_tokens: int) -> int:
    if max_new_tokens < 1:
        raise ValueError("max_new_tokens must be positive.")
    lengths = [chat_prompt_tokens(spec, p) for p in prompts]
    if not lengths:
        raise ValueError("At least one prompt is required.")
    return max(lengths) + int(max_new_tokens)
