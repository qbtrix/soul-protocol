# test_bond.py — Tests for the Human-Soul Bond model
# Created: 2026-03-06 — Bond creation, strengthen, weaken, bounds checking

from __future__ import annotations

import pytest

from soul_protocol.bond import Bond


class TestBondCreation:
    """Tests for Bond default construction."""

    def test_default_bond(self):
        bond = Bond()
        assert bond.bonded_to == ""
        assert bond.bond_strength == 50.0
        assert bond.interaction_count == 0

    def test_bond_with_identifier(self):
        bond = Bond(bonded_to="did:key:user-123")
        assert bond.bonded_to == "did:key:user-123"
        assert bond.bond_strength == 50.0

    def test_bond_with_custom_strength(self):
        bond = Bond(bond_strength=75.0)
        assert bond.bond_strength == 75.0

    def test_bond_bonded_at_set(self):
        bond = Bond()
        assert bond.bonded_at is not None


class TestStrengthen:
    """Tests for Bond.strengthen()."""

    def test_strengthen_default(self):
        bond = Bond(bond_strength=50.0)
        bond.strengthen()
        assert bond.bond_strength == 51.0
        assert bond.interaction_count == 1

    def test_strengthen_custom_amount(self):
        bond = Bond(bond_strength=50.0)
        bond.strengthen(10.0)
        assert bond.bond_strength == 60.0
        assert bond.interaction_count == 1

    def test_strengthen_increments_interaction_count(self):
        bond = Bond(bond_strength=50.0)
        bond.strengthen()
        bond.strengthen()
        bond.strengthen()
        assert bond.interaction_count == 3

    def test_strengthen_caps_at_100(self):
        bond = Bond(bond_strength=99.5)
        bond.strengthen(5.0)
        assert bond.bond_strength == 100.0


class TestWeaken:
    """Tests for Bond.weaken()."""

    def test_weaken_default(self):
        bond = Bond(bond_strength=50.0)
        bond.weaken()
        assert bond.bond_strength == 49.5

    def test_weaken_custom_amount(self):
        bond = Bond(bond_strength=50.0)
        bond.weaken(10.0)
        assert bond.bond_strength == 40.0

    def test_weaken_floors_at_zero(self):
        bond = Bond(bond_strength=0.3)
        bond.weaken(1.0)
        assert bond.bond_strength == 0.0

    def test_weaken_does_not_change_interaction_count(self):
        bond = Bond(bond_strength=50.0, interaction_count=5)
        bond.weaken()
        assert bond.interaction_count == 5


class TestBoundsValidation:
    """Test Pydantic validation on bond_strength bounds."""

    def test_bond_strength_too_high(self):
        with pytest.raises(Exception):
            Bond(bond_strength=101.0)

    def test_bond_strength_too_low(self):
        with pytest.raises(Exception):
            Bond(bond_strength=-1.0)

    def test_bond_strength_at_zero(self):
        bond = Bond(bond_strength=0.0)
        assert bond.bond_strength == 0.0

    def test_bond_strength_at_100(self):
        bond = Bond(bond_strength=100.0)
        assert bond.bond_strength == 100.0
