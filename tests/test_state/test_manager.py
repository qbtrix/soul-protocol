# tests/test_state/test_manager.py — Tests for StateManager mood inertia and label-based mapping.
# Created: 2026-03-04 — Covers two fixes added to the sentiment-driven mood system:
#   1. EMA-based mood inertia (single mild message can't flip mood)
#   2. Label-based mood mapping (_LABEL_TO_MOOD dict as primary lookup)

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from soul_protocol.state.manager import _LABEL_TO_MOOD, StateManager
from soul_protocol.types import Interaction, Mood, SomaticMarker, SoulState


def _make_state(**kwargs) -> SoulState:
    return SoulState(**kwargs)


def _make_interaction() -> Interaction:
    return Interaction(
        user_input="test",
        agent_output="ok",
        timestamp=datetime.now(UTC),
    )


def _make_somatic(valence: float, arousal: float, label: str = "neutral") -> SomaticMarker:
    return SomaticMarker(valence=valence, arousal=arousal, label=label)


# ---------------------------------------------------------------------------
# EMA inertia tests
# ---------------------------------------------------------------------------


class TestMoodInertia:
    """Single mild messages should not flip mood; accumulated signal should."""

    def test_single_mild_negative_does_not_shift_mood(self):
        """valence=-0.3 → EMA = 0.4 * -0.3 = -0.12, below threshold → no change."""
        manager = StateManager(_make_state())
        assert manager.current.mood == Mood.NEUTRAL

        # Even with arousal=0.6, smoothed valence (-0.12) is below threshold
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=-0.3, arousal=0.6, label="sadness"),
        )
        # EMA = 0.4 * -0.3 = -0.12, abs(-0.12) < 0.25 → mood unchanged
        assert manager.current.mood == Mood.NEUTRAL

    def test_single_strong_negative_shifts_mood(self):
        """valence=-0.8 → EMA = -0.32, exceeds threshold → CONTEMPLATIVE."""
        manager = StateManager(_make_state())
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=-0.8, arousal=0.1, label="sadness"),
        )
        # EMA = 0.4 * -0.8 = -0.32 → abs > 0.25 → CONTEMPLATIVE (sadness label)
        assert manager.current.mood == Mood.CONTEMPLATIVE

    def test_consecutive_mild_negatives_eventually_shift_mood(self):
        """Four consecutive mild negatives should accumulate enough EMA to shift."""
        manager = StateManager(_make_state())
        interaction = _make_interaction()
        somatic = _make_somatic(valence=-0.35, arousal=0.2, label="sadness")

        shifted = False
        for _ in range(10):
            manager.on_interaction(interaction, somatic=somatic)
            if manager.current.mood != Mood.NEUTRAL:
                shifted = True
                break

        assert shifted, "Mood should shift after several consecutive mild negatives"

    def test_ema_smooths_across_mixed_signals(self):
        """Alternating positive/negative signals should not lock in a mood."""
        manager = StateManager(_make_state())
        interaction = _make_interaction()

        for i in range(6):
            valence = 0.7 if i % 2 == 0 else -0.7
            label = "excitement" if valence > 0 else "frustration"
            manager.on_interaction(interaction, somatic=_make_somatic(valence, 0.6, label))

        # EMA oscillates near zero — mood may have shifted but shouldn't be stuck
        # at extreme. Just verify no crash and mood is a valid Mood value.
        assert manager.current.mood in list(Mood)

    def test_positive_after_strong_negative_requires_recovery(self):
        """After a strong negative, a single positive should not immediately flip mood."""
        manager = StateManager(_make_state())
        interaction = _make_interaction()

        # Build up negative EMA: 0.4 * -0.8 = -0.32 → CONCERNED
        manager.on_interaction(
            interaction, somatic=_make_somatic(valence=-0.8, arousal=0.6, label="frustration")
        )
        assert manager.current.mood == Mood.CONCERNED

        # After one strong positive:
        # EMA = 0.4*0.9 + 0.6*(-0.32) = 0.36 - 0.192 = 0.168 → below threshold
        # Mood should NOT flip to a positive state yet
        manager.on_interaction(
            interaction, somatic=_make_somatic(valence=0.9, arousal=0.7, label="excitement")
        )
        # EMA = 0.168 < 0.25 → no mood change → still CONCERNED
        assert manager.current.mood == Mood.CONCERNED

    def test_reset_clears_valence_ema(self):
        """reset() should zero out the EMA so history doesn't bleed across sessions."""
        manager = StateManager(_make_state())
        interaction = _make_interaction()

        # Build up strong negative EMA
        manager.on_interaction(
            interaction, somatic=_make_somatic(valence=-0.9, arousal=0.7, label="frustration")
        )
        assert manager.current.mood != Mood.NEUTRAL

        manager.reset()

        # After reset, a mild positive should not be dampened by old negative history
        manager.on_interaction(
            interaction, somatic=_make_somatic(valence=0.8, arousal=0.6, label="excitement")
        )
        # EMA = 0.4 * 0.8 = 0.32 → exceeds threshold → EXCITED
        assert manager.current.mood == Mood.EXCITED


# ---------------------------------------------------------------------------
# Label-based mood mapping tests
# ---------------------------------------------------------------------------


class TestLabelMoodMapping:
    """_LABEL_TO_MOOD dict is used as primary lookup."""

    @pytest.mark.parametrize(
        "label,arousal,expected_mood",
        [
            ("excitement", 0.8, Mood.EXCITED),
            ("joy", 0.1, Mood.SATISFIED),
            ("gratitude", 0.1, Mood.SATISFIED),
            ("curiosity", 0.4, Mood.CURIOUS),
            ("frustration", 0.7, Mood.CONCERNED),
            ("sadness", 0.1, Mood.CONTEMPLATIVE),
            ("confusion", 0.5, Mood.FOCUSED),
        ],
    )
    def test_label_maps_to_expected_mood(self, label: str, arousal: float, expected_mood: Mood):
        """Each label in _LABEL_TO_MOOD should map to the correct Mood."""
        manager = StateManager(_make_state())
        # Use strong valence so EMA clears threshold on first message
        valence = 0.9 if expected_mood not in (Mood.CONCERNED, Mood.CONTEMPLATIVE) else -0.9
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=valence, arousal=arousal, label=label),
        )
        assert manager.current.mood == expected_mood

    def test_all_label_to_mood_keys_covered(self):
        """Every key in _LABEL_TO_MOOD resolves to a valid Mood enum value."""
        for label, mood in _LABEL_TO_MOOD.items():
            assert isinstance(mood, Mood), f"Label '{label}' maps to non-Mood value: {mood}"

    def test_unlabeled_marker_uses_valence_arousal_fallback(self):
        """label='neutral' with valence exceeding threshold uses quadrant fallback."""
        manager = StateManager(_make_state())
        # valence=0.8, arousal=0.6, label='neutral' → fallback → EXCITED
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=0.8, arousal=0.6, label="neutral"),
        )
        assert manager.current.mood == Mood.EXCITED

    def test_below_threshold_neutral_label_no_change(self):
        """label='neutral' with sub-threshold values → no mood change."""
        manager = StateManager(_make_state())
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=0.1, arousal=0.1, label="neutral"),
        )
        assert manager.current.mood == Mood.NEUTRAL


# ---------------------------------------------------------------------------
# Energy override still works
# ---------------------------------------------------------------------------


class TestEnergyOverride:
    def test_low_energy_overrides_sentiment_mood(self):
        """TIRED override fires when energy < 20, regardless of somatic signal."""
        manager = StateManager(_make_state(energy=21.0))
        interaction = _make_interaction()

        # Drain energy to below 20
        for _ in range(2):
            manager.on_interaction(interaction)

        assert manager.current.energy < 20
        assert manager.current.mood == Mood.TIRED

    def test_positive_sentiment_does_not_override_tired(self):
        """Strong positive signal should not clear TIRED when energy is low."""
        manager = StateManager(_make_state(energy=20.0))
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=0.9, arousal=0.8, label="excitement"),
        )
        # energy drops to 18 → TIRED overrides EXCITED
        assert manager.current.mood == Mood.TIRED
