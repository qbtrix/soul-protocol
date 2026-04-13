# __init__.py — Public API for the retrieval engine.
# Created: feat/retrieval-router — Workstream C1 of Org Architecture RFC (#164).
# Exports the router, credential broker, source adapter protocol, and the
# exception hierarchy. MockAdapter is intentionally *not* re-exported —
# it lives here as a test helper and callers should import it from the
# submodule when they need it.

from __future__ import annotations

from .adapters import ProjectionAdapter, SourceAdapter
from .broker import Credential, CredentialBroker, InMemoryCredentialBroker
from .exceptions import (
    CredentialExpiredError,
    CredentialScopeError,
    NoSourcesError,
    RetrievalError,
    SourceTimeoutError,
)
from .router import RetrievalRouter

__all__ = [
    "Credential",
    "CredentialBroker",
    "CredentialExpiredError",
    "CredentialScopeError",
    "InMemoryCredentialBroker",
    "NoSourcesError",
    "ProjectionAdapter",
    "RetrievalError",
    "RetrievalRouter",
    "SourceAdapter",
    "SourceTimeoutError",
]
