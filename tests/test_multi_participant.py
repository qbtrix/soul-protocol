# test_multi_participant.py — Tests for multi-participant Interaction model (#95)
# and multi-bond Identity (#94). Covers backward compatibility, new APIs,
# serialization round-trips, and edge cases.

from __future__ import annotations

from datetime import datetime

import pytest

from soul_protocol.runtime.types import (
    BondTarget,
    Identity,
    Interaction,
    Participant,
)
from soul_protocol.spec.identity import BondTarget as CoreBondTarget
from soul_protocol.spec.identity import Identity as CoreIdentity
from soul_protocol.spec.memory import Interaction as CoreInteraction
from soul_protocol.spec.memory import Participant as CoreParticipant

# ============ Issue #95: Multi-participant Interaction ============


class TestParticipant:
    """Tests for the Participant model."""

    def test_create_participant(self):
        p = Participant(role="user", content="hello")
        assert p.role == "user"
        assert p.content == "hello"
        assert p.id is None

    def test_participant_with_id(self):
        p = Participant(role="agent", id="did:key:agent-001", content="hi there")
        assert p.id == "did:key:agent-001"

    def test_participant_serialization(self):
        p = Participant(role="system", content="context")
        data = p.model_dump()
        assert data["role"] == "system"
        assert data["content"] == "context"
        p2 = Participant.model_validate(data)
        assert p2.role == p.role


class TestInteractionBackwardCompat:
    """Tests that the legacy Interaction(user_input=..., agent_output=...) still works."""

    def test_legacy_constructor(self):
        interaction = Interaction(user_input="hello", agent_output="hi there")
        assert interaction.user_input == "hello"
        assert interaction.agent_output == "hi there"

    def test_legacy_constructor_with_channel(self):
        interaction = Interaction(user_input="hello", agent_output="hi", channel="discord")
        assert interaction.channel == "discord"
        assert interaction.user_input == "hello"

    def test_legacy_constructor_with_metadata(self):
        interaction = Interaction(
            user_input="test", agent_output="response", metadata={"key": "val"}
        )
        assert interaction.metadata == {"key": "val"}

    def test_legacy_constructor_creates_participants(self):
        interaction = Interaction(user_input="hello", agent_output="hi")
        assert len(interaction.participants) == 2
        assert interaction.participants[0].role == "user"
        assert interaction.participants[0].content == "hello"
        assert interaction.participants[1].role == "agent"
        assert interaction.participants[1].content == "hi"

    def test_legacy_user_input_only(self):
        interaction = Interaction(user_input="just user")
        assert interaction.user_input == "just user"
        assert interaction.agent_output == ""
        assert len(interaction.participants) == 1

    def test_legacy_agent_output_only(self):
        interaction = Interaction(agent_output="just agent")
        assert interaction.agent_output == "just agent"
        assert interaction.user_input == ""
        assert len(interaction.participants) == 1


class TestInteractionMultiParticipant:
    """Tests for the new multi-participant Interaction API."""

    def test_from_pair(self):
        interaction = Interaction.from_pair("hello", "hi there")
        assert interaction.user_input == "hello"
        assert interaction.agent_output == "hi there"
        assert len(interaction.participants) == 2

    def test_from_pair_with_channel(self):
        interaction = Interaction.from_pair("hello", "hi", channel="slack")
        assert interaction.channel == "slack"

    def test_from_pair_with_timestamp(self):
        ts = datetime(2026, 3, 22, 12, 0, 0)
        interaction = Interaction.from_pair("a", "b", timestamp=ts)
        assert interaction.timestamp == ts

    def test_three_participants(self):
        interaction = Interaction(
            participants=[
                Participant(role="user", content="What should we do?"),
                Participant(role="agent", id="agent-1", content="I suggest X"),
                Participant(role="agent", id="agent-2", content="I suggest Y"),
            ]
        )
        assert interaction.user_input == "What should we do?"
        # agent_output returns first agent
        assert interaction.agent_output == "I suggest X"
        assert len(interaction.participants) == 3

    def test_system_participant(self):
        interaction = Interaction(
            participants=[
                Participant(role="system", content="Context info"),
                Participant(role="user", content="question"),
                Participant(role="agent", content="answer"),
            ]
        )
        assert interaction.user_input == "question"
        assert interaction.agent_output == "answer"

    def test_no_user_participant(self):
        interaction = Interaction(
            participants=[
                Participant(role="agent", content="unsolicited message"),
            ]
        )
        assert interaction.user_input == ""
        assert interaction.agent_output == "unsolicited message"

    def test_no_agent_participant(self):
        interaction = Interaction(
            participants=[
                Participant(role="user", content="hello"),
                Participant(role="observer", content="watching"),
            ]
        )
        assert interaction.user_input == "hello"
        assert interaction.agent_output == ""

    def test_empty_participants(self):
        interaction = Interaction(participants=[])
        assert interaction.user_input == ""
        assert interaction.agent_output == ""

    def test_soul_to_soul_interaction(self):
        interaction = Interaction(
            participants=[
                Participant(role="soul", id="did:soul:a", content="hello friend"),
                Participant(role="soul", id="did:soul:b", content="hi there"),
            ]
        )
        assert interaction.user_input == ""
        assert interaction.agent_output == ""
        assert len(interaction.participants) == 2

    def test_serialization_round_trip(self):
        interaction = Interaction.from_pair("hello", "hi")
        data = interaction.model_dump()
        restored = Interaction.model_validate(data)
        assert restored.user_input == "hello"
        assert restored.agent_output == "hi"
        assert len(restored.participants) == 2

    def test_json_round_trip(self):
        interaction = Interaction(
            participants=[
                Participant(role="user", id="u1", content="test"),
                Participant(role="agent", content="response"),
                Participant(role="observer", content="noted"),
            ],
            channel="test",
            metadata={"session": "abc"},
        )
        json_str = interaction.model_dump_json()
        restored = Interaction.model_validate_json(json_str)
        assert len(restored.participants) == 3
        assert restored.channel == "test"
        assert restored.metadata == {"session": "abc"}

    def test_legacy_does_not_overwrite_explicit_participants(self):
        """If both participants and user_input are given, participants wins."""
        interaction = Interaction(
            participants=[Participant(role="user", content="explicit")],
            user_input="should be ignored",
        )
        # participants was already set, so migration shouldn't add more
        assert interaction.user_input == "explicit"


# ============ Issue #94: Multi-bond Identity ============


class TestBondTarget:
    """Tests for the BondTarget model."""

    def test_create_bond_target(self):
        bt = BondTarget(id="did:key:user-123")
        assert bt.id == "did:key:user-123"
        assert bt.label == ""
        assert bt.bond_type == "human"

    def test_bond_target_with_label(self):
        bt = BondTarget(id="did:key:user-123", label="Alice", bond_type="human")
        assert bt.label == "Alice"

    def test_bond_target_types(self):
        for bt_type in ["human", "soul", "agent", "group", "service"]:
            bt = BondTarget(id="test", bond_type=bt_type)
            assert bt.bond_type == bt_type

    def test_bond_target_serialization(self):
        bt = BondTarget(id="did:key:x", label="Test", bond_type="soul")
        data = bt.model_dump()
        restored = BondTarget.model_validate(data)
        assert restored.id == bt.id
        assert restored.bond_type == "soul"


class TestIdentityMultiBond:
    """Tests for multi-bond Identity."""

    def test_identity_default_no_bonds(self):
        identity = Identity(name="TestSoul")
        assert identity.bonds == []
        assert identity.bonded_to is None

    def test_identity_with_bonds(self):
        identity = Identity(
            name="TestSoul",
            bonds=[
                BondTarget(id="did:key:alice", label="Alice"),
                BondTarget(id="did:key:bob", label="Bob"),
            ],
        )
        assert len(identity.bonds) == 2
        assert identity.bonds[0].label == "Alice"

    def test_bonded_to_auto_migration(self):
        """When bonded_to is set and bonds is empty, bonds auto-populates."""
        identity = Identity(name="TestSoul", bonded_to="did:key:user-123")
        assert len(identity.bonds) == 1
        assert identity.bonds[0].id == "did:key:user-123"
        assert identity.bonds[0].bond_type == "human"

    def test_bonded_to_no_migration_when_bonds_set(self):
        """When bonds is already provided, bonded_to doesn't trigger migration."""
        identity = Identity(
            name="TestSoul",
            bonded_to="did:key:user-123",
            bonds=[BondTarget(id="did:key:other", bond_type="soul")],
        )
        assert len(identity.bonds) == 1
        assert identity.bonds[0].id == "did:key:other"

    def test_identity_serialization_with_bonds(self):
        identity = Identity(
            name="TestSoul",
            bonds=[
                BondTarget(id="did:key:alice", label="Alice", bond_type="human"),
                BondTarget(id="did:soul:companion", label="Buddy", bond_type="soul"),
            ],
        )
        data = identity.model_dump()
        restored = Identity.model_validate(data)
        assert len(restored.bonds) == 2
        assert restored.bonds[1].bond_type == "soul"

    def test_identity_json_round_trip(self):
        identity = Identity(
            name="TestSoul",
            bonded_to="did:key:user-123",
            bonds=[BondTarget(id="did:key:user-123", label="Owner")],
        )
        json_str = identity.model_dump_json()
        restored = Identity.model_validate_json(json_str)
        assert restored.bonded_to == "did:key:user-123"
        assert len(restored.bonds) == 1

    def test_multiple_bond_types(self):
        identity = Identity(
            name="MultiBond",
            bonds=[
                BondTarget(id="user-1", label="Alice", bond_type="human"),
                BondTarget(id="soul-2", label="Companion", bond_type="soul"),
                BondTarget(id="agent-3", label="Worker", bond_type="agent"),
                BondTarget(id="group-4", label="Team", bond_type="group"),
                BondTarget(id="svc-5", label="API", bond_type="service"),
            ],
        )
        assert len(identity.bonds) == 5
        types = [b.bond_type for b in identity.bonds]
        assert "human" in types
        assert "soul" in types
        assert "agent" in types
        assert "group" in types
        assert "service" in types


# ============ Spec-level Models ============


class TestCoreParticipant:
    """Tests for spec-level Participant (CoreParticipant)."""

    def test_create(self):
        p = CoreParticipant(role="user", content="hello")
        assert p.role == "user"
        assert p.content == "hello"


class TestCoreInteraction:
    """Tests for spec-level Interaction (CoreInteraction)."""

    def test_from_pair(self):
        i = CoreInteraction.from_pair("hello", "hi")
        assert i.user_input == "hello"
        assert i.agent_output == "hi"

    def test_multi_participant(self):
        i = CoreInteraction(
            participants=[
                CoreParticipant(role="user", content="q"),
                CoreParticipant(role="agent", content="a"),
                CoreParticipant(role="observer", content="noted"),
            ]
        )
        assert len(i.participants) == 3
        assert i.user_input == "q"

    def test_backward_compat_properties(self):
        i = CoreInteraction(
            participants=[
                CoreParticipant(role="user", content="input"),
                CoreParticipant(role="agent", content="output"),
            ]
        )
        assert i.user_input == "input"
        assert i.agent_output == "output"


class TestCoreBondTarget:
    """Tests for spec-level BondTarget (CoreBondTarget)."""

    def test_create(self):
        bt = CoreBondTarget(id="test-id", bond_type="soul")
        assert bt.id == "test-id"
        assert bt.bond_type == "soul"


class TestCoreIdentityMultiBond:
    """Tests for spec-level Identity with bonds."""

    def test_bonds_field(self):
        i = CoreIdentity(
            name="Test",
            bonds=[CoreBondTarget(id="x", bond_type="human")],
        )
        assert len(i.bonds) == 1

    def test_bonded_to_deprecated(self):
        i = CoreIdentity(name="Test", bonded_to="old-id")
        assert i.bonded_to == "old-id"


# ============ Integration with Soul lifecycle ============


class TestSoulIntegration:
    """Integration tests verifying Interaction works through the Soul pipeline."""

    @pytest.mark.asyncio
    async def test_observe_legacy_interaction(self):
        """Legacy Interaction constructor still works through observe()."""
        from soul_protocol import Soul

        soul = await Soul.birth(name="TestSoul", values=["test"])
        interaction = Interaction(
            user_input="My name is Alice", agent_output="Nice to meet you, Alice!"
        )
        await soul.observe(interaction)
        assert soul.memory_count > 0

    @pytest.mark.asyncio
    async def test_observe_from_pair(self):
        """Interaction.from_pair() works through observe()."""
        from soul_protocol import Soul

        soul = await Soul.birth(name="TestSoul", values=["test"])
        interaction = Interaction.from_pair("My name is Bob", "Hello Bob!")
        await soul.observe(interaction)
        assert soul.memory_count > 0

    @pytest.mark.asyncio
    async def test_observe_multi_participant(self):
        """Multi-participant Interaction works through observe()."""
        from soul_protocol import Soul

        soul = await Soul.birth(name="TestSoul", values=["test"])
        interaction = Interaction(
            participants=[
                Participant(role="system", content="Group chat context"),
                Participant(role="user", content="My name is Charlie"),
                Participant(role="agent", content="Welcome Charlie!"),
            ]
        )
        await soul.observe(interaction)
        assert soul.memory_count > 0

    @pytest.mark.asyncio
    async def test_soul_birth_with_bonds(self):
        """Soul.birth() with bonded_to auto-migrates to bonds."""
        from soul_protocol import Soul

        soul = await Soul.birth(name="TestSoul", bonded_to="did:key:user-001")
        assert soul.identity.bonded_to == "did:key:user-001"
        assert len(soul.identity.bonds) == 1
        assert soul.identity.bonds[0].id == "did:key:user-001"

    @pytest.mark.asyncio
    async def test_soul_serialization_preserves_bonds(self):
        """Serialization round-trip preserves bonds."""
        from soul_protocol import Soul

        soul = await Soul.birth(name="TestSoul", bonded_to="did:key:user-001")
        config = soul.serialize()
        assert len(config.identity.bonds) == 1

    @pytest.mark.asyncio
    async def test_evaluate_with_legacy_interaction(self):
        """Evaluator works with legacy Interaction constructor."""
        from soul_protocol import Soul

        soul = await Soul.birth(name="TestSoul", values=["helpfulness"])
        interaction = Interaction(
            user_input="How do I sort a list in Python?",
            agent_output="You can use sorted() or list.sort() to sort a list in Python.",
        )
        result = await soul.evaluate(interaction)
        assert result.overall_score >= 0.0
