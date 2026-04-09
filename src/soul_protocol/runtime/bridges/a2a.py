# runtime/bridges/a2a.py — Bridge between A2A Agent Cards and Soul Protocol.
# Created: 2026-03-23 — Converts Soul ↔ A2A Agent Card JSON. Maps soul identity,
#   OCEAN personality, and skills to/from the Agent Card format. Supports enriching
#   existing Agent Cards with a SoulExtension block without clobbering other extensions.
#   Uses deep copy in enrich_agent_card to avoid mutating the input dict.

from __future__ import annotations

import copy
from typing import Any

from soul_protocol.runtime.skills import Skill
from soul_protocol.runtime.types import (
    DNA,
    CoreMemory,
    Identity,
    Personality,
    SoulConfig,
)
from soul_protocol.spec.a2a import A2AAgentCard, A2ASkill, SoulExtension


class A2AAgentCardBridge:
    """Bidirectional bridge between Soul Protocol and A2A Agent Cards.

    All methods are static — no instance state needed.
    """

    @staticmethod
    def soul_to_agent_card(soul: Any, url: str = "") -> dict:
        """Convert a Soul instance to an A2A Agent Card dict.

        Args:
            soul: A Soul instance (runtime.soul.Soul) with identity, dna, skills.
            url: The agent's endpoint URL for the card.

        Returns:
            dict: A2A Agent Card JSON-serializable dictionary.
        """
        personality = soul.dna.personality
        ocean_dict = {
            "openness": personality.openness,
            "conscientiousness": personality.conscientiousness,
            "extraversion": personality.extraversion,
            "agreeableness": personality.agreeableness,
            "neuroticism": personality.neuroticism,
        }

        # Map soul skills to A2A skills
        a2a_skills: list[dict] = []
        for sk in soul.skills.skills:
            a2a_skills.append(
                A2ASkill(
                    id=sk.id,
                    name=sk.name,
                    description=f"Level {sk.level} skill ({sk.xp} XP)",
                    tags=[],
                ).model_dump()
            )

        soul_ext = SoulExtension(
            did=soul.did,
            personality=ocean_dict,
            soul_version=getattr(soul, "_config", None) and soul._config.version or "1.0.0",
            protocol="dsp/1.0",
        )

        card = A2AAgentCard(
            name=soul.name,
            description=soul.identity.archetype or f"Soul: {soul.name}",
            url=url,
            version=soul._config.version if hasattr(soul, "_config") else "1.0.0",
            provider={"organization": "Soul Protocol"},
            capabilities={"streaming": False, "pushNotifications": False},
            skills=[A2ASkill(**s) for s in a2a_skills],
            extensions={"soul": soul_ext.model_dump()},
        )

        return card.model_dump()

    @staticmethod
    def agent_card_to_soul(card: dict | A2AAgentCard) -> Any:
        """Create a Soul from an A2A Agent Card.

        Performs a synchronous construction (no async birth) by building
        a SoulConfig directly and instantiating the Soul.

        Args:
            card: A2A Agent Card as dict or A2AAgentCard model.

        Returns:
            A Soul instance with identity, personality, and skills from the card.
        """
        from soul_protocol.runtime.identity.did import generate_did
        from soul_protocol.runtime.soul import Soul

        if isinstance(card, dict):
            card = A2AAgentCard(**card)

        # Extract personality from extensions.soul if present
        personality_kwargs: dict[str, float] = {}
        soul_ext_data = card.extensions.get("soul", {})
        if isinstance(soul_ext_data, dict):
            personality_data = soul_ext_data.get("personality", {})
            for trait in (
                "openness",
                "conscientiousness",
                "extraversion",
                "agreeableness",
                "neuroticism",
            ):
                if trait in personality_data:
                    personality_kwargs[trait] = float(personality_data[trait])

        personality = Personality(**personality_kwargs)

        # Build identity
        did = ""
        if isinstance(soul_ext_data, dict):
            did = soul_ext_data.get("did", "")
        if not did:
            did = generate_did(card.name)

        identity = Identity(
            did=did,
            name=card.name,
            archetype=card.description,
        )

        # Build core memory from card description
        core_memory = CoreMemory(
            persona=f"I am {card.name}. {card.description}",
        )

        config = SoulConfig(
            version=card.version or "1.0.0",
            identity=identity,
            dna=DNA(personality=personality),
            core_memory=core_memory,
        )

        soul = Soul(config)

        # Map A2A skills to soul skills
        for a2a_skill in card.skills:
            sk = Skill(id=a2a_skill.id, name=a2a_skill.name)
            soul.skills.add(sk)

        return soul

    @staticmethod
    def enrich_agent_card(card: dict, soul: Any) -> dict:
        """Add Soul Protocol extensions to an existing Agent Card.

        Preserves all existing extensions — only adds/updates ``extensions.soul``.

        Args:
            card: Existing Agent Card dict (may already have extensions).
            soul: A Soul instance to extract soul metadata from.

        Returns:
            dict: The enriched Agent Card with ``extensions.soul`` block.
        """
        personality = soul.dna.personality
        ocean_dict = {
            "openness": personality.openness,
            "conscientiousness": personality.conscientiousness,
            "extraversion": personality.extraversion,
            "agreeableness": personality.agreeableness,
            "neuroticism": personality.neuroticism,
        }

        soul_ext = SoulExtension(
            did=soul.did,
            personality=ocean_dict,
            soul_version=getattr(soul, "_config", None) and soul._config.version or "1.0.0",
            protocol="dsp/1.0",
        )

        enriched = copy.deepcopy(card)
        if "extensions" not in enriched or not isinstance(enriched["extensions"], dict):
            enriched["extensions"] = {}
        enriched["extensions"]["soul"] = soul_ext.model_dump()

        return enriched
