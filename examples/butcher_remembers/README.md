<!-- README.md — "The Butcher Remembers" 90-second demo.
     Updated: 2026-07-02 (BD-2) — full rewrite: run one-liners per engine
     (templated / claude / deepseek), the demo script beats mapped to UI
     actions, the 7-beat video shot list, the Gemini Nano note, and
     troubleshooting. -->

# The Butcher Remembers

The Soul Protocol Game Profile's 90-second demo: two `npc.soul` minds (Bjorn
the butcher, Astrid the innkeeper), one `player.soul` (Ragnar), one `GameWorld`
narrating every state change as an engine-neutral event stream — and a 2D
canvas tavern drawing it live. Wrong the butcher, export him as a **file**,
wrong him some more, import the file back — he forgets what happened after the
export, because *he is the file*. Then ask the innkeeper about yourself: she
has never been wronged by you, but your `player.soul` carries your reputation,
and she reads it.

Python stdlib + vanilla JS. No frameworks, no build step, no npm, no account.

## Run it

```bash
# Free + deterministic (TemplatedDialogueEngine) — the default:
uv run python examples/butcher_remembers/server.py --scripted

# Real LLM lines via the local claude CLI (no API key; ~20-40s per line):
uv run python examples/butcher_remembers/server.py --engine claude

# Real LLM lines via the DeepSeek API (fast + ~$0.0001/line):
DEEPSEEK_API_KEY=sk-... uv run python examples/butcher_remembers/server.py --engine deepseek
```

Then open **http://localhost:8777**. `--scripted` auto-plays the canonical
six-beat arc (greet → trade → betrayal → theft → Astrid control beat → "old
friend?" → the butcher remembers), one beat every ~1.4s.

## The 90-second demo script (beats → UI actions)

| # | Beat | Time | Do this in the UI |
|---|------|------|-------------------|
| 1 | **Create** | 0:00 | Start the server (or click **Reset world**) — three Souls are born with real DIDs, zoned on the canvas. |
| 2 | **Befriend** | 0:15 | Bottom bar: type friendly lines ("Good morning, Bjorn! Fine sausages.") and **Send**. No kind dropdown — the server classifies. Bjorn stays warm, bond ~50+. |
| 3 | **Betray** | 0:25 | Type "While you argued with the guard, I pocketed a string of sausages." — classified `theft` (echoed under the bar). Bond drops, ledger chip flips `SLIGHTED` → `GRUDGING`. |
| 4 | **THE FILE** | 0:40 | Click **⬇ Export bjorn.soul**. A real `.soul` (zip) lands in your downloads. *He's a file. ~16 KB. And he remembers.* |
| 5 | **Return** | 0:50 | Keep wronging him, then **⬆ Import soul** and pick the earlier `bjorn.soul` — his grudge state reverts to the moment of export. Or import into a *fresh* world after Reset: still hostile, names the theft. |
| 6 | **Gut-punch** | 1:05 | Click **🏨 Ask the innkeeper about me**. Astrid has no grievance of her own — she reads Ragnar's `player.soul` reputation: *"Word travels… move along."* Amber bubble + notoriety chip. |
| 7 | **Tag** | 1:20 | Cost overlay (top-right, LLM engines only): claude = **$0.00**, plus "would cost on DeepSeek: $0.000xx". *Worlds that remember you. Your reputation is a file YOU own.* |

**⬇ Export ragnar.player.soul** downloads the reputation file itself — the
artifact the player carries between games.

## Engines

| `--engine` | Backend | Cost | Latency | Notes |
|---|---|---|---|---|
| `templated` (default) | Deterministic templates | $0 | instant | What the tests run. Cost overlay hidden. |
| `claude` | Local `claude` CLI | $0 (no API key) | **~20-40s per line** — narrate over it or pre-bake takes | Metered as `claude-cli`; token counts still feed the DeepSeek projection. |
| `deepseek` | `https://api.deepseek.com/chat/completions`, model `deepseek-chat` | ~$0.0001/line | ~2-5s | Needs `DEEPSEEK_API_KEY`. Missing key → prints a warning and falls back to templated (never crashes). |

**Gemini Nano (browser-native, not wired):** the endgame for the "$0, ran in
YOUR browser" kicker is Chrome's built-in Prompt API (Gemini Nano on-device).
It needs a Chrome Origin Trial token + `chrome://flags` today, so this demo
documents it rather than wiring it. The seam is ready: any
`async (prompt) -> str` dropped into `LLMDialogueEngine` works — a client-side
Nano bridge would POST generated lines back through the same `/line` loop.

## What you'll see

- **Canvas tavern** — labeled zones (Bjorn's stall / tables / door), souls as
  colored circles (Ragnar wears the light ring), fading speech bubbles.
  Reputation lines glow amber and linger.
- **Grudge ledger (right panel)** — per-NPC: grudge chip (`NONE` green /
  `SLIGHTED` amber / `GRUDGING` red), live bond, last remembered grievance.
- **Top bar** — Pulse director phase (`BUILD_UP` / `PEAK` / `FADE` / `RELAX`)
  and the running cost readout.
- **Bottom bar** — free-play input (kind auto-classified), the soul
  export/import buttons, the innkeeper button, the notoriety chip.

## Flags

| Flag | Default | What it does |
| --- | --- | --- |
| `--port` | `8777` | HTTP port |
| `--scripted` | off | auto-play the six-beat arc |
| `--delay` | `1.4` | seconds between scripted beats |
| `--session-log PATH` | off | mirror the event stream to a `session.jsonl` |
| `--engine` | `templated` | `templated` \| `claude` \| `deepseek` |

## Endpoints

- `GET /snapshot` — zones, phase, per-NPC bond/grudge, active `engine`
- `GET /events?since=N` — world events with `t > N` (the client polls this)
- `GET /cost` — meter summary + `projected_deepseek` + `cost_per_player_hour`
  (zeros on templated)
- `GET /reputation?npc=Astrid&player=Ragnar` — `{line, notoriety}`
- `POST /line` — `{"player","text","kind"?,"npc"?}`; omit `kind` and the
  keyword classifier picks `theft` / `betrayal` / `insult` / `neutral`
- `POST /reset` — rebuild the world fresh
- `POST /export_soul` — `{"npc"?}` → the `.soul` bytes as a download
- `POST /export_player` — `{"player"?}` → the `.player.soul` download
- `POST /import_soul` — raw `.soul` bytes → awaken + swap the same-named NPC

## Troubleshooting

- **Port already in use** — another demo is running: `--port 8778`, or kill it
  (`lsof -ti :8777 | xargs kill`).
- **`claude` lines are slow** — expected: the local CLI takes ~20-40s per
  line. The world loop serializes beats, so queued lines land in order. For a
  smooth video, use `deepseek`, or record templated and voice-over.
- **DeepSeek silently templated?** — the server printed
  `DEEPSEEK_API_KEY is not set` at startup and fell back. Export the key and
  restart.
- **Import does nothing** — the file must be a `.soul` exported from this
  demo whose NPC name matches one in the world (`Bjorn` or `Astrid`); anything
  else returns a 400 with the reason (shown under the bottom bar).
- **Stale UI after hacking on app.js** — hard-reload; there's no cache
  busting.
