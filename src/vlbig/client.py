from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from openai import AsyncOpenAI

from .registry import ModelSpec


def split_trace(message: Any) -> tuple[str, str, str]:
    data = message.model_dump() if hasattr(message, "model_dump") else dict(message)
    content = str(data.get("content") or "")
    reasoning = str(
        data.get("reasoning_content")
        or data.get("reasoning")
        or data.get("thinking")
        or ""
    )
    if reasoning:
        return reasoning, content, "reasoning_content"
    if "<think>" in content and "</think>" in content:
        a = content.find("<think>") + len("<think>")
        b = content.find("</think>", a)
        return content[a:b], content[b + len("</think>"):].lstrip(), "inline_think"
    return "", content, "no_reasoning_trace"


class FullQueueClient:
    """Keep the full logical queue live; vLLM owns physical CUDA batching."""

    def __init__(self, base_url: str, queue_size: int):
        if queue_size < 1:
            raise ValueError("queue_size must be >= 1")
        limits = httpx.Limits(
            max_connections=queue_size,
            max_keepalive_connections=queue_size,
        )
        http_client = httpx.AsyncClient(limits=limits, timeout=None)
        self.client = AsyncOpenAI(
            base_url=base_url.rstrip("/") + "/v1",
            api_key="EMPTY",
            http_client=http_client,
            max_retries=2,
        )

    async def generate_one(
        self,
        spec: ModelSpec,
        prompt: str,
        max_tokens: int,
        seed: int,
        deterministic: bool = False,
        disable_thinking: bool = False,
    ) -> dict[str, Any]:
        if max_tokens < 1:
            raise ValueError("max_tokens must be explicitly positive.")

        # Judges follow each model's official non-thinking sampling recipe.
        # The fixed seed provides reproducibility without forcing unsupported greedy settings.
        s = spec.judge_sampling if disable_thinking else spec.sampling
        use_forced_greedy = bool(deterministic and not disable_thinking)

        extra: dict[str, Any] = {}
        if s.get("top_k") is not None:
            extra["top_k"] = 1 if use_forced_greedy else int(s["top_k"])
        if s.get("min_p") is not None:
            extra["min_p"] = float(s["min_p"])
        if s.get("repetition_penalty") is not None:
            extra["repetition_penalty"] = float(s["repetition_penalty"])

        if disable_thinking and spec.family in {"qwen", "granite"}:
            kwargs = {"enable_thinking": False}
            if spec.family == "qwen":
                kwargs["preserve_thinking"] = False
            extra["chat_template_kwargs"] = kwargs

        t0 = time.perf_counter()
        r = await self.client.chat.completions.create(
            model=spec.model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.0 if use_forced_greedy else float(s["temperature"]),
            top_p=1.0 if use_forced_greedy else float(s["top_p"]),
            presence_penalty=0.0 if use_forced_greedy else float(s["presence_penalty"]),
            seed=int(seed),
            extra_body=extra,
        )
        latency = time.perf_counter() - t0
        reasoning, content, trace_source = split_trace(r.choices[0].message)
        usage = r.usage.model_dump() if r.usage else {}
        return {
            "reasoning": reasoning,
            "content": content,
            "trace_source": trace_source,
            "finish_reason": r.choices[0].finish_reason,
            "usage": usage,
            "latency_s": latency,
            "sampling_mode": "model_card_nonthinking_seeded" if disable_thinking else (
                "greedy" if use_forced_greedy else "model_card_thinking_seeded"
            ),
        }

    async def generate_many(
        self,
        spec: ModelSpec,
        prompt: str,
        count: int,
        max_tokens: int,
        seed_base: int,
        deterministic: bool = False,
        disable_thinking: bool = False,
    ) -> list[dict[str, Any]]:
        if count < 1:
            raise ValueError("count must be explicitly positive.")

        async def one(i: int):
            try:
                return {
                    "i": i,
                    **await self.generate_one(
                        spec, prompt, max_tokens, seed_base + i,
                        deterministic=deterministic,
                        disable_thinking=disable_thinking,
                    )
                }
            except Exception as e:
                return {"i": i, "error": f"{type(e).__name__}: {e}"}

        return await asyncio.gather(*(one(i) for i in range(count)))

    async def close(self) -> None:
        await self.client.close()
