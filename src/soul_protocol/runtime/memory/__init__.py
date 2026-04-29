# memory/__init__.py — Memory subsystem package for the Digital Soul Protocol.
# Updated: 2026-04-29 (#41) — Added SocialStore (relationship layer) and
#   LayerView (thin accessor) exports for user-defined layers + domain
#   isolation.
# Updated: 2026-04-01 — Added rerank_memories export for LLM-based memory reranking.
# Updated: v0.4.0 — Added ContradictionDetector export.
# Updated: Phase 2 memory-runtime-v2 — Added reconcile_fact export from dedup module.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Updated: v0.2.2 — Added SearchStrategy protocol and TokenOverlapStrategy exports.
#   v0.2.0 — Added psychology modules: sentiment, activation, attention, self_model.
#   2026-03-06 — Added ArchivalMemoryStore, MemoryCompressor exports.

from __future__ import annotations

from soul_protocol.runtime.memory.activation import compute_activation
from soul_protocol.runtime.memory.archival import ArchivalMemoryStore, ConversationArchive
from soul_protocol.runtime.memory.attention import compute_significance, is_significant
from soul_protocol.runtime.memory.compression import MemoryCompressor
from soul_protocol.runtime.memory.contradiction import ContradictionDetector
from soul_protocol.runtime.memory.core import CoreMemoryManager
from soul_protocol.runtime.memory.dedup import reconcile_fact
from soul_protocol.runtime.memory.episodic import EpisodicStore
from soul_protocol.runtime.memory.graph import KnowledgeGraph, TemporalEdge
from soul_protocol.runtime.memory.manager import LayerView, MemoryManager
from soul_protocol.runtime.memory.procedural import ProceduralStore
from soul_protocol.runtime.memory.recall import RecallEngine
from soul_protocol.runtime.memory.rerank import rerank_memories
from soul_protocol.runtime.memory.self_model import SelfModelManager
from soul_protocol.runtime.memory.semantic import SemanticStore
from soul_protocol.runtime.memory.sentiment import detect_sentiment
from soul_protocol.runtime.memory.social import SocialStore
from soul_protocol.runtime.memory.strategy import SearchStrategy, TokenOverlapStrategy

__all__ = [
    "MemoryManager",
    "CoreMemoryManager",
    "EpisodicStore",
    "SemanticStore",
    "ProceduralStore",
    # v0.4.0 (#41) — relationship layer + thin layer accessor
    "SocialStore",
    "LayerView",
    "KnowledgeGraph",
    "TemporalEdge",
    "RecallEngine",
    "ArchivalMemoryStore",
    "ConversationArchive",
    "MemoryCompressor",
    # v0.2.0 psychology modules
    "detect_sentiment",
    "compute_activation",
    "compute_significance",
    "is_significant",
    "SelfModelManager",
    # v0.2.2 pluggable retrieval
    "SearchStrategy",
    "TokenOverlapStrategy",
    # Phase 2 — dedup pipeline
    "reconcile_fact",
    # v0.4.0 — contradiction detection
    "ContradictionDetector",
    # Smart reranking
    "rerank_memories",
]
