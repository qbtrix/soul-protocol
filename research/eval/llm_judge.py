# llm_judge.py — LLM-based evaluator agents for Soul Health Score dimensions.
# Created: 2026-03-12 — Uses Claude Haiku as judge to evaluate sentiment accuracy,
#   personality fidelity, and emotional arc quality beyond what word-list heuristics can measure.
#
# Architecture:
#   - Each judge is an async function that takes a HaikuCognitiveEngine
#   - Judges run in parallel using asyncio.gather
#   - Results include both LLM scores and comparison against heuristic baseline
#   - Cost tracking via engine.usage
#
# Usage:
#   python -m research.eval.llm_judge [--dimensions 2,3] [--concurrent 10]

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from research.haiku_engine import HaikuCognitiveEngine

logger = logging.getLogger(__name__)

_CORPUS_PATH = Path(__file__).parent / "corpus" / "sentiment_labels.json"
_RESULTS_DIR = Path(__file__).parent / "results"

_MD_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def _strip_markdown(text: str) -> str:
    """Strip markdown code fences from LLM response to extract raw JSON."""
    text = text.strip()
    m = _MD_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class JudgeVerdict:
    """Single evaluation verdict from an LLM judge."""

    text: str
    expected_label: str
    heuristic_label: str
    llm_label: str
    llm_confidence: float  # 0-1
    llm_reasoning: str
    heuristic_correct: bool
    llm_correct: bool


@dataclass
class JudgeDimensionResult:
    """Aggregated results from LLM judging a dimension."""

    dimension_id: int
    dimension_name: str
    heuristic_accuracy: float
    llm_accuracy: float
    agreement_rate: float  # how often heuristic and LLM agree
    verdicts: list[JudgeVerdict] = field(default_factory=list)
    llm_only_correct: int = 0  # cases where LLM got it right but heuristic didn't
    heuristic_only_correct: int = 0  # cases where heuristic got it right but LLM didn't
    notes: str = ""


# ---------------------------------------------------------------------------
# Sentiment classification prompt
# ---------------------------------------------------------------------------

_SENTIMENT_PROMPT = """\
You are an emotion classification expert. Classify the emotion expressed in this text.

Text: "{text}"

Choose EXACTLY ONE label from: excitement, joy, gratitude, curiosity, frustration, sadness, neutral, confusion

Rules:
- excitement = high-energy positive (thrilled, pumped, can't believe it)
- joy = warm, calm positive (happy, delighted, content, peaceful)
- gratitude = thankfulness, appreciation (thank you, grateful, appreciate)
- curiosity = interest, wonder, wanting to learn more
- frustration = anger, annoyance, irritation (furious, hate, terrible)
- sadness = grief, loss, melancholy, disappointment (heartbroken, lonely, depressed)
- neutral = no clear emotion, factual statements, routine observations
- confusion = uncertainty, puzzlement, being lost

Respond in this exact JSON format (no other text):
{{"label": "<one of the labels above>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}}"""


# ---------------------------------------------------------------------------
# Personality fidelity prompt
# ---------------------------------------------------------------------------

_PERSONALITY_PROMPT = """\
You are evaluating an AI companion's system prompt for personality fidelity.

The companion was configured with these OCEAN traits:
{ocean_traits}

And these communication style settings:
{comm_style}

Here is the generated system prompt:
---
{system_prompt}
---

Rate how well the system prompt reflects the configured personality.

Score each aspect 0-100:
1. trait_coverage: Are all 5 OCEAN traits mentioned with appropriate behavioral descriptions?
2. comm_style_coverage: Are all communication style settings reflected?
3. behavioral_consistency: Do the described behaviors logically follow from the OCEAN scores?
4. specificity: Are the behavioral descriptions specific (not generic filler)?

Respond in this exact JSON format (no other text):
{{"trait_coverage": <0-100>, "comm_style_coverage": <0-100>, "behavioral_consistency": <0-100>, "specificity": <0-100>, "reasoning": "<2-3 sentences>"}}"""


# ---------------------------------------------------------------------------
# Emotional arc prompt (multi-turn coherence)
# ---------------------------------------------------------------------------

_ARC_JUDGE_PROMPT = """\
You are evaluating the emotional coherence of a memory stream.

These memories were created during a {phase_name} phase where the user expressed {expected_emotion}:

{memories_text}

Each memory has a somatic marker (detected emotion label). Rate the coherence:

1. label_accuracy: What percentage of the somatic labels correctly match {expected_emotion}? (0-100)
2. emotional_consistency: How emotionally consistent is the overall stream? (0-100)
3. false_positives: How many labels are clearly wrong? (count)

Respond in this exact JSON format (no other text):
{{"label_accuracy": <0-100>, "emotional_consistency": <0-100>, "false_positives": <count>, "reasoning": "<one sentence>"}}"""


# ---------------------------------------------------------------------------
# Judge: EI-1 Sentiment Classification
# ---------------------------------------------------------------------------


async def judge_sentiment(engine: HaikuCognitiveEngine) -> JudgeDimensionResult:
    """Use Haiku to classify all 61 sentiment corpus entries.

    Runs all classifications in parallel (bounded by engine semaphore).
    Compares LLM verdicts against both ground truth and heuristic labels.
    """
    from soul_protocol.runtime.memory.sentiment import detect_sentiment

    corpus = json.loads(_CORPUS_PATH.read_text())
    logger.info("Sentiment judge: evaluating %d entries with Haiku", len(corpus))

    async def classify_one(entry: dict) -> JudgeVerdict:
        text = entry["text"]
        expected = entry["expected_label"]

        # Get heuristic result
        heuristic = detect_sentiment(text)

        # Get LLM result
        prompt = _SENTIMENT_PROMPT.format(text=text)
        try:
            response = await engine.think(prompt)
            parsed = json.loads(_strip_markdown(response))
            llm_label = parsed["label"].lower().strip()
            llm_confidence = float(parsed.get("confidence", 0.5))
            llm_reasoning = parsed.get("reasoning", "")
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(
                "Failed to parse LLM response for %r: %s — raw: %s", text[:40], e, response[:100]
            )
            llm_label = "error"
            llm_confidence = 0.0
            llm_reasoning = f"Parse error: {e}"

        return JudgeVerdict(
            text=text,
            expected_label=expected,
            heuristic_label=heuristic.label,
            llm_label=llm_label,
            llm_confidence=llm_confidence,
            llm_reasoning=llm_reasoning,
            heuristic_correct=_fuzzy_match(expected, heuristic.label),
            llm_correct=_fuzzy_match(expected, llm_label),
        )

    # Run all classifications in parallel
    verdicts = await asyncio.gather(*[classify_one(entry) for entry in corpus])

    # Aggregate
    heuristic_correct = sum(1 for v in verdicts if v.heuristic_correct)
    llm_correct = sum(1 for v in verdicts if v.llm_correct)
    agreed = sum(1 for v in verdicts if v.heuristic_label == v.llm_label)
    llm_only = sum(1 for v in verdicts if v.llm_correct and not v.heuristic_correct)
    heur_only = sum(1 for v in verdicts if v.heuristic_correct and not v.llm_correct)

    total = len(verdicts)
    result = JudgeDimensionResult(
        dimension_id=2,
        dimension_name="Emotional Intelligence — Sentiment",
        heuristic_accuracy=heuristic_correct / total if total else 0,
        llm_accuracy=llm_correct / total if total else 0,
        agreement_rate=agreed / total if total else 0,
        verdicts=list(verdicts),
        llm_only_correct=llm_only,
        heuristic_only_correct=heur_only,
        notes=(
            f"Heuristic: {heuristic_correct}/{total} ({heuristic_correct / total:.0%}), "
            f"LLM: {llm_correct}/{total} ({llm_correct / total:.0%}), "
            f"Agreement: {agreed}/{total} ({agreed / total:.0%}), "
            f"LLM-only wins: {llm_only}, Heuristic-only wins: {heur_only}"
        ),
    )

    logger.info("Sentiment judge: %s", result.notes)
    return result


# ---------------------------------------------------------------------------
# Judge: PE-1 Personality Fidelity
# ---------------------------------------------------------------------------


async def judge_personality(engine: HaikuCognitiveEngine) -> JudgeDimensionResult:
    """Use Haiku to evaluate system prompt quality for different OCEAN profiles."""
    from soul_protocol import Soul

    profiles = [
        {
            "name": "HighOpen",
            "ocean": {
                "openness": 0.9,
                "conscientiousness": 0.2,
                "extraversion": 0.8,
                "agreeableness": 0.3,
                "neuroticism": 0.7,
            },
            "comm": {
                "warmth": "high",
                "verbosity": "moderate",
                "humor_style": "dry",
                "emoji_usage": "rare",
            },
        },
        {
            "name": "LowOpen",
            "ocean": {
                "openness": 0.1,
                "conscientiousness": 0.9,
                "extraversion": 0.2,
                "agreeableness": 0.8,
                "neuroticism": 0.1,
            },
            "comm": {
                "warmth": "moderate",
                "verbosity": "concise",
                "humor_style": "none",
                "emoji_usage": "never",
            },
        },
        {
            "name": "Balanced",
            "ocean": {
                "openness": 0.5,
                "conscientiousness": 0.5,
                "extraversion": 0.5,
                "agreeableness": 0.5,
                "neuroticism": 0.5,
            },
            "comm": {
                "warmth": "moderate",
                "verbosity": "moderate",
                "humor_style": "light",
                "emoji_usage": "occasional",
            },
        },
    ]

    scores: list[dict] = []

    for profile in profiles:
        soul = await Soul.birth(
            name=profile["name"],
            values=["honesty"],
            ocean=profile["ocean"],
            communication=profile["comm"],
            persona=f"I am {profile['name']}.",
        )
        system_prompt = soul.to_system_prompt()

        ocean_str = "\n".join(f"  {k}: {v}" for k, v in profile["ocean"].items())
        comm_str = "\n".join(f"  {k}: {v}" for k, v in profile["comm"].items())

        prompt = _PERSONALITY_PROMPT.format(
            ocean_traits=ocean_str,
            comm_style=comm_str,
            system_prompt=system_prompt,
        )

        try:
            response = await engine.think(prompt)
            parsed = json.loads(_strip_markdown(response))
            scores.append(
                {
                    "profile": profile["name"],
                    "trait_coverage": parsed.get("trait_coverage", 0),
                    "comm_style_coverage": parsed.get("comm_style_coverage", 0),
                    "behavioral_consistency": parsed.get("behavioral_consistency", 0),
                    "specificity": parsed.get("specificity", 0),
                    "reasoning": parsed.get("reasoning", ""),
                }
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse personality judge for %s: %s", profile["name"], e)
            scores.append(
                {
                    "profile": profile["name"],
                    "trait_coverage": 0,
                    "comm_style_coverage": 0,
                    "behavioral_consistency": 0,
                    "specificity": 0,
                    "reasoning": f"Parse error: {e}",
                }
            )

    # Compute averages
    avg_trait = sum(s["trait_coverage"] for s in scores) / len(scores)
    avg_comm = sum(s["comm_style_coverage"] for s in scores) / len(scores)
    avg_consistency = sum(s["behavioral_consistency"] for s in scores) / len(scores)
    avg_specificity = sum(s["specificity"] for s in scores) / len(scores)
    overall = (avg_trait + avg_comm + avg_consistency + avg_specificity) / 4

    result = JudgeDimensionResult(
        dimension_id=3,
        dimension_name="Personality Expression — LLM Judge",
        heuristic_accuracy=0.0,  # not applicable for this judge
        llm_accuracy=overall / 100.0,
        agreement_rate=0.0,
        notes=(
            f"LLM personality scores: trait={avg_trait:.0f}, comm={avg_comm:.0f}, "
            f"consistency={avg_consistency:.0f}, specificity={avg_specificity:.0f}. "
            f"Overall: {overall:.1f}/100. "
            f"Profiles: {json.dumps(scores, indent=None)}"
        ),
    )

    logger.info("Personality judge: overall %.1f/100", overall)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fuzzy_match(expected: str, actual: str) -> bool:
    """Fuzzy label match — same logic as d2_emotion._labels_match."""
    e = expected.lower().strip()
    a = actual.lower().strip()
    if e == a:
        return True
    if e in a or a in e:
        return True
    # Stem mapping
    stems = {
        "excit": "excitement",
        "joy": "joy",
        "happy": "joy",
        "grat": "gratitude",
        "thank": "gratitude",
        "curio": "curiosity",
        "intrigu": "curiosity",
        "frustr": "frustration",
        "anger": "frustration",
        "angry": "frustration",
        "sad": "sadness",
        "depress": "sadness",
        "neutr": "neutral",
        "confus": "confusion",
    }
    e_canon = next((c for s, c in stems.items() if s in e), None)
    a_canon = next((c for s, c in stems.items() if s in a), None)
    return bool(e_canon and a_canon and e_canon == a_canon)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def run_llm_judges(
    dimensions: list[int] | None = None,
    max_concurrent: int = 15,
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """Run LLM judge evaluations and save results.

    Args:
        dimensions: Which dimensions to judge (default: [2, 3]).
        max_concurrent: Max parallel API calls.
        model: Model to use for judging.

    Returns:
        Results dict with all judge verdicts.
    """
    dims = dimensions or [2, 3]
    engine = HaikuCognitiveEngine(model=model, max_concurrent=max_concurrent)

    logger.info("Starting LLM judges for dimensions %s with %s", dims, model)

    tasks = []
    if 2 in dims:
        tasks.append(("sentiment", judge_sentiment(engine)))
    if 3 in dims:
        tasks.append(("personality", judge_personality(engine)))

    # Run judges in parallel
    results_list = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

    # Build output
    output: dict = {
        "timestamp": datetime.now(UTC).isoformat(),
        "mode": "llm_judge",
        "model": model,
        "max_concurrent": max_concurrent,
        "judges": {},
    }

    for (name, _), result in zip(tasks, results_list):
        if isinstance(result, Exception):
            logger.error("Judge %s failed: %s", name, result)
            output["judges"][name] = {"error": str(result)}
        else:
            output["judges"][name] = {
                "dimension_id": result.dimension_id,
                "dimension_name": result.dimension_name,
                "heuristic_accuracy": round(result.heuristic_accuracy, 4),
                "llm_accuracy": round(result.llm_accuracy, 4),
                "agreement_rate": round(result.agreement_rate, 4),
                "llm_only_correct": result.llm_only_correct,
                "heuristic_only_correct": result.heuristic_only_correct,
                "notes": result.notes,
                "verdicts": [
                    {
                        "text": v.text[:80],
                        "expected": v.expected_label,
                        "heuristic": v.heuristic_label,
                        "llm": v.llm_label,
                        "llm_confidence": v.llm_confidence,
                        "heuristic_correct": v.heuristic_correct,
                        "llm_correct": v.llm_correct,
                    }
                    for v in result.verdicts
                ],
            }

    # Add usage stats
    output["usage"] = {
        "total_calls": engine.usage.calls,
        "input_tokens": engine.usage.input_tokens,
        "output_tokens": engine.usage.output_tokens,
        "errors": engine.usage.errors,
        "estimated_cost_usd": round(engine.usage.estimated_cost_usd, 4),
        "elapsed_seconds": round(engine.usage.elapsed, 1),
    }

    # Save results
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = _RESULTS_DIR / f"llm_judge_{timestamp}.json"
    with open(result_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info("Results saved to %s", result_path)
    logger.info("Usage: %s", engine.usage.summary())

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run LLM judge evaluations")
    parser.add_argument(
        "--dimensions",
        type=str,
        default="2,3",
        help="Comma-separated dimension IDs to judge (default: 2,3)",
    )
    parser.add_argument(
        "--concurrent", type=int, default=15, help="Max concurrent API calls (default: 15)"
    )
    parser.add_argument(
        "--model", type=str, default="claude-haiku-4-5-20251001", help="Model to use for judging"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s %(levelname)s %(message)s",
    )

    dims = [int(d.strip()) for d in args.dimensions.split(",")]
    results = asyncio.run(
        run_llm_judges(
            dimensions=dims,
            max_concurrent=args.concurrent,
            model=args.model,
        )
    )

    # Print summary
    print("\n" + "=" * 60)
    print("LLM JUDGE RESULTS")
    print("=" * 60)

    for name, data in results.get("judges", {}).items():
        if "error" in data:
            print(f"\n  {name}: ERROR — {data['error']}")
            continue
        print(f"\n  {data['dimension_name']}")
        print(f"    Heuristic accuracy: {data['heuristic_accuracy']:.0%}")
        print(f"    LLM accuracy:       {data['llm_accuracy']:.0%}")
        print(f"    Agreement rate:     {data['agreement_rate']:.0%}")
        if data.get("llm_only_correct"):
            print(f"    LLM-only wins:     {data['llm_only_correct']}")
        if data.get("heuristic_only_correct"):
            print(f"    Heuristic-only:    {data['heuristic_only_correct']}")

    usage = results.get("usage", {})
    print(f"\n  Cost: ${usage.get('estimated_cost_usd', 0):.4f}")
    print(f"  Calls: {usage.get('total_calls', 0)}")
    print(f"  Time: {usage.get('elapsed_seconds', 0):.1f}s")


if __name__ == "__main__":
    main()
