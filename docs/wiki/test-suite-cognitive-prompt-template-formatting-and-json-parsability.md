---
{
  "title": "Test Suite: Cognitive Prompt Template Formatting and JSON Parsability",
  "summary": "Tests that every cognitive prompt template in Soul Protocol formats without error and produces output parseable by the JSON extraction helper. Validates both the template variables contract and the round-trip between typical LLM responses and the `_parse_json` function.",
  "concepts": [
    "prompt templates",
    "SENTIMENT_PROMPT",
    "SIGNIFICANCE_PROMPT",
    "FACT_EXTRACTION_PROMPT",
    "ENTITY_EXTRACTION_PROMPT",
    "REFLECT_PROMPT",
    "SELF_REFLECTION_PROMPT",
    "_parse_json",
    "task marker",
    "LLM response parsing",
    "format validation",
    "cognitive prompts"
  ],
  "categories": [
    "testing",
    "cognitive processing",
    "prompt engineering",
    "LLM integration",
    "test"
  ],
  "source_docs": [
    "11d90b1a04b4fb7a"
  ],
  "backlinks": null,
  "word_count": 329,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`test_prompts.py` is a contract test suite for the six prompt templates that drive Soul Protocol's cognitive processing. Each template is a parameterized string that gets sent to an LLM; if a template breaks (missing variable, malformed placeholder), the entire observe pipeline fails at runtime. These tests catch that class of bug before deployment.

## Prompt Templates Tested

The suite imports and validates all six production prompts:

```python
from soul_protocol.runtime.cognitive.prompts import (
    ENTITY_EXTRACTION_PROMPT,
    FACT_EXTRACTION_PROMPT,
    REFLECT_PROMPT,
    SELF_REFLECTION_PROMPT,
    SENTIMENT_PROMPT,
    SIGNIFICANCE_PROMPT,
)
```

## Template Formatting Validation

`TestPromptFormatting` calls `.format()` on each template with all required variables and asserts:

1. No `KeyError` is raised (all placeholders are supplied)
2. Injected values appear in the formatted output
3. The task marker (e.g., `[TASK:sentiment]`) is preserved in the output

```python
def test_sentiment_prompt_formats(self):
    result = SENTIMENT_PROMPT.format(text="I am happy today")
    assert "I am happy today" in result
    assert "[TASK:sentiment]" in result
```

The task marker assertion is important because `_extract_task_marker` relies on it to dispatch to the correct processing function. A prompt that loses its marker would route to the wrong handler silently.

## JSON Response Parsability

`TestPromptJsonExamples` tests the other half of the round-trip: given a typical LLM response for each prompt, does `_parse_json` extract a valid structured object?

```python
def test_sentiment_response(self):
    response = json.dumps({"valence": 0.8, "arousal": 0.6, "label": "happy"})
    result = _parse_json(response)
    assert result["valence"] == 0.8

def test_fenced_sentiment_response(self):
    response = "```json\n{\"valence\": 0.8}\n```"
    result = _parse_json(response)
    assert result["valence"] == 0.8

def test_preamble_fact_response(self):
    response = "Here are the facts:\n[{\"content\": \"User is Alice\"}]"
    result = _parse_json(response)
    assert result[0]["content"] == "User is Alice"
```

These tests document the real-world LLM response patterns the parser must handle and serve as regression tests when `_parse_json` is refactored.

## Why Separate from test_engine.py

These tests focus purely on the text layer: prompt strings and their parsing. `test_engine.py` tests the behavioral layer: routing, fallback, and processor integration. Keeping them separate makes failures easier to diagnose.

## Known Gaps

No TODOs flagged. Suite was created at v0.2.1 alongside the prompt module introduction.