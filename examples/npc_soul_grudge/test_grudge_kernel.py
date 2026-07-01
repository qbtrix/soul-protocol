# test_grudge_kernel.py — Proof that the npc.soul grudge kernel holds a grudge
#   across a real .soul export -> awaken round-trip.
#
# Created: 2026-07-01 (experiment/npc-soul-grudge-kernel) — pytest-asyncio tests
#   asserting the whole loop against the REAL Soul (no mocks, no LLM, no
#   network):
#     * test_bond_weakens_and_grudge_builds — after 2+ wrongs the per-player
#       bond strictly decreased, grievances are stored, level == "GRUDGING",
#       and react() returns the hostile branch citing a remembered wrong.
#     * test_grudge_survives_soul_roundtrip (THE KILLER TEST) — export the soul
#       to a .soul file, awaken a FRESH kernel from that file, and the grudge +
#       grievances + weakened bond all persist.
#     * test_grudge_is_player_specific — a different player with no wrongs gets
#       level "NONE" and a warm reaction, proving the grudge isn't global.
#     * test_neutral_only_never_grudges — neutral interactions alone never
#       produce a grudge and never weaken the bond below its start.
#
# Updated: 2026-07-01 (experiment/npc-soul-grudge-kernel) — added
#   test_llm_dialogue_seam_feeds_grievances_to_model, a DETERMINISTIC spy test
#   (no live LLM, no subprocess, no network): a SpyGenerate records the prompt
#   the LLMDialogueEngine builds and returns a canned line. It proves the seam
#   feeds the REAL grudge context (grievance content + grudge level) to whatever
#   backs `generate` — using the real LLMDialogueEngine, not a mock of it.
#
# Run:  uv run pytest examples/npc_soul_grudge/test_grudge_kernel.py -v

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the sibling grudge.py importable whether pytest is run from the repo
# root or from inside the folder.
sys.path.insert(0, str(Path(__file__).parent))

from dialogue import LLMDialogueEngine  # noqa: E402
from grudge import GRUDGING, NONE, SLIGHTED, GrudgeKernel  # noqa: E402

pytestmark = pytest.mark.asyncio

RAGNAR = "did:soul:player:ragnar"
ASTRID = "did:soul:player:astrid"

# Starting bond strength for a brand-new per-player bond (Soul default).
START_BOND = 50.0


async def _wronged_kernel() -> GrudgeKernel:
    """Bjorn after Ragnar greets, trades, betrays, and steals."""
    kernel = await GrudgeKernel.birth()
    await kernel.record(RAGNAR, "Good morning, butcher!", kind="neutral")
    await kernel.record(RAGNAR, "Two shanks please.", kind="neutral")
    await kernel.record(RAGNAR, "I framed you to the guards.", kind="betrayal")
    await kernel.record(RAGNAR, "*steals sausages*", kind="theft")
    return kernel


async def test_bond_weakens_and_grudge_builds() -> None:
    kernel = await _wronged_kernel()

    # Bond strictly decreased from the starting point.
    bond = kernel.bond_strength(RAGNAR)
    assert bond < START_BOND, f"expected bond < {START_BOND}, got {bond}"

    # Grievances were stored (betrayal + theft = 2).
    grievances = await kernel.grievances(RAGNAR)
    assert len(grievances) >= 2
    kinds = {g.kind for g in grievances}
    assert "betrayal" in kinds
    assert "theft" in kinds

    # Level is GRUDGING.
    assert await kernel.grudge_level(RAGNAR) == GRUDGING

    # react() returns the hostile branch and cites a specific remembered wrong.
    reaction = await kernel.react(RAGNAR, player_name="Ragnar")
    assert "gall to show your face" in reaction
    assert ("betrayed" in reaction) or ("stole" in reaction) or ("mocked" in reaction)


async def test_grudge_survives_soul_roundtrip(tmp_path: Path) -> None:
    """THE KILLER TEST: export -> awaken preserves the grudge."""
    kernel = await _wronged_kernel()

    bond_before = kernel.bond_strength(RAGNAR)
    level_before = await kernel.grudge_level(RAGNAR)
    count_before = len(await kernel.grievances(RAGNAR))
    assert level_before == GRUDGING

    # Export to a real .soul file, then drop the in-memory object.
    soul_path = tmp_path / "bjorn.soul"
    await kernel.export(str(soul_path))
    assert soul_path.exists() and soul_path.stat().st_size > 0
    del kernel

    # Awaken a completely fresh kernel from the file.
    reborn = await GrudgeKernel.awaken(str(soul_path))

    # The grudge, the grievances, and the weakened bond all came back.
    assert await reborn.grudge_level(RAGNAR) == GRUDGING
    grievances = await reborn.grievances(RAGNAR)
    assert len(grievances) == count_before >= 2
    assert {g.kind for g in grievances} == {"betrayal", "theft"}

    bond_after = reborn.bond_strength(RAGNAR)
    assert bond_after == pytest.approx(bond_before), (
        f"bond changed across round-trip: {bond_before} -> {bond_after}"
    )
    assert bond_after < START_BOND

    # And he's still hostile, still naming the wrongs, in the new session.
    reaction = await reborn.react(RAGNAR, player_name="Ragnar")
    assert "gall to show your face" in reaction
    assert ("betrayed" in reaction) or ("stole" in reaction)


async def test_grudge_is_player_specific(tmp_path: Path) -> None:
    """A player Bjorn was never wronged by stays warm — before AND after a
    round-trip — proving the grudge is per-player, not global."""
    kernel = await _wronged_kernel()
    # Astrid only ever greets him.
    await kernel.record(ASTRID, "Hello, first time here!", kind="neutral")

    assert await kernel.grudge_level(ASTRID) == NONE
    assert len(await kernel.grievances(ASTRID)) == 0

    warm = await kernel.react(ASTRID, player_name="Astrid")
    assert "Welcome to my stall" in warm
    assert "gall to show your face" not in warm

    # Ragnar is GRUDGING at the same time — two players, two relationships.
    assert await kernel.grudge_level(RAGNAR) == GRUDGING

    # Survives the round-trip too.
    soul_path = tmp_path / "bjorn.soul"
    await kernel.export(str(soul_path))
    reborn = await GrudgeKernel.awaken(str(soul_path))
    assert await reborn.grudge_level(ASTRID) == NONE
    assert await reborn.grudge_level(RAGNAR) == GRUDGING


async def test_neutral_only_never_grudges() -> None:
    """Neutral interactions never plant a grudge and never weaken the bond."""
    kernel = await GrudgeKernel.birth()
    await kernel.record(ASTRID, "Morning!", kind="neutral")
    await kernel.record(ASTRID, "Nice weather.", kind="neutral")
    await kernel.record(ASTRID, "A pound of beef, please.", kind="neutral")

    assert await kernel.grudge_level(ASTRID) == NONE
    assert len(await kernel.grievances(ASTRID)) == 0
    # Neutral observes strengthen (never weaken) the bond.
    assert kernel.bond_strength(ASTRID) >= START_BOND


async def test_single_insult_is_only_slighted() -> None:
    """One low-severity wrong yields SLIGHTED, not full GRUDGING — the levels
    are graded, not binary."""
    kernel = await GrudgeKernel.birth()
    await kernel.record(RAGNAR, "Your apron is filthy, old man.", kind="insult")

    assert await kernel.grudge_level(RAGNAR) == SLIGHTED
    reaction = await kernel.react(RAGNAR, player_name="Ragnar")
    assert "smile thins" in reaction


class SpyGenerate:
    """A record-don't-mock `generate` for the LLM seam.

    It IS a real backend from the engine's point of view — an async
    ``(prompt) -> str`` — but instead of calling a model it captures the exact
    prompt string it was handed and returns a fixed line. That lets the test
    assert what context the LLM WOULD receive, using the real
    LLMDialogueEngine (the seam under test is exercised, not stubbed away).
    """

    def __init__(self, canned: str = "Bah. Get out of my shop.") -> None:
        self.canned = canned
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.canned


async def test_llm_dialogue_seam_feeds_grievances_to_model() -> None:
    """The LLM seam feeds the REAL grudge context to the model.

    Wire a GrudgeKernel with the real LLMDialogueEngine over a SpyGenerate,
    build a GRUDGING scenario, and assert (a) the NPC speaks the model's line
    (proving the seam is live, not the template) and (b) the prompt the model
    was handed carries the grievance content AND the grudge level — i.e. the
    seam actually hands the model the state it needs to stay in character.
    No live LLM, no subprocess, no network.
    """
    spy = SpyGenerate(canned="You again. I have not forgotten what you did.")
    kernel = await GrudgeKernel.birth(dialogue_engine=LLMDialogueEngine(spy))

    # Same arc as the other tests: greet, trade, betray, steal -> GRUDGING.
    await kernel.record(RAGNAR, "Good morning, butcher!", kind="neutral")
    await kernel.record(RAGNAR, "Two shanks please.", kind="neutral")
    await kernel.record(RAGNAR, "I framed you to the guards.", kind="betrayal")
    await kernel.record(RAGNAR, "*steals sausages*", kind="theft")
    assert await kernel.grudge_level(RAGNAR) == GRUDGING

    player_line = "Bjorn, old friend! Business as usual?"
    reaction = await kernel.react(RAGNAR, player_name="Ragnar", player_line=player_line)

    # (a) The spoken line is the MODEL's output, not the templated string —
    #     proving react() genuinely delegates to the LLM engine.
    assert reaction == "You again. I have not forgotten what you did."
    assert "cleaver thuds" not in reaction  # not the templated GRUDGING branch

    # (b) Exactly one prompt was built, and it carries the real context.
    assert len(spy.prompts) == 1
    prompt = spy.prompts[0]

    # The grudge LEVEL reached the model.
    assert GRUDGING in prompt or "hostile" in prompt.lower()

    # The GRIEVANCE content reached the model — both specific wrongs, phrased.
    assert "how you betrayed me" in prompt
    assert "what you stole from my stall" in prompt

    # What the player just said reached the model too (so it can answer it).
    assert player_line in prompt

    # And the persona anchors the character.
    assert "Bjorn" in prompt


async def test_llm_engine_falls_back_to_template_on_failure() -> None:
    """If `generate` raises or returns empty, the LLM engine falls back to the
    deterministic template instead of crashing — the demo/game stays alive."""

    async def boom(prompt: str) -> str:
        raise RuntimeError("model unavailable")

    async def empty(prompt: str) -> str:
        return "   "

    for bad in (boom, empty):
        kernel = await GrudgeKernel.birth(dialogue_engine=LLMDialogueEngine(bad))
        await kernel.record(RAGNAR, "I framed you to the guards.", kind="betrayal")
        await kernel.record(RAGNAR, "*steals sausages*", kind="theft")
        assert await kernel.grudge_level(RAGNAR) == GRUDGING

        reaction = await kernel.react(RAGNAR, player_name="Ragnar")
        # Fell back to the templated GRUDGING branch, citing a remembered wrong.
        assert "gall to show your face" in reaction
        assert ("betrayed" in reaction) or ("stole" in reaction)
