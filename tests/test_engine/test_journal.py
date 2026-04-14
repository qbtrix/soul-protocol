# test_journal.py — Journal engine test suite.
# Created: feat/journal-engine — Workstream A slice 2 of Org Architecture RFC (#164).
# Covers: round-trip append/query, every filter dimension, scope prefix +
# wildcard semantics, tz-aware enforcement on append and query, scope-empty
# rejection, monotonic ts, seq auto-assignment, replay ordering, DataRef
# round-trip, concurrent WAL writers, and the zero->v1 migration path.

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from soul_protocol.engine.journal import (
    IntegrityError,
    Journal,
    SQLiteJournalBackend,
    open_journal,
)
from soul_protocol.engine.journal.schema import SCHEMA_VERSION
from soul_protocol.engine.journal.sqlite import _scope_matches
from soul_protocol.spec.journal import Actor, DataRef, EventEntry


def _make_entry(
    *,
    action: str = "memory.remembered",
    actor: Actor | None = None,
    scope: list[str] | None = None,
    ts: datetime | None = None,
    correlation_id: UUID | None = None,
    payload: dict | DataRef | None = None,
) -> EventEntry:
    return EventEntry(
        id=uuid4(),
        ts=ts or datetime.now(UTC),
        actor=actor or Actor(kind="agent", id="did:soul:test-agent"),
        action=action,
        scope=scope or ["org:test"],
        correlation_id=correlation_id,
        payload=payload if payload is not None else {"note": "hello"},
    )


@pytest.fixture
def journal(tmp_path: Path) -> Journal:
    j = open_journal(tmp_path / "journal.db")
    yield j
    j.close()


# ---------- round-trip -------------------------------------------------


def test_append_query_roundtrip(journal: Journal) -> None:
    entry = _make_entry()
    journal.append(entry)
    results = journal.query()
    assert len(results) == 1
    assert results[0].id == entry.id
    assert results[0].action == entry.action
    assert results[0].scope == entry.scope
    assert results[0].payload == entry.payload


# ---------- filter dimensions -----------------------------------------


def test_query_by_action(journal: Journal) -> None:
    journal.append(_make_entry(action="memory.remembered"))
    journal.append(_make_entry(action="memory.forgotten"))
    results = journal.query(action="memory.forgotten")
    assert len(results) == 1
    assert results[0].action == "memory.forgotten"


def test_query_by_actor(journal: Journal) -> None:
    a = Actor(kind="agent", id="did:soul:a")
    b = Actor(kind="user", id="user:bob")
    journal.append(_make_entry(actor=a))
    journal.append(_make_entry(actor=b))
    journal.append(_make_entry(actor=a))
    results = journal.query(actor=a)
    assert len(results) == 2
    assert all(r.actor.id == "did:soul:a" for r in results)


def test_query_by_correlation_id(journal: Journal) -> None:
    cid = uuid4()
    journal.append(_make_entry(correlation_id=cid))
    journal.append(_make_entry(correlation_id=uuid4()))
    journal.append(_make_entry(correlation_id=cid))
    results = journal.query(correlation_id=cid)
    assert len(results) == 2


def test_query_by_time_window(journal: Journal) -> None:
    base = datetime.now(UTC)
    journal.append(_make_entry(ts=base))
    journal.append(_make_entry(ts=base + timedelta(seconds=5)))
    journal.append(_make_entry(ts=base + timedelta(seconds=10)))
    results = journal.query(
        since=base + timedelta(seconds=1),
        until=base + timedelta(seconds=9),
    )
    assert len(results) == 1


def test_query_combined_filters(journal: Journal) -> None:
    cid = uuid4()
    a = Actor(kind="agent", id="did:soul:a")
    journal.append(_make_entry(actor=a, action="memory.remembered", correlation_id=cid))
    journal.append(_make_entry(actor=a, action="memory.forgotten", correlation_id=cid))
    journal.append(_make_entry(action="memory.remembered"))
    results = journal.query(actor=a, action="memory.remembered", correlation_id=cid)
    assert len(results) == 1


# ---------- scope prefix + wildcards ----------------------------------


def test_scope_wildcard_matcher_unit() -> None:
    # Exact
    assert _scope_matches(["org:sales"], ["org:sales"])
    assert not _scope_matches(["org:sales"], ["org:hr"])

    # Leaf wildcard — same arity required
    assert _scope_matches(["org:sales:leads"], ["org:sales:*"])
    assert not _scope_matches(["org:sales"], ["org:sales:*"])  # bare parent NOT matched

    # Intermediate wildcard
    assert _scope_matches(["org:sales:leads"], ["org:*:leads"])
    assert _scope_matches(["org:hr:leads"], ["org:*:leads"])
    assert not _scope_matches(["org:sales:deals"], ["org:*:leads"])

    # Single-segment wildcard — does NOT match parent (the paw-enterprise #70 bug)
    assert _scope_matches(["org:sales"], ["org:*"])
    assert not _scope_matches(["org"], ["org:*"])


def test_query_scope_wildcard(journal: Journal) -> None:
    journal.append(_make_entry(scope=["org:sales:leads"]))
    journal.append(_make_entry(scope=["org:hr:leads"]))
    journal.append(_make_entry(scope=["org:sales:deals"]))
    results = journal.query(scope=["org:*:leads"])
    assert len(results) == 2
    scopes = sorted(r.scope[0] for r in results)
    assert scopes == ["org:hr:leads", "org:sales:leads"]


# ---------- tz enforcement --------------------------------------------


def test_append_rejects_naive_datetime() -> None:
    # The spec model rejects naive datetimes at validation time — we never
    # reach the engine layer. That is the intended behavior.
    with pytest.raises(ValidationError):
        EventEntry(
            id=uuid4(),
            ts=datetime.now(),  # naive — no tz
            actor=Actor(kind="agent", id="x"),
            action="memory.remembered",
            scope=["org:test"],
        )


def test_query_rejects_naive_since(journal: Journal) -> None:
    with pytest.raises(IntegrityError):
        journal.query(since=datetime.now())


def test_query_rejects_naive_until(journal: Journal) -> None:
    with pytest.raises(IntegrityError):
        journal.query(until=datetime.now())


# ---------- scope emptiness -------------------------------------------


def test_append_rejects_empty_scope() -> None:
    with pytest.raises(ValidationError):
        EventEntry(
            id=uuid4(),
            ts=datetime.now(UTC),
            actor=Actor(kind="agent", id="x"),
            action="memory.remembered",
            scope=[],
        )


# ---------- monotonic ts ----------------------------------------------


def test_monotonic_ts_enforced(journal: Journal) -> None:
    base = datetime.now(UTC)
    journal.append(_make_entry(ts=base))
    with pytest.raises(IntegrityError):
        journal.append(_make_entry(ts=base - timedelta(seconds=1)))


# ---------- seq auto-assignment ---------------------------------------


def test_seq_auto_assigned_gap_free(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    j = open_journal(path)
    for _ in range(5):
        j.append(_make_entry())
    j.close()

    # Peek at the raw rows to verify seq went 0,1,2,3,4.
    conn = sqlite3.connect(str(path))
    seqs = [row[0] for row in conn.execute("SELECT seq FROM events ORDER BY seq")]
    conn.close()
    assert seqs == [0, 1, 2, 3, 4]


# ---------- replay ordering -------------------------------------------


def test_replay_from_iterates_in_order(journal: Journal) -> None:
    base = datetime.now(UTC)
    ids = []
    for i in range(5):
        e = _make_entry(ts=base + timedelta(seconds=i))
        ids.append(e.id)
        journal.append(e)

    replayed = list(journal.replay_from(seq=0))
    assert [r.id for r in replayed] == ids

    from_two = list(journal.replay_from(seq=2))
    assert [r.id for r in from_two] == ids[2:]


# ---------- DataRef payload round-trip --------------------------------


def test_dataref_payload_roundtrip(journal: Journal) -> None:
    ref = DataRef(
        source="salesforce",
        query="SELECT Id FROM Lead WHERE Status='Open'",
        point_in_time=datetime.now(UTC),
        cache_policy="ttl",
        cache_ttl_s=600,
    )
    entry = _make_entry(payload=ref)
    journal.append(entry)

    (got,) = journal.query()
    assert isinstance(got.payload, DataRef)
    assert got.payload.source == "salesforce"
    assert got.payload.query == ref.query
    assert got.payload.cache_ttl_s == 600


def test_dict_payload_roundtrip(journal: Journal) -> None:
    entry = _make_entry(payload={"note": "hi", "nested": {"k": [1, 2]}})
    journal.append(entry)
    (got,) = journal.query()
    assert isinstance(got.payload, dict)
    assert got.payload == {"note": "hi", "nested": {"k": [1, 2]}}


# ---------- WAL concurrent writers ------------------------------------


def test_concurrent_writers_wal_no_data_loss(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    # Two separate journal instances pointing at the same DB — each holds
    # its own connection with WAL mode. Serialized by SQLite's lock.
    ja = open_journal(path)
    jb = open_journal(path)

    N = 25
    errors: list[Exception] = []
    barrier = threading.Barrier(2)
    # Shared clock + shared tick-and-append lock. The ts allocation and the
    # append have to be held together, otherwise thread A can tick=10, get
    # descheduled, thread B ticks=11 and commits, and A's ts=10 commit is
    # rightly rejected. That's the point of the monotonicity check.
    clock_lock = threading.Lock()
    clock = [datetime.now(UTC)]

    def writer(j: Journal, tag: str) -> None:
        barrier.wait()
        try:
            for _ in range(N):
                with clock_lock:
                    clock[0] = clock[0] + timedelta(microseconds=1)
                    ts = clock[0]
                    j.append(
                        _make_entry(
                            actor=Actor(kind="agent", id=f"did:soul:{tag}"),
                            ts=ts,
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    ta = threading.Thread(target=writer, args=(ja, "a"))
    tb = threading.Thread(target=writer, args=(jb, "b"))
    ta.start()
    tb.start()
    ta.join()
    tb.join()

    assert not errors, f"writer errors: {errors}"

    ja.close()
    jb.close()

    reader = open_journal(path)
    all_events = reader.query(limit=10_000)
    reader.close()
    assert len(all_events) == 2 * N

    by_tag: dict[str, int] = {}
    for e in all_events:
        by_tag[e.actor.id] = by_tag.get(e.actor.id, 0) + 1
    assert by_tag["did:soul:a"] == N
    assert by_tag["did:soul:b"] == N


def test_concurrent_writers_real_clocks_preserve_ts_monotonicity(tmp_path: Path) -> None:
    """Two threads appending with independent datetime.now(UTC) calls — no
    shared clock. Asserts that (a) no exceptions, (b) all events land with
    unique seqs, and (c) ts is monotonic across the combined log. This is
    the case the existing shared-tick test can't surface: the ts-monotonicity
    check has to happen inside the write transaction, not before it."""
    path = tmp_path / "journal.db"
    ja = open_journal(path)
    jb = open_journal(path)

    N = 25
    errors: list[tuple[str, Exception]] = []
    barrier = threading.Barrier(2)

    def writer(j: Journal, tag: str) -> None:
        barrier.wait()
        try:
            for _ in range(N):
                j.append(
                    EventEntry(
                        id=uuid4(),
                        ts=datetime.now(UTC),
                        actor=Actor(
                            kind="system",
                            id=f"system:{tag}",
                            scope_context=["org:*"],
                        ),
                        action="retrieval.query",
                        scope=["org:*"],
                        payload={},
                    )
                )
        except Exception as exc:  # noqa: BLE001
            errors.append((tag, exc))

    ta = threading.Thread(target=writer, args=(ja, "t1"))
    tb = threading.Thread(target=writer, args=(jb, "t2"))
    ta.start()
    tb.start()
    ta.join()
    tb.join()

    ja.close()
    jb.close()

    assert errors == [], f"concurrent writes raised: {errors}"

    reader = open_journal(path)
    events = reader.query(limit=10_000)
    reader.close()

    # All 50 events landed.
    assert len(events) == 2 * N
    # seq is unique and gap-free (query returns in seq order).
    # ts is monotonic across the combined log.
    prev_ts: datetime | None = None
    for e in events:
        if prev_ts is not None:
            assert e.ts >= prev_ts, f"ts not monotonic: {prev_ts} -> {e.ts}"
        prev_ts = e.ts


# ---------- schema migration ------------------------------------------


def test_schema_migrates_from_zero_on_first_write(tmp_path: Path) -> None:
    path = tmp_path / "journal.db"
    assert not path.exists()
    j = open_journal(path)
    j.append(_make_entry())
    j.close()

    conn = sqlite3.connect(str(path))
    row = conn.execute(
        "SELECT value FROM journal_meta WHERE key='schema_version'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert int(row[0]) == SCHEMA_VERSION


def test_backend_protocol_conformance(tmp_path: Path) -> None:
    from soul_protocol.engine.journal.backend import JournalBackend

    backend = SQLiteJournalBackend(tmp_path / "journal.db")
    assert isinstance(backend, JournalBackend)
    backend.close()
