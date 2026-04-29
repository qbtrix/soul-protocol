# middleware/domain_isolation.py — Restrict a Soul to a fixed set of domains.
# Created: 2026-04-29 (#41) — Wraps a Soul and enforces a domain allow-list:
#   reads silently filter to allowed domains; writes raise DomainAccessError
#   when the requested domain isn't allowed; observe() and remember() default
#   the domain to ``allowed_domains[0]`` when the caller doesn't specify one.
#   Use to give one bonded user / agent a sandboxed view of the soul without
#   handing them the full memory store.

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from soul_protocol.runtime.exceptions import DomainAccessError

if TYPE_CHECKING:
    from soul_protocol.runtime.soul import Soul
    from soul_protocol.runtime.types import (
        Interaction,
        MemoryEntry,
        MemoryType,
        MemoryVisibility,
    )


class DomainIsolationMiddleware:
    """Sandbox a :class:`Soul` to a fixed allow-list of memory domains.

    Construction::

        middleware = DomainIsolationMiddleware(
            soul,
            allowed_domains=["finance", "default"],
        )

    Reads (``recall``) silently filter to allowed domains. The wrapped
    soul never sees memories from other domains.

    Writes (``remember``, ``observe``) raise
    :class:`soul_protocol.runtime.exceptions.DomainAccessError` when the
    requested domain isn't in the allow-list. When the caller doesn't pass
    a ``domain`` keyword, both methods default to ``allowed_domains[0]``
    so the wrapped soul writes into a known-good namespace by default.

    The middleware does NOT modify the underlying Soul's memory layout
    or persisted data. Removing the wrapper restores full access.
    """

    def __init__(
        self,
        soul: Soul,
        *,
        allowed_domains: Sequence[str],
    ) -> None:
        if not allowed_domains:
            raise ValueError("DomainIsolationMiddleware requires at least one allowed domain.")
        self._soul = soul
        self._allowed: list[str] = list(allowed_domains)

    @property
    def soul(self) -> Soul:
        """Return the underlying soul (for callers that need full access)."""
        return self._soul

    @property
    def allowed_domains(self) -> list[str]:
        """List of domain names this middleware allows. First entry is the default."""
        return list(self._allowed)

    def _check_domain(self, domain: str) -> None:
        """Raise DomainAccessError when ``domain`` isn't allowed."""
        if domain not in self._allowed:
            raise DomainAccessError(domain, self._allowed)

    async def remember(
        self,
        content: str,
        *,
        type: MemoryType | None = None,
        importance: int = 5,
        emotion: str | None = None,
        entities: list[str] | None = None,
        visibility: MemoryVisibility | None = None,
        scope: list[str] | None = None,
        domain: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Wrapped :meth:`Soul.remember` that enforces the domain allow-list.

        When ``domain`` is None, defaults to ``allowed_domains[0]``. When
        a non-None domain is passed but isn't in the allow-list, raises
        :class:`DomainAccessError`.
        """
        from soul_protocol.runtime.types import MemoryType, MemoryVisibility

        eff_domain = domain if domain is not None else self._allowed[0]
        self._check_domain(eff_domain)
        return await self._soul.remember(
            content,
            type=type if type is not None else MemoryType.SEMANTIC,
            importance=importance,
            emotion=emotion,
            entities=entities,
            visibility=visibility if visibility is not None else MemoryVisibility.BONDED,
            scope=scope,
            domain=eff_domain,
            user_id=user_id,
        )

    async def observe(
        self,
        interaction: Interaction,
        *,
        user_id: str | None = None,
        domain: str | None = None,
    ) -> None:
        """Wrapped :meth:`Soul.observe` that enforces the domain allow-list.

        Same defaults as :meth:`remember`: ``allowed_domains[0]`` when
        nothing is passed, raises on a disallowed explicit domain.
        """
        eff_domain = domain if domain is not None else self._allowed[0]
        self._check_domain(eff_domain)
        await self._soul.observe(interaction, user_id=user_id, domain=eff_domain)

    async def recall(
        self,
        query: str,
        *,
        limit: int = 10,
        domain: str | None = None,
        layer: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> list[MemoryEntry]:
        """Wrapped :meth:`Soul.recall` that hides memories outside the allow-list.

        Two cases:

        - When ``domain`` is given and allowed, defer to the wrapped soul
          with that filter and return the result unchanged.
        - When ``domain`` is given but disallowed, return an empty list
          (a recall must never leak across the boundary, even by accident).
        - When ``domain`` is None, fetch a wider candidate pool unfiltered
          and post-filter to allowed domains so callers see one merged view.

        ``layer`` and any extra kwargs (``min_importance``, ``scopes``, ...)
        are forwarded as-is.
        """
        if domain is not None:
            if domain not in self._allowed:
                return []
            return await self._soul.recall(
                query,
                limit=limit,
                domain=domain,
                layer=layer,
                user_id=user_id,
                **kwargs,
            )
        # Domain unset: fetch a wider pool and filter post-hoc so the
        # caller sees a merged view of every allowed domain.
        wider = max(limit * len(self._allowed), limit)
        results = await self._soul.recall(
            query,
            limit=wider,
            domain=None,
            layer=layer,
            user_id=user_id,
            **kwargs,
        )
        filtered = [r for r in results if r.domain in self._allowed]
        return filtered[:limit]

    # ------------------------------------------------------------------
    # Convenience pass-through accessors. These are here so callers can
    # still inspect the wrapped soul's identity / state without breaking
    # the abstraction. Mutating accessors aren't exposed.
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """The wrapped soul's display name."""
        return self._soul.name

    @property
    def did(self) -> str:
        """The wrapped soul's DID."""
        return self._soul.did
