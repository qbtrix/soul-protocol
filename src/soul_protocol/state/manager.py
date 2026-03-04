# state/manager.py — StateManager for tracking and mutating a soul's runtime state.
# Created: 2026-02-22 — Manages mood, energy, social_battery, focus, and
# interaction-driven state changes with delta-based updates and clamping.

from __future__ import annotations

from datetime import datetime

from soul_protocol.types import Interaction, Mood, SomaticMarker, SoulState


# Default recovery rate per hour of rest (energy points)
_DEFAULT_ENERGY_REGEN_RATE: float = 10.0

# Minimum arousal/valence magnitude to trigger a mood change.
# Below this threshold the interaction is too mild to shift mood.
_MOOD_THRESHOLD: float = 0.25


def _somatic_to_mood(somatic: SomaticMarker) -> Mood | None:
    """Map a somatic marker to a Mood, or None if too mild to shift.

    Uses valence (positive/negative) and arousal (calm/intense) quadrants:
      - High positive + high arousal → EXCITED
      - High positive + low arousal  → SATISFIED
      - Mild positive               → CURIOUS
      - High negative + high arousal → CONCERNED
      - High negative + low arousal  → CONTEMPLATIVE
      - Near-zero valence + arousal  → None (no change)
    """
    v, a = somatic.valence, somatic.arousal

    # Too mild — don't shift mood
    if abs(v) < _MOOD_THRESHOLD and a < _MOOD_THRESHOLD:
        return None

    if v >= _MOOD_THRESHOLD:
        # Positive
        if a >= 0.5:
            return Mood.EXCITED
        elif a >= 0.2:
            return Mood.CURIOUS
        else:
            return Mood.SATISFIED
    elif v <= -_MOOD_THRESHOLD:
        # Negative
        if a >= 0.5:
            return Mood.CONCERNED
        else:
            return Mood.CONTEMPLATIVE
    else:
        # Neutral valence but high arousal
        if a >= 0.5:
            return Mood.FOCUSED
        return None


class StateManager:
    """Manages the mutable runtime state of a digital soul.

    Provides delta-based updates for energy and social_battery (clamped 0-100),
    interaction-driven drain, and rest-based recovery.
    """

    def __init__(self, state: SoulState) -> None:
        self._state = state

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

        # Map somatic marker to mood
        if somatic is not None:
            new_mood = _somatic_to_mood(somatic)
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
