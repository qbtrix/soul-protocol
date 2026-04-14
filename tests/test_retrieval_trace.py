"""Tests for RetrievalTrace spec + runtime emission (Move 4 PR-A).

Created: 2026-04-13 — Locks the trace model shape, its mark_used helper, and
the runtime contract that Soul.recall populates last_retrieval with a receipt
on every call (including the empty-results path).
Updated: feat/retrieval-trace-spec — Imports moved to spec.trace (the
standalone module) so the spec.retrieval router models keep their own
namespace. RetrievalCandidate renamed TraceCandidate to disambiguate from
the router's RetrievalCandidate. smart_recall coverage deferred until the
runtime exposes it on dev.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from soul_protocol import Soul
from soul_protocol.spec.memory import MemoryEntry
from soul_protocol.spec.trace import RetrievalTrace, TraceCandidate

# ---------------------------------------------------------------------------
# Spec — model shape
# ---------------------------------------------------------------------------


class TestRetrievalTraceModel:
    def test_defaults_produce_empty_trace(self) -> None:
        trace = RetrievalTrace()
        assert trace.candidates == []
        assert trace.picked == []
        assert trace.used_by is None
        assert trace.source == "soul"
        assert trace.latency_ms == 0
        assert isinstance(trace.timestamp, datetime)
        assert len(trace.id) == 12

    def test_round_trip_serialization_preserves_fields(self) -> None:
        trace = RetrievalTrace(
            actor="user:priya",
            query="renewal discount Acme",
            candidates=[
                TraceCandidate(id="m1", source="soul", score=0.9, tier="semantic"),
                TraceCandidate(id="kb_42", source="kb", score=0.85),
            ],
            picked=["m1"],
            used_by="action:act_123",
            latency_ms=42,
            pocket_id="pocket-1",
        )
        restored = RetrievalTrace.model_validate(trace.model_dump())
        assert restored == trace

    def test_candidate_accepts_optional_metadata(self) -> None:
        candidate = TraceCandidate(
            id="m1",
            source="soul",
            score=0.7,
            metadata={"rerank_rank": 2, "original_rank": 5},
        )
        restored = TraceCandidate.model_validate(candidate.model_dump())
        assert restored.metadata["rerank_rank"] == 2


class TestMarkUsed:
    def test_mark_used_records_picked_ids(self) -> None:
        trace = RetrievalTrace(
            candidates=[
                TraceCandidate(id="m1"),
                TraceCandidate(id="m2"),
            ]
        )
        trace.mark_used(["m1"], used_by="action:act_1")
        assert trace.picked == ["m1"]
        assert trace.used_by == "action:act_1"

    def test_mark_used_without_used_by_preserves_existing(self) -> None:
        trace = RetrievalTrace(used_by="action:prev")
        trace.mark_used(["m1"])
        assert trace.picked == ["m1"]
        assert trace.used_by == "action:prev"

    def test_mark_used_copies_the_input_list(self) -> None:
        picked_source = ["m1", "m2"]
        trace = RetrievalTrace()
        trace.mark_used(picked_source)
        picked_source.append("m3")
        assert trace.picked == ["m1", "m2"]


# ---------------------------------------------------------------------------
# Runtime — Soul.recall emits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_populates_last_retrieval() -> None:
    soul = await Soul.birth(name="Echo", archetype="Test")
    await soul.remember("coffee is important")

    assert soul.last_retrieval is None  # No recall yet.
    results = await soul.recall("coffee")

    trace = soul.last_retrieval
    assert trace is not None
    assert trace.query == "coffee"
    assert trace.source == "soul"
    assert trace.actor == soul.did
    assert trace.latency_ms >= 0
    # Every returned entry shows up as a candidate, in order.
    assert len(trace.candidates) == len(results)
    for entry, cand in zip(results, trace.candidates, strict=True):
        assert cand.id == entry.id
        assert 0.0 <= cand.score <= 1.0


@pytest.mark.asyncio
async def test_recall_with_empty_store_still_emits_trace() -> None:
    soul = await Soul.birth(name="Echo", archetype="Test")
    results = await soul.recall("nothing has been remembered")

    assert results == []
    trace = soul.last_retrieval
    assert trace is not None
    assert trace.candidates == []
    assert trace.query == "nothing has been remembered"


@pytest.mark.asyncio
async def test_recall_uses_requester_id_as_actor() -> None:
    soul = await Soul.birth(name="Echo", archetype="Test")
    await soul.recall("anything", requester_id="user:sarah@co.com")

    trace = soul.last_retrieval
    assert trace is not None
    assert trace.actor == "user:sarah@co.com"


@pytest.mark.asyncio
async def test_last_retrieval_is_not_serialised() -> None:
    """Traces are in-memory only. Export/awaken must drop them."""
    soul = await Soul.birth(name="Echo", archetype="Test")
    await soul.remember("x")
    await soul.recall("x")
    assert soul.last_retrieval is not None

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "echo.soul"
        await soul.export(str(path))
        restored = await Soul.awaken(str(path))

    assert restored.last_retrieval is None


# ---------------------------------------------------------------------------
# Runtime — score / tier extraction tolerates mock memories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_trace_handles_spec_memory_entries() -> None:
    """Spec MemoryEntry lacks `importance` and `type`. _build_trace must not raise."""
    from soul_protocol.runtime.soul import _build_trace

    entries = [MemoryEntry(id="m1", content="hi", layer="episodic")]
    trace = _build_trace(
        query="x",
        source="soul",
        actor="user:test",
        results=entries,
        latency_ms=1,
    )
    assert len(trace.candidates) == 1
    assert trace.candidates[0].id == "m1"
    assert trace.candidates[0].tier == "episodic"
    # Missing importance falls back to the default score.
    assert 0.0 <= trace.candidates[0].score <= 1.0


# ---------------------------------------------------------------------------
# Spec — RetrievalResult.trace wired to RetrievalTrace
# ---------------------------------------------------------------------------


def test_retrieval_result_trace_field_accepts_retrieval_trace() -> None:
    """v0.3 TODO: RetrievalResult.trace was Any | None, now RetrievalTrace | None."""
    from uuid import uuid4

    from soul_protocol.spec.retrieval import RetrievalResult

    trace = RetrievalTrace(actor="user:1", query="q")
    result = RetrievalResult(
        request_id=uuid4(),
        candidates=[],
        sources_queried=[],
        sources_failed=[],
        total_latency_ms=12.0,
        trace=trace,
    )
    assert result.trace is trace
    assert isinstance(result.trace, RetrievalTrace)
