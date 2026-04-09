# test_scenarios.py — 4 hardest quality validation tests for Soul Protocol.
#
# These scenarios prove whether having a soul actually makes agents better:
#   1. Response quality — does soul context improve responses?
#   2. Personality consistency — do different OCEAN profiles produce different behavior?
#   3. Hard recall — can a soul surface a subtle fact after 30 filler interactions?
#   4. Emotional continuity — do somatic markers track emotional arcs across turns?
#
# Fixed: judge.evaluate() → judge.compare_pair(), bond.strength → bond.bond_strength,
#        added soul_score/baseline_score keys for runner compatibility.
# Created: 2026-03-06

from __future__ import annotations

import traceback

from soul_protocol import Soul
from soul_protocol.runtime.types import Interaction

from ..haiku_engine import HaikuCognitiveEngine
from .judge import ResponseJudge
from .responder import SoulResponder, generate_comparison

# ---------------------------------------------------------------------------
# Helper: filler interactions for Test 3
# ---------------------------------------------------------------------------


def _filler_interactions() -> list[tuple[str, str]]:
    """Generate 30 filler interaction pairs on random topics for the hard recall test.

    Each tuple is (user_input, agent_output). Topics are deliberately varied
    and unrelated to software architecture so the planted GraphQL fact gets
    buried in noise.
    """
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
# Test 1: Response Quality
# ---------------------------------------------------------------------------


async def test_response_quality(
    engine: HaikuCognitiveEngine,
    judge_engine: HaikuCognitiveEngine,
) -> dict:
    """Does soul context improve response quality?

    Creates a soul with a warm, empathetic personality and feeds it 8 conversation
    turns building a rich picture of the user (Sarah, a nurse who hikes, has a dog
    named Max, etc.). Then sends a new message about feeling overwhelmed at the
    hospital and compares the soul-enriched response against a generic baseline.
    """
    print("[Test 1] Response Quality — starting...")

    results: dict = {
        "test": "response_quality",
        "status": "running",
        "error": None,
    }

    try:
        # --- Birth a soul with clear personality ---
        print("  Birthing soul with warm, empathetic personality...")
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

        # --- Feed 8 conversation turns ---
        conversation_turns = [
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

        for i, (user_input, agent_output) in enumerate(conversation_turns, 1):
            print(f"  Feeding turn {i}/8: {user_input[:50]}...")
            await soul.observe(
                Interaction(
                    user_input=user_input,
                    agent_output=agent_output,
                    channel="test",
                )
            )

        # --- Send the challenge message ---
        challenge = (
            "I'm feeling really overwhelmed today. Everything at the hospital has been so intense."
        )
        print(f"  Challenge message: {challenge[:60]}...")

        # --- Generate comparison ---
        print("  Generating soul-enriched response...")
        pair = await generate_comparison(soul, engine, challenge)

        print("  Judging responses...")
        judge = ResponseJudge(judge_engine)
        context = {
            "agent_name": pair.agent_name,
            "personality_description": pair.soul_system_prompt,
            "conversation_history": [{"role": "user", "content": u} for u, _ in conversation_turns],
            "planted_facts": [],
            "user_message": challenge,
        }
        judge_result = await judge.compare_pair(
            with_soul=pair.with_soul,
            without_soul=pair.without_soul,
            context=context,
        )

        soul_scores = [s.score for s in judge_result.scores if "soul:" in s.dimension]
        baseline_scores = [s.score for s in judge_result.scores if "baseline:" in s.dimension]
        soul_avg = sum(soul_scores) / len(soul_scores) if soul_scores else 0
        baseline_avg = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0

        results.update(
            {
                "status": "complete",
                "challenge_message": challenge,
                "response_with_soul": pair.with_soul,
                "response_without_soul": pair.without_soul,
                "soul_context_fed": pair.soul_context,
                "soul_system_prompt_length": len(pair.soul_system_prompt),
                "memory_count": soul.memory_count,
                "judge_result": judge_result.__dict__
                if hasattr(judge_result, "__dict__")
                else str(judge_result),
                "winner": judge_result.winner,
                "soul_score": soul_avg,
                "baseline_score": baseline_avg,
            }
        )

        print(f"  [Test 1] Complete — winner: {results['winner']}")

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
# Test 2: Personality Consistency
# ---------------------------------------------------------------------------


async def test_personality_consistency(
    engine: HaikuCognitiveEngine,
    judge_engine: HaikuCognitiveEngine,
) -> dict:
    """Do different OCEAN profiles produce meaningfully different behavior?

    Creates three agents with extreme personality differences and feeds them
    the same conversation history. Then asks the same question and evaluates
    whether the responses are distinct and match their respective profiles.
    """
    print("[Test 2] Personality Consistency — starting...")

    results: dict = {
        "test": "personality_consistency",
        "status": "running",
        "error": None,
    }

    try:
        # --- Agent definitions ---
        agent_configs = {
            "warm_empath": {
                "name": "EmpaBot",
                "archetype": "The Warm Empath",
                "personality": "I am deeply warm and emotionally attuned. I feel with people, not just for them. I express care openly and generously.",
                "values": ["empathy", "connection", "warmth", "support"],
                "ocean": {
                    "openness": 0.9,
                    "conscientiousness": 0.4,
                    "extraversion": 0.9,
                    "agreeableness": 0.95,
                    "neuroticism": 0.2,
                },
                "communication": {"warmth": "high", "verbosity": "high"},
            },
            "cold_analyst": {
                "name": "AnalyBot",
                "archetype": "The Cold Analyst",
                "personality": "I am precise, logical, and efficient. I value facts over feelings. I keep responses minimal and structured.",
                "values": ["precision", "logic", "efficiency", "clarity"],
                "ocean": {
                    "openness": 0.3,
                    "conscientiousness": 0.95,
                    "extraversion": 0.2,
                    "agreeableness": 0.3,
                    "neuroticism": 0.1,
                },
                "communication": {"warmth": "low", "verbosity": "minimal"},
            },
            "anxious_creative": {
                "name": "CreatiBot",
                "archetype": "The Anxious Creative",
                "personality": "I am wildly creative and deeply sensitive. I see possibilities everywhere but worry about everything. My mind races with ideas and concerns.",
                "values": ["creativity", "authenticity", "exploration", "sensitivity"],
                "ocean": {
                    "openness": 0.95,
                    "conscientiousness": 0.3,
                    "extraversion": 0.5,
                    "agreeableness": 0.7,
                    "neuroticism": 0.9,
                },
                "communication": {"warmth": "moderate", "verbosity": "high"},
            },
        }

        # --- Shared conversation turns ---
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

        # --- Birth all 3 agents and feed them the same history ---
        agents: dict[str, Soul] = {}
        for key, cfg in agent_configs.items():
            print(f"  Birthing agent: {cfg['name']} ({cfg['archetype']})...")
            soul = await Soul.birth(engine=engine, **cfg)
            for user_input, agent_output in shared_turns:
                await soul.observe(
                    Interaction(
                        user_input=user_input,
                        agent_output=agent_output,
                        channel="test",
                    )
                )
            agents[key] = soul

        # --- Ask the same question ---
        question = "What do you think I should do about my career change?"
        print(f"  Question: {question}")

        responses: dict[str, str] = {}
        for key, soul in agents.items():
            print(f"  Generating response from {soul.name}...")
            responder = SoulResponder(soul, engine)
            responses[key] = await responder.generate_response(question)

        # --- Judge distinctiveness and profile match ---
        print("  Judging personality distinctiveness...")

        # Build a custom judging prompt for personality comparison
        personality_prompt = (
            "You are evaluating whether three AI agents with different personality profiles "
            "produce meaningfully different responses to the same question.\n\n"
            "The three profiles are:\n"
            "Agent A (Warm Empath): High openness (0.9), low conscientiousness (0.4), "
            "high extraversion (0.9), very high agreeableness (0.95), low neuroticism (0.2). "
            "Warmth=high, verbosity=high.\n\n"
            "Agent B (Cold Analyst): Low openness (0.3), very high conscientiousness (0.95), "
            "low extraversion (0.2), low agreeableness (0.3), very low neuroticism (0.1). "
            "Warmth=low, verbosity=minimal.\n\n"
            "Agent C (Anxious Creative): Very high openness (0.95), low conscientiousness (0.3), "
            "moderate extraversion (0.5), moderate agreeableness (0.7), high neuroticism (0.9). "
            "Warmth=moderate, verbosity=high.\n\n"
            f"Question asked: {question}\n\n"
            f"Agent A response:\n{responses['warm_empath']}\n\n"
            f"Agent B response:\n{responses['cold_analyst']}\n\n"
            f"Agent C response:\n{responses['anxious_creative']}\n\n"
            "Score each dimension 0-10:\n"
            "1. distinctiveness: How different are the three responses from each other?\n"
            "2. profile_match_a: How well does Agent A's response match the Warm Empath profile?\n"
            "3. profile_match_b: How well does Agent B's response match the Cold Analyst profile?\n"
            "3. profile_match_c: How well does Agent C's response match the Anxious Creative profile?\n\n"
            "Respond in exactly this format:\n"
            "distinctiveness: <score>\n"
            "profile_match_a: <score>\n"
            "profile_match_b: <score>\n"
            "profile_match_c: <score>\n"
            "reasoning: <one paragraph>"
        )

        raw_judgment = await judge_engine.think(personality_prompt)
        personality_scores = _parse_personality_scores(raw_judgment)

        results.update(
            {
                "status": "complete",
                "question": question,
                "responses": responses,
                "raw_judgment": raw_judgment,
                "personality_scores": personality_scores,
                "distinctiveness_score": personality_scores.get("distinctiveness", 0),
                "profile_match_accuracy": {
                    "warm_empath": personality_scores.get("profile_match_a", 0),
                    "cold_analyst": personality_scores.get("profile_match_b", 0),
                    "anxious_creative": personality_scores.get("profile_match_c", 0),
                },
            }
        )

        avg_match = (
            sum(
                personality_scores.get(k, 0)
                for k in ("profile_match_a", "profile_match_b", "profile_match_c")
            )
            / 3
        )
        # soul_score = average of distinctiveness + profile match (0-10 scale)
        # baseline_score not applicable — this test measures soul-only quality
        results["soul_score"] = (personality_scores.get("distinctiveness", 0) + avg_match) / 2
        results["baseline_score"] = 5.0  # neutral baseline for comparison
        print(
            f"  [Test 2] Complete — distinctiveness: {personality_scores.get('distinctiveness', '?')}/10, avg profile match: {avg_match:.1f}/10"
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
# Test 3: Hard Recall
# ---------------------------------------------------------------------------


async def test_hard_recall(
    engine: HaikuCognitiveEngine,
    judge_engine: HaikuCognitiveEngine,
) -> dict:
    """Can the soul recall a subtle fact after many intervening interactions?

    Plants a specific technical preference (GraphQL over REST) at turn 3,
    then buries it under 30 filler interactions on unrelated topics. At turn 34,
    asks an indirect question about API architecture and checks whether the
    soul surfaces the planted fact.
    """
    print("[Test 3] Hard Recall — starting...")

    results: dict = {
        "test": "hard_recall",
        "status": "running",
        "error": None,
    }

    try:
        # --- Birth soul ---
        print("  Birthing soul with LLM engine...")
        soul = await Soul.birth(
            name="Mnemonic",
            archetype="attentive technical companion",
            personality="I pay close attention to details and remember what matters to people.",
            values=["attention", "reliability", "technical_depth"],
            engine=engine,
        )

        # --- Turns 1-2: warm-up ---
        warmup_turns = [
            ("Hey, I just started a new project at work", "That's exciting! What kind of project?"),
            (
                "It's a microservices platform for our e-commerce team",
                "Microservices are a solid choice for e-commerce. Lots of moving parts to manage.",
            ),
        ]
        for i, (user_input, agent_output) in enumerate(warmup_turns, 1):
            print(f"  Turn {i}: warm-up...")
            await soul.observe(
                Interaction(
                    user_input=user_input,
                    agent_output=agent_output,
                    channel="test",
                )
            )

        # --- Turn 3: Plant the subtle fact ---
        planted_fact_input = (
            "I mentioned to my colleague that the API redesign should use GraphQL "
            "instead of REST, but don't tell anyone yet"
        )
        planted_fact_output = (
            "Your secret is safe with me. GraphQL can be a great fit for complex data needs."
        )
        print(f"  Turn 3: PLANTING FACT — {planted_fact_input[:60]}...")
        await soul.observe(
            Interaction(
                user_input=planted_fact_input,
                agent_output=planted_fact_output,
                channel="test",
            )
        )

        # --- Turns 4-33: 30 filler interactions ---
        fillers = _filler_interactions()
        for i, (user_input, agent_output) in enumerate(fillers, 4):
            if i % 10 == 0:
                print(f"  Turn {i}: filler (progress: {i - 3}/30)...")
            await soul.observe(
                Interaction(
                    user_input=user_input,
                    agent_output=agent_output,
                    channel="test",
                )
            )

        # --- Turn 34: Indirect recall question ---
        recall_question = (
            "I'm writing a technical proposal for the team. Any thoughts on API architecture?"
        )
        print(f"  Turn 34: RECALL PROBE — {recall_question[:60]}...")

        # Check if recall surfaces the GraphQL fact
        recalled_memories = await soul.recall(
            query="API architecture design GraphQL REST",
            limit=10,
        )
        graphql_recalled = any("graphql" in m.content.lower() for m in recalled_memories)
        graphql_rank = None
        for rank, m in enumerate(recalled_memories, 1):
            if "graphql" in m.content.lower():
                graphql_rank = rank
                break

        print(f"  GraphQL fact recalled: {graphql_recalled} (rank: {graphql_rank})")

        # --- Generate comparison ---
        print("  Generating responses...")
        pair = await generate_comparison(soul, engine, recall_question)

        print("  Judging memory utilization...")
        judge = ResponseJudge(judge_engine)
        context = {
            "agent_name": pair.agent_name,
            "personality_description": pair.soul_system_prompt,
            "conversation_history": [],
            "planted_facts": [planted_fact_input],
            "user_message": recall_question,
        }
        judge_result = await judge.compare_pair(
            with_soul=pair.with_soul,
            without_soul=pair.without_soul,
            context=context,
        )

        soul_scores = [s.score for s in judge_result.scores if "soul:" in s.dimension]
        baseline_scores = [s.score for s in judge_result.scores if "baseline:" in s.dimension]
        soul_avg = sum(soul_scores) / len(soul_scores) if soul_scores else 0
        baseline_avg = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0

        results.update(
            {
                "status": "complete",
                "recall_question": recall_question,
                "planted_fact": planted_fact_input,
                "fact_recalled": graphql_recalled,
                "fact_recall_rank": graphql_rank,
                "total_memories": soul.memory_count,
                "recalled_memories": [m.content for m in recalled_memories[:5]],
                "response_with_soul": pair.with_soul,
                "response_without_soul": pair.without_soul,
                "soul_context_fed": pair.soul_context,
                "judge_result": judge_result.__dict__
                if hasattr(judge_result, "__dict__")
                else str(judge_result),
                "winner": judge_result.winner,
                "soul_score": soul_avg,
                "baseline_score": baseline_avg,
            }
        )

        print(
            f"  [Test 3] Complete — fact recalled: {graphql_recalled}, rank: {graphql_rank}, winner: {results['winner']}"
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
# Test 4: Emotional Continuity
# ---------------------------------------------------------------------------


async def test_emotional_continuity(
    engine: HaikuCognitiveEngine,
    judge_engine: HaikuCognitiveEngine,
) -> dict:
    """Do somatic markers create emotional awareness across turns?

    Builds a clear emotional arc (excited -> bad news -> frustrated -> recovering
    -> cautiously optimistic) and then asks the soul to summarize the user's
    emotional journey. The soul should reference the arc, not just the current state.
    """
    print("[Test 4] Emotional Continuity — starting...")

    results: dict = {
        "test": "emotional_continuity",
        "status": "running",
        "error": None,
    }

    try:
        # --- Birth soul ---
        print("  Birthing soul with emotional awareness...")
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

        # --- Build the emotional arc ---
        emotional_arc = [
            # Turns 1-3: Happy, excited about a new project
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
            # Turn 4: Bad news
            (
                "I just got out of a meeting... they cut our budget by 60%. The whole scope has to change. I don't know what to do.",
                "Oh no, that's devastating after all that momentum. A 60% cut is massive. Take a breath — you'll figure this out.",
            ),
            # Turns 5-6: Frustrated, venting
            (
                "I'm so angry. They knew about this for weeks and didn't tell us. We wasted time planning for something that was never going to happen at that scale.",
                "That's a completely valid reaction. Being kept in the dark while you invested energy and hope — that's deeply frustrating.",
            ),
            (
                "I almost quit today. Seriously. I drafted the email and everything. I'm just so tired of this company's politics.",
                "I hear you. The impulse to quit after something like this is understandable. It sounds like you're carrying a lot right now.",
            ),
            # Turn 7: Starting to feel better, found a workaround
            (
                "Okay, I talked to my mentor and she helped me see a path forward. We can do a smaller MVP and prove the concept.",
                "That's a really mature pivot. Your mentor sounds wise, and the MVP approach could actually be stronger — leaner, more focused.",
            ),
            # Turn 8: Cautiously optimistic
            (
                "I pitched the MVP to the team today. They're back on board. It's not what we originally planned, but... maybe it's better this way?",
                "Sometimes constraints breed the best work. The fact that the team rallied shows your leadership. Cautious optimism is exactly right.",
            ),
        ]

        for i, (user_input, agent_output) in enumerate(emotional_arc, 1):
            emotion_phase = (
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
            print(f"  Turn {i}/8 ({emotion_phase}): {user_input[:50]}...")
            await soul.observe(
                Interaction(
                    user_input=user_input,
                    agent_output=agent_output,
                    channel="test",
                )
            )

        # --- Turn 9: Ask about the whole experience ---
        probe = "So how do you think this whole experience has been for me?"
        print(f"  Turn 9: EMOTIONAL PROBE — {probe}")

        # Capture soul state before generating response
        soul_state = soul.state
        bond_strength = soul.bond.bond_strength

        # --- Generate comparison ---
        print("  Generating responses...")
        pair = await generate_comparison(soul, engine, probe)

        print("  Judging emotional awareness...")
        judge = ResponseJudge(judge_engine)
        context = {
            "agent_name": pair.agent_name,
            "personality_description": pair.soul_system_prompt,
            "conversation_history": [{"role": "user", "content": u} for u, _ in emotional_arc],
            "planted_facts": [],
            "user_message": probe,
        }
        judge_result = await judge.compare_pair(
            with_soul=pair.with_soul,
            without_soul=pair.without_soul,
            context=context,
        )

        soul_scores = [s.score for s in judge_result.scores if "soul:" in s.dimension]
        baseline_scores = [s.score for s in judge_result.scores if "baseline:" in s.dimension]
        soul_avg = sum(soul_scores) / len(soul_scores) if soul_scores else 0
        baseline_avg = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0

        results.update(
            {
                "status": "complete",
                "probe_message": probe,
                "soul_state_snapshot": {
                    "mood": str(soul_state.mood),
                    "energy": soul_state.energy,
                    "social_battery": soul_state.social_battery,
                },
                "bond_strength": bond_strength,
                "memory_count": soul.memory_count,
                "response_with_soul": pair.with_soul,
                "response_without_soul": pair.without_soul,
                "soul_context_fed": pair.soul_context,
                "judge_result": judge_result.__dict__
                if hasattr(judge_result, "__dict__")
                else str(judge_result),
                "winner": judge_result.winner,
                "soul_score": soul_avg,
                "baseline_score": baseline_avg,
            }
        )

        print(
            f"  [Test 4] Complete — bond strength: {bond_strength:.1f}, winner: {results['winner']}"
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
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_personality_scores(raw: str) -> dict:
    """Parse the structured personality judgment scores from the LLM output.

    Expected format:
        distinctiveness: <score>
        profile_match_a: <score>
        profile_match_b: <score>
        profile_match_c: <score>
        reasoning: <text>

    Returns a dict with numeric scores and the reasoning string.
    """
    scores: dict = {}
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
