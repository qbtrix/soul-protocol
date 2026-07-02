<!-- game.md — The Game Profile: npc + player roles as the first Soul Protocol profile -->
<!-- Created: 2026-07-02 — Written from the graduated reference runtime at
     src/soul_protocol/profiles/game/ (experiment/npc-soul-grudge-kernel). -->
<!-- Updated: 2026-07-02 — §8: director + dials moved from forward work to
     shipped-in-reference-runtime-v0.1, with a normative §8.1 (DirectorEngine,
     Dials, ChallengeDial, ProgressTracker, ChoiceGuard, SparkScheduler);
     §2 file list gains director.py + dials.py. -->

# Soul Protocol Game Profile: `npc.soul` and `player.soul`

**Version:** 0.1.0
**Status:** Draft — first profile of the Soul Protocol profile mechanism
**Date:** 2026-07-02
**Authors:** OCEAN Foundation

---

## Table of Contents

1. [Overview](#1-overview)
2. [Profiles Over Core](#2-profiles-over-core)
3. [Roles](#3-roles)
4. [Normative Conventions](#4-normative-conventions)
5. [Graceful Degradation](#5-graceful-degradation)
6. [The Dialogue Seam](#6-the-dialogue-seam)
7. [Profile Registry and Evolution](#7-profile-registry-and-evolution)
8. [Forward Work](#8-forward-work)

The key words "MUST", "MUST NOT", "SHOULD", "MAY" are to be interpreted as
described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## 1. Overview

A **profile** is a documented set of conventions layered over the unchanged
Soul Protocol core. The Game Profile specializes ordinary souls into two game
roles — an **NPC** that holds per-player grudges and a **player** whose
reputation travels with them — using only the fields, visibility rules, and
round-trip guarantees the core `.soul` format already provides.

The profile's claims are executable: the reference runtime ships at
`soul_protocol.profiles.game`, and `tests/profiles/game/` proves the two
load-bearing properties deterministically (no LLM, no network):

- **Grudge persistence** — an NPC exported to a `.soul` file and awakened in a
  fresh process still holds the grudge, cites the specific wrongs, and keeps
  the weakened per-player bond (`test_grudge_survives_soul_roundtrip`).
- **Portable reputation** — a player's own `.soul` carries their deeds; a
  fresh NPC that has never met them reads that reputation and reacts to it
  (`test_reputation_survives_roundtrip_and_fresh_npc_reacts`).

## 2. Profiles Over Core

The layering, from most stable to most product-specific:

| Layer | What | Status |
|-------|------|--------|
| **L0** | Core `.soul` spec ([SOUL-FORMAT-SPEC.md](../SOUL-FORMAT-SPEC.md)) and the `Soul` runtime | **UNCHANGED** by this profile |
| **L1** | Profiles — conventions over L0 (this document) | Draft |
| **L2** | Reference runtime — `soul_protocol.profiles.game` | Shipped |
| **L3** | Products — games, worlds, marketplaces built on L2 | Out of scope |

A profile MUST NOT require changes to L0. This is not an aspiration but the
empirical record: the Game Profile shipped with **zero modifications to core
files** — the reference runtime is new files only (`grudge.py`, `player.py`,
`dialogue.py`, `costmeter.py`, `director.py`, `dials.py`), importing `Soul`, `MemoryType`,
`MemoryVisibility`, and `Interaction` from the public API like any external
consumer would.

## 3. Roles

### 3.1 `npc` — a character mind

Implemented by `GrudgeKernel`, a thin wrapper over ONE `Soul`:

- `GrudgeKernel.birth(name, archetype, persona, dialogue_engine=None)` /
  `GrudgeKernel.awaken(path)` / `export(path)` — lifecycle over the core soul.
- `record(player_did, text, kind, player_soul=None)` — one player action,
  `kind ∈ {neutral, insult, theft, betrayal}`. Always `observe()`s the
  interaction; non-neutral kinds also plant a **grievance** memory, weaken the
  per-player bond by `BOND_DAMAGE[kind]`, and (when `player_soul` is given)
  write the matching deed to the player's own soul.
- `grievances(player_did)` / `grudge_level(player_did)` — recovered wrongs and
  the level derived from their count + cumulative `SEVERITY`:
  **`NONE`** (no grievances) → **`SLIGHTED`** (one low-severity wrong) →
  **`GRUDGING`** (2+ wrongs or cumulative severity ≥ 1.0).
- `react(player_did, player_name, player_line)` and
  `react_to_reputation(player_soul, player_line)` — the reaction seams; both
  delegate the spoken line to the configured `DialogueEngine` (§6).

### 3.2 `player` — a portable identity

Implemented by `PlayerSoul`, also a thin wrapper over ONE `Soul`:

- `PlayerSoul.birth(name, ocean=None)` / `awaken(path)` / `export(path)` —
  the player's identity is a real soul on the same `.soul` format.
- `record_deed(npc_did, npc_name, kind, text)` — the other direction of the
  ledger: the wrong the NPC remembers as a grievance, the player carries as a
  **deed** on their own soul.
- `deeds()` / `reputation()` — recovered deeds (worst first) and the notoriety
  band derived from their count + cumulative severity:
  **`UNKNOWN`** (clean record) → **`KNOWN`** → **`NOTORIOUS`**.

The two roles agree on how bad each wrong is through one shared table
(`SEVERITY`: insult 0.4, theft 0.7, betrayal 0.9).

## 4. Normative Conventions

### 4.1 Grievance and deed tagging

The core `MemoryEntry` has **no free-form metadata field**, and
`Soul.remember()` accepts no `metadata=` kwarg. Profile tags therefore ride on
fields that DO persist. A grievance or deed memory MUST carry:

1. A machine-parseable **content marker** at the start of `content`:
   - grievance: `[GRUDGE kind=<kind> severity=<0.00-1.00>]`
   - deed: `[DEED kind=<kind> target=<npc_did>]`
2. An **entities list** naming the tag, the kind, and the counterparty:
   - grievance: `entities=["grudge", kind, player_did]`
   - deed: `entities=["deed", kind, npc_did]`
3. `type=MemoryType.EPISODIC` and high importance (the reference uses 9).

Readers MUST treat the content marker as the source of truth for kind and
severity (recall is keyword-based; the entities list is the coarse filter, the
marker the classifier).

### 4.2 Visibility: negative and reputation memories MUST be PUBLIC

Grievances and deeds MUST be stored with `visibility=MemoryVisibility.PUBLIC`.

This is load-bearing, not cosmetic. The core's `filter_by_visibility()`
(`runtime/memory/recall.py`) hides **BONDED** memories from a requester once
`bond_strength < bond_threshold` (default 30.0). Wronging an NPC *weakens* the
bond below that threshold — so a grievance stored as BONDED would vanish from
recall **exactly when the grudge peaks**. This trap is real; the profile
documents it so no implementation rediscovers it. PUBLIC always passes the
filter, and it is semantically right: a grudge is a hostile fact the NPC acts
on openly, and reputation is by definition the record strangers can read.

### 4.3 Per-player scoping

Every grievance MUST be attributed via `user_id=player_did` — the core's
native per-user scoping. This gives each player their own recall partition
AND their own `Bond` in the soul's `BondRegistry` (`soul.bond_for(did)`,
seeded at strength 50). Grudges are per-relationship, never global.

### 4.4 Bond semantics

Transgressions MUST weaken the per-player bond
(`soul.bond.weaken(BOND_DAMAGE[kind], user_id=player_did)`; the reference uses
insult 12 / theft 20 / betrayal 30). Neutral interactions strengthen the same
bond through the normal `observe(..., user_id=player_did)` pipeline. The bond
is the cheap scalar readout of the relationship; the grievances are the
recoverable record.

### 4.5 Round-trip guarantees

Everything above persists through `Soul.export()` → `Soul.awaken()` with no
profile-specific serialization: per-player bonds ride in
`SoulConfig.bonds_per_user`, and grievance/deed memories ride in the archive's
memory payload (`memory_data`) like any other episodic entry. A conforming
implementation MUST NOT introduce side-channel state that does not survive
this round-trip — the `.soul` file IS the character.

## 5. Graceful Degradation

A game-profile soul is a **valid vanilla soul**. Any generic `.soul` reader —
one that has never heard of this profile — MUST be able to open it and see
ordinary episodic memories, entities, and bonds; the grievance markers are
just content prefixes to such a reader. Game-aware runtimes see more: they
parse the markers, compute grudge levels and notoriety, and drive reactions.
Profiles add meaning, never incompatibility.

## 6. The Dialogue Seam

How the NPC's state becomes *words* is deliberately outside the grudge
machinery, behind a `Protocol`:

- `DialogueEngine.speak(persona, ocean, grudge_level, grievances,
  player_line, player_name)` — the personal-grudge voice.
- `DialogueEngine.speak_reputation(npc_name, persona, ocean, notoriety,
  reputation_deeds, player_line, player_name)` — the hearsay voice, for an NPC
  reacting to a player it has never met.

Engines are swappable without touching any grudge state:
`TemplatedDialogueEngine` (deterministic, free, the default — it keeps the
test suite offline), `LLMDialogueEngine(generate)` (builds an in-character
prompt from the same state and calls any injected
`async generate(prompt) -> str`, falling back to the template on empty output
or any error), or anything else satisfying the Protocol. `claude_cli_generate`
is the reference's zero-key backend.

Cost instrumentation composes at the same seam, not inside the engines:
`CostMeter(generate, model=...)` meters tokens, latency, and $ against
`PRICING` (with `summary()`, `cost_per_player_hour()`, and `project(model)`
re-pricing), and `ReplayCache(generate, path=...)` makes a recorded session
replayable byte-identically at zero model cost. They stack:
`LLMDialogueEngine(CostMeter(ReplayCache(generate, path), model=...))`.

## 7. Profile Registry and Evolution

Profiles are **author-without-permission**: anyone can write one against the
public core API and ship it, exactly as this one was built. A profile becomes
worth registering when its conventions are documented (a spec like this one)
and its claims are executable (a conformance test suite).

Building this profile surfaced two candidates for promotion INTO the core —
the intended feedback loop:

1. **A `profiles:` declaration field in `soul.json`** — so a reader can
   discover which convention sets a soul follows instead of sniffing content
   markers.
2. **First-class `MemoryEntry` metadata** — a structured field would make §4.1
   markers unnecessary; profiles are currently encoding metadata into content
   because the core offers nowhere else to put it.

Until promoted, conforming implementations MUST rely only on the conventions
in §4.

## 8. Forward Work

The director and dials, drafted here as forward work, have shipped; §8.1
specifies them. No other forward work is currently planned.

### 8.1 Director and Dials — shipped in reference runtime v0.1 (Normative)

- **Director** — `DirectorEngine` (`director.py`) paces event FREQUENCY, not
  amplitude: `observe_beat(player_did, kind, grudge_level)` accrues per-player
  heat (base `SEVERITY`, grudge-amplified, decayed per beat) through the cycle
  `BUILD_UP → PEAK → FADE → RELAX`. A conforming director MUST escalate only
  in `BUILD_UP` below the peak threshold (`should_escalate()`), MUST enforce
  the relax window regardless of heat, and MUST NOT veto a player action —
  `yes_and()` returns a build-on suggestion for every input. An
  `enjoyment_signal` hook (0–1) MAY scale the peak threshold.
- **Dials** — `dials.py` ships the feel parameters as four continuous 0.0–1.0
  dials bundled by `Dials` and wired via `Dials.build()`: `ChallengeDial`
  (maps its level to the director's peak threshold and heat multiplier),
  `ProgressTracker` (MUST advance at least one track even on a failed beat —
  failure is progression), `ChoiceGuard` (`offer()` MUST return ≥ 2 actions,
  synthesizing an alternative when fewer are viable), and `SparkScheduler`
  (variation pressure once the last K beats run same-kind).
