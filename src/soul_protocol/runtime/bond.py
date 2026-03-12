# bond.py — Human-Soul Bond model for tracking relationship strength
# Updated: phase1-ablation-fixes — Changed strengthen() to logarithmic growth curve.
#   At bond=50 effective gain is 0.5 per interaction; at bond=90 gain is 0.1.
#   Reaching 99 from 50 takes ~460 interactions. Weaken stays linear (sharp).
# Created: 2026-03-06 — Implements Bond model with strengthen/weaken mechanics
# Updated: Added structured logging for bond strength changes.

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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
