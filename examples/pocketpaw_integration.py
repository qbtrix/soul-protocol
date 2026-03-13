# examples/pocketpaw_integration.py — Reference implementation showing how to
# integrate soul-protocol with PocketPaw.
#
# SoulProvider replaces DefaultBootstrapProvider with soul-driven system prompts,
# memory recall, interaction tracking, and auto-save.
#
# Moved from src/soul_protocol/integrations/pocketpaw.py — this is NOT part of the
# core SDK. Consumers should `pip install soul-protocol` and write their own bridge.

from __future__ import annotations

from pathlib import Path

from soul_protocol import Interaction, Soul


class SoulProvider:
    """PocketPaw integration — replaces DefaultBootstrapProvider.

    Bridges the soul-protocol into PocketPaw's agent loop by providing
    system prompts enriched with soul DNA, personality, state, and
    recalled memories. Tracks interactions and auto-saves periodically.

    This module has zero PocketPaw dependencies — it works standalone.

    Usage::

        from examples.pocketpaw_integration import SoulProvider

        soul = await Soul.awaken("~/.pocketpaw/souls/aria.soul")
        provider = SoulProvider(soul)

        # In AgentLoop, use provider for system prompts:
        system_prompt = await provider.get_system_prompt(user_query, sender_id)

        # After each interaction:
        await provider.on_interaction(user_input, agent_output, channel)

        # On graceful shutdown:
        await provider.save()
    """

    def __init__(self, soul: Soul, memory_recall_limit: int = 5) -> None:
        self._soul = soul
        self._recall_limit = memory_recall_limit
        self._interaction_count = 0
        self._auto_save_interval = 10  # Save every N interactions

    @property
    def soul(self) -> Soul:
        """Return the underlying Soul instance."""
        return self._soul

    async def get_system_prompt(
        self,
        user_query: str | None = None,
        sender_id: str | None = None,
    ) -> str:
        """Generate system prompt from soul's DNA + memory + state.

        This replaces PocketPaw's DefaultBootstrapProvider.get_system_prompt().

        The prompt is assembled in layers:
        1. Base prompt from DNA + identity + core memory + state
        2. Relevant recalled memories (if a user query is provided)
        3. State-aware annotations (e.g. low-energy notice)

        Args:
            user_query: Current user message (used to recall relevant memories).
            sender_id: Channel-specific sender ID (for multi-user support).

        Returns:
            Complete system prompt string.
        """
        # 1. Base prompt from DNA + identity + core memory + state
        prompt = self._soul.to_system_prompt()

        # 2. Inject relevant memories if we have a query
        if user_query:
            memories = await self._soul.recall(user_query, limit=self._recall_limit)
            if memories:
                prompt += "\n\n## Relevant Memories\n"
                for mem in memories:
                    prefix = f"[{mem.type.value}]" if mem.type else ""
                    prompt += f"- {prefix} {mem.content}\n"

        # 3. Add state awareness
        state = self._soul.state
        if state.energy < 30:
            prompt += "\n\n*Note: You're feeling low on energy. Keep responses concise.*\n"

        return prompt

    async def on_interaction(
        self,
        user_input: str,
        agent_output: str,
        channel: str = "web",
        metadata: dict | None = None,
    ) -> None:
        """Called after each user-agent exchange.

        The soul observes the interaction, extracts facts, updates state,
        and periodically auto-saves.

        Args:
            user_input: The user's message.
            agent_output: The agent's response.
            channel: Communication channel identifier (e.g. "web", "discord").
            metadata: Optional extra context about the interaction.
        """
        interaction = Interaction(
            user_input=user_input,
            agent_output=agent_output,
            channel=channel,
            metadata=metadata or {},
        )

        await self._soul.observe(interaction)

        self._interaction_count += 1

        # Auto-save periodically
        if self._interaction_count % self._auto_save_interval == 0:
            await self.save()

    async def save(self) -> None:
        """Persist soul state + memories to disk."""
        await self._soul.save()

    async def get_soul_status(self) -> dict:
        """Get a summary of the soul's current state for dashboard display.

        Returns:
            Dictionary with name, did, mood, energy, focus, social_battery,
            lifecycle, interaction_count, and core_memory fields.
        """
        return {
            "name": self._soul.name,
            "did": self._soul.did,
            "mood": self._soul.state.mood.value,
            "energy": self._soul.state.energy,
            "focus": self._soul.state.focus,
            "social_battery": self._soul.state.social_battery,
            "lifecycle": self._soul.lifecycle.value,
            "interaction_count": self._interaction_count,
            "core_memory": {
                "persona": self._soul.get_core_memory().persona,
                "human": self._soul.get_core_memory().human,
            },
        }

    @classmethod
    async def from_file(cls, path: str | Path, **kwargs) -> SoulProvider:
        """Create a SoulProvider from a soul file.

        Args:
            path: Path to a .soul, .json, .yaml, or .md file.
            **kwargs: Extra arguments forwarded to the SoulProvider constructor
                (e.g. memory_recall_limit).

        Returns:
            A ready-to-use SoulProvider instance.
        """
        soul = await Soul.awaken(path)
        return cls(soul, **kwargs)

    @classmethod
    async def from_name(
        cls,
        name: str,
        archetype: str = "The Companion",
        **kwargs,
    ) -> SoulProvider:
        """Create a new soul and provider. Used for first-time setup.

        Args:
            name: The soul's display name.
            archetype: Personality archetype (default "The Companion").
            **kwargs: Extra arguments forwarded to the SoulProvider constructor
                (e.g. memory_recall_limit).

        Returns:
            A SoulProvider wrapping a freshly-birthed Soul.
        """
        soul = await Soul.birth(name=name, archetype=archetype)
        return cls(soul, **kwargs)
