# tests/test_trust_chain/test_append_failure_logging.py — _safe_append_chain logging (#202).
# Created: 2026-04-29 — Verifies that:
#   1. Read-only souls (loaded without a private key, or with the
#      _PublicOnlyProvider stub) stay silent at WARNING — only DEBUG fires,
#      because a verification-only soul not appending is the documented
#      and expected flow.
#   2. A real exception during sign() (e.g. a faulty provider that raises)
#      surfaces as a WARNING with structured fields including the action
#      name, the error type, and a ``runtime.chain_append_skipped`` event
#      tag observability tooling can grep for.
#   3. The same WARNING-with-context pattern fires from BondRegistry's
#      on_change callback path under a ``runtime.bond_callback_failed``
#      event tag.

from __future__ import annotations

import logging

import pytest

from soul_protocol.runtime.bond import BondRegistry
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AlwaysRaisesProvider:
    """A SignatureProvider stub whose sign() always raises ValueError.

    Used to simulate an unexpected failure mid-append. The provider has
    a public_key (so the early-return guards in ``_safe_append_chain``
    let the call through to ``manager.append``).
    """

    algorithm = "ed25519"
    public_key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

    def sign(self, message: bytes) -> str:
        raise ValueError("boom: signing provider went bad")

    def verify(self, message: bytes, signature: str, public_key: str) -> bool:
        return False


class _RuntimeRaisesProvider(_AlwaysRaisesProvider):
    """Same as above but raises ``RuntimeError`` instead of ``ValueError``."""

    def sign(self, message: bytes) -> str:
        raise RuntimeError("transient signing error")


class _TypeRaisesProvider(_AlwaysRaisesProvider):
    """Same as above but raises ``TypeError`` (third caught type)."""

    def sign(self, message: bytes) -> str:
        raise TypeError("malformed key bytes")


# ---------------------------------------------------------------------------
# Read-only souls stay silent at WARNING (#202)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_only_soul_no_private_key_no_warning(tmp_path, caplog):
    """A soul awakened from an export without keys is verification-only.
    Trying to perform a state-changing op should not emit WARNING — only DEBUG."""
    soul = await Soul.birth("Echo")
    await soul.observe(Interaction(user_input="seed", agent_output="ok"))

    archive = tmp_path / "echo.soul"
    await soul.export(archive, include_keys=False)

    soul2 = await Soul.awaken(archive)
    pre_length = soul2.trust_chain.length

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="soul_protocol.runtime.soul"):
        await soul2.observe(Interaction(user_input="another", agent_output="ok"))

    # Nothing got signed (verification-only mode)
    assert soul2.trust_chain.length == pre_length

    # No WARNING for the verification-only flow
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warnings, f"Unexpected WARNINGs: {[r.getMessage() for r in warnings]}"

    # But a DEBUG line records the skip so observability tooling can count
    # how many ops would have been signed if a private key had been present.
    debugs = [r for r in caplog.records if r.levelno == logging.DEBUG]
    skip_messages = [r.getMessage() for r in debugs if "skipped" in r.getMessage().lower()]
    assert skip_messages, "Expected a DEBUG 'skipped' log for verification-only flow"


@pytest.mark.asyncio
async def test_read_only_soul_does_not_warn_on_supersede(tmp_path, caplog):
    """Same expectation as the observe test, for the supersede callsite."""
    soul = await Soul.birth("Hotel")
    mid = await soul.remember("original")

    archive = tmp_path / "hotel.soul"
    await soul.export(archive, include_keys=False)

    soul2 = await Soul.awaken(archive)
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.soul"):
        await soul2.supersede(mid, "replacement", reason="test")

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warnings


# ---------------------------------------------------------------------------
# Unexpected exceptions surface as WARNING (#202)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unexpected_value_error_during_sign_logs_warning(caplog):
    """A provider that raises ValueError during sign should surface as a
    WARNING with the action name in the message."""
    soul = await Soul.birth("FaultySigner")
    # Inject a faulty provider AFTER birth so the test can trigger a
    # state-changing op that exercises _safe_append_chain.
    soul._signature_provider = _AlwaysRaisesProvider()
    soul._trust_chain_manager.provider = soul._signature_provider

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.soul"):
        await soul.observe(Interaction(user_input="hi", agent_output="hello"))

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "Expected at least one WARNING from the faulty provider"

    chain_skip = [w for w in warnings if "runtime.chain_append_skipped" in w.getMessage()]
    assert chain_skip, "Expected runtime.chain_append_skipped event tag in WARNING"

    # observe() fires both bond.strengthen and memory.write through the
    # chain — both should produce structured WARNINGs. We verify the union
    # of messages contains all three required fields.
    all_messages = " ".join(w.getMessage() for w in chain_skip)
    assert "memory.write" in all_messages
    assert "ValueError" in all_messages
    assert "FaultySigner" in all_messages  # soul name


@pytest.mark.asyncio
async def test_unexpected_runtime_error_during_sign_logs_warning(caplog):
    soul = await Soul.birth("FaultyRuntime")
    soul._signature_provider = _RuntimeRaisesProvider()
    soul._trust_chain_manager.provider = soul._signature_provider

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.soul"):
        await soul.observe(Interaction(user_input="hi", agent_output="hello"))

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "runtime.chain_append_skipped" in r.getMessage()
    ]
    assert warnings
    assert "RuntimeError" in warnings[0].getMessage()


@pytest.mark.asyncio
async def test_unexpected_type_error_during_sign_logs_warning(caplog):
    soul = await Soul.birth("FaultyType")
    soul._signature_provider = _TypeRaisesProvider()
    soul._trust_chain_manager.provider = soul._signature_provider

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.soul"):
        await soul.observe(Interaction(user_input="hi", agent_output="hello"))

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "runtime.chain_append_skipped" in r.getMessage()
    ]
    assert warnings
    assert "TypeError" in warnings[0].getMessage()


@pytest.mark.asyncio
async def test_warning_includes_action_for_supersede_path(caplog):
    """The supersede callsite must also produce structured WARNINGs."""
    soul = await Soul.birth("FaultySupersede")
    mid = await soul.remember("original")

    soul._signature_provider = _AlwaysRaisesProvider()
    soul._trust_chain_manager.provider = soul._signature_provider

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.soul"):
        await soul.supersede(mid, "replacement", reason="test")

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "runtime.chain_append_skipped" in r.getMessage()
    ]
    assert warnings
    assert any("memory.supersede" in w.getMessage() for w in warnings)


@pytest.mark.asyncio
async def test_warning_does_not_break_the_underlying_action(caplog):
    """A failing chain append should not surface to the user — the underlying
    state mutation (memory write) must still complete."""
    soul = await Soul.birth("FaultyButOpen")
    soul._signature_provider = _AlwaysRaisesProvider()
    soul._trust_chain_manager.provider = soul._signature_provider

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.soul"):
        await soul.observe(Interaction(user_input="some text", agent_output="reply"))

    # Memory was written even though signing failed.
    assert soul.memory_count > 0


# ---------------------------------------------------------------------------
# Bond registry callback failure logging (#202)
# ---------------------------------------------------------------------------


def test_bond_registry_callback_failure_logs_warning_with_action(caplog):
    """A failing on_change callback must log at WARNING with the action
    namespace in the message."""
    failures: list[str] = []

    def boom(action: str, user_id, delta: float, new_strength: float) -> None:
        failures.append(action)
        raise RuntimeError("bridge into the chain went bad")

    registry = BondRegistry(on_change=boom)

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.bond"):
        registry.strengthen(amount=1.0)

    # The bond mutation itself succeeded
    assert registry.bond_strength > 50.0

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "runtime.bond_callback_failed" in r.getMessage()
    ]
    assert warnings, "Expected a runtime.bond_callback_failed WARNING"
    msg = warnings[0].getMessage()
    assert "bond.strengthen" in msg
    assert "RuntimeError" in msg


def test_bond_registry_weaken_callback_failure_logs_warning(caplog):
    def boom(action: str, user_id, delta: float, new_strength: float) -> None:
        raise ValueError("nope")

    registry = BondRegistry(on_change=boom)
    registry.bond_strength = 50.0

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.bond"):
        registry.weaken(amount=1.0)

    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "runtime.bond_callback_failed" in r.getMessage()
    ]
    assert warnings
    assert "bond.weaken" in warnings[0].getMessage()
    assert "ValueError" in warnings[0].getMessage()


def test_bond_registry_no_callback_no_warning(caplog):
    """Sanity: when no on_change is installed, strengthen/weaken stay quiet."""
    registry = BondRegistry()  # no on_change

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.bond"):
        registry.strengthen(amount=1.0)
        registry.weaken(amount=0.5)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert not warnings
