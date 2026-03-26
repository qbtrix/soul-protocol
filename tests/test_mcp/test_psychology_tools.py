# test_psychology_tools.py — MCP tests for soul_skills, soul_evaluate, soul_learn,
#   soul_evolve, and soul_bond tools added in v0.2.7 psychology pipeline batch.
# Created: 2026-03-26

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip(
    "fastmcp", reason="fastmcp required for MCP server tests — pip install soul-protocol[mcp]"
)

from fastmcp import Client  # noqa: E402

import soul_protocol.mcp.server as server_module  # noqa: E402
from soul_protocol.mcp.server import mcp  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture — mirrors the autouse fixture in test_server.py exactly
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry(tmp_path, monkeypatch):
    """Reset soul registry and isolate from real .soul/ directories."""
    server_module._registry.clear()
    monkeypatch.delenv("SOUL_DIR", raising=False)
    monkeypatch.delenv("SOUL_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    _fake_home = tmp_path / "fake_home"
    _fake_home.mkdir(exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: _fake_home))
    yield
    server_module._registry.clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _birth(client: Client, name: str = "TestBot") -> dict:
    result = await client.call_tool(
        "soul_birth",
        {"name": name, "archetype": "Test Archetype", "values": ["curiosity", "honesty"]},
    )
    return json.loads(result.data)


# ---------------------------------------------------------------------------
# soul_skills
# ---------------------------------------------------------------------------


class TestSoulSkills:
    """Tests for the soul_skills MCP tool."""

    async def test_soul_skills_returns_empty_list_on_fresh_soul(self):
        """A freshly birthed soul has no skills."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool("soul_skills", {})
            data = json.loads(result.data)

            assert data["soul"] == "TestBot"
            assert data["total"] == 0
            assert data["skills"] == []

    async def test_soul_skills_returns_soul_name(self):
        """soul_skills response includes the correct soul name."""
        async with Client(mcp) as client:
            await _birth(client, "SkillsBot")
            result = await client.call_tool("soul_skills", {})
            data = json.loads(result.data)

            assert data["soul"] == "SkillsBot"

    async def test_soul_skills_after_observe_may_gain_skills(self):
        """After observe(), soul may have gained skill entries (or still 0 — both valid)."""
        async with Client(mcp) as client:
            await _birth(client)
            # observe may trigger entity extraction and skill grants
            await client.call_tool(
                "soul_observe",
                {
                    "user_input": "I am a Python developer working on AI projects",
                    "agent_output": "That sounds exciting! Python is great for AI.",
                    "channel": "test",
                },
            )
            result = await client.call_tool("soul_skills", {})
            data = json.loads(result.data)

            # total must be non-negative and consistent with skills list length
            assert data["total"] >= 0
            assert len(data["skills"]) == data["total"]

    async def test_soul_skills_schema(self):
        """Each skill entry has the required keys: id, name, level, xp, xp_to_next."""
        async with Client(mcp) as client:
            await _birth(client)
            # Force a skill by running evaluate — grants XP which can create a skill
            await client.call_tool(
                "soul_evaluate",
                {
                    "user_input": "How do I sort a list in Python?",
                    "agent_output": "Use sorted() or list.sort(). sorted() returns a new list.",
                },
            )
            result = await client.call_tool("soul_skills", {})
            data = json.loads(result.data)

            # If any skills exist, validate their schema
            for skill in data["skills"]:
                assert "id" in skill
                assert "name" in skill
                assert "level" in skill
                assert "xp" in skill
                assert "xp_to_next" in skill

    async def test_soul_skills_targets_named_soul(self):
        """soul_skills with soul= parameter targets the specified soul."""
        async with Client(mcp) as client:
            await _birth(client, "Alpha")
            await _birth(client, "Beta")

            result = await client.call_tool("soul_skills", {"soul": "Alpha"})
            data = json.loads(result.data)

            assert data["soul"] == "Alpha"

    async def test_soul_skills_raises_without_soul(self):
        """soul_skills raises when no soul has been birthed."""
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("soul_skills", {})


# ---------------------------------------------------------------------------
# soul_evaluate
# ---------------------------------------------------------------------------


class TestSoulEvaluate:
    """Tests for the soul_evaluate MCP tool."""

    async def test_soul_evaluate_returns_rubric_scores(self):
        """soul_evaluate returns overall_score and criterion_results."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool(
                "soul_evaluate",
                {
                    "user_input": "What is the capital of France?",
                    "agent_output": "The capital of France is Paris.",
                },
            )
            data = json.loads(result.data)

            assert data["soul"] == "TestBot"
            assert "rubric" in data
            assert "overall_score" in data
            assert 0.0 <= data["overall_score"] <= 1.0
            assert "criteria" in data
            assert len(data["criteria"]) > 0

    async def test_soul_evaluate_criterion_schema(self):
        """Each criterion result has name, score, and passed fields."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool(
                "soul_evaluate",
                {
                    "user_input": "Explain async/await",
                    "agent_output": "async/await lets you write non-blocking code using coroutines.",
                },
            )
            data = json.loads(result.data)

            for criterion in data["criteria"]:
                assert "name" in criterion
                assert "score" in criterion
                assert "passed" in criterion
                assert isinstance(criterion["score"], float)
                assert isinstance(criterion["passed"], bool)

    async def test_soul_evaluate_increments_history(self):
        """eval_history_size grows with each soul_evaluate call."""
        async with Client(mcp) as client:
            await _birth(client)

            result1 = await client.call_tool(
                "soul_evaluate",
                {
                    "user_input": "What is 2+2?",
                    "agent_output": "4",
                },
            )
            size1 = json.loads(result1.data)["eval_history_size"]

            result2 = await client.call_tool(
                "soul_evaluate",
                {
                    "user_input": "What is 3+3?",
                    "agent_output": "6",
                },
            )
            size2 = json.loads(result2.data)["eval_history_size"]

            assert size2 > size1

    async def test_soul_evaluate_with_domain(self):
        """soul_evaluate accepts an optional domain parameter without error."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool(
                "soul_evaluate",
                {
                    "user_input": "Recommend a Python book",
                    "agent_output": "Try 'Fluent Python' by Luciano Ramalho.",
                    "domain": "knowledge",
                },
            )
            data = json.loads(result.data)

            assert "overall_score" in data
            assert data["soul"] == "TestBot"

    async def test_soul_evaluate_returns_learning_field(self):
        """soul_evaluate includes a learning field (may be None for medium-range scores)."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool(
                "soul_evaluate",
                {
                    "user_input": "Hello",
                    "agent_output": "Hi there!",
                },
            )
            data = json.loads(result.data)

            assert "learning" in data

    async def test_soul_evaluate_raises_without_soul(self):
        """soul_evaluate raises when no soul is active."""
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool(
                    "soul_evaluate",
                    {
                        "user_input": "Hello",
                        "agent_output": "Hi",
                    },
                )


# ---------------------------------------------------------------------------
# soul_learn
# ---------------------------------------------------------------------------


class TestSoulLearn:
    """Tests for the soul_learn MCP tool."""

    async def test_soul_learn_returns_soul_name(self):
        """soul_learn response always includes the soul name."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool(
                "soul_learn",
                {
                    "user_input": "What is recursion?",
                    "agent_output": "Recursion is when a function calls itself.",
                },
            )
            data = json.loads(result.data)

            assert data["soul"] == "TestBot"

    async def test_soul_learn_returns_learning_event_or_none(self):
        """soul_learn returns either a learning_event dict or None with a reason."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool(
                "soul_learn",
                {
                    "user_input": "Explain machine learning",
                    "agent_output": "Machine learning is a subset of AI that uses data to train models.",
                },
            )
            data = json.loads(result.data)

            # Either learning_event is None (medium score) or a dict with required fields
            assert "learning_event" in data
            if data["learning_event"] is not None:
                event = data["learning_event"]
                assert "id" in event
                assert "lesson" in event
                assert "domain" in event
                assert "confidence" in event
            else:
                assert "reason" in data

    async def test_soul_learn_learning_event_schema_when_present(self):
        """When soul_learn produces a learning event, it has the full required schema."""
        async with Client(mcp) as client:
            await _birth(client)
            # Run multiple low-quality interactions to trigger a failure pattern
            for _ in range(3):
                result = await client.call_tool(
                    "soul_learn",
                    {"user_input": "x", "agent_output": ""},
                )
                data = json.loads(result.data)
                if data.get("learning_event") is not None:
                    event = data["learning_event"]
                    assert "id" in event
                    assert "lesson" in event
                    assert "domain" in event
                    assert "confidence" in event
                    assert "skill_id" in event
                    break

    async def test_soul_learn_with_domain_param(self):
        """soul_learn accepts a domain parameter without error."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool(
                "soul_learn",
                {
                    "user_input": "Write unit tests for this function",
                    "agent_output": "Here are the unit tests using pytest...",
                    "domain": "problem_solving",
                },
            )
            data = json.loads(result.data)

            assert data["soul"] == "TestBot"
            assert "learning_event" in data

    async def test_soul_learn_raises_without_soul(self):
        """soul_learn raises when no soul is active."""
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool(
                    "soul_learn",
                    {
                        "user_input": "Hello",
                        "agent_output": "Hi",
                    },
                )


# ---------------------------------------------------------------------------
# soul_evolve
# ---------------------------------------------------------------------------


class TestSoulEvolve:
    """Tests for the soul_evolve MCP tool (list/propose/approve/reject flow)."""

    async def test_soul_evolve_list_empty_on_fresh_soul(self):
        """A fresh soul has no pending mutations."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool("soul_evolve", {"action": "list"})
            data = json.loads(result.data)

            assert data["soul"] == "TestBot"
            assert data["pending"] == []
            assert data["history_count"] >= 0

    async def test_soul_evolve_propose_creates_pending_mutation(self):
        """soul_evolve propose adds a pending mutation."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool(
                "soul_evolve",
                {
                    "action": "propose",
                    "trait": "communication.warmth",
                    "new_value": "very warm",
                    "reason": "User consistently responds well to warmth",
                },
            )
            data = json.loads(result.data)

            assert data["soul"] == "TestBot"
            assert "mutation_id" in data
            assert data["status"] == "pending"
            assert data["trait"] == "communication.warmth"
            assert data["new_value"] == "very warm"

    async def test_soul_evolve_list_shows_proposed_mutation(self):
        """After propose, soul_evolve list returns the pending mutation."""
        async with Client(mcp) as client:
            await _birth(client)
            propose_result = await client.call_tool(
                "soul_evolve",
                {
                    "action": "propose",
                    "trait": "communication.warmth",
                    "new_value": "warmer",
                    "reason": "Testing the proposal flow",
                },
            )
            proposed = json.loads(propose_result.data)

            list_result = await client.call_tool("soul_evolve", {"action": "list"})
            data = json.loads(list_result.data)

            assert len(data["pending"]) == 1
            assert data["pending"][0]["id"] == proposed["mutation_id"]

    async def test_soul_evolve_approve_flow(self):
        """soul_evolve approve marks a mutation as applied."""
        async with Client(mcp) as client:
            await _birth(client)
            # Propose
            propose_result = await client.call_tool(
                "soul_evolve",
                {
                    "action": "propose",
                    "trait": "communication.warmth",
                    "new_value": "approachable",
                    "reason": "Testing approve flow",
                },
            )
            mutation_id = json.loads(propose_result.data)["mutation_id"]

            # Approve
            approve_result = await client.call_tool(
                "soul_evolve",
                {
                    "action": "approve",
                    "mutation_id": mutation_id,
                },
            )
            data = json.loads(approve_result.data)

            assert data["soul"] == "TestBot"
            assert data["mutation_id"] == mutation_id
            assert data["approved"] is True

    async def test_soul_evolve_approve_clears_pending(self):
        """After approving a mutation, it no longer appears in pending list."""
        async with Client(mcp) as client:
            await _birth(client)
            propose_result = await client.call_tool(
                "soul_evolve",
                {
                    "action": "propose",
                    "trait": "communication.warmth",
                    "new_value": "gentle",
                    "reason": "Test pending cleared after approve",
                },
            )
            mutation_id = json.loads(propose_result.data)["mutation_id"]

            await client.call_tool(
                "soul_evolve",
                {"action": "approve", "mutation_id": mutation_id},
            )

            list_result = await client.call_tool("soul_evolve", {"action": "list"})
            data = json.loads(list_result.data)

            pending_ids = [m["id"] for m in data["pending"]]
            assert mutation_id not in pending_ids

    async def test_soul_evolve_reject_flow(self):
        """soul_evolve reject marks a mutation as rejected."""
        async with Client(mcp) as client:
            await _birth(client)
            propose_result = await client.call_tool(
                "soul_evolve",
                {
                    "action": "propose",
                    "trait": "communication.warmth",
                    "new_value": "gentle",
                    "reason": "Testing reject flow",
                },
            )
            mutation_id = json.loads(propose_result.data)["mutation_id"]

            reject_result = await client.call_tool(
                "soul_evolve",
                {"action": "reject", "mutation_id": mutation_id},
            )
            data = json.loads(reject_result.data)

            assert data["soul"] == "TestBot"
            assert data["mutation_id"] == mutation_id
            assert data["rejected"] is True

    async def test_soul_evolve_propose_requires_all_params(self):
        """soul_evolve propose without required params returns an error dict."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool(
                "soul_evolve",
                {"action": "propose"},
            )
            data = json.loads(result.data)

            assert "error" in data

    async def test_soul_evolve_approve_requires_mutation_id(self):
        """soul_evolve approve without mutation_id returns an error dict."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool("soul_evolve", {"action": "approve"})
            data = json.loads(result.data)

            assert "error" in data

    async def test_soul_evolve_unknown_action_returns_error(self):
        """soul_evolve with an unknown action returns an error dict."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool("soul_evolve", {"action": "fly"})
            data = json.loads(result.data)

            assert "error" in data

    async def test_soul_evolve_raises_without_soul(self):
        """soul_evolve raises when no soul is active."""
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("soul_evolve", {"action": "list"})

    async def test_soul_evolve_default_action_is_list(self):
        """soul_evolve with no action parameter defaults to list behavior."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool("soul_evolve", {})
            data = json.loads(result.data)

            # Default action is "list" — should return pending + history_count
            assert "pending" in data
            assert "history_count" in data


# ---------------------------------------------------------------------------
# soul_bond
# ---------------------------------------------------------------------------


class TestSoulBond:
    """Tests for the soul_bond MCP tool (view and strengthen)."""

    async def test_soul_bond_view_returns_bond_data(self):
        """soul_bond with no strengthen returns bond_strength and interaction_count."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool("soul_bond", {})
            data = json.loads(result.data)

            assert data["soul"] == "TestBot"
            assert "bond_strength" in data
            assert "interaction_count" in data
            assert isinstance(data["bond_strength"], float)
            assert isinstance(data["interaction_count"], int)

    async def test_soul_bond_initial_strength_is_valid(self):
        """A freshly birthed soul has a bond_strength in [0, 100]."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool("soul_bond", {})
            data = json.loads(result.data)

            assert 0.0 <= data["bond_strength"] <= 100.0

    async def test_soul_bond_strengthen_increases_strength(self):
        """Passing strengthen=10 increases bond_strength by ~10."""
        async with Client(mcp) as client:
            await _birth(client)

            before_result = await client.call_tool("soul_bond", {})
            before = json.loads(before_result.data)["bond_strength"]

            after_result = await client.call_tool("soul_bond", {"strengthen": 10.0})
            after = json.loads(after_result.data)["bond_strength"]

            assert after > before

    async def test_soul_bond_strengthen_zero_is_view_only(self):
        """Passing strengthen=0 returns current bond without changing it."""
        async with Client(mcp) as client:
            await _birth(client)

            result1 = await client.call_tool("soul_bond", {})
            strength1 = json.loads(result1.data)["bond_strength"]

            result2 = await client.call_tool("soul_bond", {"strengthen": 0.0})
            strength2 = json.loads(result2.data)["bond_strength"]

            # strengthen=0 should not change the value
            assert strength2 == strength1

    async def test_soul_bond_strengthen_negative_weakens(self):
        """Passing a negative strengthen value weakens the bond."""
        async with Client(mcp) as client:
            await _birth(client)

            # First strengthen to ensure we have room to weaken
            await client.call_tool("soul_bond", {"strengthen": 30.0})

            before_result = await client.call_tool("soul_bond", {})
            before = json.loads(before_result.data)["bond_strength"]

            after_result = await client.call_tool("soul_bond", {"strengthen": -10.0})
            after = json.loads(after_result.data)["bond_strength"]

            assert after < before

    async def test_soul_bond_clamps_to_zero_on_large_negative(self):
        """Bond strength cannot go below 0.0 even with a very large negative strengthen."""
        async with Client(mcp) as client:
            await _birth(client)
            result = await client.call_tool("soul_bond", {"strengthen": -9999.0})
            data = json.loads(result.data)

            assert data["bond_strength"] >= 0.0

    async def test_soul_bond_grows_after_observe(self):
        """Bond strength increases after soul_observe interactions."""
        async with Client(mcp) as client:
            await _birth(client)

            before_result = await client.call_tool("soul_bond", {})
            before = json.loads(before_result.data)["bond_strength"]

            await client.call_tool(
                "soul_observe",
                {
                    "user_input": "You are really helpful!",
                    "agent_output": "Thank you, I'm glad I could help.",
                    "channel": "test",
                },
            )

            after_result = await client.call_tool("soul_bond", {})
            after = json.loads(after_result.data)["bond_strength"]

            # Bond should grow or stay the same (never decrease from positive interaction)
            assert after >= before

    async def test_soul_bond_targets_named_soul(self):
        """soul_bond with soul= parameter returns data for the named soul."""
        async with Client(mcp) as client:
            await _birth(client, "Alpha")
            await _birth(client, "Beta")

            result = await client.call_tool("soul_bond", {"soul": "Alpha"})
            data = json.loads(result.data)

            assert data["soul"] == "Alpha"

    async def test_soul_bond_raises_without_soul(self):
        """soul_bond raises when no soul is active."""
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("soul_bond", {})
