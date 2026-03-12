# memory/manager.py — MemoryManager facade orchestrating all memory subsystems.
# Updated: phase1-ablation-fixes — Pass token_count to significance gate, weaken
#   promotion rule so trivial interactions with facts don't bypass the gate.
# Updated: feat/dspy-integration — Accept optional dspy_processor param. When set,
#   observe() routes significance assessment through DSPy instead of heuristic gate.
#   This enables the optimized DSPy SignificanceGate to catch facts the heuristic misses.
# Updated: phase1-ablation-fixes — Pass token_count to significance gate, weaken
#   promotion rule so trivial interactions with facts don't bypass the gate.
# Updated: 2026-03-12 — Use UTC timestamps in deletion audit entries; document
#   audit trail persistence gap (TODO #51).
# Updated: 2026-03-10 — Added forget(), forget_entity(), forget_before() for
#   GDPR-compliant memory deletion with cascade logic and audit trail.
# Updated: runtime restructure — fixed absolute import paths to soul_protocol.runtime.
# Updated: 2026-03-06 — Fixed edit_core docstring: edit() replaces values, not appends.
#   v0.3.1 — Accept seed_domains param, forward to SelfModelManager.
#   v0.2.3 — Added count() method for total memory count across all stores.
#   Expanded FACT_PATTERNS with Q&A knowledge extraction:
#   user questions, recommendations, advice, comparisons, user goals/learning.
#   v0.2.2 — Added SearchStrategy support, consolidate() for reflect auto-apply,
#   GeneralEvent storage (Conway hierarchy), fact conflict resolution via supersede.
#   v0.2.1 — Integrated CognitiveProcessor for LLM-enhanced observe().
#   All psychology steps now go through CognitiveProcessor which delegates to
#   either an LLM (CognitiveEngine) or v0.2.0 heuristics (HeuristicEngine).
#   Added reflect() method for LLM-driven memory consolidation.
#   v0.2.0 — Wired psychology-informed observe pipeline:
#   sentiment → significance → conditional episodic → facts → entities →
#   graph → self-model → state.
#   Added SelfModelManager, attention gate, and somatic marker integration.
#   Recall now uses ACT-R activation scoring via updated RecallEngine.
# Updated: Removed PII from debug logs — recall logs query length instead of
#   raw query text, fact conflict resolution logs word count instead of content.

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from soul_protocol.runtime.memory.attention import (
    is_significant,
    overall_significance,
)
from soul_protocol.runtime.memory.core import CoreMemoryManager
from soul_protocol.runtime.memory.episodic import EpisodicStore
from soul_protocol.runtime.memory.graph import KnowledgeGraph
from soul_protocol.runtime.memory.procedural import ProceduralStore
from soul_protocol.runtime.memory.recall import RecallEngine
from soul_protocol.runtime.memory.search import relevance_score, tokenize
from soul_protocol.runtime.memory.self_model import SelfModelManager
from soul_protocol.runtime.memory.semantic import SemanticStore
from soul_protocol.runtime.types import (
    CoreMemory,
    GeneralEvent,
    Interaction,
    MemoryEntry,
    MemorySettings,
    MemoryType,
    Personality,
    ReflectionResult,
)

if TYPE_CHECKING:
    from soul_protocol.runtime.cognitive.engine import CognitiveEngine
    from soul_protocol.runtime.memory.strategy import SearchStrategy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Heuristic fact-extraction patterns
# Each tuple: (compiled_regex, importance_score, template_string)
# Templates use {0}, {1}, ... for captured groups.
# ---------------------------------------------------------------------------

FACT_PATTERNS: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"my name is (\w+)", re.IGNORECASE), 9, "User's name is {0}"),
    (
        re.compile(r"i(?:'m| am) (?:a |an )?(\w[\w\s]{2,30})", re.IGNORECASE),
        7,
        "User is {0}",
    ),
    (
        re.compile(r"i (?:prefer|like|love) (\w[\w\s]{2,30})", re.IGNORECASE),
        7,
        "User prefers {0}",
    ),
    (
        re.compile(r"i (?:hate|dislike|don'?t like) (\w[\w\s]{2,30})", re.IGNORECASE),
        7,
        "User dislikes {0}",
    ),
    (
        re.compile(r"i (?:use|work with|am using) (\w[\w\s]{2,30})", re.IGNORECASE),
        6,
        "User uses {0}",
    ),
    (
        re.compile(
            r"i(?:'m| am) (?:building|creating|making) (\w[\w\s]{2,30})", re.IGNORECASE
        ),
        7,
        "User is building {0}",
    ),
    (
        re.compile(r"i (?:work at|work for) (\w[\w\s]{2,30})", re.IGNORECASE),
        8,
        "User works at {0}",
    ),
    (
        re.compile(r"i(?:'m| am) from (\w[\w\s]{2,30})", re.IGNORECASE),
        7,
        "User is from {0}",
    ),
    (
        re.compile(r"i live in (\w[\w\s]{2,30})", re.IGNORECASE),
        7,
        "User lives in {0}",
    ),
    (
        re.compile(r"my favorite (\w+) is (\w[\w\s]{2,30})", re.IGNORECASE),
        6,
        "User's favorite {0} is {1}",
    ),
    # --- v0.2.3: Q&A knowledge extraction patterns ---
    (
        re.compile(
            r"how (?:do|can|should|would) (?:i|you|we) ([^.!?\n]{3,50})",
            re.IGNORECASE,
        ),
        5,
        "User asked about {0}",
    ),
    (
        re.compile(
            r"\buse ([\w().\-]+(?:\s[\w().\-]+){0,4})"
            r" (?:for|to|with|when|instead of) ([^.!?\n]{3,30})",
            re.IGNORECASE,
        ),
        5,
        "Recommendation: use {0} for {1}",
    ),
    (
        re.compile(
            r"(?:^|[.!?]\s+)(?:try|install|run|check out|look into)"
            r" ([\w().\-]+(?:\s[\w().\-]+){0,3})",
            re.IGNORECASE | re.MULTILINE,
        ),
        5,
        "Advised: {0}",
    ),
    (
        re.compile(
            r"(\w[\w\s]{1,20}?) (?:vs\.?|versus|compared to) (\w[^.!?\n]{1,30})",
            re.IGNORECASE,
        ),
        5,
        "Comparison discussed: {0} vs {1}",
    ),
    (
        re.compile(
            r"(?:getting|having|seeing|encountering|returns?|got|get)"
            r" ([^.!?\n]{3,30}?) errors?",
            re.IGNORECASE,
        ),
        5,
        "User encountered {0} errors",
    ),
    (
        re.compile(r"i (?:want|need|have) to ([^.!?\n]{3,30})", re.IGNORECASE),
        6,
        "User wants to {0}",
    ),
    (
        re.compile(r"i(?:'m| am) trying to ([^.!?\n]{3,30})", re.IGNORECASE),
        6,
        "User is trying to {0}",
    ),
    (
        re.compile(
            r"i(?:'m| am) (?:learning|studying|new to) (\w[^.!?\n]{2,30})",
            re.IGNORECASE,
        ),
        6,
        "User is learning {0}",
    ),
]

# ---------------------------------------------------------------------------
# Known technology names (lowercase) for entity extraction
# ---------------------------------------------------------------------------

KNOWN_TECH: set[str] = {
    "python",
    "javascript",
    "typescript",
    "rust",
    "go",
    "java",
    "ruby",
    "swift",
    "react",
    "vue",
    "angular",
    "django",
    "flask",
    "fastapi",
    "express",
    "nextjs",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "firebase",
    "supabase",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "sqlite",
    "git",
    "github",
    "gitlab",
    "vscode",
    "neovim",
    "vim",
    "linux",
    "macos",
    "windows",
    "ubuntu",
    "openai",
    "anthropic",
    "claude",
    "gpt",
    "gemini",
    "ollama",
    "langchain",
    "pocketpaw",
    "soul-protocol",
}

ENTITY_RELATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"i (?:use|am using|work with)\b", re.IGNORECASE), "uses"),
    (
        re.compile(r"i(?:'m| am) (?:building|creating|making)\b", re.IGNORECASE),
        "builds",
    ),
    (re.compile(r"i (?:prefer|like|love)\b", re.IGNORECASE), "prefers"),
    (re.compile(r"i (?:work at|work for)\b", re.IGNORECASE), "works_at"),
    (re.compile(r"i(?:'m| am) (?:learning|studying)\b", re.IGNORECASE), "learns"),
]

_STOP_WORDS: set[str] = {
    "i", "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "it", "its", "my", "we", "our", "you", "your", "he", "she", "they",
    "this", "that", "these", "those", "what", "which", "who", "how",
    "can", "could", "will", "would", "should", "do", "does", "did",
    "but", "and", "or", "not", "no", "yes", "so", "if", "then",
    "also", "just", "very", "really", "well", "here", "there",
    "user", "agent", "let", "me", "hi", "hello", "hey",
    "thanks", "thank", "please", "sure", "okay", "ok",
}


_FACT_PREFIXES: list[str] = [
    template.split("{")[0].strip()
    for _, _, template in FACT_PATTERNS
    if "{" in template
]


def _clean_captured(text: str) -> str:
    """Strip whitespace and trailing punctuation from a regex capture."""
    return text.strip().rstrip(".,;:!?")


def _token_overlap_score(a: str, b: str) -> float:
    """Return Jaccard token-overlap score between two strings (0.0-1.0)."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


class MemoryManager:
    """Facade that orchestrates all memory subsystems."""

    def __init__(
        self,
        core: CoreMemory,
        settings: MemorySettings,
        core_values: list[str] | None = None,
        engine: CognitiveEngine | None = None,
        search_strategy: SearchStrategy | None = None,
        seed_domains: dict[str, list[str]] | None = None,
        dspy_processor: object | None = None,
        personality: Personality | None = None,
    ) -> None:
        self._settings = settings
        self._core_values = core_values or []
        self._engine = engine
        self._search_strategy = search_strategy
        self._dspy_processor = dspy_processor
        self._personality = personality

        self._core_manager = CoreMemoryManager(core)
        self._episodic = EpisodicStore(max_entries=settings.episodic_max_entries)
        self._semantic = SemanticStore(max_facts=settings.semantic_max_facts)
        self._procedural = ProceduralStore()
        self._graph = KnowledgeGraph()
        self._recall_engine = RecallEngine(
            episodic=self._episodic,
            semantic=self._semantic,
            procedural=self._procedural,
            strategy=search_strategy,
            personality=personality,
        )

        self._self_model = SelfModelManager(seed_domains=seed_domains)
        self._general_events: dict[str, GeneralEvent] = {}

        # v0.3.0 — GDPR deletion audit trail
        # TODO(#51): Persist audit trail through .soul pack/unpack cycle for GDPR compliance
        self._deletion_audit: list[dict] = []

        # v0.2.1 — Cognitive processor (LLM or heuristic)
        # Lazy import to avoid circular dependency:
        #   cognitive.engine → memory.attention → memory.__init__ → memory.manager
        from soul_protocol.runtime.cognitive.engine import CognitiveProcessor, HeuristicEngine
        from soul_protocol.runtime.cognitive.engine import (
            CognitiveProcessor,
            HeuristicEngine,
        )

        heuristic = HeuristicEngine()
        if engine is not None:
            self._cognitive = CognitiveProcessor(
                engine,
                fallback=heuristic,
                fact_extractor=self.extract_facts,
                entity_extractor=self.extract_entities,
            )
        else:
            self._cognitive = CognitiveProcessor(
                heuristic,
                fact_extractor=self.extract_facts,
                entity_extractor=self.extract_entities,
            )

    # ---- Core memory ----

    def get_core(self) -> CoreMemory:
        return self._core_manager.get()

    def set_core(self, persona: str, human: str) -> None:
        self._core_manager.set(persona=persona, human=human)

    async def edit_core(
        self, persona: str | None = None, human: str | None = None
    ) -> None:
        """Replace core memory fields (provided values overwrite existing)."""
        self._core_manager.edit(persona=persona, human=human)

    # ---- Memory operations ----

    async def add(self, entry: MemoryEntry) -> str:
        if entry.type == MemoryType.EPISODIC:
            interaction = Interaction(
                user_input=entry.content,
                agent_output="",
                timestamp=entry.created_at,
            )
            return await self._episodic.add(interaction)
        elif entry.type == MemoryType.SEMANTIC:
            return await self._semantic.add(entry)
        elif entry.type == MemoryType.PROCEDURAL:
            return await self._procedural.add(entry)
        else:
            raise ValueError(
                f"Cannot add memory of type {entry.type} via add(). "
                "Use set_core() or edit_core() for core memories."
            )

    async def add_episodic(self, interaction: Interaction) -> str:
        return await self._episodic.add(interaction)

    async def observe(
        self,
        interaction: Interaction,
        core_values: list[str] | None = None,
    ) -> dict:
        """Process an interaction through the psychology-informed pipeline."""
        values = core_values or self._core_values

        # --- 1. Detect sentiment ---
        somatic = await self._cognitive.detect_sentiment(interaction.user_input)
        logger.debug(
            "Sentiment detected: valence=%.3f, arousal=%.3f, label=%s",
            somatic.valence,
            somatic.arousal,
            somatic.label,
        )

        # --- 2. Compute significance ---
        # Use DSPy significance gate if available (LLM-powered, optimizable),
        # otherwise fall back to heuristic via CognitiveProcessor.
        recent = self._episodic.recent_contents(n=10)
        sig_score = await self._cognitive.assess_significance(interaction, values, recent)
        if self._dspy_processor is not None:
            sig_score = await self._dspy_processor.assess_significance(
                interaction, values, recent
            )
        else:
            sig_score = await self._cognitive.assess_significance(interaction, values, recent)
        combined_text = f"{interaction.user_input} {interaction.agent_output}"
        token_count = len(tokenize(combined_text))
        sig_value = overall_significance(sig_score, token_count=token_count)
        significant = is_significant(sig_score, token_count=token_count)
        recent = self._episodic.recent_contents(n=10)
        sig_score = await self._cognitive.assess_significance(
            interaction, values, recent
        )
        sig_value = overall_significance(sig_score)
        significant = is_significant(sig_score)
        logger.debug(
            "Significance assessed: score=%.3f, significant=%s", sig_value, significant
        )

        # --- 3. Conditional episodic storage ---
        episodic_id: str | None = None
        if significant:
            episodic_id = await self._episodic.add_with_psychology(
                interaction,
                somatic=somatic,
                significance=sig_value,
            )
            logger.debug("Episodic memory stored: id=%s", episodic_id)

        # --- 4. Extract and store semantic facts ---
        facts = await self._cognitive.extract_facts(
            interaction, self._semantic.facts()
        )
        await self._resolve_fact_conflicts(facts)
        for fact in facts:
            await self.add(fact)
        if facts:
            logger.debug("Facts extracted and stored: count=%d", len(facts))

        # --- 4b. v0.2.3 — Conditionally promote if facts were extracted ---
        # Only promote to episodic when significance is at least half the
        # threshold (0.25) AND facts were extracted.  This prevents trivial
        # interactions from being promoted just because a fact was found.
        if not significant and facts and sig_value >= 0.3:
        # --- 4b. Promote to episodic if facts were extracted ---
        if not significant and facts:
            significant = True
            episodic_id = await self._episodic.add_with_psychology(
                interaction,
                somatic=somatic,
                significance=sig_value,
            )
            logger.debug(
                "Promoted to episodic (facts found): id=%s, sig=%.3f",
                episodic_id,
                sig_value,
            )

        # --- 5. Extract entities ---
        entities = await self._cognitive.extract_entities(interaction)
        if entities:
            logger.debug(
                "Entities extracted: %s",
                [e.get("name") for e in entities],
            )

        # --- 6. Update self-model ---
        await self._cognitive.update_self_model(interaction, facts, self._self_model)
        logger.debug("Self-model updated")

        return {
            "somatic": somatic,
            "significance": sig_value,
            "is_significant": significant,
            "episodic_id": episodic_id,
            "facts": facts,
            "entities": entities,
        }

    async def recall(
        self,
        query: str,
        limit: int = 10,
        types: list[MemoryType] | None = None,
        min_importance: int = 0,
    ) -> list[MemoryEntry]:
        results = await self._recall_engine.recall(
            query=query,
            limit=limit,
            types=types,
            min_importance=min_importance,
        )
        logger.debug("Recall query_len=%d returned %d results", len(query), len(results))
        return results

    async def remove(self, memory_id: str) -> bool:
        if await self._episodic.remove(memory_id):
            return True
        if await self._semantic.remove(memory_id):
            return True
        if await self._procedural.remove(memory_id):
            return True
        return False

    # ---- GDPR-compliant deletion (v0.3.0) ----

    async def forget(self, query: str) -> dict:
        """Search all memory tiers for matches and delete them.

        Performs a cascading deletion: when episodic memories are deleted,
        any derived semantic facts that overlap with the deleted content
        are also removed.

        Args:
            query: Search query to match against memory content.

        Returns:
            Dict with deletion results:
              - episodic: list of deleted episodic memory IDs
              - semantic: list of deleted semantic fact IDs
              - procedural: list of deleted procedural memory IDs
              - total: total count of deleted memories
        """
        # Search and delete from each tier
        episodic_ids = await self._episodic.search_and_delete(query)
        semantic_ids = await self._semantic.search_and_delete(query)
        procedural_ids = await self._procedural.search_and_delete(query)

        total = len(episodic_ids) + len(semantic_ids) + len(procedural_ids)

        # Record audit entry (no deleted content stored)
        if total > 0:
            self._deletion_audit.append(
                {
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                    "count": total,
                    "reason": f"forget(query='{query}')",
                    "tiers": {
                        "episodic": len(episodic_ids),
                        "semantic": len(semantic_ids),
                        "procedural": len(procedural_ids),
                    },
                }
            )

        return {
            "episodic": episodic_ids,
            "semantic": semantic_ids,
            "procedural": procedural_ids,
            "total": total,
        }

    async def forget_entity(self, entity: str) -> dict:
        """Remove an entity from the knowledge graph and related memories.

        Deletes the entity node and all connected edges from the graph,
        then searches all memory tiers for content mentioning the entity
        and removes those memories too.

        Args:
            entity: The entity name to forget.

        Returns:
            Dict with deletion results:
              - edges_removed: number of graph edges removed
              - episodic: list of deleted episodic memory IDs
              - semantic: list of deleted semantic fact IDs
              - procedural: list of deleted procedural memory IDs
              - total: total count of deleted memories + edges
        """
        # Remove from knowledge graph
        edges_removed = self._graph.remove_entity(entity)

        # Remove related memories from all tiers
        episodic_ids = await self._episodic.search_and_delete(entity)
        semantic_ids = await self._semantic.search_and_delete(entity)
        procedural_ids = await self._procedural.search_and_delete(entity)

        total = edges_removed + len(episodic_ids) + len(semantic_ids) + len(procedural_ids)

        # Record audit entry
        if total > 0:
            self._deletion_audit.append(
                {
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                    "count": total,
                    "reason": f"forget_entity(entity='{entity}')",
                    "tiers": {
                        "graph_edges": edges_removed,
                        "episodic": len(episodic_ids),
                        "semantic": len(semantic_ids),
                        "procedural": len(procedural_ids),
                    },
                }
            )

        return {
            "edges_removed": edges_removed,
            "episodic": episodic_ids,
            "semantic": semantic_ids,
            "procedural": procedural_ids,
            "total": total,
        }

    async def forget_before(self, timestamp: datetime) -> dict:
        """Bulk delete memories older than a given timestamp.

        Removes memories from all tiers that were created before the
        specified timestamp.

        Args:
            timestamp: The cutoff datetime. Memories older than this
                       are deleted.

        Returns:
            Dict with deletion results:
              - episodic: list of deleted episodic memory IDs
              - semantic: list of deleted semantic fact IDs
              - procedural: list of deleted procedural memory IDs
              - total: total count of deleted memories
        """
        episodic_ids = await self._episodic.delete_before(timestamp)
        semantic_ids = await self._semantic.delete_before(timestamp)
        procedural_ids = await self._procedural.delete_before(timestamp)

        total = len(episodic_ids) + len(semantic_ids) + len(procedural_ids)

        # Record audit entry
        if total > 0:
            self._deletion_audit.append(
                {
                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                    "count": total,
                    "reason": f"forget_before(timestamp='{timestamp.isoformat()}')",
                    "tiers": {
                        "episodic": len(episodic_ids),
                        "semantic": len(semantic_ids),
                        "procedural": len(procedural_ids),
                    },
                }
            )

        return {
            "episodic": episodic_ids,
            "semantic": semantic_ids,
            "procedural": procedural_ids,
            "total": total,
        }

    @property
    def deletion_audit(self) -> list[dict]:
        """Return the deletion audit trail.

        Each entry contains:
          - deleted_at: ISO timestamp of the deletion
          - count: number of items deleted
          - reason: description of the deletion operation
          - tiers: breakdown by memory tier

        The audit trail intentionally does NOT contain deleted content.
        """
        return list(self._deletion_audit)

    # ---- Extraction helpers (MVP placeholders) ----
    # ---- Extraction helpers ----

    def extract_facts(self, interaction: Interaction) -> list[MemoryEntry]:
        """Extract semantic facts from an interaction using heuristic patterns."""
        user = interaction.user_input.rstrip(" .")
        agent = interaction.agent_output.rstrip(" .")
        combined = f"{user}. {agent}" if agent else user
        extracted: list[MemoryEntry] = []
        seen_contents: set[str] = set()

        existing_facts = [f.content for f in self._semantic.facts()]

        for pattern, importance, template in FACT_PATTERNS:
            for match in pattern.finditer(combined):
                groups = [_clean_captured(g) for g in match.groups()]
                if not all(groups):
                    continue

                content = template.format(*groups)

                if content in seen_contents:
                    continue

                is_duplicate = any(
                    _token_overlap_score(content, existing) > 0.7
                    for existing in existing_facts
                )
                if is_duplicate:
                    continue

                seen_contents.add(content)
                extracted.append(
                    MemoryEntry(
                        type=MemoryType.SEMANTIC,
                        content=content,
                        importance=importance,
                    )
                )

        return extracted

    def extract_entities(self, interaction: Interaction) -> list[dict]:
        """Extract named entities from an interaction using heuristics."""
        combined = f"{interaction.user_input} {interaction.agent_output}"
        entities: dict[str, dict] = {}

        words = re.findall(r"[\w][\w\-]*", combined)
        for word in words:
            if word.lower() in KNOWN_TECH and word.lower() not in entities:
                entities[word.lower()] = {
                    "name": word,
                    "type": "technology",
                    "relation": None,
                }

        sentences = re.split(r"[.!?]+", combined)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            tokens = re.findall(r"[\w][\w\-]*", sentence)
            for token in tokens[1:]:
                if (
                    token[0].isupper()
                    and token.lower() not in _STOP_WORDS
                    and token.lower() not in KNOWN_TECH
                    and token.lower() not in entities
                    and len(token) >= 2
                ):
                    entities[token.lower()] = {
                        "name": token,
                        "type": "person",
                        "relation": None,
                    }

        for entity_info in entities.values():
            name = entity_info["name"]
            for rel_pattern, relation in ENTITY_RELATIONS:
                context_pat = re.compile(
                    rel_pattern.pattern + r"\s+" + re.escape(name),
                    re.IGNORECASE,
                )
                if context_pat.search(combined):
                    entity_info["relation"] = relation
                    if relation == "builds":
                        entity_info["type"] = "project"
                    break

        return list(entities.values())

    # ---- Graph operations ----

    async def update_graph(self, entities: list[dict]) -> None:
        for entity in entities:
            name = entity.get("name", "")
            if not name:
                continue
            entity_type = entity.get("entity_type", "unknown")
            self._graph.add_entity(name, entity_type)

            for rel in entity.get("relationships", []):
                target = rel.get("target", "")
                relation = rel.get("relation", "related_to")
                if target:
                    self._graph.add_relationship(name, target, relation)

    @property
    def self_model(self) -> SelfModelManager:
        return self._self_model

    # ---- Reflection ----

    async def reflect(self, soul_name: str = "soul") -> ReflectionResult | None:
        return await self._cognitive.reflect(
            recent_episodes=self._episodic.entries()[:20],
            current_self_model=self._self_model.to_dict(),
            soul_name=soul_name,
        )

    # ---- Consolidation ----

    async def consolidate(
        self, result: ReflectionResult, soul_name: str = "soul"
    ) -> dict:
        applied: dict = {
            "summaries": 0,
            "general_events": 0,
            "self_insight": False,
            "emotional_pattern": False,
        }

        for summary in result.summaries:
            content = summary.get("summary", "")
            if content:
                importance = min(10, max(1, int(summary.get("importance", 5))))
                await self.add(
                    MemoryEntry(
                        type=MemoryType.SEMANTIC,
                        content=content,
                        importance=importance,
                    )
                )
                applied["summaries"] += 1

        for theme in result.themes:
            if theme:
                await self._create_or_update_general_event(theme)
                applied["general_events"] += 1

        if result.self_insight:
            self._self_model._relationship_notes["self_insight"] = (
                result.self_insight
            )
            applied["self_insight"] = True

        if result.emotional_patterns:
            await self.add(
                MemoryEntry(
                    type=MemoryType.SEMANTIC,
                    content=f"Emotional pattern: {result.emotional_patterns}",
                    importance=6,
                )
            )
            applied["emotional_pattern"] = True

        return applied

    async def _create_or_update_general_event(self, theme: str) -> str:
        existing = next(
            (ge for ge in self._general_events.values() if ge.theme == theme),
            None,
        )

        if existing:
            event = existing
        else:
            event_id = uuid.uuid4().hex[:12]
            event = GeneralEvent(
                id=event_id,
                theme=theme,
                started_at=datetime.now(),
                last_updated=datetime.now(),
            )
            self._general_events[event_id] = event

        for entry in self._episodic.entries():
            if entry.general_event_id:
                continue
            score = relevance_score(theme, entry.content)
            if score > 0.3:
                entry.general_event_id = event.id
                if entry.id not in event.episode_ids:
                    event.episode_ids.append(entry.id)

        event.last_updated = datetime.now()
        return event.id

    # ---- Fact conflict resolution ----

    def _find_conflict(
        self, new_content: str, existing_facts: list[MemoryEntry]
    ) -> MemoryEntry | None:
        for prefix in _FACT_PREFIXES:
            if new_content.startswith(prefix):
                for fact in existing_facts:
                    if fact.superseded_by is not None:
                        continue
                    if (
                        fact.content.startswith(prefix)
                        and fact.content != new_content
                    ):
                        return fact
        return None

    async def _resolve_fact_conflicts(
        self, new_facts: list[MemoryEntry]
    ) -> list[MemoryEntry]:
        existing = self._semantic.facts()
        for fact in new_facts:
            conflict = self._find_conflict(fact.content, existing)
            if conflict:
                conflict.superseded_by = fact.id or "new"
                logger.debug(
                    "Fact conflict resolved: old_len=%d superseded by new_len=%d",
                    len(conflict.content),
                    len(fact.content),
                )
        return new_facts

    # ---- Lifecycle ----

    async def clear(self) -> None:
        self._episodic = EpisodicStore(
            max_entries=self._settings.episodic_max_entries
        )
        self._semantic = SemanticStore(max_facts=self._settings.semantic_max_facts)
        self._procedural = ProceduralStore()
        self._graph = KnowledgeGraph()
        self._general_events = {}

        self._recall_engine = RecallEngine(
            episodic=self._episodic,
            semantic=self._semantic,
            procedural=self._procedural,
            strategy=self._search_strategy,
            personality=self._personality,
        )
        logger.debug("Memory stores cleared")

    @property
    def settings(self) -> MemorySettings:
        return self._settings

    def count(self) -> int:
        return (
            len(self._episodic._memories)
            + len(self._semantic._facts)
            + len(self._procedural._procedures)
        )

    # ---- Serialization ----

    def to_dict(self) -> dict:
        return {
            "core": self._core_manager.get().model_dump(),
            "episodic": [
                entry.model_dump(mode="json") for entry in self._episodic.entries()
            ],
            "semantic": [
                fact.model_dump(mode="json")
                for fact in self._semantic.facts(include_superseded=True)
            ],
            "procedural": [
                proc.model_dump(mode="json") for proc in self._procedural.entries()
            ],
            "graph": self._graph.to_dict(),
            "self_model": self._self_model.to_dict(),
            "general_events": [
                ge.model_dump(mode="json") for ge in self._general_events.values()
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        settings: MemorySettings,
        core_values: list[str] | None = None,
        engine: CognitiveEngine | None = None,
        search_strategy: SearchStrategy | None = None,
        personality: Personality | None = None,
    ) -> MemoryManager:
        """Deserialize memory state from a plain dict.

        Args:
            data: Dict as produced by to_dict().
            settings: MemorySettings to configure the new manager.
            core_values: Core values for significance scoring.
            engine: Optional CognitiveEngine for LLM-enhanced processing.
            search_strategy: Optional SearchStrategy for pluggable retrieval (v0.2.2).
            personality: Optional OCEAN personality for trait-modulated recall (v0.3.3).

        Returns:
            A fully reconstituted MemoryManager.
        """
        core_data = data.get("core", {})
        core = CoreMemory(**core_data)

        manager = cls(
            core=core,
            settings=settings,
            core_values=core_values,
            engine=engine,
            search_strategy=search_strategy,
            personality=personality,
        )

        for entry_data in data.get("episodic", []):
            entry = MemoryEntry.model_validate(entry_data)
            manager._episodic._memories[entry.id] = entry

        for fact_data in data.get("semantic", []):
            fact = MemoryEntry.model_validate(fact_data)
            manager._semantic._facts[fact.id] = fact

        for proc_data in data.get("procedural", []):
            proc = MemoryEntry.model_validate(proc_data)
            manager._procedural._procedures[proc.id] = proc

        graph_data = data.get("graph", {})
        if graph_data:
            manager._graph = KnowledgeGraph.from_dict(graph_data)

        self_model_data = data.get("self_model", {})
        if self_model_data:
            manager._self_model = SelfModelManager.from_dict(self_model_data)

        for ge_data in data.get("general_events", []):
            ge = GeneralEvent.model_validate(ge_data)
            manager._general_events[ge.id] = ge

        logger.debug(
            "MemoryManager restored: episodic=%d, semantic=%d, procedural=%d",
            len(manager._episodic._memories),
            len(manager._semantic._facts),
            len(manager._procedural._procedures),
        )
        return manager
