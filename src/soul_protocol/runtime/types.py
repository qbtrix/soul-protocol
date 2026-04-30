# types.py — All Pydantic data models for the Digital Soul Protocol
# Updated: 2026-04-29 (#203) — Biorhythms.trust_chain_max_entries: configurable
#   cap for touch-time chain pruning. Default 0 = unbounded (preserves prior
#   behaviour). Positive values trigger pruning when the chain reaches the cap.
# Updated: 2026-04-29 (#41) — User-defined memory layers + domain isolation.
#   MemoryType keeps the four built-in StrEnum members (CORE, EPISODIC,
#   SEMANTIC, PROCEDURAL) plus SOCIAL for the new relationship layer; the
#   value strings double as layer names since StrEnum members compare
#   equal to their string values. MemoryEntry grows two new fields:
#   ``layer: str`` (canonical going forward — defaults to ``type.value``
#   when empty) and ``domain: str = "default"`` (sub-namespace for
#   isolating context like "finance" vs "legal"). A model_validator
#   coerces blank layer back to type.value and reads ``layer`` first on
#   load (falling back to ``type``) so 0.3.x souls round-trip.
# Updated: 2026-04-29 (#46) — Multi-user soul support. MemoryEntry gains an
#   optional ``user_id: str | None`` field. None = legacy/orphan entry that
#   belongs to the soul's default bond and is visible to any user_id query.
#   SoulConfig gains an optional ``bonds_per_user: dict[str, Bond]`` so the
#   per-user bond registry survives export/awaken.
# Updated: 2026-04-29 — Density-driven focus: SoulState gains focus_override and
#   recent_interactions; Biorhythms gains focus_window_seconds, focus_high_threshold,
#   focus_max_threshold. focus is now computed from interaction density unless
#   focus_override is set.
# Updated: 2026-04-04 — Added skip_deep_processing_on_low_significance to
#   MemorySettings. When True (default), observe() skips entity extraction
#   (step 5) and self-model update (step 6) for non-significant interactions,
#   saving 2 LLM calls per trivial interaction.
# Updated: 2026-03-29 — Added archived field to MemoryEntry for archival memory
#   tier integration (F2). Added consolidation_interval to MemorySettings and
#   interaction_count to SoulConfig for auto-consolidation (F5).
#   Added is_summarized runtime marker to MemoryEntry for progressive disclosure
#   in recall (F1). is_summarized=True signals that content was replaced with
#   abstract for overflow entries. Never persisted to disk.
# Updated: 2026-03-26 — Added skills and evaluation_history fields to SoulConfig so
#   that learned skills and evaluation history persist through export/awaken cycles.
# Updated: v0.4.0 — Added ingested_at (bi-temporal) and superseded (contradiction detection)
#   fields to MemoryEntry. ingested_at tracks when a memory entered the pipeline,
#   superseded marks memories replaced by newer contradicting information.
# Updated: feat/spec-multi-participant — Generalized Interaction to multi-participant
#   model with Participant list. Added backward-compatible user_input/agent_output
#   properties and from_pair() factory. Added BondTarget model and bonds list to
#   Identity for multi-bond support. Legacy bonded_to field preserved. Auto-migration
#   populates bonds from bonded_to if bonds is empty.
# Updated: v0.3.5 — Added RubricCriterion, Rubric, CriterionResult, RubricResult
#   models for rubric-based self-evaluation system.
# Updated: v0.3.4 — Added MemoryCategory for structured extraction taxonomy,
#   category + abstract + overview fields on MemoryEntry for progressive content
#   loading (L0/L1/L2 layers), salience field for retrieval weighting.
# Updated: Added Bond, incarnation, previous_lives, EternalLinks to Identity/SoulManifest.
#   v0.2.2 — Added superseded_by field to MemoryEntry for fact conflict resolution.
#   v0.2.1 — Added ReflectionResult for CognitiveEngine reflection output.
#   v0.2.0 — Added SomaticMarker, SignificanceScore, GeneralEvent, SelfImage
#   for psychology-informed memory. Extended MemoryEntry with somatic markers,
#   access_timestamps, significance, and general_event_id fields.

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .bond import Bond

# ============ Identity ============


class BondTarget(BaseModel):
    """An entity this soul is bonded to.

    Bond targets are portable — they travel with the soul across platforms.
    The bond_type field classifies the relationship kind.
    """

    id: str  # DID or identifier
    label: str = ""  # Human-readable name
    bond_type: str = "human"  # "human", "soul", "agent", "group", "service"


class Identity(BaseModel):
    """A soul's unique identity with cryptographic DID.

    Multi-bond support: ``bonds`` holds a list of BondTarget entities.
    The legacy ``bonded_to`` field is preserved for backward compatibility.
    On model_post_init, if bonded_to is set and bonds is empty, bonds is
    auto-populated from bonded_to (migration path).
    """

    did: str = ""
    name: str
    archetype: str = ""
    role: str = ""  # Free-form: "root" marks an org's governance soul (undeletable). Empty for normal souls.
    born: datetime = Field(default_factory=datetime.now)
    bonded_to: str | None = None  # DEPRECATED — use bonds instead
    bonds: list[BondTarget] = Field(default_factory=list)
    origin_story: str = ""
    prime_directive: str = ""
    core_values: list[str] = Field(default_factory=list)
    bond: Bond = Field(default_factory=Bond)
    incarnation: int = 1
    previous_lives: list[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        """Auto-migrate bonded_to to bonds if bonds is empty."""
        if self.bonded_to and not self.bonds:
            self.bonds.append(BondTarget(id=self.bonded_to, bond_type="human"))


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
    """Simulated vitality and energy patterns.

    Defaults to "always-on" mode with no energy/social drain — appropriate for
    developer tools, consulting agents, and most non-companion use cases.
    For companion souls that should simulate fatigue and recovery, set
    energy_drain_rate, social_drain_rate, and auto_regen explicitly::

        Biorhythms(energy_drain_rate=2.0, social_drain_rate=5.0, auto_regen=True)
    """

    chronotype: str = "neutral"
    # Note: initial social battery at birth. StateManager reads SoulState.social_battery
    # at runtime, not this field. Soul.birth() syncs this into SoulState at creation time.
    social_battery: float = Field(default=100.0, ge=0.0, le=100.0)

    # Energy dynamics — defaults to 0 (always-on, no drain)
    energy_regen_rate: float = Field(
        default=0.0,
        ge=0.0,
        description="Energy recovered per hour of elapsed time (0 = no regen needed)",
    )
    energy_drain_rate: float = Field(
        default=0.0, ge=0.0, description="Energy lost per interaction (0 = no drain)"
    )
    social_drain_rate: float = Field(
        default=0.0, ge=0.0, description="Social battery lost per interaction (0 = no drain)"
    )

    # Mood dynamics
    tired_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Energy below this forces TIRED mood (0 = disabled)",
    )
    mood_inertia: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="EMA alpha for mood shifts (0 = max inertia, 1 = instant)",
    )
    mood_sensitivity: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Valence threshold to trigger mood change (0 = always shift)",
    )

    # Auto-regeneration
    auto_regen: bool = Field(
        default=False,
        description="Recover energy automatically based on elapsed time (enable for companion souls)",
    )

    # Focus dynamics — density-driven
    focus_window_seconds: float = Field(
        default=3600.0,
        ge=0.0,
        description="Sliding window for interaction-density focus calc (0 disables auto-focus)",
    )
    focus_high_threshold: int = Field(
        default=3,
        ge=1,
        description="Interactions in window at or above which focus rises to 'high'",
    )
    focus_max_threshold: int = Field(
        default=10,
        ge=1,
        description="Interactions in window at or above which focus rises to 'max'",
    )

    # Trust chain pruning (#203) — touch-time stub
    trust_chain_max_entries: int = Field(
        default=0,
        ge=0,
        description=(
            "Maximum entries the trust chain may carry before touch-time pruning fires. "
            "0 (default) disables pruning and preserves the unbounded-chain behaviour. "
            "Positive values cause append() to compress the non-genesis history into a "
            "single signed `chain.pruned` marker once the cap is reached. The full "
            "archival design lives in v0.5.x."
        ),
    )


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


class MemoryVisibility(StrEnum):
    """Visibility tier for memory entries in public channel contexts."""

    PUBLIC = "public"
    BONDED = "bonded"
    PRIVATE = "private"


class MemoryType(StrEnum):
    """Built-in memory tiers. v0.4.0 (#41) treats these as ergonomic
    constants for layer names — runtimes can use any string layer they
    want via :class:`soul_protocol.runtime.memory.manager.LayerView`."""

    CORE = "core"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    SOCIAL = "social"  # v0.4.0 (#41) — relationship memory tier


class MemoryCategory(StrEnum):
    """Structured extraction taxonomy for memory classification.

    User-facing categories (about the bonded entity):
    - PROFILE: Static identity attributes (name, role, location)
    - PREFERENCE: Choices and habits (one facet per memory)
    - ENTITY: Named things with attributes (projects, people, tools)
    - EVENT: Time-bound activities (always absolute timestamps)

    Agent-facing categories (about what the soul learned):
    - CASE: Problem + cause + solution + outcome
    - PATTERN: Reusable processes across scenarios
    - SKILL: Skill execution strategies and tool usage knowledge
    """

    # User-facing (feed the bond system / human profile)
    PROFILE = "profile"
    PREFERENCE = "preference"
    ENTITY = "entity"
    EVENT = "event"
    # Agent-facing (feed the self-model)
    CASE = "case"
    PATTERN = "pattern"
    SKILL = "skill"


class MemoryEntry(BaseModel):
    """A single memory with metadata.

    v0.4.0 (#41) additions: ``layer`` is the canonical going-forward layer
    name (free-form string). Defaults to the ``type`` value when not given,
    so legacy callers using ``MemoryEntry(type=MemoryType.SEMANTIC)`` get
    ``layer="semantic"`` for free. ``domain`` is a sub-namespace inside the
    layer (``"finance"``, ``"legal"``, ``"default"``); defaults to
    ``"default"`` so 0.3.x entries round-trip without migration.

    v0.3.4 additions: category (extraction taxonomy), abstract (L0 ~100 tokens),
    overview (L1 ~1K tokens) for progressive content loading, salience (retrieval
    weight). All new fields default to None for backwards compatibility.

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
    # v0.3.4 — Extraction taxonomy and progressive content loading
    category: MemoryCategory | None = None
    abstract: str | None = None  # L0: ~100 token semantic fingerprint
    overview: str | None = None  # L1: ~1K token structured summary
    salience: float = Field(default=0.5, ge=0.0, le=1.0)  # Retrieval weight
    # v0.4.0 — Bi-temporal ingestion timestamp
    ingested_at: datetime | None = None  # When memory entered the pipeline
    # v0.4.0 — Contradiction detection
    superseded: bool = False  # True when a newer memory contradicts this one
    visibility: MemoryVisibility = MemoryVisibility.BONDED
    # F2 archival memory — marks episodic memories that have been archived
    archived: bool = False  # True when memory has been compressed into a ConversationArchive
    # F1 progressive disclosure — runtime-only marker, never persisted
    is_summarized: bool = False  # Runtime marker: True when content replaced with abstract
    # Move 5 PR-A — RBAC/ABAC scope tags. Empty list = no scope assigned
    # (visible to any caller). Hierarchical glob: "org:sales:*" matches
    # "org:sales:leads". Filtered at retrieval time before results reach
    # the LLM.
    scope: list[str] = Field(default_factory=list)
    # v0.4.0 (#46) — Per-user attribution. None = legacy / orphan entry that
    # belongs to the soul's default bond and is visible to any user_id query.
    # When set, recall filters entries to those matching the requested
    # user_id (plus None entries for back-compat).
    user_id: str | None = None
    # v0.4.0 (#41) — Free-form layer namespace. Empty string is coerced to
    # ``type.value`` by ``_coerce_layer_domain`` so legacy callers keep
    # working. When both ``layer`` and ``type`` round-trip on disk, ``layer``
    # is the canonical field; ``type`` exists for back-compat.
    layer: str = ""
    # v0.4.0 (#41) — Domain sub-namespace inside the layer. Use to isolate
    # context like "finance" vs "legal" inside the same layer of facts.
    # Empty string is coerced to "default" by ``_coerce_layer_domain``.
    domain: str = "default"

    @model_validator(mode="before")
    @classmethod
    def _coerce_layer_domain(cls, data: Any) -> Any:
        """Fill in ``layer``/``domain`` defaults from legacy fields.

        - When ``layer`` is missing or blank, derive it from ``type``.
        - When ``domain`` is missing or blank, set it to ``"default"``.

        This runs at deserialize time, so 0.3.x souls (which carry only
        ``type``) come back with a sensible layer + domain without a
        separate migration pass.
        """
        if isinstance(data, dict):
            layer_val = data.get("layer", "")
            if not layer_val:
                # Pull from type — accepts MemoryType enum or raw string.
                tval = data.get("type")
                if tval is None:
                    pass
                elif isinstance(tval, MemoryType):
                    data["layer"] = tval.value
                elif isinstance(tval, str):
                    data["layer"] = tval
            domain_val = data.get("domain", "")
            if not domain_val:
                data["domain"] = "default"
        return data


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
    # F5 auto-consolidation — archive + reflect every N interactions
    consolidation_interval: int = 20
    # When True, skip entity extraction (step 5) and self-model update (step 6)
    # for interactions that are not significant after the full pipeline
    # (including fact-based promotion in step 4b). Saves 2 LLM calls per
    # low-value interaction.
    skip_deep_processing_on_low_significance: bool = True
    # LLM-based reranking on recall. Off by default because it adds an LLM
    # call on every smart_recall invocation. Callers who need relevance
    # quality over latency can opt in by constructing MemorySettings with
    # smart_recall_enabled=True, or override per-call via the enabled= arg
    # on Soul.smart_recall().
    smart_recall_enabled: bool = False


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


FOCUS_LEVELS: tuple[str, ...] = ("low", "medium", "high", "max")


class SoulState(BaseModel):
    """The soul's current emotional and energy state.

    ``focus`` is the effective level (one of FOCUS_LEVELS). When
    ``focus_override`` is None, StateManager recomputes focus from
    ``recent_interactions`` density on each interaction or status read.
    Setting ``focus_override`` to a level locks focus to that value
    until cleared (set focus_override back to None or call
    ``manager.update(focus="auto")``).
    """

    mood: Mood = Mood.NEUTRAL
    energy: float = Field(default=100.0, ge=0.0, le=100.0)
    focus: str = "medium"
    focus_override: str | None = None
    social_battery: float = Field(default=100.0, ge=0.0, le=100.0)
    last_interaction: datetime | None = None
    recent_interactions: list[datetime] = Field(default_factory=list)


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


# ============ Rubric-based Self-Evaluation ============


class RubricCriterion(BaseModel):
    """A single pass/fail evaluation criterion."""

    name: str
    description: str
    weight: float = Field(default=1.0, gt=0.0)


class Rubric(BaseModel):
    """A named collection of evaluation criteria for a domain."""

    id: str = ""
    name: str
    domain: str = ""
    criteria: list[RubricCriterion]

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            self.id = self.name.lower().replace(" ", "_")


class CriterionResult(BaseModel):
    """Result of evaluating one criterion."""

    criterion: str
    passed: bool
    score: float  # 0.0-1.0
    reasoning: str = ""


class RubricResult(BaseModel):
    """Complete evaluation result against a rubric."""

    rubric_id: str
    overall_score: float  # weighted average, 0.0-1.0
    criterion_results: list[CriterionResult]
    learning: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvolutionConfig(BaseModel):
    """Evolution system configuration."""

    mode: EvolutionMode = EvolutionMode.SUPERVISED
    mutation_rate: float = 0.01
    require_approval: bool = True
    mutable_traits: list[str] = Field(default_factory=lambda: ["communication", "biorhythms"])
    immutable_traits: list[str] = Field(default_factory=lambda: ["personality", "core_values"])
    history: list[Mutation] = Field(default_factory=list)
    pending: list[Mutation] = Field(default_factory=list)


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
    skills: list[dict] = Field(default_factory=list)
    evaluation_history: list[dict] = Field(default_factory=list)
    # F5 auto-consolidation — tracks observe() call count for consolidation triggers
    interaction_count: int = 0
    # v0.4.0 (#46) — Per-user bond registry. The default bond lives on
    # ``identity.bond`` for back-compat; this dict carries any extra per-user
    # bonds that the runtime accumulates. Empty when only one user is bonded.
    bonds_per_user: dict[str, Bond] = Field(default_factory=dict)


# ============ Interaction (input to observe()) ============


class Participant(BaseModel):
    """A participant in an interaction.

    Role is a free-form string — runtimes define their own roles.
    Common roles: "user", "agent", "soul", "system", "observer".
    """

    role: str  # "user", "agent", "soul", "system", etc.
    id: str | None = None  # DID or identifier
    content: str


class Interaction(BaseModel):
    """A multi-participant interaction for the soul to observe.

    Generalized from the original 2-party model. Supports N participants.
    Backward compatible: ``user_input`` and ``agent_output`` properties
    return the first "user" and "agent" participant content. The legacy
    constructor ``Interaction(user_input=..., agent_output=...)`` still
    works via the model_validator that auto-converts to participants.

    Use ``from_pair()`` for the common 2-party case.
    """

    participants: list[Participant] = Field(default_factory=list)
    channel: str = "unknown"
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        """Auto-convert legacy user_input/agent_output to participants."""
        if isinstance(data, dict):
            user_input = data.pop("user_input", None)
            agent_output = data.pop("agent_output", None)
            if user_input is not None or agent_output is not None:
                participants = data.get("participants", [])
                if not participants:
                    new_participants = []
                    if user_input is not None:
                        new_participants.append({"role": "user", "content": user_input})
                    if agent_output is not None:
                        new_participants.append({"role": "agent", "content": agent_output})
                    data["participants"] = new_participants
        return data

    @property
    def user_input(self) -> str:
        """Content from the first 'user' participant (backward compat)."""
        for p in self.participants:
            if p.role == "user":
                return p.content
        return ""

    @property
    def agent_output(self) -> str:
        """Content from the first 'agent' participant (backward compat)."""
        for p in self.participants:
            if p.role == "agent":
                return p.content
        return ""

    @classmethod
    def from_pair(
        cls,
        user_input: str,
        agent_output: str,
        *,
        channel: str = "unknown",
        timestamp: datetime | None = None,
        metadata: dict | None = None,
    ) -> Interaction:
        """Create a 2-party interaction from user input and agent output."""
        return cls(
            participants=[
                Participant(role="user", content=user_input),
                Participant(role="agent", content=agent_output),
            ],
            channel=channel,
            timestamp=timestamp or datetime.now(),
            metadata=metadata or {},
        )


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
