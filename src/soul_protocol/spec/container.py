# container.py — SoulContainer: the root primitive of the core layer.
# Created: v0.4.0 — Schema-free soul container that holds an Identity and
# a MemoryStore. Supports create/open/save lifecycle. No opinions about
# personality models, cognitive engines, or evolution systems.

from __future__ import annotations

from pathlib import Path
from typing import Any

from .identity import Identity
from .memory import DictMemoryStore, MemoryStore
from .soul_file import pack_soul, unpack_to_container


class SoulContainer:
    """A soul container — schema-free portable AI identity.

    This is the "HTTP layer" primitive: it holds an identity and a memory
    store, and can serialize to/from .soul files. It has no opinions about
    personality models (OCEAN, Big Five), cognitive engines, evolution,
    or state management — those belong to higher layers.

    Usage::

        # Create a new soul
        soul = SoulContainer.create("Aria", traits={"role": "assistant"})
        soul.memory.store("episodic", MemoryEntry(content="Hello!", layer="episodic"))
        soul.save("aria.soul")

        # Open an existing soul
        soul = SoulContainer.open("aria.soul")
        memories = soul.memory.recall("episodic", limit=5)
    """

    def __init__(
        self,
        identity: Identity,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self._identity = identity
        self._memory: MemoryStore = memory_store or DictMemoryStore()

    @classmethod
    def create(
        cls,
        name: str,
        *,
        traits: dict[str, Any] | None = None,
    ) -> SoulContainer:
        """Create a new soul with the given name and optional traits.

        Args:
            name: The soul's name.
            traits: Arbitrary key-value pairs (personality scores,
                    role, archetype, etc.). Defaults to empty dict.

        Returns:
            A new SoulContainer ready to use.
        """
        identity = Identity(
            name=name,
            traits=traits or {},
        )
        return cls(identity)

    @classmethod
    def open(cls, path: str | Path) -> SoulContainer:
        """Open a .soul file from disk.

        Args:
            path: Path to a .soul file (zip archive).

        Returns:
            A SoulContainer populated from the file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file is not a valid .soul archive.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Soul file not found: {file_path}")

        data = file_path.read_bytes()
        identity, memory_store = unpack_to_container(data)
        return cls(identity, memory_store)

    def save(self, path: str | Path) -> None:
        """Save the soul to a .soul file.

        Args:
            path: Destination file path. Will overwrite if exists.
        """
        data = pack_soul(self._identity, self._memory)
        Path(path).write_bytes(data)

    @property
    def identity(self) -> Identity:
        """The soul's identity."""
        return self._identity

    @property
    def memory(self) -> MemoryStore:
        """The soul's memory store."""
        return self._memory

    @property
    def name(self) -> str:
        """Convenience: the soul's name."""
        return self._identity.name

    @property
    def id(self) -> str:
        """Convenience: the soul's ID."""
        return self._identity.id

    def __repr__(self) -> str:
        return f"SoulContainer(name={self._identity.name!r}, id={self._identity.id!r})"
