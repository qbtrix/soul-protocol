# bond.py — Human-Soul Bond model for tracking relationship strength
# Updated: 2026-04-29 (#42) — BondRegistry now accepts an optional
#   ``on_change`` callback ``(action, user_id, delta, new_strength) -> None``
#   that fires after each strengthen/weaken. Soul wires it to its
#   TrustChainManager so bond mutations land in the signed audit log.
#   Pure additive: existing callers that ignore the callback see no change.
# Updated: 2026-04-29 (#46) — Added BondRegistry for multi-user soul support.
#   Wraps a default Bond plus a dict of per-user bonds keyed by user_id.
#   Exposes Bond-like proxy attributes (bond_strength, interaction_count,
#   bonded_to, bonded_at) that delegate to the default bond, so existing
#   callers reading ``soul.bond.bond_strength`` keep working unchanged.
#   strengthen()/weaken() accept a ``user_id`` keyword-only arg to route
#   to a per-user bond when given, default bond otherwise.
# Updated: feat/spec-multi-participant — No structural changes. Bond model is
#   per-relationship; multi-bond tracking is managed at the Identity level
#   via BondTarget list.
# Updated: phase1-ablation-fixes — Changed strengthen() to logarithmic growth curve.
#   At bond=50 effective gain is 0.5 per interaction; at bond=90 gain is 0.1.
#   Reaching 99 from 50 takes ~460 interactions. Weaken stays linear (sharp).
# Created: 2026-03-06 — Implements Bond model with strengthen/weaken mechanics
# Updated: Added structured logging for bond strength changes.

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Callback signature: (action, user_id, delta, new_strength).
# action ∈ {"bond.strengthen", "bond.weaken"}; user_id is None for the
# default bond. Used by Soul to bridge bond mutations into the trust chain
# without leaking trust-chain knowledge into Bond/BondRegistry.
BondChangeCallback = Callable[[str, str | None, float, float], None]


class Bond(BaseModel):
    """The relationship between a human and their soul."""

    bonded_to: str = ""  # Human's DID or identifier
    bonded_at: datetime = Field(default_factory=datetime.now)
    bond_strength: float = Field(default=50.0, ge=0, le=100)  # 0-100, evolves over time
    interaction_count: int = 0

    def strengthen(self, amount: float = 1.0) -> None:
        """Strengthen the bond (called after positive interactions).

        Uses logarithmic growth: effective gain scales with remaining headroom.
        At bond=50 the effective gain is amount * 0.5; at bond=90 it's amount * 0.1.
        This makes early bonding feel natural while making deep trust hard-earned.
        """
        remaining = 100.0 - self.bond_strength
        effective = amount * (remaining / 100.0)
        self.bond_strength = min(100.0, self.bond_strength + effective)
        self.interaction_count += 1
        logger.debug(
            "Bond strengthened: strength=%.1f, interactions=%d",
            self.bond_strength,
            self.interaction_count,
        )

    def weaken(self, amount: float = 0.5) -> None:
        """Weaken bond (time decay or negative interactions)."""
        self.bond_strength = max(0.0, self.bond_strength - amount)


class BondRegistry:
    """Per-user bond registry for multi-user souls (#46).

    Wraps a default :class:`Bond` (the soul's primary bond, kept on
    ``Identity.bond`` for back-compat) plus a dict of per-user bonds keyed
    by ``user_id``. Quacks like a :class:`Bond` for callers that only care
    about the default — reading ``registry.bond_strength`` returns the
    default bond's strength, ``registry.strengthen(amount)`` strengthens
    the default. Pass ``user_id`` to route to a per-user bond instead.

    The registry creates per-user :class:`Bond` instances lazily — calling
    :meth:`for_user` or passing ``user_id`` to :meth:`strengthen` /
    :meth:`weaken` instantiates a new bond seeded from default if absent.
    """

    def __init__(
        self,
        default: Bond | None = None,
        per_user: dict[str, Bond] | None = None,
        on_change: BondChangeCallback | None = None,
    ) -> None:
        self._default = default if default is not None else Bond()
        self._per_user: dict[str, Bond] = dict(per_user) if per_user else {}
        self._on_change: BondChangeCallback | None = on_change

    def set_on_change(self, callback: BondChangeCallback | None) -> None:
        """Install or replace the change callback. Use ``None`` to detach."""
        self._on_change = callback

    # ---- Bond proxy attributes (default bond) ----

    @property
    def default(self) -> Bond:
        """The default bond — used when no user_id is supplied."""
        return self._default

    @property
    def bonded_to(self) -> str:
        return self._default.bonded_to

    @bonded_to.setter
    def bonded_to(self, value: str) -> None:
        self._default.bonded_to = value

    @property
    def bonded_at(self) -> datetime:
        return self._default.bonded_at

    @property
    def bond_strength(self) -> float:
        return self._default.bond_strength

    @bond_strength.setter
    def bond_strength(self, value: float) -> None:
        self._default.bond_strength = value

    @property
    def interaction_count(self) -> int:
        return self._default.interaction_count

    # ---- Multi-user accessors ----

    def for_user(self, user_id: str) -> Bond:
        """Return the bond for ``user_id``, creating one if missing.

        New bonds default to ``Bond()`` (strength=50, count=0) with their
        ``bonded_to`` field set to the user_id. The default bond is never
        returned from this method — call :attr:`default` for that.
        """
        bond = self._per_user.get(user_id)
        if bond is None:
            bond = Bond(bonded_to=user_id)
            self._per_user[user_id] = bond
        return bond

    def has_user(self, user_id: str) -> bool:
        """True if a per-user bond exists for ``user_id``."""
        return user_id in self._per_user

    def users(self) -> list[str]:
        """List of user_ids with their own per-user bonds.

        Does not include the default bond's ``bonded_to`` (that's the
        soul's primary user, tracked on Identity).
        """
        return list(self._per_user.keys())

    def all_bonds(self) -> dict[str, Bond]:
        """Snapshot of all per-user bonds (excludes the default)."""
        return dict(self._per_user)

    # ---- Operations ----

    def strengthen(self, amount: float = 1.0, *, user_id: str | None = None) -> None:
        """Strengthen the bond — default bond if user_id is None, else per-user.

        Per-user bonds are created on first call with default strength=50.
        Fires ``on_change("bond.strengthen", user_id, amount, new_strength)``
        when a callback is installed (#42).
        """
        bond = self._default if user_id is None else self.for_user(user_id)
        bond.strengthen(amount)
        if self._on_change is not None:
            try:
                self._on_change("bond.strengthen", user_id, amount, bond.bond_strength)
            except Exception as e:  # pragma: no cover — defensive
                logger.warning("BondRegistry on_change callback failed: %s", e)

    def weaken(self, amount: float = 0.5, *, user_id: str | None = None) -> None:
        """Weaken the bond — default if user_id is None, else per-user.

        Fires ``on_change("bond.weaken", user_id, amount, new_strength)`` when
        a callback is installed (#42).
        """
        bond = self._default if user_id is None else self.for_user(user_id)
        bond.weaken(amount)
        if self._on_change is not None:
            try:
                self._on_change("bond.weaken", user_id, amount, bond.bond_strength)
            except Exception as e:  # pragma: no cover — defensive
                logger.warning("BondRegistry on_change callback failed: %s", e)

    # ---- Serialization ----

    def to_dict(self) -> dict[str, dict]:
        """Serialize per-user bonds (default bond is serialised separately)."""
        return {uid: b.model_dump(mode="json") for uid, b in self._per_user.items()}

    @classmethod
    def from_dict(cls, default: Bond, per_user_data: dict[str, dict] | None) -> BondRegistry:
        """Reconstruct a registry from a default bond plus serialised per-user data."""
        per_user: dict[str, Bond] = {}
        if per_user_data:
            for uid, data in per_user_data.items():
                if isinstance(data, Bond):
                    per_user[uid] = data
                else:
                    per_user[uid] = Bond.model_validate(data)
        return cls(default=default, per_user=per_user)
