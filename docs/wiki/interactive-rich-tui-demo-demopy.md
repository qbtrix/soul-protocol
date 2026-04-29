---
{
  "title": "Interactive Rich TUI Demo — `demo.py`",
  "summary": "A 5-act interactive terminal walkthrough of soul-protocol that demonstrates memory storage, emotional state, OCEAN personality, and cognitive processing without requiring an LLM or API key. Designed for GIF recording and first-run discovery.",
  "concepts": [
    "demo",
    "Rich TUI",
    "OCEAN bars",
    "soul.observe",
    "no LLM required",
    "python -m soul_protocol",
    "5-act walkthrough",
    "SOUL_DEMO_NO_PAUSE",
    "memory recall",
    "cognitive pipeline",
    "GIF recording",
    "temporary soul"
  ],
  "categories": [
    "developer-tools",
    "demo",
    "onboarding"
  ],
  "source_docs": [
    "bc2f3cbce8ef885e"
  ],
  "backlinks": null,
  "word_count": 477,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

`demo.py` is the showroom for soul-protocol. It runs entirely locally — no LLM, no API key, no network — and walks through five acts that demonstrate what the psychology pipeline does to a fresh soul as it processes scripted conversations.

Running `python -m soul_protocol` executes this file.

## Why No LLM Required

The soul-protocol psychology pipeline (OCEAN personality, mood tracking, memory compression, graph evolution) is deterministic given fixed inputs. The demo exploits this: it feeds scripted `CONVERSATIONS` into `soul.observe()` and lets the cognitive engine do its work, then displays the results with Rich. This design means anyone can see the library working in under 30 seconds without setup.

## Five-Act Structure

```
Act 1: Birth        — Create a soul with name, archetype, and OCEAN profile
Act 2: Remember     — Feed five conversations; show memories being stored
Act 3: Feel         — Display emotional state evolution (mood + energy)
Act 4: Recall       — Query memories and show retrieval results
Act 5: Reflect      — Trigger consolidation; show before/after memory counts
```

Each act is separated by a `_pause()` call that waits for Enter — making the demo suitable for step-by-step screen recording.

## Key Functions

### `_ocean_bars(console, personality)`
Renders each of the five OCEAN traits as a labelled horizontal bar using Rich `Text` objects with colour-coded percentages. High values are green; low values are red. This visual makes the abstract personality model tangible.

### `_emoji_for(label)`
Maps domain labels from `CONVERSATIONS` to display emojis for the Rich output tables. Falls back to a neutral glyph for unknown labels.

### `_make_console()`
Creates a Rich `Console` with markup and colour disabled when stdout is not a TTY. This prevents escape codes from appearing in log files or CI output.

### `_no_pause()`
Reads `SOUL_DEMO_NO_PAUSE` at call time (not at import time) so test code can set the environment variable after import and still suppress pauses:

```python
os.environ["SOUL_DEMO_NO_PAUSE"] = "1"
```

### `run_demo()`
The async main loop. Creates a `tempfile.TemporaryDirectory` so the demo soul is always ephemeral — no leftover files after the demo exits.

## CI Integration

Setting `SOUL_DEMO_NO_PAUSE=1` makes the demo run non-interactively, allowing it to be used as a smoke test in CI pipelines. The TTY check in `_make_console()` further ensures clean output in non-interactive environments.

## `CONVERSATIONS` Dataset

Ten scripted exchanges across domains (coding, emotion, philosophy, work, creativity, music, fitness, travel, reading, nature). Each entry is a `(user_input, agent_output, domain_label)` tuple. Fixed content ensures the demo renders identically across runs.

## Known Gaps

- The demo uses `tempfile.TemporaryDirectory` which means the demonstrated soul is lost when the process exits. There is no "save this demo soul" option.
- OCEAN bar rendering assumes terminal width of at least 60 characters; narrower terminals truncate the bars.
- The demo does not show eternal storage, org features, or the dream cycle — these are production features not suitable for a first-run walkthrough.
