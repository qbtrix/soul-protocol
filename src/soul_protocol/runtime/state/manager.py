# state/manager.py — StateManager for tracking and mutating a soul's runtime state.
# Updated: Configurable biorhythms — all drain/regen/mood params read from Biorhythms
#   instead of hardcoded constants. Added time-based auto-regen on elapsed time.

from __future__ import annotations

import logging
from datetime import UTC, datetime

from soul_protocol.runtime.types import (
    Biorhythms,
    Interaction,
    Mood,
    SomaticMarker,
    SoulState,
)

logger = logging.getLogger(__name__)

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


def _somatic_to_mood(somatic: SomaticMarker, mood_sensitivity: float = 0.25) -> Mood | None:
    """Map a somatic marker to a Mood, or None if too mild to shift.

    Uses label as primary lookup (avoids re-deriving quadrant logic that
    sentiment.py already computed). Falls back to valence/arousal for
    custom or unlabeled markers where label is 'neutral' but signal
    still exceeds threshold.

    Args:
        somatic: Marker with EMA-smoothed valence, raw arousal, and label.
        mood_sensitivity: Valence threshold to trigger a mood change.
    """
    v, a = somatic.valence, somatic.arousal

    if abs(v) < mood_sensitivity:
        return None

    # Label-based lookup (sentiment.py already resolved the quadrant)
    if somatic.label in _LABEL_TO_MOOD:
        return _LABEL_TO_MOOD[somatic.label]

    # Fallback: valence/arousal quadrants for unlabeled or custom markers
    if v >= mood_sensitivity:
        if a >= 0.5:
            return Mood.EXCITED
        elif a >= 0.2:
            return Mood.CURIOUS
        else:
            return Mood.SATISFIED
    elif v <= -mood_sensitivity:
        return Mood.CONCERNED if a >= 0.5 else Mood.CONTEMPLATIVE
    else:
        return Mood.FOCUSED if a >= 0.5 else None


class StateManager:
    """Manages the mutable runtime state of a digital soul.

    Provides delta-based updates for energy and social_battery (clamped 0-100),
    interaction-driven drain, and rest-based recovery.

    All behavioral parameters (drain rates, regen, mood inertia, thresholds) are
    read from the Biorhythms config. Pass ``Biorhythms()`` for default behavior,
    or customize per-soul.

    Mood inertia is implemented via an exponential moving average (EMA) of
    valence. A single mild message cannot flip mood — the smoothed signal
    must exceed the mood_sensitivity threshold. Strong signals still shift
    mood immediately.
    """

    def __init__(self, state: SoulState, biorhythms: Biorhythms | None = None) -> None:
        self._state = state
        self._bio = biorhythms or Biorhythms()
        # EMA of valence across recent interactions (mood inertia)
        self._valence_ema: float = 0.0

    @property
    def current(self) -> SoulState:
        """Return the current soul state."""
        return self._state

    @property
    def biorhythms(self) -> Biorhythms:
        """Return the biorhythms configuration."""
        return self._bio

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

    def _apply_auto_regen(self, now: datetime) -> None:
        """Recover energy based on elapsed time since last interaction.

        Uses ``biorhythms.energy_regen_rate`` (per hour) and applies
        proportionally to elapsed seconds. Only runs if ``auto_regen``
        is enabled and there is a previous interaction timestamp.
        """
        if not self._bio.auto_regen:
            return
        if self._state.last_interaction is None:
            return
        if self._bio.energy_regen_rate <= 0:
            return

        last = self._state.last_interaction
        # Ensure both datetimes are tz-aware for comparison
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        elapsed_hours = max(0.0, (now - last).total_seconds() / 3600.0)
        if elapsed_hours <= 0:
            return

        energy_gain = self._bio.energy_regen_rate * elapsed_hours
        social_gain = (self._bio.energy_regen_rate / 2.0) * elapsed_hours
        self.update(energy=energy_gain, social_battery=social_gain)

    def on_interaction(
        self,
        interaction: Interaction,
        somatic: SomaticMarker | None = None,
    ) -> None:
        """Process an interaction, draining energy and updating mood from sentiment.

        - Applies time-based auto-regen (if enabled) before draining
        - Decreases energy by ``biorhythms.energy_drain_rate``
        - Decreases social_battery by ``biorhythms.social_drain_rate``
        - Updates last_interaction to the interaction's timestamp
        - If a somatic marker is provided, maps it to a mood change
        - If energy drops below ``biorhythms.tired_threshold``, mood shifts to TIRED

        Args:
            interaction: The interaction that occurred.
            somatic: Optional somatic marker from sentiment detection.
        """
        # Regen must run before drain and before last_interaction is updated —
        # it reads the old timestamp to compute elapsed time.
        self._apply_auto_regen(interaction.timestamp)

        # Drain energy and social battery (configurable rates, 0 = no drain)
        self.update(
            energy=-self._bio.energy_drain_rate,
            social_battery=-self._bio.social_drain_rate,
        )
        self._state.last_interaction = interaction.timestamp

        # Map somatic marker to mood via EMA-smoothed valence
        if somatic is not None:
            alpha = self._bio.mood_inertia
            self._valence_ema = alpha * somatic.valence + (1 - alpha) * self._valence_ema
            smoothed = SomaticMarker(
                valence=round(self._valence_ema, 3),
                arousal=somatic.arousal,
                label=somatic.label,
            )
            new_mood = _somatic_to_mood(smoothed, self._bio.mood_sensitivity)
            if new_mood is not None:
                old_mood = self._state.mood
                self._state.mood = new_mood
                if old_mood != new_mood:
                    logger.debug("Mood shifted: %s -> %s", old_mood.value, new_mood.value)

        # Low energy overrides everything (0 = disabled)
        if self._bio.tired_threshold > 0 and self._state.energy < self._bio.tired_threshold:
            if self._state.mood != Mood.TIRED:
                logger.debug(
                    "Low energy override: energy=%.0f, mood -> tired",
                    self._state.energy,
                )
            self._state.mood = Mood.TIRED

    def rest(self, hours: float = 1.0) -> None:
        """Recover energy and social battery over a rest period.

        Args:
            hours: Duration of rest. Energy recovers at
                ``biorhythms.energy_regen_rate`` per hour; social_battery
                recovers at half that rate.
        """
        energy_gain = self._bio.energy_regen_rate * hours
        social_gain = (self._bio.energy_regen_rate / 2.0) * hours
        self.update(energy=energy_gain, social_battery=social_gain)

    def reset(self) -> None:
        """Reset state to defaults (neutral mood, full energy/battery)."""
        self._state.mood = Mood.NEUTRAL
        self._state.energy = 100.0
        self._state.focus = "medium"
        self._state.social_battery = 100.0
        self._state.last_interaction = None
        self._valence_ema = 0.0
