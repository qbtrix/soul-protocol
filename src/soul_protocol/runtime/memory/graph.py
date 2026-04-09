# memory/graph.py — KnowledgeGraph for entity relationships.
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


class TemporalEdge:
    """A directed relationship with temporal validity."""

    __slots__ = ("source", "target", "relation", "valid_from", "valid_to", "metadata")

    def __init__(
        self,
        source: str,
        target: str,
        relation: str,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.source = source
        self.target = target
        self.relation = relation
        self.valid_from = valid_from or datetime.now()
        self.valid_to = valid_to
        self.metadata = metadata

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
        )


class KnowledgeGraph:
    """Simple dict-based knowledge graph for entity relationships."""

    def __init__(self) -> None:
        self._entities: dict[str, str] = {}
        self._edges: list[TemporalEdge] = []

    def add_entity(self, name: str, entity_type: str = "unknown") -> None:
        self._entities[name] = entity_type

    def add_relationship(
        self,
        source: str,
        target: str,
        relation: str,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        metadata: dict | None = None,
    ) -> None:
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
                return
        self._edges.append(
            TemporalEdge(
                source=source,
                target=target,
                relation=relation,
                valid_from=valid_from,
                valid_to=valid_to,
                metadata=metadata,
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
        original_len = len(self._edges)
        self._edges = [
            edge for edge in self._edges if edge.source != entity and edge.target != entity
        ]
        return original_len - len(self._edges)

    def to_dict(self) -> dict:
        return {
            "entities": dict(self._entities),
            "edges": [edge.to_dict() for edge in self._edges],
        }

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
        return graph
