# soul.py — The main Soul class: birth, awaken, observe, save, export
# Updated: 2026-03-06 — Added reincarnate() classmethod for lifecycle rebirth.
#   Preserves memories, personality, and tracks incarnation lineage.

from __future__ import annotations

from pathlib import Path

from .types import (
    CoreMemory,
    DNA,
    EvolutionConfig,
    Identity,
    Interaction,
    LifecycleState,
    MemoryEntry,
    MemorySettings,
    MemoryType,
    Mood,
    Mutation,
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

    def __init__(self, config: SoulConfig) -> None:
        self._config = config
        self._identity = config.identity
        self._dna = config.dna
        self._lifecycle = config.lifecycle

        self._memory = MemoryManager(
            core=config.core_memory,
            settings=config.memory,
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
        **kwargs,
    ) -> Soul:
        """Birth a new Soul."""
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

        soul = cls(config)

        # Initialize core memory
        soul._memory.set_core(
            persona=personality or f"I am {name}.",
            human="",
        )

        return soul

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
            from .memory.manager import MemoryManager as MM
            soul._memory = MM.from_dict(memory_data, config.memory)

        return soul

    @classmethod
    async def awaken(cls, source: str | Path | bytes) -> Soul:
        """Awaken a Soul from a .soul file, soul.json, soul.yaml, or soul.md."""
        memory_data: dict = {}

        if isinstance(source, bytes):
            config, memory_data = await unpack_soul(source)
        else:
            path = Path(source)
            if path.suffix == ".soul":
                config, memory_data = await unpack_soul(path.read_bytes())
            elif path.suffix == ".json":
                config = SoulConfig.model_validate_json(path.read_text())
            elif path.suffix in (".yaml", ".yml"):
                import yaml

                data = yaml.safe_load(path.read_text())
                config = SoulConfig.model_validate(data)
            elif path.suffix == ".md":
                from .parsers.markdown import soul_from_md

                return cls(await soul_from_md(path.read_text()))
            else:
                raise ValueError(f"Unknown soul format: {path.suffix}")

        soul = cls(config)
        soul._lifecycle = LifecycleState.ACTIVE

        # If full memory data was included, replace the default memory manager
        if memory_data:
            soul._memory = MemoryManager.from_dict(memory_data, config.memory)

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

    # ============ DNA & System Prompt ============

    def to_system_prompt(self) -> str:
        """Generate a system prompt from DNA + core memory + state."""
        return dna_to_system_prompt(
            identity=self._identity,
            dna=self._dna,
            core_memory=self._memory.get_core(),
            state=self._state.current,
        )

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

        Pipeline:
          1. Store the raw interaction as episodic memory.
          2. Extract semantic facts via heuristic patterns and store them
             (duplicates are skipped by extract_facts).
          3. Extract entities and transform them into the format expected
             by update_graph (entity_type + relationships list).
          4. Update soul state and check for evolution triggers.
        """
        # Store as episodic memory
        await self._memory.add_episodic(interaction)

        # Extract and store semantic facts (dedup handled inside extract_facts)
        facts = self._memory.extract_facts(interaction)
        for fact in facts:
            await self._memory.add(fact)

        # Extract entities and update knowledge graph
        raw_entities = self._memory.extract_entities(interaction)
        if raw_entities:
            # Transform extract_entities output -> update_graph format
            # extract_entities returns: {"name", "type", "relation"}
            # update_graph expects:     {"name", "entity_type", "relationships": [{target, relation}]}
            graph_entities: list[dict] = []
            for ent in raw_entities:
                graph_ent: dict = {
                    "name": ent["name"],
                    "entity_type": ent.get("type", "unknown"),
                    "relationships": [],
                }
                relation = ent.get("relation")
                if relation:
                    # Relationship flows: user --relation--> entity
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
