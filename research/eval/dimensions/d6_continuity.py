# d6_continuity.py — Dimension 6: Identity Continuity (weight: 10%)
# Created: 2026-03-12 — Export/import round-trip fidelity tests
#
# Scenarios implemented:
#   IC-1: Basic Export/Import Round-Trip — birth, observe 30 turns, export,
#         reimport, compare DID/name/personality/bond/memory_count
#   IC-2: Recall Consistency — run 5 recall queries on original and reloaded
#         soul, compare top-1 results
#   IC-3: Incarnation Chain (full mode only) — birth, observe 10 turns,
#         reincarnate, observe 10 more, verify lineage tracking
#
# Scoring formula:
#   score = (identity_hash_match * 25) + (dna_fidelity * 20) +
#           (bond_fidelity * 15) + (memory_count_fidelity * 10) +
#           (recall_consistency * 20) + (incarnation_chain_integrity * 10)

from __future__ import annotations

import tempfile
from pathlib import Path

from soul_protocol import Interaction, Soul

from ..suite import DimensionResult

# --- Test interaction corpus for observe() calls ---

_TEST_INTERACTIONS: list[tuple[str, str]] = [
    (
        "My name is Alex and I live in Portland.",
        "Nice to meet you, Alex! Portland is a great city.",
    ),
    (
        "I work as a data engineer at a startup.",
        "That sounds like an exciting role — startups move fast.",
    ),
    (
        "My favorite programming language is Python.",
        "Python is wonderfully versatile for data work.",
    ),
    (
        "I adopted a cat named Mochi last month.",
        "Mochi is an adorable name! How is the cat settling in?",
    ),
    (
        "I love hiking in the Columbia River Gorge.",
        "The Gorge has some of the best trails in Oregon.",
    ),
    ("My birthday is on March 15th.", "I will remember that — March 15th, noted!"),
    (
        "I am learning Rust in my spare time.",
        "Rust is a great complement to Python for performance.",
    ),
    ("My partner's name is Jordan.", "Good to know — say hi to Jordan for me."),
    (
        "I am training for a half marathon.",
        "That is an impressive goal. How is the training going?",
    ),
    (
        "I just finished reading Dune for the first time.",
        "Dune is a masterpiece — what did you think of it?",
    ),
    (
        "I have been feeling stressed about a deadline at work.",
        "Deadlines can be tough. Is there anything I can help with?",
    ),
    ("My favorite food is ramen.", "A good bowl of ramen is hard to beat."),
    ("I am planning a trip to Japan next year.", "Japan is incredible — any cities on your list?"),
    ("I play guitar on weekends.", "Music is a great creative outlet. What genres do you play?"),
    (
        "My team just shipped a big feature at work.",
        "Congrats on the launch! That must feel great.",
    ),
    ("I grew up in a small town in Ohio.", "Small-town roots can shape you in lasting ways."),
    (
        "I have been meditating every morning for a month.",
        "A month of daily meditation — that takes real discipline.",
    ),
    ("My favorite season is autumn.", "Autumn in the Pacific Northwest must be stunning."),
    (
        "I am thinking about getting a second cat.",
        "Mochi might enjoy a friend! Have you found one yet?",
    ),
    (
        "I volunteer at a local food bank on Saturdays.",
        "That is really admirable. Community work matters.",
    ),
    ("I just got promoted to senior engineer.", "Congratulations on the promotion, Alex!"),
    ("My mom is visiting next week.", "That will be nice — are you planning anything special?"),
    (
        "I have been watching a lot of sci-fi shows lately.",
        "Any recommendations? I enjoy good sci-fi.",
    ),
    (
        "I switched to using Neovim this week.",
        "Neovim has a loyal following — how do you like it so far?",
    ),
    (
        "I am considering going back to school for a masters.",
        "A masters could open doors. What field are you thinking?",
    ),
    ("My cat Mochi learned to open doors.", "That is both impressive and a little concerning!"),
    ("I ran my first 10K last weekend.", "Great milestone on the way to your half marathon!"),
    (
        "I cooked a new ramen recipe and it turned out great.",
        "Homemade ramen is next level. What was the recipe?",
    ),
    (
        "I have been feeling really happy lately.",
        "That is wonderful to hear, Alex. You deserve it.",
    ),
    (
        "Thank you for always remembering things about me.",
        "Of course — that is what I am here for.",
    ),
]

_RECALL_QUERIES: list[str] = [
    "What is my name and where do I live?",
    "What pet do I have?",
    "What programming languages do I know?",
    "What am I training for?",
    "Where do I work?",
]


async def evaluate(seed: int = 42, quick: bool = False) -> DimensionResult:
    """Run Identity Continuity evaluation (D6).

    Args:
        seed: Random seed for reproducibility.
        quick: If True, skip IC-3 (incarnation chain test).

    Returns:
        DimensionResult with score 0-100 and per-metric breakdown.
    """
    metrics: dict[str, float] = {}
    passed: list[str] = []
    failed: list[str] = []
    notes_parts: list[str] = []

    # ---- IC-1: Basic Export/Import Round-Trip ----

    soul = await Soul.birth(
        name="ContinuityTest",
        values=["empathy", "curiosity"],
        ocean={
            "openness": 0.9,
            "conscientiousness": 0.7,
            "extraversion": 0.6,
            "agreeableness": 0.85,
            "neuroticism": 0.25,
        },
        persona="I remember everything.",
    )

    interactions = [Interaction(user_input=u, agent_output=a) for u, a in _TEST_INTERACTIONS[:30]]
    for interaction in interactions:
        await soul.observe(interaction)

    # Capture pre-export state
    pre_did = soul.did
    pre_name = soul.name
    pre_born = soul.born
    pre_personality = soul.dna.personality
    pre_bond_strength = soul.bond.bond_strength
    pre_interaction_count = soul.bond.interaction_count
    pre_memory_count = soul.memory_count

    # Export and reimport
    with tempfile.TemporaryDirectory() as tmpdir:
        soul_path = Path(tmpdir) / "continuity_test.soul"
        await soul.export(str(soul_path))
        reloaded = await Soul.awaken(str(soul_path))

    # Compare identity fields
    identity_hash_match = (
        reloaded.did == pre_did and reloaded.name == pre_name and reloaded.born == pre_born
    )
    metrics["identity_hash_match"] = 1.0 if identity_hash_match else 0.0
    (passed if identity_hash_match else failed).append("identity_hash_match")

    # Compare DNA (OCEAN traits within epsilon)
    eps = 0.001
    personality_r = reloaded.dna.personality
    dna_checks = [
        abs(personality_r.openness - pre_personality.openness) < eps,
        abs(personality_r.conscientiousness - pre_personality.conscientiousness) < eps,
        abs(personality_r.extraversion - pre_personality.extraversion) < eps,
        abs(personality_r.agreeableness - pre_personality.agreeableness) < eps,
        abs(personality_r.neuroticism - pre_personality.neuroticism) < eps,
    ]
    dna_fidelity = all(dna_checks)
    metrics["dna_fidelity"] = 1.0 if dna_fidelity else 0.0
    (passed if dna_fidelity else failed).append("dna_fidelity")

    # Compare bond
    bond_strength_match = abs(reloaded.bond.bond_strength - pre_bond_strength) < 0.01
    interaction_count_match = reloaded.bond.interaction_count == pre_interaction_count
    bond_fidelity = bond_strength_match and interaction_count_match
    metrics["bond_fidelity"] = 1.0 if bond_fidelity else 0.0
    (passed if bond_fidelity else failed).append("bond_fidelity")

    # Compare memory count
    memory_count_fidelity = reloaded.memory_count == pre_memory_count
    metrics["memory_count_fidelity"] = 1.0 if memory_count_fidelity else 0.0
    (passed if memory_count_fidelity else failed).append("memory_count_fidelity")

    if not identity_hash_match:
        notes_parts.append(f"IC-1: DID mismatch — pre={pre_did}, post={reloaded.did}")
    if not memory_count_fidelity:
        notes_parts.append(
            f"IC-1: Memory count mismatch — pre={pre_memory_count}, post={reloaded.memory_count}"
        )

    # ---- IC-2: Recall Consistency ----

    matching_queries = 0
    total_queries = len(_RECALL_QUERIES)

    for query in _RECALL_QUERIES:
        original_results = await soul.recall(query, limit=1)
        reloaded_results = await reloaded.recall(query, limit=1)

        if original_results and reloaded_results:
            if original_results[0].content == reloaded_results[0].content:
                matching_queries += 1
        elif not original_results and not reloaded_results:
            # Both returned nothing — that still counts as consistent
            matching_queries += 1

    recall_consistency = matching_queries / total_queries if total_queries > 0 else 0.0
    metrics["recall_consistency"] = round(recall_consistency, 4)
    (passed if recall_consistency >= 0.8 else failed).append("recall_consistency")

    if recall_consistency < 1.0:
        notes_parts.append(
            f"IC-2: Recall consistency {recall_consistency:.0%} "
            f"({matching_queries}/{total_queries} queries matched)"
        )

    # ---- IC-3: Incarnation Chain (skip if quick) ----

    if quick:
        incarnation_chain_integrity = True
        notes_parts.append("IC-3: Skipped (quick mode)")
    else:
        chain_soul = await Soul.birth(
            name="ChainTest",
            values=["growth"],
            ocean={"openness": 0.8, "conscientiousness": 0.6},
            persona="I evolve through lives.",
        )
        old_did = chain_soul.did

        # Observe 10 turns
        for u, a in _TEST_INTERACTIONS[:10]:
            await chain_soul.observe(Interaction(user_input=u, agent_output=a))

        # Reincarnate
        reincarnated = await Soul.reincarnate(chain_soul)

        # Observe 10 more
        for u, a in _TEST_INTERACTIONS[10:20]:
            await reincarnated.observe(Interaction(user_input=u, agent_output=a))

        # Verify lineage
        incarnation_ok = reincarnated.identity.incarnation == 2
        previous_lives_ok = old_did in reincarnated.identity.previous_lives
        did_different = reincarnated.did != old_did
        incarnation_chain_integrity = incarnation_ok and previous_lives_ok and did_different

        if not incarnation_chain_integrity:
            details = []
            if not incarnation_ok:
                details.append(f"incarnation={reincarnated.identity.incarnation}, expected=2")
            if not previous_lives_ok:
                details.append(
                    f"old DID not in previous_lives: {reincarnated.identity.previous_lives}"
                )
            if not did_different:
                details.append("DID did not change after reincarnation")
            notes_parts.append(f"IC-3: Chain broken — {'; '.join(details)}")

    metrics["incarnation_chain_integrity"] = 1.0 if incarnation_chain_integrity else 0.0
    (passed if incarnation_chain_integrity else failed).append("incarnation_chain_integrity")

    # ---- Compute composite score ----

    score = (
        (metrics["identity_hash_match"] * 25)
        + (metrics["dna_fidelity"] * 20)
        + (metrics["bond_fidelity"] * 15)
        + (metrics["memory_count_fidelity"] * 10)
        + (metrics["recall_consistency"] * 20)
        + (metrics["incarnation_chain_integrity"] * 10)
    )

    notes = "; ".join(notes_parts) if notes_parts else "All continuity checks passed."

    return DimensionResult(
        dimension_id=6,
        dimension_name="Identity Continuity",
        score=round(score, 2),
        metrics=metrics,
        passed=passed,
        failed=failed,
        notes=notes,
    )
