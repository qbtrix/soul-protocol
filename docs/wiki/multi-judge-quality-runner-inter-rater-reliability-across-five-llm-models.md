---
{
  "title": "Multi-Judge Quality Runner — Inter-Rater Reliability Across Five LLM Models",
  "summary": "Runs Soul Protocol's four quality test scenarios with five different judge models (Haiku, Gemini 3 Flash, Gemini 2.5 Flash Lite, DeepSeek V3, Llama 3.3 70B) to measure inter-rater reliability, ensuring that quality advantages observed for soul-enabled agents are not artifacts of a single judge model's preferences or biases.",
  "concepts": [
    "multi-judge",
    "inter-rater reliability",
    "Haiku",
    "Gemini",
    "DeepSeek",
    "Llama",
    "LiteLLMEngine",
    "HaikuCognitiveEngine",
    "TEST_REGISTRY",
    "JUDGE_MODELS",
    "scorecard",
    "shared agent engine",
    "model bias",
    "soul score",
    "baseline score"
  ],
  "categories": [
    "research",
    "quality-evaluation",
    "multi-model",
    "soul-protocol"
  ],
  "source_docs": [
    "533726566c2fdebb"
  ],
  "backlinks": null,
  "word_count": 419,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

A single judge model may have systematic biases — preferring verbose responses, certain writing styles, or outputs from the same model family it belongs to. If Soul Protocol's soul condition always generates responses using Claude Haiku and Haiku judges the outputs, there is an obvious model-family bias risk. Multi-judge validation eliminates this by requiring agreement across diverse model architectures.

## Judge Model Registry

```python
JUDGE_MODELS = {
    "haiku": {"type": "haiku"},
    "gemini-3-flash": {"type": "litellm", "model": "gemini/gemini-3-flash"},
    "gemini-2.5-flash-lite": {"type": "litellm", "model": "gemini/gemini-2.5-flash-lite"},
    "deepseek-v3": {"type": "litellm", "model": "deepseek-chat"},
    "llama-3.3-70b": {"type": "litellm", "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
}
```

Each judge is instantiated via `_make_engine()`, which returns a `HaikuCognitiveEngine` for Haiku and a `LiteLLMEngine` for all others.

## Test Registry

```python
TEST_REGISTRY = {
    "response": ("Response Quality", test_response_quality),
    "personality": ("Personality Consistency", test_personality_consistency),
    "recall": ("Hard Recall", test_hard_recall),
    "emotional": ("Emotional Continuity", test_emotional_continuity),
}
```

Test functions are imported from `test_scenarios.py` (the earlier, simpler predecessor to `scenario_generator.py` used by the enhanced runner).

## Shared Agent Engine

A single `HaikuCognitiveEngine` is shared across all tests as the agent engine, while each judge gets its own separate engine. This design ensures the responses being judged are identical across all judge models — differences in scores come from judge differences, not agent differences.

## Inter-Rater Agreement Calculation

After all tests and judges complete, the runner computes the standard deviation of soul scores across judges for each test type. Low standard deviation indicates high inter-rater agreement — all judges agree the soul condition is better (or worse) by approximately the same margin.

## Scorecard Output

A formatted table is printed showing `soul_score/baseline_score` per test per judge, with an "Overall" row averaging across tests:

```
  Test                    | haiku            | gemini-3-flash   | deepseek-v3
  Response Quality        | 7.8/5.4          | 7.2/5.1          | 7.6/5.3
  Hard Recall             | 8.1/4.2          | 7.9/4.5          | 8.0/4.1
  Overall                 | 7.8/4.7          | 7.5/4.8          | 7.7/4.7
```

## Result Persistence

Results are saved to JSON in the output directory with a UTC timestamp. The JSON includes raw per-test-per-judge results plus the scorecard string, enabling offline analysis.

## Known Gaps

- Each judge runs the full test independently (including agent soul creation and conversation replay), rather than sharing pre-generated responses. This makes results noisier across judges because the soul's memory state may differ between runs due to random seeds.
- There is no CLI argument for `--output`, so the output directory is hardcoded to `research/results/multi_judge`.
- The `test_scenarios.py` module this imports from is an earlier, less-varied version than `scenario_generator.py` used by the enhanced runner, so multi-judge and enhanced runner results are not directly comparable.