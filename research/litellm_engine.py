# litellm_engine.py — CognitiveEngine backed by any model via LiteLLM proxy.
# Supports GPT-4o, Gemini, DeepSeek, Llama, Qwen, etc. through a single
# OpenAI-compatible endpoint. Used for multi-model judge evaluation.
# Created: 2026-03-06

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field


@dataclass
class UsageTracker:
    """Track API call counts and token usage."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.monotonic)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.start_time

    def summary(self) -> str:
        return (
            f"Calls: {self.calls} ({self.errors} errors) | "
            f"Tokens: {self.input_tokens:,} in, {self.output_tokens:,} out | "
            f"Time: {self.elapsed:.1f}s"
        )


class LiteLLMEngine:
    """CognitiveEngine implementation using any model via a LiteLLM proxy.

    Implements the same interface as HaikuCognitiveEngine:
        async def think(self, prompt: str) -> str

    Connects to an OpenAI-compatible endpoint (LiteLLM proxy) and routes
    to the specified model. Supports rate limiting via semaphore.
    """

    def __init__(
        self,
        model: str,
        *,
        max_tokens: int = 2048,
        max_concurrent: int = 10,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.3,
    ) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.usage = UsageTracker()

        self._client = AsyncOpenAI(
            base_url=base_url
            or os.environ.get("LITELLM_PROXY_URL", "https://litellm.hzd.interacly.com"),
            api_key=api_key or os.environ.get("LITELLM_API_KEY", ""),
        )

    async def think(self, prompt: str) -> str:
        """Send prompt to the model via LiteLLM proxy and return response text."""
        async with self._semaphore:
            try:
                response = await self._client.chat.completions.create(
                    model=self.model,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                self.usage.calls += 1
                if response.usage:
                    self.usage.input_tokens += response.usage.prompt_tokens or 0
                    self.usage.output_tokens += response.usage.completion_tokens or 0
                return response.choices[0].message.content or ""
            except Exception as e:
                self.usage.errors += 1
                raise RuntimeError(f"LiteLLM call failed ({self.model}): {e}") from e
