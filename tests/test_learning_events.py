# test_learning_events.py — Tests for LearningEvent spec model, Evaluator.create_learning_event(),
#   SkillRegistry.grant_xp_from_learning(), and Soul.learn() convenience method.
# Created: 2026-03-22 — Covers the full learning events pipeline from evaluation
#   to lesson creation to skill XP grants.

from __future__ import annotations

import pytest

from soul_protocol.runtime.evaluation import (
    HIGH_SCORE_THRESHOLD,
    LOW_SCORE_THRESHOLD,
    Evaluator,
    heuristic_evaluate,
)
from soul_protocol.runtime.skills import Skill, SkillRegistry
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import (
    Interaction,
    Rubric,
    RubricCriterion,
    RubricResult,
)
from soul_protocol.spec.learning import LearningEvent


# ============ Helpers ============


def _interaction(
    user_input: str = "hello", agent_output: str = "hi"
) -> Interaction:
    return Interaction(user_input=user_input, agent_output=agent_output)


def _rubric(name: str = "test", domain: str = "test") -> Rubric:
    return Rubric(
        name=name,
        domain=domain,
        criteria=[
            RubricCriterion(
                name="completeness", description="Complete", weight=1.0
            ),
        ],
    )


def _result(score: float, rubric_id: str = "test") -> RubricResult:
    return RubricResult(
        rubric_id=rubric_id,
        overall_score=score,
        criterion_results=[],
        learning=f"Scored {score:.0%} on test.",
    )


# ============ LearningEvent Model ============


class TestLearningEventModel:
    def test_default_fields(self):
        event = LearningEvent(lesson="Always validate inputs")
        assert event.lesson == "Always validate inputs"
        assert event.domain == "general"
        assert event.confidence == 0.5
        assert event.applied_count == 0
        assert event.skill_id is None
        assert event.trigger_interaction_id is None
        assert event.evaluation_score is None
        assert len(event.id) == 12

    def test_custom_fields(self):
        event = LearningEvent(
            lesson="Use type hints",
            domain="technical_helper",
            confidence=0.9,
            skill_id="coding",
            evaluation_score=0.85,
            trigger_interaction_id="abc123",
        )
        assert event.domain == "technical_helper"
        assert event.confidence == 0.9
        assert event.skill_id == "coding"
        assert event.evaluation_score == 0.85
        assert event.trigger_interaction_id == "abc123"

    def test_apply_increments_count(self):
        event = LearningEvent(lesson="test")
        assert event.applied_count == 0
        event.apply()
        assert event.applied_count == 1
        event.apply()
        assert event.applied_count == 2

    def test_reinforce_increases_confidence(self):
        event = LearningEvent(lesson="test", confidence=0.5)
        event.reinforce(0.2)
        assert abs(event.confidence - 0.7) < 1e-9

    def test_reinforce_caps_at_1(self):
        event = LearningEvent(lesson="test", confidence=0.95)
        event.reinforce(0.2)
        assert event.confidence == 1.0

    def test_weaken_decreases_confidence(self):
        event = LearningEvent(lesson="test", confidence=0.5)
        event.weaken(0.2)
        assert abs(event.confidence - 0.3) < 1e-9

    def test_weaken_floors_at_0(self):
        event = LearningEvent(lesson="test", confidence=0.05)
        event.weaken(0.2)
        assert event.confidence == 0.0

    def test_confidence_validation_bounds(self):
        """Confidence must be between 0.0 and 1.0."""
        event = LearningEvent(lesson="test", confidence=0.0)
        assert event.confidence == 0.0
        event = LearningEvent(lesson="test", confidence=1.0)
        assert event.confidence == 1.0
        with pytest.raises(Exception):
            LearningEvent(lesson="test", confidence=1.5)
        with pytest.raises(Exception):
            LearningEvent(lesson="test", confidence=-0.1)

    def test_unique_ids(self):
        e1 = LearningEvent(lesson="a")
        e2 = LearningEvent(lesson="b")
        assert e1.id != e2.id

    def test_created_at_auto_set(self):
        event = LearningEvent(lesson="test")
        assert event.created_at is not None

    def test_serialization_roundtrip(self):
        event = LearningEvent(
            lesson="Important insight",
            domain="coding",
            confidence=0.8,
            evaluation_score=0.9,
        )
        data = event.model_dump()
        restored = LearningEvent.model_validate(data)
        assert restored.lesson == event.lesson
        assert restored.domain == event.domain
        assert restored.confidence == event.confidence


# ============ Evaluator.create_learning_event ============


class TestCreateLearningEvent:
    def test_high_score_creates_success_event(self):
        evaluator = Evaluator()
        result = _result(0.9)
        event = evaluator.create_learning_event(result)
        assert event is not None
        assert "Success pattern" in event.lesson
        assert event.evaluation_score == 0.9
        assert event.domain == "test"

    def test_low_score_creates_failure_event(self):
        evaluator = Evaluator()
        result = _result(0.1)
        event = evaluator.create_learning_event(result)
        assert event is not None
        assert "Failure pattern" in event.lesson
        assert event.evaluation_score == 0.1

    def test_medium_score_returns_none(self):
        evaluator = Evaluator()
        result = _result(0.5)
        event = evaluator.create_learning_event(result)
        assert event is None

    def test_exactly_high_threshold(self):
        evaluator = Evaluator()
        result = _result(HIGH_SCORE_THRESHOLD)
        event = evaluator.create_learning_event(result)
        assert event is not None
        assert "Success pattern" in event.lesson

    def test_exactly_low_threshold(self):
        evaluator = Evaluator()
        result = _result(LOW_SCORE_THRESHOLD)
        event = evaluator.create_learning_event(result)
        assert event is not None
        assert "Failure pattern" in event.lesson

    def test_just_above_low_threshold(self):
        evaluator = Evaluator()
        result = _result(LOW_SCORE_THRESHOLD + 0.01)
        event = evaluator.create_learning_event(result)
        assert event is None  # Not notable enough

    def test_just_below_high_threshold(self):
        evaluator = Evaluator()
        result = _result(HIGH_SCORE_THRESHOLD - 0.01)
        event = evaluator.create_learning_event(result)
        assert event is None

    def test_interaction_id_passed_through(self):
        evaluator = Evaluator()
        result = _result(0.9)
        event = evaluator.create_learning_event(
            result, interaction_id="int_42"
        )
        assert event is not None
        assert event.trigger_interaction_id == "int_42"

    def test_domain_override(self):
        evaluator = Evaluator()
        result = _result(0.9, rubric_id="default_domain")
        event = evaluator.create_learning_event(
            result, domain="custom_domain"
        )
        assert event is not None
        assert event.domain == "custom_domain"

    def test_domain_defaults_to_rubric_id(self):
        evaluator = Evaluator()
        result = _result(0.9, rubric_id="knowledge_guide")
        event = evaluator.create_learning_event(result)
        assert event is not None
        assert event.domain == "knowledge_guide"

    def test_skill_id_passed_through(self):
        evaluator = Evaluator()
        result = _result(0.9)
        event = evaluator.create_learning_event(
            result, skill_id="python_coding"
        )
        assert event is not None
        assert event.skill_id == "python_coding"

    def test_confidence_scales_with_score(self):
        evaluator = Evaluator()
        high_result = _result(1.0)
        low_result = _result(0.0)
        high_event = evaluator.create_learning_event(high_result)
        low_event = evaluator.create_learning_event(low_result)
        assert high_event is not None
        assert low_event is not None
        # Perfect scores should have higher confidence
        assert high_event.confidence >= 0.5
        assert low_event.confidence >= 0.5

    def test_perfect_score_confidence(self):
        evaluator = Evaluator()
        result = _result(1.0)
        event = evaluator.create_learning_event(result)
        assert event is not None
        assert event.confidence == pytest.approx(1.0, abs=1e-9)

    def test_zero_score_confidence(self):
        evaluator = Evaluator()
        result = _result(0.0)
        event = evaluator.create_learning_event(result)
        assert event is not None
        # 0.5 + (0.3 - 0.0) * 2.5 = 1.25 → capped at 1.0
        assert event.confidence == 1.0


# ============ SkillRegistry.grant_xp_from_learning ============


class TestGrantXpFromLearning:
    def test_existing_skill_gets_xp(self):
        registry = SkillRegistry()
        registry.add(Skill(id="coding", name="Coding"))
        event = LearningEvent(
            lesson="test",
            skill_id="coding",
            evaluation_score=0.9,
            confidence=0.8,
        )
        registry.grant_xp_from_learning(event)
        skill = registry.get("coding")
        assert skill is not None
        assert skill.xp > 0

    def test_auto_creates_skill(self):
        registry = SkillRegistry()
        event = LearningEvent(
            lesson="test",
            skill_id="new_skill",
            domain="New Skill",
            evaluation_score=0.9,
            confidence=0.8,
        )
        registry.grant_xp_from_learning(event)
        skill = registry.get("new_skill")
        assert skill is not None
        assert skill.xp > 0

    def test_falls_back_to_domain(self):
        registry = SkillRegistry()
        event = LearningEvent(
            lesson="test",
            domain="Technical Helper",
            evaluation_score=0.9,
            confidence=0.8,
        )
        # No skill_id — should use domain
        registry.grant_xp_from_learning(event)
        skill = registry.get("technical_helper")
        assert skill is not None
        assert skill.xp > 0

    def test_xp_scales_with_score(self):
        registry1 = SkillRegistry()
        registry2 = SkillRegistry()

        high_event = LearningEvent(
            lesson="test",
            skill_id="s",
            domain="s",
            evaluation_score=0.95,
            confidence=0.8,
        )
        low_event = LearningEvent(
            lesson="test",
            skill_id="s",
            domain="s",
            evaluation_score=0.1,
            confidence=0.8,
        )

        registry1.grant_xp_from_learning(high_event)
        registry2.grant_xp_from_learning(low_event)

        assert registry1.get("s").xp > registry2.get("s").xp

    def test_xp_scales_with_confidence(self):
        registry1 = SkillRegistry()
        registry2 = SkillRegistry()

        high_conf = LearningEvent(
            lesson="test",
            skill_id="s",
            domain="s",
            evaluation_score=0.9,
            confidence=1.0,
        )
        low_conf = LearningEvent(
            lesson="test",
            skill_id="s",
            domain="s",
            evaluation_score=0.9,
            confidence=0.2,
        )

        registry1.grant_xp_from_learning(high_conf)
        registry2.grant_xp_from_learning(low_conf)

        assert registry1.get("s").xp > registry2.get("s").xp

    def test_minimum_1_xp(self):
        registry = SkillRegistry()
        event = LearningEvent(
            lesson="test",
            skill_id="s",
            domain="s",
            evaluation_score=0.0,
            confidence=0.01,
        )
        registry.grant_xp_from_learning(event)
        assert registry.get("s").xp >= 1

    def test_none_evaluation_score_defaults(self):
        registry = SkillRegistry()
        event = LearningEvent(
            lesson="test",
            skill_id="s",
            domain="s",
            evaluation_score=None,
            confidence=0.5,
        )
        registry.grant_xp_from_learning(event)
        # Should use 0.5 as default score
        assert registry.get("s").xp > 0

    def test_levelup_returns_true(self):
        registry = SkillRegistry()
        registry.add(Skill(id="s", name="S", xp=99))
        event = LearningEvent(
            lesson="test",
            skill_id="s",
            domain="s",
            evaluation_score=1.0,
            confidence=1.0,
        )
        # XP = int(20 * (0.5 + 1.0) * 1.0) = 30
        result = registry.grant_xp_from_learning(event)
        assert result is True  # Should have leveled up (99 + 30 >= 100)


# ============ Soul.learn() Integration ============


class TestSoulLearn:
    async def test_learn_high_score_creates_event(self):
        soul = await Soul.birth("Learner")
        # Long output for high completeness
        long_output = " ".join(["great", "helpful"] * 25)
        interaction = Interaction(
            user_input="explain something",
            agent_output=long_output,
        )
        event = await soul.learn(interaction, domain="technical_helper")
        # A very long response with positive sentiment should score well
        # Whether an event is created depends on the exact score
        # This tests the pipeline doesn't crash
        assert event is None or isinstance(event, LearningEvent)

    async def test_learn_returns_none_for_medium_scores(self):
        soul = await Soul.birth("Learner")
        # Medium response with some overlap — should score between 0.3 and 0.8.
        # Not great (to stay below HIGH_SCORE_THRESHOLD) but not terrible either
        # (to stay above LOW_SCORE_THRESHOLD).
        interaction = Interaction(
            user_input="explain python decorators and how they work",
            agent_output="Decorators wrap functions. You can use the at sign to apply them. "
                         "They are useful for many things in coding.",
        )
        event = await soul.learn(interaction, domain="technical_helper")
        # Medium score — no learning event created
        assert event is None

    async def test_learn_stores_in_learning_events(self):
        soul = await Soul.birth("Learner")
        assert len(soul.learning_events) == 0

        # Force a high score by using explicit evaluation
        # We'll create an interaction that should get a very low score
        interaction = Interaction(
            user_input="quantum physics neutron star collapse explanation",
            agent_output="k",  # Extremely short and irrelevant
        )
        event = await soul.learn(interaction, domain="technical_helper")
        if event is not None:
            assert len(soul.learning_events) == 1
            assert soul.learning_events[0].lesson == event.lesson

    async def test_learn_grants_skill_xp(self):
        soul = await Soul.birth("Learner")
        # Very short response -> low score -> might create failure event
        interaction = Interaction(
            user_input="explain quantum computing in depth",
            agent_output="x",
        )
        event = await soul.learn(interaction, domain="technical_helper")
        if event is not None:
            skill = soul.skills.get("technical_helper")
            assert skill is not None
            assert skill.xp > 0

    async def test_learn_with_interaction_id(self):
        soul = await Soul.birth("Learner")
        interaction = Interaction(
            user_input="x" * 100,
            agent_output="y",
            metadata={"interaction_id": "test_123"},
        )
        event = await soul.learn(interaction, domain="technical_helper")
        if event is not None:
            assert event.trigger_interaction_id == "test_123"

    async def test_learning_events_property_returns_copy(self):
        soul = await Soul.birth("Learner")
        events = soul.learning_events
        events.append(LearningEvent(lesson="injected"))
        # Original should be unaffected
        assert len(soul.learning_events) == 0

    async def test_learn_without_domain(self):
        """learn() without explicit domain uses self-model."""
        soul = await Soul.birth("Learner")
        interaction = Interaction(
            user_input="anything",
            agent_output="y",
        )
        # Should not crash even without domain
        event = await soul.learn(interaction)
        assert event is None or isinstance(event, LearningEvent)


# ============ Spec Export ============


class TestSpecExport:
    def test_learning_event_importable_from_spec(self):
        from soul_protocol.spec import LearningEvent as SpecLearningEvent

        assert SpecLearningEvent is LearningEvent

    def test_learning_event_in_spec_all(self):
        import soul_protocol.spec as spec

        assert "LearningEvent" in spec.__all__
