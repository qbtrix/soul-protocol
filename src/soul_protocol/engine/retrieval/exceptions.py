# exceptions.py — Retrieval router + credential broker error hierarchy.
# Created: feat/retrieval-router — Workstream C1 of Org Architecture RFC (#164).
# Kept tiny on purpose — callers should be able to distinguish "no usable
# source" from "credential misuse" without inspecting messages.

from __future__ import annotations


class RetrievalError(Exception):
    """Base class for all retrieval-layer errors."""


class NoSourcesError(RetrievalError):
    """No registered source matched the request's scopes or explicit list."""


class SourceTimeoutError(RetrievalError):
    """A source adapter did not return within the per-source timeout."""


class CredentialScopeError(RetrievalError):
    """A credential was used by a requester whose scopes do not overlap
    the scopes the credential was issued for."""


class CredentialExpiredError(RetrievalError):
    """A credential was used after its TTL elapsed."""
