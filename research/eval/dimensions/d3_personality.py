# d3_personality.py — Dimension 3: Personality Expression (weight: 15%)
# Created: 2026-03-12 — Prompt fidelity, value alignment, OCEAN stability
# Updated: 2026-03-12 — Fixed emoji_usage field name (was emoji_use), added corpus
#   loading for PE-2, updated PE-3 to use distinct soul names and spec-matching OCEAN
#   values, added corpus-based filler turns for PE-4.
#
# Scenarios:
#   PE-1: Prompt fidelity — system prompt encodes all OCEAN traits + comm style
#   PE-2: Value-weighted significance — goal_relevance reflects core values
#   PE-3: Personality contrast — different OCEAN profiles produce different prompts
#   PE-4: OCEAN stability — traits don't drift over 100+ interactions
#
# Score formula:
#   score = (prompt_fidelity * 30) + (comm_coverage * 10) + (value_alignment * 25)
#         + (personality_stability * 25) + (prompt_differentiation * 10)

from __future__ import annotations

import json
import logging
from pathlib import Path

from soul_protocol import Interaction, Soul
from soul_protocol.runtime.memory.attention import compute_significance

from ..suite import DimensionResult

logger = logging.getLogger(__name__)

# Path to the topic_turns corpus
_CORPUS_PATH = Path(__file__).parent.parent / "corpus" / "topic_turns.json"


def _load_corpus_by_domain(domain: str, limit: int = 10) -> list[dict]:
    """Load turns from the corpus filtered by domain."""
    with open(_CORPUS_PATH) as f:
        all_turns = json.load(f)
    return [t for t in all_turns if t["domain"] == domain][:limit]


# ---------------------------------------------------------------------------
# PE-1: Prompt Fidelity
# ---------------------------------------------------------------------------


async def _pe1_prompt_fidelity() -> tuple[float, float]:
    """Check that system prompt encodes all OCEAN traits and comm style.

    Returns:
        (prompt_fidelity, communication_style_coverage)
    """
    soul = await Soul.birth(
        name="PersonalityTest",
        values=["honesty"],
        ocean={
            "openness": 0.9,
            "conscientiousness": 0.2,
            "extraversion": 0.8,
            "agreeableness": 0.3,
            "neuroticism": 0.7,
        },
        communication={
            "warmth": "high",
            "verbosity": "moderate",
            "humor_style": "dry",
            "emoji_usage": "rare",
        },
        persona="I am a personality test soul.",
    )

    prompt = soul.to_system_prompt()
    prompt_lower = prompt.lower()

    # Check OCEAN trait names appear
    trait_names = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
    traits_found = sum(1 for t in trait_names if t in prompt_lower)
    prompt_fidelity = traits_found / len(trait_names)

    # Check communication style fields appear
    comm_fields = ["warmth", "verbosity", "humor", "emoji"]
    comm_found = sum(1 for f in comm_fields if f in prompt_lower)
    comm_coverage = comm_found / len(comm_fields)

    logger.info(
        "PE-1: traits=%d/%d, comm=%d/%d",
        traits_found,
        len(trait_names),
        comm_found,
        len(comm_fields),
    )
    return prompt_fidelity, comm_coverage


# ---------------------------------------------------------------------------
# PE-2: Value-Weighted Significance
# ---------------------------------------------------------------------------


def _pe2_value_alignment() -> float:
    """Test that goal_relevance reflects core values.

    Soul-A (empathy values) should score higher on emotional turns.
    Soul-B (efficiency values) should score higher on technical turns.

    Returns:
        1.0 if both souls score higher on matching domain, else 0.0.
    """
    # Hand-crafted turns with deliberate keyword overlap with core values
    emotional_turns = [
        Interaction(
            user_input="I need someone to listen to me with compassion and empathy",
            agent_output="I hear you.",
        ),
        Interaction(
            user_input="I'm feeling really sad and need compassionate support",
            agent_output="I'm here.",
        ),
        Interaction(
            user_input="Can you show me empathy? I'm going through a hard time",
            agent_output="Of course.",
        ),
        Interaction(
            user_input="I just need someone who listens without judging me", agent_output="Always."
        ),
        Interaction(
            user_input="Your compassion and empathetic listening means everything",
            agent_output="Thank you.",
        ),
    ]
    technical_turns = [
        Interaction(
            user_input="We need to improve efficiency and speed of the pipeline",
            agent_output="Sure.",
        ),
        Interaction(
            user_input="The precision of this algorithm needs to be faster",
            agent_output="Let me check.",
        ),
        Interaction(
            user_input="Can you optimize for speed and processing efficiency?",
            agent_output="On it.",
        ),
        Interaction(
            user_input="The system needs more precision in calculations", agent_output="Agreed."
        ),
        Interaction(
            user_input="Speed and efficiency are critical for this deployment", agent_output="Yes."
        ),
    ]

    values_a = ["empathy", "compassion", "listening"]
    values_b = ["efficiency", "speed", "precision"]

    # Compute average goal_relevance for each (soul, turn_type) pair
    def avg_goal_relevance(values: list[str], turns: list[Interaction]) -> float:
        total = 0.0
        for t in turns:
            sig = compute_significance(t, values, [])
            total += sig.goal_relevance
        return total / len(turns) if turns else 0.0

    a_emotional = avg_goal_relevance(values_a, emotional_turns)
    a_technical = avg_goal_relevance(values_a, technical_turns)
    b_emotional = avg_goal_relevance(values_b, emotional_turns)
    b_technical = avg_goal_relevance(values_b, technical_turns)

    # Soul-A should prefer emotional, Soul-B should prefer technical
    a_correct = a_emotional > a_technical
    b_correct = b_technical > b_emotional

    logger.info(
        "PE-2: A emotional=%.3f tech=%.3f (%s), B emotional=%.3f tech=%.3f (%s)",
        a_emotional,
        a_technical,
        "PASS" if a_correct else "FAIL",
        b_emotional,
        b_technical,
        "PASS" if b_correct else "FAIL",
    )

    return 1.0 if (a_correct and b_correct) else 0.0


# ---------------------------------------------------------------------------
# PE-3: Personality Contrast
# ---------------------------------------------------------------------------


async def _pe3_personality_contrast() -> float:
    """Compare system prompts of opposite OCEAN profiles.

    Returns:
        prompt_differentiation as min(1.0, different_lines / 5).
    """
    soul_high = await Soul.birth(
        name="Soul-HIGH",
        values=["growth"],
        ocean={"openness": 0.9, "extraversion": 0.9, "agreeableness": 0.9},
        persona="I am a high-trait soul.",
    )
    soul_low = await Soul.birth(
        name="Soul-LOW",
        values=["growth"],
        ocean={"openness": 0.1, "extraversion": 0.1, "agreeableness": 0.1},
        persona="I am a low-trait soul.",
    )

    lines_high = soul_high.to_system_prompt().splitlines()
    lines_low = soul_low.to_system_prompt().splitlines()

    # Count lines that differ
    diff_count = abs(len(lines_high) - len(lines_low))
    for lh, ll in zip(lines_high, lines_low):
        if lh != ll:
            diff_count += 1

    differentiation = min(1.0, diff_count / 5.0)
    logger.info("PE-3: %d lines differ, differentiation=%.2f", diff_count, differentiation)
    return differentiation


# ---------------------------------------------------------------------------
# PE-4: OCEAN Stability Under Interaction
# ---------------------------------------------------------------------------


async def _pe4_ocean_stability(quick: bool) -> float:
    """Verify OCEAN traits don't drift over many interactions.

    Returns:
        1.0 if all checkpoints show no drift, else fraction.
    """
    soul = await Soul.birth(
        name="StabilityTest",
        values=["consistency"],
        ocean={
            "openness": 0.75,
            "conscientiousness": 0.65,
            "extraversion": 0.55,
            "agreeableness": 0.85,
            "neuroticism": 0.35,
        },
        persona="I am stable.",
    )

    original = soul.dna.personality
    n_turns = 50 if quick else 100
    checkpoint_interval = 25
    checkpoints_ok = 0
    total_checkpoints = 0

    # Load varied interactions from corpus for realistic stress-testing
    corpus_turns = _load_corpus_by_domain("mixed", limit=50) + _load_corpus_by_domain(
        "technical", limit=50
    )
    if not corpus_turns:
        # Fallback if corpus is empty
        corpus_turns = [
            {"user_input": "Tell me about your day.", "agent_output": "It was productive."}
        ]

    for i in range(n_turns):
        turn = corpus_turns[i % len(corpus_turns)]
        await soul.observe(
            Interaction(user_input=turn["user_input"], agent_output=turn["agent_output"])
        )

        if (i + 1) % checkpoint_interval == 0:
            total_checkpoints += 1
            p = soul.dna.personality
            stable = (
                abs(p.openness - original.openness) < 0.001
                and abs(p.conscientiousness - original.conscientiousness) < 0.001
                and abs(p.extraversion - original.extraversion) < 0.001
                and abs(p.agreeableness - original.agreeableness) < 0.001
                and abs(p.neuroticism - original.neuroticism) < 0.001
            )
            if stable:
                checkpoints_ok += 1
            else:
                logger.warning("PE-4: Drift detected at turn %d", i + 1)

    stability = checkpoints_ok / total_checkpoints if total_checkpoints > 0 else 1.0
    logger.info("PE-4: %d/%d checkpoints stable", checkpoints_ok, total_checkpoints)
    return stability


# ---------------------------------------------------------------------------
# Main evaluate entry point
# ---------------------------------------------------------------------------


async def evaluate(seed: int = 42, quick: bool = False) -> DimensionResult:
    """Run D3 Personality Expression evaluation."""
    logger.info("D3 Personality evaluation starting (seed=%d, quick=%s)", seed, quick)

    # PE-1
    prompt_fidelity, comm_coverage = await _pe1_prompt_fidelity()

    # PE-2
    value_alignment = _pe2_value_alignment()

    # PE-3
    prompt_diff = await _pe3_personality_contrast()

    # PE-4
    personality_stability = await _pe4_ocean_stability(quick)

    # Score
    score = (
        (prompt_fidelity * 30)
        + (comm_coverage * 10)
        + (value_alignment * 25)
        + (personality_stability * 25)
        + (prompt_diff * 10)
    )
    score = round(max(0.0, min(100.0, score)), 2)

    metrics = {
        "prompt_fidelity": round(prompt_fidelity, 4),
        "communication_style_coverage": round(comm_coverage, 4),
        "value_alignment_gap": round(value_alignment, 4),
        "personality_stability": round(personality_stability, 4),
        "prompt_differentiation": round(prompt_diff, 4),
    }

    passed: list[str] = []
    failed: list[str] = []

    if prompt_fidelity >= 0.80:
        passed.append("prompt_fidelity")
    else:
        failed.append("prompt_fidelity")

    if comm_coverage >= 0.75:
        passed.append("communication_style_coverage")
    else:
        failed.append("communication_style_coverage")

    if value_alignment >= 1.0:
        passed.append("value_alignment_gap")
    else:
        failed.append("value_alignment_gap")

    if personality_stability >= 1.0:
        passed.append("personality_stability")
    else:
        failed.append("personality_stability")

    if prompt_diff >= 0.80:
        passed.append("prompt_differentiation")
    else:
        failed.append("prompt_differentiation")

    notes = (
        f"Prompt fidelity {prompt_fidelity:.0%}, "
        f"comm {comm_coverage:.0%}, "
        f"values {'PASS' if value_alignment >= 1.0 else 'FAIL'}, "
        f"stability {personality_stability:.0%}, "
        f"contrast {prompt_diff:.0%}. "
        f"Score: {score}/100."
    )

    logger.info("D3 result: %s", notes)

    return DimensionResult(
        dimension_id=3,
        dimension_name="Personality Expression",
        score=score,
        metrics=metrics,
        passed=passed,
        failed=failed,
        notes=notes,
    )
