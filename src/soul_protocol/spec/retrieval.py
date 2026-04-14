# retrieval.py — Retrieval router request/result models.
# Created: feat/retrieval-router — Workstream C1 of Org Architecture RFC (#164).
# Describes the request envelope, candidate-source registration, and result
# shape the `RetrievalRouter` uses. Source-specific payload stays opaque so
# the router doesn't need to know about Drive, Salesforce, soul memory, etc.
# Zero-Copy federation is expressed by `CandidateSource.kind == "dataref"`
# sources — their adapters return candidates whose payload points at live
# external data rather than copying it.
# Updated: feat/retrieval-trace-spec — Wired the `trace` field on
# `RetrievalResult` to the `RetrievalTrace` receipt model from
# ``soul_protocol.spec.trace`` (closes the v0.3 TODO from PR #161).

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from soul_protocol.spec.journal import Actor
from soul_protocol.spec.trace import RetrievalTrace


class CandidateSource(BaseModel):
    """One source the retrieval router can dispatch to.

    Fields:
        name: Stable source identifier — ``"soul_memory"``, ``"kb_articles"``,
            ``"fabric_objects"``, ``"drive"``, ``"salesforce"``, ...
        kind: ``"projection"`` for a local rebuilt view (soul memory, kb,
            fabric), ``"dataref"`` for an external federated source whose
            candidates reference live data via a DataRef.
        scopes: DSP scope patterns this source is registered under. A
            request's scopes must overlap (prefix+wildcard match) for the
            source to be considered.
        adapter_ref: Module path or registered name of the adapter that
            handles this source. Free-form — the router resolves through
            its own `register_source` table.
    """

    name: str = Field(min_length=1)
    kind: Literal["projection", "dataref"]
    scopes: list[str] = Field(min_length=1)
    adapter_ref: str = Field(min_length=1)


class RetrievalRequest(BaseModel):
    """Input to `RetrievalRouter.dispatch`.

    Fields:
        query: Free-text or source-native query. Opaque to the router.
        actor: Who is asking — recorded on the emitted `retrieval.query`
            journal event.
        scopes: Caller's current scope context. The router filters
            registered sources down to those whose scopes overlap.
        correlation_id: Optional flow/session id, recorded on the journal
            event so a retrieval can be traced back to the work that asked.
        sources: Optional explicit allowlist by source name. ``None`` means
            "use every registered source whose scope overlaps".
        limit: Maximum candidates to return after merging.
        strategy: ``first`` — try sources in order, return first non-empty.
            ``parallel`` — dispatch all in threads, merge by score.
            ``sequential`` — try in order, accumulate up to `limit`.
        timeout_s: Per-source timeout in wall-clock seconds.
    """

    query: str
    actor: Actor
    scopes: list[str] = Field(min_length=1)
    correlation_id: UUID | None = None
    sources: list[str] | None = None
    limit: int = 20
    strategy: Literal["first", "parallel", "sequential"] = "parallel"
    timeout_s: float = 10.0


class RetrievalCandidate(BaseModel):
    """A single result returned by a source adapter.

    Fields:
        source: The source name this candidate came from.
        content: Source-specific payload. The router never inspects it.
            Zero-Copy sources put a DataRef-shaped dict here; projection
            sources put their own view payload.
        score: Optional source-provided relevance score. Used for merging
            in the `parallel` strategy; `None` sinks to the back.
        as_of: Timezone-aware UTC timestamp recording when this candidate
            was resolved — live resolution vs cache read.
        cached: ``True`` if the adapter served this from cache, ``False``
            if it resolved live.
    """

    source: str = Field(min_length=1)
    content: dict[str, Any]
    score: float | None = None
    as_of: datetime
    cached: bool = False

    @field_validator("as_of")
    @classmethod
    def _as_of_must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("RetrievalCandidate.as_of must be timezone-aware (UTC)")
        return v


class RetrievalResult(BaseModel):
    """Output from `RetrievalRouter.dispatch`.

    Fields:
        request_id: UUID assigned by the router for correlation.
        candidates: Merged candidates, truncated to `limit`.
        sources_queried: Names of sources actually invoked.
        sources_failed: ``(source_name, failure_reason)`` tuples for any
            source that timed out, raised, or refused (scope mismatch).
        total_latency_ms: End-to-end wall-clock time in the router.
        trace: Optional :class:`RetrievalTrace` receipt for this dispatch.
            Routers populate it when they want downstream consumers (the
            paw-runtime JSONL sink, graduation policy, the Why? drawer)
            to be able to read the per-candidate scores and pick set
            without holding onto the result object itself.
    """

    request_id: UUID
    candidates: list[RetrievalCandidate]
    sources_queried: list[str]
    sources_failed: list[tuple[str, str]]
    total_latency_ms: float
    trace: RetrievalTrace | None = None
