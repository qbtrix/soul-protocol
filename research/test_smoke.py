# test_smoke.py — Smoke tests for the research simulation framework.
# Created 2026-03-06. Validates that all framework components work end-to-end
# at minimal scale (no 1000-agent runs). Fast enough to run in CI.

from __future__ import annotations

import pytest

from research.agents import UserProfile, generate_agents, generate_users
from research.conditions import NoMemoryCondition, ObserveResult
from research.config import ExperimentConfig, MemoryCondition, UseCase
from research.metrics import (
    AgentRunMetrics,
    BondMetrics,
    EmotionalMetrics,
    MemoryEfficiencyMetrics,
    PersonalityMetrics,
    RecallMetrics,
    SkillMetrics,
    cohens_d,
    confidence_interval_95,
    mann_whitney_u,
)
from research.scenarios import Scenario, Turn, generate_scenarios

# ---------------------------------------------------------------------------
# Agent generation
# ---------------------------------------------------------------------------


def test_agent_generation():
    """Generate 10 agents, verify OCEAN traits are in range and names are unique."""
    agents = generate_agents(n=10, seed=99)

    assert len(agents) == 10

    names = set()
    for agent in agents:
        # Unique names
        assert agent.name not in names
        names.add(agent.name)

        # OCEAN traits within truncated normal bounds [0.05, 0.95]
        for trait, value in agent.ocean.items():
            assert trait in (
                "openness",
                "conscientiousness",
                "extraversion",
                "agreeableness",
                "neuroticism",
            ), f"Unexpected trait: {trait}"
            assert 0.05 <= value <= 0.95, f"{trait}={value} out of range"

        # Derived behavioral tendencies should match OCEAN values
        assert agent.emotional_reactivity == agent.ocean["neuroticism"]
        assert agent.detail_orientation == agent.ocean["conscientiousness"]
        assert agent.social_energy == agent.ocean["extraversion"]

        # Communication style fields are present
        assert agent.communication["warmth"] in ("low", "medium", "high")
        assert agent.communication["verbosity"] in (
            "minimal",
            "low",
            "medium",
            "high",
            "verbose",
        )
        assert agent.communication["formality"] in ("casual", "neutral", "formal")

    assert len(names) == 10


# ---------------------------------------------------------------------------
# User generation
# ---------------------------------------------------------------------------


def test_user_generation():
    """Generate 10 users per use case, verify required fields."""
    for use_case in ("support", "coding", "companion", "knowledge"):
        users = generate_users(n=10, seed=42, use_case=use_case)

        assert len(users) == 10

        for user in users:
            assert isinstance(user, UserProfile)
            assert user.name.startswith("User-")
            assert user.interaction_style in (
                "brief",
                "detailed",
                "emotional",
                "technical",
                "mixed",
            )
            assert len(user.topic_interests) >= 2
            assert 0.0 <= user.consistency <= 1.0
            assert -1.0 <= user.sentiment_bias <= 1.0


# ---------------------------------------------------------------------------
# Scenario generation
# ---------------------------------------------------------------------------


def test_scenario_generation():
    """Generate scenarios for a user, verify turns have required fields."""
    users = generate_users(n=1, seed=42, use_case="support")
    user = users[0]

    scenarios = generate_scenarios(user=user, use_case="support", seed=42)

    assert len(scenarios) > 0

    for scenario in scenarios:
        assert isinstance(scenario, Scenario)
        assert scenario.use_case == "support"
        assert len(scenario.turns) > 0

        for turn in scenario.turns:
            assert isinstance(turn, Turn)
            assert isinstance(turn.user_input, str) and len(turn.user_input) > 0
            assert isinstance(turn.agent_output, str) and len(turn.agent_output) > 0
            assert isinstance(turn.contains_fact, bool)
            assert isinstance(turn.importance_hint, float)
            assert 0.0 <= turn.importance_hint <= 1.0

        # Planted facts and recall queries should be present
        assert isinstance(scenario.planted_facts, list)
        assert isinstance(scenario.recall_queries, list)
        for query, expected in scenario.recall_queries:
            assert isinstance(query, str)
            assert isinstance(expected, str)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_defaults():
    """Verify ExperimentConfig defaults match expected values."""
    config = ExperimentConfig()

    assert config.num_agents == 1000
    assert config.interactions_per_agent == 50
    assert config.num_sessions == 5
    assert config.interactions_per_session == 10
    assert config.random_seed == 42
    assert config.significance_threshold == 0.3
    assert config.activation_decay_rate == 0.95
    assert config.ocean_mean == 0.5
    assert config.ocean_std == 0.15
    assert config.output_dir == "research/results"

    # All conditions and use cases present by default
    assert len(config.conditions) == len(MemoryCondition)
    assert len(config.use_cases) == len(UseCase)


def test_config_total_runs():
    """Verify total_runs = num_agents * conditions * use_cases."""
    config = ExperimentConfig(
        num_agents=10,
        conditions=[MemoryCondition.NONE, MemoryCondition.FULL_SOUL],
        use_cases=[UseCase.PERSONAL_COMPANION],
    )

    assert config.total_runs == 10 * 2 * 1
    assert config.total_interactions == config.total_runs * config.interactions_per_agent


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_metrics_to_row():
    """Create AgentRunMetrics, verify to_row() has all expected keys."""
    metrics = AgentRunMetrics(
        agent_id=0,
        condition="none",
        use_case="support",
        recall=RecallMetrics(
            precision_scores=[0.8, 0.6],
            recall_scores=[1.0, 0.0],
            hit_at_k=[True, False],
        ),
        emotional=EmotionalMetrics(emotion_accuracy=[True, False, True]),
        personality=PersonalityMetrics(
            trait_drift={"openness": [0.01, 0.02]},
        ),
        efficiency=MemoryEfficiencyMetrics(
            memory_growth_rate=[(5, 3), (10, 6)],
        ),
        bond=BondMetrics(strength_trajectory=[0.0, 0.1, 0.2]),
        skills=SkillMetrics(skills_discovered=2, max_level=1),
    )

    row = metrics.to_row()

    expected_keys = {
        "agent_id",
        "condition",
        "use_case",
        "recall_precision",
        "recall_recall",
        "recall_hit_rate",
        "emotion_accuracy",
        "bond_final",
        "bond_growth_rate",
        "personality_drift",
        "memory_compression",
        "memory_count",
        "skills_discovered",
        "skills_max_level",
    }
    assert set(row.keys()) == expected_keys

    # Spot-check computed values
    assert row["agent_id"] == 0
    assert row["condition"] == "none"
    assert row["recall_precision"] == pytest.approx(0.7)  # mean(0.8, 0.6)
    assert row["recall_hit_rate"] == pytest.approx(0.5)  # 1 of 2 hits
    assert row["emotion_accuracy"] == pytest.approx(2 / 3)
    assert row["bond_final"] == pytest.approx(0.2)
    assert row["skills_discovered"] == 2
    assert row["memory_count"] == 6  # last tuple's memory count


# ---------------------------------------------------------------------------
# Statistical utilities
# ---------------------------------------------------------------------------


def test_statistical_utils():
    """Test cohens_d, confidence_interval_95, mann_whitney_u with known values."""
    # Cohen's d: two identical groups should yield d=0
    group = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert cohens_d(group, group) == pytest.approx(0.0)

    # Cohen's d: shifted group should yield a positive d
    shifted = [x + 10 for x in group]
    d = cohens_d(shifted, group)
    assert d > 0
    # With identical variance and a 10-unit shift, d should be large
    assert d > 2.0

    # Cohen's d: empty inputs
    assert cohens_d([], [1.0, 2.0]) == 0.0
    assert cohens_d([1.0], []) == 0.0

    # Confidence interval: known data
    data = [10.0, 10.0, 10.0, 10.0, 10.0]
    lo, hi = confidence_interval_95(data)
    # All identical values, std=0, so CI should collapse to the mean
    assert lo == pytest.approx(10.0)
    assert hi == pytest.approx(10.0)

    # Confidence interval: insufficient data
    lo, hi = confidence_interval_95([5.0])
    assert lo == 0.0
    assert hi == 0.0

    # Mann-Whitney U: identical groups should yield p close to 1 (not significant)
    _, p = mann_whitney_u(group, group)
    # p should not be significant
    assert p > 0.05

    # Mann-Whitney U: clearly separated groups should be significant
    low = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    high = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0]
    u_stat, p_val = mann_whitney_u(low, high)
    assert p_val < 0.05
    assert u_stat == pytest.approx(0.0)  # no overlap, U should be 0

    # Mann-Whitney U: empty inputs
    u, p = mann_whitney_u([], [1.0])
    assert u == 0.0
    assert p == 1.0


# ---------------------------------------------------------------------------
# NoMemoryCondition (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_memory_condition():
    """Create NoMemoryCondition, setup, observe, verify empty recall."""
    from soul_protocol.runtime.types import Interaction

    condition = NoMemoryCondition()
    await condition.setup(agent_profile=None)

    # Observe an interaction
    interaction = Interaction(
        user_input="My name is Alex and I like pizza.",
        agent_output="Nice to meet you, Alex!",
    )
    result = await condition.observe(interaction)

    assert isinstance(result, ObserveResult)
    assert result.facts_extracted == []
    assert result.significance_score == 0.0
    assert result.somatic_valence is None
    assert result.stored_episodic is False
    assert result.memory_count == 0

    # Recall should always return empty
    recalled = await condition.recall("What is the user's name?")
    assert recalled == []

    # State should reflect interaction count but zero memories
    state = await condition.get_state()
    assert state["interactions"] == 1
    assert state["memories"] == 0

    # Reset clears interaction count
    await condition.reset()
    state = await condition.get_state()
    assert state["interactions"] == 0
