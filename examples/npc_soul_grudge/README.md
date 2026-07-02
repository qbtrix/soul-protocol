<!-- README.md — npc.soul grudge kernel demo (thin consumer of the game profile) -->
<!-- Updated: 2026-07-02 — the experiment graduated: grudge.py / player.py /
     dialogue.py / costmeter.py moved into src/soul_protocol/profiles/game/ and
     the tests into tests/profiles/game/. This folder keeps only demo.py + this
     README, importing from soul_protocol.profiles.game. Spec: spec/profiles/game.md -->

# npc.soul grudge kernel — demo

A walkthrough of the **Game Profile** (`soul_protocol.profiles.game`): a real
Soul as a **game NPC who holds a grudge** — and remembers it across a `.soul`
export → awaken round-trip — plus a **player.soul** whose reputation travels
with them.

This folder is a thin consumer. The code lives in the package:

- **Runtime** — `src/soul_protocol/profiles/game/` (`GrudgeKernel`,
  `PlayerSoul`, the `DialogueEngine` seam, `CostMeter` + `ReplayCache`)
- **Spec** — [`spec/profiles/game.md`](../../spec/profiles/game.md) — the Game
  Profile RFC: the normative conventions (grievance/deed tagging, PUBLIC
  visibility, per-player scoping) and why they work on the unchanged core
- **Tests** — `tests/profiles/game/` — 15 deterministic tests (no LLM, no
  network), including the round-trip and replay "killer tests"

## The magic moment

Meet **Bjorn the butcher**. A player (Ragnar) greets him, trades fairly, then
betrays and robs him:

- His **bond** with that player weakens (50 → ~2).
- Each wrong is stored as a durable **episodic grievance** memory.
- His **reaction** shifts from a warm welcome → wary → openly hostile, and when
  hostile he **names what the player did**.

Then Bjorn is **exported to a `.soul` file and awakened in a fresh process** —
and he *still* remembers. He greets the returning Ragnar with a cleaver and the
grudge intact, while a different player (Astrid) he was never wronged by gets
the warm welcome. The grudge is **per-player**, not global.

The demo then flips the ledger around: Ragnar's wrongs are also written to his
**own** `player.soul` as PUBLIC deeds, and a fresh innkeeper who has *never met
him* reads that portable reputation and turns wary — while a clean-record
newcomer stays welcome.

## Run it

From the `soul-protocol` repo root:

```bash
# the proof (deterministic — no LLM, no network)
uv run pytest tests/profiles/game/ -v

# watch Bjorn sour and remember across a reload —
# runs the templated arc + the player.soul reputation arc, then a LIVE
# claude-cli arc with real LLM lines and a cost-meter summary at the end
uv run python examples/npc_soul_grudge/demo.py
```

The LIVE section shells out to `claude -p` (~10s per line, no API key needed in
this environment) and falls back to the deterministic template — clearly
tagged — if the CLI is unavailable. Everything before it is instant and free.

## Using the profile in your own code

```python
from soul_protocol.profiles.game import GrudgeKernel, PlayerSoul

npc = await GrudgeKernel.birth(name="Bjorn", archetype="The Butcher")
player = await PlayerSoul.birth(name="Ragnar")

await npc.record(player.did, "I framed you to the guards.", kind="betrayal",
                 player_soul=player)
print(await npc.react(player.did, player_name="Ragnar"))   # hostile, names the wrong

await npc.export("bjorn.soul")                              # ...and it survives
reborn = await GrudgeKernel.awaken("bjorn.soul")
```

For the conventions behind this (why grievances are `visibility=PUBLIC`, how
tags ride on `entities` + content markers, what round-trips), read the spec:
[`spec/profiles/game.md`](../../spec/profiles/game.md).
