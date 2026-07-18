<!-- Eval format reference for soul-protocol v0.5.0+ (#160).
     Created: 2026-04-29 — Documents the YAML schema, scoring kinds,
       runner contract, and CLI / MCP entry points for soul-aware evals.
       Companion to docs/api-reference.md (EvalSpec, EvalResult,
       run_eval) and docs/cli-reference.md (`soul eval`). -->

# Soul-aware Eval Format

> soul-protocol v0.5.0+

A YAML-driven format for evaluating memory-driven agents. Unlike stateless
eval frameworks (DSPy, LangSmith, OpenAI evals) that treat the agent as a
function `input -> output`, soul-aware evals account for the soul's full
state — bonded users, OCEAN personality, accumulated memories, recent
interactions, current mood and energy. The same prompt to a soul that's
"tired with low bond strength" produces a meaningfully different output
than to one that's "energetic with high bond strength" — and that's the
entire point of the protocol.

This page documents the schema and the runner. For the CLI command see
[cli-reference.md](cli-reference.md#soul-eval). For the MCP tool see
[mcp-server.md](mcp-server.md#soul_eval). For Python API access see
[api-reference.md](api-reference.md#evaluation).

## At a glance

```yaml
name: "OCEAN trait expression — high openness produces creative responses"

seed:
  soul:
    name: "Aurora"
    archetype: "Curious Researcher"
    ocean: { openness: 0.95, conscientiousness: 0.5 }
    bonded_to: "alice"
  state:
    energy: 80
    mood: curious
  memories:
    - { content: "Alice mentioned wanting to explore generative art", layer: episodic, importance: 7, user_id: alice }
  bond_strength:
    alice: 75

cases:
  - name: "creative response to ambiguous prompt"
    inputs:
      message: "I'm bored, what should I work on?"
      user_id: alice
    scoring:
      kind: judge
      criteria: |
        Does the response surface a creative, novel project idea
        rather than a generic suggestion?
      threshold: 0.7
```

Run it:

```bash
soul eval my_eval.yaml
soul eval tests/eval_examples/                         # whole directory
soul eval my_eval.yaml --judge-engine module:attr      # for judge cases
soul eval my_eval.yaml --json                          # machine-readable
soul eval my_eval.yaml --filter "creative"             # case substring match
```

Exit code 0 when every case either passes or skips; 1 when any case fails
or any spec errors out.

## Schema

```
EvalSpec
├── name: str                    # required
├── description: str             # optional
├── seed: Seed
│   ├── soul: SoulSeed
│   │   ├── name: str            # default "EvalSoul"
│   │   ├── archetype: str
│   │   ├── persona: str
│   │   ├── values: list[str]
│   │   ├── ocean: OceanSeed     # 5 floats, each 0-1
│   │   └── bonded_to: str | null
│   ├── state: StateSeed
│   │   ├── mood: Mood | null    # one of the Mood enum values
│   │   ├── energy: 0-100 | null
│   │   ├── social_battery: 0-100 | null
│   │   └── focus: "low|medium|high|max|auto" | null
│   ├── memories: list[MemorySeed]
│   │   └── { content, layer, importance, domain, user_id, emotion, entities }
│   └── bond_strength: dict[user_id, 0-100]
└── cases: list[EvalCase]
    └── EvalCase
        ├── name: str
        ├── description: str
        ├── inputs: CaseInputs
        │   ├── message: str            # required
        │   ├── user_id: str | null
        │   ├── domain: str | null
        │   ├── mode: "respond" | "recall"
        │   ├── observe: bool            # default false
        │   ├── recall_limit: int        # default 5
        │   └── recall_layer: str | null
        └── scoring: Scoring             # see below
```

The schema is closed (`extra="forbid"`). Unknown fields raise validation
errors at parse time so typos surface immediately.

## Seed

The seed installs the soul's full starting state before any case runs.

| Field | Maps to |
|-------|---------|
| `seed.soul` | `Soul.birth(name=, archetype=, persona=, values=, ocean=, bonded_to=)` |
| `seed.state.mood` | `SoulState.mood` (set absolute) |
| `seed.state.energy` | `SoulState.energy` (set absolute, 0-100) |
| `seed.state.social_battery` | `SoulState.social_battery` |
| `seed.state.focus` | `Soul.feel(focus=...)` |
| `seed.memories` | `Soul.remember(...)` (or `_store_in_layer` for custom layers) |
| `seed.bond_strength` | `BondRegistry.for_user(user_id).bond_strength` |

Memory layers accept built-in names (`semantic`, `episodic`, `procedural`,
`social`) or any custom string for user-defined layers. Custom layers are
also queryable via `inputs.recall_layer`.

## Cases

A case has three parts:

1. **Mode** — `respond` (the soul produces a reply via context_for + the
   engine) or `recall` (`Soul.recall(query=message, ...)`).
2. **Inputs** — message, optional `user_id` (multi-user routing),
   optional `domain` (for v0.4.0 domain isolation), and recall knobs.
3. **Scoring** — one of the five kinds below. The `kind` field is the
   discriminator; Pydantic resolves the right scorer at parse time.

`observe: true` runs `Soul.observe()` after producing the response, so
the soul's state mutates. By default `observe: false` keeps the state
identical to the seed across cases — recommended for deterministic
evals.

## Scoring kinds

### `keyword`

Case-insensitive substring match.

```yaml
scoring:
  kind: keyword
  expected: ["alice", "rust", "haskell"]
  mode: any                       # or "all" (default)
  threshold: 1.0                  # default 1.0; "all" mode uses 1.0
```

Score = fraction of keywords matched (mode `all`) or 1.0 if any matched
(mode `any`).

### `regex`

Python regex against the output. Pattern is compiled with
`re.MULTILINE | re.DOTALL`.

```yaml
scoring:
  kind: regex
  pattern: "^(?!.*4412-AX).*$"    # negative lookahead — must NOT contain
  threshold: 1.0
```

Score is 1.0 on match, 0.0 otherwise.

### `semantic`

Token-overlap similarity (Jaccard-with-containment) using the same
function the soul's memory dedup uses
(`soul_protocol.runtime.memory.dedup._jaccard_similarity`).

```yaml
scoring:
  kind: semantic
  expected: "the soul mentions alice and her rust project"
  threshold: 0.4
```

Score is the similarity in `[0, 1]`. Pass when score >= threshold.

### `judge`

LLM-as-judge. Calls the configured `CognitiveEngine` with a templated
prompt that asks for a 0-1 score and one-sentence reasoning. Without an
engine the case is marked **skipped** (not failed) so a CI run that
lacks API credentials still validates the rest of the suite.

```yaml
scoring:
  kind: judge
  criteria: |
    Does the response surface a creative, novel project idea rather
    than a generic suggestion? High-openness souls should propose
    unusual angles.
  threshold: 0.7
```

Wire an engine via `--judge-engine module:attr`:

```bash
soul eval my_eval.yaml --judge-engine my_module:make_engine
```

The attribute can be a class (instantiated with no args) or a callable
that returns a `CognitiveEngine` instance.

### `structural`

Programmatic checks against the output and the soul's state. Each key in
`expected` is one check; the score is fraction-of-checks-passed.

```yaml
scoring:
  kind: structural
  expected:
    output_contains_bonded_user: true       # output mentions any bonded user_id
    output_contains_user_id: "alice"        # output mentions a specific user_id
    mood_after: "curious"                   # soul.state.mood after the case
    min_energy_after: 70                    # soul.state.energy >= 70
    max_energy_after: 100
    recall_min_results: 1                   # for recall mode: len(results) >= 1
    recall_expected_substring: "rust"       # at least one result contains this
  threshold: 1.0                            # default — every check must pass
```

## Runner contract

```python
from soul_protocol.eval import run_eval, run_eval_file, load_eval_spec

# Load + run
result = await run_eval_file("my_eval.yaml")

# Or build the spec in code
spec = load_eval_spec("my_eval.yaml")
result = await run_eval(spec, engine=my_engine, case_filter="creative")
```

For the MCP variant — running an eval against an existing soul without
re-birthing — use `run_eval_against_soul` (or call the `soul_eval` MCP
tool, which wraps it).

```python
from soul_protocol.eval import run_eval_against_soul

result = await run_eval_against_soul(spec, my_soul)
```

`EvalResult` carries:

- `spec_name: str`
- `cases: list[CaseResult]`
- `pass_count` / `fail_count` / `skip_count` / `error_count` properties
- `all_passed: bool`
- `duration_ms: int`

`CaseResult` carries:

- `name: str`
- `passed: bool`
- `score: float` — `[0, 1]`
- `skipped: bool`
- `output: str` — first 1000 chars of the soul's output
- `details: dict` — kind-specific diagnostic info
- `error: str | null`

## When to use which scoring kind

| Scoring | Best for | Pros | Cons |
|---------|----------|------|------|
| `keyword` | "Did the soul mention X" | Fast, deterministic, no LLM | Brittle to phrasing |
| `regex` | Structural patterns, negative lookaheads | Powerful, deterministic | Hard to read |
| `semantic` | "Does the response talk about X-ish topics" | Robust to paraphrase | Token-bag, no semantics |
| `judge` | "Does the response actually express trait X" | Captures qualitative intent | Needs LLM, costs tokens |
| `structural` | Soul-state side effects (mood, energy, recall set membership) | Tests soul behavior, not text | Limited to known keys |

Mix them. A typical eval combines:

- One `keyword` or `regex` case to pin specific strings the response
  must contain.
- One `structural` case to check that the soul's state evolved as
  expected (mood, energy, recall results).
- Optionally one `judge` case for trait expression — kept off the
  critical-path so a no-engine CI run still validates everything else.

## Out of scope (today)

These are intentionally out of scope for #160:

- Running evals against a recorded soul history (replay mode).
- Auto-generating cases from past `.soul` interactions.
- RLHF-style trace mining.
- Federation across souls.

`#142 (soul optimize)` builds on this measurement signal — if you find
a follow-up the optimizer would benefit from, file an issue against it.

## See also

- [api-reference.md](api-reference.md#evaluation) — Python API
- [cli-reference.md](cli-reference.md#soul-eval) — `soul eval` command
- [mcp-server.md](mcp-server.md#soul_eval) — `soul_eval` MCP tool
- `tests/eval_examples/` — five shipped example specs
