# scope.py — Hierarchical scope tag matching for RBAC/ABAC.
# Created: 2026-04-13 (Move 5 PR-A) — Pure helper. No I/O, no enums, no
# imports beyond stdlib. The same matcher is used by soul recall, fabric
# queries, kb retrievals, and pocket visibility checks. Centralised here
# so behaviour is identical across every retrieval path.
# Updated: 2026-04-14 (v0.3.1 follow-up to #163) — match_scope is now
# bidirectional containment. A concrete scope like `org:sales:leads`
# matches a glob scope like `org:sales:*` (and vice versa), because the
# former is a descendant of the latter. The old asymmetric behaviour made
# bundled archetypes' core memories invisible to agents installed from
# them — the template declares `default_scope: [org:sales:*]`, the agent
# gets installed with a concrete caller scope like `org:sales:leads`, and
# the call site used `match_scope(entity_scopes=memory.scope,
# allowed_scopes=caller.scopes)` which returned False for the common
# descendant-of-glob case. The strict one-directional helper is kept as
# `match_scope_strict` for callers that need the old semantic.

from __future__ import annotations


def match_scope(entity_scopes: list[str] | None, allowed_scopes: list[str] | None) -> bool:
    """Return True when ``entity_scopes`` and ``allowed_scopes`` overlap
    by hierarchical containment in either direction.

    Empty ``entity_scopes`` is treated as "no scope assigned" — visible
    to any caller. Empty ``allowed_scopes`` is treated as "caller has no
    scope filter" — sees everything. This matches the lean default that
    pre-scope memories continue to surface unchanged.

    Bidirectional containment: a scope ``A`` is said to contain a scope
    ``B`` when either they are equal, or ``A`` is a glob ``"<prefix>:*"``
    and ``B`` equals ``<prefix>`` or starts with ``<prefix>:``. The match
    returns True when at least one pair ``(entity, allowed)`` has one
    side contain the other.

    Examples:
        >>> match_scope(["org:sales:leads"], ["org:sales:*"])   # descendant in glob
        True
        >>> match_scope(["org:sales:*"], ["org:sales:leads"])   # caller inside glob entity
        True
        >>> match_scope(["org:sales:*"], ["org:*"])             # glob nested under broader glob
        True
        >>> match_scope(["org:sales:leads"], ["org:support:*"]) # different subtree
        False
        >>> match_scope(["org:sales:leads"], ["org:sales:leads"])  # exact
        True

    Hierarchical glob syntax: ``"org:sales:*"`` matches any descendant
    under ``org:sales`` and ``org:sales`` itself. ``"*"`` matches
    anything. Comparison is case-sensitive — scope tags are namespaced
    ASCII identifiers, not free-form labels.
    """
    if not entity_scopes:
        return True
    if not allowed_scopes:
        return True
    return any(
        _contains(entity, allowed) or _contains(allowed, entity)
        for entity in entity_scopes
        for allowed in allowed_scopes
    )


def match_scope_strict(
    entity_scopes: list[str] | None, allowed_scopes: list[str] | None
) -> bool:
    """One-directional variant: the caller's ``allowed_scopes`` must
    grant at least one ``entity_scope``.

    Retained for callers that genuinely want the asymmetric semantic —
    "is this memory's scope within what the caller is explicitly
    allowed?". Most RBAC call sites want :func:`match_scope` instead, so
    a caller with a narrow concrete scope can still see memories tagged
    with a wider glob the caller sits inside.
    """
    if not entity_scopes:
        return True
    if not allowed_scopes:
        return True
    return any(
        _contains(allowed, entity)
        for entity in entity_scopes
        for allowed in allowed_scopes
    )


def _contains(outer: str, inner: str) -> bool:
    """True when ``outer`` contains ``inner`` by hierarchical glob rules.

    A ``*`` glob contains everything. A ``<prefix>:*`` glob contains
    ``<prefix>`` itself and any ``<prefix>:...`` descendant. Equal
    strings contain each other.
    """
    if outer == "*":
        return True
    if outer == inner:
        return True
    if outer.endswith(":*"):
        prefix = outer[:-2]
        return inner == prefix or inner.startswith(prefix + ":")
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
