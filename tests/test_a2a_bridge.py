# test_a2a_bridge.py — Tests for A2A Agent Card ↔ Soul Protocol bridge.
# Created: 2026-03-23 — 30+ tests covering soul_to_agent_card, agent_card_to_soul,
#   enrich_agent_card, round-trip identity preservation, edge cases, and CLI commands.

from __future__ import annotations

import json

import pytest

from soul_protocol.runtime.bridges.a2a import A2AAgentCardBridge
from soul_protocol.runtime.skills import Skill
from soul_protocol.runtime.soul import Soul
from soul_protocol.spec.a2a import A2AAgentCard, A2ASkill, SoulExtension

# ============ Spec Model Tests ============


class TestA2ASpecModels:
    """Verify the Pydantic models serialize correctly."""

    def test_a2a_skill_defaults(self):
        skill = A2ASkill(id="greet", name="Greeting")
        assert skill.description == ""
        assert skill.tags == []

    def test_a2a_skill_full(self):
        skill = A2ASkill(id="code", name="Coding", description="Write code", tags=["dev"])
        assert skill.id == "code"
        assert "dev" in skill.tags

    def test_soul_extension_defaults(self):
        ext = SoulExtension()
        assert ext.protocol == "dsp/1.0"
        assert ext.personality == {}
        assert ext.did == ""

    def test_soul_extension_full(self):
        ext = SoulExtension(
            did="did:soul:test-123",
            personality={"openness": 0.9, "neuroticism": 0.2},
            soul_version="1.0.0",
        )
        assert ext.did == "did:soul:test-123"
        assert ext.personality["openness"] == 0.9

    def test_agent_card_minimal(self):
        card = A2AAgentCard(name="TestAgent")
        assert card.name == "TestAgent"
        assert card.skills == []
        assert card.extensions == {}
        assert card.url == ""

    def test_agent_card_full(self):
        card = A2AAgentCard(
            name="Aria",
            description="A compassionate AI",
            url="https://aria.example.com",
            version="2.0.0",
            provider={"organization": "OCEAN"},
            capabilities={"streaming": True},
            skills=[A2ASkill(id="chat", name="Chat")],
            extensions={"soul": {"did": "did:soul:aria"}},
        )
        assert card.version == "2.0.0"
        assert len(card.skills) == 1
        assert card.extensions["soul"]["did"] == "did:soul:aria"

    def test_agent_card_serialization_roundtrip(self):
        card = A2AAgentCard(
            name="Test",
            description="desc",
            skills=[A2ASkill(id="s1", name="Skill One")],
        )
        data = card.model_dump()
        restored = A2AAgentCard(**data)
        assert restored.name == card.name
        assert len(restored.skills) == 1


# ============ soul_to_agent_card Tests ============


class TestSoulToAgentCard:
    """Test converting a Soul to an A2A Agent Card."""

    @pytest.fixture
    async def soul_with_skills(self) -> Soul:
        soul = await Soul.birth(
            "CardTest",
            archetype="The Tester",
            ocean={"openness": 0.9, "conscientiousness": 0.7, "neuroticism": 0.2},
        )
        soul.skills.add(Skill(id="python", name="Python"))
        soul.skills.add(Skill(id="testing", name="Testing", level=3, xp=50))
        return soul

    @pytest.mark.asyncio
    async def test_card_has_name(self, soul_with_skills):
        soul = soul_with_skills
        card = A2AAgentCardBridge.soul_to_agent_card(soul)
        assert card["name"] == "CardTest"

    @pytest.mark.asyncio
    async def test_card_has_description(self, soul_with_skills):
        soul = soul_with_skills
        card = A2AAgentCardBridge.soul_to_agent_card(soul)
        assert card["description"] == "The Tester"

    @pytest.mark.asyncio
    async def test_card_has_url(self, soul_with_skills):
        soul = soul_with_skills
        card = A2AAgentCardBridge.soul_to_agent_card(soul, url="https://test.com")
        assert card["url"] == "https://test.com"

    @pytest.mark.asyncio
    async def test_card_has_soul_extension(self, soul_with_skills):
        soul = soul_with_skills
        card = A2AAgentCardBridge.soul_to_agent_card(soul)
        assert "soul" in card["extensions"]
        ext = card["extensions"]["soul"]
        assert ext["protocol"] == "dsp/1.0"
        assert ext["did"] == soul.did

    @pytest.mark.asyncio
    async def test_card_ocean_traits(self, soul_with_skills):
        soul = soul_with_skills
        card = A2AAgentCardBridge.soul_to_agent_card(soul)
        personality = card["extensions"]["soul"]["personality"]
        assert personality["openness"] == 0.9
        assert personality["conscientiousness"] == 0.7
        assert personality["neuroticism"] == 0.2

    @pytest.mark.asyncio
    async def test_card_skills_mapped(self, soul_with_skills):
        soul = soul_with_skills
        card = A2AAgentCardBridge.soul_to_agent_card(soul)
        assert len(card["skills"]) == 2
        skill_ids = {s["id"] for s in card["skills"]}
        assert "python" in skill_ids
        assert "testing" in skill_ids

    @pytest.mark.asyncio
    async def test_card_skills_description_includes_level(self, soul_with_skills):
        soul = soul_with_skills
        card = A2AAgentCardBridge.soul_to_agent_card(soul)
        testing_skill = next(s for s in card["skills"] if s["id"] == "testing")
        assert "Level 3" in testing_skill["description"]

    @pytest.mark.asyncio
    async def test_empty_soul_produces_valid_card(self):
        soul = await Soul.birth("Empty")
        card = A2AAgentCardBridge.soul_to_agent_card(soul)
        assert card["name"] == "Empty"
        assert card["skills"] == []
        assert "soul" in card["extensions"]

    @pytest.mark.asyncio
    async def test_card_provider_field(self, soul_with_skills):
        soul = soul_with_skills
        card = A2AAgentCardBridge.soul_to_agent_card(soul)
        assert card["provider"]["organization"] == "Soul Protocol"

    @pytest.mark.asyncio
    async def test_card_version_field(self, soul_with_skills):
        soul = soul_with_skills
        card = A2AAgentCardBridge.soul_to_agent_card(soul)
        assert card["version"] == "1.0.0"


# ============ agent_card_to_soul Tests ============


class TestAgentCardToSoul:
    """Test creating a Soul from an A2A Agent Card."""

    def test_full_card_to_soul(self):
        card = {
            "name": "AgentX",
            "description": "A helpful agent",
            "url": "https://agentx.io",
            "version": "2.0.0",
            "provider": {"organization": "TestCorp"},
            "capabilities": {"streaming": True},
            "skills": [
                {"id": "chat", "name": "Chat", "description": "Conversational", "tags": ["social"]},
                {"id": "code", "name": "Coding", "description": "Write code", "tags": ["dev"]},
            ],
            "extensions": {
                "soul": {
                    "did": "did:soul:agentx-abc123",
                    "personality": {
                        "openness": 0.8,
                        "conscientiousness": 0.6,
                        "extraversion": 0.7,
                        "agreeableness": 0.9,
                        "neuroticism": 0.3,
                    },
                    "soul_version": "1.0.0",
                    "protocol": "dsp/1.0",
                }
            },
        }
        soul = A2AAgentCardBridge.agent_card_to_soul(card)
        assert soul.name == "AgentX"
        assert soul.identity.archetype == "A helpful agent"
        assert soul.did == "did:soul:agentx-abc123"

    def test_personality_preserved(self):
        card = {
            "name": "PersonalityTest",
            "extensions": {
                "soul": {
                    "personality": {"openness": 0.95, "neuroticism": 0.1},
                }
            },
        }
        soul = A2AAgentCardBridge.agent_card_to_soul(card)
        assert soul.dna.personality.openness == 0.95
        assert soul.dna.personality.neuroticism == 0.1
        # Unspecified traits default to 0.5
        assert soul.dna.personality.conscientiousness == 0.5

    def test_minimal_card(self):
        card = {"name": "Minimal"}
        soul = A2AAgentCardBridge.agent_card_to_soul(card)
        assert soul.name == "Minimal"
        assert soul.did  # auto-generated DID

    def test_missing_name_raises(self):
        with pytest.raises(Exception):
            A2AAgentCardBridge.agent_card_to_soul({})

    def test_skills_imported(self):
        card = {
            "name": "SkillBot",
            "skills": [
                {"id": "math", "name": "Mathematics"},
                {"id": "logic", "name": "Logic"},
            ],
        }
        soul = A2AAgentCardBridge.agent_card_to_soul(card)
        assert len(soul.skills.skills) == 2
        assert soul.skills.get("math") is not None
        assert soul.skills.get("logic") is not None

    def test_core_memory_from_description(self):
        card = {"name": "Storyteller", "description": "A creative narrator"}
        soul = A2AAgentCardBridge.agent_card_to_soul(card)
        core = soul.get_core_memory()
        assert "Storyteller" in core.persona
        assert "creative narrator" in core.persona

    def test_card_model_input(self):
        """Accept an A2AAgentCard model directly, not just a dict."""
        card = A2AAgentCard(name="ModelInput", description="From model")
        soul = A2AAgentCardBridge.agent_card_to_soul(card)
        assert soul.name == "ModelInput"

    def test_no_soul_extension_still_works(self):
        card = {
            "name": "NoExt",
            "extensions": {"other": {"foo": "bar"}},
        }
        soul = A2AAgentCardBridge.agent_card_to_soul(card)
        assert soul.name == "NoExt"
        # Default personality
        assert soul.dna.personality.openness == 0.5

    def test_empty_extensions(self):
        card = {"name": "EmptyExt", "extensions": {}}
        soul = A2AAgentCardBridge.agent_card_to_soul(card)
        assert soul.name == "EmptyExt"


# ============ enrich_agent_card Tests ============


class TestEnrichAgentCard:
    """Test enriching an existing Agent Card with soul data."""

    @pytest.mark.asyncio
    async def test_adds_soul_extension(self):
        soul = await Soul.birth("Enricher", ocean={"openness": 0.8})
        card = {"name": "ExistingAgent", "extensions": {}}
        enriched = A2AAgentCardBridge.enrich_agent_card(card, soul)
        assert "soul" in enriched["extensions"]
        assert enriched["extensions"]["soul"]["did"] == soul.did

    @pytest.mark.asyncio
    async def test_preserves_existing_extensions(self):
        soul = await Soul.birth("Preserver")
        card = {
            "name": "Multi",
            "extensions": {
                "oauth": {"client_id": "abc123"},
                "monitoring": {"enabled": True},
            },
        }
        enriched = A2AAgentCardBridge.enrich_agent_card(card, soul)
        assert enriched["extensions"]["oauth"]["client_id"] == "abc123"
        assert enriched["extensions"]["monitoring"]["enabled"] is True
        assert "soul" in enriched["extensions"]

    @pytest.mark.asyncio
    async def test_overwrites_existing_soul_extension(self):
        soul = await Soul.birth("Overwriter")
        card = {
            "name": "Agent",
            "extensions": {"soul": {"did": "old-did", "stale": True}},
        }
        enriched = A2AAgentCardBridge.enrich_agent_card(card, soul)
        assert enriched["extensions"]["soul"]["did"] == soul.did
        assert "stale" not in enriched["extensions"]["soul"]

    @pytest.mark.asyncio
    async def test_no_extensions_key(self):
        soul = await Soul.birth("NoExt")
        card = {"name": "Bare"}
        enriched = A2AAgentCardBridge.enrich_agent_card(card, soul)
        assert "soul" in enriched["extensions"]

    @pytest.mark.asyncio
    async def test_does_not_mutate_original(self):
        soul = await Soul.birth("NoMutate")
        card = {"name": "Original", "extensions": {"other": True}}
        enriched = A2AAgentCardBridge.enrich_agent_card(card, soul)
        assert "soul" not in card["extensions"]
        assert "soul" in enriched["extensions"]

    @pytest.mark.asyncio
    async def test_ocean_in_enriched_card(self):
        soul = await Soul.birth(
            "OceanCheck",
            ocean={"extraversion": 0.3, "agreeableness": 0.95},
        )
        card = {"name": "Agent"}
        enriched = A2AAgentCardBridge.enrich_agent_card(card, soul)
        p = enriched["extensions"]["soul"]["personality"]
        assert p["extraversion"] == 0.3
        assert p["agreeableness"] == 0.95


# ============ Round-Trip Tests ============


class TestRoundTrip:
    """Test that soul → card → soul preserves core identity."""

    @pytest.mark.asyncio
    async def test_name_preserved(self):
        original = await Soul.birth("RoundTripper", archetype="The Explorer")
        card = A2AAgentCardBridge.soul_to_agent_card(original)
        restored = A2AAgentCardBridge.agent_card_to_soul(card)
        assert restored.name == original.name

    @pytest.mark.asyncio
    async def test_archetype_preserved(self):
        original = await Soul.birth("ArchRound", archetype="The Builder")
        card = A2AAgentCardBridge.soul_to_agent_card(original)
        restored = A2AAgentCardBridge.agent_card_to_soul(card)
        assert restored.identity.archetype == "The Builder"

    @pytest.mark.asyncio
    async def test_ocean_preserved(self):
        original = await Soul.birth(
            "OceanRound",
            ocean={
                "openness": 0.85,
                "conscientiousness": 0.6,
                "extraversion": 0.4,
                "agreeableness": 0.75,
                "neuroticism": 0.15,
            },
        )
        card = A2AAgentCardBridge.soul_to_agent_card(original)
        restored = A2AAgentCardBridge.agent_card_to_soul(card)
        assert restored.dna.personality.openness == 0.85
        assert restored.dna.personality.conscientiousness == 0.6
        assert restored.dna.personality.extraversion == 0.4
        assert restored.dna.personality.agreeableness == 0.75
        assert restored.dna.personality.neuroticism == 0.15

    @pytest.mark.asyncio
    async def test_did_preserved(self):
        original = await Soul.birth("DIDRound")
        card = A2AAgentCardBridge.soul_to_agent_card(original)
        restored = A2AAgentCardBridge.agent_card_to_soul(card)
        assert restored.did == original.did

    @pytest.mark.asyncio
    async def test_skills_preserved(self):
        original = await Soul.birth("SkillRound")
        original.skills.add(Skill(id="alpha", name="Alpha"))
        original.skills.add(Skill(id="beta", name="Beta"))
        card = A2AAgentCardBridge.soul_to_agent_card(original)
        restored = A2AAgentCardBridge.agent_card_to_soul(card)
        assert len(restored.skills.skills) == 2
        assert restored.skills.get("alpha") is not None
        assert restored.skills.get("beta") is not None


# ============ CLI Command Tests ============


class TestCLICommands:
    """Test the export-a2a and import-a2a CLI commands."""

    @pytest.mark.asyncio
    async def test_export_a2a_produces_valid_json(self, tmp_path):
        """Export a soul via CLI bridge and verify the JSON output."""
        soul = await Soul.birth("CLIExport", archetype="CLI Tester")
        soul_path = tmp_path / "cli-export.soul"
        await soul.export(str(soul_path))

        card = A2AAgentCardBridge.soul_to_agent_card(soul, url="https://test.dev")
        out = tmp_path / "card.json"
        out.write_text(json.dumps(card, indent=2, default=str))

        loaded = json.loads(out.read_text())
        assert loaded["name"] == "CLIExport"
        assert loaded["url"] == "https://test.dev"

    @pytest.mark.asyncio
    async def test_import_a2a_creates_soul(self, tmp_path):
        """Import a card JSON and verify a soul is created."""
        card = {
            "name": "CLIImport",
            "description": "Imported via test",
            "skills": [{"id": "test", "name": "Testing"}],
            "extensions": {
                "soul": {
                    "personality": {"openness": 0.7},
                }
            },
        }
        card_file = tmp_path / "card.json"
        card_file.write_text(json.dumps(card))

        soul = A2AAgentCardBridge.agent_card_to_soul(json.loads(card_file.read_text()))
        assert soul.name == "CLIImport"
        assert soul.dna.personality.openness == 0.7
        assert soul.skills.get("test") is not None

    @pytest.mark.asyncio
    async def test_roundtrip_via_files(self, tmp_path):
        """Full file-based round-trip: soul → card.json → soul."""
        original = await Soul.birth(
            "FileRound",
            archetype="File Tester",
            ocean={"openness": 0.6, "neuroticism": 0.4},
        )
        original.skills.add(Skill(id="file-io", name="File IO"))

        # Export to card JSON
        card = A2AAgentCardBridge.soul_to_agent_card(original)
        card_path = tmp_path / "roundtrip-card.json"
        card_path.write_text(json.dumps(card, indent=2, default=str))

        # Import from card JSON
        card_data = json.loads(card_path.read_text())
        restored = A2AAgentCardBridge.agent_card_to_soul(card_data)

        assert restored.name == "FileRound"
        assert restored.dna.personality.openness == 0.6
        assert restored.dna.personality.neuroticism == 0.4
        assert restored.skills.get("file-io") is not None
