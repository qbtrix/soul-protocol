# middleware/auto_observe.py — Auto-capture conversation turns with optional recall.
# Created: 2026-05 — Wraps a Soul so every conversation turn is captured without
#   the caller remembering to call Soul.observe(). A single turn() entry point
#   performs optional auto-recall (when a query is given) followed by mandatory
#   auto-observe, returning recalled memories plus the soul's updated state.
#   This is the reusable runtime primitive behind the MCP ``soul_sync`` tool and
#   the intended request/response-path hook for gateways and SDKs.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from soul_protocol.runtime.types import Interaction

if TYPE_CHECKING:
    from soul_protocol.runtime.soul import Soul


class AutoObserveMiddleware:
    """Wrap a :class:`Soul` so turns are captured automatically.

    A single :meth:`turn` call performs optional auto-recall (when ``query``
    is given) and mandatory auto-observe, returning recalled memories plus the
    soul's updated state. Callers never need to remember to call
    :meth:`Soul.observe` themselves — ideal for gateways, SDKs, and agents
    that sit in the request/response path.

    Construction::

        middleware = AutoObserveMiddleware(soul)
        result = await middleware.turn(
            user_input, agent_output, query="...", user_id="..."
        )
    """

    def __init__(
        self,
        soul: Soul,
        *,
        recall_limit: int = 5,
        default_channel: str = "auto",
    ) -> None:
        self._soul = soul
        self._recall_limit = recall_limit
        self._default_channel = default_channel

    @property
    def soul(self) -> Soul:
        """The wrapped soul."""
        return self._soul

    async def turn(
        self,
        user_input: str,
        agent_output: str = "",
        *,
        query: str | None = None,
        limit: int | None = None,
        user_id: str | None = None,
        layer: str | None = None,
        domain: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """Capture one conversation turn (auto-recall + auto-observe).

        Args:
            user_input: What the user said.
            agent_output: What the agent responded (optional; omit for
                user-only turns).
            query: Optional recall query. When set, relevant memories are
                returned before the turn is observed.
            limit: Max recall results (defaults to ``recall_limit``).
            user_id: Attribute the turn to a user (multi-user souls, #46).
            layer: Restrict recall to a single layer (#41). Optional.
            domain: Sub-namespace for the written memories (#41). Optional.
            channel: Source channel (defaults to ``default_channel``).

        Returns:
            A dict with ``soul``, ``mood``, ``energy``, ``user_id``,
            ``recalled`` and ``memories`` keys.
        """
        memories: list[dict[str, Any]] = []
        if query:
            results = await self._soul.recall(
                query,
                limit=limit if limit is not None else self._recall_limit,
                user_id=user_id,
                layer=layer,
                domain=domain,
            )
            memories = [
                {
                    "id": r.id,
                    "type": r.type.value,
                    "layer": r.layer or r.type.value,
                    "domain": r.domain or "default",
                    "content": r.content,
                    "importance": r.importance,
                    "emotion": r.emotion,
                    "user_id": r.user_id,
                }
                for r in results
            ]

        await self._soul.observe(
            Interaction(
                user_input=user_input,
                agent_output=agent_output,
                channel=channel or self._default_channel,
            ),
            user_id=user_id,
            domain=domain or "default",
        )

        state = self._soul.state
        return {
            "soul": self._soul.name,
            "mood": state.mood.value,
            "energy": round(state.energy, 1),
            "user_id": user_id,
            "recalled": len(memories),
            "memories": memories,
        }
