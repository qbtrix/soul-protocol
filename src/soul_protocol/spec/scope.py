# scope.py — Hierarchical scope tag matching for RBAC/ABAC.
# Created: 2026-04-13 (Move 5 PR-A) — Pure helper. No I/O, no enums, no
# imports beyond stdlib. The same matcher is used by soul recall, fabric
# queries, kb retrievals, and pocket visibility checks. Centralised here
# so behaviour is identical across every retrieval path.

from __future__ import annotations


def match_scope(entity_scopes: list[str] | None, allowed_scopes: list[str] | None) -> bool:
    """Return True when at least one of ``entity_scopes`` is granted by
    ``allowed_scopes`` (or when either side is empty).

    Empty ``entity_scopes`` is treated as "no scope assigned" — visible
    to any caller. Empty ``allowed_scopes`` is treated as "caller has no
    scope filter" — sees everything. This matches the lean default that
    pre-scope memories continue to surface unchanged.

    Hierarchical glob: ``"org:sales:*"`` matches ``"org:sales:leads"``
    and ``"org:sales"`` itself. ``"*"`` matches anything. Comparison is
    case-sensitive — scope tags are namespaced ASCII identifiers, not
    free-form labels.
    """
    if not entity_scopes:
        return True
    if not allowed_scopes:
        return True
    return any(
        _granted(entity, allowed)
        for entity in entity_scopes
        for allowed in allowed_scopes
    )


def _granted(entity: str, allowed: str) -> bool:
    if allowed == "*":
        return True
    if allowed == entity:
        return True
    if allowed.endswith(":*"):
        prefix = allowed[:-2]
        return entity == prefix or entity.startswith(prefix + ":")
    return False


def normalise_scopes(scopes: list[str] | None) -> list[str]:
    """Strip + lowercase + de-duplicate. Returns a fresh list, preserving order."""
    if not scopes:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in scopes:
        if not isinstance(raw, str):
            continue
        cleaned = raw.strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out
