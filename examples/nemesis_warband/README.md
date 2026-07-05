<!-- README.md — NEM-4: how to run and demo SAURON'S ARMY, the playable Nemesis
     warband. Created 2026-07-05 (feat/nemesis-warband). -->

# SAURON'S ARMY — a playable Nemesis warband

A Shadow-of-Mordor "Nemesis System" built entirely on
`soul_protocol.profiles.game`: six living orc `.soul`s that hold grudges,
climb a rank hierarchy, feud with each other, and **remember what you did to
them**. Beat one and it rises and gloats; lose and it swears revenge — citing
the specific wrong, by name.

Every member is a real Soul. Their grudges survive a `.soul` export → awaken
round-trip, so a nemesis you export carries its hatred into the next session.

```
uv run python examples/nemesis_warband/server.py
```

Then open **http://localhost:8778**.

## What you're looking at

The **SAURON'S ARMY** board is a ranked pyramid — Warlords on top, Captains in
the middle, Grunts at the bottom. Each card is a living orc: an ornate iron
frame, a procedural crest (a colored monogram, no external art), its rank badge,
and its **grudge toward you** as a blood-red intensity — dim when it has no
quarrel, an ember when SLIGHTED, a blazing red glow when it holds a blood
GRUDGING. A card that holds a grudge shows the line it **REMEMBERS**. Threads
drawn between cards are **rivalries** — orcs who hate *each other* (a hotter,
solid thread means the hatred is mutual). Kill one and it desaturates, crossed
out with a skull.

## The demo script (about a minute)

1. **Confront a Captain and lose.** Click `⚔ Confront` on a Captain, then
   `You lose`. Watch him **crown himself** — he rises to Warlord, his card
   re-flows up into the Warlords tier, and he gloats a revenge vow that names
   the wrong. A same-rank rival seethes with envy (a new rivalry thread appears).
2. **Advance the war.** Click `⚔ Advance the war` a few times. The war pulse
   climbs BUILD_UP → PEAK, and at PEAK a **REVENGE ALERT** flares: the angriest
   orc **hunts you down**, its taunt citing your history. (During the RELAX
   breather nothing hunts you — the pacing has a mandatory lull.) On its cadence
   the director also resolves a **power struggle** between two feuding rivals.
3. **Recruit an orc who already fears you.** Once your notoriety climbs, click
   `+ Recruit`. The new orc reads your **portable reputation** off your player
   `.soul` and its very first line already reacts to your legend — you've never
   met it.
4. **Export a nemesis's soul.** After a confront, click `⬇ Export this nemesis`
   in the result panel to download that orc's `.soul` (grudge and all), or
   `⬇ Export army` in the banner for a `.zip` of the whole warband.

## Live taunts with an LLM

By default every orc speaks through the deterministic grimdark
`WarbandDialogueEngine` (offline, `$0`). For real, persona-driven taunts:

```
# uses the local `claude` CLI — no API key needed in this environment (~20-40s/line)
uv run python examples/nemesis_warband/server.py --engine claude

# or DeepSeek's chat API (needs DEEPSEEK_API_KEY; missing key falls back gracefully)
DEEPSEEK_API_KEY=sk-... uv run python examples/nemesis_warband/server.py --engine deepseek
```

Each member gets its own LLM voice, prompted from its persona + OCEAN + grudge
history. A model failure never crashes the game — it falls back to that member's
grimdark warband voice, so it always sounds like an orc.

## How it's built

| Piece | File | Role |
|-------|------|------|
| Warband engine | `warband.py` | N members, ranks, clash loop, NPC↔NPC rivalries, recruit, board |
| Director | `nemesis_director.py` | revenge beats at PEAK + power struggles, all pure functions of grudge/rank state |
| The warband's voice | `warband_voice.py` | a grimdark, name/epithet/rank-aware `DialogueEngine` (replaces the package's butcher template — the engine is a pluggable protocol) |
| Server | `server.py` | stdlib HTTP bridge (one background asyncio loop), `--engine` switch, `.soul` exports |
| Board UI | `index.html` / `style.css` / `app.js` | the grimdark army screen — ranked tiers, procedural crests, rivalry threads, confront modal, revenge alerts |

Zero files under `soul_protocol.profiles.game` were modified — the warband is a
pure consumer of the package, and its own voice plugs into the package's
`DialogueEngine` protocol.

### Endpoints (for the curious)

`GET /board`, `GET /events?since=N`, `GET /reputation`,
`POST /confront {member_did, player_won}`, `POST /tick`, `POST /recruit`,
`POST /export_member {did}`, `POST /export_warband`.

### Tests

```
uv run pytest examples/nemesis_warband/ -v
```
