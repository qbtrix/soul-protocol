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
# Updated: 2026-07-01 (experiment/npc-soul-grudge-kernel) — PLAYER.SOUL SYMMETRY.
#   Added the cross-game-reputation tests (all deterministic — no live LLM, no
#   subprocess, no network):
#     * test_deed_recorded_on_player_soul — after a slight with a player_soul
#       passed to record(), the PLAYER's own soul reputation() carries the deed
#       (the both-directions ledger write works).
#     * test_reputation_survives_roundtrip_and_fresh_npc_reacts (THE KILLER) —
#       player wrongs Bjorn -> export player.soul -> awaken fresh -> a FRESH NPC
#       (Astrid, never met the player) react_to_reputation(reawakened) yields
#       wariness above baseline AND reputation() is non-empty. Portable reputation
#       across a round-trip + a never-met NPC.
#     * test_clean_player_stays_warm — a player.soul with no deeds -> Astrid's
#       reaction is the warm/baseline (UNKNOWN) branch, proving it's the
#       reputation driving wariness, not global suspicion.
#     * test_reputation_llm_seam_feeds_deeds_to_model — the SAME record-don't-mock
#       spy, on the reputation path: asserts the model's prompt carries the
#       player's deeds + notoriety framing + the fresh NPC's own name.
#
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel) — COST METER + REPLAY
#   CACHE (costmeter.py). Four new deterministic tests (no network, no
#   subprocess — spy/canned generate fns only):
#     * test_cost_meter_counts_and_prices — 3 metered kernel reactions; calls,
#       len//4 token estimates, and total_cost all match hand-computed PRICING
#       math; cost_per_player_hour() projects a sane positive $.
#     * test_replay_cache_hits_skip_generate — same prompt twice -> generate ran
#       ONCE (hits==1, misses==1); a new prompt -> generate runs again.
#     * test_replay_roundtrip_is_deterministic_and_free (THE KILLER) — session 1
#       records to a jsonl; a FRESH kernel + FRESH cache over the same file,
#       backed by a generate that must never fire, replays the same player lines
#       -> byte-identical spoken lines, zero generate calls, zero metered cost.
#     * test_meter_composes_with_cache — CostMeter(ReplayCache(...)): hits are
#       free (no tokens, $0), only misses are metered; project() re-prices.
#
# Updated: 2026-07-02 (experiment/npc-soul-grudge-kernel) — GRADUATED alongside
#   the modules: moved from examples/npc_soul_grudge/ to tests/profiles/game/
#   (git mv). The sys.path hack is gone — everything now imports from the real
#   package, soul_protocol.profiles.game — and the mid-file costmeter imports
#   were consolidated at the top (the E402 noqas existed only for the hack).
#   All 15 tests are behaviorally unchanged.
#
# Run:  uv run pytest tests/profiles/game/ -v

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from soul_protocol.profiles.game import (
    GRUDGING,
    KNOWN,
    NONE,
    NOTORIOUS,
    PRICING,
    SLIGHTED,
    UNKNOWN,
    CostMeter,
    GrudgeKernel,
    LLMDialogueEngine,
    PlayerSoul,
    ReplayCache,
)

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


# ---------------------------------------------------------------------------
# PLAYER.SOUL SYMMETRY — the cross-game reputation seam.
# ---------------------------------------------------------------------------


async def _innkeeper(**kw) -> GrudgeKernel:
    """A FRESH NPC (Astrid) who has never met any player."""
    return await GrudgeKernel.birth(
        name="Astrid",
        archetype="The Innkeeper",
        persona="I am Astrid, a wary innkeeper who keeps a careful house.",
        **kw,
    )


async def test_deed_recorded_on_player_soul() -> None:
    """The OTHER direction of the ledger: recording a slight with a player_soul
    also writes the matching deed onto the PLAYER's own soul (their reputation)."""
    bjorn = await GrudgeKernel.birth()
    ragnar = await PlayerSoul.birth(name="Ragnar")

    await bjorn.record(RAGNAR, "I framed you to the guards.", kind="betrayal", player_soul=ragnar)

    # NPC side (existing): Bjorn holds the grievance.
    assert len(await bjorn.grievances(RAGNAR)) >= 1
    # PLAYER side (new): Ragnar's own soul carries the deed = his portable reputation.
    deeds, notoriety = await ragnar.reputation()
    assert len(deeds) >= 1
    assert notoriety == KNOWN
    assert any("betray" in d.lower() for d in deeds)


async def test_reputation_survives_roundtrip_and_fresh_npc_reacts(tmp_path: Path) -> None:
    """THE KILLER TEST for player.soul: reputation survives a .soul export ->
    awaken, and a FRESH NPC who has never met the player reacts to it."""
    bjorn = await GrudgeKernel.birth()
    ragnar = await PlayerSoul.birth(name="Ragnar")
    await bjorn.record(RAGNAR, "I framed you to the guards.", kind="betrayal", player_soul=ragnar)
    await bjorn.record(RAGNAR, "*steals sausages*", kind="theft", player_soul=ragnar)

    # Export the PLAYER's portable identity, drop it, awaken a fresh copy.
    path = tmp_path / "ragnar.player.soul"
    await ragnar.export(str(path))
    assert path.exists() and path.stat().st_size > 0
    del ragnar
    reborn = await PlayerSoul.awaken(str(path))

    # Reputation persisted across the round-trip.
    deeds, notoriety = await reborn.reputation()
    assert len(deeds) >= 2
    assert notoriety == NOTORIOUS

    # A fresh innkeeper who has NEVER met Ragnar reads his player.soul and is wary.
    astrid = await _innkeeper()
    line, seen = await astrid.react_to_reputation(reborn, player_line="A room for the night?")
    assert seen == NOTORIOUS
    assert "Astrid" in line
    assert "Word travels" in line
    assert ("betrayed someone who trusted you" in line) or ("robbed a merchant blind" in line)
    assert "among friends" not in line  # not the warm-stranger branch


async def test_clean_player_stays_warm() -> None:
    """A player with a CLEAN record gets a warm welcome from the same fresh NPC —
    proving reputation drives the wariness, not global suspicion."""
    astrid = await _innkeeper()
    freya = await PlayerSoul.birth(name="Freya")  # never wronged anyone

    line, notoriety = await astrid.react_to_reputation(freya, player_line="A room, please?")
    assert notoriety == UNKNOWN
    assert "among friends" in line
    assert "Word travels" not in line


async def test_reputation_llm_seam_feeds_deeds_to_model() -> None:
    """Record-don't-mock spy on the reputation path: the fresh NPC's live line is
    driven by the player's portable DEEDS fed into the model's prompt."""
    spy = SpyGenerate(canned="You're the one they whisper about. Mind yourself under my roof.")
    astrid = await _innkeeper(dialogue_engine=LLMDialogueEngine(spy))
    ragnar = await PlayerSoul.birth(name="Ragnar")
    await ragnar.record_deed("did:soul:npc:bjorn", "Bjorn", "betrayal", "framed him to the guards")
    await ragnar.record_deed("did:soul:npc:bjorn", "Bjorn", "theft", "stole his sausages")

    line, notoriety = await astrid.react_to_reputation(ragnar, player_line="A room?")

    # (a) the spoken line is the MODEL's output, not the deterministic template.
    assert line == "You're the one they whisper about. Mind yourself under my roof."
    assert notoriety == NOTORIOUS

    # (b) exactly one prompt, carrying the reputation deeds + the NPC's own name + the line.
    assert len(spy.prompts) == 1
    prompt = spy.prompts[0]
    assert ("betrayed someone who trusted you" in prompt) or ("robbed a merchant blind" in prompt)
    assert "Astrid" in prompt
    assert "A room?" in prompt


# ---------------------------------------------------------------------------
# COST METER + REPLAY CACHE — instrumentation at the `generate` seam.
# ---------------------------------------------------------------------------


async def test_cost_meter_counts_and_prices() -> None:
    """CostMeter wraps `generate` transparently and its math checks out.

    Three kernel reactions through LLMDialogueEngine(CostMeter(spy)) ->
    calls==3, token estimates match len//4 hand-math on the exact prompts the
    spy recorded, and total_cost equals the PRICING computation to the dollar.
    """
    spy = SpyGenerate(canned="You'll get nothing from me but silence.")
    meter = CostMeter(spy, model="deepseek-v3.2")
    kernel = await GrudgeKernel.birth(dialogue_engine=LLMDialogueEngine(meter))

    await kernel.record(RAGNAR, "I framed you to the guards.", kind="betrayal")
    await kernel.record(RAGNAR, "*steals sausages*", kind="theft")

    for line in ("Morning.", "Remember me?", "Business as usual?"):
        reaction = await kernel.react(RAGNAR, player_name="Ragnar", player_line=line)
        assert reaction == spy.canned  # passthrough intact — the seam still speaks

    assert meter.calls == 3
    expected_in = sum(len(p) // 4 for p in spy.prompts)
    expected_out = 3 * (len(spy.canned) // 4)
    assert meter.tokens_in == expected_in > 0
    assert meter.tokens_out == expected_out > 0

    in_rate, out_rate = PRICING["deepseek-v3.2"]
    expected_cost = (expected_in * in_rate + expected_out * out_rate) / 1_000_000
    assert meter.total_cost == pytest.approx(expected_cost)
    assert meter.total_cost > 0.0
    assert meter.total_latency >= 0.0

    s = meter.summary()
    assert s["calls"] == 3
    assert s["tokens_in"] == expected_in
    assert s["tokens_out"] == expected_out
    assert s["total_cost"] == pytest.approx(expected_cost)
    assert s["avg_latency"] >= 0.0
    assert s["cost_per_100_lines"] == pytest.approx(expected_cost / 3 * 100)

    cph = meter.cost_per_player_hour()  # default 90 lines/hour
    assert cph == pytest.approx(expected_cost / 3 * 90)
    assert cph > 0.0


async def test_replay_cache_hits_skip_generate(tmp_path: Path) -> None:
    """THE POINT of the cache: a repeated prompt never reaches the model."""
    spy = SpyGenerate(canned="Aye, that's what I said.")
    cached = ReplayCache(spy, path=tmp_path / "cache.jsonl")

    first = await cached("Say something, butcher.")
    second = await cached("Say something, butcher.")
    assert first == second == spy.canned
    assert len(spy.prompts) == 1  # generate ran ONCE for two identical prompts
    assert cached.hits == 1
    assert cached.misses == 1

    await cached("A different prompt entirely.")
    assert len(spy.prompts) == 2  # a new prompt does reach the model
    assert cached.hits == 1
    assert cached.misses == 2

    # Both misses were persisted as jsonl lines.
    lines = (tmp_path / "cache.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2


async def test_replay_roundtrip_is_deterministic_and_free(tmp_path: Path) -> None:
    """THE KILLER: a replayed session is byte-identical and costs $0.

    Session 1 runs a grudge arc with a (canned, prompt-deterministic) model
    behind a ReplayCache writing a jsonl. Session 2 builds a FRESH kernel and a
    FRESH ReplayCache over the SAME file, backed by a generate that fails the
    test if it is ever called — replaying the same player lines yields
    identical spoken lines, zero generate calls, zero metered cost. That is
    the machine-decidable replay gate.
    """
    cache_path = tmp_path / "replay.jsonl"

    async def deterministic_llm(prompt: str) -> str:
        return "canned-" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]

    async def _arc(kernel: GrudgeKernel) -> list[str]:
        await kernel.record(RAGNAR, "Good morning, butcher!", kind="neutral")
        await kernel.record(RAGNAR, "I framed you to the guards.", kind="betrayal")
        await kernel.record(RAGNAR, "*steals sausages*", kind="theft")
        spoken: list[str] = []
        for player_line in ("Morning.", "Bjorn, old friend! Business as usual?"):
            spoken.append(await kernel.react(RAGNAR, player_name="Ragnar", player_line=player_line))
        return spoken

    # SESSION 1 — the "live" run; the cache records every miss to the jsonl.
    cache1 = ReplayCache(deterministic_llm, path=cache_path)
    kernel1 = await GrudgeKernel.birth(dialogue_engine=LLMDialogueEngine(cache1))
    lines1 = await _arc(kernel1)
    assert cache1.misses == 2 and cache1.hits == 0
    assert all(line.startswith("canned-") for line in lines1)  # model lines, not template
    assert cache_path.exists() and cache_path.stat().st_size > 0
    del kernel1

    # SESSION 2 — fresh kernel + fresh cache loading the same file, over a
    # generate that MUST NOT run. (LLMDialogueEngine swallows exceptions into
    # the templated fallback, so we detect calls via the `called` list — a
    # fallback line would also fail the equality assert below.)
    called: list[str] = []

    async def explode(prompt: str) -> str:
        called.append(prompt)
        raise RuntimeError("generate must not be called during replay")

    cache2 = ReplayCache.load(explode, path=cache_path)
    meter2 = CostMeter(cache2, model="deepseek-v3.2")
    kernel2 = await GrudgeKernel.birth(dialogue_engine=LLMDialogueEngine(meter2))
    lines2 = await _arc(kernel2)

    assert lines2 == lines1  # deterministic: byte-identical spoken lines
    assert called == []  # zero generate calls
    assert cache2.hits == 2 and cache2.misses == 0
    assert meter2.calls == 0  # nothing was metered...
    assert meter2.cached_calls == 2  # ...both lines came from the cache
    assert meter2.total_cost == 0.0  # zero-LLM-cost replay
    assert meter2.tokens_in == 0 and meter2.tokens_out == 0


async def test_meter_composes_with_cache(tmp_path: Path) -> None:
    """CostMeter(ReplayCache(...)): hits are free, only misses are metered."""
    spy = SpyGenerate(canned="State your business.")
    cache = ReplayCache(spy, path=tmp_path / "compose.jsonl")
    meter = CostMeter(cache, model="gemini-flash-lite")

    p1, p2 = "Who goes there?", "Open up, butcher."
    await meter(p1)  # miss -> metered
    await meter(p1)  # hit  -> free, unmetered
    await meter(p2)  # miss -> metered

    assert cache.hits == 1 and cache.misses == 2
    assert len(spy.prompts) == 2
    assert meter.calls == 2  # only the two misses were metered
    assert meter.cached_calls == 1  # the hit was counted, but as free

    expected_in = len(p1) // 4 + len(p2) // 4
    expected_out = 2 * (len(spy.canned) // 4)
    assert meter.tokens_in == expected_in
    assert meter.tokens_out == expected_out

    in_rate, out_rate = PRICING["gemini-flash-lite"]
    expected_cost = (expected_in * in_rate + expected_out * out_rate) / 1_000_000
    assert meter.total_cost == pytest.approx(expected_cost)

    # project(): the same metered traffic re-priced under another model.
    ds_in, ds_out = PRICING["deepseek-v3.2"]
    assert meter.project("deepseek-v3.2") == pytest.approx(
        (expected_in * ds_in + expected_out * ds_out) / 1_000_000
    )
    assert meter.project("claude-cli") == 0.0
