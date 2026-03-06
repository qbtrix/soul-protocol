# Engine-level module — opinionated bond mechanics. Not part of the core protocol.
# bond.py — Human-Soul Bond model for tracking relationship strength
# Created: 2026-03-06 — Implements Bond model with strengthen/weaken mechanics

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Bond(BaseModel):
    """The relationship between a human and their soul."""

    bonded_to: str = ""  # Human's DID or identifier
    bonded_at: datetime = Field(default_factory=datetime.now)
    bond_strength: float = Field(default=50.0, ge=0, le=100)  # 0-100, evolves over time
    interaction_count: int = 0

    def strengthen(self, amount: float = 1.0) -> None:
        """Strengthen the bond (called after positive interactions)."""
        self.bond_strength = min(100.0, self.bond_strength + amount)
        self.interaction_count += 1

    def weaken(self, amount: float = 0.5) -> None:
        """Weaken bond (time decay or negative interactions)."""
        self.bond_strength = max(0.0, self.bond_strength - amount)
