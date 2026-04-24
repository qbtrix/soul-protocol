---
{
  "title": "Mem0 Comparison Benchmark — Soul Protocol vs. Vector Memory vs. Stateless Baseline",
  "summary": "Runs a three-way quality comparison between Soul Protocol, Mem0 (embedding-based vector memory), and a stateless baseline across four test types, producing a scorecard that quantifies what the soul stack adds beyond raw memory storage. The benchmark is designed to appear in the Soul Protocol research paper as evidence that personality, emotional tracking, and bond are not incidental features.",
  "concepts": [
    "Mem0",
    "mem0ai",
    "vector memory",
    "embedding search",
    "soul protocol comparison",
    "three-way benchmark",
    "Mem0Responder",
    "SoulResponder",
    "qdrant",
    "LiteLLM proxy",
    "personality comparison",
    "emotional continuity",
    "scorecard",
    "research paper",
    "baseline comparison"
  ],
  "categories": [
    "research",
    "benchmarking",
    "quality-evaluation",
    "soul-protocol"
  ],
  "source_docs": [
    "5d9dcdf67bd5ff4b"
  ],
  "backlinks": null,
  "word_count": 441,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Soul Protocol's core claim is that AI companion quality requires more than just memory retrieval — it requires personality, emotional state, and relationship tracking. Mem0 provides embedding-based memory without any of those layers, making it the ideal ablation point: it has memory but no soul.

This benchmark generates publishable evidence for the claim that `soul_score > mem0_score > baseline_score` across quality dimensions.

## Three Conditions

| Condition | Memory | Personality | Emotional State | Bond |
|-----------|--------|-------------|-----------------|------|
| Soul Protocol | Significance-gated, tiered | OCEAN model | Somatic markers | Yes |
| Mem0 | Embedding search (qdrant) | None | None | None |
| Baseline | None | None | None | None |

## Mem0Responder

`Mem0Responder` wraps the `mem0ai` library and implements the same `observe()` and `generate_response()` interface as `SoulResponder`. It stores full exchanges via `Memory.add()` and retrieves them via `Memory.search()`. Because Mem0's API is synchronous, all calls are made directly without `await`.

Mem0 is configured via environment variables:
- If `LITELLM_PROXY_URL` and `LITELLM_API_KEY` are set, it routes through the LiteLLM proxy (using Gemini embeddings and DeepSeek for memory extraction)
- Otherwise, it falls back to OpenAI defaults (requires `OPENAI_API_KEY`)

## Graceful Degradation When Mem0 is Unavailable

```python
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
```

If `mem0ai` is not installed, the `Mem0Responder` constructor raises a helpful `ImportError` rather than a cryptic `AttributeError`, and the benchmark prints an install instruction.

## Test Coverage

Four test types mirror the `enhanced_runner.py` suite:
- **response** — overall response quality on open-ended questions
- **personality** — whether personality consistency survives across turns
- **recall** — hard recall of planted facts after filler noise
- **emotional** — emotional continuity through valence shifts

Each test returns `soul_score`, `mem0_score`, and `baseline_score` (all means from pairwise judge comparisons).

## Result Output

Results are saved as JSON to the output directory with a timestamp, plus a human-readable scorecard printed to stdout:

```
Soul Protocol vs Mem0 vs Baseline
  Response Quality: Soul=7.8  Mem0=6.2  Baseline=5.1
  Hard Recall:      Soul=8.1  Mem0=7.4  Baseline=4.3
  ...
```

Agent and judge token usage is included in the metadata to make cost attribution transparent.

## Known Gaps

- Mem0 uses an in-memory Qdrant store (`on_disk: False`), so all vectors are lost between benchmark runs. Results from a single run are internally consistent but cannot accumulate across sessions.
- The benchmark currently runs tests sequentially per condition rather than in parallel, making it significantly slower than the enhanced runner.
- `Mem0Responder.search()` returns Mem0's native dict format but does not convert scores to a normalized range, so Mem0 retrieval quality cannot be directly compared to Soul Protocol's `recall()` scoring.