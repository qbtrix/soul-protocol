# test_personality_modulation.py — Tests for OCEAN personality-modulated memory retrieval.
# Created: v0.3.3 — Comprehensive tests for compute_personality_boost() and
#   its integration with compute_activation() and RecallEngine.
#   Covers each OCEAN trait individually, neutral personality (no effect),
#   combined traits, backwards compatibility, and end-to-end recall ranking.

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from soul_protocol.runtime.memory.activation import compute_activation
from soul_protocol.runtime.memory.personality_modulation import (
    W_AGREEABLENESS,
    W_CONSCIENTIOUSNESS,
    W_EXTRAVERSION,
    W_NEUROTICISM,
    W_OPENNESS,
    _agreeableness_signal,
    _conscientiousness_signal,
    _extraversion_signal,
    _neuroticism_signal,
    _openness_signal,
    _trait_delta,
    compute_personality_boost,
)
from soul_protocol.runtime.memory.episodic import EpisodicStore
from soul_protocol.runtime.memory.procedural import ProceduralStore
from soul_protocol.runtime.memory.recall import RecallEngine
from soul_protocol.runtime.memory.semantic import SemanticStore
from soul_protocol.runtime.types import (
    MemoryEntry,
    MemoryType,
    Personality,
    SomaticMarker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 10, 12, 0, 0)


def _entry(
    content: str = "test memory",
    type: MemoryType = MemoryType.EPISODIC,
    importance: int = 5,
    somatic: SomaticMarker | None = None,
    entities: list[str] | None = None,
    access_timestamps: list[datetime] | None = None,
) -> MemoryEntry:
    """Build a minimal MemoryEntry for testing."""
    return MemoryEntry(
        type=type,
        content=content,
        importance=importance,
        somatic=somatic,
        entities=entities or [],
        access_timestamps=access_timestamps or [],
    )


def _neutral_personality() -> Personality:
    """Default/neutral personality — all traits at 0.5."""
    return Personality()


def _high_trait(trait: str) -> Personality:
    """Personality with one trait at 0.9, rest at 0.5."""
    kwargs = {trait: 0.9}
    return Personality(**kwargs)


def _low_trait(trait: str) -> Personality:
    """Personality with one trait at 0.1, rest at 0.5."""
    kwargs = {trait: 0.1}
    return Personality(**kwargs)


# ---------------------------------------------------------------------------
# _trait_delta
# ---------------------------------------------------------------------------


def test_trait_delta_neutral_is_zero():
    assert _trait_delta(0.5) == 0.0


def test_trait_delta_high_is_positive():
    assert _trait_delta(0.9) == pytest.approx(0.4)


def test_trait_delta_low_is_negative():
    assert _trait_delta(0.1) == pytest.approx(-0.4)


def test_trait_delta_extremes():
    assert _trait_delta(1.0) == pytest.approx(0.5)
    assert _trait_delta(0.0) == pytest.approx(-0.5)


# ---------------------------------------------------------------------------
# Openness signal
# ---------------------------------------------------------------------------


def test_openness_signal_semantic_memory():
    entry = _entry(type=MemoryType.SEMANTIC)
    assert _openness_signal(entry) == 1.0


def test_openness_signal_procedural_memory():
    entry = _entry(type=MemoryType.PROCEDURAL)
    assert _openness_signal(entry) == 1.0


def test_openness_signal_episodic_memory():
    entry = _entry(type=MemoryType.EPISODIC)
    assert _openness_signal(entry) == 0.0


# ---------------------------------------------------------------------------
# Conscientiousness signal
# ---------------------------------------------------------------------------


def test_conscientiousness_signal_procedural():
    entry = _entry(type=MemoryType.PROCEDURAL, importance=5)
    assert _conscientiousness_signal(entry) == 1.0


def test_conscientiousness_signal_high_importance():
    entry = _entry(type=MemoryType.EPISODIC, importance=10)
    assert _conscientiousness_signal(entry) == 1.0


def test_conscientiousness_signal_low_importance_non_procedural():
    entry = _entry(type=MemoryType.EPISODIC, importance=5)
    assert _conscientiousness_signal(entry) == 0.0


def test_conscientiousness_signal_importance_7():
    entry = _entry(type=MemoryType.EPISODIC, importance=7)
    assert _conscientiousness_signal(entry) == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Extraversion signal
# ---------------------------------------------------------------------------


def test_extraversion_signal_episodic():
    entry = _entry(type=MemoryType.EPISODIC)
    assert _extraversion_signal(entry) == 1.0


def test_extraversion_signal_with_entities():
    entry = _entry(type=MemoryType.SEMANTIC, entities=["Alice", "Bob"])
    assert _extraversion_signal(entry) == pytest.approx(0.6)


def test_extraversion_signal_semantic_no_entities():
    entry = _entry(type=MemoryType.SEMANTIC, entities=[])
    assert _extraversion_signal(entry) == 0.0


def test_extraversion_signal_episodic_with_entities_capped():
    entry = _entry(type=MemoryType.EPISODIC, entities=["A", "B", "C", "D", "E"])
    # 1.0 (episodic) + min(1.0, 5*0.3=1.5) = min(1.0, 2.0) → capped at 1.0
    assert _extraversion_signal(entry) == 1.0


# ---------------------------------------------------------------------------
# Agreeableness signal
# ---------------------------------------------------------------------------


def test_agreeableness_signal_positive_valence():
    entry = _entry(somatic=SomaticMarker(valence=0.8, arousal=0.3, label="joy"))
    assert _agreeableness_signal(entry) == pytest.approx(0.8)


def test_agreeableness_signal_negative_valence():
    entry = _entry(somatic=SomaticMarker(valence=-0.5, arousal=0.3, label="sad"))
    assert _agreeableness_signal(entry) == 0.0


def test_agreeableness_signal_no_somatic():
    entry = _entry()
    assert _agreeableness_signal(entry) == 0.0


# ---------------------------------------------------------------------------
# Neuroticism signal
# ---------------------------------------------------------------------------


def test_neuroticism_signal_high_arousal():
    entry = _entry(somatic=SomaticMarker(arousal=0.9, valence=0.0, label="anxious"))
    assert _neuroticism_signal(entry) == pytest.approx(0.9)


def test_neuroticism_signal_strong_negative_valence():
    entry = _entry(somatic=SomaticMarker(arousal=0.3, valence=-0.8, label="fear"))
    # 0.3 + 0.8*0.3 = 0.54
    assert _neuroticism_signal(entry) == pytest.approx(0.54)


def test_neuroticism_signal_no_somatic():
    entry = _entry()
    assert _neuroticism_signal(entry) == 0.0


def test_neuroticism_signal_capped_at_one():
    entry = _entry(somatic=SomaticMarker(arousal=1.0, valence=1.0, label="panic"))
    assert _neuroticism_signal(entry) <= 1.0


# ---------------------------------------------------------------------------
# compute_personality_boost — integration
# ---------------------------------------------------------------------------


def test_boost_none_personality_returns_zero():
    entry = _entry(type=MemoryType.SEMANTIC, importance=10)
    assert compute_personality_boost(entry, None) == 0.0


def test_boost_neutral_personality_returns_zero():
    """All traits at 0.5 → zero boost for any memory."""
    entry = _entry(
        type=MemoryType.SEMANTIC,
        importance=10,
        somatic=SomaticMarker(arousal=0.9, valence=0.8, label="joy"),
        entities=["Alice"],
    )
    assert compute_personality_boost(entry, _neutral_personality()) == 0.0


def test_boost_high_openness_boosts_semantic():
    semantic = _entry(type=MemoryType.SEMANTIC)
    episodic = _entry(type=MemoryType.EPISODIC)
    personality = _high_trait("openness")

    boost_semantic = compute_personality_boost(semantic, personality)
    boost_episodic = compute_personality_boost(episodic, personality)

    assert boost_semantic > boost_episodic
    assert boost_semantic > 0.0


def test_boost_low_openness_penalises_semantic():
    semantic = _entry(type=MemoryType.SEMANTIC)
    personality = _low_trait("openness")

    boost = compute_personality_boost(semantic, personality)
    assert boost < 0.0


def test_boost_high_conscientiousness_boosts_procedural():
    procedural = _entry(type=MemoryType.PROCEDURAL)
    episodic = _entry(type=MemoryType.EPISODIC, importance=5)
    personality = _high_trait("conscientiousness")

    boost_proc = compute_personality_boost(procedural, personality)
    boost_epi = compute_personality_boost(episodic, personality)

    assert boost_proc > boost_epi


def test_boost_high_extraversion_boosts_episodic():
    episodic = _entry(type=MemoryType.EPISODIC)
    semantic = _entry(type=MemoryType.SEMANTIC)
    personality = _high_trait("extraversion")

    boost_epi = compute_personality_boost(episodic, personality)
    boost_sem = compute_personality_boost(semantic, personality)

    assert boost_epi > boost_sem
    assert boost_epi > 0.0


def test_boost_high_agreeableness_boosts_positive_memories():
    positive = _entry(somatic=SomaticMarker(valence=0.9, arousal=0.3, label="happy"))
    negative = _entry(somatic=SomaticMarker(valence=-0.5, arousal=0.3, label="sad"))
    personality = _high_trait("agreeableness")

    boost_pos = compute_personality_boost(positive, personality)
    boost_neg = compute_personality_boost(negative, personality)

    assert boost_pos > boost_neg


def test_boost_high_neuroticism_boosts_emotional_memories():
    emotional = _entry(somatic=SomaticMarker(arousal=0.9, valence=-0.5, label="fear"))
    neutral = _entry()
    personality = _high_trait("neuroticism")

    boost_emo = compute_personality_boost(emotional, personality)
    boost_neu = compute_personality_boost(neutral, personality)

    assert boost_emo > boost_neu
    assert boost_emo > 0.0


def test_boost_combined_traits():
    """Multiple high traits stack their boosts."""
    entry = _entry(
        type=MemoryType.SEMANTIC,
        importance=9,
        somatic=SomaticMarker(arousal=0.8, valence=0.7, label="excited"),
        entities=["Alice"],
    )
    # All traits high
    all_high = Personality(
        openness=0.9,
        conscientiousness=0.9,
        extraversion=0.9,
        agreeableness=0.9,
        neuroticism=0.9,
    )
    boost = compute_personality_boost(entry, all_high)
    # Should be meaningfully positive with multiple signals firing
    assert boost > 0.2


def test_boost_bounded_range():
    """Boost stays within reasonable bounds even with extreme traits."""
    entry = _entry(
        type=MemoryType.PROCEDURAL,
        importance=10,
        somatic=SomaticMarker(arousal=1.0, valence=1.0, label="max"),
        entities=["A", "B", "C", "D"],
    )
    max_personality = Personality(
        openness=1.0,
        conscientiousness=1.0,
        extraversion=1.0,
        agreeableness=1.0,
        neuroticism=1.0,
    )
    boost = compute_personality_boost(entry, max_personality)
    # Each trait contributes at most 0.5 * 1.0 * 0.3 = 0.15
    # Total max ≈ 5 * 0.15 = 0.75
    assert boost <= 0.8
    assert boost >= 0.0


# ---------------------------------------------------------------------------
# compute_activation — personality integration
# ---------------------------------------------------------------------------


def test_activation_unchanged_with_none_personality():
    """compute_activation with personality=None matches old behaviour."""
    entry = _entry(content="test memory", importance=5)
    score_no_p = compute_activation(entry, "test", now=NOW, noise=False, personality=None)
    score_neutral = compute_activation(
        entry, "test", now=NOW, noise=False, personality=_neutral_personality()
    )
    assert score_no_p == score_neutral


def test_activation_personality_modulates_score():
    """A high-openness personality changes the score for semantic memories."""
    semantic_entry = _entry(content="python is interpreted", type=MemoryType.SEMANTIC)
    personality = _high_trait("openness")

    score_without = compute_activation(
        semantic_entry, "python", now=NOW, noise=False, personality=None
    )
    score_with = compute_activation(
        semantic_entry, "python", now=NOW, noise=False, personality=personality
    )
    assert score_with > score_without


def test_activation_low_trait_reduces_score():
    """A low-openness personality reduces the score for semantic memories."""
    semantic_entry = _entry(content="python is interpreted", type=MemoryType.SEMANTIC)
    personality = _low_trait("openness")

    score_without = compute_activation(
        semantic_entry, "python", now=NOW, noise=False, personality=None
    )
    score_with = compute_activation(
        semantic_entry, "python", now=NOW, noise=False, personality=personality
    )
    assert score_with < score_without


# ---------------------------------------------------------------------------
# RecallEngine — end-to-end personality-modulated ranking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_high_neuroticism_ranks_emotional_higher():
    """A neurotic soul should rank emotionally intense memories higher."""
    episodic = EpisodicStore()
    semantic = SemanticStore()
    procedural = ProceduralStore()

    # Add two memories with same content relevance but different emotion
    calm_entry = MemoryEntry(
        id="calm1",
        type=MemoryType.SEMANTIC,
        content="meeting discussion about project timeline",
        importance=5,
    )
    intense_entry = MemoryEntry(
        id="intense1",
        type=MemoryType.SEMANTIC,
        content="heated argument about project deadline",
        importance=5,
        somatic=SomaticMarker(arousal=0.9, valence=-0.6, label="anger"),
    )
    semantic._facts["calm1"] = calm_entry
    semantic._facts["intense1"] = intense_entry

    neurotic = Personality(neuroticism=0.95)
    engine = RecallEngine(episodic, semantic, procedural, personality=neurotic)

    results = await engine.recall("project", limit=10)
    ids = [r.id for r in results]
    assert ids.index("intense1") < ids.index("calm1")


@pytest.mark.asyncio
async def test_recall_high_openness_ranks_semantic_higher():
    """A high-openness soul should rank knowledge memories higher."""
    episodic_store = EpisodicStore()
    semantic_store = SemanticStore()
    procedural_store = ProceduralStore()

    # Same content but different types
    episodic_entry = MemoryEntry(
        id="epi1",
        type=MemoryType.EPISODIC,
        content="talked about python programming language",
        importance=5,
    )
    semantic_entry = MemoryEntry(
        id="sem1",
        type=MemoryType.SEMANTIC,
        content="python is a programming language",
        importance=5,
    )
    episodic_store._memories["epi1"] = episodic_entry
    semantic_store._facts["sem1"] = semantic_entry

    open_personality = Personality(openness=0.95)
    engine = RecallEngine(
        episodic_store, semantic_store, procedural_store, personality=open_personality,
    )

    results = await engine.recall("python programming", limit=10)
    ids = [r.id for r in results]
    assert ids.index("sem1") < ids.index("epi1")


@pytest.mark.asyncio
async def test_recall_no_personality_is_backwards_compatible():
    """RecallEngine without personality works exactly as before."""
    episodic = EpisodicStore()
    semantic = SemanticStore()
    procedural = ProceduralStore()

    entry = MemoryEntry(
        id="test1",
        type=MemoryType.SEMANTIC,
        content="test content about cats",
        importance=5,
    )
    semantic._facts["test1"] = entry

    engine_none = RecallEngine(episodic, semantic, procedural, personality=None)
    engine_neutral = RecallEngine(
        episodic, semantic, procedural, personality=_neutral_personality()
    )

    # Both should return the same results
    results_none = await engine_none.recall("cats", limit=10)
    results_neutral = await engine_neutral.recall("cats", limit=10)

    assert len(results_none) == len(results_neutral) == 1


@pytest.mark.asyncio
async def test_recall_high_extraversion_ranks_episodic_higher():
    """An extraverted soul should rank social/episodic memories higher."""
    episodic_store = EpisodicStore()
    semantic_store = SemanticStore()
    procedural_store = ProceduralStore()

    episodic_entry = MemoryEntry(
        id="social1",
        type=MemoryType.EPISODIC,
        content="had coffee with Alice and discussed travel plans",
        importance=5,
        entities=["Alice"],
    )
    semantic_entry = MemoryEntry(
        id="fact1",
        type=MemoryType.SEMANTIC,
        content="coffee contains caffeine and is popular worldwide for travel",
        importance=5,
    )
    episodic_store._memories["social1"] = episodic_entry
    semantic_store._facts["fact1"] = semantic_entry

    extraverted = Personality(extraversion=0.95)
    engine = RecallEngine(
        episodic_store, semantic_store, procedural_store, personality=extraverted,
    )

    results = await engine.recall("coffee travel", limit=10)
    ids = [r.id for r in results]
    assert ids.index("social1") < ids.index("fact1")


@pytest.mark.asyncio
async def test_recall_high_agreeableness_ranks_positive_higher():
    """An agreeable soul should rank positive memories above neutral ones."""
    episodic = EpisodicStore()
    semantic = SemanticStore()
    procedural = ProceduralStore()

    positive_entry = MemoryEntry(
        id="pos1",
        type=MemoryType.SEMANTIC,
        content="team collaboration on the project was wonderful",
        importance=5,
        somatic=SomaticMarker(valence=0.8, arousal=0.4, label="joy"),
    )
    neutral_entry = MemoryEntry(
        id="neu1",
        type=MemoryType.SEMANTIC,
        content="team collaboration on the project was discussed",
        importance=5,
    )
    semantic._facts["pos1"] = positive_entry
    semantic._facts["neu1"] = neutral_entry

    agreeable = Personality(agreeableness=0.95)
    engine = RecallEngine(episodic, semantic, procedural, personality=agreeable)

    results = await engine.recall("team project collaboration", limit=10)
    ids = [r.id for r in results]
    assert ids.index("pos1") < ids.index("neu1")
