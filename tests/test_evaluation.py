# tests/test_evaluation.py — Rubric-based self-evaluation tests.
# Created: 2026-03-18 — Tests for heuristic evaluator, domain stats, evolution triggers.

from __future__ import annotations

from datetime import UTC

from soul_protocol.runtime.evaluation import (
    DEFAULT_RUBRICS,
    Evaluator,
    heuristic_evaluate,
)
from soul_protocol.runtime.types import (
    Interaction,
    Rubric,
    RubricCriterion,
    RubricResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _interaction(user_input: str = "hello", agent_output: str = "hi") -> Interaction:
    """Build a minimal Interaction for testing."""
    return Interaction(user_input=user_input, agent_output=agent_output)


def _simple_rubric(name: str = "test_rubric", domain: str = "test") -> Rubric:
    """Build a minimal single-criterion rubric for testing."""
    return Rubric(
        name=name,
        domain=domain,
        criteria=[
            RubricCriterion(name="completeness", description="Substantive response", weight=1.0),
        ],
    )


def _rubric_with_criteria(*names: str) -> Rubric:
    """Build a rubric with multiple named criteria, all weight=1.0."""
    criteria = [RubricCriterion(name=n, description=f"Criterion {n}", weight=1.0) for n in names]
    return Rubric(name="multi_rubric", domain="test", criteria=criteria)


# ---------------------------------------------------------------------------
# 1. Model validation
# ---------------------------------------------------------------------------


def test_rubric_criterion_model():
    """RubricCriterion validates correctly and weight defaults to 1.0."""
    c = RubricCriterion(name="completeness", description="A complete answer")
    assert c.name == "completeness"
    assert c.description == "A complete answer"
    assert c.weight == 1.0


def test_rubric_criterion_custom_weight():
    """RubricCriterion accepts a custom weight."""
    c = RubricCriterion(name="relevance", description="On-topic", weight=0.5)
    assert c.weight == 0.5


def test_rubric_auto_id():
    """Rubric.id auto-generates from name when not provided."""
    rubric = Rubric(name="My Domain Rubric", criteria=[])
    assert rubric.id == "my_domain_rubric"


def test_rubric_explicit_id_preserved():
    """Rubric.id is not overwritten when explicitly set."""
    rubric = Rubric(id="custom_id", name="Something Else", criteria=[])
    assert rubric.id == "custom_id"


def test_rubric_result_timestamp():
    """RubricResult gets a UTC timestamp by default."""

    result = RubricResult(
        rubric_id="test",
        overall_score=0.8,
        criterion_results=[],
    )
    assert result.timestamp is not None
    assert result.timestamp.tzinfo == UTC


# ---------------------------------------------------------------------------
# 2. heuristic_evaluate — completeness scoring
# ---------------------------------------------------------------------------


def test_heuristic_evaluate_short_response():
    """Very short agent output gets a low completeness score."""
    rubric = _simple_rubric()
    interaction = _interaction(user_input="Tell me everything", agent_output="okay")
    result = heuristic_evaluate(interaction, rubric)
    # "okay" = 1 word out of 40 needed → completeness = 0.025
    completeness_result = next(r for r in result.criterion_results if r.criterion == "completeness")
    assert completeness_result.score < 0.1


def test_heuristic_evaluate_long_response():
    """A 40+ word response gets completeness = 1.0."""
    rubric = _simple_rubric()
    long_output = " ".join(["word"] * 50)
    interaction = _interaction(user_input="explain something", agent_output=long_output)
    result = heuristic_evaluate(interaction, rubric)
    completeness_result = next(r for r in result.criterion_results if r.criterion == "completeness")
    assert completeness_result.score == 1.0


def test_heuristic_evaluate_exactly_40_words():
    """A 40-word response hits the completeness cap at 1.0."""
    rubric = _simple_rubric()
    output = " ".join(["word"] * 40)
    interaction = _interaction(user_input="test", agent_output=output)
    result = heuristic_evaluate(interaction, rubric)
    completeness_result = next(r for r in result.criterion_results if r.criterion == "completeness")
    assert completeness_result.score == 1.0


# ---------------------------------------------------------------------------
# 3. heuristic_evaluate — relevance scoring
# ---------------------------------------------------------------------------


def test_heuristic_evaluate_relevant_response():
    """Shared non-stop-word tokens between input and output boost relevance."""
    rubric = _rubric_with_criteria("completeness", "relevance")
    # "python" and "error" are shared, non-stop-word tokens
    interaction = _interaction(
        user_input="python error debugging",
        agent_output="python error traceback stack",
    )
    result = heuristic_evaluate(interaction, rubric)
    relevance_result = next(r for r in result.criterion_results if r.criterion == "relevance")
    assert relevance_result.score > 0.0


def test_heuristic_evaluate_irrelevant_response():
    """No shared non-stop-word tokens yields low (possibly zero) relevance."""
    rubric = _rubric_with_criteria("completeness", "relevance")
    interaction = _interaction(
        user_input="quantum physics neutron",
        agent_output="baking cookies flour sugar",
    )
    result = heuristic_evaluate(interaction, rubric)
    relevance_result = next(r for r in result.criterion_results if r.criterion == "relevance")
    assert relevance_result.score == 0.0


def test_heuristic_evaluate_empty_input_gives_zero_relevance():
    """Empty user_input with no content tokens yields zero relevance."""
    rubric = _rubric_with_criteria("relevance")
    # Only stop words — user_tokens set is empty
    interaction = _interaction(user_input="a the is", agent_output="hello world there")
    result = heuristic_evaluate(interaction, rubric)
    relevance_result = next(r for r in result.criterion_results if r.criterion == "relevance")
    assert relevance_result.score == 0.0


# ---------------------------------------------------------------------------
# 4. heuristic_evaluate — empathy scoring
# ---------------------------------------------------------------------------


def test_heuristic_evaluate_empathy_markers():
    """Empathy marker words in agent output boost the empathy score."""
    rubric = _rubric_with_criteria("empathy")
    interaction = _interaction(
        user_input="I am struggling",
        agent_output="I understand that this is difficult. I hear you and I care about your situation.",
    )
    result = heuristic_evaluate(interaction, rubric)
    empathy_result = next(r for r in result.criterion_results if r.criterion == "empathy")
    # "understand", "difficult", "hear", "care" are all markers → at least 3 markers → score >= 1.0
    assert empathy_result.score >= 1.0


def test_heuristic_evaluate_no_empathy_markers():
    """A technical response with no empathy words scores 0.0 on empathy."""
    rubric = _rubric_with_criteria("empathy")
    interaction = _interaction(
        user_input="fix my code",
        agent_output="Run pip install requests then import requests at the top.",
    )
    result = heuristic_evaluate(interaction, rubric)
    empathy_result = next(r for r in result.criterion_results if r.criterion == "empathy")
    assert empathy_result.score == 0.0


# ---------------------------------------------------------------------------
# 5. heuristic_evaluate — specificity scoring
# ---------------------------------------------------------------------------


def test_heuristic_evaluate_specificity():
    """Technical tokens (numbers, code-like chars) boost the specificity score."""
    rubric = _rubric_with_criteria("specificity")
    interaction = _interaction(
        user_input="how do I install?",
        agent_output="Run pip install requests==2.31.0 then call requests.get() with your URL.",
    )
    result = heuristic_evaluate(interaction, rubric)
    specificity_result = next(r for r in result.criterion_results if r.criterion == "specificity")
    assert specificity_result.score > 0.0


def test_heuristic_evaluate_low_specificity():
    """Plain words with no technical tokens score low on specificity."""
    rubric = _rubric_with_criteria("specificity")
    interaction = _interaction(
        user_input="how are you",
        agent_output="great nice wonderful glad happy okay sure yes",
    )
    result = heuristic_evaluate(interaction, rubric)
    specificity_result = next(r for r in result.criterion_results if r.criterion == "specificity")
    # With recalibrated specificity (counts 6+ char words), "wonderful" scores.
    assert specificity_result.score < 0.5


# ---------------------------------------------------------------------------
# 6. Weighted average math
# ---------------------------------------------------------------------------


def test_heuristic_overall_score_is_weighted_average():
    """overall_score is the correct weighted average of criterion scores."""
    # Use a rubric with two criteria at different weights so we can verify the math
    criteria = [
        RubricCriterion(name="completeness", description="Complete", weight=2.0),
        RubricCriterion(name="relevance", description="Relevant", weight=1.0),
    ]
    rubric = Rubric(name="weighted_test", domain="test", criteria=criteria)

    # Use an interaction that produces predictable scores:
    # "hello world" = 2 words → completeness = 2/40 = 0.05
    # No shared non-stop tokens between "quantum" and "hello world" → relevance = 0.0
    interaction = _interaction(user_input="quantum", agent_output="hello world")
    result = heuristic_evaluate(interaction, rubric)

    completeness_score = next(
        r for r in result.criterion_results if r.criterion == "completeness"
    ).score
    relevance_score = next(r for r in result.criterion_results if r.criterion == "relevance").score

    expected = (completeness_score * 2.0 + relevance_score * 1.0) / (2.0 + 1.0)
    assert abs(result.overall_score - expected) < 1e-9


# ---------------------------------------------------------------------------
# 7. Learning string
# ---------------------------------------------------------------------------


def test_heuristic_evaluate_learning_string():
    """Learning string mentions the rubric name, strongest, and weakest criteria."""
    criteria = [
        RubricCriterion(name="completeness", description="Complete", weight=1.0),
        RubricCriterion(name="empathy", description="Empathetic", weight=1.0),
    ]
    rubric = Rubric(name="companion_check", domain="test", criteria=criteria)

    # Short output → low completeness; empathy marker → higher empathy
    interaction = _interaction(
        user_input="I feel sad",
        agent_output="I understand",
    )
    result = heuristic_evaluate(interaction, rubric)

    assert "companion_check" in result.learning
    assert "Strongest:" in result.learning
    assert "Weakest:" in result.learning


# ---------------------------------------------------------------------------
# 8. DEFAULT_RUBRICS coverage
# ---------------------------------------------------------------------------


def test_evaluator_default_rubrics():
    """All 6 seed domains have rubrics in DEFAULT_RUBRICS."""
    expected_domains = {
        "technical_helper",
        "creative_writer",
        "knowledge_guide",
        "problem_solver",
        "creative_collaborator",
        "emotional_companion",
    }
    assert set(DEFAULT_RUBRICS.keys()) == expected_domains


def test_default_rubrics_each_have_criteria():
    """Every default rubric contains at least one criterion."""
    for domain, rubric in DEFAULT_RUBRICS.items():
        assert len(rubric.criteria) > 0, f"{domain} rubric has no criteria"


# ---------------------------------------------------------------------------
# 9. Evaluator — auto-selection by domain
# ---------------------------------------------------------------------------


async def test_evaluator_evaluate_auto_selects_domain():
    """Evaluator picks the rubric matching the given domain."""
    evaluator = Evaluator()
    interaction = _interaction(
        user_input="I feel lonely",
        agent_output="I understand your feelings. I hear you and I care.",
    )
    result = await evaluator.evaluate(interaction, domain="emotional_companion")
    assert result.rubric_id == "emotional_companion"


async def test_evaluator_evaluate_unknown_domain_falls_back():
    """Evaluator falls back to technical_helper for an unknown domain."""
    evaluator = Evaluator()
    interaction = _interaction()
    result = await evaluator.evaluate(interaction, domain="nonexistent_domain")
    assert result.rubric_id == "technical_helper"


async def test_evaluator_evaluate_no_domain_uses_technical_helper():
    """Evaluator defaults to technical_helper when no domain or rubric is given."""
    evaluator = Evaluator()
    interaction = _interaction()
    result = await evaluator.evaluate(interaction)
    assert result.rubric_id == "technical_helper"


# ---------------------------------------------------------------------------
# 10. Evaluator — explicit rubric override
# ---------------------------------------------------------------------------


async def test_evaluator_evaluate_with_explicit_rubric():
    """Passing an explicit rubric overrides domain auto-selection."""
    evaluator = Evaluator()
    custom_rubric = Rubric(
        id="custom_eval",
        name="custom_eval",
        domain="custom",
        criteria=[
            RubricCriterion(name="completeness", description="Complete", weight=1.0),
        ],
    )
    interaction = _interaction()
    result = await evaluator.evaluate(interaction, rubric=custom_rubric)
    assert result.rubric_id == "custom_eval"


# ---------------------------------------------------------------------------
# 11. Evaluator — history cap
# ---------------------------------------------------------------------------


async def test_evaluator_history_capped():
    """History does not grow beyond max_history (100 by default)."""
    evaluator = Evaluator()
    interaction = _interaction()

    # Evaluate 110 times to exceed the default cap of 100
    for _ in range(110):
        await evaluator.evaluate(interaction)

    assert len(evaluator._history) == 100


async def test_evaluator_history_grows_before_cap():
    """History accumulates normally up to max_history."""
    evaluator = Evaluator()
    interaction = _interaction()

    for i in range(5):
        await evaluator.evaluate(interaction)

    assert len(evaluator._history) == 5


# ---------------------------------------------------------------------------
# 12. Evaluator — domain stats
# ---------------------------------------------------------------------------


async def test_evaluator_domain_stats():
    """get_domain_stats returns correct count, avg_score, and streak."""
    evaluator = Evaluator()
    # Use a custom rubric so we control the rubric_id
    rubric = Rubric(
        id="knowledge_guide",
        name="knowledge_guide",
        domain="knowledge_guide",
        criteria=[
            RubricCriterion(name="completeness", description="Complete", weight=1.0),
        ],
    )
    # 40-word output → completeness = 1.0 → overall_score = 1.0
    long_output = " ".join(["word"] * 40)
    interaction = _interaction(user_input="explain", agent_output=long_output)

    await evaluator.evaluate(interaction, rubric=rubric)
    await evaluator.evaluate(interaction, rubric=rubric)

    stats = evaluator.get_domain_stats("knowledge_guide")
    assert stats["domain"] == "knowledge_guide"
    assert stats["count"] == 2
    assert abs(stats["avg_score"] - 1.0) < 0.01
    assert stats["streak"] == 2


async def test_evaluator_domain_stats_empty():
    """get_domain_stats returns zeros for a domain with no history."""
    evaluator = Evaluator()
    stats = evaluator.get_domain_stats("nonexistent_domain")
    assert stats["count"] == 0
    assert stats["avg_score"] == 0.0
    assert stats["streak"] == 0


# ---------------------------------------------------------------------------
# 13. Evaluator — streak detection
# ---------------------------------------------------------------------------


def test_evaluator_streak_detection():
    """Five or more consecutive high scores (>=0.7) are counted as a streak."""
    evaluator = Evaluator()

    # Inject results directly so the score is controlled and above 0.7
    def _make_result(score: float) -> RubricResult:
        return RubricResult(
            rubric_id="technical_helper",
            overall_score=score,
            criterion_results=[],
        )

    # 6 consecutive scores all >= 0.7
    evaluator._history = [_make_result(0.85) for _ in range(6)]

    stats = evaluator.get_domain_stats("technical_helper")
    assert stats["streak"] >= 5


def test_evaluator_streak_breaks_on_low_score():
    """A low score in the middle resets the streak count."""
    evaluator = Evaluator()
    from soul_protocol.runtime.types import RubricResult

    # Inject results directly to avoid evaluator logic
    # Pattern: 3 high, 1 low, 2 high → streak should be 2
    def _make_result(score: float) -> RubricResult:
        return RubricResult(
            rubric_id="technical_helper",
            overall_score=score,
            criterion_results=[],
        )

    evaluator._history = [
        _make_result(0.9),
        _make_result(0.8),
        _make_result(0.9),
        _make_result(0.3),  # break
        _make_result(0.8),
        _make_result(0.9),
    ]

    stats = evaluator.get_domain_stats("technical_helper")
    assert stats["streak"] == 2


# ---------------------------------------------------------------------------
# 14. Evaluator — no false evolution triggers
# ---------------------------------------------------------------------------


def test_evaluator_no_false_triggers():
    """Mixed scores (some low) do not trigger evolution proposals."""
    evaluator = Evaluator()

    def _make_result(score: float) -> RubricResult:
        return RubricResult(
            rubric_id="technical_helper",
            overall_score=score,
            criterion_results=[],
        )

    # Alternating high and low — no streak of 5 high scores
    evaluator._history = [
        _make_result(0.9),
        _make_result(0.2),
        _make_result(0.9),
        _make_result(0.2),
        _make_result(0.9),
    ]

    triggers = evaluator.check_evolution_triggers()
    assert triggers == []


# ---------------------------------------------------------------------------
# 15. Evaluator — evolution trigger on high streak
# ---------------------------------------------------------------------------


def test_evaluator_evolution_trigger():
    """Five consecutive high scores with good avg triggers an evolution proposal."""
    evaluator = Evaluator()

    def _make_result(score: float) -> RubricResult:
        return RubricResult(
            rubric_id="technical_helper",
            overall_score=score,
            criterion_results=[],
        )

    # 6 consecutive high scores, avg well above 0.75
    evaluator._history = [_make_result(0.9) for _ in range(6)]

    triggers = evaluator.check_evolution_triggers()
    assert len(triggers) == 1
    trigger = triggers[0]
    assert trigger["domain"] == "technical_helper"
    assert trigger["trigger"] == "high_performance_streak"
    assert trigger["streak"] >= 5
    assert trigger["avg_score"] >= 0.75


def test_evaluator_evolution_trigger_requires_high_avg():
    """A streak of 5 is not enough if avg_score is below the trigger threshold (0.55)."""
    evaluator = Evaluator()

    def _make_result(score: float) -> RubricResult:
        return RubricResult(
            rubric_id="technical_helper",
            overall_score=score,
            criterion_results=[],
        )

    # 5 scores at exactly 0.50 → streak=0 (below 0.55), avg=0.50 < 0.55 → no trigger
    evaluator._history = [_make_result(0.50) for _ in range(5)]

    triggers = evaluator.check_evolution_triggers()
    assert triggers == []


# ---------------------------------------------------------------------------
# 16. Evaluator — serialization roundtrip
# ---------------------------------------------------------------------------


async def test_evaluator_serialization_roundtrip():
    """to_dict() + from_dict() preserves history length and scores."""
    evaluator = Evaluator()
    interaction = _interaction(
        user_input="explain recursion",
        agent_output=" ".join(["word"] * 20),
    )

    await evaluator.evaluate(interaction, domain="technical_helper")
    await evaluator.evaluate(interaction, domain="knowledge_guide")

    data = evaluator.to_dict()
    restored = Evaluator.from_dict(data)

    assert len(restored._history) == len(evaluator._history)
    for original, restored_result in zip(evaluator._history, restored._history):
        assert abs(original.overall_score - restored_result.overall_score) < 1e-9
        assert original.rubric_id == restored_result.rubric_id


async def test_evaluator_serialization_roundtrip_empty():
    """to_dict() + from_dict() handles empty history gracefully."""
    evaluator = Evaluator()
    data = evaluator.to_dict()
    restored = Evaluator.from_dict(data)
    assert restored._history == []


async def test_evaluator_from_dict_preserves_timestamps():
    """Restored history entries have the same timestamp as originals."""
    evaluator = Evaluator()
    interaction = _interaction()
    await evaluator.evaluate(interaction)

    original_ts = evaluator._history[0].timestamp
    data = evaluator.to_dict()
    restored = Evaluator.from_dict(data)

    assert restored._history[0].timestamp == original_ts
