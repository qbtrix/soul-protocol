# test_bitemporal.py — Tests for bi-temporal ingestion timestamps (v0.4.0).
# Created: v0.4.0 — 12 tests covering ingested_at field on MemoryEntry,
#   backward compatibility with None, auto-stamping in storage pipeline,
#   and the superseded boolean field.

from __future__ import annotations

from datetime import datetime

import pytest

from soul_protocol.runtime.memory.manager import MemoryManager
from soul_protocol.runtime.types import (
    CoreMemory,
    MemoryEntry,
    MemorySettings,
    MemoryType,
)
from soul_protocol.spec.memory import MemoryEntry as SpecMemoryEntry


@pytest.fixture
def manager() -> MemoryManager:
    return MemoryManager(core=CoreMemory(), settings=MemorySettings())


# ==== Runtime MemoryEntry field tests ====


class TestIngestedAtField:
    """Tests for the ingested_at field on runtime MemoryEntry."""

    def test_default_is_none(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test")
        assert entry.ingested_at is None

    def test_explicit_value_preserved(self):
        ts = datetime(2025, 6, 15, 12, 0, 0)
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test", ingested_at=ts)
        assert entry.ingested_at == ts

    def test_created_at_independent_of_ingested_at(self):
        before = datetime.now()
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test")
        assert entry.created_at >= before
        assert entry.ingested_at is None

    async def test_add_sets_ingested_at(self, manager: MemoryManager):
        """MemoryManager.add() should auto-stamp ingested_at."""
        before = datetime.now()
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="auto stamped", importance=5)
        assert entry.ingested_at is None
        await manager.add(entry)
        assert entry.ingested_at is not None
        assert entry.ingested_at >= before

    async def test_add_preserves_explicit_ingested_at(self, manager: MemoryManager):
        """If ingested_at is already set, add() should not overwrite it."""
        ts = datetime(2025, 1, 1, 0, 0, 0)
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC, content="preset", importance=5, ingested_at=ts
        )
        await manager.add(entry)
        assert entry.ingested_at == ts

    async def test_ingested_at_set_for_procedural(self, manager: MemoryManager):
        """Procedural memories also get ingested_at stamped."""
        entry = MemoryEntry(type=MemoryType.PROCEDURAL, content="how to deploy", importance=5)
        await manager.add(entry)
        assert entry.ingested_at is not None

    def test_serialization_roundtrip(self):
        ts = datetime(2025, 6, 15, 12, 0, 0)
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="roundtrip", ingested_at=ts)
        data = entry.model_dump(mode="json")
        restored = MemoryEntry.model_validate(data)
        assert restored.ingested_at is not None

    def test_backward_compat_no_ingested_at(self):
        """Old data without ingested_at should deserialize fine."""
        data = {
            "type": "semantic",
            "content": "old memory",
            "importance": 5,
        }
        entry = MemoryEntry.model_validate(data)
        assert entry.ingested_at is None


# ==== Superseded boolean field tests ====


class TestSupersededField:
    """Tests for the superseded boolean field on MemoryEntry."""

    def test_default_is_false(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="test")
        assert entry.superseded is False

    def test_set_to_true(self):
        entry = MemoryEntry(type=MemoryType.SEMANTIC, content="old fact")
        entry.superseded = True
        assert entry.superseded is True

    def test_backward_compat_no_superseded(self):
        data = {
            "type": "semantic",
            "content": "old memory",
            "importance": 5,
        }
        entry = MemoryEntry.model_validate(data)
        assert entry.superseded is False


# ==== Spec MemoryEntry field tests ====


class TestSpecMemoryEntry:
    """Tests for the spec-layer MemoryEntry additions."""

    def test_spec_ingested_at_default_none(self):
        entry = SpecMemoryEntry(content="spec test")
        assert entry.ingested_at is None

    def test_spec_superseded_default_false(self):
        entry = SpecMemoryEntry(content="spec test")
        assert entry.superseded is False

    def test_spec_roundtrip(self):
        entry = SpecMemoryEntry(
            content="spec roundtrip",
            ingested_at=datetime(2025, 6, 15),
            superseded=True,
        )
        data = entry.model_dump(mode="json")
        restored = SpecMemoryEntry.model_validate(data)
        assert restored.ingested_at is not None
        assert restored.superseded is True
