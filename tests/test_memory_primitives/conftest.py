# tests/test_memory_primitives/conftest.py — shared fixtures for the v0.5.0
# brain-aligned memory primitives test suite (#192).
# Created: 2026-04-29 — fresh-soul fixture plus a small helper that exposes a
# few seeded memories so individual test files don't have to repeat the
# birth + remember dance.

from __future__ import annotations

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryType


@pytest.fixture
async def soul():
    """Brand-new soul, no seeded memories. Most tests use this and add their own."""
    return await Soul.birth(name="MemPrimTest", personality="Test soul for memory primitives.")


@pytest.fixture
async def soul_with_facts(soul):
    """Soul pre-loaded with three semantic facts for the verbs to act on."""
    ids = []
    for content in (
        "Project Atlas ships in May",
        "Aria prefers light mode",
        "Database migration was applied 2026-04-15",
    ):
        ids.append(await soul.remember(content, type=MemoryType.SEMANTIC, importance=7))
    soul._seed_ids = ids  # type: ignore[attr-defined]
    return soul
