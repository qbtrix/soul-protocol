# test_retrieval.py — Retrieval router + credential broker test suite.
# Created: feat/retrieval-router — Workstream C1 of Org Architecture RFC (#164).
# Covers: scope filtering, parallel/first/sequential strategies, per-source
# timeout, journal event emission on dispatch, broker acquire/use/expire
# flow + scope enforcement, and Protocol conformance for MockAdapter and
# ProjectionAdapter.

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from soul_protocol.engine.journal import Journal, open_journal
from soul_protocol.engine.retrieval import (
    CredentialExpiredError,
    CredentialScopeError,
    InMemoryCredentialBroker,
    NoSourcesError,
    ProjectionAdapter,
    RetrievalRouter,
    SourceAdapter,
)
from soul_protocol.engine.retrieval.adapters import MockAdapter
from soul_protocol.spec.journal import Actor
from soul_protocol.spec.retrieval import (
    CandidateSource,
    RetrievalCandidate,
    RetrievalRequest,
)


# -- fixtures -------------------------------------------------------------


def _actor() -> Actor:
    return Actor(kind="agent", id="did:soul:test-agent", scope_context=["org:sales:leads"])


def _candidate(source: str, score: float | None = 0.9) -> RetrievalCandidate:
    return RetrievalCandidate(
        source=source,
        content={"hit": source},
        score=score,
        as_of=datetime.now(UTC),
        cached=False,
    )


def _request(**overrides) -> RetrievalRequest:
    defaults = dict(
        query="who bought the thing",
        actor=_actor(),
        scopes=["org:sales:leads"],
        strategy="parallel",
        timeout_s=2.0,
    )
    defaults.update(overrides)
    return RetrievalRequest(**defaults)


@pytest.fixture
def journal(tmp_path: Path) -> Journal:
    j = open_journal(tmp_path / "journal.db")
    yield j
    j.close()


# -- router: strategies ---------------------------------------------------


def test_parallel_merges_candidates_from_two_sources() -> None:
    router = RetrievalRouter()
    router.register_source(
        CandidateSource(
            name="soul_memory",
            kind="projection",
            scopes=["org:sales:*"],
            adapter_ref="mock",
        ),
        MockAdapter(candidates=[_candidate("soul_memory", score=0.9)]),
    )
    router.register_source(
        CandidateSource(
            name="kb_articles",
            kind="projection",
            scopes=["org:sales:*"],
            adapter_ref="mock",
        ),
        MockAdapter(candidates=[_candidate("kb_articles", score=0.7)]),
    )

    result = router.dispatch(_request())

    assert {c.source for c in result.candidates} == {"soul_memory", "kb_articles"}
    assert set(result.sources_queried) == {"soul_memory", "kb_articles"}
    # Higher score sorts first.
    assert result.candidates[0].source == "soul_memory"
    assert result.sources_failed == []


def test_first_strategy_returns_first_non_empty() -> None:
    router = RetrievalRouter()
    first_adapter = MockAdapter(candidates=[])
    second_adapter = MockAdapter(candidates=[_candidate("kb_articles", 0.5)])
    third_adapter = MockAdapter(candidates=[_candidate("fabric", 0.9)])
    for name, adapter in [
        ("soul_memory", first_adapter),
        ("kb_articles", second_adapter),
        ("fabric", third_adapter),
    ]:
        router.register_source(
            CandidateSource(
                name=name, kind="projection", scopes=["org:sales:*"], adapter_ref="mock"
            ),
            adapter,
        )

    result = router.dispatch(_request(strategy="first"))

    # Should stop at kb_articles and never call fabric.
    assert [c.source for c in result.candidates] == ["kb_articles"]
    assert result.sources_queried == ["soul_memory", "kb_articles"]
    assert third_adapter.calls == []


def test_sequential_accumulates_up_to_limit() -> None:
    router = RetrievalRouter()
    router.register_source(
        CandidateSource(name="a", kind="projection", scopes=["org:sales:*"], adapter_ref="mock"),
        MockAdapter(candidates=[_candidate("a", 0.9), _candidate("a", 0.8)]),
    )
    never_called = MockAdapter(candidates=[_candidate("b", 0.7)])
    router.register_source(
        CandidateSource(name="b", kind="projection", scopes=["org:sales:*"], adapter_ref="mock"),
        never_called,
    )

    result = router.dispatch(_request(strategy="sequential", limit=2))
    assert len(result.candidates) == 2
    assert never_called.calls == []


def test_scope_filter_skips_unrelated_source() -> None:
    router = RetrievalRouter()
    allowed = MockAdapter(candidates=[_candidate("sales_src", 0.9)])
    forbidden = MockAdapter(candidates=[_candidate("support_src", 0.9)])
    router.register_source(
        CandidateSource(
            name="sales_src", kind="projection", scopes=["org:sales:*"], adapter_ref="mock"
        ),
        allowed,
    )
    router.register_source(
        CandidateSource(
            name="support_src",
            kind="projection",
            scopes=["org:support:*"],
            adapter_ref="mock",
        ),
        forbidden,
    )

    result = router.dispatch(_request(scopes=["org:sales:leads"]))

    assert result.sources_queried == ["sales_src"]
    assert forbidden.calls == []


def test_no_sources_raises() -> None:
    router = RetrievalRouter()
    router.register_source(
        CandidateSource(
            name="ops", kind="projection", scopes=["org:ops:*"], adapter_ref="mock"
        ),
        MockAdapter(),
    )
    with pytest.raises(NoSourcesError):
        router.dispatch(_request(scopes=["org:sales:leads"]))


def test_parallel_source_timeout_is_reported() -> None:
    router = RetrievalRouter()
    fast = MockAdapter(candidates=[_candidate("fast", 0.9)])
    slow = MockAdapter(candidates=[_candidate("slow", 0.9)], delay_s=1.0)
    router.register_source(
        CandidateSource(name="fast", kind="projection", scopes=["org:sales:*"], adapter_ref="m"),
        fast,
    )
    router.register_source(
        CandidateSource(name="slow", kind="projection", scopes=["org:sales:*"], adapter_ref="m"),
        slow,
    )

    result = router.dispatch(_request(strategy="parallel", timeout_s=0.2))

    assert any(name == "slow" for name, _ in result.sources_failed)
    assert {c.source for c in result.candidates} == {"fast"}


def test_first_strategy_timeout_falls_through() -> None:
    router = RetrievalRouter()
    router.register_source(
        CandidateSource(name="slow", kind="projection", scopes=["org:sales:*"], adapter_ref="m"),
        MockAdapter(candidates=[_candidate("slow")], delay_s=1.0),
    )
    router.register_source(
        CandidateSource(name="fast", kind="projection", scopes=["org:sales:*"], adapter_ref="m"),
        MockAdapter(candidates=[_candidate("fast")]),
    )

    result = router.dispatch(_request(strategy="first", timeout_s=0.2))
    assert [c.source for c in result.candidates] == ["fast"]
    assert any(name == "slow" for name, _ in result.sources_failed)


# -- router: journal emission --------------------------------------------


def test_dispatch_emits_retrieval_query_event(journal: Journal) -> None:
    router = RetrievalRouter(journal=journal)
    router.register_source(
        CandidateSource(
            name="soul_memory",
            kind="projection",
            scopes=["org:sales:*"],
            adapter_ref="mock",
        ),
        MockAdapter(candidates=[_candidate("soul_memory", 0.9)]),
    )
    correlation = uuid4()
    router.dispatch(_request(correlation_id=correlation))

    events = journal.query(action="retrieval.query")
    assert len(events) == 1
    ev = events[0]
    assert ev.action == "retrieval.query"
    assert ev.actor.id == "did:soul:test-agent"
    assert ev.scope == ["org:sales:leads"]
    assert ev.correlation_id == correlation
    assert isinstance(ev.payload, dict)
    assert ev.payload["query"] == "who bought the thing"
    assert ev.payload["sources_queried"] == ["soul_memory"]


# -- broker ---------------------------------------------------------------


def test_broker_acquire_returns_scoped_credential() -> None:
    broker = InMemoryCredentialBroker(ttl_s=60)
    cred = broker.acquire("drive", ["org:sales:leads"])
    assert cred.source == "drive"
    assert cred.scopes == ["org:sales:leads"]
    assert cred.token
    assert cred.expires_at > cred.acquired_at
    assert (cred.expires_at - cred.acquired_at).total_seconds() == pytest.approx(60, abs=1)


def test_broker_refuses_credential_used_by_wrong_scope() -> None:
    broker = InMemoryCredentialBroker()
    cred = broker.acquire("drive", ["org:sales:*"])
    broker.ensure_usable(cred, ["org:sales:leads"])  # overlap allowed
    with pytest.raises(CredentialScopeError):
        broker.ensure_usable(cred, ["org:support:tickets"])


def test_broker_credential_expires_after_ttl() -> None:
    broker = InMemoryCredentialBroker(ttl_s=0.05)
    cred = broker.acquire("drive", ["org:sales:leads"])
    time.sleep(0.1)
    with pytest.raises(CredentialExpiredError):
        broker.ensure_usable(cred, ["org:sales:leads"])


def test_broker_emits_journal_events(journal: Journal) -> None:
    actor = Actor(kind="system", id="system:credential-broker")
    broker = InMemoryCredentialBroker(ttl_s=60, journal=journal, broker_actor=actor)
    cred = broker.acquire("drive", ["org:sales:leads"])
    broker.ensure_usable(cred, ["org:sales:leads"])
    broker.mark_used(cred)
    broker.revoke(cred.id)

    actions = [e.action for e in journal.query()]
    assert "credential.acquired" in actions
    assert "credential.used" in actions
    assert "credential.expired" in actions


def test_broker_expiry_emits_event(journal: Journal) -> None:
    broker = InMemoryCredentialBroker(ttl_s=0.05, journal=journal)
    cred = broker.acquire("drive", ["org:sales:leads"])
    time.sleep(0.1)
    with pytest.raises(CredentialExpiredError):
        broker.ensure_usable(cred, ["org:sales:leads"])
    actions = [e.action for e in journal.query()]
    assert actions.count("credential.expired") == 1


# -- adapter conformance --------------------------------------------------


def test_mock_and_projection_are_source_adapters() -> None:
    mock = MockAdapter()
    proj = ProjectionAdapter(lambda req: [])
    assert isinstance(mock, SourceAdapter)
    assert isinstance(proj, SourceAdapter)


def test_projection_adapter_calls_underlying_fn() -> None:
    calls: list[RetrievalRequest] = []

    def fn(req: RetrievalRequest) -> list[RetrievalCandidate]:
        calls.append(req)
        return [_candidate("proj", 0.5)]

    adapter = ProjectionAdapter(fn)
    out = adapter.query(_request(), credential=None)
    assert [c.source for c in out] == ["proj"]
    assert len(calls) == 1


def test_dataref_source_triggers_broker(journal: Journal) -> None:
    broker = InMemoryCredentialBroker(ttl_s=60, journal=journal)
    router = RetrievalRouter(journal=journal, broker=broker)
    mock = MockAdapter(candidates=[_candidate("drive", 0.9)])
    mock.supports_dataref = True
    router.register_source(
        CandidateSource(
            name="drive", kind="dataref", scopes=["org:sales:*"], adapter_ref="drive"
        ),
        mock,
    )
    router.dispatch(_request(strategy="sequential"))

    actions = [e.action for e in journal.query()]
    assert "credential.acquired" in actions
    assert "credential.used" in actions
    assert "retrieval.query" in actions
    # MockAdapter saw a real credential.
    assert mock.calls
    _, cred = mock.calls[0]
    assert cred is not None
    assert cred.source == "drive"
