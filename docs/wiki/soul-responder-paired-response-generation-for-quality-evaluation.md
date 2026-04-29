---
{
  "title": "Soul Responder: Paired Response Generation for Quality Evaluation",
  "summary": "The `SoulResponder` class generates agent responses in two modes — enriched by a soul's personality and memories, or from a bare baseline — enabling paired comparisons that quantify whether having a soul actually improves output quality. It uses a dedicated `HaikuCognitiveEngine` for response generation, intentionally separate from any cognitive engine the soul uses internally.",
  "concepts": [
    "SoulResponder",
    "ResponsePair",
    "HaikuCognitiveEngine",
    "paired comparison",
    "BASELINE_SYSTEM_PROMPT",
    "soul context",
    "quality evaluation",
    "response generation",
    "prompt construction",
    "cognitive engine"
  ],
  "categories": [
    "research",
    "quality-evaluation",
    "response-generation",
    "soul-protocol"
  ],
  "source_docs": [
    "797424bee7009da6"
  ],
  "backlinks": null,
  "word_count": 459,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

The responder module exists to answer one concrete question: does injecting a soul's context into an LLM prompt produce meaningfully better responses? Without a rigorous paired comparison — the same message, same model, same temperature, only the system prompt and context differ — any quality claim is anecdote. `SoulResponder` operationalizes that comparison.

## Architecture

```python
class SoulResponder:
    def __init__(self, soul: Soul, engine: HaikuCognitiveEngine) -> None:
        self._soul = soul
        self._engine = engine
```

The constructor accepts both a `Soul` and a `HaikuCognitiveEngine`. The separation is intentional: a soul may run its own cognitive engine for internal tasks like sentiment analysis, reflection, and significance scoring. Billing those internal costs against the response-generation budget would obscure which pipeline component consumed which tokens. Passing a dedicated engine keeps the accounting clean.

## Prompt Construction

`_build_prompt(system, context, user_message)` assembles prompts in a fixed three-part structure:

1. **System block** — either the soul's compiled system prompt (personality, values, communication style) or `BASELINE_SYSTEM_PROMPT = "You are a helpful AI assistant. Be concise and helpful."` for the control condition.
2. **Context block** — for the soul path, recalled memories and current soul state (energy, mood, somatic markers). For the baseline, this block is empty.
3. **User message** — identical in both paths, ensuring the only variable is the soul context.

## Data Flow

```
user_message
  ├── generate_response()        → soul system prompt + recalled memories + message
  │     └── engine.complete()   → soul-enriched answer
  └── generate_response_no_soul() → BASELINE_SYSTEM_PROMPT + message
        └── engine.complete()   → bare-baseline answer
```

Both answers are collected into a `ResponsePair` dataclass alongside the soul's actual system prompt and context strings, giving evaluators full traceability into what information the soul-path had access to.

## ResponsePair

```python
@dataclass
class ResponsePair:
    user_message: str
    with_soul: str
    without_soul: str
    soul_system_prompt: str
    soul_context: str
    agent_name: str
```

Storing `soul_system_prompt` and `soul_context` on every pair is a defensive choice. Without them, a judge scoring "with_soul > baseline" cannot distinguish between a well-constructed soul context and a lucky generation. The attached context lets reviewers audit the inputs, not just the outputs.

## Integration with the Quality Pipeline

`SoulResponder` is consumed by `test_scenarios.py`, which drives the four core quality tests (response quality, personality consistency, hard recall, emotional continuity). The test runner calls `generate_response` and `generate_response_no_soul` for the same message, then passes the `ResponsePair` to a `ResponseJudge` for LLM-based evaluation.

## Known Gaps

- Memory recall within `generate_response` is performed at call time with no caching between turns in a multi-turn sequence. For long sessions this means repeated identical recalls. A turn-level context cache would reduce redundant queries.
- `BASELINE_SYSTEM_PROMPT` is a single short string. Ideally the baseline should also vary (e.g., a more capable generic prompt) to test whether the soul adds value over a well-engineered baseline, not just over a minimal one.
