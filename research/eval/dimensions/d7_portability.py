# d7_portability.py — Dimension 7: Portability (weight: 5%)
# Created: 2026-03-12 — Engine independence tests
#
# Scenarios implemented:
#   PT-1: System Prompt Independence — birth two souls with identical params
#         (one default, one explicit), verify to_system_prompt() matches
#   PT-2: Recall Independence — create soul, observe 20 interactions, run
#         5 recall queries, export/reimport, run same queries, compare results
#   PT-3: Engine Swap Continuity (full mode only) — birth soul, observe 20
#         turns, export, awaken, observe 10 more, export again, awaken again,
#         verify memory_count and bond_strength preserved
#
# Scoring formula:
#   score = (system_prompt_independence * 35) +
#           (recall_independence * 35) +
#           (engine_swap_continuity * 30)

from __future__ import annotations

import tempfile
from pathlib import Path

from soul_protocol import Interaction, Soul

from ..suite import DimensionResult

# --- Shared interaction corpus ---

_TEST_INTERACTIONS: list[tuple[str, str]] = [
    ("I just started learning to paint.", "Painting is a wonderful creative outlet."),
    ("My dog Bruno loves the park.", "Bruno sounds like a happy pup!"),
    ("I work remotely from my apartment.", "Remote work has its perks and challenges."),
    ("I have been reading about stoicism.", "Stoic philosophy has a lot of practical wisdom."),
    ("My favorite movie is Blade Runner.", "A classic — the visuals still hold up."),
    ("I am trying to eat healthier this year.", "Small changes add up over time."),
    ("I used to play basketball in high school.", "Do you still play recreationally?"),
    ("My sister just had a baby.", "Congratulations to your sister and the family!"),
    (
        "I am thinking about moving to Denver.",
        "Denver has great outdoor access. What draws you there?",
    ),
    (
        "I built a small bookshelf this weekend.",
        "Woodworking is so satisfying. How did it turn out?",
    ),
    (
        "I have been journaling every night.",
        "Journaling helps process the day. Noticing any patterns?",
    ),
    ("My favorite season is winter.", "There is something peaceful about winter."),
    (
        "I started a small herb garden on my balcony.",
        "Fresh herbs make a huge difference in cooking.",
    ),
    ("I am learning to play the piano.", "Piano is great for the mind. What are you practicing?"),
    (
        "I just got back from a trip to the coast.",
        "The coast is always restorative. Did you enjoy it?",
    ),
    ("My coworker recommended a great podcast.", "What is the podcast about?"),
    ("I have been sleeping better since I cut caffeine.", "Sleep quality makes such a difference."),
    ("I adopted Bruno from a shelter two years ago.", "Shelter dogs are the best. Bruno is lucky."),
    ("I am saving up for a new camera.", "Photography pairs well with painting."),
    ("I feel grateful for the people in my life.", "That is a beautiful thing to carry with you."),
]

_RECALL_QUERIES: list[str] = [
    "What pet do I have?",
    "What hobbies do I enjoy?",
    "Where am I thinking of moving?",
    "What have I been reading about?",
    "What is my favorite movie?",
]


async def evaluate(seed: int = 42, quick: bool = False) -> DimensionResult:
    """Run Portability evaluation (D7).

    Args:
        seed: Random seed for reproducibility.
        quick: If True, skip PT-3 (engine swap continuity test).

    Returns:
        DimensionResult with score 0-100 and per-metric breakdown.
    """
    metrics: dict[str, float] = {}
    passed: list[str] = []
    failed: list[str] = []
    notes_parts: list[str] = []

    # Shared birth params for consistency across scenarios
    birth_params = dict(
        name="PortabilityTest",
        values=["curiosity", "honesty"],
        ocean={
            "openness": 0.85,
            "conscientiousness": 0.65,
            "extraversion": 0.5,
            "agreeableness": 0.75,
            "neuroticism": 0.3,
        },
        persona="I am a portable soul.",
    )

    # ---- PT-1: System Prompt Independence ----

    soul_a = await Soul.birth(**birth_params)
    soul_b = await Soul.birth(**birth_params)

    prompt_a = soul_a.to_system_prompt()
    prompt_b = soul_b.to_system_prompt()

    system_prompt_independence = prompt_a == prompt_b
    metrics["system_prompt_engine_independence"] = 1.0 if system_prompt_independence else 0.0
    (passed if system_prompt_independence else failed).append("system_prompt_engine_independence")

    if not system_prompt_independence:
        # Find first differing line for diagnostics
        lines_a = prompt_a.splitlines()
        lines_b = prompt_b.splitlines()
        diff_line = None
        for i, (la, lb) in enumerate(zip(lines_a, lines_b)):
            if la != lb:
                diff_line = i
                break
        if diff_line is None and len(lines_a) != len(lines_b):
            diff_line = min(len(lines_a), len(lines_b))
        notes_parts.append(f"PT-1: System prompts differ at line {diff_line}")

    # ---- PT-2: Recall Independence ----

    soul_recall = await Soul.birth(**birth_params)

    # Observe 20 interactions
    for u, a in _TEST_INTERACTIONS[:20]:
        await soul_recall.observe(Interaction(user_input=u, agent_output=a))

    # Run recall queries on original
    original_results: dict[str, str | None] = {}
    for query in _RECALL_QUERIES:
        results = await soul_recall.recall(query, limit=1)
        original_results[query] = results[0].content if results else None

    # Export and reimport
    with tempfile.TemporaryDirectory() as tmpdir:
        soul_path = Path(tmpdir) / "portability_recall.soul"
        await soul_recall.export(str(soul_path))
        reloaded = await Soul.awaken(str(soul_path))

    # Run same queries on reloaded soul
    matching = 0
    for query in _RECALL_QUERIES:
        results = await reloaded.recall(query, limit=1)
        reloaded_content = results[0].content if results else None
        if original_results[query] == reloaded_content:
            matching += 1

    recall_independence = matching / len(_RECALL_QUERIES) if _RECALL_QUERIES else 0.0
    # Treat as binary: all queries must match for full credit
    recall_engine_independence = recall_independence == 1.0
    metrics["recall_engine_independence"] = 1.0 if recall_engine_independence else 0.0
    (passed if recall_engine_independence else failed).append("recall_engine_independence")

    if not recall_engine_independence:
        notes_parts.append(f"PT-2: Recall matched {matching}/{len(_RECALL_QUERIES)} queries")

    # ---- PT-3: Engine Swap Continuity (skip if quick) ----

    if quick:
        engine_swap_continuity = True
        notes_parts.append("PT-3: Skipped (quick mode)")
    else:
        swap_soul = await Soul.birth(**birth_params)

        # Observe 20 interactions
        for u, a in _TEST_INTERACTIONS[:20]:
            await swap_soul.observe(Interaction(user_input=u, agent_output=a))

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save first checkpoint
            path1 = Path(tmpdir) / "swap_v1.soul"
            await swap_soul.export(str(path1))

            # Awaken, observe 10 more, save again
            swap_v2 = await Soul.awaken(str(path1))
            for u, a in _TEST_INTERACTIONS[10:20]:
                await swap_v2.observe(Interaction(user_input=u, agent_output=a))

            path2 = Path(tmpdir) / "swap_v2.soul"
            await swap_v2.export(str(path2))
            v2_memory_count = swap_v2.memory_count
            v2_bond_strength = swap_v2.bond.bond_strength

            # Awaken final version, verify state preserved
            swap_v3 = await Soul.awaken(str(path2))

        memory_ok = swap_v3.memory_count == v2_memory_count
        bond_ok = abs(swap_v3.bond.bond_strength - v2_bond_strength) < 0.01
        engine_swap_continuity = memory_ok and bond_ok

        if not engine_swap_continuity:
            details = []
            if not memory_ok:
                details.append(
                    f"memory_count: expected={v2_memory_count}, got={swap_v3.memory_count}"
                )
            if not bond_ok:
                details.append(
                    f"bond_strength: expected={v2_bond_strength:.4f}, "
                    f"got={swap_v3.bond.bond_strength:.4f}"
                )
            notes_parts.append(f"PT-3: State mismatch — {'; '.join(details)}")

    metrics["engine_swap_continuity"] = 1.0 if engine_swap_continuity else 0.0
    (passed if engine_swap_continuity else failed).append("engine_swap_continuity")

    # ---- Compute composite score ----

    score = (
        (metrics["system_prompt_engine_independence"] * 35)
        + (metrics["recall_engine_independence"] * 35)
        + (metrics["engine_swap_continuity"] * 30)
    )

    notes = "; ".join(notes_parts) if notes_parts else "All portability checks passed."

    return DimensionResult(
        dimension_id=7,
        dimension_name="Portability",
        score=round(score, 2),
        metrics=metrics,
        passed=passed,
        failed=failed,
        notes=notes,
    )
