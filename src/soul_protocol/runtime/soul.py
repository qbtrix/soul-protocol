# soul.py — The main Soul class: birth, awaken, observe, save, export
# Updated: feat/dspy-integration — Wired DSPy processor into observe() pipeline.
#   _dspy_processor is now initialized BEFORE MemoryManager and passed to it,
#   so MemoryManager.observe() uses DSPy significance gate when available.
#   Previously, _dspy_processor was stored on Soul but never used during observe.
# Updated: 2026-03-10 — Added forget(), forget_entity(), forget_before() for
#   GDPR-compliant memory deletion. Renamed old forget(memory_id) to forget_by_id().
# Updated: feat/soul-encryption — Re-raise SoulDecryptionError without wrapping
#   alongside SoulEncryptedError in awaken() exception handling.
# Updated: feat/soul-encryption — Added password parameter to awaken() and export()
#   for encrypted .soul file support.
# Updated: Wired Bond.strengthen() and SkillRegistry into observe() pipeline.
# Updated: Added reincarnate() classmethod for lifecycle rebirth.
#   Preserves memories, personality, and tracks incarnation lineage.
# Updated: v0.3.2 — Added proper error handling for awaken(), export(), retire().
#   Custom exceptions: SoulFileNotFoundError, SoulCorruptError, SoulExportError,
#   SoulRetireError. retire() now fails before lifecycle change if save fails.
# Updated: v0.3.1 — Wired seed_domains through Soul.__init__() → MemoryManager
#   → SelfModelManager. Custom seed domains now replace default bootstrapping.
# Updated: v0.3.0 — Expanded birth() with ocean, communication, biorhythms,
#   persona, and seed_domains parameters for flexible soul configuration at
#   creation time. Added birth_from_config() classmethod. awaken() supports
#   directory paths (.soul/ folders). Added save_local().
#   v0.2.3 — Added system_prompt property alias and memory_count property
#   for paw integration convenience.
#   v0.2.2 — Accept optional SearchStrategy for pluggable retrieval.
#   reflect(apply=True) auto-applies consolidation. Added general_events property.
#   v0.2.1 — Accept optional CognitiveEngine for LLM-enhanced cognition.
#   Added reflect() method for LLM-driven memory consolidation.
#   birth() and awaken() pass engine to MemoryManager.
#   v0.2.0 — Psychology-informed observe() pipeline. Added self_model
#   property for API access. to_system_prompt() includes self-model insights.
#   MemoryManager.observe() now handles sentiment, significance gating,
#   and self-model updates internally. Soul.observe() delegates to it and
#   handles entity graph + state updates.
# Updated: Added structured logging (stdlib) for lifecycle events (birth,
#   awaken, reincarnate, export, retire), observe pipeline completion,
#   persistence operations, and evolution. INFO for lifecycle, DEBUG for
#   pipeline internals, WARNING for degraded paths, ERROR for failures.
# Updated: Removed PII from debug logs — observe() now logs input length
#   instead of raw user input. Recall logs query length, not query text.

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any

from .bond import Bond
from .cognitive.engine import CognitiveEngine
from .dna.prompt import dna_to_system_prompt
from .evolution.manager import EvolutionManager
from .export.pack import pack_soul
from .export.unpack import unpack_soul
from .identity.did import generate_did
from .memory.manager import MemoryManager
from .memory.strategy import SearchStrategy
from .skills import SkillRegistry
from .state.manager import StateManager
from .types import (
    DNA,
    Biorhythms,
    CommunicationStyle,
    CoreMemory,
    GeneralEvent,
    Identity,
    Interaction,
    LifecycleState,
    MemoryEntry,
    MemoryType,
    Mutation,
    Personality,
    ReflectionResult,
    SoulConfig,
    SoulState,
)

logger = logging.getLogger(__name__)


class Soul:
    """A Digital Soul — persistent identity, memory, and state for an AI agent."""

    def __init__(
        self,
        config: SoulConfig,
        engine: CognitiveEngine | None = None,
        search_strategy: SearchStrategy | None = None,
        seed_domains: dict[str, list[str]] | None = None,
        use_dspy: bool = False,
        dspy_model: str | None = None,
        dspy_optimized_path: str | None = None,
    ) -> None:
        self._config = config
        self._identity = config.identity
        self._dna = config.dna
        self._lifecycle = config.lifecycle
        self._engine = engine
        self._search_strategy = search_strategy

        # Optional DSPy-optimized cognitive processor
        self._dspy_processor = None
        if use_dspy:
            try:
                from soul_protocol.runtime.cognitive.dspy_adapter import DSPyCognitiveProcessor

                model = dspy_model or "anthropic/claude-haiku-4-5-20251001"
                self._dspy_processor = DSPyCognitiveProcessor(
                    lm_model=model,
                    optimized_path=dspy_optimized_path,
                )
            except ImportError:
                # dspy not installed — silently fall back to heuristic
                pass

        self._memory = MemoryManager(
            core=config.core_memory,
            settings=config.memory,
            core_values=config.identity.core_values,
            engine=engine,
            search_strategy=search_strategy,
            seed_domains=seed_domains,
            dspy_processor=self._dspy_processor,
        )
        self._state = StateManager(config.state)
        self._evolution = EvolutionManager(config.evolution)
        self._skills = SkillRegistry()

    # ============ Lifecycle ============

    @classmethod
    async def birth(
        cls,
        name: str,
        archetype: str = "",
        personality: str = "",
        values: list[str] | None = None,
        communication_style: str | None = None,
        bonded_to: str | None = None,
        engine: CognitiveEngine | None = None,
        search_strategy: SearchStrategy | None = None,
        # v0.3.0 — Flexible configuration parameters
        ocean: dict[str, float] | None = None,
        communication: dict[str, str] | None = None,
        biorhythms: dict[str, Any] | None = None,
        persona: str | None = None,
        seed_domains: dict[str, list[str]] | None = None,
        # DSPy integration — optional optimized cognitive processing
        use_dspy: bool = False,
        dspy_model: str | None = None,
        dspy_optimized_path: str | None = None,
        **kwargs,
    ) -> Soul:
        """Birth a new Soul.

        Args:
            name: The soul's name.
            archetype: Personality archetype description.
            personality: Origin story / persona text.
            values: Core values for significance scoring.
            communication_style: Communication style description (legacy).
            bonded_to: Entity this soul is bonded to.
            engine: Optional CognitiveEngine for LLM-enhanced cognition.
            search_strategy: Optional SearchStrategy for pluggable retrieval (v0.2.2).
            ocean: OCEAN personality traits, e.g. {"openness": 0.8, ...}.
                   Unspecified traits default to 0.5.
            communication: Communication style dict, e.g. {"warmth": "high", ...}.
                           Unspecified fields keep model defaults.
            biorhythms: Biorhythm settings, e.g. {"chronotype": "night_owl", ...}.
                        Unspecified fields keep model defaults.
            persona: Core memory persona text. If provided, overrides the
                     personality parameter for core memory initialization.
            seed_domains: Custom seed domains for the self-model, e.g.
                          {"cooking": ["recipe", "bake", ...]}. Replaces
                          the default 6 bootstrapping domains.
            use_dspy: If True, use DSPy-optimized cognitive processing.
                Requires the dspy package to be installed (pip install soul-protocol[dspy]).
                Falls back silently to heuristic if dspy is not available.
            dspy_model: DSPy-compatible LM model string (default: claude-haiku-4-5).
            dspy_optimized_path: Path to pre-optimized DSPy module weights.
            **kwargs: Additional arguments (reserved for future use).
        """
        identity = Identity(
            did=generate_did(name),
            name=name,
            archetype=archetype,
            origin_story=personality,
            core_values=values or [],
            bonded_to=bonded_to,
        )

        # Build DNA from optional configuration parameters
        dna_personality = Personality()
        if ocean:
            dna_personality = Personality(
                openness=ocean.get("openness", 0.5),
                conscientiousness=ocean.get("conscientiousness", 0.5),
                extraversion=ocean.get("extraversion", 0.5),
                agreeableness=ocean.get("agreeableness", 0.5),
                neuroticism=ocean.get("neuroticism", 0.5),
            )

        dna_comm = CommunicationStyle()
        if communication:
            dna_comm = CommunicationStyle(**communication)

        dna_bio = Biorhythms()
        if biorhythms:
            dna_bio = Biorhythms(**biorhythms)

        dna = DNA(
            personality=dna_personality,
            communication=dna_comm,
            biorhythms=dna_bio,
        )

        config = SoulConfig(
            identity=identity,
            dna=dna,
            lifecycle=LifecycleState.ACTIVE,
        )

        # Use explicit persona text, fall back to personality, fall back to default
        persona_text = persona or personality or f"I am {name}."

        soul = cls(
            config,
            engine=engine,
            search_strategy=search_strategy,
            seed_domains=seed_domains,
            use_dspy=use_dspy,
            dspy_model=dspy_model,
            dspy_optimized_path=dspy_optimized_path,
        )

        # Initialize core memory
        soul._memory.set_core(
            persona=persona_text,
            human="",
        )

        logger.info("Soul born: name=%s, did=%s", name, identity.did)
        return soul

    @classmethod
    async def birth_from_config(
        cls,
        config_path: str | Path,
        engine: CognitiveEngine | None = None,
    ) -> Soul:
        """Birth a soul from a YAML/JSON config file.

        The config file can specify all soul parameters:
        name, archetype, values, ocean, communication, biorhythms, persona, etc.

        Args:
            config_path: Path to a .yaml/.yml/.json file with soul parameters.
            engine: Optional CognitiveEngine for LLM-enhanced cognition.

        Returns:
            A newly birthed Soul configured from the file.

        Raises:
            ValueError: If the file format is not supported.
            FileNotFoundError: If the config file does not exist.
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        if path.suffix in (".yaml", ".yml"):
            import yaml

            data = yaml.safe_load(path.read_text())
        elif path.suffix == ".json":
            import json

            data = json.loads(path.read_text())
        else:
            raise ValueError(
                f"Unsupported config format: {path.suffix}. Use .yaml, .yml, or .json."
            )

        if not isinstance(data, dict):
            raise ValueError(f"Config file is empty or not a valid mapping: {path}")

        logger.info("Birthing soul from config: %s", path)
        return await cls.birth(
            engine=engine,
            **data,
        )

    @classmethod
    async def reincarnate(
        cls,
        old_soul: Soul,
        *,
        name: str | None = None,
    ) -> Soul:
        """Create a new Soul from an existing soul's essence.

        Preserves memories, personality (DNA), and core values from the
        previous life. Generates a new DID and increments the incarnation
        counter. The old soul's DID is recorded in ``previous_lives``.

        Args:
            old_soul: The soul to reincarnate from.
            name: Optional new name. Defaults to the old soul's name.

        Returns:
            A fresh Soul carrying forward the old soul's essence.
        """
        new_name = name or old_soul.name
        old_identity = old_soul.identity

        # Build lineage
        previous_lives = list(old_identity.previous_lives)
        previous_lives.append(old_soul.did)

        # born intentionally reset — new incarnation begins fresh
        identity = Identity(
            did=generate_did(new_name),
            name=new_name,
            archetype=old_identity.archetype,
            origin_story=old_identity.origin_story,
            core_values=list(old_identity.core_values),
            bonded_to=old_identity.bonded_to,
            bond=old_identity.bond.model_copy(),
            incarnation=old_identity.incarnation + 1,
            previous_lives=previous_lives,
        )

        config = SoulConfig(
            identity=identity,
            dna=old_soul.dna.model_copy(deep=True),
            core_memory=old_soul.get_core_memory().model_copy(),
            evolution=old_soul._evolution.config.model_copy(deep=True),
            lifecycle=LifecycleState.ACTIVE,
        )

        soul = cls(config)

        # Carry forward memories from the old soul
        memory_data = old_soul._memory.to_dict()
        if memory_data:
            soul._memory = MemoryManager.from_dict(
                memory_data,
                config.memory,
                core_values=config.identity.core_values,
            )

        logger.info(
            "Soul reincarnated: name=%s, incarnation=%d, old_did=%s, new_did=%s",
            new_name,
            identity.incarnation,
            old_soul.did,
            identity.did,
        )
        return soul

    @classmethod
    async def awaken(
        cls,
        source: str | Path | bytes,
        engine: CognitiveEngine | None = None,
        search_strategy: SearchStrategy | None = None,
        password: str | None = None,
    ) -> Soul:
        """Awaken a Soul from a .soul file, directory, soul.json, soul.yaml, or soul.md.

        Args:
            source: Path to soul file/directory, or raw bytes of a .soul archive.
                    Directories must contain a ``soul.json`` file.
            engine: Optional CognitiveEngine for LLM-enhanced cognition.
            search_strategy: Optional SearchStrategy for pluggable retrieval (v0.2.2).
            password: Optional password for decrypting encrypted .soul archives.
        """
        from .exceptions import SoulCorruptError, SoulDecryptionError, SoulEncryptedError, SoulFileNotFoundError

        memory_data: dict = {}

        if isinstance(source, bytes):
            try:
                config, memory_data = await unpack_soul(source, password=password)
            except (SoulEncryptedError, SoulDecryptionError):
                raise
            except Exception as e:
                logger.error("Failed to awaken soul from bytes: %s", e)
                raise SoulCorruptError("<bytes>", str(e)) from e
        else:
            path = Path(source)
            if not path.exists():
                raise SoulFileNotFoundError(str(path))
            try:
                # Directory support: load from .soul/ folders or any dir with soul.json
                if path.is_dir():
                    from .storage.file import load_soul_full

                    config, memory_data = await load_soul_full(path)
                    if config is None:
                        raise SoulFileNotFoundError(str(path))
                elif path.suffix == ".soul":
                    try:
                        config, memory_data = await unpack_soul(
                            path.read_bytes(), password=password
                        )
                    except (SoulEncryptedError, SoulDecryptionError):
                        raise
                    except Exception as e:
                        logger.error(
                            "Corrupt .soul archive: path=%s, error=%s", path, e
                        )
                        raise SoulCorruptError(str(path), str(e)) from e
                elif path.suffix == ".json":
                    config = SoulConfig.model_validate_json(path.read_text())
                elif path.suffix in (".yaml", ".yml"):
                    import yaml

                    data = yaml.safe_load(path.read_text())
                    config = SoulConfig.model_validate(data)
                elif path.suffix == ".md":
                    from .parsers.markdown import soul_from_md

                    return cls(
                        await soul_from_md(path.read_text()),
                        engine=engine,
                        search_strategy=search_strategy,
                    )
                else:
                    raise ValueError(f"Unknown soul format: {path.suffix}")
            except (SoulFileNotFoundError, SoulCorruptError, SoulEncryptedError, SoulDecryptionError):
                raise
            except PermissionError as e:
                raise SoulFileNotFoundError(str(path)) from e

        soul = cls(config, engine=engine, search_strategy=search_strategy)
        soul._lifecycle = LifecycleState.ACTIVE

        # If full memory data was included, replace the default memory manager
        if memory_data:
            soul._memory = MemoryManager.from_dict(
                memory_data,
                config.memory,
                core_values=config.identity.core_values,
                engine=engine,
                search_strategy=search_strategy,
            )

        logger.info(
            "Soul awakened: name=%s, did=%s, memories=%d",
            soul.name,
            soul.did,
            soul.memory_count,
        )
        return soul

    @classmethod
    async def from_markdown(cls, content: str) -> Soul:
        """Create a Soul from SOUL.md content."""
        from .parsers.markdown import soul_from_md

        config = await soul_from_md(content)
        return cls(config)

    # ============ Properties ============

    @property
    def did(self) -> str:
        return self._identity.did

    @property
    def name(self) -> str:
        return self._identity.name

    @property
    def born(self):
        return self._identity.born

    @property
    def archetype(self) -> str:
        return self._identity.archetype

    @property
    def dna(self) -> DNA:
        return self._dna

    @property
    def state(self) -> SoulState:
        return self._state.current

    @property
    def lifecycle(self) -> LifecycleState:
        return self._lifecycle

    @property
    def identity(self) -> Identity:
        return self._identity

    @property
    def self_model(self):
        """Access the soul's self-model (Klein's self-concept).

        Returns the SelfModelManager which tracks self-images and
        relationship notes accumulated from experience.
        """
        return self._memory.self_model

    # ============ DNA & System Prompt ============

    def to_system_prompt(self) -> str:
        """Generate a system prompt from DNA + core memory + state + self-model."""
        base_prompt = dna_to_system_prompt(
            identity=self._identity,
            dna=self._dna,
            core_memory=self._memory.get_core(),
            state=self._state.current,
        )

        # Append self-model insights if available
        self_model_fragment = self._memory.self_model.to_prompt_fragment()
        if self_model_fragment:
            base_prompt += "\n\n" + self_model_fragment

        return base_prompt

    @property
    def system_prompt(self) -> str:
        """Convenience alias for to_system_prompt()."""
        return self.to_system_prompt()

    @property
    def memory_count(self) -> int:
        """Total number of stored memories."""
        return self._memory.count()

    async def context_for(
        self,
        user_input: str,
        *,
        max_memories: int = 5,
        include_state: bool = True,
        include_memories: bool = True,
        include_self_model: bool = False,
    ) -> str:
        """Generate a per-turn context block for any agentic system.

        Designed to be prepended to user messages or injected as context
        so the agent stays grounded as conversation history gets compressed
        or truncated. Works with any LLM framework — not tied to a specific SDK.

        Returns a string with the soul's live state and relevant memories
        for the current turn. Use alongside ``to_system_prompt()``::

            # At session start — set once:
            system = soul.to_system_prompt()

            # Before each turn — always fresh:
            context = await soul.context_for(user_input)
            full_message = context + user_input

        Args:
            user_input: The current user message (used for memory retrieval).
            max_memories: Maximum relevant memories to include.
            include_state: Include current mood, energy, social battery.
            include_memories: Recall and include relevant memories.
            include_self_model: Include self-model insights.

        Returns:
            A context string ready to prepend to the user message.
        """
        parts: list[str] = []

        if include_state:
            s = self._state.current
            parts.append(
                f"[Soul state: mood={s.mood.value}, energy={s.energy:.0f}%, "
                f"social_battery={s.social_battery:.0f}%]"
            )

        if include_memories and user_input.strip():
            memories = await self._memory.recall(query=user_input, limit=max_memories)
            if memories:
                lines = [f"- {m.content}" for m in memories]
                parts.append("[Relevant memories:\n" + "\n".join(lines) + "]")

        if include_self_model:
            fragment = self._memory.self_model.to_prompt_fragment()
            if fragment:
                parts.append(f"[Self-model: {fragment}]")

        if not parts:
            return ""

        return "\n".join(parts) + "\n\n"

    # ============ Memory ============

    async def remember(
        self,
        content: str,
        *,
        type: MemoryType = MemoryType.SEMANTIC,
        importance: int = 5,
        emotion: str | None = None,
        entities: list[str] | None = None,
    ) -> str:
        """Soul remembers something. Returns memory ID."""
        return await self._memory.add(
            MemoryEntry(
                type=type,
                content=content,
                importance=importance,
                emotion=emotion,
                entities=entities or [],
            )
        )

    async def recall(
        self,
        query: str,
        *,
        limit: int = 10,
        types: list[MemoryType] | None = None,
        min_importance: int = 0,
    ) -> list[MemoryEntry]:
        """Soul recalls relevant memories."""
        results = await self._memory.recall(
            query=query,
            limit=limit,
            types=types,
            min_importance=min_importance,
        )
        if not results:
            logger.debug("Recall returned no results: query_len=%d", len(query))
        return results

    async def observe(self, interaction: Interaction) -> None:
        """Soul observes an interaction and learns from it.

        This is the main learning hook — call after every user-agent exchange.

        v0.2.0 Pipeline (handled by MemoryManager.observe()):
          1. Detect sentiment → SomaticMarker
          2. Compute significance → gate for episodic storage
          3. If significant: store episodic with somatic marker
          4. Extract semantic facts (always)
          5. Extract entities (always)
          6. Update self-model

        After the memory pipeline, Soul handles:
          7. Update knowledge graph from extracted entities
          8. Update soul state (energy/social_battery drain)
          9. Check evolution triggers
        """
        logger.debug("observe() started: input_len=%d", len(interaction.user_input))

        # Delegate to psychology-informed memory pipeline
        result = await self._memory.observe(interaction)

        # Update knowledge graph from extracted entities
        raw_entities = result["entities"]
        if raw_entities:
            graph_entities: list[dict] = []
            for ent in raw_entities:
                graph_ent: dict = {
                    "name": ent["name"],
                    "entity_type": ent.get("type", "unknown"),
                    "relationships": [],
                }
                relation = ent.get("relation")
                if relation:
                    graph_ent["relationships"].append(
                        {"target": "user", "relation": relation}
                    )
                graph_entities.append(graph_ent)

            await self._memory.update_graph(graph_entities)

        # Update state based on interaction + detected sentiment
        self._state.on_interaction(interaction, somatic=result.get("somatic"))

        # Strengthen bond on each interaction
        somatic = result.get("somatic")
        if somatic and somatic.valence >= 0:
            self._identity.bond.strengthen(amount=1.0 + somatic.valence)
        else:
            self._identity.bond.strengthen(amount=0.5)

        # Grant XP to skills matching extracted entities/topics
        for entity in raw_entities:
            entity_name = entity["name"].lower().replace(" ", "_")
            skill = self._skills.get(entity_name)
            if skill:
                skill.add_xp(10)
            else:
                from .skills import Skill

                new_skill = Skill(id=entity_name, name=entity["name"])
                new_skill.add_xp(10)
                self._skills.add(new_skill)

        # Check for evolution triggers
        await self._evolution.check_triggers(self._dna, interaction)

    async def forget_by_id(self, memory_id: str) -> bool:
        """Soul forgets a specific memory by ID.

        For targeted deletion, prefer forget(), forget_entity(), or
        forget_before() which provide GDPR-compliant bulk deletion
        with audit trails.
        """
        logger.debug(
            "observe() complete: significant=%s, facts=%d, entities=%d",
            result.get("is_significant"),
            len(result.get("facts", [])),
            len(raw_entities),
        )

    async def forget(self, memory_id: str) -> bool:
        """Soul forgets a specific memory."""
        return await self._memory.remove(memory_id)

    async def forget(self, query: str) -> dict:
        """Forget memories matching a query across all tiers.

        Searches episodic, semantic, and procedural memory stores for
        content matching the query, and deletes all matches. Records
        a deletion audit entry (without storing deleted content).

        Args:
            query: Search query to match against memory content.

        Returns:
            Dict with deletion results per tier and total count.
        """
        return await self._memory.forget(query)

    async def forget_entity(self, entity: str) -> dict:
        """Forget an entity and all related memories.

        Removes the entity from the knowledge graph (node + edges)
        and deletes any memories mentioning the entity across all tiers.

        Args:
            entity: The entity name to forget.

        Returns:
            Dict with deletion results including graph edges removed.
        """
        return await self._memory.forget_entity(entity)

    async def forget_before(self, timestamp: datetime) -> dict:
        """Forget all memories created before a timestamp.

        Bulk deletes memories from all tiers that are older than
        the given cutoff.

        Args:
            timestamp: Cutoff datetime. Memories older than this are deleted.

        Returns:
            Dict with deletion results per tier and total count.
        """
        return await self._memory.forget_before(timestamp)

    @property
    def deletion_audit(self) -> list[dict]:
        """Access the deletion audit trail.

        Returns a list of audit records. Each record contains:
          - deleted_at: ISO timestamp
          - count: number of items deleted
          - reason: description of the operation
          - tiers: per-tier breakdown

        No deleted content is stored in the audit trail.
        """
        return self._memory.deletion_audit

    def get_core_memory(self) -> CoreMemory:
        """Get the always-loaded core memory."""
        return self._memory.get_core()

    async def edit_core_memory(
        self, *, persona: str | None = None, human: str | None = None
    ):
        """Edit core memory."""
        await self._memory.edit_core(persona=persona, human=human)

    async def reflect(self, *, apply: bool = True) -> ReflectionResult | None:
        """Trigger a reflection pass with optional auto-apply.

        The soul reviews recent interactions, consolidates memories,
        and updates its self-understanding. Call periodically (e.g.,
        every 10-20 interactions, or at session end).

        Args:
            apply: If True (default), consolidate results into memory.
                Summaries become semantic memories, themes create
                GeneralEvents, self-insight updates the self-model.

        Returns:
            ReflectionResult with themes, summaries, and insights,
            or None if no CognitiveEngine is available.
        """
        result = await self._memory.reflect(soul_name=self.name)
        if result is not None and apply:
            await self._memory.consolidate(result, soul_name=self.name)
        return result

    @property
    def general_events(self) -> list[GeneralEvent]:
        """Access the soul's general events (Conway hierarchy)."""
        return list(self._memory._general_events.values())

    # ============ Bond / Skills ============

    @property
    def bond(self) -> Bond:
        """Access the soul's bond with its bonded entity."""
        return self._identity.bond

    @property
    def skills(self) -> SkillRegistry:
        """Access the soul's skill registry."""
        return self._skills

    # ============ State / Feelings ============

    def feel(self, **kwargs) -> None:
        """Update the soul's emotional state.

        Example: soul.feel(energy=-5, mood=Mood.TIRED)
        """
        self._state.update(**kwargs)

    # ============ Evolution ============

    async def propose_evolution(
        self, trait: str, new_value: str, reason: str
    ) -> Mutation:
        """Propose a trait mutation."""
        return await self._evolution.propose(
            dna=self._dna,
            trait=trait,
            new_value=new_value,
            reason=reason,
        )

    async def approve_evolution(self, mutation_id: str) -> bool:
        """Approve a pending mutation."""
        result = await self._evolution.approve(mutation_id)
        if result:
            self._dna = self._evolution.apply(self._dna, mutation_id)
            logger.info(
                "Evolution approved and applied: mutation_id=%s", mutation_id
            )
        return result

    async def reject_evolution(self, mutation_id: str) -> bool:
        """Reject a pending mutation."""
        return await self._evolution.reject(mutation_id)

    @property
    def pending_mutations(self) -> list[Mutation]:
        return self._evolution.pending

    @property
    def evolution_history(self) -> list[Mutation]:
        return self._evolution.history

    # ============ Persistence ============

    async def save(self, path: str | Path | None = None) -> None:
        """Save soul to file storage (config + full memory)."""
        from .storage.file import save_soul_full

        save_path = Path(path) if path else None
        memory_data = self._memory.to_dict()
        await save_soul_full(self.serialize(), memory_data, path=save_path)
        logger.info("Soul saved: name=%s, path=%s", self.name, save_path)

    async def save_local(self, path: str | Path = ".soul") -> None:
        """Save to a local directory (flat, no soul_id nesting).

        Designed for .soul/ project folders where the directory IS the soul.

        Args:
            path: Target directory (default ``".soul"``).
        """
        from .storage.file import save_soul_flat

        config = self.serialize()
        memory_data = self._memory.to_dict()
        await save_soul_flat(config, memory_data, Path(path))
        logger.info("Soul saved locally: name=%s, path=%s", self.name, path)

    async def export(self, path: str | Path, *, password: str | None = None) -> None:
        """Export soul as a portable .soul file with full memory data.

        Args:
            path: File path for the exported .soul archive.
            password: Optional password for AES-256-GCM encryption at rest.
                When provided, all content except the manifest is encrypted.
        """
        from .exceptions import SoulExportError

        try:
            memory_data = self._memory.to_dict()
            data = await pack_soul(
                self.serialize(), memory_data=memory_data, password=password
            )
            Path(path).write_bytes(data)
            logger.info(
                "Soul exported: name=%s, path=%s, size=%d bytes",
                self.name,
                path,
                len(data),
            )
        except PermissionError as e:
            logger.error("Export failed (permission denied): path=%s", path)
            raise SoulExportError(str(path), "permission denied") from e
        except OSError as e:
            logger.error("Export failed: path=%s, error=%s", path, e)
            raise SoulExportError(str(path), str(e)) from e

    async def retire(
        self, *, farewell: bool = False, preserve_memories: bool = True
    ) -> None:
        """Retire this soul with dignity.

        If preserve_memories is True (default), saves all memories before
        retiring. If the save fails, the soul remains in its current
        lifecycle state and a SoulRetireError is raised.
        """
        if preserve_memories:
            from .exceptions import SoulRetireError

            try:
                await self.save()
            except Exception as e:
                logger.error(
                    "Retire failed (save error): name=%s, error=%s",
                    self.name,
                    e,
                )
                raise SoulRetireError(str(e)) from e

        self._lifecycle = LifecycleState.RETIRED
        await self._memory.clear()
        self._state.reset()
        logger.info("Soul retired: name=%s, did=%s", self.name, self.did)

    # ============ Serialization ============

    def serialize(self) -> SoulConfig:
        """Serialize to a SoulConfig for storage/export."""
        return SoulConfig(
            version="1.0.0",
            identity=self._identity,
            dna=self._dna,
            memory=self._memory.settings,
            core_memory=self._memory.get_core(),
            state=self._state.current,
            evolution=self._evolution.config,
            lifecycle=self._lifecycle,
        )
