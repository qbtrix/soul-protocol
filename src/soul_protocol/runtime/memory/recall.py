# memory/recall.py — RecallEngine for cross-store memory retrieval.
# Updated: 2026-03-29 — Added progressive parameter to recall(). When progressive=True,
#   returns up to limit*2 entries: primary (full content) + overflow (abstract-only copies).
#   Overflow entries with no abstract keep their original content unchanged.
# Updated: v0.4.0 — Wire knowledge graph into recall pipeline. After ACT-R scoring,
#   query graph for entities mentioned in the query via progressive_context(level=1).
#   Graph-connected memories get a boost. Add use_graph parameter (default True).
# Updated: feat/memory-visibility-templates — Added visibility filtering to recall
#   pipeline. Accept requester_id and bond_strength params to gate BONDED/PRIVATE
#   memories. PUBLIC memories always pass. BONDED requires bond_strength >= threshold.
#   PRIVATE only passes for system/soul requesters (requester_id=None).
# Updated: v0.3.3 — Accept optional Personality for OCEAN trait-modulated recall.
#   Personality influences which memories surface: high-Neuroticism boosts emotional
#   memories, high-Openness boosts knowledge, etc. Backwards compatible.
# Updated: phase1-ablation-fixes — Default to BM25SearchStrategy instead of
#   TokenOverlapStrategy when no strategy is provided.
# Updated: 2026-03-10 — Accept optional personality param (passed by MemoryManager, reserved for future use).
# Updated: v0.2.2 — Accept optional SearchStrategy for pluggable spreading activation.
#   v0.2.0 — Replaced flat relevance scoring with ACT-R activation-based
#   ranking. Memories are now scored by base-level activation (recency + frequency),
#   spreading activation (query relevance), and emotional boost (somatic markers).
#   Access timestamps are updated on retrieval (strengthens future recall).
#   Timestamps capped at MAX_ACCESS_TIMESTAMPS to bound memory growth.
# Updated: Added structured logging for recall queries and empty results.
# Updated: Removed PII from debug logs — logs query length instead of raw
#   query text. Fixed import ordering (logger after all imports).

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from soul_protocol.runtime.memory.activation import compute_activation
from soul_protocol.runtime.memory.episodic import EpisodicStore
from soul_protocol.runtime.memory.graph import KnowledgeGraph
from soul_protocol.runtime.memory.procedural import ProceduralStore
from soul_protocol.runtime.memory.semantic import SemanticStore
from soul_protocol.runtime.memory.strategy import BM25SearchStrategy
from soul_protocol.runtime.types import MemoryEntry, MemoryType, MemoryVisibility, Personality

if TYPE_CHECKING:
    from soul_protocol.runtime.memory.strategy import SearchStrategy

# Cap access_timestamps to prevent unbounded memory growth in long-running sessions.
# 100 timestamps is sufficient for ACT-R power-law decay calculations.
MAX_ACCESS_TIMESTAMPS: int = 100

# Default bond strength threshold for BONDED memory access.
# Souls start at bond_strength=50, so 30 means even new bonds get some access.
DEFAULT_BOND_THRESHOLD: float = 30.0


def filter_by_visibility(
    entries: list[MemoryEntry],
    requester_id: str | None,
    bond_strength: float,
    bond_threshold: float = DEFAULT_BOND_THRESHOLD,
) -> list[MemoryEntry]:
    """Filter memories by visibility tier based on requester context.

    Args:
        entries: Candidate memories to filter.
        requester_id: ID of the entity requesting recall.
            None means the soul itself or system (full access).
        bond_strength: Current bond strength with the requester (0-100).
        bond_threshold: Minimum bond strength for BONDED memory access.

    Returns:
        Filtered list containing only memories the requester can see.
    """
    if requester_id is None:
        # Soul/system context — full access to everything
        return entries

    filtered: list[MemoryEntry] = []
    for entry in entries:
        if entry.visibility == MemoryVisibility.PUBLIC:
            filtered.append(entry)
        elif entry.visibility == MemoryVisibility.BONDED:
            if bond_strength >= bond_threshold:
                filtered.append(entry)
        # PRIVATE memories are never returned to external requesters
    return filtered


class RecallEngine:
    """Cross-store memory retrieval engine with ACT-R activation scoring.

    Queries all configured memory stores and ranks results by cognitive
    activation: recency + frequency (base-level), query relevance (spreading),
    and emotional intensity (somatic boost).
    """

    def __init__(
        self,
        episodic: EpisodicStore,
        semantic: SemanticStore,
        procedural: ProceduralStore,
        strategy: SearchStrategy | None = None,
        personality: Personality | None = None,
        graph: KnowledgeGraph | None = None,
    ) -> None:
        self._episodic = episodic
        self._semantic = semantic
        self._procedural = procedural
        self._strategy = strategy if strategy is not None else BM25SearchStrategy()
        self._personality = personality
        self._graph = graph

    async def recall(
        self,
        query: str,
        limit: int = 10,
        types: list[MemoryType] | None = None,
        min_importance: int = 0,
        use_graph: bool = True,
        requester_id: str | None = None,
        bond_strength: float = 100.0,
        bond_threshold: float = DEFAULT_BOND_THRESHOLD,
        progressive: bool = False,
    ) -> list[MemoryEntry]:
        """Search across memory stores and return activation-ranked results.

        When use_graph is True and a KnowledgeGraph is available, entities
        mentioned in the query are looked up via progressive_context(level=1).
        Related entity names are used as additional search terms to surface
        graph-connected memories that pure text matching would miss.

        Args:
            query: Search string for activation scoring.
            limit: Maximum number of results to return.
            types: If provided, only search these memory types.
                   If None, search all stores.
            min_importance: Minimum importance score (1-10) for results.
            use_graph: If True, augment recall with knowledge graph traversal.
            requester_id: ID of the requesting entity. None means
                the soul itself (system context, full access).
            bond_strength: Bond strength with the requester (0-100).
                Only used when requester_id is not None.
            bond_threshold: Minimum bond strength for BONDED memory access.

        Returns:
            List of MemoryEntry sorted by activation score descending.
        """
        results: list[MemoryEntry] = []
        search_all = types is None

        # When progressive mode is on, fetch more candidates so we have overflow
        fetch_limit = limit * 2 if progressive else limit

        # Query each store based on requested types
        if search_all or MemoryType.EPISODIC in types:
            episodic_results = await self._episodic.search(query, limit=fetch_limit)
            results.extend(episodic_results)

        if search_all or MemoryType.SEMANTIC in types:
            semantic_results = await self._semantic.search(
                query, limit=fetch_limit, min_importance=min_importance
            )
            results.extend(semantic_results)

        if search_all or MemoryType.PROCEDURAL in types:
            procedural_results = await self._procedural.search(query, limit=fetch_limit)
            results.extend(procedural_results)

        # Apply importance filter to non-semantic results (semantic already filtered)
        if min_importance > 0:
            results = [r for r in results if r.importance >= min_importance]

        # --- Graph augmentation: surface graph-connected memories ---
        if use_graph and self._graph is not None:
            graph_entities = self._graph.entities()
            query_lower = query.lower()
            # Find entities mentioned in the query
            matched_entities: list[str] = []
            for entity_name in graph_entities:
                if entity_name.lower() in query_lower:
                    matched_entities.append(entity_name)

            if matched_entities:
                # Collect related entity names from graph traversal
                related_terms: set[str] = set()
                for entity_name in matched_entities:
                    context = self._graph.progressive_context(entity_name, level=1)
                    for rel in context:
                        related_terms.add(rel["target"])
                        related_terms.add(rel["source"])

                # Search for memories mentioning related entities
                existing_ids = {r.id for r in results}
                for term in related_terms:
                    search_all = types is None
                    if search_all or MemoryType.SEMANTIC in types:
                        graph_results = await self._semantic.search(
                            term, limit=limit, min_importance=min_importance
                        )
                        for gr in graph_results:
                            if gr.id not in existing_ids:
                                results.append(gr)
                                existing_ids.add(gr.id)
                    if search_all or MemoryType.EPISODIC in types:
                        graph_results = await self._episodic.search(term, limit=limit)
                        for gr in graph_results:
                            if gr.id not in existing_ids:
                                results.append(gr)
                                existing_ids.add(gr.id)

                logger.debug(
                    "Graph augmentation: matched_entities=%d, related_terms=%d",
                    len(matched_entities),
                    len(related_terms),
                )

        # Apply visibility filtering based on requester context
        results = filter_by_visibility(
            results,
            requester_id=requester_id,
            bond_strength=bond_strength,
            bond_threshold=bond_threshold,
        )

        now = datetime.now()

        # Score by ACT-R activation (deterministic — no noise in recall ranking)
        # Uses pluggable strategy for spreading activation if provided (v0.2.2)
        # Uses personality modulation for trait-influenced ranking (v0.3.3)
        results.sort(
            key=lambda e: (
                -compute_activation(
                    e, query, now=now, noise=False,
                    strategy=self._strategy, personality=self._personality,
                )
            ),
        )

        # Progressive disclosure: return primary (full) + overflow (abstract-only)
        if progressive:
            primary = results[:limit]
            overflow_entries = results[limit:limit * 2]
            # Create shallow copies for overflow with abstract content
            summarized_overflow: list[MemoryEntry] = []
            for entry in overflow_entries:
                if entry.abstract:
                    # Copy entry and replace content with abstract
                    summarized = entry.model_copy()
                    summarized.content = summarized.abstract
                    summarized.is_summarized = True
                    summarized_overflow.append(summarized)
                else:
                    # No abstract available — copy to avoid mutating store
                    summarized_overflow.append(entry.model_copy())
            results = primary + summarized_overflow

        # Update access metadata on retrieved entries (strengthens future recall).
        # Cap timestamps to MAX_ACCESS_TIMESTAMPS to prevent unbounded growth.
        for entry in results[:limit]:
            entry.last_accessed = now
            entry.access_count += 1
            entry.access_timestamps.append(now)
            if len(entry.access_timestamps) > MAX_ACCESS_TIMESTAMPS:
                entry.access_timestamps = entry.access_timestamps[-MAX_ACCESS_TIMESTAMPS:]

        if not results:
            logger.debug("Recall found no matches: query_len=%d", len(query))
        if progressive:
            return results  # primary + overflow already sized correctly
        return results[:limit]
