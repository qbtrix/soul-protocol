---
{
  "title": "Haiku Cognitive Engine — Claude Haiku LLM Backend with Rate Limiting",
  "summary": "A thin async wrapper around the Anthropic SDK that implements the single-method `CognitiveEngine` protocol (`async think(prompt) -\u003e str`) using Claude Haiku. Includes semaphore-based concurrency control, retry logic for rate limits and timeouts, and a `UsageTracker` dataclass for cost and throughput monitoring.",
  "concepts": [
    "CognitiveEngine",
    "Claude Haiku",
    "asyncio",
    "semaphore",
    "rate limiting",
    "retry logic",
    "UsageTracker",
    "token counting",
    "cost estimation",
    "Anthropic SDK",
    "think protocol",
    "concurrency control",
    "exponential backoff",
    "timeout"
  ],
  "categories": [
    "research",
    "llm-backend",
    "infrastructure",
    "soul-protocol"
  ],
  "source_docs": [
    "b8a436e4037b1e8b"
  ],
  "backlinks": null,
  "word_count": 417,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`HaikuCognitiveEngine` is the primary LLM backend used across Soul Protocol's research infrastructure. It exists because research scripts need to fire many parallel LLM calls (significance scoring, memory extraction, judge scoring) while staying within Anthropic's rate limits and keeping costs visible.

## CognitiveEngine Protocol

The engine implements a minimal one-method interface:

```python
async def think(self, prompt: str) -> str
```

This duck-typed protocol allows research components to swap in a `LiteLLMEngine` or a mock without changing call sites — all callers just call `.think(prompt)`.

## Concurrency Control

A `asyncio.Semaphore(max_concurrent)` (default 20) gates every call. Without this guard, spinning up hundreds of `asyncio.gather` tasks would all hit the Anthropic API simultaneously, triggering HTTP 429 rate-limit errors and cascading failures in long benchmark runs.

```python
async with self._semaphore:
    # API call happens here
```

## Retry Logic

Each call gets up to 3 attempts:

1. **Timeout**: A 2-minute `asyncio.wait_for` wraps the API call. If the Anthropic API hangs (network partition, slow cold start), the timeout prevents indefinite blocking in long benchmarks.
2. **Rate limit (429)**: If the error string contains `"rate"` or `"429"`, the engine sleeps for `(attempt + 1) * 2` seconds (2s, 4s) before retrying. Exponential back-off keeps a stalled batch from hammering the API.
3. **Other exceptions**: Non-retryable errors are immediately re-raised after incrementing the error counter.

## Usage Tracking

`UsageTracker` is a dataclass that accumulates:

- `calls` and `errors` — total call volume and failure rate
- `input_tokens` / `output_tokens` — from Anthropic's response `.usage` field
- `start_time` — for throughput calculation

Derived properties compute `calls_per_second` and `estimated_cost_usd` using Haiku 4.5 pricing ($0.80/M input, $4.00/M output). This lets research scripts print a cost summary after each run, which is critical for budget-aware benchmark design.

```python
print(engine.usage.summary())
# Calls: 1240 (3 errors) | Tokens: 450,000 in, 120,000 out | Est. cost: $0.84 | Rate: 12.4 calls/s | Time: 100.0s
```

## Model Configuration

The model defaults to `claude-haiku-4-5-20251001` but is overridable at construction time. `max_tokens` defaults to 512, which is enough for JSON-structured judge outputs but may need increasing for longer responses (the enhanced runner sets it to 2048).

## Known Gaps

- **No jitter in back-off**: the retry sleep is deterministic (`attempt * 2`). Under high concurrency, all retrying coroutines sleep the same amount and then re-collide at the API.
- **No persistent cost ledger**: usage is in-memory only and lost if the process crashes mid-run.
- The 120-second timeout is fixed; very long prompts (e.g., 1000-turn scenario summaries) may legitimately need more time.