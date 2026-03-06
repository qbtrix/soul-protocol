# memory/graph.py — KnowledgeGraph for entity relationships.
# Created: 2026-02-22
# Updated: 2026-03-06 — Added temporal fields (valid_from, valid_to) to edges.
#   New methods: as_of_date(), relationship_evolution(), expire_relationship().
#   Backward-compatible: edges without temporal fields default to always-valid.
# Simple in-memory knowledge graph using plain dicts (no networkx dependency).
# Stores entities with types and directed relationships between them.
# Supports serialization/deserialization for persistence.

from __future__ import annotations

from datetime import datetime


class TemporalEdge:
    """A directed relationship with temporal validity.

    Attributes:
        source: The source entity name.
        target: The target entity name.
        relation: The relationship type/verb.
        valid_from: When this relationship became active.
        valid_to: When this relationship ended (None = still active).
    """

    __slots__ = ("source", "target", "relation", "valid_from", "valid_to")

    def __init__(
        self,
        source: str,
        target: str,
        relation: str,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> None:
        self.source = source
        self.target = target
        self.relation = relation
        self.valid_from = valid_from or datetime.now()
        self.valid_to = valid_to

    def is_active_at(self, dt: datetime) -> bool:
        """Check if this edge is active at a specific datetime."""
        if self.valid_from > dt:
            return False
        if self.valid_to is not None and self.valid_to < dt:
            return False
        return True

    def is_currently_active(self) -> bool:
        """Check if this edge is currently active (no end date)."""
        return self.valid_to is None

    def as_tuple(self) -> tuple[str, str, str]:
        """Return the (source, target, relation) triple for backward compat."""
        return (self.source, self.target, self.relation)

    def to_dict(self) -> dict:
        """Serialize to a plain dict."""
        d: dict = {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "valid_from": self.valid_from.isoformat(),
        }
        if self.valid_to is not None:
            d["valid_to"] = self.valid_to.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> TemporalEdge:
        """Deserialize from a plain dict."""
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
        )


class KnowledgeGraph:
    """Simple dict-based knowledge graph for entity relationships.

    Tracks entities (people, places, concepts) and directed relationships
    between them. No external dependencies — uses plain Python dicts.

    Internal structure:
      _entities: {name: entity_type}
      _edges: [(source, target, relation)]
    """

    def __init__(self) -> None:
        self._entities: dict[str, str] = {}  # name -> entity_type
        self._edges: list[TemporalEdge] = []

    def add_entity(self, name: str, entity_type: str = "unknown") -> None:
        """Add or update an entity in the graph.

        If the entity already exists, its type is updated.
        """
        self._entities[name] = entity_type

    def add_relationship(
        self,
        source: str,
        target: str,
        relation: str,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
    ) -> None:
        """Add a directed relationship between two entities.

        Both entities are auto-created if they don't exist yet.
        Duplicate edges (same source, target, relation) are ignored
        when checking currently active edges.

        Args:
            source: Source entity name.
            target: Target entity name.
            relation: Relationship type/verb.
            valid_from: When this relationship started (defaults to now).
            valid_to: When this relationship ended (None = still active).
        """
        # Auto-create entities if missing
        if source not in self._entities:
            self._entities[source] = "unknown"
        if target not in self._entities:
            self._entities[target] = "unknown"

        # Check for duplicate active edges with same (source, target, relation)
        for edge in self._edges:
            if (
                edge.source == source
                and edge.target == target
                and edge.relation == relation
                and edge.is_currently_active()
            ):
                return  # Already exists and is active

        self._edges.append(
            TemporalEdge(
                source=source,
                target=target,
                relation=relation,
                valid_from=valid_from,
                valid_to=valid_to,
            )
        )

    def get_related(self, entity: str) -> list[dict]:
        """Get all relationships involving an entity (as source or target).

        Returns a list of dicts with keys: source, target, relation, direction.
        direction is "outgoing" if entity is the source, "incoming" if target.
        Only returns currently active relationships.
        """
        results: list[dict] = []
        for edge in self._edges:
            if not edge.is_currently_active():
                continue
            if edge.source == entity:
                results.append(
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "relation": edge.relation,
                        "direction": "outgoing",
                    }
                )
            elif edge.target == entity:
                results.append(
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "relation": edge.relation,
                        "direction": "incoming",
                    }
                )
        return results

    def entities(self) -> list[str]:
        """Return a list of all entity names."""
        return list(self._entities.keys())

    def expire_relationship(
        self, source: str, target: str, relation: str, expire_at: datetime | None = None
    ) -> bool:
        """Mark a relationship as expired (set valid_to).

        Only affects the first matching active edge. Returns True if found.

        Args:
            source: Source entity name.
            target: Target entity name.
            relation: Relationship type.
            expire_at: When the relationship ended (defaults to now).

        Returns:
            True if a matching active edge was found and expired.
        """
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
        """Get all relationships that were active at a specific point in time.

        Returns a list of dicts with keys: source, target, relation,
        valid_from, valid_to.

        Args:
            dt: The point-in-time to query.

        Returns:
            List of relationship dicts active at the given datetime.
        """
        results: list[dict] = []
        for edge in self._edges:
            if edge.is_active_at(dt):
                results.append(
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "relation": edge.relation,
                        "valid_from": edge.valid_from,
                        "valid_to": edge.valid_to,
                    }
                )
        return results

    def relationship_evolution(self, source: str, target: str) -> list[dict]:
        """Get the full history of relationships between two entities.

        Returns all edges (active and expired) between source and target,
        sorted chronologically by valid_from.

        Args:
            source: Source entity name.
            target: Target entity name.

        Returns:
            List of relationship dicts sorted by valid_from.
        """
        results: list[dict] = []
        for edge in self._edges:
            if edge.source == source and edge.target == target:
                results.append(
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "relation": edge.relation,
                        "valid_from": edge.valid_from,
                        "valid_to": edge.valid_to,
                    }
                )
        results.sort(key=lambda r: r["valid_from"])
        return results

    def to_dict(self) -> dict:
        """Serialize the graph to a plain dict for persistence.

        Returns:
            {
                "entities": {"name": "type", ...},
                "edges": [{"source": ..., "target": ..., "relation": ..., ...}, ...]
            }
        """
        return {
            "entities": dict(self._entities),
            "edges": [edge.to_dict() for edge in self._edges],
        }

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeGraph:
        """Deserialize a graph from a plain dict.

        Args:
            data: Dict with "entities" and "edges" keys as produced by to_dict().
                  Edges may include temporal fields (valid_from, valid_to).
        """
        graph = cls()
        for name, entity_type in data.get("entities", {}).items():
            graph.add_entity(name, entity_type)
        for edge_data in data.get("edges", []):
            # Support both old format (no temporal) and new format
            if "valid_from" in edge_data:
                edge = TemporalEdge.from_dict(edge_data)
                graph._edges.append(edge)
                # Auto-create entities
                if edge.source not in graph._entities:
                    graph._entities[edge.source] = "unknown"
                if edge.target not in graph._entities:
                    graph._entities[edge.target] = "unknown"
            else:
                graph.add_relationship(
                    edge_data["source"],
                    edge_data["target"],
                    edge_data["relation"],
                )
        return graph
