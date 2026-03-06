# types.py — All Pydantic data models for the Digital Soul Protocol
# Created: 2026-02-22 — Complete type system from DSP-IMPLEMENTATION-SPEC
# Updated: 2026-03-06 — Added Bond, incarnation, previous_lives to Identity

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from soul_protocol.bond import Bond


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


# ============ Memory ============


class MemoryType(str, Enum):
    CORE = "core"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryEntry(BaseModel):
    """A single memory with metadata."""

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


class Mood(str, Enum):
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


class EvolutionMode(str, Enum):
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
    mutable_traits: list[str] = Field(
        default_factory=lambda: ["communication", "biorhythms"]
    )
    immutable_traits: list[str] = Field(
        default_factory=lambda: ["personality", "core_values"]
    )
    history: list[Mutation] = Field(default_factory=list)


# ============ Lifecycle ============


class LifecycleState(str, Enum):
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


class SoulManifest(BaseModel):
    """Metadata for a .soul archive file."""

    format_version: str = "1.0.0"
    created: datetime = Field(default_factory=datetime.now)
    exported: datetime = Field(default_factory=datetime.now)
    soul_id: str = ""
    soul_name: str = ""
    checksum: str = ""
    stats: dict = Field(default_factory=dict)
