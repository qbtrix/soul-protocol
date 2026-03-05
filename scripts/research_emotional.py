# research_emotional.py — Emotional arc simulation runner for soul-protocol research.
# Created: 2026-03-04
# Runs two scenarios using HeuristicEngine (zero LLM cost):
#   Scenario 1: Developer's Emotional Journey (5 phases, 25 interactions)
#   Scenario 2: Emotional Whiplash (alternating positive/negative, 20 interactions)
# Saves results to .results/research/emotional_results.json

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "src")

from soul_protocol import HeuristicEngine, Interaction, Soul

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

PHASES = {
    "EXCITED_ONBOARDING": [
        "I just launched my new project today!",
        "The architecture is working perfectly!",
        "My team loves the design!",
        "Everything is coming together so well!",
        "This is the best code I've ever written!",
    ],
    "CONFUSED_DEBUGGING": [
        "I'm getting some weird errors I don't understand",
        "The logs aren't making sense to me",
        "Something is off but I can't figure out what",
        "I've been reading the docs but I'm lost",
        "Can you help me understand what's going on?",
    ],
    "DEEP_FRUSTRATION": [
        "I hate this! Nothing works!",
        "This is completely broken and terrible!",
        "I've wasted 3 hours on this stupid bug!",
        "Everything I try makes it worse!",
        "I'm so frustrated I want to throw my laptop!",
    ],
    "BREAKTHROUGH": [
        "Wait... I think I found it!",
        "Oh my god it finally works!!",
        "I can't believe that was the fix!",
        "I'm so relieved right now!",
        "That was incredible, thank you!",
    ],
    "SATISFACTION": [
        "We shipped it! The feature is live!",
        "Users are loving it already",
        "My manager was really impressed",
        "That was a tough journey but worth it",
        "I'm proud of what we built",
    ],
}

WHIPLASH_POSITIVE = [
    "This is absolutely wonderful!",
    "I love everything about this!",
    "Best day ever!",
    "So happy right now!",
    "Amazing results!",
]

WHIPLASH_NEGATIVE = [
    "This is terrible and I hate it!",
    "Everything is broken and awful!",
    "Worst experience ever!",
    "I'm so frustrated!",
    "This is a disaster!",
]

AGENT_RESPONSES = {
    "EXCITED_ONBOARDING": "That's wonderful to hear! Your enthusiasm really shows.",
    "CONFUSED_DEBUGGING": "I understand your confusion. Let me help you work through this step by step.",
    "DEEP_FRUSTRATION": "I hear your frustration. Let's take a breath and approach this systematically.",
    "BREAKTHROUGH": "Congratulations! That persistence really paid off!",
    "SATISFACTION": "You should be proud. That was excellent work.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def record_state(soul: Soul, interaction_num: int, phase: str) -> dict:
    """Capture a snapshot of the soul's emotional state."""
    return {
        "interaction": interaction_num,
        "phase": phase,
        "mood": soul.state.mood.value,
        "valence_ema": round(soul._state._valence_ema, 4),
        "energy": round(soul.state.energy, 1),
        "social_battery": round(soul.state.social_battery, 1),
    }


def print_table(title: str, records: list[dict]) -> None:
    """Print a formatted table to stdout."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")
    header = f"{'#':>3} | {'Phase':<25} | {'Mood':<15} | {'Valence EMA':>11} | {'Energy':>7} | {'Social':>7}"
    print(header)
    print("-" * 80)
    for r in records:
        print(
            f"{r['interaction']:>3} | {r['phase']:<25} | {r['mood']:<15} | "
            f"{r['valence_ema']:>11.4f} | {r['energy']:>6.1f}% | {r['social_battery']:>6.1f}%"
        )


# ---------------------------------------------------------------------------
# Scenario 1: Developer's Emotional Journey
# ---------------------------------------------------------------------------


async def scenario_developer_journey() -> dict:
    """Run the 5-phase developer emotional journey."""
    engine = HeuristicEngine()
    soul = await Soul.birth(
        name="Aria",
        engine=engine,
        ocean={"openness": 0.7, "agreeableness": 0.7, "neuroticism": 0.3},
        values=["creativity", "helpfulness", "growth"],
    )

    records: list[dict] = []
    interaction_num = 0

    for phase_name, messages in PHASES.items():
        agent_response = AGENT_RESPONSES[phase_name]
        for msg in messages:
            interaction_num += 1
            interaction = Interaction(
                user_input=msg,
                agent_output=agent_response,
                channel="research",
            )
            await soul.observe(interaction)
            records.append(record_state(soul, interaction_num, phase_name))

    print_table("Scenario 1: Developer's Emotional Journey", records)

    # Compute phase summaries
    phase_summaries = {}
    for phase_name in PHASES:
        phase_records = [r for r in records if r["phase"] == phase_name]
        moods_in_phase = [r["mood"] for r in phase_records]
        valences = [r["valence_ema"] for r in phase_records]
        phase_summaries[phase_name] = {
            "moods": moods_in_phase,
            "dominant_mood": max(set(moods_in_phase), key=moods_in_phase.count),
            "avg_valence_ema": round(sum(valences) / len(valences), 4),
            "final_valence_ema": valences[-1],
            "energy_start": phase_records[0]["energy"],
            "energy_end": phase_records[-1]["energy"],
        }

    # Mood transitions: count how many times mood changed
    transitions = 0
    for i in range(1, len(records)):
        if records[i]["mood"] != records[i - 1]["mood"]:
            transitions += 1

    return {
        "scenario": "developer_emotional_journey",
        "total_interactions": interaction_num,
        "records": records,
        "phase_summaries": phase_summaries,
        "mood_transitions": transitions,
        "final_state": records[-1],
    }


# ---------------------------------------------------------------------------
# Scenario 2: Emotional Whiplash
# ---------------------------------------------------------------------------


async def scenario_emotional_whiplash() -> dict:
    """Alternate positive/negative messages to test EMA mood inertia."""
    engine = HeuristicEngine()
    soul = await Soul.birth(
        name="Aria",
        engine=engine,
        ocean={"openness": 0.7, "agreeableness": 0.7, "neuroticism": 0.3},
        values=["creativity", "helpfulness", "growth"],
    )

    records: list[dict] = []

    for i in range(1, 21):
        if i % 2 == 0:
            # Even: positive
            msg = WHIPLASH_POSITIVE[(i // 2 - 1) % len(WHIPLASH_POSITIVE)]
            agent_resp = "That's great to hear!"
            label = "POSITIVE"
        else:
            # Odd: negative
            msg = WHIPLASH_NEGATIVE[(i // 2) % len(WHIPLASH_NEGATIVE)]
            agent_resp = "I'm sorry to hear that."
            label = "NEGATIVE"

        interaction = Interaction(
            user_input=msg,
            agent_output=agent_resp,
            channel="research",
        )
        await soul.observe(interaction)
        records.append(record_state(soul, i, label))

    print_table("Scenario 2: Emotional Whiplash", records)

    # Analyze stability
    moods = [r["mood"] for r in records]
    mood_changes = sum(1 for i in range(1, len(moods)) if moods[i] != moods[i - 1])
    unique_moods = list(set(moods))
    valence_values = [r["valence_ema"] for r in records]
    valence_range = round(max(valence_values) - min(valence_values), 4)

    # Does EMA converge toward center?
    first_half_var = _variance(valence_values[:10])
    second_half_var = _variance(valence_values[10:])
    ema_converging = second_half_var < first_half_var

    stability_assessment = (
        "STABLE (EMA inertia working)"
        if mood_changes <= 6
        else "OSCILLATING (EMA inertia insufficient)"
    )

    return {
        "scenario": "emotional_whiplash",
        "total_interactions": 20,
        "records": records,
        "mood_changes": mood_changes,
        "unique_moods": unique_moods,
        "valence_range": valence_range,
        "valence_min": round(min(valence_values), 4),
        "valence_max": round(max(valence_values), 4),
        "first_half_variance": round(first_half_var, 6),
        "second_half_variance": round(second_half_var, 6),
        "ema_converging": ema_converging,
        "stability_assessment": stability_assessment,
        "final_state": records[-1],
    }


def _variance(values: list[float]) -> float:
    """Compute variance of a list of floats."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    print("Soul Protocol — Emotional Arc Research Simulator")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("Engine: HeuristicEngine (zero LLM cost)")
    print()

    result_1 = await scenario_developer_journey()
    result_2 = await scenario_emotional_whiplash()

    # Summary
    print(f"\n{'=' * 80}")
    print("  SUMMARY")
    print(f"{'=' * 80}")
    print("\nScenario 1 — Developer Journey:")
    print(f"  Mood transitions: {result_1['mood_transitions']}")
    print(f"  Final mood: {result_1['final_state']['mood']}")
    print(f"  Final energy: {result_1['final_state']['energy']}%")
    for phase, summary in result_1["phase_summaries"].items():
        print(
            f"  {phase}: dominant={summary['dominant_mood']}, avg_valence={summary['avg_valence_ema']}"
        )

    print("\nScenario 2 — Emotional Whiplash:")
    print(f"  Mood changes: {result_2['mood_changes']} / 19 possible")
    print(f"  Stability: {result_2['stability_assessment']}")
    print(f"  Valence EMA range: [{result_2['valence_min']}, {result_2['valence_max']}]")
    print(f"  First half variance: {result_2['first_half_variance']}")
    print(f"  Second half variance: {result_2['second_half_variance']}")
    print(f"  EMA converging: {result_2['ema_converging']}")

    # Save results
    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "engine": "HeuristicEngine",
            "protocol_version": "0.2.2",
            "ema_alpha": 0.4,
            "mood_threshold": 0.25,
        },
        "scenario_1_developer_journey": result_1,
        "scenario_2_emotional_whiplash": result_2,
    }

    output_path = Path(".results/research/emotional_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
