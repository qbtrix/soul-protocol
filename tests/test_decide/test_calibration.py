# test_decide/test_calibration.py — Tests for InstinctCalibration, personality
#   modulation, and calibration-aware DeciderChain gating.
# Created: feat/soul-instinct

from __future__ import annotations

import pytest

from soul_protocol.runtime.decide import DeciderChain, DecisionKind, modulated_thresholds
from soul_protocol.runtime.memory.attention import DEFAULT_SIGNIFICANCE_THRESHOLD
from soul_protocol.runtime.types import (
    CALIBRATION_BINS,
    CALIBRATION_PRIOR_STRENGTH,
    InstinctCalibration,
    InstinctState,
    MemoryEntry,
    MemoryType,
    Personality,
)
from tests.test_decide.conftest import KeywordContradictionDecider


class TestInstinctCalibration:
    def test_unreviewed_decider_keeps_raw_confidence(self):
        cal = InstinctCalibration()
        assert cal.calibrate("nli", "contradiction", 0.42) == 0.42
        assert cal.accuracy("nli", "contradiction") is None

    def test_wrong_answers_lower_confidence(self):
        cal = InstinctCalibration()
        for _ in range(20):
            cal.record("nli", "contradiction", 0.9, correct=False)
        assert cal.calibrate("nli", "contradiction", 0.9) < 0.3
        assert cal.accuracy("nli", "contradiction") == 0.0

    def test_right_answers_raise_low_confidence(self):
        cal = InstinctCalibration()
        for _ in range(20):
            cal.record("nli", "contradiction", 0.55, correct=True)
        assert cal.calibrate("nli", "contradiction", 0.55) > 0.85

    def test_prior_smooths_single_review(self):
        cal = InstinctCalibration()
        cal.record("nli", "contradiction", 0.8, correct=False)
        expected = (0 + CALIBRATION_PRIOR_STRENGTH * 0.8) / (1 + CALIBRATION_PRIOR_STRENGTH)
        assert cal.calibrate("nli", "contradiction", 0.8) == pytest.approx(expected)

    def test_bins_are_independent(self):
        cal = InstinctCalibration()
        for _ in range(10):
            cal.record("nli", "contradiction", 0.95, correct=False)
        assert cal.calibrate("nli", "contradiction", 0.35) == 0.35

    def test_sources_and_kinds_are_independent(self):
        cal = InstinctCalibration()
        for _ in range(10):
            cal.record("nli", "contradiction", 0.9, correct=False)
        assert cal.calibrate("jev", "contradiction", 0.9) == 0.9
        assert cal.calibrate("nli", "significance", 0.9) == 0.9

    @pytest.mark.parametrize("confidence", [0.0, 0.5, 0.999, 1.0])
    def test_every_confidence_maps_to_a_bin(self, confidence):
        cal = InstinctCalibration()
        cal.record("x", "dedup", confidence, correct=True)
        assert len(cal.sources["x:dedup"]) == CALIBRATION_BINS
        assert sum(b.total for b in cal.sources["x:dedup"]) == 1

    def test_round_trips_through_json(self):
        state = InstinctState()
        state.calibration.record("nli", "contradiction", 0.7, correct=True)
        state.settings.min_confidence = 0.8
        restored = InstinctState.model_validate_json(state.model_dump_json())
        assert restored == state


class TestChainCalibration:
    @pytest.fixture
    def memories(self):
        return [MemoryEntry(id="m1", type=MemoryType.SEMANTIC, content="User loves steak")]

    async def test_learned_distrust_rejects_confident_answer(self, memories):
        cal = InstinctCalibration()
        for _ in range(30):
            cal.record("keyword", DecisionKind.CONTRADICTION, 0.95, correct=False)
        chain = DeciderChain([KeywordContradictionDecider(confidence=0.95)], calibration=cal)

        decision = await chain.contradictions("User is vegetarian now", memories)

        assert decision.source == "heuristic"
        attempt = decision.attempts[0]
        assert attempt.outcome == "unsure"
        assert attempt.confidence == 0.95
        assert attempt.effective_confidence < 0.7

    async def test_learned_trust_accepts_low_confidence_answer(self, memories):
        cal = InstinctCalibration()
        for _ in range(30):
            cal.record("keyword", DecisionKind.CONTRADICTION, 0.55, correct=True)
        chain = DeciderChain([KeywordContradictionDecider(confidence=0.55)], calibration=cal)

        decision = await chain.contradictions("User is vegetarian now", memories)

        assert decision.source == "keyword"
        assert decision.attempts[0].outcome == "accepted"


class TestPersonalityModulation:
    def test_default_personality_changes_nothing(self):
        assert modulated_thresholds(Personality(), 0.7) == (
            0.7,
            DEFAULT_SIGNIFICANCE_THRESHOLD,
        )

    def test_conscientious_soul_demands_more_confidence(self):
        careful, _ = modulated_thresholds(Personality(conscientiousness=1.0), 0.7)
        relaxed, _ = modulated_thresholds(Personality(conscientiousness=0.0), 0.7)
        assert careful == pytest.approx(0.8)
        assert relaxed == pytest.approx(0.6)

    def test_open_soul_remembers_more(self):
        _, curious = modulated_thresholds(Personality(openness=1.0), 0.7)
        _, closed = modulated_thresholds(Personality(openness=0.0), 0.7)
        assert curious == pytest.approx(DEFAULT_SIGNIFICANCE_THRESHOLD - 0.1)
        assert closed == pytest.approx(DEFAULT_SIGNIFICANCE_THRESHOLD + 0.1)

    def test_results_are_clamped(self):
        conf, sig = modulated_thresholds(
            Personality(conscientiousness=1.0, openness=1.0), 0.99, significance_threshold=0.01
        )
        assert conf == 1.0
        assert sig == 0.0
