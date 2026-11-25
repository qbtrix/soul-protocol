# tests/test_mcp/test_zip_save_keys.py — MCP saves of .soul zips and the private key.
# Created: 2026-11-25 — A zip that had keys/private.key keeps it after an MCP
#   save (so the soul can still sign); a zip without one stays without one.

from __future__ import annotations

import zipfile

import pytest

pytest.importorskip("fastmcp", reason="fastmcp required for MCP server tests")

from soul_protocol.mcp.server import _auto_save_one  # noqa: E402
from soul_protocol.runtime.soul import Soul  # noqa: E402
from soul_protocol.runtime.types import Interaction  # noqa: E402


def _has_private_key(path) -> bool:
    with zipfile.ZipFile(path) as zf:
        return "keys/private.key" in zf.namelist()


@pytest.mark.parametrize("had_key", [True, False])
async def test_zip_save_preserves_private_key_state(tmp_path, had_key):
    path = tmp_path / "s.soul"
    soul = await Soul.birth("Keys")
    await soul.export(path, include_keys=had_key)

    loaded = await Soul.awaken(str(path))
    await loaded.remember("a new fact")
    await _auto_save_one(loaded, str(path), "zip")

    assert _has_private_key(path) is had_key
    # With the key kept, the reloaded soul can still sign trust-chain entries.
    reloaded = await Soul.awaken(str(path))
    before = reloaded.trust_chain.length
    await reloaded.observe(Interaction(user_input="I moved to Pune", agent_output="Noted."))
    assert (reloaded.trust_chain.length > before) is had_key
