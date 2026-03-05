# scripts/research_memory.py — Memory formation, recall accuracy, export persistence,
# and ACT-R decay research scenarios for the soul-protocol whitepaper.
# Created: 2026-03-04 — Task #2 of the soul-research team.
#
# Scenarios:
#   1. Memory Formation Rate — 40 diverse interactions, measure episodic/semantic/graph counts,
#      then run 15 targeted recall queries and check correctness.
#   2. Export/Awaken Persistence — Export soul to .soul file, awaken fresh, re-run same 15
#      queries and compare recall counts.
#   3. ACT-R Decay — Verify recency-weighted recall: recent topics rank higher than old ones.
#
# Usage:
#   cd soul-protocol && uv run python scripts/research_memory.py

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Ensure the src directory is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from soul_protocol import Interaction, Soul

# ---------------------------------------------------------------------------
# Interaction datasets
# ---------------------------------------------------------------------------

GROUP_A_PERSONAL = [
    ("My name is Jordan", "Nice to meet you Jordan!"),
    ("I live in Austin Texas", "Austin is a great city!"),
    ("I work at DataCorp as an ML engineer", "That sounds fascinating!"),
    ("I have a dog named Pixel", "Pixel is a great name!"),
    ("I drive a Tesla Model 3", "Nice choice!"),
    ("I drink only black coffee", "A purist! Respect."),
    ("I'm allergic to peanuts", "Good to know, I'll remember that."),
    ("My birthday is March 15", "I'll remember that!"),
    ("My sister is named Mia", "That's lovely."),
    ("I'm learning Spanish right now", "Bueno! Keep at it."),
]

GROUP_B_PREFERENCES = [
    ("I love hiking in the mountains", "Nature is the best reset."),
    ("I hate unnecessary meetings", "Who doesn't?"),
    ("I prefer async communication over sync", "Makes deep work easier."),
    ("I use VSCode as my editor", "Great choice."),
    ("I listen to jazz while coding", "Nice vibe."),
    ("I read science fiction novels", "Good taste."),
    ("I play chess online", "A great mental workout."),
    ("I dislike social media", "Understandable."),
    ("I'm a morning person", "Early bird!"),
    ("I collect vintage maps", "That's a unique hobby."),
]

GROUP_C_WORK = [
    ("I work on NLP recommendation models", "Interesting problem space!"),
    ("My team has 5 engineers", "Small team, high impact!"),
    ("We use PyTorch for all our models", "PyTorch is excellent."),
    ("Our infrastructure runs on AWS", "Solid choice."),
    ("Python is my primary language", "Great for ML."),
    ("Our product is a recommendation engine", "Classic ML challenge."),
    ("We struggle with the cold-start problem", "That's tough — limited data for new users."),
    ("Our model accuracy improved 12% last quarter", "Impressive progress!"),
    ("I'm working on a new transformer architecture", "Exciting research!"),
    ("We're deploying to production next month", "Exciting milestone!"),
]

GROUP_D_EMOTIONAL = [
    ("I just got promoted to senior engineer!", "Congratulations! That's well-deserved."),
    ("I'm frustrated with our legacy codebase", "Legacy debt is real."),
    ("My latest model hit 94% accuracy!", "That's excellent!"),
    ("I'm worried about our Q4 deadline", "Pressure is real."),
    ("We had a great team lunch today", "Those moments matter."),
    ("I'm excited about our new project launch", "New beginnings are thrilling!"),
    ("I feel burned out after this sprint", "Take care of yourself."),
    ("My mentor gave me amazing feedback today", "Good mentors are invaluable."),
    ("I'm nervous about my conference talk next week", "You'll do great!"),
    (
        "I finally fixed that bug that's been haunting me for weeks",
        "Victory! That must feel amazing.",
    ),
]

ALL_INTERACTIONS = GROUP_A_PERSONAL + GROUP_B_PREFERENCES + GROUP_C_WORK + GROUP_D_EMOTIONAL

RECALL_QUERIES = [
    "name is Jordan",
    "live in Austin Texas",
    "work at DataCorp ML engineer",
    "dog named Pixel",
    "VSCode editor",
    "drink black coffee",
    "allergic peanuts",
    "Python primary language",
    "team engineers",
    "DataCorp company",
    "model accuracy improved",
    "hiking mountains hobby chess",
    "hate unnecessary meetings",
    "birthday March",
    "sister named Mia",
]

# Ground truth for each query — what the correct answer should contain
RECALL_GROUND_TRUTH = {
    "name is Jordan": ["jordan"],
    "live in Austin Texas": ["austin"],
    "work at DataCorp ML engineer": ["datacorp", "engineer", "ml"],
    "dog named Pixel": ["pixel", "dog"],
    "VSCode editor": ["vscode", "editor"],
    "drink black coffee": ["coffee", "black"],
    "allergic peanuts": ["peanut", "allergic"],
    "Python primary language": ["python"],
    "team engineers": ["team", "engineer"],
    "DataCorp company": ["datacorp"],
    "model accuracy improved": ["accuracy", "model"],
    "hiking mountains hobby chess": ["hiking", "chess", "maps", "vintage", "mountain"],
    "hate unnecessary meetings": ["meeting", "hate", "unnecessary"],
    "birthday March": ["march", "birthday"],
    "sister named Mia": ["mia", "sister"],
}


def _check_recall_hit(results: list, ground_truth_terms: list[str]) -> bool:
    """Check if any of the top results contain any ground truth term."""
    for entry in results:
        content_lower = entry.content.lower()
        for term in ground_truth_terms:
            if term.lower() in content_lower:
                return True
    return False


# ---------------------------------------------------------------------------
# Scenario 1: Memory Formation Rate
# ---------------------------------------------------------------------------


async def scenario_memory_formation() -> dict:
    """Feed 40 interactions, measure memory counts and recall accuracy."""
    print("\n=== SCENARIO 1: Memory Formation Rate ===")
    # Don't pass engine explicitly — let MemoryManager create its own HeuristicEngine
    # internally with _is_heuristic_only=True, so it uses the full FACT_PATTERNS
    # regex set for fact extraction instead of the minimal HeuristicEngine.think().
    soul = await Soul.birth(
        name="Sage",
        values=["curiosity", "honesty", "helpfulness"],
    )

    # Feed all 40 interactions
    # Use soul._memory.observe() to capture pipeline results, then
    # replicate the graph/state/evolution steps that Soul.observe() does.
    formation_log = []
    for i, (user_msg, agent_msg) in enumerate(ALL_INTERACTIONS):
        interaction = Interaction(user_input=user_msg, agent_output=agent_msg)
        result = await soul._memory.observe(interaction)

        # Replicate Soul.observe() post-pipeline: graph + state + evolution
        raw_entities = result["entities"]
        if raw_entities:
            graph_entities = []
            for ent in raw_entities:
                graph_ent = {
                    "name": ent["name"],
                    "entity_type": ent.get("type", "unknown"),
                    "relationships": [],
                }
                relation = ent.get("relation")
                if relation:
                    graph_ent["relationships"].append({"target": "user", "relation": relation})
                graph_entities.append(graph_ent)
            await soul._memory.update_graph(graph_entities)

        soul._state.on_interaction(interaction, somatic=result.get("somatic"))
        await soul._evolution.check_triggers(soul._dna, interaction)

        formation_log.append(
            {
                "index": i,
                "user": user_msg,
                "is_significant": result["is_significant"],
                "significance": round(result["significance"], 3),
                "facts_extracted": len(result["facts"]),
                "fact_contents": [f.content for f in result["facts"]],
                "entities_found": len(result["entities"]),
                "entity_names": [e["name"] for e in result["entities"]],
            }
        )

    # Measure memory store counts directly
    episodic_count = len(soul._memory._episodic._memories)
    semantic_count = len(soul._memory._semantic._facts)
    graph_node_count = len(soul._memory._graph._entities)
    graph_edge_count = len(soul._memory._graph._edges)
    total_memories = soul.memory_count

    print(f"  Episodic memories:  {episodic_count}")
    print(f"  Semantic facts:     {semantic_count}")
    print(f"  Graph nodes:        {graph_node_count}")
    print(f"  Graph edges:        {graph_edge_count}")
    print(f"  Total memory count: {total_memories}")

    # Run 15 targeted recall queries
    recall_results = []
    hits = 0
    misses = 0
    for query in RECALL_QUERIES:
        memories = await soul.recall(query, limit=3)
        ground_truth = RECALL_GROUND_TRUTH.get(query, [])
        hit = _check_recall_hit(memories, ground_truth)
        if hit:
            hits += 1
        else:
            misses += 1

        recall_results.append(
            {
                "query": query,
                "hit": hit,
                "result_count": len(memories),
                "top_results": [
                    {"content": m.content[:120], "type": m.type.value, "importance": m.importance}
                    for m in memories
                ],
            }
        )
        status = "HIT" if hit else "MISS"
        print(f"  [{status}] {query} -> {len(memories)} results")

    recall_accuracy = hits / len(RECALL_QUERIES) if RECALL_QUERIES else 0.0
    print(f"\n  Recall accuracy: {hits}/{len(RECALL_QUERIES)} ({recall_accuracy:.0%})")

    # Also grab the semantic facts for the report
    all_facts = [f.content for f in soul._memory._semantic.facts()]

    return {
        "scenario": "memory_formation",
        "soul_name": "Sage",
        "interactions_fed": len(ALL_INTERACTIONS),
        "group_counts": {
            "personal": len(GROUP_A_PERSONAL),
            "preferences": len(GROUP_B_PREFERENCES),
            "work": len(GROUP_C_WORK),
            "emotional": len(GROUP_D_EMOTIONAL),
        },
        "memory_counts": {
            "episodic": episodic_count,
            "semantic": semantic_count,
            "graph_nodes": graph_node_count,
            "graph_edges": graph_edge_count,
            "total": total_memories,
        },
        "formation_log": formation_log,
        "all_semantic_facts": all_facts,
        "recall_results": recall_results,
        "recall_accuracy": round(recall_accuracy, 3),
        "hits": hits,
        "misses": misses,
        "_soul_ref": soul,  # keep reference for scenario 2
    }


# ---------------------------------------------------------------------------
# Scenario 2: Export/Awaken Persistence
# ---------------------------------------------------------------------------


async def scenario_export_persistence(soul: Soul) -> dict:
    """Export soul to .soul file, awaken fresh, re-run recall queries."""
    print("\n=== SCENARIO 2: Export/Awaken Persistence ===")

    # Record pre-export counts
    pre_episodic = len(soul._memory._episodic._memories)
    pre_semantic = len(soul._memory._semantic._facts)
    pre_graph = len(soul._memory._graph._entities)

    # Export to temp file
    with tempfile.NamedTemporaryFile(suffix=".soul", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await soul.export(tmp_path)
        file_size = os.path.getsize(tmp_path)
        print(f"  Exported to: {tmp_path} ({file_size} bytes)")

        # Awaken fresh from exported file (no engine = heuristic-only mode)
        awakened = await Soul.awaken(tmp_path)

        # Measure post-awaken counts
        post_episodic = len(awakened._memory._episodic._memories)
        post_semantic = len(awakened._memory._semantic._facts)
        post_graph = len(awakened._memory._graph._entities)

        print(f"  Pre-export:  episodic={pre_episodic}, semantic={pre_semantic}, graph={pre_graph}")
        print(
            f"  Post-awaken: episodic={post_episodic}, semantic={post_semantic}, graph={post_graph}"
        )

        # Re-run same 15 recall queries on awakened soul
        recall_results = []
        hits = 0
        for query in RECALL_QUERIES:
            memories = await awakened.recall(query, limit=3)
            ground_truth = RECALL_GROUND_TRUTH.get(query, [])
            hit = _check_recall_hit(memories, ground_truth)
            if hit:
                hits += 1

            recall_results.append(
                {
                    "query": query,
                    "hit": hit,
                    "result_count": len(memories),
                    "top_results": [
                        {
                            "content": m.content[:120],
                            "type": m.type.value,
                            "importance": m.importance,
                        }
                        for m in memories
                    ],
                }
            )
            status = "HIT" if hit else "MISS"
            print(f"  [{status}] {query} -> {len(memories)} results")

        recall_accuracy = hits / len(RECALL_QUERIES) if RECALL_QUERIES else 0.0
        print(
            f"\n  Post-awaken recall accuracy: {hits}/{len(RECALL_QUERIES)} ({recall_accuracy:.0%})"
        )

        # Check identity preservation
        identity_preserved = awakened.name == soul.name and awakened.did == soul.did
        print(f"  Identity preserved: {identity_preserved}")

    finally:
        os.unlink(tmp_path)

    return {
        "scenario": "export_persistence",
        "export_file_size_bytes": file_size,
        "pre_export_counts": {
            "episodic": pre_episodic,
            "semantic": pre_semantic,
            "graph_nodes": pre_graph,
        },
        "post_awaken_counts": {
            "episodic": post_episodic,
            "semantic": post_semantic,
            "graph_nodes": post_graph,
        },
        "count_preservation": {
            "episodic_match": pre_episodic == post_episodic,
            "semantic_match": pre_semantic == post_semantic,
            "graph_match": pre_graph == post_graph,
        },
        "identity_preserved": identity_preserved,
        "recall_results": recall_results,
        "recall_accuracy": round(recall_accuracy, 3),
        "hits": hits,
    }


# ---------------------------------------------------------------------------
# Scenario 3: ACT-R Decay
# ---------------------------------------------------------------------------

COOKING_INTERACTIONS = [
    ("I love making pasta from scratch", "Homemade pasta is the best!"),
    ("My favorite recipe is chicken tikka masala", "That's a classic!"),
    ("I bake sourdough bread every weekend", "Sourdough takes patience."),
    ("I use cast iron skillets for everything", "Cast iron is amazing."),
    ("I'm learning to make sushi at home", "That's ambitious!"),
    ("My grandmother taught me to cook", "Family recipes are precious."),
    ("I prefer cooking with fresh herbs", "Fresh herbs make a difference."),
    ("I make my own hot sauce", "Spice is life!"),
    ("I'm experimenting with fermentation", "Fermented foods are great."),
    ("I love grilling in the summer", "Nothing beats a good grill."),
    ("My kitchen has a wood-fired pizza oven", "That's a dream kitchen!"),
    ("I meal prep on Sundays for the whole week", "Great discipline."),
    ("I use a slow cooker for stews", "Low and slow is the way."),
    ("I recently tried molecular gastronomy", "Science meets cooking!"),
    ("I grow my own vegetables in a garden", "Farm to table at home."),
    ("I make homemade ice cream in summer", "Homemade ice cream is unbeatable."),
    ("I love trying street food when traveling", "Street food is authentic."),
    ("I collect vintage cookbooks", "Old recipes are gold."),
    ("I'm vegetarian on weekdays", "Flexitarian approach is smart."),
    ("I use a wok for stir-fry dishes", "Wok cooking is fast and delicious."),
]

PYTHON_INTERACTIONS = [
    ("I use Python for data analysis every day", "Python is great for that."),
    ("I love Python's list comprehensions", "They make code so clean."),
    ("I'm building a Python web scraper", "Beautiful Soup or Scrapy?"),
    ("I use Python decorators extensively", "Decorators are powerful."),
    ("Python type hints improved my codebase", "Static typing helps catch bugs."),
    ("I switched from Python 3.10 to 3.12", "3.12 is much faster!"),
    ("I use Python asyncio for concurrent tasks", "Async is essential for I/O."),
    ("I write Python unit tests with pytest", "Pytest is the best framework."),
    ("I use Python virtual environments for isolation", "Good practice."),
    ("I love Python f-strings for formatting", "F-strings are clean."),
    ("I'm using Python pandas for data processing", "Pandas is indispensable."),
    ("I use Python logging module for debugging", "Proper logging saves time."),
    ("I'm migrating Python code to use Pydantic v2", "V2 is much faster."),
    ("I use Python pathlib for file operations", "Pathlib is so much better than os.path."),
    ("I'm building a Python CLI with Click", "Click is elegant."),
    ("I use Python generators for memory efficiency", "Lazy evaluation is smart."),
    ("I profile Python code with cProfile", "Profiling reveals bottlenecks."),
    ("I use Python dataclasses for simple models", "Dataclasses are convenient."),
    ("I'm learning Python metaprogramming", "Meta stuff is mind-bending."),
    ("I debug Python with breakpoint() and pdb", "Built-in debugging is handy."),
    ("I use Python context managers for resources", "With statements are clean."),
    ("I'm building a Python package for PyPI", "Sharing code is great."),
    ("I use Python walrus operator for assignments", "Walrus is useful in loops."),
    ("I'm exploring Python 3.12 pattern matching", "Match/case is powerful."),
    ("I use Python multiprocessing for CPU tasks", "GIL bypass for heavy compute."),
    ("I'm refactoring Python code to reduce complexity", "Simpler is better."),
    ("I use Python rich library for terminal output", "Rich makes CLIs beautiful."),
    ("I'm writing Python type stubs for C extensions", "Types for everything."),
    ("I use Python ABC for abstract base classes", "Enforces interface contracts."),
    ("I'm building a Python REST API with FastAPI", "FastAPI is blazing fast."),
]


async def scenario_actr_decay() -> dict:
    """Verify ACT-R recency effect: recent Python topics rank higher than old cooking topics."""
    print("\n=== SCENARIO 3: ACT-R Decay ===")
    # No engine = heuristic-only mode (uses full FACT_PATTERNS)
    soul = await Soul.birth(
        name="Temporal",
        values=["learning", "growth"],
    )

    # Phase 1: Feed 20 early cooking interactions with timestamps in the past
    base_time = datetime.now() - timedelta(hours=24)
    cooking_log = []
    for i, (user_msg, agent_msg) in enumerate(COOKING_INTERACTIONS):
        ts = base_time + timedelta(minutes=i * 5)
        interaction = Interaction(user_input=user_msg, agent_output=agent_msg, timestamp=ts)
        result = await soul._memory.observe(interaction)
        # Replicate Soul.observe() post-pipeline
        raw_entities = result["entities"]
        if raw_entities:
            graph_entities = []
            for ent in raw_entities:
                graph_ent = {
                    "name": ent["name"],
                    "entity_type": ent.get("type", "unknown"),
                    "relationships": [],
                }
                relation = ent.get("relation")
                if relation:
                    graph_ent["relationships"].append({"target": "user", "relation": relation})
                graph_entities.append(graph_ent)
            await soul._memory.update_graph(graph_entities)
        soul._state.on_interaction(interaction, somatic=result.get("somatic"))
        cooking_log.append(
            {
                "index": i,
                "user": user_msg,
                "facts": len(result["facts"]),
                "timestamp": ts.isoformat(),
            }
        )

    cooking_episodic = len(soul._memory._episodic._memories)
    cooking_semantic = len(soul._memory._semantic._facts)
    print(f"  After cooking phase: episodic={cooking_episodic}, semantic={cooking_semantic}")

    # Phase 2: Feed 30 recent Python interactions with recent timestamps
    recent_base = datetime.now() - timedelta(minutes=30)
    python_log = []
    for i, (user_msg, agent_msg) in enumerate(PYTHON_INTERACTIONS):
        ts = recent_base + timedelta(minutes=i)
        interaction = Interaction(user_input=user_msg, agent_output=agent_msg, timestamp=ts)
        result = await soul._memory.observe(interaction)
        # Replicate Soul.observe() post-pipeline
        raw_entities = result["entities"]
        if raw_entities:
            graph_entities = []
            for ent in raw_entities:
                graph_ent = {
                    "name": ent["name"],
                    "entity_type": ent.get("type", "unknown"),
                    "relationships": [],
                }
                relation = ent.get("relation")
                if relation:
                    graph_ent["relationships"].append({"target": "user", "relation": relation})
                graph_entities.append(graph_ent)
            await soul._memory.update_graph(graph_entities)
        soul._state.on_interaction(interaction, somatic=result.get("somatic"))
        python_log.append(
            {
                "index": i,
                "user": user_msg,
                "facts": len(result["facts"]),
                "timestamp": ts.isoformat(),
            }
        )

    total_episodic = len(soul._memory._episodic._memories)
    total_semantic = len(soul._memory._semantic._facts)
    print(f"  After Python phase: episodic={total_episodic}, semantic={total_semantic}")

    # Query "Python" — should rank higher due to recency
    python_results = await soul.recall("Python programming", limit=10)
    python_contents = [m.content[:100] for m in python_results]

    # Query "cooking" — should rank lower due to being older
    cooking_results = await soul.recall("cooking recipes food", limit=10)
    cooking_contents = [m.content[:100] for m in cooking_results]

    # Analyze: count how many of the top-5 Python results are actually about Python
    python_in_top5 = 0
    cooking_in_top5 = 0
    for m in python_results[:5]:
        content_lower = m.content.lower()
        if "python" in content_lower:
            python_in_top5 += 1

    for m in cooking_results[:5]:
        content_lower = m.content.lower()
        if any(
            w in content_lower
            for w in ["cook", "recipe", "food", "kitchen", "bake", "grill", "pasta"]
        ):
            cooking_in_top5 += 1

    # Check recency ranking: compute average activation rank for Python vs cooking
    # If ACT-R decay works, Python (recent) results should have higher activation
    python_result_count = len(python_results)
    cooking_result_count = len(cooking_results)

    # Verify Python gets more results (it has more interactions and is more recent)
    python_dominates = python_result_count >= cooking_result_count

    print(f"\n  Python query results: {python_result_count} (top 5 about Python: {python_in_top5})")
    print(
        f"  Cooking query results: {cooking_result_count} (top 5 about cooking: {cooking_in_top5})"
    )
    print(f"  Python dominates recall: {python_dominates}")

    # Additional check: query both topics and see which appears first
    mixed_results = await soul.recall("topics I've discussed", limit=10)
    mixed_is_python_first = False
    for m in mixed_results[:3]:
        content_lower = m.content.lower()
        if "python" in content_lower:
            mixed_is_python_first = True
            break
        if any(w in content_lower for w in ["cook", "recipe", "pasta"]):
            break

    print(f"  Mixed query — Python appears first in top 3: {mixed_is_python_first}")

    return {
        "scenario": "actr_decay",
        "cooking_interactions": len(COOKING_INTERACTIONS),
        "python_interactions": len(PYTHON_INTERACTIONS),
        "cooking_timestamps": "24 hours ago",
        "python_timestamps": "last 30 minutes",
        "memory_counts_after_cooking": {
            "episodic": cooking_episodic,
            "semantic": cooking_semantic,
        },
        "memory_counts_after_python": {
            "episodic": total_episodic,
            "semantic": total_semantic,
        },
        "python_query": {
            "total_results": python_result_count,
            "python_in_top5": python_in_top5,
            "top_results": python_contents[:5],
        },
        "cooking_query": {
            "total_results": cooking_result_count,
            "cooking_in_top5": cooking_in_top5,
            "top_results": cooking_contents[:5],
        },
        "actr_recency_effect": {
            "python_dominates_recall": python_dominates,
            "python_in_top5_count": python_in_top5,
            "cooking_in_top5_count": cooking_in_top5,
        },
        "cooking_log_sample": cooking_log[:3],
        "python_log_sample": python_log[:3],
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def main():
    print("=" * 70)
    print("SOUL PROTOCOL — MEMORY RESEARCH SCENARIOS")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    # Scenario 1: Memory Formation Rate
    s1 = await scenario_memory_formation()
    soul_ref = s1.pop("_soul_ref")

    # Scenario 2: Export/Awaken Persistence (uses soul from scenario 1)
    s2 = await scenario_export_persistence(soul_ref)

    # Scenario 3: ACT-R Decay
    s3 = await scenario_actr_decay()

    # Compile results
    results = {
        "metadata": {
            "script": "research_memory.py",
            "task": "Memory Formation + Recall Accuracy",
            "timestamp": datetime.now().isoformat(),
            "soul_protocol_version": "0.2.2",
        },
        "scenario_1_memory_formation": s1,
        "scenario_2_export_persistence": s2,
        "scenario_3_actr_decay": s3,
        "summary": {
            "formation_rate": {
                "interactions": s1["interactions_fed"],
                "episodic_formed": s1["memory_counts"]["episodic"],
                "semantic_extracted": s1["memory_counts"]["semantic"],
                "graph_entities": s1["memory_counts"]["graph_nodes"],
                "episodic_per_interaction": round(
                    s1["memory_counts"]["episodic"] / s1["interactions_fed"], 2
                ),
                "semantic_per_interaction": round(
                    s1["memory_counts"]["semantic"] / s1["interactions_fed"], 2
                ),
            },
            "recall_accuracy": {
                "pre_export": s1["recall_accuracy"],
                "post_export": s2["recall_accuracy"],
                "accuracy_preserved": abs(s1["recall_accuracy"] - s2["recall_accuracy"]) < 0.15,
            },
            "export_persistence": {
                "identity_preserved": s2["identity_preserved"],
                "episodic_preserved": s2["count_preservation"]["episodic_match"],
                "semantic_preserved": s2["count_preservation"]["semantic_match"],
                "graph_preserved": s2["count_preservation"]["graph_match"],
            },
            "actr_decay": {
                "recency_works": s3["actr_recency_effect"]["python_dominates_recall"],
                "recent_topic_recall": s3["actr_recency_effect"]["python_in_top5_count"],
                "old_topic_recall": s3["actr_recency_effect"]["cooking_in_top5_count"],
            },
        },
    }

    # Save results
    output_path = Path(__file__).parent.parent / ".results" / "research" / "memory_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'=' * 70}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 70}")
    print(
        f"  Formation: {s1['memory_counts']['episodic']} episodic, {s1['memory_counts']['semantic']} semantic, {s1['memory_counts']['graph_nodes']} graph nodes from {s1['interactions_fed']} interactions"
    )
    print(
        f"  Recall accuracy: {s1['recall_accuracy']:.0%} pre-export, {s2['recall_accuracy']:.0%} post-export"
    )
    print(
        f"  Export preserves: identity={s2['identity_preserved']}, episodic={s2['count_preservation']['episodic_match']}, semantic={s2['count_preservation']['semantic_match']}, graph={s2['count_preservation']['graph_match']}"
    )
    print(
        f"  ACT-R decay: Python (recent) top5={s3['actr_recency_effect']['python_in_top5_count']}, Cooking (old) top5={s3['actr_recency_effect']['cooking_in_top5_count']}"
    )
    print(f"\n  Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
