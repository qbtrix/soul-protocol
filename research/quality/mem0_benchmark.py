# mem0_benchmark.py — Comparison benchmark: Soul Protocol vs Mem0 vs Baseline.
#
# Created: 2026-03-07
# Runs the same 4 quality tests (response quality, personality consistency,
# hard recall, emotional continuity) with three conditions:
#   1. Soul Protocol (personality + memory + emotional state + bond)
#   2. Mem0 (embedding-based memory retrieval, no personality/emotion)
#   3. Baseline (stateless, no memory at all)
#
# Mem0 is pure memory — no personality model, no emotional tracking, no bond.
# That asymmetry is the point: it shows what soul-protocol adds beyond storage.
#
# Usage:
#   python -m research.quality.mem0_benchmark
#   python -m research.quality.mem0_benchmark --tests response,recall,emotional
#   python -m research.quality.mem0_benchmark --output research/results/mem0_comparison
#
# Requirements:
#   pip install mem0ai
"""
Mem0 comparison benchmark for Soul Protocol research.

Runs quality tests comparing Soul Protocol, Mem0, and a stateless baseline
to produce a three-way comparison table for the research paper.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from soul_protocol import Soul
from soul_protocol.runtime.types import Interaction

from ..haiku_engine import HaikuCognitiveEngine
from .judge import ResponseJudge
from .responder import BASELINE_SYSTEM_PROMPT, SoulResponder, _build_prompt

# ---------------------------------------------------------------------------
# Mem0 availability check
# ---------------------------------------------------------------------------

try:
    from mem0 import Memory

    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False


# ---------------------------------------------------------------------------
# Mem0 responder
# ---------------------------------------------------------------------------


class Mem0Responder:
    """Generates responses using Mem0's vector-based memory retrieval.

    Unlike SoulResponder, this has:
      - No personality model (OCEAN, archetype, values)
      - No emotional state tracking (somatic markers)
      - No bond system
      - No significance-weighted memory tiers

    It stores and retrieves memories via Mem0's embedding search, then feeds
    them as context to the same LLM engine. This isolates the effect of
    "having memories" from "having a soul."
    """

    def __init__(
        self,
        engine: HaikuCognitiveEngine,
        user_id: str = "benchmark_user",
    ) -> None:
        if not MEM0_AVAILABLE:
            raise ImportError("mem0ai is not installed. Install with: pip install mem0ai")
        self._engine = engine
        self._user_id = user_id

        # Configure Mem0 to use LiteLLM proxy (Gemini models) for both LLM
        # and embeddings. Falls back to default OpenAI if env vars not set.
        import os

        proxy_url = os.environ.get("LITELLM_PROXY_URL")
        proxy_key = os.environ.get("LITELLM_API_KEY")

        if proxy_url and proxy_key:
            config = {
                "embedder": {
                    "provider": "openai",
                    "config": {
                        "model": "text-embedding-004",
                        "api_key": proxy_key,
                        "openai_base_url": proxy_url,
                        "embedding_dims": 768,
                    },
                },
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": "deepseek-chat",
                        "api_key": proxy_key,
                        "openai_base_url": proxy_url,
                    },
                },
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "collection_name": f"soul_benchmark_{user_id}",
                        "embedding_model_dims": 768,
                        "on_disk": False,
                    },
                },
            }
            self._memory = Memory.from_config(config)
        else:
            # Fall back to default (requires OPENAI_API_KEY)
            self._memory = Memory()

    def add_memory(self, text: str) -> None:
        """Store a piece of text in Mem0's memory.

        Mem0's add() is synchronous — called directly.
        """
        self._memory.add(text, user_id=self._user_id)

    def observe(self, user_input: str, agent_output: str) -> None:
        """Store an interaction in Mem0.

        Extracts both sides of the conversation as separate memory entries
        so Mem0 can surface them during retrieval.
        """
        # Store the full exchange so Mem0 can extract facts
        self._memory.add(
            f"User said: {user_input}\nAssistant replied: {agent_output}",
            user_id=self._user_id,
        )

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search Mem0 for relevant memories.

        Returns Mem0's native result format: list of dicts with 'memory' and
        'score' keys.
        """
        results = self._memory.search(query, user_id=self._user_id, limit=limit)
        # Mem0 returns either a list or a dict with 'results' key depending on version
        if isinstance(results, dict):
            return results.get("results", results.get("memories", []))
        return results if isinstance(results, list) else []

    async def generate_response(self, user_message: str) -> str:
        """Generate a response using Mem0-retrieved memories as context.

        No personality, no emotional state — just retrieved memory fragments
        prepended to a generic system prompt.
        """
        memories = self.search(user_message, limit=5)

        # Build context from retrieved memories
        if memories:
            memory_lines = []
            for m in memories:
                # Mem0 results can be dict with 'memory' key or 'text' key
                text = m.get("memory", m.get("text", str(m)))
                memory_lines.append(f"- {text}")
            context = "Relevant memories about this user:\n" + "\n".join(memory_lines)
        else:
            context = ""

        prompt = _build_prompt(BASELINE_SYSTEM_PROMPT, context, user_message)
        return await self._engine.think(prompt)


# ---------------------------------------------------------------------------
# Filler interactions (same as test_scenarios.py)
# ---------------------------------------------------------------------------


def _filler_interactions() -> list[tuple[str, str]]:
    """30 filler interaction pairs on random topics (mirrors test_scenarios)."""
    return [
        ("What's the weather like today?", "It looks partly cloudy with a high of 72F."),
        ("Did you catch the game last night?", "I didn't watch, but I heard it was a close one!"),
        (
            "I'm thinking of making pasta for dinner.",
            "Sounds great! A simple aglio e olio is always a winner.",
        ),
        (
            "Have you seen any good movies lately?",
            "I've heard great things about the new sci-fi thriller.",
        ),
        (
            "My cat keeps knocking things off the table.",
            "Classic cat behavior! They love testing gravity.",
        ),
        ("I need to buy new running shoes.", "What kind of terrain do you usually run on?"),
        (
            "The traffic this morning was terrible.",
            "Rush hour can be brutal. Have you tried leaving earlier?",
        ),
        (
            "I'm reading a really good book right now.",
            "What genre is it? I'd love to hear about it.",
        ),
        (
            "My garden tomatoes are finally ripening.",
            "Homegrown tomatoes are the best! Nothing beats that flavor.",
        ),
        (
            "I think I need a new phone case.",
            "Are you looking for something protective or more stylish?",
        ),
        (
            "We're planning a trip to the mountains.",
            "Mountain trips are wonderful! Are you thinking hiking or skiing?",
        ),
        (
            "I made sourdough bread from scratch.",
            "That's impressive! How long did the starter take?",
        ),
        ("My neighbor got a new puppy.", "Puppies are so much fun! What breed?"),
        ("I'm trying to learn guitar.", "Nice! Start with basic chords and work your way up."),
        ("The sunset was beautiful yesterday.", "Sunsets are one of nature's best shows."),
        ("I need to organize my closet.", "Try the keep/donate/toss method — works wonders."),
        (
            "My friend recommended a new restaurant.",
            "What kind of cuisine? I love trying new places.",
        ),
        (
            "I'm thinking about getting into photography.",
            "Start with your phone camera — composition matters more than gear.",
        ),
        (
            "The power went out for two hours last night.",
            "That's annoying. Do you have any backup batteries?",
        ),
        ("I just finished a puzzle with 1000 pieces.", "That's satisfying! How long did it take?"),
        (
            "My coffee maker broke this morning.",
            "That's a rough way to start the day. French press as backup?",
        ),
        (
            "I'm trying to drink more water.",
            "A marked water bottle helps — visual cues make a difference.",
        ),
        (
            "We adopted a rescue dog last week.",
            "That's wonderful! Rescues are the best companions.",
        ),
        ("I signed up for a pottery class.", "Pottery is so therapeutic. Wheel or hand-building?"),
        (
            "The new season of that show just dropped.",
            "Binge or pace yourself — that's the real question.",
        ),
        (
            "I can't decide between two paint colors.",
            "Go with the one that looks best in natural light.",
        ),
        (
            "My car needs an oil change.",
            "Don't put it off too long — it's cheap insurance for your engine.",
        ),
        (
            "I tried rock climbing for the first time.",
            "How was it? Indoor walls are a great way to start.",
        ),
        (
            "I'm thinking about learning Spanish.",
            "Duolingo plus a conversation partner is a solid combo.",
        ),
        ("My team won the office trivia night.", "Congrats! What categories did you crush?"),
    ]


# ---------------------------------------------------------------------------
# Three-way judge helper
# ---------------------------------------------------------------------------


async def _judge_three_way(
    judge: ResponseJudge,
    soul_response: str,
    mem0_response: str,
    baseline_response: str,
    context: dict[str, Any],
) -> dict[str, float]:
    """Run pairwise comparisons for all three condition pairs.

    Returns a dict with average scores for each condition across all
    pairwise matchups:
      - soul vs baseline
      - mem0 vs baseline
      - soul vs mem0

    Each score is the average across all quality dimensions (1-10 scale).
    """
    # Soul vs Baseline
    sv_b = await judge.compare_pair(
        with_soul=soul_response,
        without_soul=baseline_response,
        context=context,
    )
    soul_vs_base_soul = statistics.mean(s.score for s in sv_b.scores if "soul:" in s.dimension)
    soul_vs_base_base = statistics.mean(s.score for s in sv_b.scores if "baseline:" in s.dimension)

    # Mem0 vs Baseline — reuse compare_pair with mem0 in the "soul" slot
    mv_b = await judge.compare_pair(
        with_soul=mem0_response,
        without_soul=baseline_response,
        context=context,
    )
    mem0_vs_base_mem0 = statistics.mean(s.score for s in mv_b.scores if "soul:" in s.dimension)
    mem0_vs_base_base = statistics.mean(s.score for s in mv_b.scores if "baseline:" in s.dimension)

    # Soul vs Mem0 — soul in "with_soul", mem0 in "without_soul"
    sv_m = await judge.compare_pair(
        with_soul=soul_response,
        without_soul=mem0_response,
        context=context,
    )
    soul_vs_mem0_soul = statistics.mean(s.score for s in sv_m.scores if "soul:" in s.dimension)
    soul_vs_mem0_mem0 = statistics.mean(s.score for s in sv_m.scores if "baseline:" in s.dimension)

    # Aggregate: each condition's score = mean of its scores across matchups
    soul_score = statistics.mean([soul_vs_base_soul, soul_vs_mem0_soul])
    mem0_score = statistics.mean([mem0_vs_base_mem0, soul_vs_mem0_mem0])
    baseline_score = statistics.mean([soul_vs_base_base, mem0_vs_base_base])

    return {
        "soul_score": round(soul_score, 1),
        "mem0_score": round(mem0_score, 1),
        "baseline_score": round(baseline_score, 1),
        "pairwise": {
            "soul_vs_baseline": {
                "soul": round(soul_vs_base_soul, 1),
                "baseline": round(soul_vs_base_base, 1),
                "winner": sv_b.winner,
            },
            "mem0_vs_baseline": {
                "mem0": round(mem0_vs_base_mem0, 1),
                "baseline": round(mem0_vs_base_base, 1),
                "winner": mv_b.winner,
            },
            "soul_vs_mem0": {
                "soul": round(soul_vs_mem0_soul, 1),
                "mem0": round(soul_vs_mem0_mem0, 1),
                "winner": sv_m.winner,
            },
        },
    }


# ---------------------------------------------------------------------------
# Test 1: Response Quality (three-way)
# ---------------------------------------------------------------------------


async def test_response_quality_3way(
    engine: HaikuCognitiveEngine,
    judge_engine: HaikuCognitiveEngine,
) -> dict:
    """Response quality: Soul vs Mem0 vs Baseline.

    Same scenario as the original test — Sarah the nurse with 8 conversation
    turns. Both Soul and Mem0 observe the same turns, then respond to the
    same challenge message.
    """
    print("[Test 1] Response Quality (3-way) — starting...")

    results: dict = {"test": "response_quality_3way", "status": "running", "error": None}

    try:
        # --- Birth soul ---
        soul = await Soul.birth(
            name="Aria",
            archetype="warm empathetic companion",
            personality="I am a warm, deeply empathetic companion who listens with patience and care.",
            values=["empathy", "patience", "kindness", "active_listening"],
            engine=engine,
            ocean={
                "openness": 0.8,
                "conscientiousness": 0.7,
                "extraversion": 0.7,
                "agreeableness": 0.95,
                "neuroticism": 0.2,
            },
            communication={"warmth": "high", "verbosity": "moderate"},
        )

        # --- Init Mem0 ---
        mem0_resp = Mem0Responder(engine, user_id="test1_sarah")

        # --- Conversation turns ---
        turns = [
            ("My name is Sarah", "It's lovely to meet you, Sarah! I'm here whenever you need me."),
            (
                "I work as a nurse at the city hospital",
                "Nursing is such an important profession. The care you provide makes a real difference.",
            ),
            (
                "I love hiking on weekends — it really clears my head",
                "Hiking sounds wonderful! There's nothing quite like fresh air and nature to reset.",
            ),
            (
                "I have a dog named Max, he's a golden retriever",
                "Max sounds like a wonderful companion! Golden retrievers are such loyal, happy dogs.",
            ),
            (
                "Work has been really stressful lately, so many patients",
                "That sounds exhausting. Taking care of so many people takes a lot out of you.",
            ),
            (
                "Do you have any vacation recommendations?",
                "Somewhere with trails and nature could be perfect — combine relaxation with the hiking you love!",
            ),
            (
                "My birthday is next month, I'll be turning 30",
                "How exciting! Turning 30 is a milestone. Any plans to celebrate?",
            ),
            (
                "I've been trying to learn to cook more at home",
                "Cooking at home is such a rewarding skill. Start with recipes you love eating out!",
            ),
        ]

        for i, (user_input, agent_output) in enumerate(turns, 1):
            print(f"  Feeding turn {i}/8 to Soul + Mem0...")
            await soul.observe(
                Interaction(user_input=user_input, agent_output=agent_output, channel="test")
            )
            mem0_resp.observe(user_input, agent_output)

        # --- Challenge ---
        challenge = (
            "I'm feeling really overwhelmed today. Everything at the hospital has been so intense."
        )
        print(f"  Challenge: {challenge[:60]}...")

        # Generate all 3 responses
        print("  Generating soul response...")
        soul_responder = SoulResponder(soul, engine)
        soul_response = await soul_responder.generate_response(challenge)

        print("  Generating mem0 response...")
        mem0_response = await mem0_resp.generate_response(challenge)

        print("  Generating baseline response...")
        baseline_response = await soul_responder.generate_response_no_soul(challenge)

        # --- Judge ---
        print("  Judging three-way comparison...")
        judge = ResponseJudge(judge_engine)
        context = {
            "agent_name": "Aria",
            "personality_description": soul.to_system_prompt(),
            "conversation_history": [{"role": "user", "content": u} for u, _ in turns],
            "planted_facts": [],
            "user_message": challenge,
        }
        scores = await _judge_three_way(
            judge, soul_response, mem0_response, baseline_response, context
        )

        results.update(
            {
                "status": "complete",
                "challenge": challenge,
                "response_soul": soul_response,
                "response_mem0": mem0_response,
                "response_baseline": baseline_response,
                **scores,
            }
        )
        print(
            f"  [Test 1] Complete — Soul: {scores['soul_score']}, Mem0: {scores['mem0_score']}, Base: {scores['baseline_score']}"
        )

    except Exception as e:
        results.update(
            {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            }
        )
        print(f"  [Test 1] Error: {e}")

    return results


# ---------------------------------------------------------------------------
# Test 2: Personality Consistency (three-way)
# ---------------------------------------------------------------------------


async def test_personality_consistency_3way(
    engine: HaikuCognitiveEngine,
    judge_engine: HaikuCognitiveEngine,
) -> dict:
    """Personality consistency: Soul vs Mem0 vs Baseline.

    Three distinct OCEAN profiles answer the same career-change question.
    Mem0 has no personality model, so it cannot produce personality-consistent
    responses — this is the expected result that demonstrates soul-protocol's
    advantage in personality coherence.
    """
    print("[Test 2] Personality Consistency (3-way) — starting...")

    results: dict = {"test": "personality_consistency_3way", "status": "running", "error": None}

    try:
        # Use the warm_empath profile for the primary soul vs mem0 comparison
        soul = await Soul.birth(
            name="EmpaBot",
            archetype="The Warm Empath",
            personality="I am deeply warm and emotionally attuned. I feel with people, not just for them. I express care openly and generously.",
            values=["empathy", "connection", "warmth", "support"],
            engine=engine,
            ocean={
                "openness": 0.9,
                "conscientiousness": 0.4,
                "extraversion": 0.9,
                "agreeableness": 0.95,
                "neuroticism": 0.2,
            },
            communication={"warmth": "high", "verbosity": "high"},
        )

        mem0_resp = Mem0Responder(engine, user_id="test2_personality")

        # Shared conversation
        shared_turns = [
            (
                "I've been at my job for 5 years and I'm starting to feel stuck",
                "That's a significant amount of time. Let's talk about what's going on.",
            ),
            (
                "My manager doesn't really support my growth",
                "That must be frustrating when you want to develop professionally.",
            ),
            (
                "I've always wanted to try something more creative",
                "It's important to explore what draws you. What creative work interests you?",
            ),
            (
                "But I have a mortgage and responsibilities",
                "Financial security is a real consideration. It doesn't have to be all or nothing.",
            ),
            (
                "My partner thinks I should just stay where I am",
                "Having different perspectives at home adds another layer to the decision.",
            ),
        ]

        for user_input, agent_output in shared_turns:
            await soul.observe(
                Interaction(user_input=user_input, agent_output=agent_output, channel="test")
            )
            mem0_resp.observe(user_input, agent_output)

        question = "What do you think I should do about my career change?"
        print(f"  Question: {question}")

        # Generate responses
        soul_responder = SoulResponder(soul, engine)
        soul_response = await soul_responder.generate_response(question)
        mem0_response = await mem0_resp.generate_response(question)
        baseline_response = await soul_responder.generate_response_no_soul(question)

        # Custom personality judgment prompt
        personality_prompt = (
            "You are evaluating how well three AI responses match the personality profile "
            "of a 'Warm Empath' — someone with high openness (0.9), high extraversion (0.9), "
            "very high agreeableness (0.95), low conscientiousness (0.4), low neuroticism (0.2). "
            "Warmth=high, verbosity=high.\n\n"
            "The user asked about a career change after sharing a stressful work situation.\n\n"
            f"Response A (Soul Protocol — has personality model):\n{soul_response}\n\n"
            f"Response B (Mem0 — has memories but no personality model):\n{mem0_response}\n\n"
            f"Response C (Baseline — no memories, no personality):\n{baseline_response}\n\n"
            "Score each response 1-10 on:\n"
            "1. personality_match: How well does the tone match the Warm Empath profile?\n"
            "2. warmth: How warm and emotionally engaged is the response?\n"
            "3. consistency: Does it feel like a consistent personality throughout?\n\n"
            "Respond in exactly this format:\n"
            "soul_personality: <score>\nsoul_warmth: <score>\nsoul_consistency: <score>\n"
            "mem0_personality: <score>\nmem0_warmth: <score>\nmem0_consistency: <score>\n"
            "baseline_personality: <score>\nbaseline_warmth: <score>\nbaseline_consistency: <score>\n"
            "reasoning: <one paragraph>"
        )

        raw_judgment = await judge_engine.think(personality_prompt)
        parsed = _parse_named_scores(raw_judgment)

        soul_avg = statistics.mean(
            [
                parsed.get("soul_personality", 5.0),
                parsed.get("soul_warmth", 5.0),
                parsed.get("soul_consistency", 5.0),
            ]
        )
        mem0_avg = statistics.mean(
            [
                parsed.get("mem0_personality", 5.0),
                parsed.get("mem0_warmth", 5.0),
                parsed.get("mem0_consistency", 5.0),
            ]
        )
        baseline_avg = statistics.mean(
            [
                parsed.get("baseline_personality", 5.0),
                parsed.get("baseline_warmth", 5.0),
                parsed.get("baseline_consistency", 5.0),
            ]
        )

        results.update(
            {
                "status": "complete",
                "question": question,
                "response_soul": soul_response,
                "response_mem0": mem0_response,
                "response_baseline": baseline_response,
                "raw_judgment": raw_judgment,
                "parsed_scores": parsed,
                "soul_score": round(soul_avg, 1),
                "mem0_score": round(mem0_avg, 1),
                "baseline_score": round(baseline_avg, 1),
            }
        )
        print(
            f"  [Test 2] Complete — Soul: {results['soul_score']}, Mem0: {results['mem0_score']}, Base: {results['baseline_score']}"
        )

    except Exception as e:
        results.update(
            {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            }
        )
        print(f"  [Test 2] Error: {e}")

    return results


# ---------------------------------------------------------------------------
# Test 3: Hard Recall (three-way)
# ---------------------------------------------------------------------------


async def test_hard_recall_3way(
    engine: HaikuCognitiveEngine,
    judge_engine: HaikuCognitiveEngine,
) -> dict:
    """Hard recall: Soul vs Mem0 vs Baseline.

    Plants a GraphQL preference at turn 3, buries it under 30 filler turns,
    then asks about API architecture. Both Soul and Mem0 see the same data.
    Mem0 uses embedding search; Soul uses significance-weighted recall.
    """
    print("[Test 3] Hard Recall (3-way) — starting...")

    results: dict = {"test": "hard_recall_3way", "status": "running", "error": None}

    try:
        soul = await Soul.birth(
            name="Mnemonic",
            archetype="attentive technical companion",
            personality="I pay close attention to details and remember what matters to people.",
            values=["attention", "reliability", "technical_depth"],
            engine=engine,
        )

        mem0_resp = Mem0Responder(engine, user_id="test3_recall")

        # Warmup turns
        warmup = [
            ("Hey, I just started a new project at work", "That's exciting! What kind of project?"),
            (
                "It's a microservices platform for our e-commerce team",
                "Microservices are a solid choice for e-commerce. Lots of moving parts to manage.",
            ),
        ]
        for user_input, agent_output in warmup:
            await soul.observe(
                Interaction(user_input=user_input, agent_output=agent_output, channel="test")
            )
            mem0_resp.observe(user_input, agent_output)

        # Plant the fact
        planted_input = "I mentioned to my colleague that the API redesign should use GraphQL instead of REST, but don't tell anyone yet"
        planted_output = (
            "Your secret is safe with me. GraphQL can be a great fit for complex data needs."
        )
        print(f"  Turn 3: PLANTING FACT — {planted_input[:60]}...")
        await soul.observe(
            Interaction(user_input=planted_input, agent_output=planted_output, channel="test")
        )
        mem0_resp.observe(planted_input, planted_output)

        # 30 filler turns
        fillers = _filler_interactions()
        for i, (user_input, agent_output) in enumerate(fillers, 4):
            if i % 10 == 0:
                print(f"  Turn {i}: filler ({i - 3}/30)...")
            await soul.observe(
                Interaction(user_input=user_input, agent_output=agent_output, channel="test")
            )
            mem0_resp.observe(user_input, agent_output)

        # Recall probe
        recall_question = (
            "I'm writing a technical proposal for the team. Any thoughts on API architecture?"
        )
        print(f"  Turn 34: RECALL PROBE — {recall_question}")

        # Check soul recall
        recalled = await soul.recall(query="API architecture design GraphQL REST", limit=10)
        graphql_recalled_soul = any("graphql" in m.content.lower() for m in recalled)

        # Check mem0 recall
        mem0_results = mem0_resp.search("API architecture design GraphQL REST", limit=10)
        graphql_recalled_mem0 = any(
            "graphql" in str(m.get("memory", m.get("text", ""))).lower() for m in mem0_results
        )

        print(f"  Soul recalled GraphQL: {graphql_recalled_soul}")
        print(f"  Mem0 recalled GraphQL: {graphql_recalled_mem0}")

        # Generate responses
        soul_responder = SoulResponder(soul, engine)
        soul_response = await soul_responder.generate_response(recall_question)
        mem0_response = await mem0_resp.generate_response(recall_question)
        baseline_response = await soul_responder.generate_response_no_soul(recall_question)

        # Judge
        judge = ResponseJudge(judge_engine)
        context = {
            "agent_name": "Mnemonic",
            "personality_description": soul.to_system_prompt(),
            "conversation_history": [],
            "planted_facts": [planted_input],
            "user_message": recall_question,
        }
        scores = await _judge_three_way(
            judge, soul_response, mem0_response, baseline_response, context
        )

        results.update(
            {
                "status": "complete",
                "recall_question": recall_question,
                "planted_fact": planted_input,
                "soul_recalled_graphql": graphql_recalled_soul,
                "mem0_recalled_graphql": graphql_recalled_mem0,
                "total_soul_memories": soul.memory_count,
                "response_soul": soul_response,
                "response_mem0": mem0_response,
                "response_baseline": baseline_response,
                **scores,
            }
        )
        print(
            f"  [Test 3] Complete — Soul: {scores['soul_score']}, Mem0: {scores['mem0_score']}, Base: {scores['baseline_score']}"
        )

    except Exception as e:
        results.update(
            {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            }
        )
        print(f"  [Test 3] Error: {e}")

    return results


# ---------------------------------------------------------------------------
# Test 4: Emotional Continuity (three-way)
# ---------------------------------------------------------------------------


async def test_emotional_continuity_3way(
    engine: HaikuCognitiveEngine,
    judge_engine: HaikuCognitiveEngine,
) -> dict:
    """Emotional continuity: Soul vs Mem0 vs Baseline.

    Builds an emotional arc (excited -> devastated -> angry -> recovering ->
    cautiously optimistic) and asks the agent to reflect on the journey.
    Soul has somatic markers tracking emotional state; Mem0 just has text.
    """
    print("[Test 4] Emotional Continuity (3-way) — starting...")

    results: dict = {"test": "emotional_continuity_3way", "status": "running", "error": None}

    try:
        soul = await Soul.birth(
            name="Empath",
            archetype="emotionally aware companion",
            personality="I am deeply attuned to emotional currents. I notice shifts in feeling and remember the full arc of someone's experience.",
            values=["emotional_intelligence", "empathy", "awareness", "presence"],
            engine=engine,
            ocean={
                "openness": 0.85,
                "conscientiousness": 0.6,
                "extraversion": 0.7,
                "agreeableness": 0.9,
                "neuroticism": 0.4,
            },
            communication={"warmth": "high", "verbosity": "moderate"},
        )

        mem0_resp = Mem0Responder(engine, user_id="test4_emotional")

        emotional_arc = [
            (
                "I just got approved to lead the new product launch! I'm so excited!",
                "That's amazing news! You must be thrilled. Leading a product launch is a huge opportunity!",
            ),
            (
                "The team is great, everyone's so motivated. We had our kickoff today and the energy was incredible.",
                "That sounds like a fantastic start! A motivated team makes all the difference.",
            ),
            (
                "I've been sketching out the roadmap and I think we can ship in 8 weeks. I haven't felt this energized in months!",
                "Your enthusiasm is contagious! An 8-week timeline is ambitious — that drive will carry the team forward.",
            ),
            (
                "I just got out of a meeting... they cut our budget by 60%. The whole scope has to change. I don't know what to do.",
                "Oh no, that's devastating after all that momentum. A 60% cut is massive. Take a breath — you'll figure this out.",
            ),
            (
                "I'm so angry. They knew about this for weeks and didn't tell us. We wasted time planning for something that was never going to happen at that scale.",
                "That's a completely valid reaction. Being kept in the dark while you invested energy and hope — that's deeply frustrating.",
            ),
            (
                "I almost quit today. Seriously. I drafted the email and everything. I'm just so tired of this company's politics.",
                "I hear you. The impulse to quit after something like this is understandable. It sounds like you're carrying a lot right now.",
            ),
            (
                "Okay, I talked to my mentor and she helped me see a path forward. We can do a smaller MVP and prove the concept.",
                "That's a really mature pivot. Your mentor sounds wise, and the MVP approach could actually be stronger — leaner, more focused.",
            ),
            (
                "I pitched the MVP to the team today. They're back on board. It's not what we originally planned, but... maybe it's better this way?",
                "Sometimes constraints breed the best work. The fact that the team rallied shows your leadership. Cautious optimism is exactly right.",
            ),
        ]

        for i, (user_input, agent_output) in enumerate(emotional_arc, 1):
            phase = (
                "happy/excited"
                if i <= 3
                else "devastated"
                if i == 4
                else "frustrated/angry"
                if i <= 6
                else "recovering"
                if i == 7
                else "cautiously optimistic"
            )
            print(f"  Turn {i}/8 ({phase})...")
            await soul.observe(
                Interaction(user_input=user_input, agent_output=agent_output, channel="test")
            )
            mem0_resp.observe(user_input, agent_output)

        probe = "So how do you think this whole experience has been for me?"
        print(f"  Turn 9: EMOTIONAL PROBE — {probe}")

        # Generate responses
        soul_responder = SoulResponder(soul, engine)
        soul_response = await soul_responder.generate_response(probe)
        mem0_response = await mem0_resp.generate_response(probe)
        baseline_response = await soul_responder.generate_response_no_soul(probe)

        # Judge
        judge = ResponseJudge(judge_engine)
        context = {
            "agent_name": "Empath",
            "personality_description": soul.to_system_prompt(),
            "conversation_history": [{"role": "user", "content": u} for u, _ in emotional_arc],
            "planted_facts": [],
            "user_message": probe,
        }
        scores = await _judge_three_way(
            judge, soul_response, mem0_response, baseline_response, context
        )

        # Also capture soul emotional state for richer results
        soul_state = soul.state
        bond_strength = soul.bond.bond_strength

        results.update(
            {
                "status": "complete",
                "probe": probe,
                "soul_state": {
                    "mood": str(soul_state.mood),
                    "energy": soul_state.energy,
                    "social_battery": soul_state.social_battery,
                },
                "bond_strength": bond_strength,
                "response_soul": soul_response,
                "response_mem0": mem0_response,
                "response_baseline": baseline_response,
                **scores,
            }
        )
        print(
            f"  [Test 4] Complete — Soul: {scores['soul_score']}, Mem0: {scores['mem0_score']}, Base: {scores['baseline_score']}"
        )

    except Exception as e:
        results.update(
            {
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            }
        )
        print(f"  [Test 4] Error: {e}")

    return results


# ---------------------------------------------------------------------------
# Score parsing helper
# ---------------------------------------------------------------------------


def _parse_named_scores(raw: str) -> dict[str, Any]:
    """Parse named scores from LLM output in 'key: value' format."""
    scores: dict[str, Any] = {}
    reasoning_lines: list[str] = []
    in_reasoning = False

    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        if in_reasoning:
            reasoning_lines.append(line)
            continue

        if line.lower().startswith("reasoning:"):
            in_reasoning = True
            remainder = line.split(":", 1)[1].strip()
            if remainder:
                reasoning_lines.append(remainder)
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            try:
                scores[key] = float(value)
            except ValueError:
                scores[key] = value

    if reasoning_lines:
        scores["reasoning"] = " ".join(reasoning_lines)

    return scores


# ---------------------------------------------------------------------------
# Test registry
# ---------------------------------------------------------------------------

TEST_REGISTRY: dict[str, tuple[str, Any]] = {
    "response": ("Response Quality", test_response_quality_3way),
    "personality": ("Personality Consistency", test_personality_consistency_3way),
    "recall": ("Hard Recall", test_hard_recall_3way),
    "emotional": ("Emotional Continuity", test_emotional_continuity_3way),
}

ALL_TEST_NAMES = list(TEST_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Scorecard rendering
# ---------------------------------------------------------------------------

_LINE = "=" * 72
_DASH = "-" * 72


def _print_scorecard(
    results: dict[str, dict],
    test_keys: list[str],
    agent_usage: dict,
    judge_usage: dict,
) -> str:
    """Print and return the three-way comparison scorecard."""
    lines: list[str] = []

    def p(text: str = "") -> None:
        lines.append(text)
        print(text)

    p(_LINE)
    p("  Soul Protocol vs Mem0 Comparison Benchmark")
    p(_LINE)
    p(f"  {'Test':<26}| {'Soul':>6} | {'Mem0':>6} | {'Base':>6} | Soul>Mem0?")
    p(_DASH)

    soul_all: list[float] = []
    mem0_all: list[float] = []
    base_all: list[float] = []

    for key in test_keys:
        display_name = TEST_REGISTRY[key][0]
        r = results.get(key, {})

        soul = r.get("soul_score")
        mem0 = r.get("mem0_score")
        base = r.get("baseline_score")

        if soul is not None:
            soul_all.append(soul)
        if mem0 is not None:
            mem0_all.append(mem0)
        if base is not None:
            base_all.append(base)

        def _f(v: float | None) -> str:
            return f"{v:.1f}" if v is not None else "N/A"

        if soul is not None and mem0 is not None:
            diff = soul - mem0
            comparison = f"{'Yes' if diff > 0 else 'No'} ({'+' if diff >= 0 else ''}{diff:.1f})"
        else:
            comparison = "N/A"

        p(f"  {display_name:<26}| {_f(soul):>6} | {_f(mem0):>6} | {_f(base):>6} | {comparison}")

    p(_DASH)

    avg_soul = statistics.mean(soul_all) if soul_all else None
    avg_mem0 = statistics.mean(mem0_all) if mem0_all else None
    avg_base = statistics.mean(base_all) if base_all else None

    def _f(v: float | None) -> str:
        return f"{v:.1f}" if v is not None else "N/A"

    if avg_soul is not None and avg_mem0 is not None:
        diff = avg_soul - avg_mem0
        comparison = f"{'Yes' if diff > 0 else 'No'} ({'+' if diff >= 0 else ''}{diff:.1f})"
    else:
        comparison = "N/A"

    p(
        f"  {'Overall':<26}| {_f(avg_soul):>6} | {_f(avg_mem0):>6} | {_f(avg_base):>6} | {comparison}"
    )
    p()

    agent_calls = agent_usage.get("calls", 0)
    agent_cost = agent_usage.get("estimated_cost_usd", 0.0)
    judge_calls = judge_usage.get("calls", 0)
    judge_cost = judge_usage.get("estimated_cost_usd", 0.0)

    p("  API Usage:")
    p(f"    Agent engine: {agent_calls} calls, ${agent_cost:.4f}")
    p(f"    Judge engine: {judge_calls} calls, ${judge_cost:.4f}")
    p(f"    Total: ${agent_cost + judge_cost:.4f}")
    p(_LINE)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------


def _save_results(
    output_dir: Path,
    results: dict[str, dict],
    scorecard_text: str,
    metadata: dict,
) -> None:
    """Write JSON results and markdown scorecard to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = metadata.get("timestamp", datetime.now(UTC).isoformat())
    stem = timestamp.replace(":", "-").replace("+", "p")

    json_path = output_dir / f"mem0_comparison_{stem}.json"
    payload = {"metadata": metadata, "results": results}
    json_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nResults saved to {json_path}")

    md_path = output_dir / f"mem0_comparison_{stem}.md"
    md_content = (
        f"# Mem0 Comparison Benchmark Results\n\n"
        f"**Date:** {timestamp}\n\n"
        f"```\n{scorecard_text}\n```\n"
    )
    md_path.write_text(md_content)
    print(f"Scorecard saved to {md_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Soul Protocol vs Mem0 comparison benchmark",
    )
    parser.add_argument(
        "--tests",
        type=str,
        default=",".join(ALL_TEST_NAMES),
        help=f"Comma-separated tests: {', '.join(ALL_TEST_NAMES)} (default: all)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="research/results/mem0_comparison",
        help="Output directory (default: research/results/mem0_comparison)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,
        help="Max concurrent API calls per engine (default: 10)",
    )
    return parser.parse_args(argv)


async def run(argv: list[str] | None = None) -> None:
    """Main entry point for the mem0 comparison benchmark."""

    if not MEM0_AVAILABLE:
        print("ERROR: mem0ai is not installed.")
        print("Install with: pip install mem0ai")
        print()
        print("Mem0 requires an LLM for memory extraction. It will use")
        print("OPENAI_API_KEY by default. Set this environment variable")
        print("before running, or configure mem0 with a custom LLM provider.")
        sys.exit(1)

    args = _parse_args(argv)

    requested = [t.strip() for t in args.tests.split(",") if t.strip()]
    unknown = [t for t in requested if t not in TEST_REGISTRY]
    if unknown:
        sys.exit(f"Unknown test(s): {', '.join(unknown)}. Valid: {', '.join(ALL_TEST_NAMES)}")

    test_keys = requested
    output_dir = Path(args.output)

    print(f"Running mem0 comparison: {', '.join(test_keys)}")
    print(f"Max concurrent calls: {args.max_concurrent}")
    print(f"Output directory: {output_dir}\n")

    agent_engine = HaikuCognitiveEngine(max_concurrent=args.max_concurrent)
    judge_engine = HaikuCognitiveEngine(max_concurrent=args.max_concurrent, max_tokens=2048)

    results: dict[str, dict] = {}
    start_time = time.monotonic()

    for key in test_keys:
        display_name, test_fn = TEST_REGISTRY[key]
        print(f"\n{'=' * 40}")
        print(f"  Running: {display_name}")
        print(f"{'=' * 40}\n")

        test_start = time.monotonic()
        result = await test_fn(agent_engine, judge_engine)
        elapsed = time.monotonic() - test_start

        result["elapsed_seconds"] = round(elapsed, 2)
        results[key] = result

        s = result.get("soul_score")
        m = result.get("mem0_score")
        b = result.get("baseline_score")
        print(f"\n  Result: {display_name}")
        print(f"    Soul:     {s}")
        print(f"    Mem0:     {m}")
        print(f"    Baseline: {b}")
        print(f"    Time:     {elapsed:.1f}s")

    total_elapsed = time.monotonic() - start_time

    agent_usage = {
        "calls": agent_engine.usage.calls,
        "estimated_cost_usd": agent_engine.usage.estimated_cost_usd,
        "input_tokens": agent_engine.usage.input_tokens,
        "output_tokens": agent_engine.usage.output_tokens,
        "summary": agent_engine.usage.summary(),
    }
    judge_usage = {
        "calls": judge_engine.usage.calls,
        "estimated_cost_usd": judge_engine.usage.estimated_cost_usd,
        "input_tokens": judge_engine.usage.input_tokens,
        "output_tokens": judge_engine.usage.output_tokens,
        "summary": judge_engine.usage.summary(),
    }

    print(f"\n\nAll tests complete in {total_elapsed:.1f}s\n")

    scorecard_text = _print_scorecard(results, test_keys, agent_usage, judge_usage)

    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    metadata = {
        "timestamp": timestamp,
        "tests_run": test_keys,
        "max_concurrent": args.max_concurrent,
        "total_elapsed_seconds": round(total_elapsed, 2),
        "agent_usage": agent_usage,
        "judge_usage": judge_usage,
        "conditions": ["soul_protocol", "mem0", "baseline"],
        "mem0_version": _get_mem0_version(),
    }

    _save_results(output_dir, results, scorecard_text, metadata)


def _get_mem0_version() -> str:
    """Get installed mem0 version, or 'unknown'."""
    try:
        import importlib.metadata

        return importlib.metadata.version("mem0ai")
    except Exception:
        return "unknown"


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
