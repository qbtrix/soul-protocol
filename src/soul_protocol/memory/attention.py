# memory/attention.py — LIDA-inspired significance gate for episodic storage.
# Created: v0.2.0 — Filters which interactions become episodic memories.
#   Only significant interactions (novel, emotional, goal-relevant) are stored.
#   Mundane exchanges ("hello", "thanks") skip episodic but still get fact extraction.

from __future__ import annotations

from soul_protocol.memory.search import relevance_score, tokenize
from soul_protocol.memory.sentiment import detect_sentiment
from soul_protocol.types import Interaction, SignificanceScore

# ---------------------------------------------------------------------------
# Default threshold — interactions scoring below this skip episodic storage
# ---------------------------------------------------------------------------

DEFAULT_SIGNIFICANCE_THRESHOLD: float = 0.3


def compute_significance(
    interaction: Interaction,
    core_values: list[str],
    recent_contents: list[str],
) -> SignificanceScore:
    """Compute how significant an interaction is for episodic storage.

    Three dimensions (LIDA architecture):
    1. Novelty — how different from recent interactions
    2. Emotional intensity — from somatic marker detection
    3. Goal relevance — alignment with the soul's core values

    Args:
        interaction: The interaction to evaluate.
        core_values: The soul's core values (strings).
        recent_contents: Content strings of the last N episodic memories
            (for novelty comparison).

    Returns:
        A SignificanceScore with novelty, emotional_intensity, and goal_relevance.
    """
    combined_text = f"{interaction.user_input} {interaction.agent_output}"

    # --- 1. Novelty: inverse of similarity to recent interactions ---
    if recent_contents:
        similarities = [relevance_score(combined_text, recent) for recent in recent_contents]
        avg_similarity = sum(similarities) / len(similarities)
        novelty = 1.0 - avg_similarity
    else:
        # First interaction is always novel
        novelty = 1.0

    # --- 2. Emotional intensity: from sentiment detection ---
    somatic = detect_sentiment(interaction.user_input)
    emotional_intensity = somatic.arousal + abs(somatic.valence) * 0.3
    emotional_intensity = min(1.0, emotional_intensity)

    # --- 3. Goal relevance: overlap between interaction and core values ---
    if core_values:
        values_text = " ".join(core_values)
        goal_relevance = relevance_score(combined_text, values_text)
    else:
        goal_relevance = 0.0

    # Boost for substantial content — longer messages are more likely significant
    content_tokens = tokenize(combined_text)
    length_bonus = min(0.2, len(content_tokens) * 0.01)

    # Apply length bonus to novelty (short greetings get penalized)
    novelty = min(1.0, novelty + length_bonus)

    return SignificanceScore(
        novelty=round(novelty, 3),
        emotional_intensity=round(emotional_intensity, 3),
        goal_relevance=round(goal_relevance, 3),
    )


def overall_significance(score: SignificanceScore) -> float:
    """Compute a single significance value from the three dimensions.

    Weighted combination: novelty matters most, emotional intensity second,
    goal relevance third.

    Args:
        score: The three-dimensional significance score.

    Returns:
        A single float (0.0 to 1.0) representing overall significance.
    """
    return 0.4 * score.novelty + 0.35 * score.emotional_intensity + 0.25 * score.goal_relevance


def is_significant(
    score: SignificanceScore,
    threshold: float = DEFAULT_SIGNIFICANCE_THRESHOLD,
) -> bool:
    """Determine if an interaction is significant enough for episodic storage.

    Args:
        score: The significance score to evaluate.
        threshold: Minimum overall significance (default 0.3).

    Returns:
        True if the interaction should become an episodic memory.
    """
    return overall_significance(score) >= threshold
