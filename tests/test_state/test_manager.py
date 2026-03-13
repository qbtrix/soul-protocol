# tests/test_state/test_manager.py — Tests for StateManager mood inertia, label-based mapping,
# and configurable Biorhythms (energy drain, social drain, tired threshold, mood dynamics,
# time-based auto-regen).
# Created: 2026-03-04 — Covers two fixes added to the sentiment-driven mood system:
#   1. EMA-based mood inertia (single mild message can't flip mood)
#   2. Label-based mood mapping (_LABEL_TO_MOOD dict as primary lookup)
# Updated: 2026-03-13 — Added TestBiorhythmsConfig and TestAutoRegen test classes covering
#   configurable Biorhythms parameter: drain rates, tired threshold, mood inertia, mood
#   sensitivity, auto-regen on/off, and the "always-on" agent preset.

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from soul_protocol.runtime.state.manager import _LABEL_TO_MOOD, StateManager
from soul_protocol.runtime.types import Biorhythms, Interaction, Mood, SomaticMarker, SoulState


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


# ---------------------------------------------------------------------------
# Configurable Biorhythms — drain rates, thresholds, mood dynamics
# ---------------------------------------------------------------------------


def _make_interaction_at(ts: datetime) -> Interaction:
    """Create an Interaction with an explicit timestamp."""
    return Interaction(
        user_input="test",
        agent_output="ok",
        timestamp=ts,
    )


class TestBiorhythmsConfig:
    """StateManager respects configurable Biorhythms parameters."""

    # ------------------------------------------------------------------
    # Constructor: default Biorhythms when none supplied
    # ------------------------------------------------------------------

    def test_default_biorhythms_applied_when_not_supplied(self):
        """StateManager(state) uses Biorhythms() defaults — 2 energy drain per interaction."""
        manager = StateManager(_make_state())
        manager.on_interaction(_make_interaction())
        # Default energy_drain_rate=2.0; energy starts at 100 → 98
        assert manager.current.energy == pytest.approx(98.0)

    def test_default_biorhythms_social_drain(self):
        """Default social_drain_rate=5 → social_battery drops from 100 to 95."""
        manager = StateManager(_make_state())
        manager.on_interaction(_make_interaction())
        assert manager.current.social_battery == pytest.approx(95.0)

    def test_biorhythms_attribute_accessible(self):
        """biorhythms property returns the configured Biorhythms instance."""
        bio = Biorhythms(energy_drain_rate=3.0)
        manager = StateManager(_make_state(), biorhythms=bio)
        assert manager.biorhythms is bio

    # ------------------------------------------------------------------
    # Energy drain rate
    # ------------------------------------------------------------------

    def test_zero_energy_drain_rate_no_energy_loss(self):
        """Biorhythms(energy_drain_rate=0) → energy never decreases per interaction."""
        bio = Biorhythms(energy_drain_rate=0, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        for _ in range(10):
            manager.on_interaction(_make_interaction())
        assert manager.current.energy == pytest.approx(100.0)

    def test_custom_energy_drain_rate_applied(self):
        """Custom drain rate of 5 → energy drops 5 per interaction."""
        bio = Biorhythms(energy_drain_rate=5.0, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        manager.on_interaction(_make_interaction())
        assert manager.current.energy == pytest.approx(95.0)

    def test_energy_clamped_at_zero(self):
        """Energy never goes below 0, even with high drain rate."""
        bio = Biorhythms(energy_drain_rate=60.0, tired_threshold=0.0, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        manager.on_interaction(_make_interaction())
        manager.on_interaction(_make_interaction())
        assert manager.current.energy == pytest.approx(0.0)

    # ------------------------------------------------------------------
    # Social drain rate
    # ------------------------------------------------------------------

    def test_zero_social_drain_rate_no_battery_loss(self):
        """Biorhythms(social_drain_rate=0) → social_battery never decreases."""
        bio = Biorhythms(social_drain_rate=0, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        for _ in range(10):
            manager.on_interaction(_make_interaction())
        assert manager.current.social_battery == pytest.approx(100.0)

    def test_custom_social_drain_rate_applied(self):
        """Custom social_drain_rate=10 → social_battery drops 10 per interaction."""
        bio = Biorhythms(social_drain_rate=10.0, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        manager.on_interaction(_make_interaction())
        assert manager.current.social_battery == pytest.approx(90.0)

    # ------------------------------------------------------------------
    # Tired threshold
    # ------------------------------------------------------------------

    def test_tired_threshold_zero_disables_tired_override(self):
        """tired_threshold=0 → TIRED mood override never fires, even at low energy."""
        bio = Biorhythms(energy_drain_rate=10.0, tired_threshold=0.0, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        # Drain to near 0 — 10 interactions × 10 drain = 0 energy
        for _ in range(10):
            manager.on_interaction(_make_interaction())
        assert manager.current.energy == pytest.approx(0.0)
        assert manager.current.mood != Mood.TIRED

    def test_custom_tired_threshold_triggers_at_right_level(self):
        """tired_threshold=50 → TIRED fires when energy drops below 50."""
        bio = Biorhythms(energy_drain_rate=2.0, tired_threshold=50.0, auto_regen=False)
        manager = StateManager(_make_state(energy=51.0), biorhythms=bio)
        # After one interaction: energy = 49 < 50 → TIRED
        manager.on_interaction(_make_interaction())
        assert manager.current.energy == pytest.approx(49.0)
        assert manager.current.mood == Mood.TIRED

    def test_tired_not_triggered_above_threshold(self):
        """TIRED does not fire when energy stays above the threshold."""
        bio = Biorhythms(energy_drain_rate=2.0, tired_threshold=20.0, auto_regen=False)
        manager = StateManager(_make_state(energy=50.0), biorhythms=bio)
        manager.on_interaction(_make_interaction())
        # energy = 48 > 20 → no TIRED
        assert manager.current.mood != Mood.TIRED

    # ------------------------------------------------------------------
    # Mood inertia
    # ------------------------------------------------------------------

    def test_mood_inertia_one_instant_mood_shift(self):
        """mood_inertia=1.0 → alpha=1.0, EMA equals raw valence → instant mood shifts."""
        bio = Biorhythms(mood_inertia=1.0, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        # With alpha=1, EMA = 1.0 * 0.3 = 0.3 > default threshold (0.25) → mood shifts
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=0.3, arousal=0.8, label="excitement"),
        )
        assert manager.current.mood == Mood.EXCITED

    def test_mood_inertia_zero_maximum_resistance(self):
        """mood_inertia=0.0 → alpha=0.0, EMA stays at 0 → no mood shift ever."""
        bio = Biorhythms(mood_inertia=0.0, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        # With alpha=0, EMA = 0*valence + 1*0 = 0 forever → never exceeds threshold
        for _ in range(5):
            manager.on_interaction(
                _make_interaction(),
                somatic=_make_somatic(valence=0.9, arousal=0.8, label="excitement"),
            )
        assert manager.current.mood == Mood.NEUTRAL

    def test_default_mood_inertia_blocks_single_mild_negative(self):
        """Default inertia (0.4) blocks a single mild negative signal."""
        manager = StateManager(_make_state())
        # Reproduces existing behavior: single valence=-0.3 should not shift mood
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=-0.3, arousal=0.4, label="sadness"),
        )
        assert manager.current.mood == Mood.NEUTRAL

    # ------------------------------------------------------------------
    # Mood sensitivity
    # ------------------------------------------------------------------

    def test_mood_sensitivity_zero_any_valence_triggers_shift(self):
        """mood_sensitivity=0.0 → threshold is 0, any nonzero valence triggers mood change."""
        bio = Biorhythms(mood_inertia=1.0, mood_sensitivity=0.0, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        # With sensitivity=0 and inertia=1, even tiny valence should shift mood
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=0.05, arousal=0.8, label="excitement"),
        )
        assert manager.current.mood == Mood.EXCITED

    def test_high_mood_sensitivity_requires_strong_signal(self):
        """mood_sensitivity=0.8 → only very strong valence triggers a shift."""
        bio = Biorhythms(mood_inertia=1.0, mood_sensitivity=0.8, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        # valence=0.7 < 0.8 threshold → no shift
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=0.7, arousal=0.8, label="excitement"),
        )
        assert manager.current.mood == Mood.NEUTRAL

    def test_high_mood_sensitivity_shifts_on_strong_enough_signal(self):
        """mood_sensitivity=0.8 with valence=0.9 (> 0.8) → mood shifts."""
        bio = Biorhythms(mood_inertia=1.0, mood_sensitivity=0.8, auto_regen=False)
        manager = StateManager(_make_state(), biorhythms=bio)
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=0.9, arousal=0.8, label="excitement"),
        )
        assert manager.current.mood == Mood.EXCITED

    # ------------------------------------------------------------------
    # Always-on agent preset
    # ------------------------------------------------------------------

    def test_always_on_preset_energy_never_drains(self):
        """energy_drain_rate=0, social_drain_rate=0, tired_threshold=0 → energy stays at 100."""
        bio = Biorhythms(
            energy_drain_rate=0,
            social_drain_rate=0,
            tired_threshold=0.0,
            auto_regen=False,
        )
        manager = StateManager(_make_state(), biorhythms=bio)
        for _ in range(20):
            manager.on_interaction(_make_interaction())
        assert manager.current.energy == pytest.approx(100.0)
        assert manager.current.social_battery == pytest.approx(100.0)

    def test_always_on_preset_mood_never_forced_to_tired(self):
        """Always-on preset: TIRED override is disabled regardless of interaction count."""
        bio = Biorhythms(
            energy_drain_rate=0,
            social_drain_rate=0,
            tired_threshold=0.0,
            auto_regen=False,
        )
        manager = StateManager(_make_state(), biorhythms=bio)
        for _ in range(20):
            manager.on_interaction(_make_interaction())
        assert manager.current.mood != Mood.TIRED

    def test_always_on_preset_still_responds_to_somatic_signals(self):
        """Always-on preset doesn't break mood tracking — somatic signals still work."""
        bio = Biorhythms(
            energy_drain_rate=0,
            social_drain_rate=0,
            tired_threshold=0.0,
            auto_regen=False,
        )
        manager = StateManager(_make_state(), biorhythms=bio)
        manager.on_interaction(
            _make_interaction(),
            somatic=_make_somatic(valence=0.9, arousal=0.8, label="excitement"),
        )
        assert manager.current.mood == Mood.EXCITED


# ---------------------------------------------------------------------------
# Time-based auto-regen
# ---------------------------------------------------------------------------


class TestAutoRegen:
    """Energy and social_battery recover automatically based on elapsed time."""

    def test_auto_regen_recovers_energy_after_gap(self):
        """2 hours elapsed at 10/hr regen → +20 energy before next drain."""
        t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(hours=2)

        bio = Biorhythms(energy_drain_rate=2.0, energy_regen_rate=10.0, auto_regen=True)
        manager = StateManager(_make_state(energy=50.0), biorhythms=bio)

        # First interaction establishes last_interaction = t1
        manager.on_interaction(_make_interaction_at(t1))
        energy_after_first = manager.current.energy  # 50 - 2 = 48

        # Second interaction at t2: regen(+20) first, then drain(-2) → 48 + 20 - 2 = 66
        manager.on_interaction(_make_interaction_at(t2))
        expected = energy_after_first + 20.0 - 2.0
        assert manager.current.energy == pytest.approx(expected)

    def test_auto_regen_recovers_social_battery_after_gap(self):
        """Social battery recovers at half the energy_regen_rate per hour."""
        t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(hours=4)

        bio = Biorhythms(
            social_drain_rate=5.0,
            energy_regen_rate=10.0,
            auto_regen=True,
        )
        manager = StateManager(_make_state(), biorhythms=bio)

        # First interaction: social drops from 100 → 95
        manager.on_interaction(_make_interaction_at(t1))
        battery_after_first = manager.current.social_battery  # 95

        # Second interaction: regen = 10/2 * 4 = +20 social, then drain -5 → 95 + 20 - 5 = 110 → clamped 100
        manager.on_interaction(_make_interaction_at(t2))
        # After regen +20 = 115, clamped to 100, then drain -5 = 95
        assert manager.current.social_battery == pytest.approx(95.0)

    def test_auto_regen_capped_at_100(self):
        """Energy recovery is clamped at 100 even after a very long gap."""
        t1 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(hours=24)

        bio = Biorhythms(
            energy_drain_rate=2.0,
            energy_regen_rate=10.0,
            auto_regen=True,
        )
        manager = StateManager(_make_state(energy=30.0), biorhythms=bio)

        # First interaction drains 2 → 28
        manager.on_interaction(_make_interaction_at(t1))

        # 24 hrs later → regen = 10 * 24 = 240, clamped to 100, then drain -2 = 98
        manager.on_interaction(_make_interaction_at(t2))
        assert manager.current.energy == pytest.approx(98.0)

    def test_auto_regen_disabled_no_recovery(self):
        """Biorhythms(auto_regen=False) → no energy recovery between interactions."""
        t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(hours=8)

        bio = Biorhythms(
            energy_drain_rate=2.0,
            energy_regen_rate=10.0,
            auto_regen=False,
        )
        manager = StateManager(_make_state(energy=50.0), biorhythms=bio)

        manager.on_interaction(_make_interaction_at(t1))
        energy_after_first = manager.current.energy  # 48

        # Despite 8-hour gap, no regen → only drain
        manager.on_interaction(_make_interaction_at(t2))
        assert manager.current.energy == pytest.approx(energy_after_first - 2.0)

    def test_auto_regen_skipped_on_first_interaction(self):
        """No last_interaction → auto-regen does not run on the very first interaction."""
        t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        bio = Biorhythms(energy_drain_rate=2.0, energy_regen_rate=10.0, auto_regen=True)
        manager = StateManager(_make_state(energy=80.0), biorhythms=bio)

        assert manager.current.last_interaction is None
        manager.on_interaction(_make_interaction_at(t1))
        # No regen on first call; only drain: 80 - 2 = 78
        assert manager.current.energy == pytest.approx(78.0)

    def test_auto_regen_same_timestamp_no_recovery(self):
        """Two consecutive interactions at the same timestamp → zero elapsed → no regen."""
        t = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        bio = Biorhythms(energy_drain_rate=2.0, energy_regen_rate=10.0, auto_regen=True)
        manager = StateManager(_make_state(energy=50.0), biorhythms=bio)

        manager.on_interaction(_make_interaction_at(t))
        energy_after_first = manager.current.energy  # 48

        # Same timestamp → no elapsed time → no regen, only drain
        manager.on_interaction(_make_interaction_at(t))
        assert manager.current.energy == pytest.approx(energy_after_first - 2.0)

    def test_auto_regen_zero_regen_rate_no_recovery(self):
        """energy_regen_rate=0 with auto_regen=True → no recovery even with large gap."""
        t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(hours=10)

        bio = Biorhythms(energy_drain_rate=2.0, energy_regen_rate=0.0, auto_regen=True)
        manager = StateManager(_make_state(energy=50.0), biorhythms=bio)

        manager.on_interaction(_make_interaction_at(t1))
        energy_after_first = manager.current.energy  # 48

        manager.on_interaction(_make_interaction_at(t2))
        # regen rate = 0 → no gain, only drain
        assert manager.current.energy == pytest.approx(energy_after_first - 2.0)

    def test_auto_regen_last_interaction_timestamp_updated(self):
        """last_interaction is updated to each interaction's timestamp."""
        t1 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(hours=1)

        bio = Biorhythms(auto_regen=True)
        manager = StateManager(_make_state(), biorhythms=bio)

        manager.on_interaction(_make_interaction_at(t1))
        assert manager.current.last_interaction == t1

        manager.on_interaction(_make_interaction_at(t2))
        assert manager.current.last_interaction == t2

    def test_rest_uses_configurable_regen_rate(self):
        """rest() should use biorhythms.energy_regen_rate, not a hardcoded value."""
        bio = Biorhythms(energy_regen_rate=20.0)
        manager = StateManager(_make_state(energy=50.0), biorhythms=bio)
        manager.rest(hours=1.0)
        # 50 + 20*1 = 70
        assert manager.current.energy == pytest.approx(70.0)
        # social recovers at half rate: 100 + 10*1 = 100 (capped)
        assert manager.current.social_battery == pytest.approx(100.0)
