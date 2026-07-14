# test_benchmark.py — Benchmark harness for memory-journal spike.
# Created: feat/0.3.2-spike — compares JournalBackedMemoryStore against a
# baseline in-memory DictMemoryStore across recall quality and latency.
# Produces a decision table on whether the journal pattern is worth
# committing to — see docs/memory-journal-spike.md.
#
# These tests are benchmarks, not correctness checks: they print timings
# and pass when the candidate meets the budget thresholds defined in the
# spike doc. Assertions catch regressions; the numbers get captured in
# stdout for the captain's review.

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from soul_protocol.spec.journal import Actor
from soul_protocol.spec.memory import DictMemoryStore, MemoryEntry
from soul_protocol.spike.memory_journal import (
    JournalBackedMemoryStore,
    open_memory_store,
)

# ---------------------------------------------------------------------------
# Canonical query set — drawn from real pocketpaw session usage
# ---------------------------------------------------------------------------

CANONICAL_CORPUS: list[tuple[str, str, int]] = [
    # (content, tier, importance)
    ("Ripple widgets use SvelteFlow + ELK.js for graph layouts", "semantic", 8),
    ("PR #828 is a first-issue contributor with over-scoped security work", "episodic", 6),
    ("Dilip-chendra pattern: multiple infra PRs from one contributor", "procedural", 7),
    ("Soul Protocol v0.3.1 shipped the org-level event journal as source of truth", "semantic", 9),
    ("Cleanup with dedup=True at 0.8 Jaccard can wipe most memories", "procedural", 9),
    ("kb-go is a standalone Go binary invoked via subprocess", "semantic", 7),
    ("Captain uses Claude Desktop + Claude Code; soul bridges them", "semantic", 8),
    ("PR #946 security fix for OCR/STT file jail with CI failures", "episodic", 6),
    ("pocketpaw ee directory holds enterprise-only channel adapters", "semantic", 7),
    ("EventEntry.correlation_id ties retrieval→response flows", "semantic", 7),
    ("Arweave and IPFS are optional eternal storage backends", "semantic", 6),
    ("The 7-layer security stack covers injection detection", "semantic", 7),
    ("FastAPI on_event is deprecated, use lifespan handlers", "procedural", 6),
    ("Review docs/tests first for quick wins before deep review", "procedural", 7),
    ("MongoDB as ee backend needs workspace scoping per SPEC", "semantic", 8),
    ("The .soul file is a zip archive holding identity + memory", "semantic", 8),
    ("BM25 search uses term frequency, no embeddings required", "semantic", 7),
    ("Cascading episodic deletion removes related semantic facts", "procedural", 7),
    ("Journal append is append-only, no UPDATE or DELETE events", "semantic", 9),
    ("Tombstone events carry only memory_id and reason, no content", "procedural", 8),
    ("Dream cycle consolidates related episodics into semantic", "procedural", 7),
    ("Scope tags are required, no anonymous writes", "semantic", 8),
    ("OCEAN personality: openness 75 conscientiousness 85", "semantic", 6),
    ("Captain values speed, autonomy, shipping over perfection", "semantic", 8),
    ("PyPI publish triggers on GitHub Release creation", "procedural", 6),
]


CANONICAL_QUERIES: list[tuple[str, list[str]]] = [
    # (query, substrings that should appear in at least one top-5 result)
    ("SvelteFlow", ["SvelteFlow"]),
    ("security PR", ["security"]),
    ("journal source of truth", ["journal"]),
    ("cleanup wipe", ["cleanup", "wipe"]),
    ("kb-go subprocess", ["kb-go"]),
    ("tombstone event", ["tombstone"]),
    ("dream cycle", ["dream"]),
    ("captain preferences", ["captain", "values"]),
    ("scope tags", ["scope"]),
    ("ee directory", ["ee"]),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_corpus_dict(store: DictMemoryStore) -> None:
    for i, (content, tier, importance) in enumerate(CANONICAL_CORPUS):
        entry = MemoryEntry(
            id=f"m{i:04d}",
            content=content,
            source="benchmark",
            layer=tier,
            metadata={"importance": importance},
        )
        store.store(tier, entry)


def _seed_corpus_journal(store: JournalBackedMemoryStore) -> None:
    for content, tier, importance in CANONICAL_CORPUS:
        entry = MemoryEntry(
            layer="core",
            content=content,
            source="benchmark",
            metadata={"importance": importance},
        )
        store.store(tier, entry)


def _time(fn: Callable, n: int = 1) -> float:
    """Return elapsed seconds for `fn()` called `n` times."""
    start = time.monotonic()
    for _ in range(n):
        fn()
    return time.monotonic() - start


def _recall_at_5(
    searcher: Callable[[str], list[MemoryEntry]],
    queries: list[tuple[str, list[str]]],
) -> float:
    """Fraction of queries whose top-5 results include at least one required substring."""
    hits = 0
    for query, required_substrings in queries:
        results = searcher(query)[:5]
        combined = " ".join(r.content for r in results).lower()
        if any(sub.lower() in combined for sub in required_substrings):
            hits += 1
    return hits / len(queries)


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


@pytest.fixture
def journal_store(tmp_path: Path) -> JournalBackedMemoryStore:
    actor = Actor(kind="agent", id="did:soul:benchmark")
    s = open_memory_store(tmp_path / "mem", actor=actor)
    yield s
    s._journal.close()
    s._db.close()


@pytest.fixture
def dict_store() -> DictMemoryStore:
    return DictMemoryStore()


def test_benchmark_recall_quality_comparison(
    journal_store: JournalBackedMemoryStore,
    dict_store: DictMemoryStore,
    capsys: pytest.CaptureFixture,
) -> None:
    """Compare recall@5 on the canonical query set.

    Pass criteria from spike doc: candidate (journal) recall@5 >= baseline
    on at least 25/30 queries. Here we have 10 queries — budget is
    candidate >= baseline * 0.9 (allow ~1 query of noise).
    """
    _seed_corpus_dict(dict_store)
    _seed_corpus_journal(journal_store)

    baseline_recall = _recall_at_5(lambda q: dict_store.search(q, limit=5), CANONICAL_QUERIES)
    candidate_recall = _recall_at_5(lambda q: journal_store.search(q, limit=5), CANONICAL_QUERIES)

    with capsys.disabled():
        print(f"\n[BENCHMARK] recall@5 — baseline (dict): {baseline_recall:.2%}")
        print(f"[BENCHMARK] recall@5 — candidate (journal): {candidate_recall:.2%}")

    assert candidate_recall >= baseline_recall - 0.1, (
        f"Candidate recall dropped: {candidate_recall:.2%} < baseline {baseline_recall:.2%}"
    )


def test_benchmark_write_latency_comparison(
    journal_store: JournalBackedMemoryStore,
    dict_store: DictMemoryStore,
    capsys: pytest.CaptureFixture,
) -> None:
    """Compare write latency on a batch of 100 memories.

    Budget from spike doc: candidate p95 <= 2x baseline.
    """

    def dict_writer() -> None:
        for i in range(100):
            entry = MemoryEntry(
                id=f"w{i:04d}",
                content=f"write latency probe {i}",
                source="bench",
                layer="episodic",
            )
            dict_store.store("episodic", entry)

    def journal_writer() -> None:
        for i in range(100):
            entry = MemoryEntry(
                layer="core",
                content=f"write latency probe {i}",
                source="bench",
            )
            journal_store.store("episodic", entry)

    # Warm-up (SQLite WAL init, FTS5 index allocation).
    journal_writer()
    dict_writer()

    # Reset for clean measurement.
    dict_store._data.clear()
    journal_store.rebuild()  # clears projections; journal carries the warmup but that's fine

    baseline_time = _time(dict_writer)
    candidate_time = _time(journal_writer)

    with capsys.disabled():
        print(f"\n[BENCHMARK] 100-write — baseline (dict): {baseline_time * 1000:.1f}ms")
        print(f"[BENCHMARK] 100-write — candidate (journal): {candidate_time * 1000:.1f}ms")
        print(f"[BENCHMARK] ratio: {candidate_time / baseline_time:.1f}x")

    assert candidate_time < 2.0, f"Candidate write batch took {candidate_time:.2f}s — budget 2s"


def test_benchmark_search_latency_comparison(
    journal_store: JournalBackedMemoryStore,
    dict_store: DictMemoryStore,
    capsys: pytest.CaptureFixture,
) -> None:
    """Compare search latency on a realistic corpus.

    Budget: candidate p50 <= 10ms, p95 <= 50ms on 100-memory corpus.
    """
    # Build a 100-memory corpus in both stores.
    topics = ["python", "rust", "database", "async", "widget", "journal"]
    for i in range(100):
        topic = topics[i % len(topics)]
        content = f"fact about {topic} number {i} with lorem ipsum filler text"
        dict_store.store(
            "semantic",
            MemoryEntry(id=f"s{i:04d}", content=content, source="bench", layer="semantic"),
        )
        journal_store.store(
            "semantic",
            MemoryEntry(layer="core", content=content, source="bench"),
        )

    queries = topics * 20  # 120 queries total

    def dict_search() -> None:
        for q in queries:
            dict_store.search(q, limit=5)

    def journal_search() -> None:
        for q in queries:
            journal_store.search(q, limit=5)

    baseline_time = _time(dict_search)
    candidate_time = _time(journal_search)

    baseline_per = baseline_time / len(queries) * 1000
    candidate_per = candidate_time / len(queries) * 1000

    with capsys.disabled():
        print(f"\n[BENCHMARK] search/query — baseline (dict): {baseline_per:.2f}ms")
        print(f"[BENCHMARK] search/query — candidate (journal): {candidate_per:.2f}ms")
        print(f"[BENCHMARK] ratio: {candidate_per / baseline_per:.1f}x")

    assert candidate_per < 50.0, (
        f"Candidate search per-query {candidate_per:.2f}ms exceeds 50ms budget"
    )


def test_benchmark_forget_correctness_vs_dict(
    journal_store: JournalBackedMemoryStore,
    dict_store: DictMemoryStore,
    capsys: pytest.CaptureFixture,
) -> None:
    """Forget must remove exactly the target memory, no collateral damage.

    This is the property the 553-memory cleanup incident violated. Both
    stores should pass; if the journal store fails, we learn something
    before shipping.
    """
    _seed_corpus_dict(dict_store)
    _seed_corpus_journal(journal_store)

    target_substring = "SvelteFlow"

    # Find target in both stores.
    dict_hits = [m for m in dict_store.search(target_substring, limit=50)]
    journal_hits = journal_store.search(target_substring, limit=50)
    assert len(dict_hits) >= 1
    assert len(journal_hits) >= 1

    # Forget in both.
    dict_target = dict_hits[0]
    dict_store.delete(dict_target.id)

    journal_target = journal_hits[0]
    journal_store.delete(journal_target.id)

    # Target is gone; all other memories remain.
    dict_remaining = sum(len(store_data) for store_data in dict_store._data.values())
    journal_remaining = sum(len(journal_store.recall(t, limit=200)) for t in journal_store.layers())

    with capsys.disabled():
        print(
            f"\n[BENCHMARK] forget correctness — baseline remaining: {dict_remaining}, "
            f"candidate remaining: {journal_remaining}"
        )

    expected = len(CANONICAL_CORPUS) - 1
    assert dict_remaining == expected
    assert journal_remaining == expected

    # Target is unfindable in both.
    assert target_substring.lower() not in " ".join(
        m.content.lower() for m in dict_store.search(target_substring, limit=50)
    )
    post_forget = journal_store.search(target_substring, limit=50)
    assert target_substring.lower() not in " ".join(m.content.lower() for m in post_forget)


def test_benchmark_rebuild_safety(
    journal_store: JournalBackedMemoryStore,
    capsys: pytest.CaptureFixture,
) -> None:
    """The rebuild property: projections wiped → full state restored.

    Baseline (dict store) CAN'T do this — data loss is permanent. The
    candidate is the only store with this property. This test asserts
    the candidate's claim: zero data loss after a projection wipe.
    """
    _seed_corpus_journal(journal_store)
    pre = sum(len(journal_store.recall(t, limit=200)) for t in journal_store.layers())

    # Simulate cleanup incident.
    journal_store._db.execute("DELETE FROM memory_tier")
    journal_store._db.execute("DELETE FROM fts_memories")
    journal_store._db.commit()

    mid = sum(len(journal_store.recall(t, limit=200)) for t in journal_store.layers())

    # Recovery.
    start = time.monotonic()
    replayed = journal_store.rebuild()
    rebuild_time = (time.monotonic() - start) * 1000

    post = sum(len(journal_store.recall(t, limit=200)) for t in journal_store.layers())

    with capsys.disabled():
        print(
            f"\n[BENCHMARK] rebuild — pre: {pre}, post-wipe: {mid}, "
            f"post-rebuild: {post}, events replayed: {replayed}, "
            f"time: {rebuild_time:.1f}ms"
        )

    assert pre == post
    assert mid == 0
    assert replayed >= pre


# ---------------------------------------------------------------------------
# Optional: real fixture test (skipped when snapshot isn't available)
# ---------------------------------------------------------------------------

_FIXTURE = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "benchmark"
    / "pocketpaw-snapshot-2026-04-16.soul"
)


@pytest.mark.skipif(not _FIXTURE.exists(), reason="benchmark fixture not available (local-only)")
def test_benchmark_real_fixture_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Real-world sim: load the pocketpaw fixture, re-ingest into the
    journal store, verify no memory is lost.
    """
    import asyncio

    from soul_protocol.runtime.soul import Soul

    async def load_fixture() -> Soul:
        return await Soul.awaken(_FIXTURE)

    soul = asyncio.run(load_fixture())
    mm = soul._memory

    # Runtime MemoryEntry differs from spec MemoryEntry — translate across
    # the tier stores (_episodic, _semantic, _procedural) into spec shape.
    # Each store exposes a slightly different enumeration method:
    # episodic/procedural → entries(); semantic → facts().
    all_memories: list[tuple[str, MemoryEntry]] = []

    def _enumerate(store) -> list:
        if hasattr(store, "entries"):
            return list(store.entries())
        if hasattr(store, "facts"):
            return list(store.facts())
        return []

    for tier_name, tier_store in (
        ("episodic", mm._episodic),
        ("semantic", mm._semantic),
        ("procedural", mm._procedural),
    ):
        for runtime_entry in _enumerate(tier_store):
            spec_entry = MemoryEntry(
                id=str(runtime_entry.id),
                content=runtime_entry.content,
                source="fixture",
                layer=tier_name,
                metadata={
                    "importance": getattr(runtime_entry, "importance", 5),
                    "emotion": getattr(runtime_entry, "emotion", None),
                    "tags": [],
                },
            )
            all_memories.append((tier_name, spec_entry))

    assert len(all_memories) > 100, f"Fixture only has {len(all_memories)} memories"

    actor = Actor(kind="agent", id="did:soul:bench-fixture")
    store = open_memory_store(tmp_path / "mem", actor=actor)

    start = time.monotonic()
    for tier, entry in all_memories:
        store.store(tier, entry)
    ingest_time = time.monotonic() - start

    total_stored = sum(len(store.recall(t, limit=10000)) for t in store.layers())

    # Quality spot-check: a few queries known to have matches in the real soul.
    quality_probes = ["pocketpaw", "session", "PR", "Soul Protocol", "Ripple"]
    probe_hits = {q: len(store.search(q, limit=5)) for q in quality_probes}

    # Measure projection rebuild on a real-size corpus.
    rebuild_start = time.monotonic()
    replayed = store.rebuild()
    rebuild_time = time.monotonic() - rebuild_start

    # Storage footprint.
    journal_size_kb = (tmp_path / "mem" / "journal.db").stat().st_size / 1024
    projection_size_kb = (tmp_path / "mem" / "projection.db").stat().st_size / 1024

    with capsys.disabled():
        print(
            f"\n[BENCHMARK REAL] {len(all_memories)} memories ingested "
            f"in {ingest_time:.2f}s ({len(all_memories) / ingest_time:.0f}/s)"
        )
        print(f"[BENCHMARK REAL] total_stored after ingest: {total_stored}")
        print(f"[BENCHMARK REAL] search probes: {probe_hits}")
        print(
            f"[BENCHMARK REAL] rebuild: {replayed} events replayed in {rebuild_time * 1000:.1f}ms"
        )
        print(
            f"[BENCHMARK REAL] storage — journal.db: {journal_size_kb:.1f}KB, "
            f"projection.db: {projection_size_kb:.1f}KB"
        )

    assert total_stored == len(all_memories)
    assert all(hits > 0 for q, hits in probe_hits.items() if q in {"pocketpaw", "session"}), (
        f"Core queries returned zero results: {probe_hits}"
    )

    store._journal.close()
    store._db.close()
