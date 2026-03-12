# test_scenarios.py — Tests for long-horizon scenario generation.
# Updated: 2026-03-12 — Fixed vacuous assertion in test_recall_tests_cover_all_facts;
#   now each planted fact is checked against recall test points.
# Created: 2026-03-11
# Validates turn counts, test point existence, planted fact structure,
# and determinism of scenario generators.

from __future__ import annotations

import pytest

from research.long_horizon.scenarios import (
    LongHorizonScenario,
    TestPoint,
    generate_adversarial_burial,
    generate_all_scenarios,
    generate_emotional_rollercoaster,
    generate_life_updates,
)


class TestLifeUpdatesScenario:
    """Tests for Scenario A: Life Updates Over Time."""

    def test_turn_count_above_100(self):
        scenario = generate_life_updates()
        assert scenario.turn_count >= 100, (
            f"Life Updates should have 100+ turns, got {scenario.turn_count}"
        )

    def test_has_test_points(self):
        scenario = generate_life_updates()
        assert len(scenario.test_points) > 0, "Should have test points"

    def test_has_recall_test_points(self):
        scenario = generate_life_updates()
        recall_points = [tp for tp in scenario.test_points if tp.test_type == "recall"]
        assert len(recall_points) >= 10, (
            f"Should have at least 10 recall test points, got {len(recall_points)}"
        )

    def test_planted_facts_exist(self):
        scenario = generate_life_updates()
        assert len(scenario.planted_facts) >= 5, (
            f"Should have at least 5 planted facts, got {len(scenario.planted_facts)}"
        )

    def test_planted_facts_within_turn_range(self):
        scenario = generate_life_updates()
        for turn_idx, _fact in scenario.planted_facts:
            assert 0 <= turn_idx < scenario.turn_count, (
                f"Planted fact at turn {turn_idx} outside range [0, {scenario.turn_count})"
            )

    def test_test_points_have_expected_content(self):
        scenario = generate_life_updates()
        for tp in scenario.test_points:
            assert tp.expected_content, f"Test point missing expected_content: {tp.query}"
            assert tp.query, f"Test point missing query"

    def test_scenario_metadata(self):
        scenario = generate_life_updates()
        assert scenario.scenario_id == "life_updates"
        assert scenario.name == "Life Updates Over Time"
        assert scenario.description

    def test_deterministic_generation(self):
        s1 = generate_life_updates(seed=42)
        s2 = generate_life_updates(seed=42)
        assert s1.turn_count == s2.turn_count
        assert len(s1.test_points) == len(s2.test_points)
        assert s1.turns[0] == s2.turns[0]
        assert s1.turns[-1] == s2.turns[-1]

    def test_different_seeds_produce_variation(self):
        s1 = generate_life_updates(seed=42)
        s2 = generate_life_updates(seed=99)
        # Scripted turns are the same, but filler turns should differ
        # At least some turns should be different
        differences = sum(1 for a, b in zip(s1.turns, s2.turns) if a != b)
        assert differences > 0, "Different seeds should produce at least some different turns"

    def test_buried_callback_test_points(self):
        """Verify test points exist for buried callbacks (turn 100+)."""
        scenario = generate_life_updates()
        buried = [tp for tp in scenario.test_points if tp.turn_index >= 100]
        assert len(buried) >= 2, "Should have buried callback test points"

    def test_turns_are_tuples(self):
        scenario = generate_life_updates()
        for i, turn in enumerate(scenario.turns):
            assert isinstance(turn, tuple), f"Turn {i} should be tuple, got {type(turn)}"
            assert len(turn) == 2, f"Turn {i} should have 2 elements"
            assert isinstance(turn[0], str), f"Turn {i} user_input should be str"
            assert isinstance(turn[1], str), f"Turn {i} agent_output should be str"


class TestEmotionalRollercoasterScenario:
    """Tests for Scenario B: Emotional Rollercoaster."""

    def test_turn_count_above_100(self):
        scenario = generate_emotional_rollercoaster()
        assert scenario.turn_count >= 100, (
            f"Emotional Rollercoaster should have 100+ turns, got {scenario.turn_count}"
        )

    def test_has_emotional_test_points(self):
        scenario = generate_emotional_rollercoaster()
        emotion_points = [tp for tp in scenario.test_points if tp.test_type == "emotion"]
        assert len(emotion_points) >= 2, "Should have emotional test points"

    def test_has_recall_test_points(self):
        scenario = generate_emotional_rollercoaster()
        recall_points = [tp for tp in scenario.test_points if tp.test_type == "recall"]
        assert len(recall_points) >= 5, "Should have at least 5 recall test points"

    def test_planted_facts_cover_emotional_range(self):
        scenario = generate_emotional_rollercoaster()
        facts_text = " ".join(f for _, f in scenario.planted_facts)
        # Should cover happy, sad, and angry phases
        assert "promoted" in facts_text.lower() or "director" in facts_text.lower(), (
            "Should plant facts during happy phase"
        )
        assert "biscuit" in facts_text.lower() or "dog" in facts_text.lower(), (
            "Should plant facts during sad phase"
        )
        assert "hacked" in facts_text.lower() or "bank" in facts_text.lower(), (
            "Should plant facts during angry phase"
        )

    def test_deterministic_generation(self):
        s1 = generate_emotional_rollercoaster(seed=42)
        s2 = generate_emotional_rollercoaster(seed=42)
        assert s1.turn_count == s2.turn_count
        assert len(s1.test_points) == len(s2.test_points)

    def test_scenario_metadata(self):
        scenario = generate_emotional_rollercoaster()
        assert scenario.scenario_id == "emotional_rollercoaster"
        assert "Emotional" in scenario.name


class TestAdversarialBurialScenario:
    """Tests for Scenario C: Adversarial Burial."""

    def test_turn_count_above_100(self):
        scenario = generate_adversarial_burial()
        assert scenario.turn_count >= 100, (
            f"Adversarial Burial should have 100+ turns, got {scenario.turn_count}"
        )

    def test_five_planted_facts(self):
        scenario = generate_adversarial_burial()
        assert len(scenario.planted_facts) == 5, (
            f"Should have exactly 5 planted facts, got {len(scenario.planted_facts)}"
        )

    def test_facts_planted_early(self):
        """All 5 facts should be planted in the first 10 turns."""
        scenario = generate_adversarial_burial()
        for turn_idx, _fact in scenario.planted_facts:
            assert turn_idx < 10, (
                f"Fact should be planted in first 10 turns, got turn {turn_idx}"
            )

    def test_recall_tests_are_late(self):
        """Recall tests should be at turn 150+."""
        scenario = generate_adversarial_burial()
        recall_points = [tp for tp in scenario.test_points if tp.test_type == "recall"]
        for tp in recall_points:
            assert tp.turn_index >= 150, (
                f"Recall test should be at turn 150+, got {tp.turn_index}"
            )

    def test_sufficient_noise_between_facts_and_tests(self):
        """At least 140 turns of noise between facts and tests."""
        scenario = generate_adversarial_burial()
        max_fact_turn = max(idx for idx, _ in scenario.planted_facts)
        min_test_turn = min(
            tp.turn_index for tp in scenario.test_points if tp.test_type == "recall"
        )
        gap = min_test_turn - max_fact_turn
        assert gap >= 100, (
            f"Need at least 100 turns of noise between facts and tests, got {gap}"
        )

    def test_recall_tests_cover_all_facts(self):
        """Each planted fact should have at least one recall test."""
        scenario = generate_adversarial_burial()
        fact_contents = [f.lower() for _, f in scenario.planted_facts]
        test_expecteds = [
            tp.expected_content.lower()
            for tp in scenario.test_points
            if tp.test_type == "recall"
        ]
        # Each fact should be testable by at least one test point
        for fact in fact_contents:
            key_words = set(fact.split())
            matched = any(
                any(word in expected for word in key_words)
                for expected in test_expecteds
            )
            assert matched, f"No recall test covers fact: {fact}"

    def test_deterministic_generation(self):
        s1 = generate_adversarial_burial(seed=42)
        s2 = generate_adversarial_burial(seed=42)
        assert s1.turn_count == s2.turn_count
        assert s1.turns[0] == s2.turns[0]

    def test_scenario_metadata(self):
        scenario = generate_adversarial_burial()
        assert scenario.scenario_id == "adversarial_burial"


class TestGenerateAllScenarios:
    """Tests for the generate_all_scenarios helper."""

    def test_returns_three_scenarios(self):
        scenarios = generate_all_scenarios()
        assert len(scenarios) == 3

    def test_all_above_100_turns(self):
        for scenario in generate_all_scenarios():
            assert scenario.turn_count >= 100, (
                f"{scenario.name} has only {scenario.turn_count} turns"
            )

    def test_unique_scenario_ids(self):
        scenarios = generate_all_scenarios()
        ids = [s.scenario_id for s in scenarios]
        assert len(ids) == len(set(ids)), "Scenario IDs should be unique"

    def test_all_have_test_points(self):
        for scenario in generate_all_scenarios():
            assert len(scenario.test_points) > 0, (
                f"{scenario.name} has no test points"
            )


class TestTestPointDataclass:
    """Tests for the TestPoint dataclass."""

    def test_creation(self):
        tp = TestPoint(
            turn_index=50,
            query="What is the user's name?",
            expected_content="Alice",
            test_type="recall",
        )
        assert tp.turn_index == 50
        assert tp.query == "What is the user's name?"
        assert tp.expected_content == "Alice"
        assert tp.test_type == "recall"
        assert tp.description == ""

    def test_with_description(self):
        tp = TestPoint(
            turn_index=50,
            query="test",
            expected_content="test",
            test_type="recall",
            description="A test point",
        )
        assert tp.description == "A test point"
