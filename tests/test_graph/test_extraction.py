# test_graph/test_extraction.py — Tests for the typed-ontology extractor.
# Created: 2026-04-29 (#190) — Verifies that:
#   1. The LLM-driven extractor returns typed entities + relations when given
#      a mock engine that responds with the new JSON schema.
#   2. The heuristic fallback (engine-less souls) still produces typed
#      entities via the translate_to_ontology mapping.
#   3. Re-running extraction on the same interaction is idempotent — graph
#      state stays the same on the second pass.

from __future__ import annotations

import json

import pytest

from soul_protocol import CoreMemory, HeuristicEngine, Interaction
from soul_protocol.runtime.cognitive.engine import CognitiveProcessor
from soul_protocol.runtime.memory.graph import KnowledgeGraph
from soul_protocol.runtime.memory.manager import (
    MemoryManager,
    translate_to_ontology,
)
from soul_protocol.runtime.types import MemorySettings


class FakeLLMEngine:
    """Minimal mock CognitiveEngine that returns a canned JSON response."""

    def __init__(self, response_payload: list[dict] | dict) -> None:
        self._response = json.dumps(response_payload)
        self.calls: int = 0

    async def think(self, prompt: str) -> str:
        self.calls += 1
        return self._response


@pytest.fixture
def memory_manager() -> MemoryManager:
    return MemoryManager(core=CoreMemory(), settings=MemorySettings())


# ============ Heuristic fallback ============


class TestHeuristicFallback:
    """Engine-less souls still produce typed entities via the heuristic."""

    @pytest.mark.asyncio
    async def test_heuristic_extracts_typed_entities(self, memory_manager: MemoryManager) -> None:
        engine = HeuristicEngine()
        processor = CognitiveProcessor(
            engine=engine,
            entity_extractor=memory_manager.extract_entities,
        )
        interaction = Interaction(
            user_input="I use Python and work at Acme",
            agent_output="Got it.",
        )
        entities = await processor.extract_entities(interaction, source_memory_id="ep-1")
        types = {e["name"].lower(): e["type"] for e in entities}
        # technology -> tool, organization -> org via translate_to_ontology
        assert types.get("python") == "tool"
        # All entities should carry edge_metadata with the source_memory_id
        for e in entities:
            assert e["edge_metadata"]["source_memory_id"] == "ep-1"
            assert e["source_memory_id"] == "ep-1"

    @pytest.mark.asyncio
    async def test_heuristic_extracts_first_person_relation(
        self, memory_manager: MemoryManager
    ) -> None:
        engine = HeuristicEngine()
        processor = CognitiveProcessor(
            engine=engine,
            entity_extractor=memory_manager.extract_entities,
        )
        interaction = Interaction(
            user_input="I use Rust daily",
            agent_output="Rust is fast.",
        )
        entities = await processor.extract_entities(interaction)
        rust = next((e for e in entities if e["name"].lower() == "rust"), None)
        assert rust is not None
        assert rust["relation"] == "uses"


# ============ LLM-driven extraction ============


class TestLLMExtraction:
    """A mock engine returning the new JSON schema feeds typed entities/edges."""

    @pytest.mark.asyncio
    async def test_llm_returns_typed_entities(self) -> None:
        fake = FakeLLMEngine(
            [
                {
                    "name": "Alice",
                    "type": "person",
                    "relations": [
                        {"target": "Acme", "relation": "owned_by", "weight": 0.9},
                    ],
                },
                {"name": "Acme", "type": "org", "relations": []},
            ]
        )
        processor = CognitiveProcessor(engine=fake)
        interaction = Interaction(
            user_input="Alice works at Acme",
            agent_output="OK",
        )
        entities = await processor.extract_entities(interaction, source_memory_id="ep-1")
        names = {e["name"] for e in entities}
        assert names == {"Alice", "Acme"}
        alice = next(e for e in entities if e["name"] == "Alice")
        assert alice["type"] == "person"
        assert len(alice["relationships"]) == 1
        edge = alice["relationships"][0]
        assert edge["target"] == "Acme"
        assert edge["relation"] == "owned_by"
        assert edge["weight"] == 0.9

    @pytest.mark.asyncio
    async def test_llm_arbitrary_type_passes_through(self) -> None:
        fake = FakeLLMEngine(
            [
                {"name": "PR-1024", "type": "pr", "relations": []},
            ]
        )
        processor = CognitiveProcessor(engine=fake)
        interaction = Interaction(user_input="PR-1024 ready", agent_output="")
        entities = await processor.extract_entities(interaction)
        assert entities[0]["type"] == "pr"

    @pytest.mark.asyncio
    async def test_llm_falls_back_to_heuristic_on_malformed(
        self, memory_manager: MemoryManager
    ) -> None:
        # FakeLLMEngine returning broken JSON triggers the fallback
        class BrokenEngine:
            async def think(self, prompt: str) -> str:
                return "not even close to JSON"

        processor = CognitiveProcessor(
            engine=BrokenEngine(),
            entity_extractor=memory_manager.extract_entities,
        )
        interaction = Interaction(user_input="I use Python", agent_output="OK")
        entities = await processor.extract_entities(interaction)
        # Heuristic still produces Python tool entity
        assert any(e["name"].lower() == "python" for e in entities)

    @pytest.mark.asyncio
    async def test_llm_no_engine_no_extractor_returns_empty(self) -> None:
        # Engine produces malformed JSON and there's no heuristic fallback
        class BrokenEngine:
            async def think(self, prompt: str) -> str:
                return "garbage"

        processor = CognitiveProcessor(engine=BrokenEngine())
        interaction = Interaction(user_input="hi", agent_output="hi")
        entities = await processor.extract_entities(interaction)
        assert entities == []


# ============ Idempotence ============


class TestIdempotence:
    """Re-extraction on the same interaction shouldn't multiply graph state."""

    def test_double_add_entity_is_no_op(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("Alice", "person")
        g.add_entity("Alice", "person")
        nodes = g.list_nodes()
        assert len(nodes) == 1

    def test_double_add_relationship_is_no_op(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("A", "person")
        g.add_entity("B", "person")
        g.add_relationship("A", "B", "mentions")
        g.add_relationship("A", "B", "mentions")
        edges = g.list_edges()
        assert len(edges) == 1

    def test_re_extraction_records_provenance(self) -> None:
        g = KnowledgeGraph()
        g.add_entity("Alice", "person", source_memory_id="m1")
        g.add_entity("Alice", "person", source_memory_id="m2")
        # Same entity, two memories — provenance grows
        nodes = g.list_nodes()
        assert nodes[0].provenance == ["m1", "m2"]

    def test_re_extraction_keeps_first_meaningful_type(self) -> None:
        # Adding the same entity with a meaningful type shouldn't downgrade it
        g = KnowledgeGraph()
        g.add_entity("Alice", "person")
        g.add_entity("Alice", "")  # blank type — should be ignored
        nodes = g.list_nodes()
        assert nodes[0].type == "person"


# ============ Translation helper ============


class TestTranslationHelper:
    @pytest.mark.parametrize(
        "legacy,expected",
        [
            ("technology", "tool"),
            ("tech", "tool"),  # synonym — normalizes to tool
            ("organization", "org"),
            ("user", "person"),
            ("location", "place"),
            ("doc", "document"),
            ("project", "project"),  # custom type passes through
            ("library", "library"),
            ("", "concept"),
            ("unknown", "concept"),
        ],
    )
    def test_translation_table(self, legacy: str, expected: str) -> None:
        assert translate_to_ontology(legacy) == expected
