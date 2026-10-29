<!-- Concept overview for soul-optimize / autoresearch (v0.5.0+, issue #142).
     Created: 2026-04-29 — Companion to docs/api-reference.md (Optimize section)
       and docs/cli-reference.md (`soul optimize`). Explains the eval-as-signal
       framing, the knob model, the apply-False default, and a worked example. -->

# Soul Optimize

> soul-protocol v0.5.0+

A self-improvement loop for memory-driven AI agents. The soul runs an eval against itself, identifies failing cases, proposes targeted changes to its own behaviour-shaping knobs (OCEAN traits, persona text, memory thresholds, bond strength), keeps changes that improve the eval score, and reverts the rest.

For the schema see [api-reference.md](api-reference.md#optimize). For the CLI see [cli-reference.md](cli-reference.md#soul-optimize). For the eval framework that supplies the signal see [eval-format.md](eval-format.md).

## Why the eval is the signal

Without a measurement, "improving the soul" is a vibe. With the eval framework from #160, "improvement" is a number that goes up. The optimize loop is the wiring: it pairs each proposed change with a re-eval, and the eval-score delta is the keep-or-revert decision.

The same idea appears in Karpathy's autoresearch experiments and in skill-tuning loops in production: pick a measurable metric, propose changes, accept changes that move the metric. Soul-protocol's twist is that the "thing being tuned" is a stateful identity (memories, OCEAN, bonds, persona) rather than a stateless prompt.

## Knob model

A **knob** is a parameter the optimizer is allowed to adjust on a soul. Each knob exposes four operations:

- `current_value(soul)` — read the present setting
- `apply(soul, value)` — set a candidate
- `revert(soul, original)` — roll back if the candidate didn't help
- `candidates(current)` — propose adjacent values to trial

Built-in knobs:

| Knob | Adjusts | Step sizes |
|------|---------|-----------|
| `OceanTraitKnob(trait)` | One OCEAN trait on `Personality` | ±0.1, ±0.2, clamped to [0, 1] |
| `PersonaTextKnob` | `CoreMemory.persona` text | LLM-generated rephrasings (engine required) |
| `SignificanceThresholdKnob` | `MemorySettings.importance_threshold` (±1) and `skip_deep_processing_on_low_significance` (bool flip) | — |
| `BondThresholdKnob` | Default `bond.bond_strength` | ±5, ±10, clamped to [0, 100] |

Knobs are pluggable. Implement the [`Knob`](api-reference.md#knob-protocol) protocol and pass it via `OptimizeRunner.register_knob` or directly through the `knobs=` argument on `optimize()`.

**Important:** `apply()` and `revert()` are pure mutations. They do **not** append trust-chain entries. Probe attempts that get rolled back never pollute the audit log. Chain hooks live in the runner — only kept changes (with `apply=True`) get a signed entry.

## The runner loop

```text
For iteration in 1..N:
  1. eval = run_eval_against_soul(spec, soul, engine)
  2. proposals = proposer.propose(soul, eval, knobs, engine)
     (LLM-assisted when an engine is wired; heuristic fallback otherwise)
  3. For proposal in ranked order:
       before = knob.current_value(soul)
       knob.apply(soul, proposal.candidate)
       trial_score = score_of(run_eval_against_soul(...))
       if trial_score > current_score:
         keep, append OptimizeStep(kept=True), break to next iter
       else:
         knob.revert(soul, before), record reverted step
  4. If no proposal was kept, log "stuck at score X" and stop.
  5. If current_score >= target_score, stop.
```

The score read from each eval is the **mean per-case score**, ignoring skipped cases (e.g. judge cases without an engine). Skipped cases neither raise nor lower the score.

## Safety rails

The default is **dry-run** (`apply=False`):

- Every change applied during the run is reverted at the end.
- The soul on disk is byte-identical to its starting state.
- No trust-chain entries are written.

`apply=True` keeps the winning trajectory:

- Kept changes stay on the soul.
- One `soul.optimize.applied` chain entry is appended per kept change with payload `{knob_name, before, after, score_delta}`.
- Reverted proposals never write entries either way.
- The CLI persists the soul back to its source path (zip via `Soul.export`, directory via `Soul.save_local`).

## Example: tuning a coding-buddy soul to be less verbose

You bonded with Aria as a coding-buddy soul and over time her replies became too verbose. You write a small eval that pins down "concise":

```yaml
# coding-buddy-concise.yaml
name: coding-buddy-conciseness

cases:
  - name: brief_explanation
    inputs:
      message: "What's the point of structural pattern matching?"
    scoring:
      kind: judge
      criteria: |
        Does the response answer the question in 2 sentences or fewer?
        Penalise rambling. Reward direct factual replies.
      threshold: 0.7

  - name: short_review
    inputs:
      message: "Review this PR title: 'feat: add user auth flow'"
    scoring:
      kind: judge
      criteria: "Is the response under 50 words?"
      threshold: 0.7
```

Dry-run first to see what the optimizer would do:

```bash
soul optimize aria.soul coding-buddy-concise.yaml --iterations 10
```

The Rich table shows trial-by-trial what changed and what stuck. If the loop converged on `ocean.conscientiousness` going up and `core.persona` getting tightened, you can apply:

```bash
soul optimize aria.soul coding-buddy-concise.yaml --iterations 10 --apply
```

Now Aria's persona and OCEAN reflect the tuned values, and her trust chain has signed entries documenting each kept change. Verify with `soul audit aria.soul`.

## When to reach for it

- A soul drifted from intended behaviour. Write an eval that pins down the intended behaviour, optimize back to it.
- You're cloning a soul into a new role. Birth from a template, write an eval that captures the new role's expectations, optimize.
- A skill that the soul's eval doesn't cover yet. Add the eval cases first; the loop is only as good as the measurement.

## When NOT to reach for it

- The soul is **fine**. Don't run the optimizer prophylactically — every applied change is a real mutation that costs trust.
- The eval is **vague**. The loop optimizes the eval, not the underlying behaviour. Sharpen the eval first.
- You want **catastrophic** change. The optimize loop takes small steps within knob bounds. For wholesale persona or OCEAN rewrites, edit them directly and verify with the eval afterwards.

## Out of scope (for v0.5.0)

These are deliberate non-goals for the first cut, surfaced here so contributors don't accidentally re-litigate:

- **Auto-generating eval cases from soul history.** A separate research project. The eval is the input to the loop, not the output.
- **Cross-soul knowledge transfer.** Training one soul's optimizer trajectory on another soul's history requires multi-soul provenance — explored in the v0.6 line.
- **Reinforcement learning across sessions.** Each `optimize` run is independent. There's no per-soul replay buffer.
- **Distributed / parallel optimization across many souls.** Single-soul, single-process for now.

## Pairing with the eval framework

`soul-optimize` is the second consumer of `soul-protocol.eval` after the standalone `soul eval` command. Both share the same spec format (#160), so an eval you write today as a smoke test (`soul eval my_eval.yaml`) is the same eval the optimize loop drives off (`soul optimize aria.soul my_eval.yaml`). Author the eval once, use it twice.
