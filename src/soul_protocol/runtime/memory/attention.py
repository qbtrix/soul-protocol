# memory/attention.py — LIDA-inspired significance gate for episodic storage.
# Updated: v0.2.3 — Moved `import re` to top-level imports (PEP 8), fixed stale
#   docstring (said "default 0.5" but constant is 0.35).
# Updated: phase1-tuning — Rebalanced gate for heuristic engine. Added content_richness
#   dimension (proper nouns, numbers, specificity) so factual statements pass even without
#   emotion words. Threshold 0.5 -> 0.4. Reweighted: novelty 0.3, emotion 0.2,
#   goal 0.2, richness 0.3. Short penalty -0.3 -> -0.2.
# Updated: phase1-ablation-fixes — emotional_intensity formula, select_top_k batch filter.
# Created: v0.2.0 — Filters which interactions become episodic memories.

from __future__ import annotations

import re

from soul_protocol.runtime.memory.search import relevance_score, tokenize
from soul_protocol.runtime.memory.sentiment import detect_sentiment
from soul_protocol.runtime.types import Interaction, SignificanceScore

# ---------------------------------------------------------------------------
# Default threshold — interactions scoring below this skip episodic storage
# ---------------------------------------------------------------------------

DEFAULT_SIGNIFICANCE_THRESHOLD: float = 0.35

# Short-message penalty: messages under this token count get penalized
SHORT_MESSAGE_TOKEN_LIMIT: int = 12
SHORT_MESSAGE_PENALTY: float = 0.15

# Content richness indicators — proper nouns, numbers, specificity signals

_PROPER_NOUN_PATTERN = re.compile(r'\b[A-Z][a-z]{2,}\b')
_NUMBER_PATTERN = re.compile(r'\b\d+\b')
_SPECIFICITY_MARKERS = {
    'named', 'called', 'name', 'birthday', 'born', 'started', 'began',
    'moved', 'married', 'divorced', 'hired', 'fired', 'promoted',
    'allergic', 'allergy', 'diagnosed', 'died', 'passed', 'killed',
    'bought', 'sold', 'paid', 'earned', 'salary', 'address', 'phone',
    'email', 'manager', 'director', 'engineer', 'doctor', 'teacher',
    'university', 'college', 'school', 'company', 'team', 'project',
}


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

    # --- 4. Content richness: proper nouns, numbers, specificity ---
    richness = _content_richness(combined_text)

    return SignificanceScore(
        novelty=round(novelty, 3),
        emotional_intensity=round(emotional_intensity, 3),
        goal_relevance=round(goal_relevance, 3),
        content_richness=round(richness, 3),
    )


def _content_richness(text: str) -> float:
    """Score how information-rich a message is (0.0 to 1.0).

    Detects proper nouns, numbers, and specificity markers — signals that
    a message contains memorable facts even without emotional language.
    "I'm a product manager at TechCorp" scores high.
    "Nice weather today" scores low.
    """
    score = 0.0

    # Proper nouns (capitalized words not at sentence start)
    proper_nouns = _PROPER_NOUN_PATTERN.findall(text)
    meaningful_proper = [w for w in proper_nouns if len(w) > 2]
    score += min(0.5, len(meaningful_proper) * 0.15)

    # Numbers (dates, ages, amounts, counts)
    numbers = _NUMBER_PATTERN.findall(text)
    score += min(0.3, len(numbers) * 0.15)

    # Specificity markers
    words_lower = set(text.lower().split())
    marker_hits = words_lower & _SPECIFICITY_MARKERS
    score += min(0.4, len(marker_hits) * 0.15)

    # Long messages are more likely to contain meaningful content
    word_count = len(text.split())
    if word_count > 15:
        score += 0.1

    return min(1.0, score)


def overall_significance(
    score: SignificanceScore,
    token_count: int | None = None,
) -> float:
    """Compute a single significance value from four dimensions.

    Rebalanced weights: novelty and content richness matter most (catch both
    emotional AND factual significance), with emotion and goal relevance
    as secondary signals.  Short messages receive a penalty.

    Args:
        score: The multi-dimensional significance score.
        token_count: Number of tokens in the combined interaction text.
            If provided and below SHORT_MESSAGE_TOKEN_LIMIT, a penalty is applied.

    Returns:
        A single float (0.0 to 1.0) representing overall significance.
    """
    richness = getattr(score, 'content_richness', 0.0)
    raw = (0.3 * score.novelty
           + 0.2 * score.emotional_intensity
           + 0.2 * score.goal_relevance
           + 0.3 * richness)

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
        threshold: Minimum overall significance (default 0.35).
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
