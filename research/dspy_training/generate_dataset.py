# generate_dataset.py — Generate labeled training data for DSPy optimization.
# Created: feat/dspy-integration — Reads ablation study scenarios and labels each
#   turn for significance (should_store) and generates query expansion examples
#   from recall test points. Outputs JSON files split into train/val sets.
#
# Usage:
#   python -m research.dspy_training.generate_dataset
#   python -m research.dspy_training.generate_dataset --output-dir custom/path

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

# Add project root to path so we can import research modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research.agents import UserProfile
from research.scenarios import generate_scenarios


def generate_significance_dataset(
    seed: int = 42,
    num_users: int = 10,
) -> list[dict]:
    """Generate labeled significance training data from scenarios.

    Each example contains an interaction turn labeled as should_store or not.

    Labels are derived from:
    - contains_fact=True -> should_store=True
    - Within 2 turns of a planted fact -> should_store=True
    - importance_hint >= 0.7 -> should_store=True
    - Has expected_emotion -> should_store=True
    - Otherwise -> should_store=False

    Args:
        seed: Random seed for reproducibility.
        num_users: Number of simulated users to generate scenarios for.

    Returns:
        List of labeled dicts with keys: user_input, agent_output,
        core_values, recent_context, should_store, metadata.
    """
    rng = random.Random(seed)
    examples: list[dict] = []
    use_cases = ["support", "coding", "companion", "knowledge"]

    for uid in range(num_users):
        user = UserProfile(
            user_id=uid,
            name=f"user_{uid}",
            interaction_style=rng.choice(["brief", "detailed", "emotional", "technical"]),
            topic_interests=["general"],
            consistency=0.5,
            sentiment_bias=0.0,
        )

        for use_case in use_cases:
            scenarios = generate_scenarios(user, use_case, seed=seed)

            for scenario in scenarios:
                # Build recent context from previous turns
                recent: list[str] = []

                for i, turn in enumerate(scenario.turns):
                    # Determine should_store label
                    near_fact = any(
                        abs(i - j) <= 2
                        for j, t in enumerate(scenario.turns)
                        if t.contains_fact
                    )
                    should_store = (
                        turn.contains_fact
                        or near_fact
                        or turn.importance_hint >= 0.7
                        or bool(turn.expected_emotion)
                    )

                    recent_context = "\n".join(f"- {r[:100]}" for r in recent[-5:])

                    example = {
                        "user_input": turn.user_input,
                        "agent_output": turn.agent_output,
                        "core_values": ["helpfulness", "empathy", "accuracy"],
                        "recent_context": recent_context,
                        "should_store": should_store,
                        "metadata": {
                            "scenario_id": scenario.scenario_id,
                            "turn_index": i,
                            "contains_fact": turn.contains_fact,
                            "fact_content": turn.fact_content,
                            "importance_hint": turn.importance_hint,
                            "expected_emotion": turn.expected_emotion,
                            "use_case": use_case,
                        },
                    }
                    examples.append(example)

                    # Update recent context
                    recent.append(
                        f"User: {turn.user_input[:50]} | Agent: {turn.agent_output[:50]}"
                    )

    return examples


def generate_recall_dataset(
    seed: int = 42,
    num_users: int = 10,
) -> list[dict]:
    """Generate query expansion training data from recall test points.

    For each recall query in the scenarios, generates an example with:
    - The original query
    - The expected fact/answer
    - 3-5 expanded query variations that would better match the planted fact

    Args:
        seed: Random seed for reproducibility.
        num_users: Number of simulated users.

    Returns:
        List of dicts with keys: query, expected_fact, expanded_queries, planted_facts.
    """
    rng = random.Random(seed)
    examples: list[dict] = []
    use_cases = ["support", "coding", "companion", "knowledge"]

    for uid in range(num_users):
        user = UserProfile(
            user_id=uid,
            name=f"user_{uid}",
            interaction_style=rng.choice(["brief", "detailed", "emotional", "technical"]),
            topic_interests=["general"],
            consistency=0.5,
            sentiment_bias=0.0,
        )

        for use_case in use_cases:
            scenarios = generate_scenarios(user, use_case, seed=seed)

            for scenario in scenarios:
                for query, expected_fact in scenario.recall_queries:
                    # Generate expanded queries that rephrase the question
                    # to increase token overlap with planted facts
                    expanded = _expand_query_heuristic(query, expected_fact, scenario.planted_facts)

                    example = {
                        "query": query,
                        "expected_fact": expected_fact,
                        "expanded_queries": expanded,
                        "planted_facts": scenario.planted_facts,
                        "personality_summary": "",
                    }
                    examples.append(example)

    return examples


def _expand_query_heuristic(
    query: str,
    expected_fact: str,
    planted_facts: list[str],
) -> list[str]:
    """Generate heuristic query expansions for training labels.

    Creates 3-5 rephrased versions of the query that would have better
    token overlap with the planted facts.

    Args:
        query: The original recall query.
        expected_fact: The expected answer.
        planted_facts: All planted facts in the scenario.

    Returns:
        List of expanded query strings.
    """
    expanded = [query]

    # Rephrase with keywords from the expected fact
    fact_words = set(expected_fact.lower().split()) - {
        "the", "a", "an", "is", "are", "was", "were", "user", "user's",
    }
    if fact_words:
        keyword_query = " ".join(sorted(fact_words)[:5])
        expanded.append(keyword_query)

    # Add the expected fact itself as a query variation
    expanded.append(expected_fact)

    # Generate a "tell me about" variation
    topic = query.lower().replace("what is", "").replace("what does", "").strip(" ?")
    expanded.append(f"tell me about {topic}")

    # Add a short keyword-only version
    keywords = [w for w in query.split() if len(w) > 3 and w.lower() not in {"what", "does", "the", "user"}]
    if keywords:
        expanded.append(" ".join(keywords))

    return expanded[:5]


def split_dataset(
    data: list[dict],
    val_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """Split dataset into train and validation sets.

    Args:
        data: Full dataset to split.
        val_ratio: Fraction reserved for validation (default 20%).
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (train, val) lists.
    """
    rng = random.Random(seed)
    shuffled = list(data)
    rng.shuffle(shuffled)
    split_idx = int(len(shuffled) * (1 - val_ratio))
    return shuffled[:split_idx], shuffled[split_idx:]


def main(output_dir: str = "research/dspy_training/data") -> None:
    """Generate all training datasets and save to disk.

    Args:
        output_dir: Directory to write JSON files to.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("Generating significance dataset...")
    sig_data = generate_significance_dataset()
    sig_train, sig_val = split_dataset(sig_data)

    print(f"  Total: {len(sig_data)}, Train: {len(sig_train)}, Val: {len(sig_val)}")
    print(f"  Positive rate: {sum(1 for e in sig_data if e['should_store']) / len(sig_data):.1%}")

    (out / "significance_train.json").write_text(json.dumps(sig_train, indent=2))
    (out / "significance_val.json").write_text(json.dumps(sig_val, indent=2))

    print("Generating recall dataset...")
    recall_data = generate_recall_dataset()
    recall_train, recall_val = split_dataset(recall_data)

    print(f"  Total: {len(recall_data)}, Train: {len(recall_train)}, Val: {len(recall_val)}")

    (out / "recall_train.json").write_text(json.dumps(recall_train, indent=2))
    (out / "recall_val.json").write_text(json.dumps(recall_val, indent=2))

    print(f"Saved to {out}/")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate DSPy training data")
    parser.add_argument("--output-dir", default="research/dspy_training/data")
    args = parser.parse_args()
    main(args.output_dir)
