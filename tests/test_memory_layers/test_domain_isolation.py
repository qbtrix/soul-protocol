# tests/test_memory_layers/test_domain_isolation.py — Domain filtering on recall.
# Created: 2026-04-29 (#41) — Verifies that recall(domain=...) only surfaces
# memories from the requested domain. Recall without a domain filter
# returns the full union (back-compat).

from __future__ import annotations

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryEntry, MemoryType


@pytest.fixture
async def populated_soul():
    """A soul with 3 finance memories, 2 legal, 1 default."""
    soul = await Soul.birth(name="Aria", archetype="domain test")
    finance_lines = [
        "Q3 revenue is up 12 percent",
        "AWS bill jumped to fifty thousand",
        "The acquisition closes in March",
    ]
    legal_lines = [
        "NDA expires in six months",
        "The vendor contract auto-renews",
    ]
    default_lines = ["User likes Python"]

    for line in finance_lines:
        await soul._memory.add(
            MemoryEntry(
                type=MemoryType.SEMANTIC,
                content=line,
                importance=8,
                domain="finance",
            )
        )
    for line in legal_lines:
        await soul._memory.add(
            MemoryEntry(
                type=MemoryType.SEMANTIC,
                content=line,
                importance=8,
                domain="legal",
            )
        )
    for line in default_lines:
        await soul._memory.add(
            MemoryEntry(
                type=MemoryType.SEMANTIC,
                content=line,
                importance=8,
            )
        )
    return soul


@pytest.mark.asyncio
async def test_recall_finance_only_returns_finance(populated_soul):
    results = await populated_soul.recall(
        "revenue OR contract OR Python OR closes OR vendor OR likes",
        domain="finance",
        limit=20,
    )
    assert results, "expected finance memories"
    assert all(r.domain == "finance" for r in results), (
        f"finance recall surfaced foreign domains: {[r.domain for r in results]}"
    )


@pytest.mark.asyncio
async def test_recall_legal_only_returns_legal(populated_soul):
    results = await populated_soul.recall(
        "revenue OR contract OR Python OR closes OR vendor OR likes",
        domain="legal",
        limit=20,
    )
    assert results
    assert all(r.domain == "legal" for r in results)


@pytest.mark.asyncio
async def test_recall_default_returns_default_only(populated_soul):
    results = await populated_soul.recall(
        "Python OR revenue OR contract OR vendor OR likes",
        domain="default",
        limit=20,
    )
    assert results
    assert all(r.domain == "default" for r in results)


@pytest.mark.asyncio
async def test_recall_without_domain_filter_returns_union(populated_soul):
    results = await populated_soul.recall(
        "revenue OR contract OR Python OR closes OR vendor OR likes",
        limit=20,
    )
    domains = {r.domain for r in results}
    # Union should include at least two of the three distinct domains.
    assert len(domains) >= 2


@pytest.mark.asyncio
async def test_finance_does_not_leak_into_legal(populated_soul):
    finance_results = await populated_soul.recall(
        "revenue OR contract OR vendor", domain="finance", limit=20
    )
    finance_contents = {r.content for r in finance_results}
    assert "NDA expires in six months" not in finance_contents
    assert "The vendor contract auto-renews" not in finance_contents


@pytest.mark.asyncio
async def test_remember_with_domain_stamps_entry():
    soul = await Soul.birth(name="Bri", archetype="stamp test")
    mid = await soul.remember("X", domain="finance", importance=5)
    found = await soul._memory._semantic.get(mid)
    assert found is not None
    assert found.domain == "finance"
