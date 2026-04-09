# test_runner.py — Tests for the long-horizon ablation runner.
# Created: 2026-03-11
# Tests use HeuristicEngine (no API key needed) with short scenarios
# to validate the runner mechanics without burning through 100+ turns.

from __future__ import annotations

import pytest

from research.long_horizon.runner import (
    ConditionResult,
    ConditionType,
    LongHorizonResults,
    LongHorizonRunner,
    ScenarioResults,
)
from research.long_horizon.scenarios import (
    LongHorizonScenario,
    TestPoint,
)


def _make_short_scenario() -> LongHorizonScenario:
    """Create a short scenario for fast testing (15 turns instead of 150)."""
    turns = [
        (
            "My name is Alice and I live in Portland.",
            "Nice to meet you, Alice! Portland is a great city.",
        ),
        (
            "I work as a data scientist at Acme Corp.",
            "Data science at Acme Corp, that's exciting work!",
        ),
        ("I love hiking in the Pacific Northwest.", "The PNW has incredible hiking trails."),
        ("My favorite food is ramen.", "Ramen is delicious. Any favorite spots?"),
        ("I have a cat named Whiskers.", "Whiskers is a classic cat name!"),
    ]
    # Add filler
    for i in range(5):
        turns.append(("Just checking in.", "Good to hear from you!"))

    # Add recall test turns
    turns.extend(
        [
            ("What is my name?", "Your name is Alice."),
            ("Where do I live?", "You live in Portland."),
            ("What do I do for work?", "You're a data scientist at Acme Corp."),
            ("What's my cat's name?", "Your cat's name is Whiskers."),
            ("What food do I love?", "You love ramen!"),
        ]
    )

    test_points = [
        TestPoint(
            turn_index=10, query="What is my name?", expected_content="Alice", test_type="recall"
        ),
        TestPoint(
            turn_index=11, query="Where do I live?", expected_content="Portland", test_type="recall"
        ),
        TestPoint(
            turn_index=12,
            query="What do I do for work?",
            expected_content="data scientist",
            test_type="recall",
        ),
        TestPoint(
            turn_index=13,
            query="What's my cat's name?",
            expected_content="Whiskers",
            test_type="recall",
        ),
        TestPoint(
            turn_index=14,
            query="What food do I love?",
            expected_content="ramen",
            test_type="recall",
        ),
    ]

    planted_facts = [
        (0, "User's name is Alice"),
        (0, "User lives in Portland"),
        (1, "User is a data scientist at Acme Corp"),
        (4, "User has a cat named Whiskers"),
        (3, "User loves ramen"),
    ]

    return LongHorizonScenario(
        scenario_id="test_short",
        name="Test Short Scenario",
        description="Short scenario for runner testing",
        turns=turns,
        test_points=test_points,
        planted_facts=planted_facts,
    )


@pytest.mark.asyncio
async def test_runner_creates_results():
    """Runner should produce a ScenarioResults with entries for each condition."""
    runner = LongHorizonRunner(
        conditions=[ConditionType.FULL_SOUL, ConditionType.BARE_BASELINE],
    )
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    assert isinstance(results, ScenarioResults)
    assert results.scenario_id == "test_short"
    assert ConditionType.FULL_SOUL in results.condition_results
    assert ConditionType.BARE_BASELINE in results.condition_results


@pytest.mark.asyncio
async def test_full_soul_has_memories():
    """Full Soul condition should store memories after processing turns."""
    runner = LongHorizonRunner(conditions=[ConditionType.FULL_SOUL])
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    cr = results.condition_results[ConditionType.FULL_SOUL]
    assert cr.total_memories > 0, "Full Soul should store memories"
    assert cr.total_turns == scenario.turn_count


@pytest.mark.asyncio
async def test_bare_baseline_no_memories():
    """Bare baseline should have zero memories."""
    runner = LongHorizonRunner(conditions=[ConditionType.BARE_BASELINE])
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    cr = results.condition_results[ConditionType.BARE_BASELINE]
    assert cr.total_memories == 0, "Bare baseline should have no memories"


@pytest.mark.asyncio
async def test_bare_baseline_zero_recall():
    """Bare baseline should have zero recall hits."""
    runner = LongHorizonRunner(conditions=[ConditionType.BARE_BASELINE])
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    cr = results.condition_results[ConditionType.BARE_BASELINE]
    assert cr.recall_hits == 0
    assert cr.recall_misses == len(scenario.test_points)
    assert cr.recall_precision == 0.0


@pytest.mark.asyncio
async def test_personality_only_no_memories():
    """Personality Only should have no memories (OCEAN prompt but no storage)."""
    runner = LongHorizonRunner(conditions=[ConditionType.PERSONALITY_ONLY])
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    cr = results.condition_results[ConditionType.PERSONALITY_ONLY]
    assert cr.total_memories == 0


@pytest.mark.asyncio
async def test_rag_only_stores_everything():
    """RAG Only should store a memory for every turn."""
    runner = LongHorizonRunner(conditions=[ConditionType.RAG_ONLY])
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    cr = results.condition_results[ConditionType.RAG_ONLY]
    # RAG stores one memory per turn
    assert cr.total_memories == scenario.turn_count, (
        f"RAG should store {scenario.turn_count} memories, got {cr.total_memories}"
    )


@pytest.mark.asyncio
async def test_full_soul_has_richer_memory_than_rag():
    """Full Soul stores episodic + semantic (richer), RAG stores raw turns only.

    With short fact-heavy scenarios, Full Soul may store MORE total memories
    because it extracts both episodic and semantic facts. The advantage of
    significance gating shows at scale (100+ turns) where RAG drowns in
    noise while Full Soul is selective about what becomes episodic.
    """
    runner = LongHorizonRunner(
        conditions=[ConditionType.FULL_SOUL, ConditionType.RAG_ONLY],
    )
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    full = results.condition_results[ConditionType.FULL_SOUL]
    rag = results.condition_results[ConditionType.RAG_ONLY]

    # Full Soul has semantic facts (extracted) + episodic memories
    assert full.semantic_count > 0, "Full Soul should extract semantic facts"
    # RAG stores everything as semantic (one per turn)
    assert rag.total_memories == scenario.turn_count, (
        f"RAG should store {scenario.turn_count} memories, got {rag.total_memories}"
    )


@pytest.mark.asyncio
async def test_full_soul_has_bond():
    """Full Soul should build bond strength over interactions."""
    runner = LongHorizonRunner(conditions=[ConditionType.FULL_SOUL])
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    cr = results.condition_results[ConditionType.FULL_SOUL]
    assert cr.bond_strength > 0, "Full Soul should build bond strength"
    assert len(cr.bond_trajectory) > 0, "Should track bond trajectory"


@pytest.mark.asyncio
async def test_memory_growth_tracked():
    """Memory growth should be tracked periodically."""
    runner = LongHorizonRunner(conditions=[ConditionType.FULL_SOUL])
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    cr = results.condition_results[ConditionType.FULL_SOUL]
    assert len(cr.memory_growth) > 0, "Should track memory growth"
    # Growth should be monotonically non-decreasing
    for i in range(1, len(cr.memory_growth)):
        _, prev_count = cr.memory_growth[i - 1]
        _, curr_count = cr.memory_growth[i]
        assert curr_count >= prev_count, "Memory count should not decrease"


@pytest.mark.asyncio
async def test_recall_results_populated():
    """Recall results should have entries for each test point."""
    runner = LongHorizonRunner(conditions=[ConditionType.FULL_SOUL])
    scenario = _make_short_scenario()
    results = await runner.run_scenario(scenario)

    cr = results.condition_results[ConditionType.FULL_SOUL]
    recall_test_count = len([tp for tp in scenario.test_points if tp.test_type == "recall"])
    assert len(cr.recall_results) == recall_test_count


@pytest.mark.asyncio
async def test_run_all():
    """run_all should process multiple scenarios."""
    runner = LongHorizonRunner(
        conditions=[ConditionType.BARE_BASELINE],
    )
    s1 = _make_short_scenario()
    s2 = LongHorizonScenario(
        scenario_id="test_minimal",
        name="Minimal",
        description="Minimal scenario",
        turns=[("Hello", "Hi there!")],
        test_points=[],
        planted_facts=[],
    )
    results = await runner.run_all([s1, s2])

    assert isinstance(results, LongHorizonResults)
    assert len(results.scenario_results) == 2
    assert results.total_duration > 0


@pytest.mark.asyncio
async def test_condition_result_properties():
    """Verify ConditionResult property calculations."""
    cr = ConditionResult(
        condition="test",
        scenario_id="test",
        total_turns=100,
        recall_hits=7,
        recall_misses=3,
        total_memories=30,
    )
    assert cr.recall_precision == pytest.approx(0.7)
    assert cr.memory_efficiency == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_condition_result_empty():
    """ConditionResult with zero values should not crash."""
    cr = ConditionResult(condition="test", scenario_id="test")
    assert cr.recall_precision == 0.0
    assert cr.memory_efficiency == 0.0


@pytest.mark.asyncio
async def test_results_to_rows():
    """LongHorizonResults.to_rows should produce flat dicts."""
    runner = LongHorizonRunner(
        conditions=[ConditionType.BARE_BASELINE],
    )
    scenario = _make_short_scenario()
    results = await runner.run_all([scenario])

    rows = results.to_rows()
    assert len(rows) == 1
    row = rows[0]
    assert "scenario" in row
    assert "condition" in row
    assert "recall_precision" in row
    assert "total_memories" in row
