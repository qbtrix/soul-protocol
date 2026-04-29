# tests/test_memory_layers/test_domain_isolation_middleware.py — Sandbox a Soul.
# Created: 2026-04-29 (#41) — Verifies DomainIsolationMiddleware blocks reads
# and writes outside the allow-list. Reads silently filter; writes raise
# DomainAccessError. Default domain falls through to the first allowed
# entry.

from __future__ import annotations

import pytest

from soul_protocol.runtime.exceptions import DomainAccessError
from soul_protocol.runtime.middleware import DomainIsolationMiddleware
from soul_protocol.runtime.soul import Soul
from soul_protocol.runtime.types import MemoryEntry, MemoryType


@pytest.fixture
async def soul_with_mixed_domains():
    soul = await Soul.birth(name="Iso", archetype="middleware test")
    layout: list[tuple[str, str]] = [
        ("finance", "Q3 revenue up 12 percent"),
        ("finance", "AWS bill jumped fifty thousand"),
        ("legal", "NDA expires in six months"),
        ("legal", "Vendor auto-renew clause"),
        ("default", "User likes Python"),
    ]
    for domain, content in layout:
        await soul._memory.add(
            MemoryEntry(
                type=MemoryType.SEMANTIC,
                content=content,
                importance=8,
                domain=domain,
            )
        )
    return soul


@pytest.mark.asyncio
async def test_middleware_recall_filters_to_allowed_domains(
    soul_with_mixed_domains,
):
    finance_only = DomainIsolationMiddleware(soul_with_mixed_domains, allowed_domains=["finance"])
    results = await finance_only.recall("revenue OR NDA OR AWS OR Python OR vendor", limit=20)
    assert results
    assert all(r.domain == "finance" for r in results)


@pytest.mark.asyncio
async def test_middleware_disallowed_domain_recall_returns_empty(
    soul_with_mixed_domains,
):
    finance_only = DomainIsolationMiddleware(soul_with_mixed_domains, allowed_domains=["finance"])
    # Asking for legal directly returns nothing — no leak across boundary.
    results = await finance_only.recall("NDA OR vendor", domain="legal", limit=5)
    assert results == []


@pytest.mark.asyncio
async def test_middleware_remember_default_domain_uses_first_allowed(
    soul_with_mixed_domains,
):
    finance_only = DomainIsolationMiddleware(
        soul_with_mixed_domains, allowed_domains=["finance", "default"]
    )
    mid = await finance_only.remember("New OPEX line item", importance=7)
    found = await soul_with_mixed_domains._memory._semantic.get(mid)
    assert found is not None
    assert found.domain == "finance"


@pytest.mark.asyncio
async def test_middleware_remember_disallowed_domain_raises(
    soul_with_mixed_domains,
):
    finance_only = DomainIsolationMiddleware(soul_with_mixed_domains, allowed_domains=["finance"])
    with pytest.raises(DomainAccessError) as exc:
        await finance_only.remember("An NDA fact", domain="legal", importance=5)
    assert "legal" in str(exc.value)
    assert "finance" in str(exc.value)


@pytest.mark.asyncio
async def test_middleware_observe_disallowed_domain_raises(
    soul_with_mixed_domains,
):
    from soul_protocol.runtime.types import Interaction

    finance_only = DomainIsolationMiddleware(soul_with_mixed_domains, allowed_domains=["finance"])
    interaction = Interaction.from_pair("hi", "hello")
    with pytest.raises(DomainAccessError):
        await finance_only.observe(interaction, domain="legal")


@pytest.mark.asyncio
async def test_middleware_observe_default_routes_to_first_allowed():
    soul = await Soul.birth(name="ObsRoute", archetype="middleware obs route")
    finance_only = DomainIsolationMiddleware(soul, allowed_domains=["finance"])

    from soul_protocol.runtime.types import Interaction

    # "my name is X" hits a deterministic heuristic FACT_PATTERN, which
    # avoids relying on the LLM-driven extraction in this unit test.
    await finance_only.observe(Interaction.from_pair("my name is Alex", "Hi Alex."))

    # Episodic + any extracted facts must all be stamped finance.
    facts = soul._memory._semantic.facts()
    epi = soul._memory._episodic.entries()
    stamped = facts + epi
    assert stamped, "expected at least one stored memory"
    assert all(m.domain == "finance" for m in stamped), [(m.content, m.domain) for m in stamped]


@pytest.mark.asyncio
async def test_middleware_construction_requires_at_least_one_domain():
    soul = await Soul.birth(name="Empty", archetype="empty allow list")
    with pytest.raises(ValueError):
        DomainIsolationMiddleware(soul, allowed_domains=[])


@pytest.mark.asyncio
async def test_middleware_recall_with_two_allowed_domains_returns_union(
    soul_with_mixed_domains,
):
    middleware = DomainIsolationMiddleware(
        soul_with_mixed_domains, allowed_domains=["finance", "default"]
    )
    results = await middleware.recall(
        "revenue OR Python OR NDA OR vendor OR likes OR AWS", limit=20
    )
    assert results
    found_domains = {r.domain for r in results}
    assert found_domains <= {"finance", "default"}
    # Legal must never leak through.
    assert "legal" not in found_domains
