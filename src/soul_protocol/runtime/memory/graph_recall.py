# memory/graph_recall.py — Graph-walk recall + progressive loading.
# Created: 2026-04-29 (#108) — Adds three things to Soul.recall:
#   1. graph_walk parameter — filter recalled memories to those linked to
#      entities reachable from a starting node within ``depth`` hops, with
#      optional ``edge_types`` filter on the traversal.
#   2. token_budget parameter — once cumulative content size of returned
#      memories exceeds the budget, switch overflow entries to their L0
#      abstract (the F1 progressive disclosure mechanism shipped earlier).
#   3. page_token / next_page_token — when a graph_walk produces more
#      results than ``limit``, paginate. Page tokens encode (graph_walk
#      hash, offset) so resuming from a stale token raises a clear error.
#
# All three play together: a graph walk over a 200-entity neighborhood with
# ``token_budget=8000`` returns the most-relevant memories with full content
# until the budget runs out, then keeps surfacing entries as L0 abstracts so
# the agent can ask for more detail by id.

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

from soul_protocol.runtime.types import MemoryEntry

if TYPE_CHECKING:
    from soul_protocol.runtime.memory.graph_view import GraphView


class RecallResults(list[MemoryEntry]):
    """List of memories with an optional ``next_page_token`` attribute.

    Subclasses ``list`` so existing callers (``for entry in results: ...``)
    keep working unchanged. The token surfaces only when a graph walk hit
    its limit and more results are available; otherwise it stays None.
    """

    next_page_token: str | None = None
    total_estimate: int | None = None
    truncated_for_budget: bool = False

    def __init__(
        self,
        entries: list[MemoryEntry] | None = None,
        *,
        next_page_token: str | None = None,
        total_estimate: int | None = None,
        truncated_for_budget: bool = False,
    ) -> None:
        super().__init__(entries or [])
        self.next_page_token = next_page_token
        self.total_estimate = total_estimate
        self.truncated_for_budget = truncated_for_budget


# ============ Page tokens ============


def encode_page_token(payload: dict) -> str:
    """Encode a pagination payload as an opaque base64 token.

    Tokens are base64-encoded JSON so callers can pass them around as
    plain strings (URL-safe). The payload typically contains:
      - ``query``: the original query string
      - ``graph_walk``: the graph walk dict from the original call
      - ``offset``: how many entries the next page should skip
      - ``signature``: a stable hash of (query, graph_walk) so a token from
        one call doesn't accidentally resume a different call
    """
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_page_token(token: str) -> dict:
    """Decode a token. Raises ``ValueError`` on malformed input."""
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - convert any decode error to ValueError
        raise ValueError(f"invalid page_token: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid page_token: payload not a dict")
    return payload


def signature_for_walk(query: str, graph_walk: dict | None) -> str:
    """Stable signature for (query, graph_walk) used to bind tokens to a call.

    Two recall calls with the same query+walk produce the same signature, so
    page tokens can resume the second call. Different walks produce
    different signatures, so a token won't silently apply to the wrong walk.
    """
    payload = {
        "q": query,
        "w": graph_walk or {},
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    # Short signature — full SHA isn't needed; this is a paste-protection
    # check, not security.
    import hashlib

    return hashlib.sha256(raw).hexdigest()[:16]


# ============ Graph-walk filter ============


def filter_by_graph_walk(
    entries: list[MemoryEntry],
    graph_walk: dict,
    graph: GraphView,
) -> tuple[list[MemoryEntry], dict[str, int]]:
    """Filter ``entries`` to those that mention an entity reachable in the walk.

    Returns ``(filtered_entries, distance_map)`` where ``distance_map`` is
    ``{entity_name: hop_distance}`` so callers can rank by combined relevance
    + graph distance.

    ``graph_walk`` keys:
      - ``start`` (required): node id to start the walk from
      - ``depth`` (optional, default 2): how many hops to traverse
      - ``edge_types`` (optional): list of relation strings to whitelist

    Memories are matched by checking whether any reachable entity name
    appears in the memory's entity list, content, or abstract. This is a
    superset match — the goal is recall, not precision.
    """
    start = graph_walk.get("start")
    if not start:
        return entries, {}
    depth = int(graph_walk.get("depth", 2))
    edge_types = graph_walk.get("edge_types")
    if edge_types is not None and not isinstance(edge_types, list):
        edge_types = list(edge_types)

    distance_map = graph.reachable(start, depth=depth, edge_types=edge_types)
    if not distance_map:
        return [], {}

    reachable_names_lower = {name.lower() for name in distance_map}
    filtered: list[MemoryEntry] = []
    for entry in entries:
        if _entry_mentions_any(entry, reachable_names_lower):
            filtered.append(entry)
    return filtered, distance_map


def _entry_mentions_any(entry: MemoryEntry, reachable_lower: set[str]) -> bool:
    """Cheap mention check — entity-list first, content fallback."""
    if not reachable_lower:
        return False
    for ent in entry.entities or []:
        if ent.lower() in reachable_lower:
            return True
    content_lower = (entry.content or "").lower()
    for name in reachable_lower:
        if name in content_lower:
            return True
    if entry.abstract:
        abs_lower = entry.abstract.lower()
        for name in reachable_lower:
            if name in abs_lower:
                return True
    return False


def rank_with_graph_distance(
    entries: list[MemoryEntry],
    distance_map: dict[str, int],
) -> list[MemoryEntry]:
    """Re-rank ``entries`` so memories closer in the graph come first.

    The base order (relevance) is preserved as the secondary key, so two
    memories at the same graph distance keep the input ordering. Memories
    with no matched entity get pushed to the back (distance=infinity).
    """
    if not distance_map:
        return list(entries)

    def best_distance(entry: MemoryEntry) -> int:
        best = 10**6
        names_lower = {n.lower() for n in (entry.entities or [])}
        for name, dist in distance_map.items():
            if name.lower() in names_lower:
                if dist < best:
                    best = dist
        if best == 10**6:
            content_lower = (entry.content or "").lower()
            for name, dist in distance_map.items():
                if name.lower() in content_lower:
                    if dist < best:
                        best = dist
        return best

    indexed = list(enumerate(entries))
    indexed.sort(key=lambda p: (best_distance(p[1]), p[0]))
    return [e for _, e in indexed]


# ============ Token-budget overflow ============


def apply_token_budget(
    entries: list[MemoryEntry],
    token_budget: int,
    *,
    avg_chars_per_token: int = 4,
) -> tuple[list[MemoryEntry], bool]:
    """Trim ``entries`` to fit ``token_budget`` chars-converted-to-tokens.

    Memories are kept full-content while there's budget. Once the budget
    is exhausted, subsequent entries get their content swapped for the L0
    abstract (matching the F1 progressive disclosure pattern). Entries
    without an abstract are kept at full length but flagged as truncating
    by setting ``is_summarized=False`` — the caller should treat the
    boolean return as "did anything overflow".

    Returns ``(adjusted_entries, did_truncate)``.
    """
    if token_budget <= 0:
        return list(entries), False

    out: list[MemoryEntry] = []
    used_chars = 0
    char_budget = token_budget * avg_chars_per_token
    truncated = False
    for entry in entries:
        content_len = len(entry.content or "")
        if used_chars + content_len <= char_budget:
            out.append(entry)
            used_chars += content_len
            continue
        # Over budget — swap to abstract if we have one
        if entry.abstract:
            summarized = entry.model_copy()
            summarized.content = entry.abstract
            summarized.is_summarized = True
            out.append(summarized)
            used_chars += len(summarized.content)
        else:
            # Keep entry but mark truncation so caller knows there's more
            out.append(entry)
            used_chars += content_len
        truncated = True
    return out, truncated
