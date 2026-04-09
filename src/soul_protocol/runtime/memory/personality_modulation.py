# memory/personality_modulation.py — Personality-modulated memory retrieval scoring.
# Created: v0.3.3 — OCEAN traits influence which memories are recalled.
#   Openness boosts semantic/procedural memories (knowledge-seeking).
#   Conscientiousness boosts procedural and high-importance memories.
#   Extraversion boosts episodic memories (social interactions) and entity-rich memories.
#   Agreeableness boosts positive-valence memories (via somatic marker).
#   Neuroticism boosts high-arousal/emotional memories (via somatic marker).
#
#   Each trait contributes (trait - 0.5) * weight, so default personality (all 0.5)
#   produces zero modulation — fully backwards compatible.

from __future__ import annotations

from soul_protocol.runtime.types import MemoryEntry, MemoryType, Personality

# ---------------------------------------------------------------------------
# Per-trait weight caps — prevent any single trait from dominating.
# Max contribution per trait: ±0.5 * WEIGHT = ±WEIGHT/2
# Total max personality boost across all 5 traits ≈ ±0.75
# ---------------------------------------------------------------------------

W_OPENNESS: float = 0.3
W_CONSCIENTIOUSNESS: float = 0.3
W_EXTRAVERSION: float = 0.3
W_AGREEABLENESS: float = 0.3
W_NEUROTICISM: float = 0.3


def _trait_delta(trait_value: float) -> float:
    """Convert a 0.0-1.0 trait to a -0.5 to +0.5 delta from neutral."""
    return trait_value - 0.5


def _openness_signal(entry: MemoryEntry) -> float:
    """Openness signal: boost knowledge-rich memories (semantic, procedural).

    High-openness souls are curious and value breadth of knowledge.
    Semantic and procedural memories represent accumulated understanding.
    """
    if entry.type in (MemoryType.SEMANTIC, MemoryType.PROCEDURAL):
        return 1.0
    return 0.0


def _conscientiousness_signal(entry: MemoryEntry) -> float:
    """Conscientiousness signal: boost procedural memories and high-importance facts.

    Conscientious souls value structure, reliability, and thoroughness.
    Procedural memories (how-to) and high-importance facts are preferred.
    """
    signal = 0.0
    if entry.type == MemoryType.PROCEDURAL:
        signal += 1.0
    # High importance (7+) gets a boost; normalized to 0.0-1.0 range
    if entry.importance >= 7:
        signal += (entry.importance - 6) / 4.0  # 7→0.25, 8→0.5, 9→0.75, 10→1.0
    return min(1.0, signal)


def _extraversion_signal(entry: MemoryEntry) -> float:
    """Extraversion signal: boost episodic (social) memories and entity-rich memories.

    Extraverted souls are energised by interactions and social contexts.
    Episodic memories capture interactions; entity-rich memories reference people/things.
    """
    signal = 0.0
    if entry.type == MemoryType.EPISODIC:
        signal += 1.0
    # Entities suggest social or interactional content
    if entry.entities:
        signal += min(1.0, len(entry.entities) * 0.3)
    return min(1.0, signal)


def _agreeableness_signal(entry: MemoryEntry) -> float:
    """Agreeableness signal: boost positive-valence memories.

    Agreeable souls gravitate toward warmth and positive experiences.
    Memories with positive somatic valence are preferred.
    """
    if entry.somatic is None:
        return 0.0
    # Only boost positive valence; negative valence returns 0 (not penalised)
    return max(0.0, entry.somatic.valence)


def _neuroticism_signal(entry: MemoryEntry) -> float:
    """Neuroticism signal: boost high-arousal and emotionally intense memories.

    Neurotic souls have heightened emotional sensitivity — intense memories
    (high arousal, strong valence in either direction) are more accessible.
    """
    if entry.somatic is None:
        return 0.0
    # Both arousal and absolute valence contribute
    arousal = entry.somatic.arousal
    valence_intensity = abs(entry.somatic.valence)
    return min(1.0, arousal + valence_intensity * 0.3)


def compute_personality_boost(
    entry: MemoryEntry,
    personality: Personality | None,
) -> float:
    """Compute the personality-modulated activation boost for a memory entry.

    Each OCEAN trait modulates recall differently:
      - Openness → knowledge (semantic/procedural) memories
      - Conscientiousness → procedural + high-importance memories
      - Extraversion → episodic (social) + entity-rich memories
      - Agreeableness → positive-valence memories
      - Neuroticism → high-arousal/emotional memories

    The boost is computed as sum of (trait_delta * signal * weight) across all
    five traits. With default personality (all 0.5), every delta is 0.0 and the
    total boost is exactly 0.0 — no change to existing recall behaviour.

    Args:
        entry: The memory entry being scored.
        personality: The soul's OCEAN personality (or None for no modulation).

    Returns:
        A float boost to add to the activation score. Typically in [-0.75, +0.75].
    """
    if personality is None:
        return 0.0

    boost = 0.0
    boost += _trait_delta(personality.openness) * _openness_signal(entry) * W_OPENNESS
    boost += (
        _trait_delta(personality.conscientiousness)
        * _conscientiousness_signal(entry)
        * W_CONSCIENTIOUSNESS
    )
    boost += _trait_delta(personality.extraversion) * _extraversion_signal(entry) * W_EXTRAVERSION
    boost += (
        _trait_delta(personality.agreeableness) * _agreeableness_signal(entry) * W_AGREEABLENESS
    )
    boost += _trait_delta(personality.neuroticism) * _neuroticism_signal(entry) * W_NEUROTICISM

    return boost
