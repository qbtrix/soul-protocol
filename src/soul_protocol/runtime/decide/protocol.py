# decide/protocol.py — The Decider protocol: one interface for every decision backend.
# Created: feat/soul-instinct — A decider answers typed DecisionRequests with a
#   typed Decision. Backends declare which DecisionKinds they support and may
#   abstain (return None) on any request, e.g. a local contradiction classifier
#   that only handles DecisionKind.CONTRADICTION.

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from soul_protocol.runtime.decide.types import Decision, DecisionKind, DecisionRequest


@runtime_checkable
class Decider(Protocol):
    """Interface for anything that can answer Soul's memory-pipeline decisions.

    Simplest implementation::

        class MyDecider:
            name = "my-decider"

            def supports(self, kind: DecisionKind) -> bool:
                return kind == DecisionKind.CONTRADICTION

            async def decide(self, request: DecisionRequest) -> Decision | None:
                ...
    """

    name: str

    def supports(self, kind: DecisionKind) -> bool:
        """Return True if this decider can answer requests of ``kind``."""
        ...

    async def decide(self, request: DecisionRequest) -> Decision[Any] | None:
        """Answer ``request``, or return None to abstain."""
        ...
