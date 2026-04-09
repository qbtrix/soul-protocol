# run_tier2.py — Tier 2 validation: 100 agents with real Haiku LLM calls.
# Compares heuristic vs LLM-backed cognitive processing.
# Usage: python -m research.run_tier2 [--agents 100] [--quick]

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from soul_protocol import Soul
from soul_protocol.runtime.types import Interaction

from .agents import generate_agents, generate_users
from .haiku_engine import HaikuCognitiveEngine
from .metrics import (
    AgentRunMetrics,
    BondMetrics,
    EmotionalMetrics,
    MemoryEfficiencyMetrics,
    PersonalityMetrics,
    RecallMetrics,
    SkillMetrics,
)
from .scenarios import generate_scenarios


async def run_agent_with_engine(
    agent_profile,
    user_profile,
    use_case: str,
    engine: HaikuCognitiveEngine | None,
    seed: int,
) -> AgentRunMetrics:
    """Run one agent through scenarios with optional LLM engine."""
    condition_name = "haiku_llm" if engine else "heuristic"

    soul = await Soul.birth(
        name=agent_profile.name,
        archetype=agent_profile.archetype,
        values=agent_profile.values,
        ocean=agent_profile.ocean,
        communication=agent_profile.communication,
        persona=agent_profile.persona,
        engine=engine,
    )

    scenarios = generate_scenarios(user_profile, use_case, seed=seed)

    recall_metrics = RecallMetrics()
    emotional_metrics = EmotionalMetrics()
    efficiency_metrics = MemoryEfficiencyMetrics()
    bond_metrics = BondMetrics()
    skill_metrics = SkillMetrics()
    personality_metrics = PersonalityMetrics()

    interaction_count = 0

    for scenario in scenarios:
        for turn in scenario.turns:
            interaction = Interaction(
                user_input=turn.user_input,
                agent_output=turn.agent_output,
            )
            await soul.observe(interaction)
            interaction_count += 1

            efficiency_metrics.memory_growth_rate.append((interaction_count, soul.memory_count))
            bond_metrics.strength_trajectory.append(soul.bond.bond_strength)

        # Recall evaluation
        for query, expected_fact in scenario.recall_queries:
            recalled = await soul.recall(query, limit=10)
            recalled_contents = [m.content.lower() for m in recalled]
            expected_lower = expected_fact.lower()

            hit = any(expected_lower in c for c in recalled_contents)
            recall_metrics.hit_at_k.append(hit)

            if recalled_contents:
                relevant = sum(1 for c in recalled_contents if expected_lower in c)
                recall_metrics.precision_scores.append(relevant / len(recalled_contents))
            else:
                recall_metrics.precision_scores.append(0.0)

            recall_metrics.recall_scores.append(1.0 if hit else 0.0)

    skill_metrics.skills_discovered = len(soul.skills.skills)

    for trait in ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"):
        personality_metrics.trait_drift[trait] = [0.0]

    return AgentRunMetrics(
        agent_id=agent_profile.agent_id,
        condition=condition_name,
        use_case=use_case,
        recall=recall_metrics,
        emotional=emotional_metrics,
        personality=personality_metrics,
        efficiency=efficiency_metrics,
        bond=bond_metrics,
        skills=skill_metrics,
    )


async def run_tier2(
    num_agents: int = 100, use_case: str = "companion", seed: int = 42, batch_size: int = 10
):
    """Run Tier 2 comparison: heuristic vs Haiku-backed agents."""

    print("=" * 60)
    print("  Soul Protocol — Tier 2: LLM Validation (Haiku)")
    print("=" * 60)

    agents = generate_agents(num_agents, seed=seed)
    users = generate_users(num_agents, seed=seed, use_case=use_case)

    engine = HaikuCognitiveEngine(max_concurrent=20)

    all_metrics: list[AgentRunMetrics] = []
    errors: list[str] = []

    # --- Run heuristic baseline ---
    print(f"\n  Phase 1: Heuristic baseline ({num_agents} agents)...")
    t0 = time.monotonic()

    for batch_start in range(0, num_agents, batch_size):
        batch_end = min(batch_start + batch_size, num_agents)
        coros = [
            run_agent_with_engine(agents[i], users[i], use_case, None, seed)
            for i in range(batch_start, batch_end)
        ]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for r in results:
            if isinstance(r, AgentRunMetrics):
                all_metrics.append(r)
            else:
                errors.append(str(r))
        done = min(batch_end, num_agents)
        print(f"    [{done}/{num_agents}] heuristic")

    heuristic_time = time.monotonic() - t0
    print(f"  Heuristic done in {heuristic_time:.1f}s")

    # --- Run Haiku LLM ---
    print(f"\n  Phase 2: Haiku LLM ({num_agents} agents)...")
    t1 = time.monotonic()

    for batch_start in range(0, num_agents, batch_size):
        batch_end = min(batch_start + batch_size, num_agents)
        coros = [
            run_agent_with_engine(agents[i], users[i], use_case, engine, seed)
            for i in range(batch_start, batch_end)
        ]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for r in results:
            if isinstance(r, AgentRunMetrics):
                all_metrics.append(r)
            else:
                errors.append(str(r))
        done = min(batch_end, num_agents)
        print(f"    [{done}/{num_agents}] haiku  |  {engine.usage.summary()}")

    haiku_time = time.monotonic() - t1
    print(f"  Haiku done in {haiku_time:.1f}s")

    # --- Analysis ---
    print("\n  Analyzing results...")
    rows = [m.to_row() for m in all_metrics]

    # Simple comparison
    heuristic_rows = [r for r in rows if r["condition"] == "heuristic"]
    haiku_rows = [r for r in rows if r["condition"] == "haiku_llm"]

    def avg(data, key):
        vals = [r[key] for r in data if key in r]
        return sum(vals) / len(vals) if vals else 0.0

    print("\n" + "=" * 60)
    print("  RESULTS: Heuristic vs Haiku LLM")
    print("=" * 60)
    print(f"  {'Metric':<25} {'Heuristic':>12} {'Haiku LLM':>12} {'Delta':>12}")
    print("  " + "-" * 55)

    for metric in [
        "recall_hit_rate",
        "recall_precision",
        "recall_recall",
        "emotion_accuracy",
        "bond_final",
        "skills_discovered",
        "memory_count",
    ]:
        h_val = avg(heuristic_rows, metric)
        l_val = avg(haiku_rows, metric)
        delta = l_val - h_val
        delta_str = f"{delta:+.3f}" if abs(delta) > 0.001 else "0.000"
        print(f"  {metric:<25} {h_val:>12.3f} {l_val:>12.3f} {delta_str:>12}")

    print("  " + "-" * 55)
    print(f"\n  Haiku API usage: {engine.usage.summary()}")
    print(f"  Errors: {len(errors)}")

    # Save results
    output_dir = Path("research/results/tier2")
    output_dir.mkdir(parents=True, exist_ok=True)

    results_file = output_dir / "tier2_results.json"
    results_file.write_text(
        json.dumps(
            {
                "num_agents": num_agents,
                "use_case": use_case,
                "heuristic_time_s": heuristic_time,
                "haiku_time_s": haiku_time,
                "haiku_api_calls": engine.usage.calls,
                "haiku_input_tokens": engine.usage.input_tokens,
                "haiku_output_tokens": engine.usage.output_tokens,
                "haiku_estimated_cost_usd": engine.usage.estimated_cost_usd,
                "haiku_errors": engine.usage.errors,
                "rows": rows,
                "errors": errors,
            },
            indent=2,
            default=str,
        )
    )

    print(f"\n  Results saved to: {output_dir.resolve()}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Tier 2: LLM validation with Haiku")
    parser.add_argument("--agents", type=int, default=100)
    parser.add_argument("--use-case", type=str, default="companion")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--quick", action="store_true", help="Quick mode: 5 agents")
    args = parser.parse_args()

    if args.quick:
        args.agents = 5

    asyncio.run(
        run_tier2(
            num_agents=args.agents,
            use_case=args.use_case,
            seed=args.seed,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    main()
