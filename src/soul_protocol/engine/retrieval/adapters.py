# adapters.py — SourceAdapter Protocol + two reference implementations.
# Created: feat/retrieval-router — Workstream C1 of Org Architecture RFC (#164).
# Adapters are intentionally sync for this slice — async wrapping is a
# follow-up. The router runs adapters on a thread pool for the `parallel`
# strategy, so sync-only callers (sqlite projections, requests-backed
# federated sources) stay the simple case.
#
# Two concrete adapters live here:
#   * `MockAdapter` — returns fixed candidates and tracks invocations. Pure
#     test fixture; not exported from the retrieval __init__.
#   * `ProjectionAdapter` — wraps a callable so soul memory, kb, and fabric
#     can plug in without each building a class. Represents the
#     "local rebuilt view" case.
#
# The concrete external-federation adapters (Drive, Salesforce, ...) are C2.

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from soul_protocol.spec.retrieval import RetrievalCandidate, RetrievalRequest

from .broker import Credential


@runtime_checkable
class SourceAdapter(Protocol):
    """Protocol implemented by every retrieval source adapter.

    An adapter is registered under a `CandidateSource`. `query` receives
    the full request (so it can read `query`, `limit`, `scopes`) plus an
    optional credential — projection adapters ignore the credential,
    DataRef adapters require it.

    The `supports_dataref` class attribute advertises whether this adapter
    can produce Zero-Copy candidates whose content is a DataRef payload.
    """

    supports_dataref: bool

    def query(
        self,
        request: RetrievalRequest,
        credential: Credential | None,
    ) -> list[RetrievalCandidate]: ...


class MockAdapter:
    """Test adapter. Returns a fixed list, records every call.

    Parameters:
        candidates: What to return on `query`.
        delay_s: If >0, sleeps that long before returning. Lets tests
            exercise the router's per-source timeout path.
        raises: If set, raises this exception instead of returning.
    """

    supports_dataref: bool = False

    def __init__(
        self,
        candidates: list[RetrievalCandidate] | None = None,
        *,
        delay_s: float = 0.0,
        raises: Exception | None = None,
    ) -> None:
        self._candidates = candidates or []
        self._delay_s = delay_s
        self._raises = raises
        self.calls: list[tuple[RetrievalRequest, Credential | None]] = []

    def query(
        self,
        request: RetrievalRequest,
        credential: Credential | None,
    ) -> list[RetrievalCandidate]:
        self.calls.append((request, credential))
        if self._delay_s > 0:
            import time

            time.sleep(self._delay_s)
        if self._raises is not None:
            raise self._raises
        return list(self._candidates)


class ProjectionAdapter:
    """Adapter over a plain callable — the "local rebuilt view" shape.

    Soul memory, kb, and fabric all live inside the same Paw OS instance
    the router runs in. They don't need federation or credentials. A
    callable that takes the request and returns candidates is enough.
    """

    supports_dataref: bool = False

    def __init__(
        self,
        fn: Callable[[RetrievalRequest], list[RetrievalCandidate]],
    ) -> None:
        self._fn = fn

    def query(
        self,
        request: RetrievalRequest,
        credential: Credential | None,  # noqa: ARG002 — projection ignores creds
    ) -> list[RetrievalCandidate]:
        return list(self._fn(request))
