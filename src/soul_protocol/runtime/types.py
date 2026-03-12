# types.py — All Pydantic data models for the Digital Soul Protocol
# Updated: Added Bond, incarnation, previous_lives, EternalLinks to Identity/SoulManifest.
#   v0.2.2 — Added superseded_by field to MemoryEntry for fact conflict resolution.
#   v0.2.1 — Added ReflectionResult for CognitiveEngine reflection output.
#   v0.2.0 — Added SomaticMarker, SignificanceScore, GeneralEvent, SelfImage
#   for psychology-informed memory. Extended MemoryEntry with somatic markers,
#   access_timestamps, significance, and general_event_id fields.

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .bond import Bond

# ============ Identity ============


class Identity(BaseModel):
    """A soul's unique identity with cryptographic DID."""

    did: str = ""
    name: str
    archetype: str = ""
    born: datetime = Field(default_factory=datetime.now)
    bonded_to: str | None = None
    origin_story: str = ""
    prime_directive: str = ""
    core_values: list[str] = Field(default_factory=list)
    bond: Bond = Field(default_factory=Bond)
    incarnation: int = 1
    previous_lives: list[str] = Field(default_factory=list)


# ============ DNA / Personality ============


class Personality(BaseModel):
    """Big Five OCEAN model — each trait 0.0 to 1.0."""

    openness: float = Field(default=0.5, ge=0.0, le=1.0)
    conscientiousness: float = Field(default=0.5, ge=0.0, le=1.0)
    extraversion: float = Field(default=0.5, ge=0.0, le=1.0)
    agreeableness: float = Field(default=0.5, ge=0.0, le=1.0)
    neuroticism: float = Field(default=0.5, ge=0.0, le=1.0)


class CommunicationStyle(BaseModel):
    """How the soul communicates."""

    warmth: str = "moderate"
    verbosity: str = "moderate"
    humor_style: str = "none"
    emoji_usage: str = "none"


class Biorhythms(BaseModel):
    """Simulated vitality and energy patterns."""

    chronotype: str = "neutral"
    social_battery: float = Field(default=100.0, ge=0.0, le=100.0)
    energy_regen_rate: float = 5.0


class DNA(BaseModel):
    """The soul's complete personality blueprint."""

    personality: Personality = Field(default_factory=Personality)
    communication: CommunicationStyle = Field(default_factory=CommunicationStyle)
    biorhythms: Biorhythms = Field(default_factory=Biorhythms)


# ============ Psychology — Somatic Markers (Damasio) ============


class SomaticMarker(BaseModel):
    """Emotional context tagged onto a memory (Damasio's Somatic Marker Hypothesis).

    Emotions are not separate from cognition — they guide recall and decision-making.
    """

    valence: float = Field(default=0.0, ge=-1.0, le=1.0)  # negative to positive
    arousal: float = Field(default=0.0, ge=0.0, le=1.0)  # calm to intense
    label: str = "neutral"  # joy, frustration, curiosity, etc.


# ============ Psychology — Significance (LIDA) ============


class SignificanceScore(BaseModel):
    """Significance gate for episodic storage (LIDA architecture).

    Only experiences that pass a significance threshold become episodic memories.
    """

    novelty: float = Field(default=0.0, ge=0.0, le=1.0)
    emotional_intensity: float = Field(default=0.0, ge=0.0, le=1.0)
    goal_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    content_richness: float = Field(default=0.0, ge=0.0, le=1.0)


# ============ Psychology — General Events (Conway) ============


class GeneralEvent(BaseModel):
    """Hierarchical autobiography grouping (Conway's Self-Memory System).

    Episodes cluster into general events (themes), which cluster into
    lifetime periods. This is the general event level.
    """

    id: str = ""
    theme: str = ""
    episode_ids: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)


# ============ Psychology — Self-Image (Klein) ============


class SelfImage(BaseModel):
    """A facet of the soul's self-concept (Klein's self-model).

    Built from accumulated experience — the soul learns who it is
    by observing what it does.
    """

    domain: str = ""  # e.g. "technical_helper", "creative_writer"
    confidence: float = Field(default=0.1, ge=0.0, le=1.0)
    evidence_count: int = 0  # interactions supporting this self-image


# ============ Memory ============


class MemoryType(StrEnum):
    CORE = "core"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryEntry(BaseModel):
    """A single memory with metadata.

    v0.2.0 additions: somatic markers (emotional context), access_timestamps
    (full history for ACT-R decay), significance score, and general_event_id
    (Conway hierarchy link). All new fields default to None/empty for
    backwards compatibility with v0.1.0 data.
    """

    id: str = ""
    type: MemoryType
    content: str
    importance: int = Field(default=5, ge=1, le=10)
    emotion: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    entities: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    last_accessed: datetime | None = None
    access_count: int = 0
    # v0.2.0 — Psychology-informed fields
    somatic: SomaticMarker | None = None
    access_timestamps: list[datetime] = Field(default_factory=list)
    significance: float = 0.0
    general_event_id: str | None = None
    # v0.2.2 — Fact conflict resolution
    superseded_by: str | None = None


class CoreMemory(BaseModel):
    """Always-loaded memory — persona description + human profile."""

    persona: str = ""
    human: str = ""


class MemorySettings(BaseModel):
    """Configuration for memory subsystem."""

    episodic_max_entries: int = 10000
    semantic_max_facts: int = 1000
    importance_threshold: int = 3
    confidence_threshold: float = 0.7
    persona_tokens: int = 500
    human_tokens: int = 500


# ============ State / Feelings ============


class Mood(StrEnum):
    NEUTRAL = "neutral"
    CURIOUS = "curious"
    FOCUSED = "focused"
    TIRED = "tired"
    EXCITED = "excited"
    CONTEMPLATIVE = "contemplative"
    SATISFIED = "satisfied"
    CONCERNED = "concerned"


class SoulState(BaseModel):
    """The soul's current emotional and energy state."""

    mood: Mood = Mood.NEUTRAL
    energy: float = Field(default=100.0, ge=0.0, le=100.0)
    focus: str = "medium"
    social_battery: float = Field(default=100.0, ge=0.0, le=100.0)
    last_interaction: datetime | None = None


# ============ Evolution ============


class EvolutionMode(StrEnum):
    DISABLED = "disabled"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class Mutation(BaseModel):
    """A proposed or applied trait change."""

    id: str = ""
    trait: str
    old_value: str
    new_value: str
    reason: str
    proposed_at: datetime = Field(default_factory=datetime.now)
    approved: bool | None = None
    approved_at: datetime | None = None


class EvolutionConfig(BaseModel):
    """Evolution system configuration."""

    mode: EvolutionMode = EvolutionMode.SUPERVISED
    mutation_rate: float = 0.01
    require_approval: bool = True
    mutable_traits: list[str] = Field(default_factory=lambda: ["communication", "biorhythms"])
    immutable_traits: list[str] = Field(default_factory=lambda: ["personality", "core_values"])
    history: list[Mutation] = Field(default_factory=list)


# ============ Lifecycle ============


class LifecycleState(StrEnum):
    BORN = "born"
    ACTIVE = "active"
    DORMANT = "dormant"
    RETIRED = "retired"


# ============ Full Soul Config ============


class SoulConfig(BaseModel):
    """Complete serializable Soul configuration."""

    version: str = "1.0.0"
    identity: Identity
    dna: DNA = Field(default_factory=DNA)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    core_memory: CoreMemory = Field(default_factory=CoreMemory)
    state: SoulState = Field(default_factory=SoulState)
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    lifecycle: LifecycleState = LifecycleState.BORN


# ============ Interaction (input to observe()) ============


class Interaction(BaseModel):
    """A single user-agent interaction for the soul to observe."""

    user_input: str
    agent_output: str
    channel: str = "unknown"
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)


# ============ Manifest (for .soul archives) ============


# ============ Reflection (v0.2.1) ============


class ReflectionResult(BaseModel):
    """Output of a soul's reflection pass (LLM-only).

    Contains themes, summaries, and insights from reviewing recent episodes.
    Only produced when a CognitiveEngine (LLM) is available.
    """

    themes: list[str] = Field(default_factory=list)
    summaries: list[dict] = Field(default_factory=list)
    emotional_patterns: str = ""
    self_insight: str = ""


# ============ Eternal Storage ============


class EternalLinks(BaseModel):
    """References to eternal storage tiers for a soul archive."""

    ipfs: dict[str, Any] = Field(default_factory=dict)  # cid, pinned_by, etc.
    arweave: dict[str, Any] = Field(default_factory=dict)  # tx_id, cost, etc.
    blockchain: dict[str, Any] = Field(default_factory=dict)  # chain, contract, token_id


# ============ Manifest (for .soul archives) ============


class SoulManifest(BaseModel):
    """Metadata for a .soul archive file."""

    format_version: str = "1.0.0"
    created: datetime = Field(default_factory=datetime.now)
    exported: datetime = Field(default_factory=datetime.now)
    soul_id: str = ""
    soul_name: str = ""
    checksum: str = ""
    encrypted: bool = False
    stats: dict = Field(default_factory=dict)
    eternal: EternalLinks = Field(default_factory=EternalLinks)
