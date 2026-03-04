# state/manager.py — StateManager for tracking and mutating a soul's runtime state.
# Created: 2026-02-22 — Manages mood, energy, social_battery, focus, and
# interaction-driven state changes with delta-based updates and clamping.
# Updated: 2026-03-04 — Two fixes to sentiment-driven mood:
#   1. Mood inertia via EMA: valence is smoothed with exponential moving average
#      (alpha=0.4) before the threshold check, so a single mild message can't
#      flip mood — accumulated signal is required.
#   2. Label-based mood mapping: _somatic_to_mood() now uses the label field
#      from SomaticMarker as primary lookup (_LABEL_TO_MOOD dict), with
#      valence/arousal quadrant logic as fallback for unlabeled markers.
#      Removes duplicate quadrant math that already existed in sentiment.py.

from __future__ import annotations

from datetime import datetime

from soul_protocol.types import Interaction, Mood, SomaticMarker, SoulState


# Default recovery rate per hour of rest (energy points)
_DEFAULT_ENERGY_REGEN_RATE: float = 10.0

# Minimum EMA-smoothed valence/arousal magnitude to trigger a mood change.
_MOOD_THRESHOLD: float = 0.25

# EMA smoothing factor for valence history.
# Weight given to current message vs accumulated history.
# 0.4 means ~4 consecutive mild signals shift mood; 1 strong signal shifts immediately.
_EMA_ALPHA: float = 0.4

# Primary label → Mood lookup. Labels come from sentiment.py's _classify_label(),
# which already did the quadrant math — no need to redo it here.
_LABEL_TO_MOOD: dict[str, Mood] = {
    "excitement": Mood.EXCITED,
    "joy": Mood.SATISFIED,
    "gratitude": Mood.SATISFIED,
    "curiosity": Mood.CURIOUS,
    "frustration": Mood.CONCERNED,
    "sadness": Mood.CONTEMPLATIVE,
    "confusion": Mood.FOCUSED,
}


def _somatic_to_mood(somatic: SomaticMarker) -> Mood | None:
    """Map a somatic marker to a Mood, or None if too mild to shift.

    Uses label as primary lookup (avoids re-deriving quadrant logic that
    sentiment.py already computed). Falls back to valence/arousal for
    custom or unlabeled markers where label is 'neutral' but signal
    still exceeds threshold.

    Args:
        somatic: Marker with EMA-smoothed valence, raw arousal, and label.
    """
    v, a = somatic.valence, somatic.arousal

    # EMA-smoothed valence is the inertia gate.
    # Arousal stays for quality differentiation (excited vs satisfied, etc.)
    # but does not override the valence gate — pure high-arousal neutral
    # conversation should not shift mood on its own.
    if abs(v) < _MOOD_THRESHOLD:
        return None

    # Label-based lookup (sentiment.py already resolved the quadrant)
    if somatic.label in _LABEL_TO_MOOD:
        return _LABEL_TO_MOOD[somatic.label]

    # Fallback: valence/arousal quadrants for unlabeled or custom markers
    if v >= _MOOD_THRESHOLD:
        if a >= 0.5:
            return Mood.EXCITED
        elif a >= 0.2:
            return Mood.CURIOUS
        else:
            return Mood.SATISFIED
    elif v <= -_MOOD_THRESHOLD:
        return Mood.CONCERNED if a >= 0.5 else Mood.CONTEMPLATIVE
    else:
        return Mood.FOCUSED if a >= 0.5 else None


class StateManager:
    """Manages the mutable runtime state of a digital soul.

    Provides delta-based updates for energy and social_battery (clamped 0-100),
    interaction-driven drain, and rest-based recovery.

    Mood inertia is implemented via an exponential moving average (EMA) of
    valence. A single mild message cannot flip mood — the smoothed signal
    must exceed _MOOD_THRESHOLD. Strong signals still shift mood immediately.
    """

    def __init__(self, state: SoulState) -> None:
        self._state = state
        # EMA of valence across recent interactions (mood inertia)
        self._valence_ema: float = 0.0

    @property
    def current(self) -> SoulState:
        """Return the current soul state."""
        return self._state

    def update(self, **kwargs: object) -> None:
        """Update state fields.

        For ``energy`` and ``social_battery``, numeric values are treated as
        *deltas* (added to the current value) and the result is clamped to
        the 0-100 range.  All other fields are set directly.

        Examples::

            manager.update(mood=Mood.TIRED)
            manager.update(energy=-10)        # decrease by 10
            manager.update(focus="high")
            manager.update(energy=5, social_battery=-3)
        """
        for key, value in kwargs.items():
            if key == "energy" and isinstance(value, (int, float)):
                new_val = self._state.energy + float(value)
                self._state.energy = max(0.0, min(100.0, new_val))
            elif key == "social_battery" and isinstance(value, (int, float)):
                new_val = self._state.social_battery + float(value)
                self._state.social_battery = max(0.0, min(100.0, new_val))
            elif hasattr(self._state, key):
                setattr(self._state, key, value)

    def on_interaction(
        self,
        interaction: Interaction,
        somatic: SomaticMarker | None = None,
    ) -> None:
        """Process an interaction, draining energy and updating mood from sentiment.

        - Decreases energy by 2
        - Decreases social_battery by 5
        - Updates last_interaction to the interaction's timestamp
        - If a somatic marker is provided, maps it to a mood change
        - If energy drops below 20, mood shifts to TIRED (overrides sentiment)

        Args:
            interaction: The interaction that occurred.
            somatic: Optional somatic marker from sentiment detection.
        """
        self.update(energy=-2, social_battery=-5)
        self._state.last_interaction = interaction.timestamp

        # Map somatic marker to mood via EMA-smoothed valence
        if somatic is not None:
            # Smooth valence: current message gets _EMA_ALPHA weight, history the rest
            self._valence_ema = _EMA_ALPHA * somatic.valence + (1 - _EMA_ALPHA) * self._valence_ema
            smoothed = SomaticMarker(
                valence=round(self._valence_ema, 3),
                arousal=somatic.arousal,
                label=somatic.label,
            )
            new_mood = _somatic_to_mood(smoothed)
            if new_mood is not None:
                self._state.mood = new_mood

        # Low energy overrides everything
        if self._state.energy < 20:
            self._state.mood = Mood.TIRED

    def rest(self, hours: float = 1.0) -> None:
        """Recover energy and social battery over a rest period.

        Args:
            hours: Duration of rest. Energy recovers at
                ``_DEFAULT_ENERGY_REGEN_RATE`` per hour; social_battery
                recovers at half that rate.
        """
        energy_gain = _DEFAULT_ENERGY_REGEN_RATE * hours
        social_gain = (_DEFAULT_ENERGY_REGEN_RATE / 2.0) * hours

        self.update(energy=energy_gain, social_battery=social_gain)

    def reset(self) -> None:
        """Reset state to defaults (neutral mood, full energy/battery)."""
        self._state.mood = Mood.NEUTRAL
        self._state.energy = 100.0
        self._state.focus = "medium"
        self._state.social_battery = 100.0
        self._state.last_interaction = None
        self._valence_ema = 0.0
