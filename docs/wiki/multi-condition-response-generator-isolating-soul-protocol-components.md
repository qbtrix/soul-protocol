---
{
  "title": "Multi-Condition Response Generator — Isolating Soul Protocol Components",
  "summary": "Defines four experimental conditions (`FULL_SOUL`, `RAG_ONLY`, `PROMPT_PERSONALITY`, `BARE_BASELINE`) and the `MultiConditionResponder` class, which generates responses under each condition against the same underlying soul state to isolate the contribution of personality, memory, and emotional scaffolding to response quality.",
  "concepts": [
    "ablation conditions",
    "FULL_SOUL",
    "RAG_ONLY",
    "PROMPT_PERSONALITY",
    "BARE_BASELINE",
    "MultiConditionResponder",
    "soul.context_for",
    "soul.to_system_prompt",
    "soul.recall",
    "memory formatting",
    "parallel generation",
    "asyncio",
    "controlled variable",
    "ConditionResponse"
  ],
  "categories": [
    "research",
    "quality-evaluation",
    "ablation-study",
    "soul-protocol"
  ],
  "source_docs": [
    "722fa159f78423ec"
  ],
  "backlinks": null,
  "word_count": 357,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

`conditions.py` implements the controlled variable methodology for Soul Protocol's quality ablation. The core insight is that running all four conditions against the same `Soul` instance — same memories, same personality, same emotional state — ensures that any quality differences measured by the judge are caused by what information is presented to the LLM, not by differences in accumulated soul state.

## Four Conditions

```python
class Condition(Enum):
    FULL_SOUL = "full_soul"             # personality + memories + somatic state + bond
    RAG_ONLY = "rag_only"               # generic prompt + raw memory retrieval
    PROMPT_PERSONALITY = "prompt_personality"  # OCEAN prompt only, no memories
    BARE_BASELINE = "bare_baseline"     # generic prompt, nothing
```

Each condition changes only the information flow to the LLM:
- **System prompt**: personality-modulated (`soul.to_system_prompt()`) vs. generic
- **Context**: full soul context vs. raw memories vs. nothing

## Key Design: Same Data, Different Presentation

For RAG_ONLY, the code calls the same `soul.recall(user_message, limit=5)` as FULL_SOUL — retrieving the same memories. `_format_memories_as_context()` strips somatic markers, bond info, and personality-modulated language, returning only fact text. This isolates memory from emotional framing.

```python
def _format_memories_as_context(memories: list[MemoryEntry]) -> str:
    lines = ["[Recalled memories]"]
    for i, mem in enumerate(memories, 1):
        lines.append(f"  {i}. {mem.content}")
    return "\n".join(lines)
```

## Parallel Generation

`generate_all()` creates `asyncio.Task` objects for all four conditions simultaneously:

```python
tasks = {cond: asyncio.create_task(self.generate(user_message, cond)) for cond in Condition}
```

Because all four conditions read soul state (no writes) and call the LLM independently, parallel execution is safe and reduces wall-clock time to roughly one LLM call's latency instead of four.

## Context Inclusion

`ConditionResponse` captures not just the response text but the system prompt and context string injected for that condition. Downstream judges and analysts can inspect exactly what the model was told, enabling debugging when a condition underperforms.

## Known Gaps

- `generate_all()` uses `asyncio.create_task` but then awaits each task sequentially in a loop rather than using `asyncio.gather`. Under the semaphore, this means tasks are created but may not actually run in parallel depending on the event loop schedule.
- PROMPT_PERSONALITY constructs the personality prompt internally rather than reusing `soul.to_system_prompt()`, which could cause the two to diverge if the soul's system prompt template changes.