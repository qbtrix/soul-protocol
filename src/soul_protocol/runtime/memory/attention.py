# memory/attention.py — LIDA-inspired significance gate for episodic storage.
# Updated: phase1-ablation-fixes — Raised DEFAULT_SIGNIFICANCE_THRESHOLD from 0.3 to 0.5,
#   fixed emotional_intensity formula (scale down arousal: arousal*0.5 + |valence|*0.3),
#   added short-message penalty (-0.3 for <20 tokens), added select_top_k batch filter.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Created: v0.2.0 — Filters which interactions become episodic memories.
#   Only significant interactions (novel, emotional, goal-relevant) are stored.
#   Mundane exchanges ("hello", "thanks") skip episodic but still get fact extraction.

from __future__ import annotations

from soul_protocol.runtime.memory.search import relevance_score, tokenize
from soul_protocol.runtime.memory.sentiment import detect_sentiment
from soul_protocol.runtime.types import Interaction, SignificanceScore

# ---------------------------------------------------------------------------
# Default threshold — interactions scoring below this skip episodic storage
# ---------------------------------------------------------------------------

DEFAULT_SIGNIFICANCE_THRESHOLD: float = 0.5

# Short-message penalty: messages under this token count get penalized
SHORT_MESSAGE_TOKEN_LIMIT: int = 20
SHORT_MESSAGE_PENALTY: float = 0.3


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
    emotional_intensity = somatic.arousal * 0.5 + abs(somatic.valence) * 0.3
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


def overall_significance(
    score: SignificanceScore,
    token_count: int | None = None,
) -> float:
    """Compute a single significance value from the three dimensions.

    Weighted combination: novelty matters most, emotional intensity second,
    goal relevance third.  Short messages (< SHORT_MESSAGE_TOKEN_LIMIT tokens)
    receive a penalty to prevent trivial exchanges from passing the gate.

    Args:
        score: The three-dimensional significance score.
        token_count: Number of tokens in the combined interaction text.
            If provided and below SHORT_MESSAGE_TOKEN_LIMIT, a penalty is applied.

    Returns:
        A single float (0.0 to 1.0) representing overall significance.
    """
    raw = 0.4 * score.novelty + 0.35 * score.emotional_intensity + 0.25 * score.goal_relevance

    # Penalize short messages — greetings and one-word responses are not significant
    if token_count is not None and token_count < SHORT_MESSAGE_TOKEN_LIMIT:
        raw = max(0.0, raw - SHORT_MESSAGE_PENALTY)

    return raw


def is_significant(
    score: SignificanceScore,
    threshold: float = DEFAULT_SIGNIFICANCE_THRESHOLD,
    token_count: int | None = None,
) -> bool:
    """Determine if an interaction is significant enough for episodic storage.

    Args:
        score: The significance score to evaluate.
        threshold: Minimum overall significance (default 0.5).
        token_count: Token count for short-message penalty (forwarded to
            overall_significance).

    Returns:
        True if the interaction should become an episodic memory.
    """
    return overall_significance(score, token_count=token_count) >= threshold


def select_top_k(scores: list[float], k_ratio: float = 0.5) -> list[bool]:
    """Mark only the top fraction of a batch as significant (competition filter).

    Useful when processing a batch of interactions — only the top ``k_ratio``
    fraction (by significance score) are selected, even if all pass the threshold.

    Args:
        scores: List of overall significance values.
        k_ratio: Fraction of the batch to accept (default 0.5 = top 50%).

    Returns:
        A list of bools aligned with ``scores`` — True for selected entries.
    """
    if not scores:
        return []
    k = max(1, int(len(scores) * k_ratio))
    # Find the kth-highest score as the cutoff
    sorted_desc = sorted(scores, reverse=True)
    cutoff = sorted_desc[min(k - 1, len(sorted_desc) - 1)]
    # Mark entries at or above the cutoff, but only up to k entries
    result: list[bool] = []
    selected_count = 0
    for s in scores:
        if s >= cutoff and selected_count < k:
            result.append(True)
            selected_count += 1
        else:
            result.append(False)
    return result
