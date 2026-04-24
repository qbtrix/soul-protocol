---
{
  "title": "LCM Compaction Prompt Templates: SUMMARY and BULLETS",
  "summary": "This module provides the two LLM prompt templates used by `ThreeLevelCompactor` when a `CognitiveEngine` is available: `SUMMARY_PROMPT` for Level 1 prose summarization and `BULLETS_PROMPT` for Level 2 bullet-point compression. Both follow the `[TASK:xxx]` routing convention for compatibility with `HeuristicEngine`.",
  "concepts": [
    "SUMMARY_PROMPT",
    "BULLETS_PROMPT",
    "ThreeLevelCompactor",
    "context compaction",
    "LCM",
    "task routing",
    "CognitiveEngine",
    "HeuristicEngine",
    "context summarization",
    "prompt templates"
  ],
  "categories": [
    "context management",
    "LCM",
    "prompt engineering",
    "compaction"
  ],
  "source_docs": [
    "4691525f60b7a970"
  ],
  "backlinks": null,
  "word_count": 532,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

When `ThreeLevelCompactor` runs Level 1 or Level 2 compaction and a `CognitiveEngine` is available, it needs LLM prompts to drive summarization. These two templates are those prompts — minimal, explicit, and designed to minimize hallucination while maximizing compression. Each follows the `[TASK:xxx]` routing convention so they work with `HeuristicEngine` as well as LLM-backed engines.

## SUMMARY_PROMPT (Level 1)

```
[TASK:context_summary]
Summarize the following conversation messages into a concise prose paragraph.
Preserve all key facts, decisions, action items, and emotional tone.
Do NOT add information that isn't in the messages.

Messages:
{messages}

Write a single paragraph summary:
```

The critical instruction is "Do NOT add information that isn't in the messages." LLMs tend to fill conversational gaps with plausible-sounding facts when summarizing. This explicit prohibition reduces confabulation at the cost of slightly less fluent output — an acceptable trade for a memory system where factual accuracy is paramount.

The output format is a single prose paragraph. This keeps token overhead predictable and produces text that reads naturally as narrative context in the assembled window — useful when the assembled context is sent to an LLM that needs to understand the conversation arc, not just its facts.

## BULLETS_PROMPT (Level 2)

```
[TASK:context_bullets]
Compress the following text into a bullet-point list.
Each bullet should capture one distinct fact, decision, or action item.
Be concise but preserve all important information. Drop filler and pleasantries.

Text:
{text}

Bullet points:
```

Level 2 takes Level 1 prose summaries and compresses them further into discrete bullets. The format shift from prose to bullets trades readability for density — each bullet is independently parseable, which matters when the assembled context must convey many independent facts in minimal tokens.

"Drop filler and pleasantries" targets the tendency for Level 1 summaries to include conversational connective tissue ("The user mentioned that...", "It was noted that...") which adds tokens without contributing information. Bullets enforce a fact-per-line discipline that the prose format does not.

## [TASK:xxx] Routing Markers

Both templates include routing markers (`[TASK:context_summary]`, `[TASK:context_bullets]`) on the first line. `ThreeLevelCompactor` passes these prompts directly to `CognitiveEngine.think()`. When `HeuristicEngine` is the active engine (no LLM configured), `_extract_task_marker()` in `engine.py` parses these markers and routes to the appropriate fallback handler — for context compaction, the fallback skips to Level 3 truncation since the heuristic engine has no summarization capability.

## Template Variables

| Template | Variable | Content |
|----------|----------|---------|
| `SUMMARY_PROMPT` | `{messages}` | Formatted string of role + content pairs for the batch being summarized |
| `BULLETS_PROMPT` | `{text}` | The prose paragraph produced by a prior Level 1 summary |

## Design Trade-offs

- **Single paragraph output**: Keeps token overhead predictable; multi-paragraph summaries would defeat the purpose of compaction.
- **No explicit length constraint**: Relies on the LLM's natural conciseness combined with `CognitiveEngine`'s `max_tokens` parameter to bound output length.
- **No few-shot examples**: Would improve quality but add per-call token cost that compounds across many compaction rounds.

## Known Gaps

No template exists for Level 3 (TRUNCATED) compaction — that level is deterministic and requires no LLM. If future compaction levels are added (e.g., extreme single-sentence distillation), new templates must follow this module's pattern and register corresponding `HeuristicEngine` routing handlers.