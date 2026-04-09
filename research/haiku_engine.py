# haiku_engine.py — CognitiveEngine backed by Claude Haiku for Tier 2 validation.
# Makes real LLM calls for sentiment, significance, fact extraction, entity extraction.
# Includes rate limiting and cost tracking.

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

    @property
    def calls_per_second(self) -> float:
        return self.calls / self.elapsed if self.elapsed > 0 else 0.0

    @property
    def estimated_cost_usd(self) -> float:
        # Haiku 4.5 pricing: $0.80/M input, $4.00/M output
        return (self.input_tokens * 0.80 + self.output_tokens * 4.00) / 1_000_000

    def summary(self) -> str:
        return (
            f"Calls: {self.calls} ({self.errors} errors) | "
            f"Tokens: {self.input_tokens:,} in, {self.output_tokens:,} out | "
            f"Est. cost: ${self.estimated_cost_usd:.4f} | "
            f"Rate: {self.calls_per_second:.1f} calls/s | "
            f"Time: {self.elapsed:.1f}s"
        )


class HaikuCognitiveEngine:
    """CognitiveEngine implementation using Claude Haiku.

    Implements the single-method protocol:
        async def think(self, prompt: str) -> str

    Features:
    - Async with semaphore-based rate limiting
    - Usage tracking (tokens, cost, errors)
    - Automatic retry on rate limit errors
    """

    def __init__(
        self,
        *,
        model: str = "claude-haiku-4-5-20251001",
        max_tokens: int = 512,
        max_concurrent: int = 20,
        api_key: str | None = None,
    ) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        )
        self._model = model
        self._max_tokens = max_tokens
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.usage = UsageTracker()

    async def think(self, prompt: str) -> str:
        """Send prompt to Haiku and return response text."""
        async with self._semaphore:
            for attempt in range(3):
                try:
                    response = await asyncio.wait_for(
                        self._client.messages.create(
                            model=self._model,
                            max_tokens=self._max_tokens,
                            messages=[{"role": "user", "content": prompt}],
                        ),
                        timeout=120,  # 2 minute timeout per API call
                    )
                    self.usage.calls += 1
                    self.usage.input_tokens += response.usage.input_tokens
                    self.usage.output_tokens += response.usage.output_tokens
                    return response.content[0].text

                except TimeoutError:
                    if attempt < 2:
                        continue
                    self.usage.errors += 1
                    raise RuntimeError("Haiku API call timed out after 120s")

                except Exception as e:
                    error_str = str(e).lower()
                    if "rate" in error_str or "429" in error_str:
                        wait = (attempt + 1) * 2
                        await asyncio.sleep(wait)
                        continue
                    self.usage.errors += 1
                    raise

            self.usage.errors += 1
            raise RuntimeError("Max retries exceeded for Haiku API call")
