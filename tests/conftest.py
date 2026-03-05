# conftest.py — Shared fixtures for the soul-protocol test suite.
# Created: 2026-02-22 — Provides sample_identity, sample_config, sample_soul,
# and tmp_soul_file fixtures used across all test modules.

from __future__ import annotations

import pytest

from soul_protocol.soul import Soul
from soul_protocol.types import Identity, SoulConfig


@pytest.fixture
def sample_identity() -> Identity:
    """Return an Identity with name='Aria', archetype='The Compassionate Creator'."""
    return Identity(
        name="Aria",
        archetype="The Compassionate Creator",
    )


@pytest.fixture
def sample_config(sample_identity: Identity) -> SoulConfig:
    """Return a SoulConfig built from the sample_identity fixture."""
    return SoulConfig(identity=sample_identity)


@pytest.fixture
async def sample_soul() -> Soul:
    """Return a Soul birthed via Soul.birth with name='Aria'."""
    return await Soul.birth("Aria", archetype="The Compassionate Creator")


@pytest.fixture
async def tmp_soul_file(sample_soul: Soul, tmp_path) -> str:
    """Export sample_soul to a temporary .soul file and return the path string."""
    path = tmp_path / "aria.soul"
    await sample_soul.export(str(path))
    return str(path)
