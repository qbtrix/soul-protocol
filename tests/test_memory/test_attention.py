# test_attention.py — Tests for LIDA-inspired significance gate.
# Updated: phase1-ablation-fixes — Adjusted tests for raised threshold (0.5),
#   updated emotional_intensity formula, and short-message penalty.
# Created: v0.2.0 — Covers compute_significance, overall_significance, and
#   is_significant with novelty, emotional, goal-relevance, and threshold cases.

from __future__ import annotations

import pytest

from soul_protocol.runtime.memory.attention import (
    DEFAULT_SIGNIFICANCE_THRESHOLD,
    compute_significance,
    is_significant,
    overall_significance,
)
from soul_protocol.runtime.types import Interaction, SignificanceScore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_interaction(user_input: str, agent_output: str = "") -> Interaction:
    """Convenience factory — keeps test bodies terse."""
    return Interaction(user_input=user_input, agent_output=agent_output)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def neutral_interaction() -> Interaction:
    """An interaction with no emotional words, no proper nouns, no numbers."""
    return make_interaction(
        user_input="ok sure thing",
        agent_output="got it",
    )


@pytest.fixture
def emotional_interaction() -> Interaction:
    """An interaction with strong positive emotional language."""
    return make_interaction(
        user_input="I am absolutely thrilled and excited about this!",
        agent_output="That is wonderful to hear!",
    )


@pytest.fixture
def meaningful_interaction() -> Interaction:
    """A multi-sentence interaction covering the soul's core domain."""
    return make_interaction(
        user_input="I really want to learn Python and explore machine learning concepts.",
        agent_output="Let me guide you through the fundamentals step by step.",
    )


@pytest.fixture
def core_values() -> list[str]:
    """Sample core values used in goal-relevance tests."""
    return ["learning", "explore", "curiosity", "growth"]


# ---------------------------------------------------------------------------
# 1. First interaction — empty recent_contents → maximum novelty
# ---------------------------------------------------------------------------


def test_first_interaction_novelty_is_max(neutral_interaction, core_values):
    """With no prior interactions, novelty must be 1.0 (plus any length bonus)."""
    score = compute_significance(neutral_interaction, core_values, recent_contents=[])
    # Base novelty is 1.0; length bonus can only keep it at 1.0 (capped).
    assert score.novelty == 1.0


def test_first_interaction_score_is_signifance_score_type(neutral_interaction):
    """compute_significance always returns a SignificanceScore instance."""
    score = compute_significance(neutral_interaction, [], recent_contents=[])
    assert isinstance(score, SignificanceScore)


def test_first_interaction_neutral_below_raised_threshold(neutral_interaction):
    """A first interaction with neutral tone is below the raised 0.5 threshold.

    With threshold raised to 0.5, a neutral-emotion first interaction
    (novelty=1.0 → 0.4 contribution) falls short. This is by design:
    mundane first messages shouldn't pass the gate.
    """
    score = compute_significance(neutral_interaction, [], recent_contents=[])
    assert overall_significance(score) < DEFAULT_SIGNIFICANCE_THRESHOLD


# ---------------------------------------------------------------------------
# 2. Repeated content → low novelty
# ---------------------------------------------------------------------------


def test_repeated_content_yields_low_novelty():
    """An interaction identical to a recent one should have near-zero novelty."""
    text = "What is the weather today?"
    interaction = make_interaction(user_input=text, agent_output="")
    recent = [text]  # same content already seen

    score = compute_significance(interaction, [], recent_contents=recent)

    # Novelty = 1 - 1.0 (full similarity) + small length bonus.
    # For a short phrase the length bonus is tiny, so novelty must be very low.
    assert score.novelty < 0.2


def test_repeated_content_multiple_times_stays_low():
    """Seeing the same text several times does not inflate novelty."""
    text = "Hello there, how are you doing today?"
    interaction = make_interaction(user_input=text, agent_output="")
    recent = [text, text, text]

    score = compute_significance(interaction, [], recent_contents=recent)
    assert score.novelty < 0.25


# ---------------------------------------------------------------------------
# 3. Emotional user input → high emotional_intensity
# ---------------------------------------------------------------------------


def test_emotional_input_raises_intensity(emotional_interaction):
    """Strongly emotional words must push emotional_intensity noticeably above zero."""
    score = compute_significance(emotional_interaction, [], recent_contents=[])
    # "thrilled", "excited", "wonderful" are high-valence / high-arousal words.
    assert score.emotional_intensity > 0.3


def test_emotional_input_stays_within_bounds(emotional_interaction):
    """emotional_intensity must never exceed 1.0."""
    score = compute_significance(emotional_interaction, [], recent_contents=[])
    assert 0.0 <= score.emotional_intensity <= 1.0


# ---------------------------------------------------------------------------
# 4. Neutral user input → low emotional_intensity
# ---------------------------------------------------------------------------


def test_neutral_input_has_low_emotional_intensity():
    """Plain, factual text with no sentiment words should have low emotional_intensity."""
    interaction = make_interaction(
        user_input="The document was submitted on Tuesday.",
        agent_output="",
    )
    score = compute_significance(interaction, [], recent_contents=[])
    # With scaled-down arousal (arousal*0.5), neutral text stays low
    assert score.emotional_intensity < 0.3


# ---------------------------------------------------------------------------
# 5. Interaction matching core values → high goal_relevance
# ---------------------------------------------------------------------------


def test_matching_core_values_yields_high_goal_relevance(core_values):
    """When user input tokens overlap heavily with core_values, goal_relevance rises."""
    interaction = make_interaction(
        user_input="I want to explore learning and satisfy my curiosity for growth.",
        agent_output="",
    )
    score = compute_significance(interaction, core_values, recent_contents=[])
    # "explore", "learning", "curiosity", "growth" all appear in core_values.
    assert score.goal_relevance > 0.4


def test_goal_relevance_within_bounds(core_values):
    """goal_relevance must be clamped to [0.0, 1.0]."""
    interaction = make_interaction(
        user_input="explore learning curiosity growth",
        agent_output="",
    )
    score = compute_significance(interaction, core_values, recent_contents=[])
    assert 0.0 <= score.goal_relevance <= 1.0


# ---------------------------------------------------------------------------
# 6. No core values → goal_relevance is exactly 0.0
# ---------------------------------------------------------------------------


def test_empty_core_values_gives_zero_goal_relevance(neutral_interaction):
    """When core_values=[], goal_relevance must be exactly 0.0."""
    score = compute_significance(neutral_interaction, core_values=[], recent_contents=[])
    assert score.goal_relevance == 0.0


# ---------------------------------------------------------------------------
# 7. overall_significance math check
# ---------------------------------------------------------------------------


def test_overall_significance_weighted_sum():
    """overall_significance uses rebalanced weights: 0.3*novelty + 0.2*emotion + 0.2*goal + 0.3*richness."""
    score = SignificanceScore(novelty=0.8, emotional_intensity=0.6, goal_relevance=0.4, content_richness=0.5)
    expected = round(0.3 * 0.8 + 0.2 * 0.6 + 0.2 * 0.4 + 0.3 * 0.5, 10)
    assert pytest.approx(overall_significance(score), abs=1e-9) == expected


def test_overall_significance_all_zero():
    """A zero score produces 0.0 overall significance."""
    score = SignificanceScore(novelty=0.0, emotional_intensity=0.0, goal_relevance=0.0, content_richness=0.0)
    assert overall_significance(score) == 0.0


def test_overall_significance_all_one():
    """A perfect score of 1.0 on all dimensions produces 1.0 overall."""
    score = SignificanceScore(novelty=1.0, emotional_intensity=1.0, goal_relevance=1.0, content_richness=1.0)
    assert pytest.approx(overall_significance(score)) == 1.0


# ---------------------------------------------------------------------------
# 8 & 9. is_significant threshold gate
# ---------------------------------------------------------------------------


def test_is_significant_above_default_threshold():
    """A high-novelty + emotional score must pass the default 0.5 threshold."""
    score = SignificanceScore(novelty=1.0, emotional_intensity=0.5, goal_relevance=0.0)
    # overall = 0.4 * 1.0 + 0.35 * 0.5 = 0.575 >= 0.5 → True
    assert is_significant(score) is True


def test_is_significant_below_default_threshold():
    """A near-zero score must fail the default 0.5 threshold."""
    score = SignificanceScore(novelty=0.05, emotional_intensity=0.0, goal_relevance=0.0)
    # overall = 0.4 * 0.05 = 0.02 < 0.5 → False
    assert is_significant(score) is False


# ---------------------------------------------------------------------------
# 10. Mundane "hello"/"hi" with prior similar greeting → below threshold
# ---------------------------------------------------------------------------


def test_mundane_greeting_below_threshold_with_prior_context():
    """A repeated greeting-style interaction should fail the significance gate."""
    # Populate recent_contents with a similar greeting so novelty collapses.
    recent = ["hello how are you"]
    interaction = make_interaction(user_input="hello how are you", agent_output="")

    score = compute_significance(interaction, core_values=[], recent_contents=recent)

    # novelty is near 0, emotional_intensity is 0 (no sentiment words), goal = 0.
    assert is_significant(score) is False


# ---------------------------------------------------------------------------
# 11. Meaningful interaction → above threshold
# ---------------------------------------------------------------------------


def test_meaningful_interaction_passes_gate(meaningful_interaction, core_values):
    """A substantive, emotionally relevant, on-topic interaction must be significant."""
    score = compute_significance(meaningful_interaction, core_values, recent_contents=[])
    assert is_significant(score) is True


# ---------------------------------------------------------------------------
# 12. Custom threshold
# ---------------------------------------------------------------------------


def test_custom_threshold_high_rejects_moderate_score():
    """With a very high custom threshold, a moderate score is rejected."""
    score = SignificanceScore(novelty=0.4, emotional_intensity=0.0, goal_relevance=0.0)
    # overall ≈ 0.16, which is below threshold=0.5
    assert is_significant(score, threshold=0.5) is False


def test_custom_threshold_low_accepts_weak_score():
    """With a very low custom threshold, even a weak score passes."""
    score = SignificanceScore(novelty=0.1, emotional_intensity=0.0, goal_relevance=0.0)
    # overall = 0.04, which is above threshold=0.01
    assert is_significant(score, threshold=0.01) is True


def test_custom_threshold_exact_boundary():
    """Score exactly at the threshold boundary must be accepted (>=)."""
    # With weights 0.3*novelty + 0.2*emotion + 0.2*goal + 0.3*richness
    # 0.3*1.0 + 0.2*0.0 + 0.2*0.0 + 0.3*0.0 = 0.3
    score = SignificanceScore(novelty=1.0, emotional_intensity=0.0, goal_relevance=0.0, content_richness=0.0)
    assert is_significant(score, threshold=0.3) is True
