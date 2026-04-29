---
{
  "title": "Cognitive Prompt Templates for LLM-Powered Memory Tasks",
  "summary": "This module contains all LLM prompt templates used by `CognitiveProcessor` for sentiment analysis, significance gating, fact extraction, entity extraction, and self-reflection. Each template embeds a `[TASK:xxx]` routing marker so that `HeuristicEngine` can dispatch to its regex fallbacks without parsing the full prompt.",
  "concepts": [
    "SENTIMENT_PROMPT",
    "SIGNIFICANCE_PROMPT",
    "FACT_EXTRACTION_PROMPT",
    "ENTITY_EXTRACTION_PROMPT",
    "SELF_REFLECTION_PROMPT",
    "REFLECT_PROMPT",
    "task routing",
    "prompt templates",
    "CognitiveProcessor",
    "HeuristicEngine routing"
  ],
  "categories": [
    "cognitive engine",
    "prompt engineering",
    "memory pipeline",
    "runtime"
  ],
  "source_docs": [
    "c3415912b3fb0c62"
  ],
  "backlinks": null,
  "word_count": 473,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

Centralizing prompt templates in one module makes them easy to review, audit, and version independently from the orchestration logic in `CognitiveProcessor`. Every prompt follows the same structure: a routing marker, a brief role description, the input fields, and an explicit JSON output schema. Six templates cover the full cognitive pipeline.

## The [TASK:xxx] Routing Convention

Every prompt starts with a `[TASK:xxx]` marker on the first line:

```
[TASK:sentiment]
Analyze the emotional tone of this text.
```

`CognitiveProcessor` constructs prompts from these templates and sends them to whatever `CognitiveEngine` is configured. `HeuristicEngine` uses `_extract_task_marker()` in `engine.py` to parse this marker and dispatch to the matching regex method without re-implementing task identification. This ensures the same prompt string works correctly with both LLM engines and the regex fallback.

## Prompt Inventory

### SENTIMENT_PROMPT
Returns a `SomaticMarker` JSON object:
```json
{"valence": -1.0..1.0, "arousal": 0.0..1.0, "label": "<emotion>"}
```
The fixed label set (joy, gratitude, curiosity, frustration, confusion, sadness, excitement, neutral) keeps the output space predictable. The `valence` dimension captures positive/negative tone; `arousal` captures activation level (calm vs. excited). Together they encode a dimensional model of emotion rather than flat categories.

### SIGNIFICANCE_PROMPT
Assesses whether the current interaction is worth long-term storage. Includes `recent_summaries` context so the model can penalize novelty-free repetitions — a conversation the soul has had many times before should score lower than a genuinely new topic.

### FACT_EXTRACTION_PROMPT
Returns a JSON array of `{content, importance}` objects. The explicit instruction "Return [] if no notable facts" prevents the model from hallucinating facts to satisfy the format requirement — a critical safeguard for memory integrity.

### ENTITY_EXTRACTION_PROMPT
Extracts named entities with typed relations. The `relation` field captures how the user relates to the entity (uses, builds, learns, works_at, prefers) to enrich the soul's knowledge graph beyond simple entity counts.

### SELF_REFLECTION_PROMPT
Asks the soul to reflect on who it is becoming based on recent episodes. The soul is addressed by name and given its current self-understanding as context, grounding reflection in accumulated identity rather than generating it from scratch.

### REFLECT_PROMPT
A shorter template for scheduled autonomous reflection runs. Distinct from `SELF_REFLECTION_PROMPT` to allow different tuning — session-end reflection can be more detailed, while scheduled background reflection uses this lighter template to keep costs low.

## Design Principles

- **Explicit JSON schemas in every prompt**: Reduces parse failures versus natural language output instructions.
- **No system prompt separation**: Templates are self-contained, so they work uniformly across all `CognitiveEngine` implementations regardless of whether the underlying API supports system messages.
- **Minimal examples**: Prompts rely on schema and task description rather than few-shot examples, keeping per-call token cost low.

## Known Gaps

No versioning system exists for prompt templates. Changing a template immediately affects all running souls. A template registry with version tags would allow gradual rollout of improved prompts and A/B testing across soul instances.