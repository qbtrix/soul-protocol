# memory/graph_types.py — Typed graph primitives for v0.5.0 graph layer.
# Created: 2026-04-29 (#108, #190) — Combined graph traversal + typed entity
#   ontology. Defines:
#   - EntityType: string-enum of built-in entity kinds (person, place, org,
#     concept, tool, document, event, relation). Open: any string is accepted
#     as an entity type, the enum just names the well-known ones.
#   - GraphNode: pydantic view of a graph entity (id, type, name, depth?).
#   - GraphEdge: pydantic view of a directed relation between entities.
#   - Subgraph: container for a node/edge slice (the result of walks/queries).
#   - RelationType: small enum of built-in relation predicates. Open string —
#     callers can pass app-specific predicates without registering them.
#
# These models are Pydantic so they round-trip cleanly through MCP, CLI JSON
# output, and any future on-disk index format. The KnowledgeGraph keeps its
# internal dict + adjacency list — these types are the public read shape.

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    """Built-in entity types for the typed ontology.

    StrEnum members compare equal to their string values, so callers can
    pass either ``EntityType.PERSON`` or the literal ``"person"``. The
    KnowledgeGraph stores entity types as plain strings — any string is
    accepted (e.g. ``"pr"``, ``"channel"``, ``"library"``). The enum just
    names the well-known kinds so they don't drift across modules.
    """

    PERSON = "person"
    PLACE = "place"
    ORG = "org"
    CONCEPT = "concept"
    TOOL = "tool"
    DOCUMENT = "document"
    EVENT = "event"
    RELATION = "relation"


class RelationType(StrEnum):
    """Built-in relation predicates for the controlled vocabulary.

    Same open-string contract as :class:`EntityType` — these are well-known
    names, but any string is accepted on the edge.
    """

    MENTIONS = "mentions"
    RELATED = "related"
    DEPENDS_ON = "depends_on"
    CONTRIBUTES_TO = "contributes_to"
    CAUSES = "causes"
    FOLLOWS = "follows"
    SUPERSEDES = "supersedes"
    OWNED_BY = "owned_by"


# ============ View models ============


class GraphNode(BaseModel):
    """A typed entity in the knowledge graph.

    ``id`` is the canonical name used as the graph key (the same value passed
    to :meth:`KnowledgeGraph.add_entity`). ``name`` is the display string —
    defaults to ``id`` for back-compat with the dict-keyed graph.

    ``depth`` is set by traversal queries (``neighbors``, ``path``) to record
    how many hops from the source the node lives at. ``None`` for nodes
    returned by direct list operations.

    ``provenance`` carries the memory IDs that produced this entity (Phase 1
    of #190). Empty list when the graph was populated before provenance
    tracking landed — those entities still surface, they just don't yet
    carry a back-link to their source memories.
    """

    id: str
    type: str = "concept"
    name: str = ""
    depth: int | None = None
    provenance: list[str] = Field(default_factory=list)

    def model_post_init(self, __context: object) -> None:  # noqa: D401 - pydantic hook
        """Default ``name`` to ``id`` so display-friendly queries still work."""
        if not self.name:
            self.name = self.id


class GraphEdge(BaseModel):
    """A directed relation between two entities.

    ``relation`` is a free-form string — built-in predicates are listed in
    :class:`RelationType`. ``weight`` is an optional confidence score (0-1)
    set by the LLM extractor. ``provenance`` carries the source memory IDs
    that produced this edge.
    """

    source: str
    target: str
    relation: str
    weight: float | None = None
    provenance: list[str] = Field(default_factory=list)
    metadata: dict | None = None


class Subgraph(BaseModel):
    """A slice of the graph — nodes and edges produced by a query.

    Returned by :meth:`GraphView.subgraph` and the backing storage for path
    walks. ``nodes`` and ``edges`` are independent lists (not adjacency-
    indexed) so callers can serialize the subgraph with one ``model_dump``.
    """

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    def to_mermaid(self) -> str:
        """Render this subgraph as a Mermaid ``graph`` block.

        Used by :meth:`GraphView.to_mermaid` and the ``soul graph mermaid``
        CLI. Output is always ``graph LR`` with sanitized node IDs (Mermaid
        rejects spaces and most punctuation in IDs). Display names retain
        the original characters via the ``["..."]`` label form.
        """
        return _render_mermaid(self.nodes, self.edges)


# ============ Mermaid helpers ============


def _sanitize_node_id(name: str) -> str:
    """Convert a free-form entity name into a Mermaid-safe identifier.

    Mermaid IDs must be alphanumeric with underscores. Anything else gets
    replaced with ``_`` so the resulting ID is unique-but-readable.
    """
    out: list[str] = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    sanitized = "".join(out)
    if not sanitized:
        return "node"
    if sanitized[0].isdigit():
        sanitized = "n_" + sanitized
    return sanitized


def _render_mermaid(nodes: list[GraphNode], edges: list[GraphEdge]) -> str:
    """Render a Mermaid ``graph LR`` block from node/edge lists.

    Stable ordering: nodes appear in the input order, edges in input order.
    Display labels use Mermaid's ``id["label"]`` form so entity names with
    spaces or punctuation render correctly.
    """
    lines: list[str] = ["graph LR"]
    seen: dict[str, str] = {}
    for node in nodes:
        nid = _sanitize_node_id(node.id)
        # Disambiguate when multiple entities sanitize to the same id
        if nid in seen and seen[nid] != node.id:
            nid = f"{nid}_{len(seen)}"
        seen[nid] = node.id
        label = node.name or node.id
        type_tag = f" :: {node.type}" if node.type else ""
        lines.append(f'    {nid}["{label}{type_tag}"]')
    # Build a quick reverse lookup so we use the same sanitized id on edges
    id_to_nid: dict[str, str] = {orig: nid for nid, orig in seen.items()}
    for edge in edges:
        src_nid = id_to_nid.get(edge.source) or _sanitize_node_id(edge.source)
        tgt_nid = id_to_nid.get(edge.target) or _sanitize_node_id(edge.target)
        rel = edge.relation or "related"
        lines.append(f"    {src_nid} -->|{rel}| {tgt_nid}")
    return "\n".join(lines)
