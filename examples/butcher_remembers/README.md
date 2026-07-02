# The Butcher Remembers

The Game Profile's scripted grudge arc, rendered live in a browser. Two
`npc.soul` minds (Bjorn the butcher, Astrid the innkeeper), one `player.soul`
(Ragnar), one `GameWorld` narrating everything as an engine-neutral event
stream — and a 2D canvas tavern drawing that stream as it happens.

Python stdlib + vanilla JS only. No frameworks, no build step, no npm, no API
key: dialogue is the deterministic `TemplatedDialogueEngine`.

## Run it

```bash
uv run python examples/butcher_remembers/server.py --scripted
```

Then open **http://localhost:8777**.

`--scripted` auto-plays the canonical arc, one beat every ~1.4s:

1. Ragnar greets Bjorn (neutral) — warm welcome, bond healthy.
2. Ragnar trades fairly (neutral) — still friendly.
3. Ragnar lies to the town guard about him (**betrayal**) — Bjorn tips to
   `SLIGHTED`, bond drops hard.
4. Ragnar pockets sausages (**theft**) — `GRUDGING`. The ledger card goes red.
5. Ragnar chats with Astrid (neutral) — the control: she holds no grudge and
   stays warm while Bjorn seethes two zones away.
6. Ragnar tries "old friend?" on Bjorn (neutral) — the butcher remembers, and
   says so, citing the actual wrongs.

## What you'll see

- **Canvas tavern** — labeled zones (Bjorn's stall / tables / door), each soul
  a colored circle (Ragnar wears the light ring), speech bubbles that fade
  after a few seconds. Player lines get the slate bubble, NPC lines the
  parchment one.
- **Grudge ledger (right panel)** — one card per NPC: grudge level chip
  (`NONE` green / `SLIGHTED` amber / `GRUDGING` red), live bond number, and
  the last remembered grievance line.
- **Top bar** — the Pulse director's phase (`BUILD_UP` / `PEAK` / `FADE` /
  `RELAX`) plus a dialogue-cost readout (always $0 here; `cost_tick` events
  light it up when a metered LLM engine is wired in).

## Controls

After (or instead of) the script, keep playing from the panel: pick the NPC
and the act kind (`neutral` / `insult` / `theft` / `betrayal`), type a line,
**Say it**. **Reset world** births fresh souls and starts the ledger clean.

## Flags

| Flag | Default | What it does |
| --- | --- | --- |
| `--port` | `8777` | HTTP port |
| `--scripted` | off | auto-play the six-beat arc above |
| `--delay` | `1.4` | seconds between scripted beats |
| `--session-log PATH` | off | mirror the event stream to a `session.jsonl` |

## Endpoints (for the curious)

- `GET /snapshot` — zones, director phase, per-NPC bond/grudge (HUD bootstrap)
- `GET /events?since=N` — world events with `t > N` (the client polls this)
- `POST /line` — `{"player": "Ragnar", "text": "...", "kind": "insult", "npc": "Bjorn"}`
- `POST /reset` — rebuild the world fresh
