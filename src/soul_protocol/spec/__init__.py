# spec/__init__.py — Public exports for the spec primitives layer.
# Created: v0.4.0 — The "HTTP layer" of soul-protocol: minimal, unopinionated
# primitives that any runtime can implement. Zero imports from opinionated
# modules (memory/, cognitive/, evolution/, state/, dna/).
# Updated: Added EternalStorageProvider, EmbeddingProvider, similarity functions.
# Updated: Added ContextEngine protocol and LCM models for Lossless Context Management.
# Updated: 2026-03-23 — Added A2A Agent Card models (A2AAgentCard, A2ASkill, SoulExtension).
# Updated: feat/journal-spec — Exported Journal primitives (Actor, DataRef, EventEntry,
#   ACTION_NAMESPACES) from the new org journal module. See RFC PR #164.
# Updated: feat/decision-traces — Exported decision trace payload models
#   (AgentProposal, HumanCorrection, DecisionGraduation) and helpers
#   (build_proposal_event, build_correction_event, find_corrections_for,
#   trace_decision_chain, cluster_correction_patterns). See RFC PR #164,
#   Workstream D.
# Updated: feat/retrieval-trace-spec — Exported RetrievalTrace + TraceCandidate
#   from spec.trace (the per-recall receipt model — PR #161).
# Updated: feat/0.3.2-prune-retrieval-infra — Exported the retrieval vocabulary
#   that used to live under engine/retrieval/ as public spec types: protocols
#   (SourceAdapter, AsyncSourceAdapter, CredentialBroker), data classes
#   (Credential), and the RetrievalError exception hierarchy. Concrete
#   implementations (RetrievalRouter, InMemoryCredentialBroker,
#   ProjectionAdapter) are application-layer and now live in pocketpaw.
#   DataRef is re-exported as RetrievalDataRef to distinguish it from the
#   journal-layer DataRef in spec.journal.
# Updated: 2026-04-29 (#42) — Exported trust chain primitives from spec.trust:
#   TrustEntry, TrustChain, SignatureProvider, verify_chain, verify_entry,
#   chain_integrity_check, compute_payload_hash, compute_entry_hash,
#   GENESIS_PREV_HASH, DEFAULT_ALGORITHM. These are pure spec — concrete
#   Ed25519 implementation lives under runtime/crypto/.
# Updated: 2026-04-29 (#203) — Exported CHAIN_PRUNED_ACTION for the touch-time
#   pruning marker. Verifier carve-out lives in spec.trust.verify_entry.

from __future__ import annotations

from .a2a import A2AAgentCard, A2ASkill, SoulExtension
from .container import SoulContainer
from .context import (
    AssembleResult,
    CompactionLevel,
    ContextEngine,
    ContextMessage,
    ContextNode,
    DescribeResult,
    ExpandResult,
    GrepResult,
)
from .decisions import (
    AgentProposal,
    DecisionGraduation,
    Disposition,
    HumanCorrection,
    build_correction_event,
    build_proposal_event,
    cluster_correction_patterns,
    find_corrections_for,
    trace_decision_chain,
)
from .embeddings import (
    EmbeddingProvider,
    cosine_similarity,
    dot_product,
    euclidean_distance,
)
from .eternal import ArchiveResult, EternalStorageProvider, RecoverySource
from .identity import BondTarget, Identity
from .journal import ACTION_NAMESPACES, Actor, DataRef, EventEntry
from .learning import LearningEvent
from .manifest import Manifest
from .memory import (
    DEFAULT_DOMAIN,
    LAYER_CORE,
    LAYER_EPISODIC,
    LAYER_PROCEDURAL,
    LAYER_SEMANTIC,
    LAYER_SOCIAL,
    DictMemoryStore,
    Interaction,
    MemoryEntry,
    MemoryStore,
    MemoryVisibility,
    Participant,
)
from .retrieval import (
    AsyncSourceAdapter,
    CandidateSource,
    Credential,
    CredentialBroker,
    CredentialExpiredError,
    CredentialScopeError,
    NoSourcesError,
    PointInTimeNotSupported,
    RetrievalCandidate,
    RetrievalError,
    RetrievalRequest,
    RetrievalResult,
    SourceAdapter,
    SourceTimeoutError,
)
from .retrieval import (
    DataRef as RetrievalDataRef,
)
from .scope import match_scope, normalise_scopes
from .soul_file import pack_soul, unpack_soul, unpack_to_container
from .template import SoulTemplate
from .trace import RetrievalTrace, TraceCandidate
from .trust import (
    CHAIN_PRUNED_ACTION,
    DEFAULT_ALGORITHM,
    GENESIS_PREV_HASH,
    SignatureProvider,
    TrustChain,
    TrustEntry,
    chain_integrity_check,
    compute_entry_hash,
    compute_payload_hash,
    verify_chain,
    verify_entry,
)

__all__ = [
    # A2A Agent Card
    "A2AAgentCard",
    "A2ASkill",
    "SoulExtension",
    # Container
    "SoulContainer",
    # Context (LCM)
    "AssembleResult",
    "CompactionLevel",
    "ContextEngine",
    "ContextMessage",
    "ContextNode",
    "DescribeResult",
    "ExpandResult",
    "GrepResult",
    # Identity
    "BondTarget",
    "Identity",
    # Journal (org-level event sourcing)
    "ACTION_NAMESPACES",
    "Actor",
    "DataRef",
    "EventEntry",
    # Decision traces (agent.proposed / human.corrected / decision.graduated)
    "AgentProposal",
    "HumanCorrection",
    "DecisionGraduation",
    "Disposition",
    "build_proposal_event",
    "build_correction_event",
    "find_corrections_for",
    "trace_decision_chain",
    "cluster_correction_patterns",
    # Memory
    "Interaction",
    "MemoryEntry",
    "Participant",
    "MemoryStore",
    "MemoryVisibility",
    "DictMemoryStore",
    # Layer constants (#41) — conventions, not constraints
    "LAYER_CORE",
    "LAYER_EPISODIC",
    "LAYER_SEMANTIC",
    "LAYER_PROCEDURAL",
    "LAYER_SOCIAL",
    "DEFAULT_DOMAIN",
    # Scope
    "match_scope",
    "normalise_scopes",
    # Retrieval trace (per-recall receipt)
    "RetrievalTrace",
    "TraceCandidate",
    # Retrieval spec (types + protocols + exceptions).
    # Concrete implementations (RetrievalRouter, InMemoryCredentialBroker,
    # ProjectionAdapter) live in the consuming runtime — not part of the
    # headless standard. See ADR-NNN / docs/SPEC.md.
    "CandidateSource",
    "RetrievalRequest",
    "RetrievalCandidate",
    "RetrievalResult",
    "RetrievalDataRef",
    "PointInTimeNotSupported",
    "Credential",
    "CredentialBroker",
    "SourceAdapter",
    "AsyncSourceAdapter",
    "RetrievalError",
    "NoSourcesError",
    "SourceTimeoutError",
    "CredentialScopeError",
    "CredentialExpiredError",
    # Learning
    "LearningEvent",
    "SoulTemplate",
    # Soul file format
    "pack_soul",
    "unpack_soul",
    "unpack_to_container",
    # Manifest
    "Manifest",
    # Eternal storage protocol
    "ArchiveResult",
    "EternalStorageProvider",
    "RecoverySource",
    # Embedding protocol
    "EmbeddingProvider",
    "cosine_similarity",
    "euclidean_distance",
    "dot_product",
    # Trust chain (#42) — verifiable action history
    "DEFAULT_ALGORITHM",
    "GENESIS_PREV_HASH",
    "CHAIN_PRUNED_ACTION",
    "SignatureProvider",
    "TrustChain",
    "TrustEntry",
    "chain_integrity_check",
    "compute_entry_hash",
    "compute_payload_hash",
    "verify_chain",
    "verify_entry",
]
