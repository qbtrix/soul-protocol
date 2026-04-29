---
{
  "title": "LLM-as-Judge — Six-Dimension Response Quality Scorer with Position-Bias Mitigation",
  "summary": "Implements the LLM-as-judge evaluation methodology with six quality dimensions scored on a 1-10 scale, supporting both single-response scoring and pairwise A/B comparison. The pairwise mode randomly assigns responses to positions A and B on each call to eliminate position bias from judge models that favor whichever response appears first.",
  "concepts": [
    "LLM-as-judge",
    "pairwise comparison",
    "position bias",
    "quality dimensions",
    "memory utilization",
    "personality consistency",
    "emotional awareness",
    "naturalness",
    "ResponseJudge",
    "JudgeScore",
    "JudgeResult",
    "JSON parsing",
    "score clamping",
    "QualityDimension",
    "inter-rater reliability"
  ],
  "categories": [
    "research",
    "quality-evaluation",
    "llm-judge",
    "soul-protocol"
  ],
  "source_docs": [
    "9d878d3f6f8d950b"
  ],
  "backlinks": null,
  "word_count": 424,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Human annotation at scale is expensive and slow. LLM-as-judge is a validated alternative where a capable judge model scores responses against a rubric. The `ResponseJudge` class operationalizes this for Soul Protocol by scoring on six dimensions that map directly to soul capabilities, making the connection between feature and quality measurable.

## Six Quality Dimensions

```python
class QualityDimension(Enum):
    MEMORY_UTILIZATION      # references past interactions
    PERSONALITY_CONSISTENCY # matches described personality
    EMOTIONAL_AWARENESS     # acknowledges user's emotional state
    CONTINUITY              # feels like the same entity across turns
    HELPFULNESS             # actually useful and relevant
    NATURALNESS             # sounds like a real personality, not a generic bot
```

Dimensions are passed to the judge as structured English descriptions, not enum names, so the judge model doesn't need to know the codebase to score correctly.

## Pairwise Comparison with Position-Bias Mitigation

Research has consistently shown that LLM judges prefer whichever response appears first in the prompt. `compare_pair()` randomizes which response is presented as A vs. B on every call:

```python
soul_is_a = random.random() < 0.5
if soul_is_a:
    response_a, response_b = with_soul, without_soul
else:
    response_a, response_b = without_soul, with_soul
```

After receiving the winner declaration, the code maps `"A"` or `"B"` back to `"soul"` or `"baseline"` using the `soul_is_a` flag. This eliminates systematic position bias from the win rate statistics.

## Score Ordering

The pairwise prompt explicitly instructs the judge to score BOTH responses on ALL dimensions before declaring a winner. Without this ordering constraint, judges tend to justify their predetermined winner preference through post-hoc scoring, inflating winner scores artificially.

## JSON Parsing with Fallback

Judge responses are expected as raw JSON (no markdown fences). The `_parse_judge_response()` function first attempts direct parsing, then falls back to regex extraction of the first `{...}` block. If both fail, an empty dict is returned and all scores default to 0.0. This prevents a malformed judge response from aborting a 30-variation benchmark run.

## Score Clamping

`JudgeScore.__post_init__` clamps scores to `[1.0, 10.0]`. This prevents edge cases where the judge hallucinates a score of 0 or 11 from propagating into confidence interval calculations.

## Dimension Labeling in Results

After collecting A/B scores, dimensions are relabeled from `"a:memory"` / `"b:memory"` to `"soul:memory"` / `"baseline:memory"`, making downstream analysis readable without needing to track the A/B assignment.

## Known Gaps

- `score_single()` (single-response scoring without a baseline comparison) is implemented but not used by any current runner — only `compare_pair()` is called in practice.
- The 1-10 scale has no defined anchors beyond "1 = terrible, 10 = exceptional", which may introduce judge-to-judge calibration differences that inflate inter-rater agreement estimates.