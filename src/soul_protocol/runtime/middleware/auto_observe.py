# middleware/auto_observe.py — Auto-capture conversation turns with optional recall.
# Created: 2026-05 — Wraps a Soul so every conversation turn is captured without
#   the caller remembering to call Soul.observe(). A single turn() entry point
#   performs optional auto-recall (when a query is given) followed by mandatory
#   auto-observe, returning recalled memories plus the soul's updated state.
#   This is the reusable runtime primitive behind the MCP ``soul_sync`` tool and
#   the intended request/response-path hook for gateways and SDKs.
# Updated: 2026-10 (#320 review) — Added memory_to_dict(), the shared
#   MemoryEntry -> response-dict mapping used by turn() and the MCP soul_recall
#   tool so the two response shapes cannot drift. Documented that ``domain``
#   scopes both recall and the observed turn's writes.

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from soul_protocol.runtime.types import Interaction

if TYPE_CHECKING:
    from soul_protocol.runtime.soul import Soul
    from soul_protocol.runtime.types import MemoryEntry


def memory_to_dict(entry: MemoryEntry) -> dict[str, Any]:
    """Serialize a recalled memory into the public recall response shape.

    Shared by :meth:`AutoObserveMiddleware.turn` and the MCP ``soul_recall``
    tool so both return identical memory dicts.
    """
    return {
        "id": entry.id,
        "type": entry.type.value,
        "layer": entry.layer or entry.type.value,
        "domain": entry.domain or "default",
        "content": entry.content,
        "importance": entry.importance,
        "emotion": entry.emotion,
        "user_id": entry.user_id,
    }


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
            user_id: Scopes both halves of the turn (multi-user souls, #46):
                recall is restricted to this user's memories (plus legacy
                unattributed ones), and every memory written by the observe
                step is stamped with it.
            layer: Restrict recall to a single layer (#41). Recall only;
                the observe pipeline decides which layers it writes to.
            domain: Scopes both halves of the turn (#41): recall is
                restricted to this domain, and memories written by the
                observe step are stored in it. Omit to recall across all
                domains and store the turn in ``"default"``.
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
            memories = [memory_to_dict(r) for r in results]

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
