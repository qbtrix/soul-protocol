# decide/personality.py — OCEAN traits shape Soul Instinct thresholds.
# Created: feat/soul-instinct — Opt-in (InstinctSettings.personality_modulation).
#   Openness lowers the significance bar (a curious soul remembers more novelty);
#   conscientiousness raises the confidence bar for model answers (a careful soul
#   double-checks more). Each trait contributes (trait - 0.5) * weight, so the
#   default personality (all 0.5) changes nothing — same convention as
#   memory/personality_modulation.py.

from __future__ import annotations

from soul_protocol.runtime.memory.attention import DEFAULT_SIGNIFICANCE_THRESHOLD
from soul_protocol.runtime.types import Personality

W_OPENNESS_SIGNIFICANCE: float = 0.2
W_CONSCIENTIOUSNESS_CONFIDENCE: float = 0.2


def modulated_thresholds(
    personality: Personality,
    min_confidence: float,
    significance_threshold: float = DEFAULT_SIGNIFICANCE_THRESHOLD,
) -> tuple[float, float]:
    """Return ``(min_confidence, significance_threshold)`` shifted by personality.

    With the default weights each value moves at most ±0.1 from its base.
    """
    confidence = min_confidence + W_CONSCIENTIOUSNESS_CONFIDENCE * (
        personality.conscientiousness - 0.5
    )
    significance = significance_threshold - W_OPENNESS_SIGNIFICANCE * (personality.openness - 0.5)
    return (min(1.0, max(0.0, confidence)), min(1.0, max(0.0, significance)))
