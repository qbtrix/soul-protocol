# dream.py — Offline consolidation engine ("dreaming") for Soul Protocol.
# Updated: 2026-04-09 — Added dry_run mode (preview without mutating), switched
#   _dedup_semantic to soft-delete via superseded_by for audit trail (no more
#   direct _facts dict mutation), added _find_semantic_duplicates helper that
#   both the real dedup and dry-run counter share.
# Updated: 2026-04-06 — Fixed timezone mismatch in _gather_episodes (naive vs aware),
#   fixed cumulative archive count (now reports delta), added TODO for A/N traits.
# Created: 2026-04-06 — Medium-depth implementation: orchestrator + heuristic
#   pattern detection. No new LLM calls beyond existing reflect().
#
# Dream is the offline counterpart to observe() (online). While observe()
# processes interactions one-at-a-time in real-time, dream() reviews
# accumulated episodes in batch to:
#   1. Detect recurring patterns across episodes (topic clusters, procedures)
#   2. Consolidate memory tiers (archive old, dedup, prune stale graph edges)
#   3. Synthesize cross-tier insights (episodes → procedures, entities → evolution)
#
# Inspired by Harrison Chase's three-layer taxonomy for continual learning:
#   - Model layer (weights) — not our concern
#   - Harness layer (scaffolding) — PocketPaw runtime
#   - Context layer (memory) — Soul Protocol ← dream() optimizes this layer
#
# Psychology reference: memory consolidation during sleep (Stickgold & Walker, 2013).
# Episodic replay → semantic extraction → procedural skill formation → pruning.

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from soul_protocol.runtime.memory.search import relevance_score, tokenize

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DreamReport — output of a dream cycle
# ---------------------------------------------------------------------------


@dataclass
class TopicCluster:
    """A group of episodes sharing a common topic/theme."""

    topic: str
    episode_ids: list[str] = field(default_factory=list)
    episode_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    representative_content: str = ""


@dataclass
class DetectedProcedure:
    """A recurring pattern extracted from episodes, ready to become procedural memory."""

    description: str
    source_episode_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    frequency: int = 0


@dataclass
class GraphConsolidation:
    """Results of graph cleanup during dreaming."""

    merged_entities: list[tuple[str, str]] = field(default_factory=list)  # (kept, merged_into)
    pruned_edges: int = 0
    strengthened_edges: list[tuple[str, str, str]] = field(default_factory=list)  # (src, tgt, rel)


@dataclass
class EvolutionInsight:
    """A personality drift suggestion derived from behavioral patterns."""

    trait: str
    direction: str  # "increase" or "decrease"
    evidence: str
    magnitude: float = 0.0  # 0.0-1.0 suggested change


@dataclass
class DreamReport:
    """Complete output of a dream() cycle."""

    dreamed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    episodes_reviewed: int = 0
    # Phase 2: Pattern detection
    topic_clusters: list[TopicCluster] = field(default_factory=list)
    detected_procedures: list[DetectedProcedure] = field(default_factory=list)
    behavioral_trends: list[str] = field(default_factory=list)
    # Phase 3: Consolidation
    archived_count: int = 0
    deduplicated_count: int = 0
    graph_consolidation: GraphConsolidation = field(default_factory=GraphConsolidation)
    # Phase 4: Synthesis
    procedures_created: int = 0
    evolution_insights: list[EvolutionInsight] = field(default_factory=list)
    # Metadata
    duration_ms: int = 0
    # True when the cycle ran in dry-run mode and no destructive mutations
    # were applied. Counters reflect what *would* have happened.
    dry_run: bool = False

    def summary(self) -> str:
        """Human-readable summary of the dream cycle."""
        lines = [
            f"Dream cycle completed at {self.dreamed_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"  Episodes reviewed: {self.episodes_reviewed}",
        ]
        if self.topic_clusters:
            lines.append(f"  Topic clusters found: {len(self.topic_clusters)}")
            for tc in self.topic_clusters[:5]:
                lines.append(f"    - {tc.topic} ({tc.episode_count} episodes)")
        if self.detected_procedures:
            lines.append(f"  Procedures detected: {len(self.detected_procedures)}")
            for dp in self.detected_procedures[:3]:
                lines.append(f"    - {dp.description} (freq={dp.frequency})")
        if self.behavioral_trends:
            lines.append(f"  Behavioral trends: {len(self.behavioral_trends)}")
            for bt in self.behavioral_trends[:3]:
                lines.append(f"    - {bt}")
        if self.archived_count:
            lines.append(f"  Memories archived: {self.archived_count}")
        if self.deduplicated_count:
            lines.append(f"  Duplicates removed: {self.deduplicated_count}")
        gc = self.graph_consolidation
        if gc.merged_entities or gc.pruned_edges:
            lines.append(
                f"  Graph: {len(gc.merged_entities)} entities merged, "
                f"{gc.pruned_edges} edges pruned"
            )
        if self.procedures_created:
            lines.append(f"  Procedures created: {self.procedures_created}")
        if self.evolution_insights:
            lines.append(f"  Evolution insights: {len(self.evolution_insights)}")
            for ei in self.evolution_insights:
                lines.append(f"    - {ei.trait}: {ei.direction} ({ei.evidence})")
        lines.append(f"  Duration: {self.duration_ms}ms")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dreamer — the offline consolidation engine
# ---------------------------------------------------------------------------

# Minimum episodes to form a cluster
_MIN_CLUSTER_SIZE = 3

# Token overlap threshold for considering episodes related
_CLUSTER_THRESHOLD = 0.25

# Minimum frequency to promote a pattern to procedure
_PROCEDURE_MIN_FREQ = 3

# Entity name similarity threshold for merge candidates
_ENTITY_MERGE_THRESHOLD = 0.85


class Dreamer:
    """Offline consolidation engine for Soul memory.

    Operates on a MemoryManager instance, analyzing accumulated episodes
    and performing batch optimization across all memory tiers.

    Usage::

        dreamer = Dreamer(soul._memory)
        report = await dreamer.dream()
    """

    def __init__(
        self,
        memory: MemoryManager,  # noqa: F821
        graph: KnowledgeGraph | None = None,  # noqa: F821
        skills: SkillRegistry | None = None,  # noqa: F821
        evolution: EvolutionManager | None = None,  # noqa: F821
        dna: DNA | None = None,  # noqa: F821
    ) -> None:
        self._memory = memory
        self._graph = graph or memory._graph
        self._skills = skills
        self._evolution = evolution
        self._dna = dna

    async def dream(
        self,
        *,
        since: datetime | None = None,
        archive: bool = True,
        detect_patterns: bool = True,
        consolidate_graph: bool = True,
        synthesize: bool = True,
        dry_run: bool = False,
    ) -> DreamReport:
        """Run a full dream cycle.

        Args:
            since: Only consider episodes after this time. If None, uses all.
            archive: Whether to archive old memories (Phase 3).
            detect_patterns: Whether to detect topic clusters and procedures (Phase 2).
            consolidate_graph: Whether to merge/prune graph entities (Phase 3).
            synthesize: Whether to create procedural memories and evolution insights (Phase 4).
            dry_run: When True, run the full pipeline for its analysis output
                but skip every destructive mutation: no archiving, no
                semantic dedup, no graph consolidation, no new procedural
                memories. The returned DreamReport still shows what *would*
                happen so the caller can preview and then re-run with
                dry_run=False once the plan looks right.

        Returns:
            DreamReport with all findings and actions taken (or the no-op
            result shape when dry_run=True).
        """
        start = datetime.now(UTC)
        report = DreamReport()
        report.dry_run = dry_run

        # Phase 1: Gather (read-only)
        episodes = self._gather_episodes(since=since)
        report.episodes_reviewed = len(episodes)

        if not episodes:
            report.duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
            return report

        # Phase 2: Pattern Detection (read-only)
        if detect_patterns:
            report.topic_clusters = self._detect_topic_clusters(episodes)
            report.detected_procedures = self._detect_procedures(episodes)
            report.behavioral_trends = self._detect_behavioral_trends(episodes)

        # Phase 3: Consolidate (destructive — skip on dry run, only count)
        if archive:
            if dry_run:
                # Report what *would* be archived/deduped without doing it
                report.archived_count = self._count_archivable(episodes)
                report.deduplicated_count = await self._count_semantic_duplicates()
            else:
                report.archived_count = await self._archive_old(episodes)
                report.deduplicated_count = await self._dedup_semantic()

        if consolidate_graph:
            if dry_run:
                report.graph_consolidation = self._preview_graph_consolidation(episodes)
            else:
                report.graph_consolidation = self._consolidate_graph(episodes)

        # Phase 4: Synthesize (destructive — skip on dry run)
        if synthesize:
            if dry_run:
                # Count how many procedures would be created without creating them
                report.procedures_created = len(report.detected_procedures)
            else:
                report.procedures_created = await self._synthesize_procedures(
                    report.detected_procedures
                )
            # Evolution analysis is read-only, run it either way
            report.evolution_insights = self._analyze_evolution(episodes, report.topic_clusters)

        report.duration_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
        logger.info(
            "Dream cycle %scomplete: episodes=%d, clusters=%d, procedures=%d, archived=%d, duration=%dms",
            "(dry run) " if dry_run else "",
            report.episodes_reviewed,
            len(report.topic_clusters),
            report.procedures_created,
            report.archived_count,
            report.duration_ms,
        )
        return report

    # ======================================================================
    # Phase 1: Gather
    # ======================================================================

    def _gather_episodes(self, *, since: datetime | None = None) -> list:
        """Collect episodes for review.

        Returns MemoryEntry objects from the episodic store, optionally
        filtered to only those after `since`.
        """
        all_episodes = self._memory._episodic.entries()
        if since is None:
            return all_episodes

        # Normalize timezone for comparison — the episodic store may use naive
        # datetimes (datetime.now()) or aware ones depending on context. The
        # `since` param may come from MCP (aware, via fromisoformat) or CLI
        # (naive, via click.DateTime). Strip tzinfo from both sides to avoid
        # TypeError on mixed comparison.
        since_naive = since.replace(tzinfo=None) if since.tzinfo is not None else since
        return [
            ep
            for ep in all_episodes
            if (
                ep.created_at.replace(tzinfo=None)
                if ep.created_at.tzinfo is not None
                else ep.created_at
            )
            >= since_naive
        ]

    # ======================================================================
    # Phase 2: Pattern Detection (heuristic, no LLM)
    # ======================================================================

    def _detect_topic_clusters(self, episodes: list) -> list[TopicCluster]:
        """Cluster episodes by shared tokens/topics.

        Uses token overlap to group episodes that discuss the same topics.
        Builds clusters greedily: for each episode, assign it to the
        best-matching existing cluster or create a new one.
        """
        clusters: list[dict] = []  # Each: {tokens, episodes, content_samples}

        for ep in episodes:
            ep_tokens = tokenize(ep.content)
            if not ep_tokens:
                continue

            best_match_idx = -1
            best_overlap = 0.0

            for idx, cluster in enumerate(clusters):
                # Jaccard-ish overlap between episode tokens and cluster tokens
                cluster_tokens = cluster["tokens"]
                if not cluster_tokens:
                    continue
                overlap = len(ep_tokens & cluster_tokens) / len(ep_tokens | cluster_tokens)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match_idx = idx

            if best_overlap >= _CLUSTER_THRESHOLD and best_match_idx >= 0:
                cluster = clusters[best_match_idx]
                cluster["episodes"].append(ep)
                cluster["tokens"] |= ep_tokens
            else:
                clusters.append(
                    {
                        "tokens": set(ep_tokens),
                        "episodes": [ep],
                    }
                )

        # Convert to TopicCluster, filter by minimum size
        result: list[TopicCluster] = []
        for cluster in clusters:
            eps = cluster["episodes"]
            if len(eps) < _MIN_CLUSTER_SIZE:
                continue

            # Pick the most common meaningful tokens as the topic label
            all_tokens: Counter[str] = Counter()
            for ep in eps:
                all_tokens.update(tokenize(ep.content))

            # Top 3 most frequent tokens form the topic name
            top_tokens = [tok for tok, _ in all_tokens.most_common(5)]
            topic_label = " ".join(top_tokens[:3])

            timestamps = [ep.created_at for ep in eps]
            result.append(
                TopicCluster(
                    topic=topic_label,
                    episode_ids=[ep.id for ep in eps],
                    episode_count=len(eps),
                    first_seen=min(timestamps) if timestamps else None,
                    last_seen=max(timestamps) if timestamps else None,
                    representative_content=eps[0].content[:200] if eps else "",
                )
            )

        # Sort by episode count descending
        result.sort(key=lambda tc: -tc.episode_count)
        return result

    def _detect_procedures(self, episodes: list) -> list[DetectedProcedure]:
        """Detect recurring action patterns that could become procedural memories.

        Looks for repeated sequences of actions/decisions across episodes.
        A procedure is detected when the soul encounters similar situations
        and takes similar actions multiple times.
        """
        # Extract action-like phrases from agent outputs
        action_patterns: Counter[str] = Counter()
        action_episodes: defaultdict[str, list[str]] = defaultdict(list)

        for ep in episodes:
            # Split content into user/agent parts
            parts = ep.content.split("\nAgent: ", 1)
            if len(parts) < 2:
                continue
            agent_output = parts[1]

            # Tokenize the agent response into action fragments
            # Look for imperative/procedural phrases
            action_tokens = tokenize(agent_output)
            if len(action_tokens) < 3:
                continue

            # Create a normalized "action signature" from top tokens
            # This groups similar agent responses together
            sorted_tokens = sorted(action_tokens)[:6]  # Top 6 tokens alphabetically
            signature = " ".join(sorted_tokens)

            if signature:
                action_patterns[signature] += 1
                action_episodes[signature].append(ep.id)

        # Promote frequent patterns to detected procedures
        result: list[DetectedProcedure] = []
        for signature, count in action_patterns.most_common(10):
            if count < _PROCEDURE_MIN_FREQ:
                break

            ep_ids = action_episodes[signature]
            # Build a human-readable description from the common tokens
            description = f"Recurring pattern ({count}x): {signature}"

            result.append(
                DetectedProcedure(
                    description=description,
                    source_episode_ids=ep_ids[:10],
                    confidence=min(1.0, count / 10.0),
                    frequency=count,
                )
            )

        return result

    def _detect_behavioral_trends(self, episodes: list) -> list[str]:
        """Detect shifts in topic focus over time.

        Compares the first half of episodes to the second half to see
        if the soul's focus has shifted between topic areas.
        """
        if len(episodes) < 6:
            return []

        # Sort by time
        sorted_eps = sorted(episodes, key=lambda e: e.created_at)
        mid = len(sorted_eps) // 2
        first_half = sorted_eps[:mid]
        second_half = sorted_eps[mid:]

        # Count tokens in each half
        first_tokens: Counter[str] = Counter()
        second_tokens: Counter[str] = Counter()

        for ep in first_half:
            first_tokens.update(tokenize(ep.content))
        for ep in second_half:
            second_tokens.update(tokenize(ep.content))

        trends: list[str] = []

        # Find tokens that grew significantly
        all_tokens = set(first_tokens.keys()) | set(second_tokens.keys())
        for token in all_tokens:
            first_count = first_tokens.get(token, 0)
            second_count = second_tokens.get(token, 0)

            # Normalize by half size
            first_rate = first_count / max(len(first_half), 1)
            second_rate = second_count / max(len(second_half), 1)

            # Significant increase (appeared in >30% of second half but <10% of first)
            if second_rate > 0.3 and first_rate < 0.1:
                trends.append(
                    f"Emerging topic: '{token}' (appeared in {second_count}/{len(second_half)} recent episodes)"
                )

            # Significant decrease
            if first_rate > 0.3 and second_rate < 0.1:
                trends.append(
                    f"Declining topic: '{token}' (dropped from {first_count}/{len(first_half)} to {second_count}/{len(second_half)})"
                )

        # Cap at 10 trends
        return trends[:10]

    # ======================================================================
    # Phase 3: Consolidate
    # ======================================================================

    async def _archive_old(self, episodes: list) -> int:
        """Delegate to MemoryManager's archive mechanism.

        Returns the number of newly archived episodes (delta, not cumulative).
        """
        try:
            before = sum(
                1 for ep in self._memory._episodic.entries() if getattr(ep, "archived", False)
            )
            await self._memory.archive_old_memories()
            after = sum(
                1 for ep in self._memory._episodic.entries() if getattr(ep, "archived", False)
            )
            return max(0, after - before)
        except Exception as e:
            logger.warning("Archive during dream failed: %s", e)
            return 0

    def _find_semantic_duplicates(self) -> list[tuple[str, str]]:
        """Return (loser_id, winner_id) pairs for duplicate semantic facts.

        ``facts()`` is pre-sorted by importance desc, then created_at desc,
        so the first time we see a token-overlap ≥ 0.85 the already-seen
        entry is the more important / newer one — that's the keeper.
        The later occurrence becomes the "loser" and is superseded.
        """
        facts = self._memory._semantic.facts()
        if len(facts) < 2:
            return []

        seen: list[tuple[str, set[str]]] = []
        pairs: list[tuple[str, str]] = []

        for fact in facts:
            if fact.superseded_by is not None:
                continue  # Already marked as superseded

            fact_tokens = tokenize(fact.content)
            is_dup = False

            for existing_id, existing_tokens in seen:
                if not existing_tokens or not fact_tokens:
                    continue
                overlap = len(fact_tokens & existing_tokens) / max(
                    len(fact_tokens | existing_tokens), 1
                )
                if overlap >= 0.85:
                    pairs.append((fact.id, existing_id))
                    is_dup = True
                    break

            if not is_dup:
                seen.append((fact.id, fact_tokens))

        return pairs

    async def _count_semantic_duplicates(self) -> int:
        """Dry-run equivalent of _dedup_semantic. Counts without mutating."""
        return len(self._find_semantic_duplicates())

    async def _dedup_semantic(self) -> int:
        """Supersede duplicate semantic facts using token overlap.

        Uses ``superseded_by`` for a soft-delete audit trail rather than
        hard-deleting the duplicate. The winning fact keeps living; the
        duplicate is marked superseded and will be filtered out of
        future ``facts()`` calls but remains available via
        ``facts(include_superseded=True)`` for inspection.
        """
        pairs = self._find_semantic_duplicates()
        if not pairs:
            return 0

        removed = 0
        for loser_id, winner_id in pairs:
            loser = self._memory._semantic._facts.get(loser_id)
            if loser is None:
                continue
            # Soft-delete via supersede — preserves the entry for audit
            # and ensures any future API change on remove() is honored.
            loser.superseded_by = winner_id
            removed += 1

        if removed:
            logger.debug("Dream dedup: superseded %d duplicate semantic facts", removed)

        return removed

    def _count_archivable(self, episodes: list) -> int:
        """Dry-run equivalent of _archive_old. Counts what would be archived.

        Mirrors MemoryManager.archive_old_memories() exactly so the dry-run
        preview matches what a real run would do:
          - 48-hour age cutoff (matches the default max_age_hours)
          - Excludes already-archived entries
          - Minimum 3 entries or archival is skipped entirely
        If archive_old_memories changes its cutoff or guard logic, this
        method needs to track it. The test
        test_count_archivable_matches_archive_cutoff guards against drift.
        """
        if not episodes:
            return 0

        max_age_hours = 48.0
        now = datetime.now()
        cutoff = now.timestamp() - (max_age_hours * 3600)

        candidates = [
            ep
            for ep in episodes
            if ep.created_at.timestamp() < cutoff and not getattr(ep, "archived", False)
        ]

        # archive_old_memories requires at least 3 entries or it no-ops
        if len(candidates) < 3:
            return 0
        return len(candidates)

    def _preview_graph_consolidation(self, episodes: list) -> GraphConsolidation:
        """Dry-run equivalent of _consolidate_graph. Reports what would change.

        Runs the same similarity logic but does not mutate _graph. The
        returned GraphConsolidation shows planned merges and prunes so the
        caller can preview the outcome before committing.
        """
        result = GraphConsolidation()
        entities = self._graph.entities()
        if len(entities) < 2:
            return result

        normalized: dict[str, list[str]] = defaultdict(list)
        for entity in entities:
            normalized[entity.lower().strip()].append(entity)

        for norm_name, variants in normalized.items():
            if len(variants) <= 1:
                continue
            # Same selection logic as _consolidate_graph: keep the variant
            # with the most edges, record the others as merge candidates.
            edge_counts: dict[str, int] = {}
            for v in variants:
                edge_counts[v] = sum(
                    1 for e in self._graph._edges if e.source == v or e.target == v
                )
            keeper = max(edge_counts, key=lambda k: edge_counts[k])
            for v in variants:
                if v != keeper:
                    result.merged_entities.append((v, keeper))

        return result

    def _consolidate_graph(self, episodes: list) -> GraphConsolidation:
        """Merge similar entities and prune stale edges in the knowledge graph."""
        result = GraphConsolidation()

        entities = self._graph.entities()
        if len(entities) < 2:
            return result

        # --- Merge similar entity names ---
        # e.g., "Python" and "python" or "PocketPaw" and "pocketpaw"
        normalized: dict[str, list[str]] = defaultdict(list)
        for entity in entities:
            normalized[entity.lower().strip()].append(entity)

        for norm_name, variants in normalized.items():
            if len(variants) <= 1:
                continue
            # Keep the variant that appears in most edges
            edge_counts: dict[str, int] = {}
            for v in variants:
                edge_counts[v] = len(self._graph.get_related(v))

            # Sort by edge count desc, then by case (prefer capitalized)
            variants.sort(key=lambda v: (-edge_counts.get(v, 0), v.islower()))
            keeper = variants[0]

            for duplicate in variants[1:]:
                # Move edges from duplicate to keeper
                for edge in list(self._graph._edges):
                    if edge.source == duplicate:
                        edge.source = keeper
                    if edge.target == duplicate:
                        edge.target = keeper

                # Remove duplicate entity
                if duplicate in self._graph._entities:
                    del self._graph._entities[duplicate]

                result.merged_entities.append((duplicate, keeper))

        # --- Prune expired edges ---
        now = datetime.now()
        original_edge_count = len(self._graph._edges)
        # Remove edges that have been expired for over 30 days
        self._graph._edges = [
            edge
            for edge in self._graph._edges
            if edge.valid_to is None or (now - edge.valid_to).days < 30
        ]
        result.pruned_edges = original_edge_count - len(self._graph._edges)

        # --- Deduplicate edges ---
        # Remove exact duplicate edges (same source, target, relation, both active)
        seen_edges: set[tuple[str, str, str]] = set()
        unique_edges = []
        for edge in self._graph._edges:
            key = (edge.source, edge.target, edge.relation)
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(edge)
            else:
                result.pruned_edges += 1
        self._graph._edges = unique_edges

        # --- Track frequently co-occurring entities ---
        entity_cooccurrence: Counter[tuple[str, str]] = Counter()
        for ep in episodes:
            ep_entities = [e for e in ep.entities if e in set(self._graph.entities())]
            for i, e1 in enumerate(ep_entities):
                for e2 in ep_entities[i + 1 :]:
                    pair = tuple(sorted([e1, e2]))
                    entity_cooccurrence[pair] += 1

        for (e1, e2), count in entity_cooccurrence.most_common(20):
            if count >= 3:
                result.strengthened_edges.append((e1, e2, f"co-occurs ({count}x)"))

        return result

    # ======================================================================
    # Phase 4: Synthesize
    # ======================================================================

    async def _synthesize_procedures(self, detected: list[DetectedProcedure]) -> int:
        """Convert detected patterns into procedural memories.

        Only creates procedures that don't already exist in the procedural store.
        """
        from soul_protocol.runtime.types import MemoryEntry, MemoryType

        created = 0
        existing_procedures = self._memory._procedural.entries()

        for proc in detected:
            if proc.confidence < 0.3:
                continue

            # Check if a similar procedure already exists
            is_duplicate = False
            for existing in existing_procedures:
                score = relevance_score(proc.description, existing.content)
                if score >= 0.6:
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            # Create new procedural memory
            entry = MemoryEntry(
                type=MemoryType.PROCEDURAL,
                content=f"[dream] {proc.description}",
                importance=min(8, max(4, int(proc.confidence * 8))),
            )
            await self._memory._procedural.add(entry)
            created += 1
            logger.debug("Dream created procedure: %s", proc.description[:80])

        return created

    def _analyze_evolution(
        self, episodes: list, clusters: list[TopicCluster]
    ) -> list[EvolutionInsight]:
        """Analyze behavioral patterns for personality evolution insights.

        Maps observed behaviors to OCEAN trait dimensions:
        - Openness: variety of topics, novel explorations
        - Conscientiousness: structured responses, planning patterns
        - Extraversion: interaction frequency, social engagement
        - Agreeableness: accommodating patterns, conflict avoidance (TODO)
        - Neuroticism: error handling, anxiety patterns (TODO)
        """
        if len(episodes) < 10:
            return []

        insights: list[EvolutionInsight] = []

        # --- Openness: topic diversity ---
        unique_topics = len(clusters)
        topic_ratio = unique_topics / max(len(episodes), 1)
        if topic_ratio > 0.3:
            insights.append(
                EvolutionInsight(
                    trait="personality.openness",
                    direction="increase",
                    evidence=f"High topic diversity: {unique_topics} distinct clusters across {len(episodes)} episodes",
                    magnitude=min(0.05, topic_ratio * 0.1),
                )
            )
        elif topic_ratio < 0.05 and len(episodes) > 20:
            insights.append(
                EvolutionInsight(
                    trait="personality.openness",
                    direction="decrease",
                    evidence=f"Low topic diversity: only {unique_topics} clusters across {len(episodes)} episodes",
                    magnitude=0.02,
                )
            )

        # --- Conscientiousness: structured/planning keywords ---
        planning_keywords = {
            "plan",
            "step",
            "first",
            "then",
            "next",
            "organize",
            "schedule",
            "review",
            "test",
        }
        planning_count = 0
        for ep in episodes:
            ep_tokens = tokenize(ep.content, min_length=2)
            if ep_tokens & planning_keywords:
                planning_count += 1

        planning_ratio = planning_count / max(len(episodes), 1)
        if planning_ratio > 0.4:
            insights.append(
                EvolutionInsight(
                    trait="personality.conscientiousness",
                    direction="increase",
                    evidence=f"Frequent structured/planning behavior: {planning_count}/{len(episodes)} episodes",
                    magnitude=min(0.05, planning_ratio * 0.08),
                )
            )

        # --- Extraversion: interaction density ---
        if len(episodes) >= 2:
            sorted_eps = sorted(episodes, key=lambda e: e.created_at)
            time_span = (sorted_eps[-1].created_at - sorted_eps[0].created_at).total_seconds()
            if time_span > 0:
                interactions_per_hour = len(episodes) / (time_span / 3600)
                if interactions_per_hour > 10:
                    insights.append(
                        EvolutionInsight(
                            trait="personality.extraversion",
                            direction="increase",
                            evidence=f"High interaction density: {interactions_per_hour:.1f}/hour",
                            magnitude=0.03,
                        )
                    )

        return insights
