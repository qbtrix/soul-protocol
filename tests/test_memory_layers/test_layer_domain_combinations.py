# tests/test_memory_layers/test_layer_domain_combinations.py — Layer x domain matrix.
# Created: 2026-04-29 (#41) — Verifies that recall combines layer and
# domain filters correctly. recall(layer=..., domain=...) returns only
# entries matching both. recall(layer=...) returns all entries in that
# layer regardless of domain. recall(domain=...) returns all matching
# domain entries regardless of layer.

from __future__ import annotations

import pytest

from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryEntry, MemoryType


@pytest.fixture
async def matrix_soul():
    """A soul with entries spanning 3 layers x 2 domains.

    Layer / domain layout:
      semantic   x finance:   2
      semantic   x legal:     2
      procedural x finance:   2
      procedural x legal:     1
      social     x finance:   1
      social     x legal:     1
    """
    soul = await Soul.birth(name="Matrix", archetype="layer-domain test")

    layout: list[tuple[MemoryType, str, str]] = [
        (MemoryType.SEMANTIC, "finance", "AWS bill jumped"),
        (MemoryType.SEMANTIC, "finance", "Q3 revenue up"),
        (MemoryType.SEMANTIC, "legal", "NDA expires soon"),
        (MemoryType.SEMANTIC, "legal", "Auto-renew clause"),
        (MemoryType.PROCEDURAL, "finance", "Run the close every month"),
        (MemoryType.PROCEDURAL, "finance", "Reconcile payable weekly"),
        (MemoryType.PROCEDURAL, "legal", "Send NDA before sharing"),
        (MemoryType.SOCIAL, "finance", "Alice prefers async budget reviews"),
        (MemoryType.SOCIAL, "legal", "Bob handles vendor contracts"),
    ]
    for tier, domain, text in layout:
        await soul._memory.add(MemoryEntry(type=tier, content=text, importance=8, domain=domain))
    return soul


@pytest.mark.asyncio
async def test_layer_and_domain_intersection(matrix_soul):
    """recall(layer="semantic", domain="finance") returns only that combo."""
    results = await matrix_soul.recall(
        "AWS OR revenue OR NDA OR clause OR close OR Alice OR Bob",
        layer="semantic",
        domain="finance",
        limit=20,
    )
    assert results
    for r in results:
        assert r.layer == "semantic"
        assert r.domain == "finance"


@pytest.mark.asyncio
async def test_layer_only_returns_all_domains_in_layer(matrix_soul):
    """recall(layer="semantic") returns every semantic entry, any domain."""
    results = await matrix_soul.recall(
        "AWS OR revenue OR NDA OR clause OR close OR Alice OR Bob",
        layer="semantic",
        limit=20,
    )
    assert results
    layers = {r.layer for r in results}
    assert layers == {"semantic"}, f"unexpected layers: {layers}"
    domains = {r.domain for r in results}
    assert "finance" in domains
    assert "legal" in domains


@pytest.mark.asyncio
async def test_domain_only_returns_all_layers_for_that_domain(matrix_soul):
    """recall(domain="finance") returns every finance entry across layers."""
    results = await matrix_soul.recall(
        "AWS OR revenue OR NDA OR clause OR close OR Alice OR Bob OR async OR reconcile",
        domain="finance",
        limit=20,
    )
    assert results
    for r in results:
        assert r.domain == "finance", f"non-finance entry leaked: {r.domain}"


@pytest.mark.asyncio
async def test_neither_filter_returns_full_union(matrix_soul):
    results = await matrix_soul.recall(
        "AWS OR revenue OR NDA OR clause OR close OR Alice OR Bob OR async OR reconcile",
        limit=30,
    )
    assert results
    layers = {r.layer for r in results}
    domains = {r.domain for r in results}
    assert "finance" in domains
    assert "legal" in domains
    # Should reach at least two layers when no filter is applied.
    assert len(layers) >= 2


@pytest.mark.asyncio
async def test_social_layer_with_domain_filter(matrix_soul):
    """The social layer participates in layer/domain filtering."""
    results = await matrix_soul.recall(
        "Alice OR Bob OR prefers OR vendor",
        layer="social",
        domain="finance",
        limit=10,
    )
    assert results
    for r in results:
        assert r.layer == "social"
        assert r.domain == "finance"


@pytest.mark.asyncio
async def test_custom_layer_with_domain_filter():
    """A user-defined layer obeys domain filtering on recall."""
    soul = await Soul.birth(name="Cu", archetype="custom layer test")
    custom = soul._memory.layer("preferences")
    await custom.store(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="dark mode for finance dashboards",
            importance=7,
            domain="finance",
        )
    )
    await custom.store(
        MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="long-form summaries for legal briefs",
            importance=7,
            domain="legal",
        )
    )

    finance_results = await soul.recall(
        "dark mode OR summaries", layer="preferences", domain="finance", limit=5
    )
    assert finance_results
    assert all(r.domain == "finance" for r in finance_results)
    assert all(r.layer == "preferences" for r in finance_results)
