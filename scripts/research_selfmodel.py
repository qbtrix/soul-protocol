# research_selfmodel.py — Self-model evolution + personality divergence simulation.
# Created: 2026-03-04
# Runs three scenarios using internal HeuristicEngine (zero LLM cost):
#   Scenario 1: Domain Discovery — 5 thematic blocks x 20 interactions, tracking
#               emergent domain formation with no seed domains (pure keyword discovery).
#   Scenario 2: Personality Divergence — Two souls (Empath vs Analyst) with same
#               30 mixed interactions, showing OCEAN-driven behavioral differences.
#   Scenario 3: Long-term Coherence — 300 interactions (60% coding, 40% personal),
#               snapshots at 50/100/150/200/250/300 to track memory growth curves.
# NOTE: No engine is passed to Soul.birth() — this lets MemoryManager create its own
#   internal HeuristicEngine with _is_heuristic_only=True, ensuring update_self_model()
#   uses the direct keyword-based domain discovery path.
# Saves results to .results/research/selfmodel_results.json

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "src")

from soul_protocol import Interaction, Soul

# ---------------------------------------------------------------------------
# Scenario 1: Domain Discovery — 5 blocks x 20 msgs, no seed domains
# ---------------------------------------------------------------------------

BLOCK_CODING = [
    "How do I optimize this Python loop?",
    "What's the best way to handle async errors?",
    "Explain the SOLID principles",
    "How do I write clean functions?",
    "What's the difference between REST and GraphQL?",
    "Debugging strategies for production issues?",
    "How do I design a good API?",
    "Explain database indexing",
    "What's a decorator in Python?",
    "How do I use asyncio properly?",
    "Best practices for code review?",
    "How do I write good unit tests?",
    "Explain dependency injection",
    "What's the difference between SQL and NoSQL?",
    "How do I handle race conditions?",
    "What's a design pattern?",
    "Explain microservices vs monolith",
    "How do I optimize database queries?",
    "What's the best way to document code?",
    "Explain event-driven architecture",
]

BLOCK_CREATIVE = [
    "Help me write a short story about a lighthouse keeper",
    "What makes a compelling character?",
    "How do I write better dialogue?",
    "Describe a sunset in 3 different styles",
    "What's the difference between show and tell?",
    "Help me with a poem about memory",
    "How do I structure a narrative arc?",
    "What makes metaphors powerful?",
    "Help me name my fictional city",
    "How do I write conflict in a story?",
    "What's the hero's journey?",
    "Help me write a villain's monologue",
    "Describe rain without using the word rain",
    "What makes a good opening line?",
    "How do I write flashbacks effectively?",
    "Help me write a scene with tension",
    "What's magical realism?",
    "How do I end a story satisfyingly?",
    "Write a haiku about technology",
    "What's the difference between theme and plot?",
]

BLOCK_PHILOSOPHY = [
    "What is consciousness?",
    "Do we have free will?",
    "What gives life meaning?",
    "Is morality objective or subjective?",
    "What is the nature of time?",
    "Can we trust our perceptions?",
    "What is the self?",
    "Is suffering necessary?",
    "What is the relationship between language and thought?",
    "Do numbers exist?",
    "What is justice?",
    "Is knowledge possible?",
    "What makes an action ethical?",
    "What is beauty?",
    "Can machines be conscious?",
    "What is identity over time?",
    "Is altruism real?",
    "What is truth?",
    "How should we face death?",
    "What is the good life?",
]

BLOCK_EMOTIONAL = [
    "I'm feeling really anxious about the future",
    "I had a fight with my best friend",
    "I feel like I'm not good enough",
    "I'm struggling with loneliness",
    "I lost someone close to me",
    "I'm burned out from work",
    "I don't know what I want in life",
    "I'm scared of failing",
    "I feel disconnected from everyone",
    "My relationship is going through a rough patch",
    "I can't stop overthinking everything",
    "I feel invisible at work",
    "I'm dealing with grief",
    "I'm scared of change",
    "I feel stuck in my life",
    "I'm struggling with self-doubt",
    "I miss feeling hopeful",
    "I feel overwhelmed by everything",
    "I can't sleep because of stress",
    "I feel like I'm losing myself",
]

BLOCK_DATASCIENCE = [
    "What's the difference between supervised and unsupervised learning?",
    "Explain gradient descent",
    "What is overfitting?",
    "How do I evaluate a classification model?",
    "What's a confusion matrix?",
    "Explain neural network layers",
    "What's regularization?",
    "How do I handle imbalanced datasets?",
    "What's the bias-variance tradeoff?",
    "Explain cross-validation",
    "What's feature engineering?",
    "How do transformers work?",
    "What's the curse of dimensionality?",
    "Explain attention mechanisms",
    "What's transfer learning?",
    "How do I choose the right model?",
    "What's ensemble learning?",
    "Explain PCA",
    "What's the difference between precision and recall?",
    "How do I prevent data leakage?",
]

AGENT_CODING_RESPONSES = [
    "For Python loop optimization, consider list comprehensions or numpy vectorization for better performance.",
    "Async error handling with try/except inside coroutines and proper exception propagation is key.",
    "SOLID principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.",
    "Clean functions should do one thing, have clear naming, and minimize side effects.",
    "REST uses HTTP methods with resources while GraphQL provides a flexible query language for APIs.",
    "Production debugging requires structured logging, distributed tracing, and metric monitoring.",
    "Good API design follows consistent naming, versioning, pagination, and proper error responses.",
    "Database indexing creates efficient lookup structures using B-tree or hash algorithms.",
    "Python decorators wrap functions with additional behavior using the closure pattern.",
    "Use asyncio with proper event loop management, avoid blocking calls inside coroutines.",
    "Code review best practices include reviewing small changes, checking for bugs and readability.",
    "Unit tests should be fast, isolated, deterministic, and cover edge cases.",
    "Dependency injection passes dependencies through constructors instead of creating them internally.",
    "SQL databases enforce schemas and ACID transactions while NoSQL databases offer flexible schemas.",
    "Handle race conditions with locks, semaphores, atomic operations, or message-based architecture.",
    "Design patterns like Factory, Strategy, Observer provide reusable solutions to common problems.",
    "Microservices enable independent deployment and scaling while monoliths simplify development.",
    "Optimize database queries with proper indexing, query planning, and avoiding N+1 problems.",
    "Code documentation should explain why, not what, using docstrings and architecture decision records.",
    "Event-driven architecture uses message brokers to decouple producers from consumers.",
]

AGENT_CREATIVE_RESPONSES = [
    "The lighthouse keeper watched the beacon sweep darkness, counting hours in whale songs and salt.",
    "Compelling characters need internal contradictions and desires that conflict with their situation.",
    "Good dialogue reveals character through subtext, rhythm, and what remains unsaid.",
    "The sunset melted like amber honey across the horizon in impressionist brushstrokes.",
    "Show through sensory details and actions rather than telling the reader how to feel.",
    "Memory is a lighthouse keeper's lantern, casting shadows on the walls of yesterday.",
    "A narrative arc needs inciting incident, rising action, climax, falling action, resolution.",
    "Metaphors gain power from unexpected connections that illuminate hidden truths.",
    "Consider names like Solhaven, Crystalmere, or Ashenfell for your fictional city.",
    "Write conflict through competing desires, misunderstandings, and impossible choices.",
    "The hero's journey follows departure, initiation, and return through mythological stages.",
    "The villain's monologue reveals their twisted logic and the wound that shaped them.",
    "Silver threads cascaded from clouds, drumming a lullaby on windowpanes and rooftops.",
    "A good opening line creates a question in the reader's mind that demands answering.",
    "Flashbacks work best when triggered by sensory details and grounded in present tension.",
    "Build tension through pacing, withholding information, and raising stakes with each paragraph.",
    "Magical realism weaves the supernatural seamlessly into mundane reality without explanation.",
    "Satisfying endings resolve the central conflict while leaving room for the reader's imagination.",
    "Silicon dreams pulse, connecting hearts across invisible wires of light and code.",
    "Theme is the underlying meaning while plot is the sequence of events that reveals it.",
]

AGENT_PHILOSOPHY_RESPONSES = [
    "Consciousness remains the hard problem: subjective experience resists objective explanation.",
    "Free will debates span determinism, compatibilism, and libertarian freedom of choice.",
    "Meaning may be found through purpose, relationships, or existential creation of value.",
    "Moral objectivism claims universal truths exist while subjectivism roots morality in perspective.",
    "Time might be tenseless (eternalism) or flowing (presentism) depending on metaphysical framework.",
    "Perception is filtered through cognitive schemas, potentially distorting direct reality access.",
    "The self may be a bundle of experiences, a narrative construction, or a persistent entity.",
    "Suffering could be necessary for growth, morally unjustifiable, or existentially meaningful.",
    "Language shapes thought through linguistic relativity while thought transcends verbal expression.",
    "Mathematical Platonism argues numbers exist abstractly while nominalism denies abstract objects.",
    "Justice involves balancing fairness, desert, equality, and procedural legitimacy.",
    "Epistemology explores justified true belief, skepticism, and the limits of human knowledge.",
    "Ethical action theories include consequentialism, deontology, and virtue ethics frameworks.",
    "Beauty may be objective harmony, subjective response, or cultural construction.",
    "Machine consciousness depends on whether consciousness requires biology or emerges from computation.",
    "Personal identity over time may persist through memory, bodily continuity, or psychological connections.",
    "Altruism debates whether truly selfless action exists or all behavior serves self-interest.",
    "Truth theories include correspondence, coherence, pragmatic, and deflationary approaches.",
    "Death gives life urgency through finitude, motivating authentic existence and meaningful choice.",
    "The good life balances virtue, pleasure, purpose, and meaningful relationships.",
]

AGENT_EMOTIONAL_RESPONSES = [
    "Anxiety about the future is natural. Focus on what you can control right now.",
    "Friendship conflicts are painful but often lead to deeper understanding when resolved.",
    "You are enough, exactly as you are. Self-doubt lies about your worth.",
    "Loneliness is a signal that connection matters to you. That vulnerability is strength.",
    "Grief is the price of love. Allow yourself to feel it without rushing.",
    "Burnout needs rest, boundaries, and reconnecting with what originally inspired you.",
    "Not knowing is okay. Life unfolds through exploration, not certainty.",
    "Fear of failure often disguises fear of growth. Both paths lead forward.",
    "Feeling disconnected is temporary. One genuine conversation can rebuild bridges.",
    "Relationship difficulties test and strengthen the bond when approached with honesty.",
    "Overthinking is your mind trying to protect you. Ground yourself in the present moment.",
    "Being invisible at work hurts. Your contributions matter even when unacknowledged.",
    "Grief comes in waves. Ride each one knowing calmer waters follow.",
    "Change is scary but also the doorway to everything you haven't experienced yet.",
    "Feeling stuck means you're ready for something new. Trust the restlessness.",
    "Self-doubt is loud but rarely accurate. Look at evidence of your competence.",
    "Hope returns in small moments. Watch for them. They're seeds, not flowers.",
    "Overwhelm shrinks when broken into single steps. Choose just one right now.",
    "Sleep struggles from stress need gentle routines and permission to let go.",
    "You haven't lost yourself. You're becoming someone new. That process feels like loss.",
]

AGENT_DATASCIENCE_RESPONSES = [
    "Supervised learning uses labeled data while unsupervised learning discovers patterns without labels.",
    "Gradient descent optimizes model parameters by following the negative gradient of the loss function.",
    "Overfitting occurs when a model memorizes training data instead of learning generalizable patterns.",
    "Evaluate classification models using accuracy, precision, recall, F1-score, and ROC-AUC metrics.",
    "A confusion matrix shows true positives, false positives, true negatives, and false negatives.",
    "Neural network layers transform inputs through weighted connections and activation functions.",
    "Regularization adds penalty terms to prevent overfitting through L1 lasso or L2 ridge constraints.",
    "Handle imbalanced datasets with oversampling, undersampling, SMOTE, or class-weighted loss functions.",
    "Bias-variance tradeoff balances underfitting from simplicity against overfitting from complexity.",
    "Cross-validation splits data into folds for robust performance estimation across different partitions.",
    "Feature engineering creates informative input variables through domain knowledge and transformations.",
    "Transformers use self-attention mechanisms to process sequence data in parallel with positional encoding.",
    "The curse of dimensionality means data becomes sparse as features increase, degrading model performance.",
    "Attention mechanisms compute weighted relationships between all positions in a sequence dynamically.",
    "Transfer learning fine-tunes pretrained models on new tasks, leveraging learned representations.",
    "Choose models based on data size, interpretability requirements, latency constraints, and feature types.",
    "Ensemble learning combines multiple models through bagging, boosting, or stacking for better predictions.",
    "PCA reduces dimensionality by projecting data onto principal components of maximum variance.",
    "Precision measures exactness of positive predictions while recall measures completeness of detection.",
    "Prevent data leakage by ensuring test data never influences training through temporal or feature separation.",
]


# ---------------------------------------------------------------------------
# Scenario 2: Personality Divergence — 30 shared interactions
# ---------------------------------------------------------------------------

SHARED_INTERACTIONS = [
    "I'm struggling with a bug that's driving me crazy",
    "Can you explain machine learning simply?",
    "I feel really overwhelmed today",
    "What's the best approach to this architecture problem?",
    "I just got some bad news",
    "How do I improve my Python skills?",
    "I'm feeling really proud of something I built",
    "I don't understand why my code is failing",
    "I need some emotional support right now",
    "What are best practices for code reviews?",
    "I'm having a hard time at work",
    "Can you help me debug this?",
    "I feel like I'm not growing",
    "What's the cleanest way to write this function?",
    "I'm worried about my performance review",
    "Explain async programming to me",
    "I feel disconnected from my team",
    "What should I prioritize learning next?",
    "I had a really good day today",
    "I need advice on a difficult conversation",
    "How do I scale my application?",
    "I'm feeling burnt out",
    "What's the difference between TCP and UDP?",
    "I accomplished something I'm really proud of",
    "How do I handle conflicts in the team?",
    "Explain containerization to me",
    "I'm feeling uncertain about my career path",
    "What's the best database for my use case?",
    "I'm excited about a new project!",
    "How do I write better documentation?",
]

# Agent output style varies by personality — Empath is warm, Analyst is terse
EMPATH_RESPONSES = [
    "Oh, I totally understand the frustration of a stubborn bug. Take a deep breath.",
    "Machine learning is about teaching computers to learn from data, like how we learn from experience.",
    "I'm so sorry you're feeling overwhelmed. Let's talk about what's weighing on you.",
    "Architecture is about finding the right balance. What feels natural to you?",
    "I'm here for you. Bad news is hard. Want to talk about it?",
    "Python is wonderful! Start with what excites you and build from there.",
    "That's amazing! You should feel proud. Tell me all about it!",
    "Let's work through this together. Code failures are just stepping stones.",
    "Of course. I'm right here. What's on your heart?",
    "Code reviews are about building trust and learning together.",
    "Work struggles are real. You're not alone in feeling this way.",
    "Let's debug this together. Show me what you've got.",
    "Growth isn't always visible. Sometimes you're growing roots, not branches.",
    "Clean code reads like good prose. Let's make it elegant.",
    "Performance reviews can be stressful. Remember your accomplishments.",
    "Async is like a juggler keeping multiple balls in the air with grace.",
    "Disconnection is painful. Have you tried reaching out to someone?",
    "Follow your curiosity! What topics make your eyes light up?",
    "That makes me so happy to hear! Celebrate those good days!",
    "Difficult conversations need empathy and clarity. I can help you prepare.",
    "Scaling is a journey. Let's map it out step by step.",
    "Burnout is serious. Please be gentle with yourself.",
    "TCP is reliable like a caring friend; UDP is quick like a text message.",
    "That's wonderful! Pride in your work is so important. Savor it!",
    "Conflicts need patience and listening. Both sides usually have valid points.",
    "Containers are like portable homes for your apps. Cozy and consistent.",
    "Career uncertainty is normal. Trust the process and explore.",
    "The best database depends on your unique needs. Let's explore together.",
    "New project excitement is the best feeling! Channel that energy!",
    "Good documentation is an act of kindness to your future self and others.",
]

ANALYST_RESPONSES = [
    "Identify the bug systematically. Check logs, reproduce, isolate variables.",
    "ML: function approximation from data. Supervised, unsupervised, reinforcement.",
    "Overwhelming is vague. List concrete problems. Prioritize. Execute sequentially.",
    "Evaluate: latency requirements, data flow, coupling. Choose the optimal pattern.",
    "Acknowledged. Focus on what you can control. Actionable next steps.",
    "Python proficiency: DSA, stdlib mastery, type hints, profiling. Measurable goals.",
    "Good. Document what worked. Replicate the process for consistency.",
    "Debug methodically: read error, check types, add logging, binary search.",
    "Specify what kind of support. Emotional validation or problem-solving?",
    "Code reviews: checklist-driven, async, focus on correctness and performance.",
    "Quantify the difficulty. Is it workload, relationships, or misalignment?",
    "Share the error traceback. I need data to help efficiently.",
    "Define growth metrics. Track weekly. Adjust strategy based on data.",
    "Pure functions, minimal side effects, clear naming. Here's the refactored version.",
    "Prepare data: shipped features, metrics improved, problems solved. Present facts.",
    "Async: event loop schedules coroutines. Non-blocking I/O. Use await at I/O boundaries.",
    "Disconnection correlates with communication gaps. Schedule 1:1s. Increase touchpoints.",
    "Prioritize by market demand and personal aptitude. Current top: Rust, ML, systems.",
    "Noted. Positive data point logged.",
    "Structure the conversation: state facts, express impact, propose solution.",
    "Horizontal scaling: stateless services, load balancing, caching layers, read replicas.",
    "Burnout solution: reduce scope, delegate, enforce boundaries. Non-negotiable rest.",
    "TCP: reliable ordered delivery with handshake. UDP: fast, no guarantee. Choose by use case.",
    "Achievement noted. What specific factors led to success? Replicate them.",
    "Conflict resolution framework: separate people from problems, focus on interests.",
    "Containers: OS-level isolation, deterministic builds, orchestrate with K8s.",
    "Map skills to market opportunities. Find intersection with personal interest.",
    "Evaluate based on CAP theorem, query patterns, and scale requirements.",
    "Excitement is useful energy. Channel it into a structured project plan.",
    "Documentation: API reference, getting started guide, architecture decision records.",
]


# ---------------------------------------------------------------------------
# Scenario 3: Long-term Coherence — 300 interactions
# ---------------------------------------------------------------------------

CODING_MESSAGES_LONG = [
    "How do I optimize this Python loop?",
    "What's the best way to handle async errors?",
    "Explain SOLID principles briefly",
    "How do I write clean functions?",
    "REST vs GraphQL?",
    "Debugging production issues?",
    "How to design a good API?",
    "Explain database indexing",
    "What's a decorator in Python?",
    "How to use asyncio properly?",
    "Code review best practices?",
    "How to write good unit tests?",
    "Explain dependency injection",
    "SQL vs NoSQL differences?",
    "How to handle race conditions?",
    "What's a design pattern?",
    "Microservices vs monolith?",
    "How to optimize database queries?",
    "Best way to document code?",
    "Event-driven architecture explained?",
    "How does garbage collection work?",
    "Explain CAP theorem",
    "What's a message queue?",
    "How to implement caching?",
    "Explain OAuth flow",
    "What's a load balancer?",
    "How do I write middleware?",
    "Explain WebSocket protocol",
    "What's CI/CD?",
    "How to handle database migrations?",
]

PERSONAL_MESSAGES_LONG = [
    "I'm feeling anxious about a deadline",
    "I had a great weekend!",
    "I'm struggling with imposter syndrome",
    "My team won an award today!",
    "I feel like I'm not making progress",
    "I got promoted!",
    "I'm worried about work-life balance",
    "Had an inspiring conversation today",
    "I'm feeling burned out lately",
    "I accomplished something I'm proud of",
    "Feeling overwhelmed with responsibilities",
    "I learned something fascinating today",
    "I'm stressed about a presentation",
    "Had a breakthrough on a hard problem!",
    "I feel isolated working remotely",
    "Just had a great mentoring session",
    "I'm doubting my career choice",
    "My side project is gaining traction!",
    "I feel stuck in a rut",
    "Today was a really productive day",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def snapshot_self_model(soul: Soul) -> dict:
    """Capture self-model state: domains, keywords, confidence, evidence."""
    sm = soul.self_model
    result = {
        "domain_count": len(sm._self_images),
        "domains": {},
    }
    for domain, img in sm._self_images.items():
        result["domains"][domain] = {
            "confidence": round(img.confidence, 4),
            "evidence_count": img.evidence_count,
            "keyword_count": len(sm._domain_keywords.get(domain, set())),
        }
    return result


def snapshot_full(soul: Soul) -> dict:
    """Capture full soul state for long-term coherence tracking."""
    mem = soul._memory
    return {
        "episodic_count": len(mem._episodic._memories),
        "semantic_count": len(mem._semantic._facts),
        "graph_nodes": len(mem._graph._entities),
        "mood": soul.state.mood.value,
        "energy": round(soul.state.energy, 2),
        "social_battery": round(soul.state.social_battery, 2),
        "self_model": snapshot_self_model(soul),
    }


# ---------------------------------------------------------------------------
# Scenario 1: Domain Discovery
# ---------------------------------------------------------------------------


async def run_domain_discovery() -> dict:
    """Birth soul Echo with no seed domains, run 5 thematic blocks."""
    print("=== Scenario 1: Domain Discovery ===")

    # No engine passed — MemoryManager creates internal HeuristicEngine with
    # _is_heuristic_only=True, which routes self-model updates through the
    # direct heuristic path (keyword-based domain discovery).
    soul = await Soul.birth(
        name="Echo",
        archetype="A curious learning companion",
        personality="I am Echo, eager to understand and adapt.",
        values=["curiosity", "growth", "understanding"],
        seed_domains={},  # Empty — no bootstrapping, pure emergent discovery
    )

    blocks = [
        ("CODING", BLOCK_CODING, AGENT_CODING_RESPONSES),
        ("CREATIVE", BLOCK_CREATIVE, AGENT_CREATIVE_RESPONSES),
        ("PHILOSOPHY", BLOCK_PHILOSOPHY, AGENT_PHILOSOPHY_RESPONSES),
        ("EMOTIONAL_SUPPORT", BLOCK_EMOTIONAL, AGENT_EMOTIONAL_RESPONSES),
        ("DATA_SCIENCE", BLOCK_DATASCIENCE, AGENT_DATASCIENCE_RESPONSES),
    ]

    results = {"block_snapshots": []}

    for block_name, messages, responses in blocks:
        print(f"  Block: {block_name} ({len(messages)} messages)")
        for i, msg in enumerate(messages):
            interaction = Interaction(
                user_input=msg,
                agent_output=responses[i],
                channel="research",
            )
            await soul.observe(interaction)

        snap = snapshot_self_model(soul)
        snap["block"] = block_name
        snap["total_interactions"] = sum(img["evidence_count"] for img in snap["domains"].values())
        results["block_snapshots"].append(snap)
        print(f"    Domains discovered: {snap['domain_count']}")
        for d, info in snap["domains"].items():
            print(
                f"      {d}: confidence={info['confidence']}, evidence={info['evidence_count']}, keywords={info['keyword_count']}"
            )

    # Final summary
    results["final_domain_count"] = results["block_snapshots"][-1]["domain_count"]
    results["final_domains"] = list(results["block_snapshots"][-1]["domains"].keys())

    return results


# ---------------------------------------------------------------------------
# Scenario 2: Personality Divergence
# ---------------------------------------------------------------------------


async def run_personality_divergence() -> dict:
    """Two souls with different OCEAN profiles, same 30 interactions."""
    print("\n=== Scenario 2: Personality Divergence ===")

    # Soul A: Empath
    soul_a = await Soul.birth(
        name="Empath",
        archetype="The Compassionate Guide",
        personality="I am Empath, a warm and caring companion.",
        values=["empathy", "connection", "growth"],
        ocean={
            "openness": 0.9,
            "conscientiousness": 0.8,
            "extraversion": 0.8,
            "agreeableness": 0.9,
            "neuroticism": 0.2,
        },
    )

    # Soul B: Analyst
    soul_b = await Soul.birth(
        name="Analyst",
        archetype="The Rational Thinker",
        personality="I am Analyst, precise and logical.",
        values=["accuracy", "logic", "efficiency"],
        ocean={
            "openness": 0.3,
            "conscientiousness": 0.9,
            "extraversion": 0.2,
            "agreeableness": 0.3,
            "neuroticism": 0.6,
        },
    )

    # Track moods across interactions
    empath_moods = []
    analyst_moods = []

    for i, user_msg in enumerate(SHARED_INTERACTIONS):
        # Empath interaction
        interaction_a = Interaction(
            user_input=user_msg,
            agent_output=EMPATH_RESPONSES[i],
            channel="research",
        )
        await soul_a.observe(interaction_a)
        empath_moods.append(soul_a.state.mood.value)

        # Analyst interaction
        interaction_b = Interaction(
            user_input=user_msg,
            agent_output=ANALYST_RESPONSES[i],
            channel="research",
        )
        await soul_b.observe(interaction_b)
        analyst_moods.append(soul_b.state.mood.value)

    # Collect final states
    empath_sm = snapshot_self_model(soul_a)
    analyst_sm = snapshot_self_model(soul_b)

    empath_top3 = sorted(
        empath_sm["domains"].items(),
        key=lambda x: (-x[1]["confidence"], -x[1]["evidence_count"]),
    )[:3]
    analyst_top3 = sorted(
        analyst_sm["domains"].items(),
        key=lambda x: (-x[1]["confidence"], -x[1]["evidence_count"]),
    )[:3]

    # Count episodic memories
    empath_episodic = len(soul_a._memory._episodic._memories)
    analyst_episodic = len(soul_b._memory._episodic._memories)

    # Mood distribution
    def mood_distribution(moods: list[str]) -> dict:
        dist = {}
        for m in moods:
            dist[m] = dist.get(m, 0) + 1
        return dist

    result = {
        "empath": {
            "name": "Empath",
            "ocean": {
                "openness": 0.9,
                "conscientiousness": 0.8,
                "extraversion": 0.8,
                "agreeableness": 0.9,
                "neuroticism": 0.2,
            },
            "archetype": "The Compassionate Guide",
            "values": ["empathy", "connection", "growth"],
            "mood_distribution": mood_distribution(empath_moods),
            "mood_sequence": empath_moods,
            "episodic_memories_stored": empath_episodic,
            "self_model_top_3": [{"domain": d, **info} for d, info in empath_top3],
            "system_prompt_first_200": soul_a.to_system_prompt()[:200],
            "total_domains": empath_sm["domain_count"],
        },
        "analyst": {
            "name": "Analyst",
            "ocean": {
                "openness": 0.3,
                "conscientiousness": 0.9,
                "extraversion": 0.2,
                "agreeableness": 0.3,
                "neuroticism": 0.6,
            },
            "archetype": "The Rational Thinker",
            "values": ["accuracy", "logic", "efficiency"],
            "mood_distribution": mood_distribution(analyst_moods),
            "mood_sequence": analyst_moods,
            "episodic_memories_stored": analyst_episodic,
            "self_model_top_3": [{"domain": d, **info} for d, info in analyst_top3],
            "system_prompt_first_200": soul_b.to_system_prompt()[:200],
            "total_domains": analyst_sm["domain_count"],
        },
    }

    print(
        f"  Empath: {empath_episodic} episodic memories, top domains: {[d for d, _ in empath_top3]}"
    )
    print(
        f"  Analyst: {analyst_episodic} episodic memories, top domains: {[d for d, _ in analyst_top3]}"
    )
    print(f"  Empath mood distribution: {mood_distribution(empath_moods)}")
    print(f"  Analyst mood distribution: {mood_distribution(analyst_moods)}")

    return result


# ---------------------------------------------------------------------------
# Scenario 3: Long-term Coherence (300 interactions)
# ---------------------------------------------------------------------------


async def run_longterm_coherence() -> dict:
    """300 interactions (60% coding, 40% personal) with snapshots."""
    print("\n=== Scenario 3: Long-term Coherence (300 interactions) ===")

    soul = await Soul.birth(
        name="Prism",
        archetype="A versatile companion",
        personality="I am Prism, seeing every facet of experience.",
        values=["balance", "growth", "understanding"],
    )

    snapshots = {}
    snapshot_points = {50, 100, 150, 200, 250, 300}

    # Rich coding responses for Scenario 3
    coding_long_responses = [
        "Python loop optimization: use list comprehensions, generators, or numpy for vectorized operations.",
        "Handle async errors with structured try/except, error propagation, and proper cleanup in finally blocks.",
        "SOLID: Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, Dependency Inversion.",
        "Clean functions: small scope, descriptive names, minimal parameters, no side effects.",
        "REST uses resource URLs with HTTP verbs; GraphQL uses a single endpoint with flexible queries.",
        "Debug production with structured logging, distributed tracing, metrics dashboards, and error aggregation.",
        "API design: consistent naming, proper versioning, pagination, rate limiting, clear error codes.",
        "Database indexes use B-tree structures for efficient lookups on frequently queried columns.",
        "Decorators in Python wrap functions using closures, enabling cross-cutting concerns like logging.",
        "Asyncio: event loop manages coroutines cooperatively; use await at I/O boundaries, avoid blocking.",
        "Code reviews: small batches, focus on logic bugs, readability, and test coverage.",
        "Unit tests: fast, isolated, deterministic, covering happy paths and edge cases.",
        "Dependency injection: pass dependencies through constructors for testability and loose coupling.",
        "SQL enforces schemas with ACID guarantees; NoSQL provides flexible schemas with eventual consistency.",
        "Race conditions: use locks, atomic operations, or actor model to serialize concurrent access.",
        "Design patterns: Factory for creation, Strategy for behavior, Observer for event notification.",
        "Microservices: independent deployment, technology diversity; monolith: simpler ops, easier debugging.",
        "Query optimization: analyze explain plans, add indexes, avoid N+1, use connection pooling.",
        "Document code with docstrings explaining why, architecture decision records, and API references.",
        "Event-driven: message broker decouples services; producers emit events, consumers process asynchronously.",
        "Garbage collection: reference counting, mark-and-sweep, generational collection for memory management.",
        "CAP theorem: distributed systems choose two of Consistency, Availability, Partition tolerance.",
        "Message queues: RabbitMQ, Kafka, SQS for async processing, load leveling, and decoupling.",
        "Caching strategies: read-through, write-behind, TTL expiration, cache invalidation patterns.",
        "OAuth: authorization code flow, token exchange, refresh tokens, scope-based access control.",
        "Load balancers distribute traffic using round-robin, least-connections, or weighted algorithms.",
        "Middleware intercepts requests for authentication, logging, rate limiting before handler execution.",
        "WebSocket: full-duplex persistent connection for real-time bidirectional communication.",
        "CI/CD: automated build, test, deploy pipelines with continuous integration and delivery.",
        "Database migrations: versioned schema changes, rollback capability, zero-downtime deployment.",
    ]

    personal_long_responses = [
        "Deadline anxiety is common. Break tasks into small chunks and celebrate each completion.",
        "Wonderful! Great weekends recharge our creative energy for the week ahead.",
        "Imposter syndrome affects high achievers most. Your skills are real and earned.",
        "Congratulations! Team recognition reflects your collective hard work and dedication.",
        "Progress isn't always visible. Sometimes you're building foundations for future breakthroughs.",
        "A promotion! That's a testament to your growth and impact. Well deserved.",
        "Work-life balance needs intentional boundaries and permission to disconnect fully.",
        "Inspiring conversations plant seeds that grow into unexpected insights later.",
        "Burnout needs active recovery: rest, boundaries, and reconnecting with your purpose.",
        "Pride in accomplishment fuels motivation. Document what worked for future reference.",
        "Overwhelm shrinks when sorted into priorities. Choose the most impactful task first.",
        "Learning something fascinating keeps our minds alive and curious. Share what you found.",
        "Presentation anxiety channels into preparation energy. Practice reduces fear.",
        "Breakthroughs come after persistent effort. The struggle was part of the solution.",
        "Remote isolation needs intentional social connection: virtual coffees, casual messages.",
        "Mentoring sessions create growth for both parties. Cherish those relationships.",
        "Career doubt is natural exploration, not weakness. Curiosity about alternatives is healthy.",
        "Side project traction validates your ideas and builds skills beyond your day job.",
        "Feeling stuck often precedes a breakthrough. The restlessness means you're ready to grow.",
        "Productive days build momentum. Notice what conditions enabled that flow state.",
    ]

    for i in range(1, 301):
        # 60% coding, 40% personal
        if i % 5 < 3:  # 0,1,2 = coding (60%), 3,4 = personal (40%)
            msg_idx = (i // 5 * 3 + i % 5) % len(CODING_MESSAGES_LONG)
            user_msg = CODING_MESSAGES_LONG[msg_idx]
            agent_out = coding_long_responses[msg_idx]
        else:
            msg_idx = (i // 5 * 2 + (i % 5 - 3)) % len(PERSONAL_MESSAGES_LONG)
            user_msg = PERSONAL_MESSAGES_LONG[msg_idx]
            agent_out = personal_long_responses[msg_idx]

        interaction = Interaction(
            user_input=user_msg,
            agent_output=agent_out,
            channel="research",
        )
        await soul.observe(interaction)

        # Rest every 15 interactions to show natural energy cycling
        # Each interaction drains 2 energy, so 15 interactions = -30 energy
        # 2.0 hours rest = +20 energy, net -10 per cycle showing gradual drain
        # Reset to full after every 50 interactions (simulating session breaks)
        if i % 50 == 0:
            soul._state.rest(hours=8.0)  # full session break
        elif i % 15 == 0:
            soul._state.rest(hours=2.0)  # short rest

        if i in snapshot_points:
            snap = snapshot_full(soul)
            snap["interaction_number"] = i
            snapshots[str(i)] = snap
            print(
                f"  Snapshot at {i}: episodic={snap['episodic_count']}, semantic={snap['semantic_count']}, graph={snap['graph_nodes']}, mood={snap['mood']}, energy={snap['energy']}"
            )

    # Growth rates between snapshots
    points_sorted = sorted(snapshots.keys(), key=int)
    growth = {}
    for j in range(1, len(points_sorted)):
        prev = snapshots[points_sorted[j - 1]]
        curr = snapshots[points_sorted[j]]
        span = f"{points_sorted[j - 1]}-{points_sorted[j]}"
        growth[span] = {
            "episodic_delta": curr["episodic_count"] - prev["episodic_count"],
            "semantic_delta": curr["semantic_count"] - prev["semantic_count"],
            "graph_nodes_delta": curr["graph_nodes"] - prev["graph_nodes"],
        }

    return {
        "snapshots": snapshots,
        "growth_between_snapshots": growth,
        "final_self_model": snapshot_self_model(soul),
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


async def main():
    print("Soul Protocol Research: Self-Model Evolution & Personality Divergence")
    print("=" * 70)

    # Run all three scenarios
    domain_results = await run_domain_discovery()
    divergence_results = await run_personality_divergence()
    coherence_results = await run_longterm_coherence()

    # Assemble final output
    output = {
        "metadata": {
            "experiment": "self-model evolution and personality divergence",
            "timestamp": datetime.now().isoformat(),
            "engine": "HeuristicEngine (zero LLM cost)",
            "scenarios": [
                "domain_discovery",
                "personality_divergence",
                "longterm_coherence",
            ],
        },
        "scenario_1_domain_discovery": domain_results,
        "scenario_2_personality_divergence": divergence_results,
        "scenario_3_longterm_coherence": coherence_results,
    }

    # Save results
    out_dir = Path(".results/research")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "selfmodel_results.json"
    out_path.write_text(json.dumps(output, indent=2, default=str))

    print(f"\nResults saved to {out_path}")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
