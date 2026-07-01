# npc.soul grudge kernel (experiment)

A thin layer that turns a real Soul into a **game NPC who holds a grudge** — and
remembers it across a `.soul` export → awaken round-trip.

Built on top of Soul Protocol. It imports the real `Soul` and touches no core
files. The grudge machinery is deterministic and free (proven by `pytest`); the
NPC's **spoken line** sits behind a pluggable `DialogueEngine` seam, so the exact
same grudge can be voiced by a deterministic template (default, free) **or a real
LLM** (vivid, in-character) without changing any of the memory/bond logic.

## The magic moment

Meet **Bjorn the butcher**. A player (Ragnar) greets him, trades fairly, then
betrays and robs him:

- His **bond** with that player weakens (50 → ~2).
- Each wrong is stored as a durable **episodic grievance** memory.
- His **reaction** shifts from a warm welcome → wary → openly hostile, and when
  hostile he **names what the player did**.

Then Bjorn is **exported to a `.soul` file and awakened in a fresh process** —
and he *still* remembers. He greets the returning Ragnar with a cleaver and the
grudge intact, while a different player (Astrid) he was never wronged by gets the
warm welcome. The grudge is **per-player**, not global.

The proof is `test_grudge_survives_soul_roundtrip`: export → awaken → the grudge,
the grievances, and the weakened bond all persist.

## Files

- `grudge.py` — `GrudgeKernel`, a thin wrapper over one `Soul`:
  - `record(player_did, text, kind)` — `kind ∈ {neutral, insult, theft, betrayal}`.
    Always `observe()`s the interaction; for a non-neutral kind it plants a
    tagged episodic grievance and weakens the per-player bond.
  - `grievances(player_did)` — recall this player's grievances.
  - `grudge_level(player_did)` — `NONE | SLIGHTED | GRUDGING`, from grievance
    count + cumulative severity.
  - `react(player_did, player_name, player_line="")` — the NPC's spoken
    reaction, produced by the configured `DialogueEngine`. Tone changes by level
    and the hostile branch cites the remembered wrongs. `player_line` (what the
    player just said) is only used by the LLM engine; the templated engine
    ignores it, so old call sites keep working.
  - `GrudgeKernel.birth(..., dialogue_engine=...)` / `.awaken(..., dialogue_engine=...)`
    — swap how the line is voiced. Default is the templated engine.
- `dialogue.py` — the pluggable seam (mirrors Soul Protocol's own
  Protocol + fallback + optional real backend pattern):
  - `DialogueEngine` (`Protocol`) — `async speak(persona, ocean, grudge_level,
    grievances, player_line, player_name) -> str`.
  - `TemplatedDialogueEngine` — the original deterministic branches, verbatim.
    The **default**: free, offline, keeps the tests green.
  - `LLMDialogueEngine(generate)` — builds a strong in-character prompt from the
    NPC's full state and calls an injected `async generate(prompt) -> str`. On
    empty output or **any** error it falls back to the templated engine, so a
    flaky model or missing binary never crashes the game loop.
  - `claude_cli_generate` — a working no-key backend for this environment: shells
    out to `claude -p` (~10s/call, no `ANTHROPIC_API_KEY` needed here). Soul
    Protocol also ships adapters at
    `src/soul_protocol/runtime/cognitive/adapters/` (ollama, anthropic, litellm,
    …) that can back `generate` when a key/endpoint exists.
- `demo.py` — headless walkthrough that prints Bjorn's reaction and bond at each
  step, exports him, awakens a fresh kernel, and reacts again — first with the
  **templated** engine, then a **LIVE** section that replays the same arc with
  `LLMDialogueEngine(claude_cli_generate)` so you can watch real LLM lines shift
  warm → hostile (falls back to templated, clearly tagged, if claude-cli errors).
- `test_grudge_kernel.py` — pytest (pytest-asyncio) proving the loop and the
  round-trip. Includes a **spy** test (`SpyGenerate`, record-don't-mock) that
  drives the real `LLMDialogueEngine` and asserts the prompt the model *would*
  receive carries the grievance content and the grudge level — proving the seam
  feeds real context to the model — plus a fallback test. All tests are
  deterministic (no live LLM, no subprocess, no network).

## Run it

From the `soul-protocol` repo root:

```bash
# the proof (deterministic — no LLM, no network)
uv run pytest examples/npc_soul_grudge/test_grudge_kernel.py -v

# watch Bjorn sour and remember across a reload —
# runs the templated arc, then a LIVE claude-cli arc with real LLM lines
uv run python examples/npc_soul_grudge/demo.py
```

## How it maps onto the real Soul (API notes)

The runtime `MemoryEntry` has **no free-form metadata dict**, and
`Soul.remember()` takes no `metadata=` kwarg. So grievance tags ride on the real
fields that persist through export:

- **`user_id=player_did`** — Soul's native per-user attribution. `recall(user_id=…)`
  filters by it, and each player automatically gets their own `Bond` in the
  `BondRegistry`. This is what makes the grudge per-player.
- **`entities=["grudge", kind, player_did]`** + a marker embedded in the content
  (`[GRUDGE kind=betrayal severity=0.90]`) — machine-recoverable tags so
  `grievances()` can find and classify wrongs after a reload.
- **`visibility=PUBLIC`** — deliberate. `recall()` hides `BONDED` memories once
  `bond_strength < bond_threshold` (default 30). Because wronging Bjorn *weakens*
  the bond below 30, storing grievances as `BONDED` would hide them exactly when
  the grudge peaks. `PUBLIC` always passes the visibility filter — and it's
  semantically right: a grudge is a hostile fact the NPC acts on openly.
- **`bond.weaken(amount, user_id=player_did)`** — routes to the per-player bond;
  `observe(user_id=…)` strengthens the same one. Both survive export via
  `SoulConfig.bonds_per_user`.

Bond and grievance memories round-trip through `Soul.export()` →
`Soul.awaken()` with no extra work — that's the persistence the experiment
proves.
