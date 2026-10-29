# tests/cross_runtime/conftest.py — Shared fixtures for cross-runtime tests.
# Created: 2026-06-10 (#228) — Provides a pre-populated soul with known
#   semantic and episodic memories for round-trip testing across runtimes.

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from soul_protocol.runtime.types import MemoryType


def pytest_configure(config):
    """Register the cross_runtime marker so pytest doesn't warn about it."""
    config.addinivalue_line(
        "markers",
        "cross_runtime: marks tests that require external runtime packages "
        "(PocketPaw, LangChain, CrewAI). Skipped when packages are missing.",
    )


# ---------- Known test data ----------

# These are the memories we store and expect to survive the round-trip.
SEMANTIC_MEMORIES = [
    {"content": "Python is my primary programming language", "importance": 8},
    {"content": "I prefer dark mode in all editors", "importance": 6},
    {"content": "Kubernetes is used for container orchestration", "importance": 7},
]

EPISODIC_MEMORIES = [
    {"content": "Had a great debugging session fixing the auth bug", "importance": 5},
    {"content": "Deployed the API to production for the first time", "importance": 9},
]

SOUL_NAME = "CrossRuntimeProbe"


# ---------- Fixtures ----------


@pytest.fixture
def populated_soul_path(tmp_path: Path) -> Path:
    """Create a .soul file with known memories and return its path.

    The soul contains:
    - 3 semantic memories (facts)
    - 2 episodic memories (events)

    All with known content and importance values for assertion.
    """

    async def _create():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name=SOUL_NAME)

        # Store semantic memories (facts)
        for mem in SEMANTIC_MEMORIES:
            await soul.remember(mem["content"], importance=mem["importance"])

        # Store episodic memories (events)
        for mem in EPISODIC_MEMORIES:
            await soul.remember(
                mem["content"],
                importance=mem["importance"],
                type=MemoryType.EPISODIC,
            )

        # Export to .soul file
        soul_path = tmp_path / "probe.soul"
        await soul.export(str(soul_path), include_keys=True)
        return soul_path

    return asyncio.get_event_loop().run_until_complete(_create())


@pytest.fixture
def soul_path_semantic_only(tmp_path: Path) -> Path:
    """Create a .soul file with only semantic memories.

    Simpler fixture for runtimes that only support semantic memory
    (LangChain, CrewAI).
    """

    async def _create():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.birth(name=SOUL_NAME)

        for mem in SEMANTIC_MEMORIES:
            await soul.remember(mem["content"], importance=mem["importance"])

        soul_path = tmp_path / "probe_semantic.soul"
        await soul.export(str(soul_path), include_keys=True)
        return soul_path

    return asyncio.get_event_loop().run_until_complete(_create())
