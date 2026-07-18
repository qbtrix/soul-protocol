# memory/graph.py — KnowledgeGraph for entity relationships.
# Updated: v0.5.0 (#108, #190) — Typed entity ontology + traversal upgrades.
#   - Entities now store provenance (list of memory_ids) alongside type, so the
#     graph layer can answer "which memories produced this entity" cheaply.
#   - Edges gain a weight field (0-1 confidence from the LLM extractor) and
#     pass through any metadata.source_memory_id as edge provenance.
#   - New typed view helpers: list_nodes(), list_edges(), neighbors_typed(),
#     find_path_typed() return GraphNode/GraphEdge dataclasses suitable for
#     the new GraphView API. Existing list-of-dict methods stay for back-compat.
# Updated: v0.4.0 — Added progressive_context() for multi-hop graph traversal.
#   Returns entity relationships at configurable depth levels for recall augmentation.
# Updated: fix/graph-progressive-context-conflict — Renamed duplicate progressive_context()
#   (string-returning, LLM-formatted) to format_context() to avoid method override.
#   progressive_context() now unambiguously returns list[dict] for programmatic use.
# Created: 2026-02-22
# Updated: 2026-03-22 — Added graph traversal methods (traverse, shortest_path,
#   get_neighborhood, subgraph) and progressive_context() for L0/L1/L2 loading.
# Updated: v0.3.4 — Added metadata dict to TemporalEdge for reasoning context.
# Updated: 2026-03-10 — Added remove_entity() for GDPR-compliant entity deletion.
# Updated: 2026-03-06 — Added temporal fields (valid_from, valid_to) to edges.

from __future__ import annotations

from collections import deque
from datetime import datetime

from soul_protocol.runtime.memory.graph_types import GraphEdge, GraphNode


class TemporalEdge:
    """A directed relationship with temporal validity."""

    __slots__ = (
        "source",
        "target",
        "relation",
        "valid_from",
        "valid_to",
        "metadata",
        "weight",
    )

    def __init__(
        self,
        source: str,
        target: str,
        relation: str,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        metadata: dict | None = None,
        weight: float | None = None,
    ) -> None:
        self.source = source
        self.target = target
        self.relation = relation
        self.valid_from = valid_from or datetime.now()
        self.valid_to = valid_to
        self.metadata = metadata
        self.weight = weight

    def is_active_at(self, dt: datetime) -> bool:
        if self.valid_from > dt:
            return False
        if self.valid_to is not None and self.valid_to < dt:
            return False
        return True

    def is_currently_active(self) -> bool:
        return self.valid_to is None

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.relation)

    def to_dict(self) -> dict:
        d: dict = {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "valid_from": self.valid_from.isoformat(),
        }
        if self.valid_to is not None:
            d["valid_to"] = self.valid_to.isoformat()
        if self.metadata is not None:
            d["metadata"] = self.metadata
        if self.weight is not None:
            d["weight"] = self.weight
        return d

    @classmethod
    def from_dict(cls, data: dict) -> TemporalEdge:
        valid_from = None
        if "valid_from" in data:
            valid_from = datetime.fromisoformat(data["valid_from"])
        valid_to = None
        if "valid_to" in data:
            valid_to = datetime.fromisoformat(data["valid_to"])
        return cls(
            source=data["source"],
            target=data["target"],
            relation=data["relation"],
            valid_from=valid_from,
            valid_to=valid_to,
            metadata=data.get("metadata"),
            weight=data.get("weight"),
        )


class KnowledgeGraph:
    """Simple dict-based knowledge graph for entity relationships.

    v0.5.0 (#190) tracks **provenance** — the list of memory IDs that
    produced each entity — alongside the entity type. ``_entities`` keeps
    storing ``name -> type`` for back-compat; ``_provenance`` is a parallel
    dict ``name -> list[memory_id]`` so old serializations still load
    cleanly. New entities and edges accept an optional ``source_memory_id``
    keyword that gets folded into the provenance lists.
    """

    def __init__(self) -> None:
        self._entities: dict[str, str] = {}
        self._edges: list[TemporalEdge] = []
        # v0.5.0 (#190) — entity provenance: name -> list of memory_ids that
        # contributed this entity. Stored separately so legacy graph files
        # (which don't carry provenance) round-trip via from_dict() without
        # blowing up on a missing field.
        self._provenance: dict[str, list[str]] = {}

    def add_entity(
        self,
        name: str,
        entity_type: str = "unknown",
        *,
        source_memory_id: str | None = None,
    ) -> None:
        """Add (or update) an entity in the graph.

        ``entity_type`` is a free-form string — the EntityType enum names
        the well-known kinds (person, place, org, concept, tool, document,
        event, relation) but any string is accepted.

        ``source_memory_id`` (#190): when given, append the id to the
        entity's provenance list. Idempotent — the same memory_id is only
        recorded once per entity. Pass None for legacy callers (no
        provenance tracking).
        """
        # When the entity already exists with a meaningful type, keep that
        # type — re-adding with type="unknown" should never clobber a
        # previously-typed entity. This makes it safe to call add_entity()
        # purely to record provenance.
        existing = self._entities.get(name)
        if existing in (None, "", "unknown") or entity_type not in ("", "unknown"):
            self._entities[name] = entity_type or "unknown"

        if source_memory_id:
            ids = self._provenance.setdefault(name, [])
            if source_memory_id not in ids:
                ids.append(source_memory_id)

    def add_relationship(
        self,
        source: str,
        target: str,
        relation: str,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        metadata: dict | None = None,
        weight: float | None = None,
    ) -> None:
        """Add a directed edge from ``source`` to ``target``.

        Idempotent: if an active edge with the same ``(source, target,
        relation)`` triple already exists, the call is a no-op (so re-running
        the extractor on the same memory doesn't create duplicates). Any
        ``metadata.source_memory_id`` is folded into the existing edge's
        provenance list when the metadata changes the source memory.
        """
        if source not in self._entities:
            self._entities[source] = "unknown"
        if target not in self._entities:
            self._entities[target] = "unknown"
        for edge in self._edges:
            if (
                edge.source == source
                and edge.target == target
                and edge.relation == relation
                and edge.is_currently_active()
            ):
                # Idempotent re-extraction — fold provenance into the
                # existing edge's metadata so a second visit records that
                # memory too. Keeps weight at the existing value.
                if metadata and "source_memory_id" in metadata:
                    edge.metadata = _merge_edge_metadata(edge.metadata, metadata)
                return
        self._edges.append(
            TemporalEdge(
                source=source,
                target=target,
                relation=relation,
                valid_from=valid_from,
                valid_to=valid_to,
                metadata=metadata,
                weight=weight,
            )
        )

    def get_related(self, entity: str) -> list[dict]:
        results: list[dict] = []
        for edge in self._edges:
            if not edge.is_currently_active():
                continue
            if edge.source == entity:
                result: dict = {
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "direction": "outgoing",
                }
                if edge.metadata is not None:
                    result["metadata"] = edge.metadata
                results.append(result)
            elif edge.target == entity:
                result = {
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "direction": "incoming",
                }
                if edge.metadata is not None:
                    result["metadata"] = edge.metadata
                results.append(result)
        return results

    def progressive_context(self, entity: str, level: int = 1) -> list[dict]:
        """Get progressively wider context around an entity via graph traversal.

        Level 0: Just the entity's direct relationships (same as get_related).
        Level 1: Direct relationships + one-hop neighbors' relationships.
        Level 2+: Continue expanding (capped at level to prevent explosion).

        Each result dict includes a 'depth' key indicating the hop distance.

        Args:
            entity: Starting entity name.
            level: How many hops to traverse (0=direct only, 1=one-hop, etc.).

        Returns:
            List of relationship dicts with added 'depth' field.
        """
        if entity not in self._entities:
            return []

        visited: set[str] = set()
        results: list[dict] = []
        frontier: set[str] = {entity}

        for depth in range(level + 1):
            next_frontier: set[str] = set()
            for current_entity in frontier:
                if current_entity in visited:
                    continue
                visited.add(current_entity)
                related = self.get_related(current_entity)
                for rel in related:
                    rel_with_depth = dict(rel)
                    rel_with_depth["depth"] = depth
                    results.append(rel_with_depth)
                    # Collect neighbors for next hop
                    neighbor = rel["target"] if rel["source"] == current_entity else rel["source"]
                    if neighbor not in visited:
                        next_frontier.add(neighbor)
            frontier = next_frontier

        return results

    def entities(self) -> list[str]:
        """Return a list of all entity names."""
        return list(self._entities.keys())

    def expire_relationship(
        self, source: str, target: str, relation: str, expire_at: datetime | None = None
    ) -> bool:
        expire_at = expire_at or datetime.now()
        for edge in self._edges:
            if (
                edge.source == source
                and edge.target == target
                and edge.relation == relation
                and edge.is_currently_active()
            ):
                edge.valid_to = expire_at
                return True
        return False

    def as_of_date(self, dt: datetime) -> list[dict]:
        results: list[dict] = []
        for edge in self._edges:
            if edge.is_active_at(dt):
                result: dict = {
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "valid_from": edge.valid_from,
                    "valid_to": edge.valid_to,
                }
                if edge.metadata is not None:
                    result["metadata"] = edge.metadata
                results.append(result)
        return results

    def relationship_evolution(self, source: str, target: str) -> list[dict]:
        results: list[dict] = []
        for edge in self._edges:
            if edge.source == source and edge.target == target:
                result: dict = {
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "valid_from": edge.valid_from,
                    "valid_to": edge.valid_to,
                }
                if edge.metadata is not None:
                    result["metadata"] = edge.metadata
                results.append(result)
        results.sort(key=lambda r: r["valid_from"])
        return results

    # ============ Graph Traversal ============

    def _active_neighbors(self, entity: str) -> list[str]:
        neighbors: list[str] = []
        seen: set[str] = set()
        for edge in self._edges:
            if not edge.is_currently_active():
                continue
            if edge.source == entity and edge.target not in seen:
                neighbors.append(edge.target)
                seen.add(edge.target)
            elif edge.target == entity and edge.source not in seen:
                neighbors.append(edge.source)
                seen.add(edge.source)
        return neighbors

    def traverse(self, start: str, max_depth: int = 2, max_nodes: int = 50) -> list[dict]:
        """BFS traversal from an entity, returning connected subgraph."""
        if start not in self._entities:
            return []
        visited: dict[str, int] = {start: 0}
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        result: list[dict] = []
        while queue and len(result) < max_nodes:
            entity, depth = queue.popleft()
            edges = self.get_related(entity)
            result.append(
                {
                    "entity": entity,
                    "entity_type": self._entities.get(entity, "unknown"),
                    "depth": depth,
                    "edges": edges,
                }
            )
            if depth < max_depth:
                for neighbor in self._active_neighbors(entity):
                    if neighbor not in visited and len(visited) < max_nodes:
                        visited[neighbor] = depth + 1
                        queue.append((neighbor, depth + 1))
        return result

    def shortest_path(self, source: str, target: str) -> list[str] | None:
        """Find shortest path between two entities using BFS."""
        if source not in self._entities or target not in self._entities:
            return None
        if source == target:
            return [source]
        visited: set[str] = {source}
        queue: deque[list[str]] = deque([[source]])
        while queue:
            path = queue.popleft()
            current = path[-1]
            for neighbor in self._active_neighbors(current):
                if neighbor in visited:
                    continue
                new_path = path + [neighbor]
                if neighbor == target:
                    return new_path
                visited.add(neighbor)
                queue.append(new_path)
        return None

    def get_neighborhood(self, entity: str, radius: int = 1) -> dict:
        """Get entity + all neighbors within radius hops. Returns nodes + edges."""
        if entity not in self._entities:
            return {"nodes": [], "edges": []}
        visited: dict[str, int] = {entity: 0}
        queue: deque[tuple[str, int]] = deque([(entity, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth < radius:
                for neighbor in self._active_neighbors(current):
                    if neighbor not in visited:
                        visited[neighbor] = depth + 1
                        queue.append((neighbor, depth + 1))
        nodes: list[dict] = [
            {"entity": name, "entity_type": self._entities.get(name, "unknown"), "depth": d}
            for name, d in visited.items()
        ]
        neighborhood_set = set(visited.keys())
        edges: list[dict] = []
        for edge in self._edges:
            if not edge.is_currently_active():
                continue
            if edge.source in neighborhood_set and edge.target in neighborhood_set:
                edge_dict: dict = {
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                }
                if edge.metadata is not None:
                    edge_dict["metadata"] = edge.metadata
                edges.append(edge_dict)
        return {"nodes": nodes, "edges": edges}

    def subgraph(self, entities: list[str]) -> dict:
        """Extract subgraph containing only the given entities and edges between them."""
        entity_set = set(entities)
        nodes: list[dict] = [
            {"entity": name, "entity_type": self._entities.get(name, "unknown")}
            for name in entities
            if name in self._entities
        ]
        edges: list[dict] = []
        for edge in self._edges:
            if not edge.is_currently_active():
                continue
            if edge.source in entity_set and edge.target in entity_set:
                edge_dict: dict = {
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                }
                if edge.metadata is not None:
                    edge_dict["metadata"] = edge.metadata
                edges.append(edge_dict)
        return {"nodes": nodes, "edges": edges}

    # ============ Progressive Context Loading (string formatter) ============

    def format_context(self, entity: str, level: int = 1) -> str:
        """Return human-readable context string at L0/L1/L2 depth.

        Use for LLM prompt injection. For programmatic graph traversal
        (e.g. in RecallEngine), use progressive_context() which returns list[dict].
        """
        if entity not in self._entities:
            return ""
        entity_type = self._entities[entity]
        if level <= 0:
            return f"{entity} ({entity_type})"
        related = self.get_related(entity)
        if not related:
            return f"{entity} ({entity_type}): no known relationships"
        rel_parts: list[str] = []
        for r in related:
            if r["direction"] == "outgoing":
                rel_parts.append(f"{r['relation']} -> {r['target']}")
            else:
                rel_parts.append(f"{r['source']} -> {r['relation']}")
        summary = f"{entity} ({entity_type}): " + "; ".join(rel_parts)
        if level <= 1:
            return summary
        lines: list[str] = [f"{entity} ({entity_type})"]
        lines.append("Relationships:")
        for r in related:
            direction = r["direction"]
            other = r["target"] if direction == "outgoing" else r["source"]
            other_type = self._entities.get(other, "unknown")
            if direction == "outgoing":
                line = f"  {r['relation']} -> {other}"
            else:
                line = f"  {r['relation']} <- {other}"
            line += f" ({other_type})"
            meta = r.get("metadata")
            if meta:
                if "context" in meta:
                    line += f" — {meta['context']}"
                if "confidence" in meta:
                    line += f" [confidence: {meta['confidence']}]"
            lines.append(line)
        neighbors = self._active_neighbors(entity)
        if neighbors:
            lines.append("Neighbors:")
            for n in neighbors[:10]:
                n_type = self._entities.get(n, "unknown")
                n_rel_count = len(self.get_related(n))
                lines.append(f"  {n} ({n_type}) — {n_rel_count} relationships")
        return "\n".join(lines)

    # ============ GDPR ============

    def remove_entity(self, entity: str) -> int:
        if entity in self._entities:
            del self._entities[entity]
        # Drop the entity's provenance record too — keeping it would leak
        # the source memory IDs of a forgotten entity.
        self._provenance.pop(entity, None)
        original_len = len(self._edges)
        self._edges = [
            edge for edge in self._edges if edge.source != entity and edge.target != entity
        ]
        return original_len - len(self._edges)

    def to_dict(self) -> dict:
        out: dict = {
            "entities": dict(self._entities),
            "edges": [edge.to_dict() for edge in self._edges],
        }
        # v0.5.0 (#190) — only emit the provenance map when at least one
        # entity has a recorded source memory. Keeps the on-disk shape stable
        # for graphs that were populated before provenance landed.
        if self._provenance:
            out["provenance"] = {k: list(v) for k, v in self._provenance.items()}
        return out

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeGraph:
        graph = cls()
        for name, entity_type in data.get("entities", {}).items():
            graph.add_entity(name, entity_type)
        for edge_data in data.get("edges", []):
            if "valid_from" in edge_data:
                edge = TemporalEdge.from_dict(edge_data)
                graph._edges.append(edge)
                if edge.source not in graph._entities:
                    graph._entities[edge.source] = "unknown"
                if edge.target not in graph._entities:
                    graph._entities[edge.target] = "unknown"
            else:
                graph.add_relationship(
                    edge_data["source"], edge_data["target"], edge_data["relation"]
                )
        prov = data.get("provenance") or {}
        for name, ids in prov.items():
            if isinstance(ids, list):
                graph._provenance[name] = [str(i) for i in ids]
        return graph

    # ============ Typed views (v0.5.0 / #108, #190) ============

    def list_nodes(
        self,
        *,
        type: str | None = None,  # noqa: A002 - public param name
        name_match: str | None = None,
        limit: int | None = None,
    ) -> list[GraphNode]:
        """Return a typed list of nodes, optionally filtered.

        ``type``: when set, only nodes whose entity_type matches are returned.
        ``name_match``: case-insensitive substring filter on the node name.
        ``limit``: clamp the result count.
        """
        out: list[GraphNode] = []
        match_lc = name_match.lower() if name_match else None
        for name, etype in self._entities.items():
            if type is not None and etype != type:
                continue
            if match_lc is not None and match_lc not in name.lower():
                continue
            out.append(
                GraphNode(
                    id=name,
                    type=etype or "unknown",
                    name=name,
                    provenance=list(self._provenance.get(name, [])),
                )
            )
            if limit is not None and len(out) >= limit:
                break
        return out

    def list_edges(
        self,
        *,
        source: str | None = None,
        target: str | None = None,
        relation: str | None = None,
    ) -> list[GraphEdge]:
        """Return a typed list of currently-active edges."""
        out: list[GraphEdge] = []
        for edge in self._edges:
            if not edge.is_currently_active():
                continue
            if source is not None and edge.source != source:
                continue
            if target is not None and edge.target != target:
                continue
            if relation is not None and edge.relation != relation:
                continue
            prov: list[str] = []
            meta = edge.metadata or {}
            if isinstance(meta, dict):
                src_id = meta.get("source_memory_id")
                if src_id:
                    prov.append(str(src_id))
                extra = meta.get("provenance")
                if isinstance(extra, list):
                    for pid in extra:
                        s = str(pid)
                        if s and s not in prov:
                            prov.append(s)
            out.append(
                GraphEdge(
                    source=edge.source,
                    target=edge.target,
                    relation=edge.relation,
                    weight=edge.weight,
                    provenance=prov,
                    metadata=edge.metadata if edge.metadata else None,
                )
            )
        return out

    def neighbors_typed(
        self,
        node_id: str,
        depth: int = 1,
        types: list[str] | None = None,
    ) -> list[GraphNode]:
        """BFS neighbors as :class:`GraphNode` instances.

        ``depth``: how many hops out from ``node_id`` to expand. ``depth=1``
        returns direct neighbors; ``depth=0`` returns just ``node_id`` itself.

        ``types``: optional whitelist — only nodes whose entity_type matches
        appear in the result. The starting node is always included so the
        caller can inspect the source even when its type doesn't match.
        """
        if node_id not in self._entities:
            return []
        visited: dict[str, int] = {node_id: 0}
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        order: list[str] = [node_id]
        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue
            for neighbor in self._active_neighbors(current):
                if neighbor not in visited:
                    visited[neighbor] = d + 1
                    queue.append((neighbor, d + 1))
                    order.append(neighbor)
        type_filter: set[str] | None = set(types) if types else None
        out: list[GraphNode] = []
        for name in order:
            etype = self._entities.get(name, "unknown")
            if name != node_id and type_filter is not None and etype not in type_filter:
                continue
            out.append(
                GraphNode(
                    id=name,
                    type=etype or "unknown",
                    name=name,
                    depth=visited[name],
                    provenance=list(self._provenance.get(name, [])),
                )
            )
        return out

    def find_path_typed(
        self,
        source: str,
        target: str,
        max_depth: int = 4,
    ) -> list[GraphEdge] | None:
        """Shortest path BFS — returns the chain of edges from source to target.

        Returns ``None`` when either endpoint is unknown or no path exists
        within ``max_depth`` hops. Returns ``[]`` when ``source == target``
        (zero-length path).

        Edges are returned in traversal order; the path is reconstructed by
        walking the parent pointers, so for an A->B->C path the result is
        ``[A->B edge, B->C edge]``.
        """
        if source not in self._entities or target not in self._entities:
            return None
        if source == target:
            return []
        # parent[node] = (predecessor, edge_used)
        parent: dict[str, tuple[str, GraphEdge]] = {}
        visited: set[str] = {source}
        queue: deque[tuple[str, int]] = deque([(source, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in self._edges:
                if not edge.is_currently_active():
                    continue
                if edge.source == current:
                    nxt = edge.target
                elif edge.target == current:
                    nxt = edge.source
                else:
                    continue
                if nxt in visited:
                    continue
                visited.add(nxt)
                parent[nxt] = (
                    current,
                    GraphEdge(
                        source=edge.source,
                        target=edge.target,
                        relation=edge.relation,
                        weight=edge.weight,
                        metadata=edge.metadata if edge.metadata else None,
                    ),
                )
                if nxt == target:
                    # Reconstruct path
                    path: list[GraphEdge] = []
                    cur = target
                    while cur != source:
                        prev, edge_used = parent[cur]
                        path.append(edge_used)
                        cur = prev
                    path.reverse()
                    return path
                queue.append((nxt, depth + 1))
        return None

    def to_mermaid(self) -> str:
        """Render the entire graph as a Mermaid ``graph LR`` block."""
        nodes = self.list_nodes()
        edges = self.list_edges()
        from soul_protocol.runtime.memory.graph_types import _render_mermaid

        return _render_mermaid(nodes, edges)


def _merge_edge_metadata(existing: dict | None, incoming: dict) -> dict:
    """Combine an edge's stored metadata with a new extraction's metadata.

    Used by :meth:`KnowledgeGraph.add_relationship` when re-extraction hits
    an existing edge: we want to retain the original ``source_memory_id``
    while recording the new one in a ``provenance`` list. Other keys from
    the incoming dict overwrite (e.g. updated ``confidence``).
    """
    out: dict = dict(existing) if isinstance(existing, dict) else {}
    incoming_src = incoming.get("source_memory_id")
    out_src = out.get("source_memory_id")
    if incoming_src and out_src and incoming_src != out_src:
        prov = out.get("provenance") or []
        if not isinstance(prov, list):
            prov = []
        if out_src not in prov:
            prov.append(out_src)
        if incoming_src not in prov:
            prov.append(incoming_src)
        out["provenance"] = prov
        # Keep first source as the canonical one for back-compat with
        # callers that just read source_memory_id.
    elif incoming_src and not out_src:
        out["source_memory_id"] = incoming_src
    for k, v in incoming.items():
        if k in ("source_memory_id", "provenance"):
            continue
        out[k] = v
    return out
