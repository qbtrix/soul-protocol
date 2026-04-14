# scope.py — Public scope-matching helper extracted from the sqlite backend.
# Created: feat/retrieval-router — lift `_scope_matches` out of the SQLite
# backend (where router and broker were reaching into a private symbol) and
# into a proper public module. Semantics are unchanged; the sqlite backend
# now imports from here, and the router + broker do too.
#
# Grammar (colon-delimited segments, ``*`` is a single-segment wildcard):
#   - ``"org:sales"`` matches exactly ``org:sales``.
#   - ``"org:sales:*"`` matches ``org:sales:leads`` and ``org:sales:deals``
#     but NOT bare ``org:sales`` (segment count must match).
#   - ``"org:*"`` matches ``org:sales`` and ``org:hr`` but NOT bare ``org``.
#   - ``"org:*:leads"`` matches ``org:sales:leads`` and ``org:hr:leads``.
#
# This is a placeholder until ``spec.scope`` from #162 lands; the final
# grammar there is a superset of what we implement. Callers swap to the
# richer helper when it ships — same name, same shape.
#
# v0.3.1 note (2026-04-14): `spec.scope.match_scope` now implements
# hierarchical containment (a concrete scope matches its ancestor glob).
# The journal's `scope_matches` stays with its stricter segment-count
# grammar on purpose: it answers a different question. Here we ask "does
# this event belong to the set of events the query pattern names", which
# is a set-membership check where `org:sales` and `org:sales:leads` are
# genuinely different sets. The router calls this helper twice
# (both directions) to get the overlap it wants for fanout, so moving to
# containment would change event fan-out semantics. Leaving as-is.

from __future__ import annotations


def scope_matches(event_scopes: list[str], query_scopes: list[str]) -> bool:
    """Return True iff any event scope matches any query pattern.

    Semantics are asymmetric on purpose: `event_scopes` are concrete scopes
    carried by a journal event, `query_scopes` are patterns supplied by a
    caller looking for matches. Wildcards are valid on the pattern side;
    putting a wildcard in an event scope works but means "this event was
    emitted across a wildcard scope" which few writers do.
    """
    for pat in query_scopes:
        pat_parts = pat.split(":")
        for scope in event_scopes:
            scope_parts = scope.split(":")
            if len(pat_parts) != len(scope_parts):
                continue
            if all(p == "*" or p == s for p, s in zip(pat_parts, scope_parts)):
                return True
    return False


def scopes_overlap(granted: list[str], requested: list[str]) -> bool:
    """Return True iff any requested pattern is covered by any granted one.

    Policy pinned: this is intentionally symmetric against wildcards — a
    credential granted for ``org:sales:*`` is usable by a requester
    presenting a specific scope like ``org:sales:leads``, AND a credential
    granted for a specific scope ``org:sales:leads`` is usable by a
    requester presenting ``org:sales:*`` (a wildcard requester asserting
    "I am operating anywhere in this subtree").

    Both directions are deliberate. Breaking either:
      * reject specific-requester-vs-wildcard-grant -> admins who issue a
        broad credential can't use it for any concrete call.
      * reject wildcard-requester-vs-specific-grant -> a retrieval router
        operating org-wide can't consume per-scope credentials, which
        kneecaps fanout.
    """
    for req in requested:
        req_parts = req.split(":")
        for grant in granted:
            grant_parts = grant.split(":")
            if len(grant_parts) != len(req_parts):
                continue
            if all(
                g == "*" or r == "*" or g == r
                for g, r in zip(grant_parts, req_parts)
            ):
                return True
    return False
