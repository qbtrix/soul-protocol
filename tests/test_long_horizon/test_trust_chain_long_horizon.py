# test_trust_chain_long_horizon.py — 50+ trust-chain ops survive end to end (#201, #202).
# Created: 2026-04-29 — Long-horizon assurance for the audit-log payload-summaries
# work and the structured WARNING-level chain-append-failure logging.
#
# Three guarantees verified across one extended scenario:
#
# 1. Every emitted entry carries a non-empty ``summary`` — proving the
#    formatter registry covers every action namespace Soul actually uses
#    in a long-running session, not just a hand-picked few.
#
# 2. When a flaky signature provider is wired in (1-in-N appends raises),
#    every failed append produces a ``runtime.chain_append_skipped``
#    WARNING with the action name. The count of WARNINGs matches the
#    count of injected failures — no double counting, no silent drops.
#
# 3. The chain still verifies even when some entries were skipped due to
#    the failures. Skipped operations don't write to the chain at all —
#    they're not corrupted entries, just absences. Chain integrity is
#    therefore unaffected.
#
# This test runs entirely without an LLM (HeuristicEngine path) so it
# fits inside the normal pytest suite and doesn't burn API credits.

from __future__ import annotations

import logging

import pytest

from soul_protocol.runtime.crypto.ed25519 import Ed25519SignatureProvider
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import Interaction


class _FlakySignatureProvider:
    """A SignatureProvider that wraps a real Ed25519 provider but raises
    on every Nth ``sign()`` call to simulate an intermittent backend
    failure (HSM hiccup, key-vault rate limit, etc.).

    All other methods delegate to the wrapped provider so verification
    still works for the entries that did get signed.
    """

    def __init__(self, base: Ed25519SignatureProvider, fail_every: int = 10) -> None:
        self._base = base
        self._fail_every = max(1, fail_every)
        self._calls = 0
        self.failures = 0

    @property
    def algorithm(self) -> str:
        return self._base.algorithm

    @property
    def public_key(self) -> str:
        return self._base.public_key

    def sign(self, message: bytes) -> str:
        self._calls += 1
        if self._calls % self._fail_every == 0:
            self.failures += 1
            raise RuntimeError(f"flaky-provider: simulated failure on call {self._calls}")
        return self._base.sign(message)

    def verify(self, message: bytes, signature: str, public_key: str) -> bool:
        return self._base.verify(message, signature, public_key)


@pytest.mark.asyncio
async def test_long_horizon_50_ops_summaries_warnings_and_verification(caplog):
    """Run 50+ trust-chain-emitting ops; assert summaries, WARNING count, and verify."""
    soul = await Soul.birth("LongHorizonAuditSoul")

    # Drive 25 turns of observe() — each one writes a memory.write entry and
    # also strengthens the bond, so we get ~50+ chain entries before any
    # other action runs.
    pre_chain_length = soul.trust_chain.length
    for i in range(25):
        await soul.observe(
            Interaction(
                user_input=f"Telling you fact #{i}: my favourite color is color-{i % 5}.",
                agent_output=f"Got it, color-{i % 5}.",
            )
        )

    # Add a few more action types so the registry coverage is real
    # (memory.supersede, memory.forget, evolution.proposed,
    # evolution.applied, learning.event are all already exercised by
    # observe + the supersede/forget calls below).
    mid = await soul.remember("ephemeral fact for forget+supersede")
    res = await soul.supersede(mid, "corrected version", reason="long-horizon test")
    assert res["found"]

    mid2 = await soul.remember("another fact to forget")
    fres = await soul.forget_one(mid2)
    assert fres["found"]

    # Confirm we've crossed the 50-entry bar.
    assert soul.trust_chain.length - pre_chain_length >= 50, (
        f"Need 50+ entries for the long-horizon test; got {soul.trust_chain.length}"
    )

    # ---- Assertion 1: every entry has a non-empty summary ----
    log = soul.audit_log()
    missing = [row for row in log if not row.get("summary")]
    assert not missing, (
        f"Found {len(missing)} entries with empty summary. "
        f"Sample actions: {[row['action'] for row in missing[:5]]}"
    )

    # ---- Phase 2: replay with a flaky provider, count WARNINGs ----
    flaky_soul = await Soul.birth("LongHorizonFlakySoul")
    base_provider = flaky_soul._signature_provider
    assert isinstance(base_provider, Ed25519SignatureProvider)
    flaky = _FlakySignatureProvider(base_provider, fail_every=10)
    flaky_soul._signature_provider = flaky
    flaky_soul._trust_chain_manager.provider = flaky

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="soul_protocol.runtime.soul"):
        for i in range(25):
            await flaky_soul.observe(
                Interaction(
                    user_input=f"flaky turn {i}: noting fact-{i}.",
                    agent_output=f"recorded fact-{i}.",
                )
            )

    # ---- Assertion 2: warnings match the injected failure count ----
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "runtime.chain_append_skipped" in r.getMessage()
    ]
    assert flaky.failures > 0, "Test setup error: flaky provider didn't fire any failures"
    # Each failed sign() corresponds to exactly one chain_append_skipped WARNING.
    # No silent drops, no double counting.
    assert len(warnings) == flaky.failures, (
        f"Expected {flaky.failures} WARNINGs, got {len(warnings)}. "
        "Failure-count must match WARNING-count to surface real audit-trail gaps."
    )

    # Each WARNING records the action namespace.
    failed_actions = {w.getMessage().split("action=")[1].split(" ")[0] for w in warnings}
    # observe() emits both memory.write and bond.strengthen — at least one
    # of those has to appear in the failure set.
    assert failed_actions, "WARNINGs missing action= field"
    assert all(
        a.startswith(("memory.", "bond.", "evolution.", "learning.")) for a in failed_actions
    ), f"Unexpected failure actions: {failed_actions}"

    # ---- Assertion 3: chain still verifies despite the gaps ----
    valid, reason = flaky_soul.verify_chain()
    assert valid, (
        f"Chain failed verification despite the failures being silent skips, "
        f"not corrupt entries: {reason}"
    )

    # And the chain length reflects the gaps — fewer entries than the
    # intended 50 because some ops were skipped (the underlying memory
    # writes still happened though).
    appended = flaky_soul.trust_chain.length
    expected_max = 25 * 2  # observe writes memory.write + bond.strengthen
    assert appended < expected_max, (
        f"Chain has {appended} entries; expected fewer than {expected_max} "
        f"because {flaky.failures} appends should have been skipped."
    )
