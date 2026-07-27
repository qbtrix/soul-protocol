# test_memory_journal.py — Tests for the spike JournalBackedMemoryStore.
# Created: feat/0.3.2-spike — 4 test layers per captain's discipline:
# unit (each method in isolation), smoke (basic sanity), e2e (full flow),
# real-world sim (cleanup-incident recovery, GDPR tombstone, canonical queries).

from __future__ import annotations

import time
from pathlib import Path

import pytest

from soul_protocol.spec.journal import Actor
from soul_protocol.spec.memory import MemoryEntry, MemoryStore
from soul_protocol.spike.memory_journal import (
    JournalBackedMemoryStore,
    open_memory_store,
)


@pytest.fixture
def actor() -> Actor:
    return Actor(kind="agent", id="did:soul:test-agent")


@pytest.fixture
def store(tmp_path: Path, actor: Actor) -> JournalBackedMemoryStore:
    s = open_memory_store(tmp_path / "mem", actor=actor)
    yield s
    s._journal.close()
    s._db.close()


def _make_entry(
    content: str,
    *,
    importance: int = 5,
    tags: list[str] | None = None,
    source: str = "user",
) -> MemoryEntry:
    return MemoryEntry(
        layer="core",
        content=content,
        source=source,
        metadata={"importance": importance, "tags": tags or []},
    )


# =============================================================================
# UNIT TESTS — each method in isolation
# =============================================================================


def test_unit_store_returns_stable_id(store: JournalBackedMemoryStore) -> None:
    mem_id = store.store("episodic", _make_entry("hello"))
    assert isinstance(mem_id, str)
    assert len(mem_id) > 0


def test_unit_store_populates_tier(store: JournalBackedMemoryStore) -> None:
    store.store("semantic", _make_entry("fact"))
    assert "semantic" in store.layers()


def test_unit_recall_returns_most_recent_first(
    store: JournalBackedMemoryStore,
) -> None:
    store.store("episodic", _make_entry("first"))
    store.store("episodic", _make_entry("second"))
    store.store("episodic", _make_entry("third"))

    results = store.recall("episodic", limit=10)
    assert [e.content for e in results] == ["third", "second", "first"]


def test_unit_search_ranks_by_bm25(store: JournalBackedMemoryStore) -> None:
    store.store("semantic", _make_entry("python programming language"))
    store.store("semantic", _make_entry("python snake in the wild"))
    store.store("semantic", _make_entry("ruby programming language"))

    results = store.search("python programming", limit=5)
    assert len(results) >= 1
    # Top result should contain both 'python' and 'programming'
    assert "python" in results[0].content.lower()
    assert "programming" in results[0].content.lower()


def test_unit_search_empty_query_returns_empty(
    store: JournalBackedMemoryStore,
) -> None:
    store.store("semantic", _make_entry("anything"))
    assert store.search("") == []
    assert store.search("   ") == []


def test_unit_delete_existing_returns_true(
    store: JournalBackedMemoryStore,
) -> None:
    mem_id = store.store("episodic", _make_entry("forget me"))
    assert store.delete(mem_id) is True
    assert store.recall("episodic") == []


def test_unit_delete_nonexistent_returns_false(
    store: JournalBackedMemoryStore,
) -> None:
    assert store.delete("nonexistent") is False


def test_unit_promote_moves_tier(store: JournalBackedMemoryStore) -> None:
    mem_id = store.store("episodic", _make_entry("important"))
    assert store.promote(mem_id, "semantic") is True

    assert store.recall("episodic") == []
    semantic = store.recall("semantic")
    assert len(semantic) == 1
    assert semantic[0].content == "important"


def test_unit_promote_same_tier_is_noop(
    store: JournalBackedMemoryStore,
) -> None:
    mem_id = store.store("episodic", _make_entry("x"))
    assert store.promote(mem_id, "episodic") is False


def test_unit_promote_missing_memory(store: JournalBackedMemoryStore) -> None:
    assert store.promote("nonexistent", "semantic") is False


def test_unit_audit_trail_includes_all_events(
    store: JournalBackedMemoryStore,
) -> None:
    mem_id = store.store("episodic", _make_entry("a"))
    store.promote(mem_id, "semantic")
    store.delete(mem_id)

    trail = store.audit_trail(mem_id)
    actions = [e.action for e in trail]
    assert actions == [
        "memory.remembered",
        "memory.graduated",
        "memory.forgotten",
    ]


# =============================================================================
# SMOKE TESTS — basic sanity
# =============================================================================


def test_smoke_store_recall_search_roundtrip(
    store: JournalBackedMemoryStore,
) -> None:
    store.store("episodic", _make_entry("Ripple widgets use SvelteFlow"))
    recalled = store.recall("episodic", limit=1)
    searched = store.search("SvelteFlow")

    assert len(recalled) == 1
    assert len(searched) == 1
    assert "SvelteFlow" in recalled[0].content
    assert "SvelteFlow" in searched[0].content


def test_smoke_delete_then_search_miss(store: JournalBackedMemoryStore) -> None:
    mem_id = store.store("episodic", _make_entry("temporary data"))
    assert len(store.search("temporary")) == 1
    store.delete(mem_id)
    assert store.search("temporary") == []


# =============================================================================
# E2E TESTS — full flow
# =============================================================================


def test_e2e_protocol_conformance(
    store: JournalBackedMemoryStore,
) -> None:
    """E2E: the store conforms to the MemoryStore Protocol structurally."""
    assert isinstance(store, MemoryStore)


def test_e2e_fifty_memories_with_mixed_ops(
    store: JournalBackedMemoryStore,
) -> None:
    ids = []
    for i in range(50):
        tier = "episodic" if i % 2 == 0 else "semantic"
        ids.append(store.store(tier, _make_entry(f"memory number {i}", importance=i % 10)))

    # Promote every 10th
    for mem_id in ids[::10]:
        store.promote(mem_id, "procedural")

    # Forget every 20th
    for mem_id in ids[::20]:
        store.delete(mem_id)

    layers = set(store.layers())
    assert {"episodic", "semantic", "procedural"}.issubset(layers) or layers == {
        "episodic",
        "semantic",
        "procedural",
    }

    # Search still hits survivors
    results = store.search("memory")
    assert len(results) > 0


def test_e2e_rebuild_reproduces_state(tmp_path: Path, actor: Actor) -> None:
    """E2E: drop projection tables, rebuild from journal, same state."""
    store = open_memory_store(tmp_path / "mem", actor=actor)

    ids = [store.store("episodic", _make_entry(f"event {i}", importance=i)) for i in range(20)]
    store.promote(ids[5], "semantic")
    store.delete(ids[10])

    pre_rebuild_episodic = {m.id for m in store.recall("episodic", limit=100)}
    pre_rebuild_semantic = {m.id for m in store.recall("semantic", limit=100)}

    count = store.rebuild()
    assert count >= 22  # 20 stored + 1 promoted + 1 forgotten

    assert {m.id for m in store.recall("episodic", limit=100)} == pre_rebuild_episodic
    assert {m.id for m in store.recall("semantic", limit=100)} == pre_rebuild_semantic

    store._journal.close()
    store._db.close()


def test_e2e_separate_session_sees_prior_writes(tmp_path: Path, actor: Actor) -> None:
    """E2E: close and reopen the store — data survives."""
    base = tmp_path / "mem"

    store1 = open_memory_store(base, actor=actor)
    mem_id = store1.store("semantic", _make_entry("persistent"))
    store1._journal.close()
    store1._db.close()

    store2 = open_memory_store(base, actor=actor)
    results = store2.recall("semantic", limit=10)
    assert len(results) == 1
    assert results[0].id == mem_id
    store2._journal.close()
    store2._db.close()


# =============================================================================
# REAL-WORLD SIM TESTS — actual failure modes we're trying to fix
# =============================================================================


def test_realworld_cleanup_incident_recovery(tmp_path: Path, actor: Actor) -> None:
    """Real-world sim: simulate the April 5 cleanup incident.

    Scenario: projection tables get dropped (or the cleanup heuristic deletes
    them). In the old system, this was data loss. In the new system, the
    journal is truth, so rebuild() restores everything.
    """
    store = open_memory_store(tmp_path / "mem", actor=actor)

    for i in range(100):
        store.store(
            "episodic" if i % 2 == 0 else "semantic",
            _make_entry(f"production memory {i}", importance=(i % 10) + 1),
        )

    pre_incident_count = sum(len(store.recall(tier, limit=200)) for tier in store.layers())
    assert pre_incident_count == 100

    # Simulate disaster: projections are nuked.
    store._db.execute("DELETE FROM memory_tier")
    store._db.execute("DELETE FROM fts_memories")
    store._db.commit()

    mid_incident_count = sum(len(store.recall(tier, limit=200)) for tier in store.layers())
    assert mid_incident_count == 0  # projections empty

    # Recovery: rebuild from journal.
    events_replayed = store.rebuild()
    assert events_replayed >= 100

    post_recovery_count = sum(len(store.recall(tier, limit=200)) for tier in store.layers())
    assert post_recovery_count == pre_incident_count

    store._journal.close()
    store._db.close()


def test_realworld_gdpr_forget_leaves_only_tombstone(
    store: JournalBackedMemoryStore,
) -> None:
    """Real-world sim: GDPR delete must remove content from projections,
    leave an audit-only tombstone in the journal with no content.
    """
    mem_id = store.store("semantic", _make_entry("user email was alice@example.com"))

    assert len(store.search("alice@example.com")) == 1
    store.delete(mem_id)
    assert len(store.search("alice@example.com")) == 0

    # Audit trail shows both events.
    trail = store.audit_trail(mem_id)
    assert len(trail) == 2
    assert trail[0].action == "memory.remembered"
    assert trail[1].action == "memory.forgotten"

    # The tombstone carries no content — only memory_id + reason.
    tombstone_payload = trail[1].payload
    assert "memory_id" in tombstone_payload
    assert "reason" in tombstone_payload
    assert "content" not in tombstone_payload


def test_realworld_idempotent_rebuild(
    store: JournalBackedMemoryStore,
) -> None:
    """Real-world sim: rebuilding twice yields the same state. No accidental
    drift across multiple rebuilds (e.g. during an upgrade dance).
    """
    for i in range(30):
        store.store("episodic", _make_entry(f"mem {i}"))

    state_a = {m.id for m in store.recall("episodic", limit=100)}

    store.rebuild()
    state_b = {m.id for m in store.recall("episodic", limit=100)}

    store.rebuild()
    state_c = {m.id for m in store.recall("episodic", limit=100)}

    assert state_a == state_b == state_c


def test_realworld_write_latency_under_budget(
    store: JournalBackedMemoryStore,
) -> None:
    """Real-world sim: 100 writes must complete in under 2 seconds on a
    cold store. This is a regression guard — if we blow this budget, we
    probably accidentally disabled WAL or did something silly.
    """
    start = time.monotonic()
    for i in range(100):
        store.store("episodic", _make_entry(f"burst {i}"))
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"100 writes took {elapsed:.2f}s (budget 2.0s)"


def test_realworld_recall_latency_under_budget(
    store: JournalBackedMemoryStore,
) -> None:
    """Real-world sim: recall on 500 memories must stay snappy."""
    for i in range(500):
        store.store("episodic", _make_entry(f"m{i} " + "lorem ipsum " * 3))

    start = time.monotonic()
    for _ in range(50):
        store.recall("episodic", limit=10)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"50 recalls on 500 memories took {elapsed:.2f}s"


def test_realworld_search_latency_under_budget(
    store: JournalBackedMemoryStore,
) -> None:
    """Real-world sim: bm25 search on 500 memories stays interactive."""
    topics = ["python", "rust", "database", "async", "widget", "journal"]
    for i in range(500):
        topic = topics[i % len(topics)]
        store.store("semantic", _make_entry(f"fact about {topic} number {i}"))

    start = time.monotonic()
    for topic in topics:
        store.search(topic, limit=5)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"search on 500 memories took {elapsed:.2f}s"
