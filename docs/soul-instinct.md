<!-- Covers: Soul Instinct decision layer — what it is, the Decider protocol, the
     DeciderChain fallback, built-in deciders (heuristic, local NLI, LLM),
     contradiction rule merging,
     uncertain-memory markers, review_instincts() and dream() review, per-soul
     calibration persisted in the .soul file, personality modulation, settings,
     MCP tools, privacy notes, compatibility, and limitations.
     Created: feat/soul-instinct
     Updated: feat/soul-instinct (#322 review) — Contradiction deciders add to the
       rules instead of replacing them; original_confidence restore on review;
       older-version compatibility note; JevDecider moved to its own PR. -->

# Soul Instinct

Soul Instinct is a fast, pluggable decision layer for the memory pipeline. Every time a soul observes a conversation turn it makes four small decisions:

| Decision | Question | Verdict |
|---|---|---|
| `significance` | Is this worth storing as an episodic memory? | per-dimension scores + yes/no |
| `sentiment` | What is the emotional tone? | `SomaticMarker` (valence, arousal, label) |
| `contradiction` | Which existing facts does this contradict? | list of findings |
| `dedup` | Is this fact new, a duplicate, or an update? | `CREATE` / `SKIP` / `MERGE` |

Before Soul Instinct these were answered by word lists and regexes (or by parsing free-text LLM output). Now every decision goes through a **`DeciderChain`**: model-backed **deciders** answer first, and an answer is only used when the decider is confident. When nobody is confident, the soul's original path decides — so a soul with no deciders behaves exactly as before.

```
observe("I'm vegetarian now")
   │
   ├─ decider 1 (e.g. local NLI model) ── confident? ──▶ use it
   ├─ decider 2 (e.g. an LLM)         ── confident? ──▶ use it
   └─ original path (LLM engine or heuristics) ───────▶ always answers
```

Rule-based contradiction checks miss paraphrases: "User loves steak" vs "I'm vegetarian now" share no keywords, so the heuristics keep both facts as true. A model decider catches it.

### Contradiction: deciders add, they don't replace

For `significance`, `sentiment` and `dedup`, an accepted decider answer **replaces** the original path for that decision. `contradiction` is different: when a decider's contradiction answer is accepted, the chain also runs the rule-based heuristics (negation and verb-fact rules, which cost almost nothing) and **merges** their findings in. A decider can catch contradictions the rules miss, but a confident "nothing contradicts" can't switch the rules off. For example, after "User loves steak", the message "User dislikes steak" still supersedes the old fact even if the model was sure nothing was related.

- Only the cheap heuristics are merged. If the soul has an LLM engine, the LLM contradiction check is **not** run on top of an accepted decider.
- When the rules add something the model rejected, the chain records a `merged` attempt on `Decision.attempts`, and the old memory is marked **uncertain** (`model_verdict: false, applied: true`) so a review can check who was right. See below.
- To let an accepted decider fully replace the rules, build the chain with `DeciderChain(..., merge_contradiction_rules=False)`.

## Quick start

Try it on any soul from the terminal — read-only, nothing is saved:

```bash
pip install 'soul-protocol[embeddings-st]'
soul instinct shekhar.soul                       # interactive: type messages
soul instinct shekhar.soul -m "I hate dosa now"  # one-off
soul instinct                                    # uses the soul in the current folder
```

In code:

```python
from soul_protocol import Soul
from soul_protocol.runtime.decide import NLIContradictionDecider

soul = await Soul.birth("Aria", deciders=[NLIContradictionDecider()])
# or attach later / after awaken:
soul.use_deciders([NLIContradictionDecider()])
soul = await Soul.awaken("aria.soul", deciders=[NLIContradictionDecider()])
```

Ask the instinct directly (read-only, nothing is stored):

```python
decision = await soul.decide("contradiction", "I'm vegetarian now")
decision.value.findings   # [ContradictionFinding(old_memory_id=..., confidence=0.97)]
decision.source           # "nli"
decision.confidence       # 0.97
decision.attempts         # what every consulted decider said
```

## Built-in deciders

| Decider | Answers | Runs | Install |
|---|---|---|---|
| `HeuristicDecider` | all four | locally, rules | built in |
| `NLIContradictionDecider` | contradiction | locally, small NLI cross-encoder (`cross-encoder/nli-deberta-v3-xsmall`), no data leaves the machine | `pip install 'soul-protocol[embeddings-st]'` |
| `EngineDecider` | contradiction, significance | any `CognitiveEngine` (Claude, GPT, Ollama, MCP sampling) | engine extra |

`CognitiveDecider` wraps the soul's original path (LLM engine → DSPy gate → heuristics) and is always the chain's final fallback inside `observe()`.

### How the local NLI decider avoids false alarms

Off-the-shelf NLI models are trained on SNLI-style data, where both sentences describe the *same scene* — so they label merely *different* facts as contradictions ("User likes cricket" vs "User loves steak" scores 0.99). `NLIContradictionDecider` adds three guards:

1. **Relatedness gate** — a memory is only judged if its embedding cosine similarity to the new content is at least `relatedness_threshold` (default `0.5`, using `all-MiniLM-L6-v2`). Unrelated memories are confidently "no contradiction".
2. **Both directions** — some contradictions only register one way (Delhi → Mumbai: 0.36 forward, 0.99 backward), so the higher score is used.
3. **First-person and name normalization** — "I'm vegetarian" is compared as "User is vegetarian", and names listed in `instinct.settings.user_aliases` ("Shekhar loves dosa") become "User" too.

On a small hand-labelled set (13 cases including paraphrases, first-person phrasing and unrelated-fact traps) the decider gets 13/13 with these guards; without the gate it flagged nearly every unrelated pair. That set also informed the default threshold, so treat it as a sanity check, not a benchmark. Run it yourself:

```bash
pip install 'soul-protocol[embeddings-st]'
SOUL_LIVE_MODELS=1 pytest tests/test_decide/test_nli_live.py
```

Latency on a laptop CPU is ~200 ms per decision after a one-time model load (~25 s on first use).

### Writing your own decider

Anything with a `name`, `supports(kind)` and `async decide(request)` is a decider:

```python
from soul_protocol.runtime.decide import (
    ContradictionRequest, ContradictionVerdict, Decision, DecisionKind,
)

class MyDecider:
    name = "my-model"

    def supports(self, kind: DecisionKind) -> bool:
        return kind == DecisionKind.CONTRADICTION

    async def decide(self, request):
        if not isinstance(request, ContradictionRequest):
            return None                      # abstain
        ...
        return Decision(
            kind=DecisionKind.CONTRADICTION,
            value=ContradictionVerdict(findings=[...]),
            confidence=0.91,                 # None = "I can't say how sure I am"
            source=self.name,
        )
```

A decider may return `None` to abstain or raise — the chain logs it, records the attempt, and moves on. Answers with `confidence=None` are never accepted from a non-fallback decider.

## Uncertain memories and review

When a model decider was consulted but **unsure**, the soul still makes a decision (via the fallback), but it remembers that it wasn't sure:

- the affected memory gets `metadata["instinct"]` with the unsure decider's name, confidence and verdict,
- `MemoryEntry.confidence` is lowered to that confidence, and the value it had before is saved as `original_confidence` in the marker,
- `soul.uncertain_memories()` lists everything waiting for review.

A memory is also marked uncertain when a confident decider said "no contradiction" but the merged rules superseded it anyway.

```python
report = await soul.review_instincts()          # uses the soul's LLM engine
report.reviewed, report.corrected, report.restored, report.superseded
```

The reviewer (by default an `EngineDecider` over the soul's LLM engine; pass `reviewer=` to choose another) re-asks each question:

- **contradiction** — if the reviewer says the old memory *is* contradicted, it is superseded; if it was superseded but the reviewer disagrees, it is **restored**.
- **significance** — the verdict is recorded; memories are never deleted by a review.

Once reviewed, the memory gets its `original_confidence` back. The reviewer's own confidence is stored in `metadata["instinct"]["reviewed"]` and is not written to the memory: it says how sure the reviewer is, not how true the memory is.

`soul.dream()` runs this review automatically when there are uncertain memories and an LLM engine is available (`dream(review_instincts=False)` or `instinct.settings.review_during_dream = False` to opt out; never on `dry_run`). Over MCP, the host LLM is used via sampling — no extra API key.

## Learning: per-soul calibration

Every review is a lesson. Whether the unsure decider turned out right is recorded in `soul.instinct.calibration`, bucketed into ten confidence bands per decider and decision kind. The chain then gates on the **calibrated** confidence:

- a decider that is often wrong at 0.9 gets its 0.9 answers discounted (they fall back more);
- a decider that is usually right at 0.55 gets trusted at 0.55.

Sparse bands are smoothed toward the raw confidence, so one review can't swing it. Calibration is saved inside the `.soul` file (`SoulConfig.instinct`), so the soul's learned judgment travels with it. Deciders themselves are runtime objects and are not saved.

```python
soul.instinct.calibration.accuracy("nli", "contradiction")   # e.g. 0.92, or None
```

## Settings

`soul.instinct.settings` (persisted):

| Setting | Default | Meaning |
|---|---|---|
| `min_confidence` | `0.7` | Calibrated confidence a decider needs for its answer to be used |
| `review_during_dream` | `True` | Run `review_instincts()` inside `dream()` |
| `personality_modulation` | `False` | Let OCEAN traits shape the thresholds (below) |
| `user_aliases` | `[]` | Names that mean "the user" in memories, e.g. `["Shekhar"]` when facts read "Shekhar loves dosa". Without it, "I hate dosa" and "Shekhar loves dosa" look like different people to the local model. |

### Personality modulation (opt-in)

- **Openness** lowers the significance bar — a curious soul remembers more (±0.1).
- **Conscientiousness** raises `min_confidence` — a careful soul double-checks more (±0.1).

The default personality (all traits 0.5) changes nothing.

## MCP tools

- `soul_decide(kind, text)` — read-only typed decision from the soul's instinct.
- `soul_instinct_review(include_confident=False)` — review uncertain decisions with the host LLM.

See [MCP Server](mcp-server.md#soul_decide).

## Privacy

`NLIContradictionDecider` and `HeuristicDecider` run entirely on the user's machine. `EngineDecider` sends memory text to its LLM provider — attach it only with the user's consent.

The `soul instinct` CLI downloads the two local models (about 380 MB) on first run and says so before it starts; later runs work offline.

## Compatibility

The `instinct` block (settings and learned calibration) is a new optional field on `SoulConfig`. Older `.soul` files load with defaults. Going the other way, an **older soul-protocol** loads a newer soul fine but ignores the `instinct` block, and if it saves the soul again, the block is dropped: the settings and the calibration it learned are lost. Memory text embedded in `EngineDecider` prompts is sanitized and marked as data.

## Limitations

- Decisions the fallback made *without* storing anything (e.g. an unsure "not significant" turn that was then dropped) leave nothing to review.
- Calibration only learns from reviewed decisions; by default those are the unsure ones. Use `review_instincts(include_confident=True)` occasionally to calibrate the high-confidence bands too.
- Model deciders compare against at most 10 (`EngineDecider`) or 20 (`NLIContradictionDecider`) related live memories per decision.
- `metadata["instinct"]` holds one marker per memory. If a second statement questions the same fact before review, only the latest marker is kept (its saved `original_confidence` carries over).
- Model judgments vary; measure on your own data (see `research/eval`) before raising trust.
