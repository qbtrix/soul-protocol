# trace.py — Retrieval trace primitives for the core layer.
# Created: 2026-04-13 — RetrievalTrace + TraceCandidate. One trace per
# recall/search/match call. Runtimes emit; paw-runtime sinks to a JSONL log
# that downstream systems (debug, graduation, compliance, eval) read from.
# Source is a free-form string — runtimes define their own vocabularies.
# Note: lives in spec/trace.py (not spec/retrieval.py) to avoid name collision
# with the v0.3 retrieval router models (RetrievalCandidate/RetrievalRequest/
# RetrievalResult). The trace candidate is renamed TraceCandidate for the
# same reason — different concern (receipt vs router payload).

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceCandidate(BaseModel):
    """One ranked candidate recorded in a retrieval trace.

    ``score`` is runtime-defined — may be ACT-R activation, BM25 score, cosine
    similarity, an LLM rerank score, or the importance value used by the
    heuristic recall path. The shape is portable; the scale is not. Callers
    that care about cross-source comparisons should normalize.

    ``tier`` applies when the candidate comes from a tiered store (soul
    memories). It is optional so other sources (kb articles, skills, fabric
    objects) don't have to fake one.
    """

    id: str
    source: str = "soul"
    score: float = 0.0
    tier: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalTrace(BaseModel):
    """The receipt for one retrieval event.

    Written once per ``recall()`` / ``smart_recall()`` / kb search / skill
    match call. Downstream systems (the paw-runtime JSONL sink, the
    graduation policy, the Why? drawer, SoulBench fixture generation) all
    read the same shape.

    ``picked`` is the subset of candidate IDs the caller actually used —
    populated by the caller, not the retrieval function. ``used_by``
    carries a downstream reference (e.g. ``"action:act_123"`` when the
    retrieval fed an Instinct proposal) so traces can be joined to the
    audit log without duplicating content.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    actor: str = ""
    query: str = ""
    source: str = "soul"
    candidates: list[TraceCandidate] = Field(default_factory=list)
    picked: list[str] = Field(default_factory=list)
    used_by: str | None = None
    latency_ms: int = 0
    pocket_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def mark_used(self, picked_ids: list[str], used_by: str | None = None) -> None:
        """Record which candidates the caller actually used.

        Separate from construction so retrieval functions can return a trace
        with the candidate list populated, and callers downstream can fill
        in ``picked`` / ``used_by`` without reconstructing the whole trace.
        """
        self.picked = list(picked_ids)
        if used_by is not None:
            self.used_by = used_by
