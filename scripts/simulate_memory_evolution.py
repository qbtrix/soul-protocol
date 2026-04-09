#!/usr/bin/env python3
# simulate_memory_evolution.py — Simulates 100 interactions to demonstrate
# memory compression, archival storage, and temporal graph evolution.
# Created: 2026-03-06

"""
Simulate 100 interactions and show:
  - Memory compression working (before/after counts)
  - Archival storage growing
  - Temporal graph evolution
  - Final stats summary
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta

from soul_protocol.runtime.memory.archival import ArchivalMemoryStore, ConversationArchive
from soul_protocol.runtime.memory.compression import MemoryCompressor
from soul_protocol.runtime.memory.graph import KnowledgeGraph
from soul_protocol.runtime.types import MemoryEntry, MemoryType

# Simulated conversation topics for variety
TOPICS = [
    ("python", "I use Python for data analysis", "technology"),
    ("rust", "I'm learning Rust for systems programming", "technology"),
    ("cooking", "I love cooking Italian food", "hobby"),
    ("music", "I play guitar in a band", "hobby"),
    ("work", "I work at a startup called Acme", "career"),
    ("travel", "I live in Tokyo and love it", "location"),
    ("books", "My favorite book is Dune", "preference"),
    ("fitness", "I run every morning before work", "habit"),
    ("family", "My sister Alice is a doctor", "relationship"),
    ("tech", "I'm building a side project with FastAPI", "project"),
]


async def run_simulation():
    print("=" * 60)
    print("  MEMORY EVOLUTION SIMULATION")
    print("  100 interactions with compression, archival, and graph")
    print("=" * 60)
    print()

    # --- Setup ---
    archival = ArchivalMemoryStore()
    compressor = MemoryCompressor()
    graph = KnowledgeGraph()

    # Track stats
    memories_created = 0
    archives_created = 0
    graph_edges_added = 0
    session_memories: list[MemoryEntry] = []
    all_memories: list[MemoryEntry] = []

    base_time = datetime(2026, 1, 1, 8, 0, 0)

    print("[Phase 1] Simulating 100 interactions...")
    print("-" * 40)

    for i in range(100):
        topic_idx = i % len(TOPICS)
        topic_name, user_msg, entity_type = TOPICS[topic_idx]

        # Vary the message slightly each cycle
        cycle = i // len(TOPICS)
        user_input = f"{user_msg} (conversation {i + 1}, cycle {cycle})"

        interaction_time = base_time + timedelta(hours=i)

        # Create memory entry
        mem = MemoryEntry(
            id=uuid.uuid4().hex[:12],
            type=MemoryType.SEMANTIC,
            content=f"[{topic_name}] {user_input}",
            importance=max(1, min(10, 5 + (i % 3) - 1)),
            created_at=interaction_time,
        )
        session_memories.append(mem)
        all_memories.append(mem)
        memories_created += 1

        # Update knowledge graph with temporal edges
        # Every 10 interactions, "evolve" a relationship
        if i % 20 == 0 and i > 0:
            # Expire old relationship
            graph.expire_relationship(
                "user", topic_name, "interested_in", expire_at=interaction_time
            )
            # Add new stronger relationship
            graph.add_relationship(
                "user",
                topic_name,
                "expert_in",
                valid_from=interaction_time,
            )
            graph_edges_added += 1
        else:
            graph.add_relationship(
                "user",
                topic_name,
                "interested_in",
                valid_from=interaction_time,
            )
            graph_edges_added += 1

        # Every 10 interactions, archive the session
        if (i + 1) % 10 == 0:
            session_start = base_time + timedelta(hours=i - 9)
            session_end = interaction_time

            # Summarize session memories
            summary = compressor.summarize_memories(session_memories, max_tokens=100)

            archive = ConversationArchive(
                id=f"arc-{archives_created + 1:03d}",
                start_time=session_start,
                end_time=session_end,
                summary=summary,
                key_moments=[m.content for m in session_memories[:3]],
                participants=["user", "Aria"],
                memory_refs=[m.id for m in session_memories],
            )
            archival.archive_conversation(archive)
            archives_created += 1
            session_memories = []

            if (i + 1) % 25 == 0:
                print(
                    f"  [{i + 1}/100] {archives_created} archives, "
                    f"{memories_created} memories, {graph_edges_added} graph edges"
                )

    print(f"\n  Simulation complete: {memories_created} memories generated")
    print()

    # --- Phase 2: Compression ---
    print("[Phase 2] Memory Compression")
    print("-" * 40)

    before_count = len(all_memories)
    print(f"  Before compression: {before_count} memories")

    # Deduplicate
    deduped = compressor.deduplicate(all_memories, similarity_threshold=0.7)
    print(
        f"  After deduplication: {len(deduped)} memories "
        f"({before_count - len(deduped)} duplicates removed)"
    )

    # Prune by importance
    keep, pruned = compressor.prune_by_importance(deduped, min_importance=4)
    print(f"  After pruning (min_importance=4): {len(keep)} kept, {len(pruned)} pruned")

    # Export split
    inline, external = compressor.compress_for_export(keep, max_inline=20)
    print(f"  Export split: {len(inline)} inline, {len(external)} external")

    # Full summary
    summary = compressor.summarize_memories(keep, max_tokens=200)
    print(f"\n  Compressed summary ({len(summary.split())} words):")
    for line in summary.split("\n")[:8]:
        print(f"    {line}")
    if len(summary.split("\n")) > 8:
        print(f"    ... ({len(summary.split(chr(10))) - 8} more lines)")
    print()

    # --- Phase 3: Archival ---
    print("[Phase 3] Archival Storage")
    print("-" * 40)
    print(f"  Total archives: {archival.count()}")

    # Search demo
    results = archival.search_archives("Python data", limit=3)
    print(f"  Search 'Python data': {len(results)} results")
    for r in results[:2]:
        print(f"    - {r.id}: {r.summary[:80]}...")

    # Date range demo
    mid_point = base_time + timedelta(hours=50)
    range_results = archival.get_by_date_range(
        mid_point - timedelta(hours=10),
        mid_point + timedelta(hours=10),
    )
    print(f"  Archives around hour 50: {len(range_results)} found")
    print()

    # --- Phase 4: Temporal Graph ---
    print("[Phase 4] Temporal Knowledge Graph")
    print("-" * 40)
    print(f"  Entities: {len(graph.entities())}")

    # Point-in-time queries
    early = graph.as_of_date(base_time + timedelta(hours=5))
    mid = graph.as_of_date(base_time + timedelta(hours=50))
    late = graph.as_of_date(base_time + timedelta(hours=95))
    print(f"  Relationships at hour 5:  {len(early)}")
    print(f"  Relationships at hour 50: {len(mid)}")
    print(f"  Relationships at hour 95: {len(late)}")

    # Evolution demo
    evolution = graph.relationship_evolution("user", "python")
    print(f"\n  Evolution of user->python: {len(evolution)} stages")
    for stage in evolution:
        end = stage["valid_to"].isoformat() if stage["valid_to"] else "present"
        print(f"    {stage['valid_from'].isoformat()} -> {end}: {stage['relation']}")
    print()

    # --- Final Stats ---
    print("=" * 60)
    print("  FINAL STATS")
    print("=" * 60)
    print("  Interactions simulated:    100")
    print(f"  Raw memories created:      {memories_created}")
    print(f"  After dedup:               {len(deduped)}")
    print(f"  After pruning:             {len(keep)}")
    print(f"  Archives created:          {archives_created}")
    print(f"  Graph entities:            {len(graph.entities())}")
    print(f"  Graph total edges:         {graph_edges_added}")
    print(
        f"  Compression ratio:         {len(keep)}/{before_count} "
        f"({len(keep) / before_count:.1%} retained)"
    )
    print()


if __name__ == "__main__":
    asyncio.run(run_simulation())
