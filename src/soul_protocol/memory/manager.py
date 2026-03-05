# memory/manager.py — MemoryManager facade orchestrating all memory subsystems.
# Updated: v0.3.1 — Accept seed_domains param, forward to SelfModelManager.
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

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from soul_protocol.memory.attention import (
    is_significant,
    overall_significance,
)
from soul_protocol.memory.core import CoreMemoryManager
from soul_protocol.memory.episodic import EpisodicStore
from soul_protocol.memory.graph import KnowledgeGraph
from soul_protocol.memory.procedural import ProceduralStore
from soul_protocol.memory.recall import RecallEngine
from soul_protocol.memory.search import relevance_score
from soul_protocol.memory.self_model import SelfModelManager
from soul_protocol.memory.semantic import SemanticStore
from soul_protocol.types import (
    CoreMemory,
    GeneralEvent,
    Interaction,
    MemoryEntry,
    MemorySettings,
    MemoryType,
    ReflectionResult,
)

if TYPE_CHECKING:
    from soul_protocol.cognitive.engine import CognitiveEngine
    from soul_protocol.memory.strategy import SearchStrategy


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
        re.compile(r"i(?:'m| am) (?:building|creating|making) (\w[\w\s]{2,30})", re.IGNORECASE),
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
    # User questions reveal interests/needs
    (
        re.compile(
            r"how (?:do|can|should|would) (?:i|you|we) ([^.!?\n]{3,50})",
            re.IGNORECASE,
        ),
        5,
        "User asked about {0}",
    ),
    # Agent recommendations: "use X for/to/with Y"
    (
        re.compile(
            r"\buse ([\w().\-]+(?:\s[\w().\-]+){0,4})"
            r" (?:for|to|with|when|instead of) ([^.!?\n]{3,30})",
            re.IGNORECASE,
        ),
        5,
        "Recommendation: use {0} for {1}",
    ),
    # Advice: imperative "try/install/run X" at sentence start
    (
        re.compile(
            r"(?:^|[.!?]\s+)(?:try|install|run|check out|look into)"
            r" ([\w().\-]+(?:\s[\w().\-]+){0,3})",
            re.IGNORECASE | re.MULTILINE,
        ),
        5,
        "Advised: {0}",
    ),
    # Comparisons: "X vs Y", "X compared to Y"
    (
        re.compile(
            r"(\w[\w\s]{1,20}?) (?:vs\.?|versus|compared to) (\w[^.!?\n]{1,30})",
            re.IGNORECASE,
        ),
        5,
        "Comparison discussed: {0} vs {1}",
    ),
    # User errors/struggles
    (
        re.compile(
            r"(?:getting|having|seeing|encountering|returns?|got|get)"
            r" ([^.!?\n]{3,30}?) errors?",
            re.IGNORECASE,
        ),
        5,
        "User encountered {0} errors",
    ),
    # User goals: "I want/need to X"
    (
        re.compile(r"i (?:want|need|have) to ([^.!?\n]{3,30})", re.IGNORECASE),
        6,
        "User wants to {0}",
    ),
    # User attempts: "I'm trying to X"
    (
        re.compile(r"i(?:'m| am) trying to ([^.!?\n]{3,30})", re.IGNORECASE),
        6,
        "User is trying to {0}",
    ),
    # User learning: "I'm learning/studying/new to X"
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

# Regex-to-relation mapping for entity relationship inference.
# Each tuple: (compiled_regex, relation_verb)
ENTITY_RELATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"i (?:use|am using|work with)\b", re.IGNORECASE), "uses"),
    (re.compile(r"i(?:'m| am) (?:building|creating|making)\b", re.IGNORECASE), "builds"),
    (re.compile(r"i (?:prefer|like|love)\b", re.IGNORECASE), "prefers"),
    (re.compile(r"i (?:work at|work for)\b", re.IGNORECASE), "works_at"),
    (re.compile(r"i(?:'m| am) (?:learning|studying)\b", re.IGNORECASE), "learns"),
]

# Words that should never be treated as proper-noun entities even when
# capitalised (common sentence starters, pronouns, filler words).
_STOP_WORDS: set[str] = {
    "i",
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "it",
    "its",
    "my",
    "we",
    "our",
    "you",
    "your",
    "he",
    "she",
    "they",
    "this",
    "that",
    "these",
    "those",
    "what",
    "which",
    "who",
    "how",
    "can",
    "could",
    "will",
    "would",
    "should",
    "do",
    "does",
    "did",
    "but",
    "and",
    "or",
    "not",
    "no",
    "yes",
    "so",
    "if",
    "then",
    "also",
    "just",
    "very",
    "really",
    "well",
    "here",
    "there",
    "user",
    "agent",
    "let",
    "me",
    "hi",
    "hello",
    "hey",
    "thanks",
    "thank",
    "please",
    "sure",
    "okay",
    "ok",
}


# v0.2.2 — Precompute fact prefixes for conflict detection.
# Each FACT_PATTERN template like "User lives in {0}" becomes prefix "User lives in".
_FACT_PREFIXES: list[str] = [
    template.split("{")[0].strip() for _, _, template in FACT_PATTERNS if "{" in template
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
    """Facade that orchestrates all memory subsystems.

    Provides a unified API for:
      - Core memory (always-loaded persona + human profile)
      - Episodic memory (interaction history)
      - Semantic memory (extracted facts)
      - Procedural memory (how-to knowledge)
      - Knowledge graph (entity relationships)
      - Cross-store recall (unified search)
      - Self-model (Klein's self-concept)

    v0.2.0: observe() pipeline is psychology-informed:
      sentiment → significance → conditional episodic → facts →
      entities → graph → self-model
    """

    def __init__(
        self,
        core: CoreMemory,
        settings: MemorySettings,
        core_values: list[str] | None = None,
        engine: CognitiveEngine | None = None,
        search_strategy: SearchStrategy | None = None,
        seed_domains: dict[str, list[str]] | None = None,
    ) -> None:
        self._settings = settings
        self._core_values = core_values or []
        self._engine = engine
        self._search_strategy = search_strategy

        # Initialize subsystems
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
        )

        # v0.2.0 — Psychology modules
        self._self_model = SelfModelManager(seed_domains=seed_domains)

        # v0.2.2 — GeneralEvent storage (Conway hierarchy)
        self._general_events: dict[str, GeneralEvent] = {}

        # v0.2.1 — Cognitive processor (LLM or heuristic)
        # Lazy import to avoid circular dependency:
        #   cognitive.engine → memory.attention → memory.__init__ → memory.manager
        from soul_protocol.cognitive.engine import CognitiveProcessor, HeuristicEngine

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
        """Return the current core memory."""
        return self._core_manager.get()

    def set_core(self, persona: str, human: str) -> None:
        """Replace core memory fields."""
        self._core_manager.set(persona=persona, human=human)

    async def edit_core(self, persona: str | None = None, human: str | None = None) -> None:
        """Append to core memory fields (incremental update)."""
        self._core_manager.edit(persona=persona, human=human)

    # ---- Memory operations ----

    async def add(self, entry: MemoryEntry) -> str:
        """Add a memory entry to the appropriate store based on its type.

        Routes the entry to episodic, semantic, or procedural store.
        Returns the memory ID.
        """
        if entry.type == MemoryType.EPISODIC:
            # For direct episodic adds, store the entry in episodic store
            # by creating a minimal Interaction wrapper
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
            # Core memories are handled via set_core/edit_core
            raise ValueError(
                f"Cannot add memory of type {entry.type} via add(). "
                "Use set_core() or edit_core() for core memories."
            )

    async def add_episodic(self, interaction: Interaction) -> str:
        """Add an interaction as an episodic memory.

        This is the primary way to record interactions. Returns memory ID.
        """
        return await self._episodic.add(interaction)

    async def observe(
        self,
        interaction: Interaction,
        core_values: list[str] | None = None,
    ) -> dict:
        """Process an interaction through the psychology-informed pipeline.

        v0.2.0 Pipeline:
          1. Detect sentiment → SomaticMarker
          2. Compute significance → SignificanceScore
          3. If significant: store episodic with somatic marker
          4. Extract semantic facts (always, even if not significant)
          5. Extract entities and update graph
          6. Update self-model from interaction + facts

        Non-significant interactions still get fact extraction (semantic
        memory) but skip episodic storage. This means mundane "hello/hi"
        exchanges don't clutter episodic memory.

        Args:
            interaction: The interaction to process.
            core_values: Override core values for significance scoring.

        Returns:
            Dict with pipeline results (for inspection/testing):
              - somatic: SomaticMarker
              - significance: float
              - is_significant: bool
              - episodic_id: str | None
              - facts: list[MemoryEntry]
              - entities: list[dict]
        """
        values = core_values or self._core_values

        # --- 1. Detect sentiment (via CognitiveProcessor) ---
        somatic = await self._cognitive.detect_sentiment(interaction.user_input)

        # --- 2. Compute significance (via CognitiveProcessor) ---
        recent = self._episodic.recent_contents(n=10)
        sig_score = await self._cognitive.assess_significance(interaction, values, recent)
        sig_value = overall_significance(sig_score)
        significant = is_significant(sig_score)

        # --- 3. Conditional episodic storage (first pass) ---
        episodic_id: str | None = None
        if significant:
            episodic_id = await self._episodic.add_with_psychology(
                interaction,
                somatic=somatic,
                significance=sig_value,
            )

        # --- 4. Extract and store semantic facts (via CognitiveProcessor) ---
        facts = await self._cognitive.extract_facts(interaction, self._semantic.facts())
        # v0.2.2 — Resolve fact conflicts before storing
        await self._resolve_fact_conflicts(facts)
        for fact in facts:
            await self.add(fact)

        # --- 4b. v0.2.3 — Promote to episodic if facts were extracted ---
        # Any interaction that produces extracted facts is worth remembering,
        # even if it didn't pass the initial significance gate.
        if not significant and facts:
            significant = True
            sig_value = max(sig_value, 0.3)
            episodic_id = await self._episodic.add_with_psychology(
                interaction,
                somatic=somatic,
                significance=sig_value,
            )

        # --- 5. Extract entities (via CognitiveProcessor) ---
        entities = await self._cognitive.extract_entities(interaction)

        # --- 6. Update self-model (via CognitiveProcessor) ---
        await self._cognitive.update_self_model(interaction, facts, self._self_model)

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
        """Search across all memory stores for relevant memories.

        Args:
            query: Keyword search string.
            limit: Maximum results.
            types: Filter to specific memory types (None = all).
            min_importance: Minimum importance threshold.

        Returns:
            Ranked list of matching MemoryEntry objects.
        """
        return await self._recall_engine.recall(
            query=query,
            limit=limit,
            types=types,
            min_importance=min_importance,
        )

    async def remove(self, memory_id: str) -> bool:
        """Remove a memory by ID from all stores.

        Tries each store until the memory is found and removed.
        Returns True if the memory was found and removed.
        """
        if await self._episodic.remove(memory_id):
            return True
        if await self._semantic.remove(memory_id):
            return True
        if await self._procedural.remove(memory_id):
            return True
        return False

    # ---- Extraction helpers (MVP placeholders) ----

    def extract_facts(self, interaction: Interaction) -> list[MemoryEntry]:
        """Extract semantic facts from an interaction using heuristic patterns.

        Scans the combined text of user_input and agent_output for
        predefined regex patterns (preferences, identity, tech usage, etc.).
        Each match produces a MemoryEntry of type SEMANTIC.

        Deduplication: if an existing semantic fact has a token-overlap
        score > 0.7 with a newly extracted fact, the new fact is skipped.

        Returns:
            List of MemoryEntry objects ready to be added to the semantic store.
        """
        # Join with period-space to create a sentence boundary between
        # user input and agent output, preventing captures from crossing.
        user = interaction.user_input.rstrip(" .")
        agent = interaction.agent_output.rstrip(" .")
        combined = f"{user}. {agent}" if agent else user
        extracted: list[MemoryEntry] = []
        seen_contents: set[str] = set()

        # Collect existing semantic fact contents for dedup comparison
        existing_facts = [f.content for f in self._semantic.facts()]

        for pattern, importance, template in FACT_PATTERNS:
            for match in pattern.finditer(combined):
                groups = [_clean_captured(g) for g in match.groups()]
                # Skip if any captured group is empty after cleaning
                if not all(groups):
                    continue

                content = template.format(*groups)

                # Skip exact duplicates within this extraction batch
                if content in seen_contents:
                    continue

                # Skip if a sufficiently similar fact already exists
                is_duplicate = any(
                    _token_overlap_score(content, existing) > 0.7 for existing in existing_facts
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
        """Extract named entities from an interaction using heuristics.

        Detection strategies:
          1. Known technology terms matched case-insensitively.
          2. Capitalised words that are NOT at the start of a sentence and
             NOT common stop-words — treated as proper nouns (person/place).

        Each entity dict contains:
          - name (str): the entity surface form
          - type (str): "technology", "person", "project", or "unknown"
          - relation (str | None): inferred verb relation to the user

        Returns:
            List of entity dicts.
        """
        combined = f"{interaction.user_input} {interaction.agent_output}"
        entities: dict[str, dict] = {}  # name_lower -> entity dict

        # --- 1. Known tech terms ---
        words = re.findall(r"[\w][\w\-]*", combined)
        for word in words:
            if word.lower() in KNOWN_TECH and word.lower() not in entities:
                # Preserve original casing from the text
                entities[word.lower()] = {
                    "name": word,
                    "type": "technology",
                    "relation": None,
                }

        # --- 2. Capitalised words not at sentence start ---
        # Split into sentences on . ! ? then inspect each word
        sentences = re.split(r"[.!?]+", combined)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            # Tokenize preserving hyphens
            tokens = re.findall(r"[\w][\w\-]*", sentence)
            # Skip the first token (sentence-start capitalisation is expected)
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
                        "type": "person",  # default guess for proper nouns
                        "relation": None,
                    }

        # --- 3. Infer relationships from surrounding context ---
        for entity_info in entities.values():
            name = entity_info["name"]
            for rel_pattern, relation in ENTITY_RELATIONS:
                # Check if the relation pattern appears near the entity name
                # e.g. "I use Python" or "I'm building PocketPaw"
                context_pat = re.compile(
                    rel_pattern.pattern + r"\s+" + re.escape(name),
                    re.IGNORECASE,
                )
                if context_pat.search(combined):
                    entity_info["relation"] = relation
                    # Upgrade type if we have a "builds" relation
                    if relation == "builds":
                        entity_info["type"] = "project"
                    break

        return list(entities.values())

    # ---- Graph operations ----

    async def update_graph(self, entities: list[dict]) -> None:
        """Update the knowledge graph with extracted entities.

        Each entity dict should have:
          - name (str): entity name
          - entity_type (str, optional): type of entity
          - relationships (list[dict], optional): list of
            {target: str, relation: str} dicts
        """
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

    # ---- Self-model access ----

    @property
    def self_model(self) -> SelfModelManager:
        """Return the self-model manager."""
        return self._self_model

    # ---- Reflection (v0.2.1) ----

    async def reflect(self, soul_name: str = "soul") -> ReflectionResult | None:
        """Run a reflection/consolidation pass over recent episodes.

        LLM-only — returns None in heuristic mode. The soul reviews
        recent interactions, identifies themes, and updates self-understanding.

        Args:
            soul_name: The soul's name (included in reflection prompt).

        Returns:
            ReflectionResult with themes, summaries, and insights, or None.
        """
        return await self._cognitive.reflect(
            recent_episodes=self._episodic.entries()[:20],
            current_self_model=self._self_model.to_dict(),
            soul_name=soul_name,
        )

    # ---- Consolidation (v0.2.2) ----

    async def consolidate(self, result: ReflectionResult, soul_name: str = "soul") -> dict:
        """Apply a ReflectionResult to memory: summaries, themes, self-insight, emotions.

        Called by Soul.reflect(apply=True) to actually consolidate the LLM's
        reflection into persistent memory changes.

        Args:
            result: The ReflectionResult from reflect().
            soul_name: The soul's name (for self-model notes).

        Returns:
            Dict summarizing what was applied:
              - summaries: int (count of semantic memories created)
              - general_events: int (count of GeneralEvents created/updated)
              - self_insight: bool (whether self-model was updated)
              - emotional_pattern: bool (whether pattern was stored)
        """
        applied: dict = {
            "summaries": 0,
            "general_events": 0,
            "self_insight": False,
            "emotional_pattern": False,
        }

        # 1. Summaries → semantic memories
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

        # 2. Themes → GeneralEvents (Conway hierarchy)
        for theme in result.themes:
            if theme:
                await self._create_or_update_general_event(theme)
                applied["general_events"] += 1

        # 3. Self-insight → self-model
        if result.self_insight:
            self._self_model._relationship_notes["self_insight"] = result.self_insight
            applied["self_insight"] = True

        # 4. Emotional patterns → semantic memory
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
        """Create or update a GeneralEvent for a theme and link matching episodes.

        If an event with this theme already exists, it is updated. Otherwise
        a new GeneralEvent is created. Episodes matching the theme (by
        token-overlap > 0.3) are linked via their general_event_id field.

        Args:
            theme: The theme string for the general event.

        Returns:
            The GeneralEvent ID.
        """
        # Find existing event with matching theme, or create new
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

        # Link episodes that match this theme
        for entry in self._episodic.entries():
            if entry.general_event_id:
                continue  # already grouped
            score = relevance_score(theme, entry.content)
            if score > 0.3:
                entry.general_event_id = event.id
                if entry.id not in event.episode_ids:
                    event.episode_ids.append(entry.id)

        event.last_updated = datetime.now()
        return event.id

    # ---- Fact conflict resolution (v0.2.2) ----

    def _find_conflict(
        self, new_content: str, existing_facts: list[MemoryEntry]
    ) -> MemoryEntry | None:
        """Find an existing fact that the new content contradicts.

        Uses template prefix matching: if two facts share the same prefix
        (e.g., "User lives in") but differ in value, they conflict.

        Args:
            new_content: The content of the new fact.
            existing_facts: List of existing semantic facts.

        Returns:
            The conflicting MemoryEntry, or None.
        """
        for prefix in _FACT_PREFIXES:
            if new_content.startswith(prefix):
                for fact in existing_facts:
                    if fact.superseded_by is not None:
                        continue
                    if fact.content.startswith(prefix) and fact.content != new_content:
                        return fact
        return None

    async def _resolve_fact_conflicts(self, new_facts: list[MemoryEntry]) -> list[MemoryEntry]:
        """Detect and resolve conflicting facts before storage.

        Marks old conflicting facts as superseded by the new fact.

        Args:
            new_facts: List of newly extracted facts (not yet stored).

        Returns:
            The same list of new facts (unmodified — conflicts are resolved
            by marking old facts, not by removing new ones).
        """
        existing = self._semantic.facts()
        for fact in new_facts:
            conflict = self._find_conflict(fact.content, existing)
            if conflict:
                conflict.superseded_by = fact.id or "new"
        return new_facts

    # ---- Lifecycle ----

    async def clear(self) -> None:
        """Clear all memory stores and reset the knowledge graph.

        Core memory is preserved — use set_core() to reset it.
        Self-model is preserved across clears.
        """
        self._episodic = EpisodicStore(max_entries=self._settings.episodic_max_entries)
        self._semantic = SemanticStore(max_facts=self._settings.semantic_max_facts)
        self._procedural = ProceduralStore()
        self._graph = KnowledgeGraph()
        self._general_events = {}

        # Rebuild recall engine with new stores
        self._recall_engine = RecallEngine(
            episodic=self._episodic,
            semantic=self._semantic,
            procedural=self._procedural,
            strategy=self._search_strategy,
        )

    @property
    def settings(self) -> MemorySettings:
        """Return the current memory settings."""
        return self._settings

    def count(self) -> int:
        """Total number of stored memories across all stores.

        Counts episodic, semantic, and procedural memories.
        Does not include core memory (which is always exactly one record).
        """
        return (
            len(self._episodic._memories)
            + len(self._semantic._facts)
            + len(self._procedural._procedures)
        )

    # ---- Serialization ----

    def to_dict(self) -> dict:
        """Serialize the entire memory state to a plain dict.

        Includes core memory, all store entries, the knowledge graph,
        the self-model, and general events.
        """
        return {
            "core": self._core_manager.get().model_dump(),
            "episodic": [entry.model_dump(mode="json") for entry in self._episodic.entries()],
            "semantic": [
                fact.model_dump(mode="json")
                for fact in self._semantic.facts(include_superseded=True)
            ],
            "procedural": [proc.model_dump(mode="json") for proc in self._procedural.entries()],
            "graph": self._graph.to_dict(),
            "self_model": self._self_model.to_dict(),
            "general_events": [ge.model_dump(mode="json") for ge in self._general_events.values()],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        settings: MemorySettings,
        core_values: list[str] | None = None,
        engine: CognitiveEngine | None = None,
        search_strategy: SearchStrategy | None = None,
    ) -> MemoryManager:
        """Deserialize memory state from a plain dict.

        Args:
            data: Dict as produced by to_dict().
            settings: MemorySettings to configure the new manager.
            core_values: Core values for significance scoring.
            engine: Optional CognitiveEngine for LLM-enhanced processing.
            search_strategy: Optional SearchStrategy for pluggable retrieval (v0.2.2).

        Returns:
            A fully reconstituted MemoryManager.
        """
        # Restore core memory
        core_data = data.get("core", {})
        core = CoreMemory(**core_data)

        manager = cls(
            core=core,
            settings=settings,
            core_values=core_values,
            engine=engine,
            search_strategy=search_strategy,
        )

        # Restore episodic memories
        for entry_data in data.get("episodic", []):
            entry = MemoryEntry.model_validate(entry_data)
            manager._episodic._memories[entry.id] = entry

        # Restore semantic facts
        for fact_data in data.get("semantic", []):
            fact = MemoryEntry.model_validate(fact_data)
            manager._semantic._facts[fact.id] = fact

        # Restore procedural memories
        for proc_data in data.get("procedural", []):
            proc = MemoryEntry.model_validate(proc_data)
            manager._procedural._procedures[proc.id] = proc

        # Restore knowledge graph
        graph_data = data.get("graph", {})
        if graph_data:
            manager._graph = KnowledgeGraph.from_dict(graph_data)

        # Restore self-model
        self_model_data = data.get("self_model", {})
        if self_model_data:
            manager._self_model = SelfModelManager.from_dict(self_model_data)

        # Restore general events (v0.2.2)
        for ge_data in data.get("general_events", []):
            ge = GeneralEvent.model_validate(ge_data)
            manager._general_events[ge.id] = ge

        return manager
