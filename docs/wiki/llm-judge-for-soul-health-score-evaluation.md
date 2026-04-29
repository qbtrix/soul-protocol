---
{
  "title": "LLM Judge for Soul Health Score Evaluation",
  "summary": "Uses Claude Haiku as an independent LLM judge to evaluate sentiment accuracy and personality prompt quality beyond what word-list heuristics can measure, running all verdicts in parallel and comparing results against the heuristic baseline. Provides a cost-tracked, auditable layer of evaluation for D2 and D3.",
  "concepts": [
    "LLM judge",
    "Claude Haiku",
    "sentiment classification",
    "personality fidelity",
    "parallel evaluation",
    "asyncio.gather",
    "heuristic baseline",
    "cost tracking",
    "JudgeVerdict",
    "JudgeDimensionResult",
    "agreement_rate"
  ],
  "categories": [
    "evaluation",
    "llm-judge",
    "soul-health-score"
  ],
  "source_docs": [
    "6934054f24b846b3"
  ],
  "backlinks": null,
  "word_count": 397,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Heuristic evaluators (word lists, Pearson correlation, keyword matching) are fast and deterministic but miss nuance. "I didn't dislike it" is negative sentiment, but no keyword list catches double negation. LLM judges fill the gap—they evaluate the same cases using natural language reasoning, then the two approaches are compared.

## Architecture

All judge functions are async and accept a shared `HaikuCognitiveEngine` instance:
```python
engine = HaikuCognitiveEngine(model=model, max_concurrent=max_concurrent)
tasks = [judge_sentiment(engine), judge_personality(engine)]
results = await asyncio.gather(*tasks)
```

Running judges in parallel reduces wall-clock time from O(N) to O(1) bounded by `max_concurrent`. The engine's semaphore prevents overwhelming the API.

## Sentiment Judge (EI-1)

For each of the 61 corpus entries, `classify_one` runs in parallel:
1. Calls the heuristic `detect_sentiment()` to get a baseline label
2. Sends the text to Haiku with a structured prompt requesting exactly one label from the allowed set
3. Parses the JSON response, falling back to `label="error"` on parse failure
4. Records both `heuristic_correct` and `llm_correct` against ground truth

The `_strip_markdown` function handles a common LLM behavior: wrapping JSON in ` ```json ``` ` fences despite instructions not to. The regex extracts the inner content, preventing JSON parse failures from valid but fence-wrapped responses.

Aggregated output includes:
- `heuristic_accuracy` and `llm_accuracy` (for direct comparison)
- `agreement_rate` (how often they agree, regardless of correctness)
- `llm_only_correct` and `heuristic_only_correct` (where one outperforms the other)

## Personality Judge (D3)

Evaluates three OCEAN profiles (HighOpen, LowOpen, Balanced) by sending each soul's `to_system_prompt()` output to Haiku with a rubric covering:
- `trait_coverage`: all 5 OCEAN traits described behaviorally
- `comm_style_coverage`: warmth/verbosity/humor/emoji reflected
- `behavioral_consistency`: behaviors logically follow from trait values
- `specificity`: descriptions are concrete, not generic filler

Averages across all three profiles produce the dimension-level score.

## Cost Tracking

All API usage is tracked through `engine.usage`:
```python
output["usage"] = {
    "total_calls": engine.usage.calls,
    "input_tokens": engine.usage.input_tokens,
    "output_tokens": engine.usage.output_tokens,
    "estimated_cost_usd": round(engine.usage.estimated_cost_usd, 4),
}
```

This makes the judge economically auditable—operators know exactly what each eval run costs before deciding whether to run it in CI.

## Output

Results are saved to `research/eval/results/llm_judge_{timestamp}.json` automatically. The directory is created with `mkdir(parents=True, exist_ok=True)` to prevent failure on first run.

## Known Gaps

- Only D2 (sentiment) and D3 (personality) have LLM judges. D4-D7 have no LLM evaluation layer.
- The `_ARC_JUDGE_PROMPT` template is defined but no `judge_arc` function currently uses it—this is dead code from a planned EI-4 LLM judge that was not implemented.