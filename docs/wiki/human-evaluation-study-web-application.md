---
{
  "title": "Human Evaluation Study Web Application",
  "summary": "A FastAPI web application that runs a blinded A/B human evaluation study, presenting participants with two AI agents — one soul-enabled, one a plain baseline — and collecting Likert survey responses after each. The app manages sessions, randomizes agent order to eliminate position bias, and exports results to JSON and CSV for statistical analysis.",
  "concepts": [
    "FastAPI",
    "human evaluation",
    "A/B study",
    "session management",
    "soul preset",
    "OCEAN personality",
    "blinded study",
    "Likert survey",
    "soul.observe",
    "Interaction",
    "admin token",
    "CSV export",
    "session TTL",
    "position bias",
    "Soul.birth"
  ],
  "categories": [
    "research",
    "evaluation",
    "web application",
    "soul-protocol"
  ],
  "source_docs": [
    "7e5f6d19c5a4fc23"
  ],
  "backlinks": null,
  "word_count": 545,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Overview

The evaluation UI (`research/eval_ui/app.py`) is the front-end for Soul Protocol's human-subjects study. Students chat with two AI agents, fill out a 6-item Likert survey after each, and record a final preference. Because agent identity (soul-enabled vs. baseline) is blinded and randomized, the study can attribute quality differences to soul features rather than order effects or participant expectations.

## Session Lifecycle

Each participant session moves through a deterministic state machine:

```
start → chat_a → survey_a → chat_b → survey_b → preference → done
```

A `session_id` is generated on `POST /api/start` and kept client-side. The in-memory `sessions` dict holds all state, which is sufficient for a lab study but would not survive a server restart.

## Soul Preset Randomization

At session start, one of five OCEAN personality presets is chosen at random:

- **warm_companion** (Sage) — high agreeableness/extraversion
- **curious_explorer** (Nova) — very high openness
- **steady_mentor** (Atlas) — high conscientiousness, low neuroticism
- **playful_creative** (Pixel) — high openness/extraversion
- **thoughtful_analyst** (Cipher) — high conscientiousness, low extraversion

Agent order (`["soul", "baseline"]` or reversed) is also randomized per session so position bias cannot inflate soul scores across participants.

## Message Handling and Soul Observation

On `POST /api/message`, the server checks which phase is active (chat_a or chat_b), looks up whether that slot maps to the soul or baseline condition, and routes accordingly. After each soul response, `soul.observe()` is called so the soul builds memory across the conversation:

```python
await soul.observe(
    Interaction(
        user_input=req.message,
        agent_output=response,
        channel="eval_ui",
    )
)
```

Observation failures are caught and logged as warnings rather than hard errors — a deliberate defensive choice. If the soul's memory pipeline throws, the evaluation continues rather than crashing mid-session.

## Survey and Result Persistence

The 6-question survey includes a reverse-coded item (q6: "responses felt generic and repetitive") to detect careless responding. Final submissions capture free-text feedback and a forced-choice A/B preference. Completed sessions are serialized to JSON in `research/results/human_eval/` via `_save_session()`. This write-on-completion pattern means partial sessions generate no files, keeping the results directory clean.

## Admin Endpoints

Two token-gated admin endpoints exist:

- `GET /api/results` — returns all completed results as JSON
- `GET /api/results/csv` — streams a CSV with per-survey-item columns plus derived `preferred_condition` (maps the participant's A/B preference back to `soul` or `baseline`)

The admin token is read from `EVAL_ADMIN_TOKEN` with no hardcoded default — the server raises `RuntimeError` at startup if the variable is missing. This prevents accidentally running an unprotected results endpoint.

## Session TTL and Cleanup

A background coroutine (`_session_cleanup_loop`) removes sessions older than 30 minutes every 5 minutes. This prevents memory growth over a full study day without requiring a persistent store.

## Startup Validation

On boot, the app validates `ANTHROPIC_API_KEY` presence and enforces `EVAL_ADMIN_TOKEN`. Both checks fail fast to surface misconfigurations before any participant traffic arrives.

## Known Gaps

- **In-memory sessions** are lost on restart. A crash mid-study would drop all in-progress sessions.
- **No authentication on participant routes** — any caller who knows a `session_id` can POST messages or surveys. Fine for a controlled lab setting, not suitable for open deployment.
- Session cleanup runs every 5 minutes, so a session can linger up to 35 minutes after expiry before being evicted.
- Max turns is hardcoded at 5 per agent; there is no per-study configuration.