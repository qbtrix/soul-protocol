# soul.py — The main Soul class: birth, awaken, observe, save, export
# Updated: v0.3.0 — awaken() now supports directory paths (.soul/ folders).
#   Added save_local() for flat directory saving without soul_id nesting.
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

from __future__ import annotations

from pathlib import Path

from .cognitive.engine import CognitiveEngine
from .memory.strategy import SearchStrategy
from .types import (
    CoreMemory,
    DNA,
    EvolutionConfig,
    GeneralEvent,
    Identity,
    Interaction,
    LifecycleState,
    MemoryEntry,
    MemorySettings,
    MemoryType,
    Mood,
    Mutation,
    ReflectionResult,
    SoulConfig,
    SoulState,
)
from .identity.did import generate_did
from .dna.prompt import dna_to_system_prompt
from .memory.manager import MemoryManager
from .state.manager import StateManager
from .evolution.manager import EvolutionManager
from .export.pack import pack_soul
from .export.unpack import unpack_soul


class Soul:
    """A Digital Soul — persistent identity, memory, and state for an AI agent."""

    def __init__(
        self,
        config: SoulConfig,
        engine: CognitiveEngine | None = None,
        search_strategy: SearchStrategy | None = None,
    ) -> None:
        self._config = config
        self._identity = config.identity
        self._dna = config.dna
        self._lifecycle = config.lifecycle
        self._engine = engine
        self._search_strategy = search_strategy

        self._memory = MemoryManager(
            core=config.core_memory,
            settings=config.memory,
            core_values=config.identity.core_values,
            engine=engine,
            search_strategy=search_strategy,
        )
        self._state = StateManager(config.state)
        self._evolution = EvolutionManager(config.evolution)

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
        **kwargs,
    ) -> Soul:
        """Birth a new Soul.

        Args:
            name: The soul's name.
            archetype: Personality archetype description.
            personality: Origin story / persona text.
            values: Core values for significance scoring.
            communication_style: Communication style description.
            bonded_to: Entity this soul is bonded to.
            engine: Optional CognitiveEngine for LLM-enhanced cognition.
            search_strategy: Optional SearchStrategy for pluggable retrieval (v0.2.2).
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

        config = SoulConfig(
            identity=identity,
            lifecycle=LifecycleState.ACTIVE,
        )

        soul = cls(config, engine=engine, search_strategy=search_strategy)

        # Initialize core memory
        soul._memory.set_core(
            persona=personality or f"I am {name}.",
            human="",
        )

        return soul

    @classmethod
    async def awaken(
        cls,
        source: str | Path | bytes,
        engine: CognitiveEngine | None = None,
        search_strategy: SearchStrategy | None = None,
    ) -> Soul:
        """Awaken a Soul from a .soul file, directory, soul.json, soul.yaml, or soul.md.

        Args:
            source: Path to soul file/directory, or raw bytes of a .soul archive.
                    Directories must contain a ``soul.json`` file.
            engine: Optional CognitiveEngine for LLM-enhanced cognition.
            search_strategy: Optional SearchStrategy for pluggable retrieval (v0.2.2).
        """
        memory_data: dict = {}

        if isinstance(source, bytes):
            config, memory_data = await unpack_soul(source)
        else:
            path = Path(source)

            # Directory support: load from .soul/ folders or any dir with soul.json
            if path.is_dir():
                from .storage.file import load_soul_full

                config, memory_data = await load_soul_full(path)
                if config is None:
                    raise FileNotFoundError(
                        f"No soul.json found in directory: {path}"
                    )
            elif path.suffix == ".soul":
                config, memory_data = await unpack_soul(path.read_bytes())
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
        return await self._memory.recall(
            query=query,
            limit=limit,
            types=types,
            min_importance=min_importance,
        )

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

        # Update state based on interaction
        self._state.on_interaction(interaction)

        # Check for evolution triggers
        await self._evolution.check_triggers(self._dna, interaction)

    async def forget(self, memory_id: str) -> bool:
        """Soul forgets a specific memory."""
        return await self._memory.remove(memory_id)

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

    async def export(self, path: str | Path) -> None:
        """Export soul as a portable .soul file with full memory data."""
        memory_data = self._memory.to_dict()
        data = await pack_soul(self.serialize(), memory_data=memory_data)
        Path(path).write_bytes(data)

    async def retire(
        self, *, farewell: bool = False, preserve_memories: bool = True
    ) -> None:
        """Retire this soul with dignity."""
        if preserve_memories:
            await self.save()

        self._lifecycle = LifecycleState.RETIRED
        await self._memory.clear()
        self._state.reset()

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
