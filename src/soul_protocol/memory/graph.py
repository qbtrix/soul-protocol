# memory/graph.py — KnowledgeGraph for entity relationships.
# Created: 2026-02-22
# Simple in-memory knowledge graph using plain dicts (no networkx dependency).
# Stores entities with types and directed relationships between them.
# Supports serialization/deserialization for persistence.

from __future__ import annotations


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
        self._edges: list[tuple[str, str, str]] = []  # (source, target, relation)

    def add_entity(self, name: str, entity_type: str = "unknown") -> None:
        """Add or update an entity in the graph.

        If the entity already exists, its type is updated.
        """
        self._entities[name] = entity_type

    def add_relationship(self, source: str, target: str, relation: str) -> None:
        """Add a directed relationship between two entities.

        Both entities are auto-created if they don't exist yet.
        Duplicate edges (same source, target, relation) are ignored.
        """
        # Auto-create entities if missing
        if source not in self._entities:
            self._entities[source] = "unknown"
        if target not in self._entities:
            self._entities[target] = "unknown"

        edge = (source, target, relation)
        if edge not in self._edges:
            self._edges.append(edge)

    def get_related(self, entity: str) -> list[dict]:
        """Get all relationships involving an entity (as source or target).

        Returns a list of dicts with keys: source, target, relation, direction.
        direction is "outgoing" if entity is the source, "incoming" if target.
        """
        results: list[dict] = []
        for source, target, relation in self._edges:
            if source == entity:
                results.append(
                    {
                        "source": source,
                        "target": target,
                        "relation": relation,
                        "direction": "outgoing",
                    }
                )
            elif target == entity:
                results.append(
                    {
                        "source": source,
                        "target": target,
                        "relation": relation,
                        "direction": "incoming",
                    }
                )
        return results

    def entities(self) -> list[str]:
        """Return a list of all entity names."""
        return list(self._entities.keys())

    def to_dict(self) -> dict:
        """Serialize the graph to a plain dict for persistence.

        Returns:
            {
                "entities": {"name": "type", ...},
                "edges": [{"source": ..., "target": ..., "relation": ...}, ...]
            }
        """
        return {
            "entities": dict(self._entities),
            "edges": [{"source": s, "target": t, "relation": r} for s, t, r in self._edges],
        }

    @classmethod
    def from_dict(cls, data: dict) -> KnowledgeGraph:
        """Deserialize a graph from a plain dict.

        Args:
            data: Dict with "entities" and "edges" keys as produced by to_dict().
        """
        graph = cls()
        for name, entity_type in data.get("entities", {}).items():
            graph.add_entity(name, entity_type)
        for edge in data.get("edges", []):
            graph.add_relationship(edge["source"], edge["target"], edge["relation"])
        return graph
