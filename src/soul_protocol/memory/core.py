# memory/core.py — CoreMemoryManager for the always-loaded ~2KB core memory.
# Created: 2026-02-22
# Updated: 2026-03-06 — Fixed Bug #15: edit() now replaces values instead of
#   appending. The old append behavior was moved to append() for callers that
#   explicitly want incremental updates.
# Manages the persona description and human profile that are always available
# in context. Supports get/set/edit/append operations on the CoreMemory model.

from __future__ import annotations

from soul_protocol.types import CoreMemory


class CoreMemoryManager:
    """Manages the always-loaded core memory (persona + human profile).

    Core memory is a small (~2KB) block that stays in context at all times.
    It holds two sections:
      - persona: description of the soul's identity, role, and behavior
      - human: profile of the human the soul is bonded to
    """

    def __init__(self, core: CoreMemory) -> None:
        self._core = core

    def get(self) -> CoreMemory:
        """Return the current core memory."""
        return self._core

    def set(self, persona: str | None = None, human: str | None = None) -> None:
        """Replace core memory fields entirely.

        Only provided fields are updated; None fields are left unchanged.
        """
        if persona is not None:
            self._core.persona = persona
        if human is not None:
            self._core.human = human

    def edit(self, persona: str | None = None, human: str | None = None) -> None:
        """Replace core memory fields with new values.

        Only provided fields are updated; None fields are left unchanged.
        This is equivalent to set() — it replaces the value entirely.
        """
        if persona is not None:
            self._core.persona = persona
        if human is not None:
            self._core.human = human

    def append(self, persona: str | None = None, human: str | None = None) -> None:
        """Append to existing core memory fields.

        Appends the given text to the existing persona/human strings,
        separated by a newline. This is useful for incremental updates
        where you want to add context without replacing what's there.
        """
        if persona is not None:
            if self._core.persona:
                self._core.persona = f"{self._core.persona}\n{persona}"
            else:
                self._core.persona = persona
        if human is not None:
            if self._core.human:
                self._core.human = f"{self._core.human}\n{human}"
            else:
                self._core.human = human
