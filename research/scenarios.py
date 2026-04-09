# scenarios.py — Scenario bank: realistic interaction sequences for 4 use cases.
# Each scenario generates user_input + expected_agent_output pairs.
# Includes callback references (e.g., "remember my name is X") for testing recall.

from __future__ import annotations

import random
from dataclasses import dataclass

from .agents import UserProfile


@dataclass
class Turn:
    """A single interaction turn."""

    user_input: str
    agent_output: str
    # Ground truth metadata for evaluation
    contains_fact: bool = False  # should the system extract a fact?
    fact_content: str = ""  # what fact should be extracted
    references_previous: bool = False  # does this reference earlier context?
    reference_topic: str = ""  # what topic is being referenced
    expected_emotion: str = ""  # expected emotional tone
    importance_hint: float = 0.5  # how important is this interaction (0-1)


@dataclass
class Scenario:
    """A multi-turn interaction scenario with ground truth."""

    scenario_id: str
    use_case: str
    turns: list[Turn]
    planted_facts: list[str]  # facts deliberately planted for recall testing
    recall_queries: list[tuple[str, str]]  # (query, expected_fact) pairs


# ---------------------------------------------------------------------------
# Scenario templates — parameterized by user profile
# ---------------------------------------------------------------------------


def _support_scenarios(user: UserProfile, rng: random.Random) -> list[Scenario]:
    """Generate customer support scenarios."""
    scenarios = []
    names = ["Alex", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Taylor", "Quinn"]
    user_name = rng.choice(names)
    products = ["Pro Plan", "Basic Plan", "Enterprise", "Starter Kit", "Premium"]
    product = rng.choice(products)

    # Scenario 1: Account issue with personal info
    turns = [
        Turn(
            user_input=f"Hi, my name is {user_name} and I'm having trouble with my {product} account",
            agent_output=f"I'd be happy to help you with your {product} account, {user_name}. What seems to be the issue?",
            contains_fact=True,
            fact_content=f"User's name is {user_name}",
            importance_hint=0.8,
        ),
        Turn(
            user_input="I can't log in since yesterday. I've tried resetting my password twice.",
            agent_output="That sounds frustrating. Let me look into the login issue. Have you checked if your email address is correct?",
            expected_emotion="frustrated",
            importance_hint=0.6,
        ),
        Turn(
            user_input="Yes, my email is correct. I use the same one I signed up with.",
            agent_output="I see. Sometimes accounts get temporarily locked after multiple failed attempts. Let me check the account status.",
            importance_hint=0.4,
        ),
        Turn(
            user_input=f"Also, I want to mention I've been using {product} for about 2 years now",
            agent_output=f"Thank you for being a loyal {product} customer for 2 years! Let me prioritize getting this resolved for you.",
            contains_fact=True,
            fact_content=f"User has been using {product} for 2 years",
            importance_hint=0.7,
        ),
    ]

    # Add a recall test: later ask about the user
    recall_queries = [
        ("What is the user's name?", f"User's name is {user_name}"),
        ("What product does the user use?", f"User has been using {product}"),
    ]

    scenarios.append(
        Scenario(
            scenario_id=f"support_account_{user.user_id}",
            use_case="support",
            turns=turns,
            planted_facts=[
                f"User's name is {user_name}",
                f"User has been using {product} for 2 years",
            ],
            recall_queries=recall_queries,
        )
    )

    # Scenario 2: Follow-up session (tests cross-session memory)
    followup_turns = [
        Turn(
            user_input="Hey, I'm back. The login issue happened again.",
            agent_output="I'm sorry to hear that. Let me pull up your account details.",
            references_previous=True,
            reference_topic="login issue",
            importance_hint=0.7,
        ),
        Turn(
            user_input="I think it might be a browser issue. I switched to Firefox and it worked.",
            agent_output="That's a helpful finding! It sounds like there might be a browser compatibility issue. I'll note that Firefox works for you.",
            contains_fact=True,
            fact_content="User found Firefox works when other browser doesn't",
            importance_hint=0.6,
        ),
    ]

    scenarios.append(
        Scenario(
            scenario_id=f"support_followup_{user.user_id}",
            use_case="support",
            turns=followup_turns,
            planted_facts=["User found Firefox works when other browser doesn't"],
            recall_queries=[
                ("What browser issue did the user have?", "Firefox works"),
            ],
        )
    )

    return scenarios


def _coding_scenarios(user: UserProfile, rng: random.Random) -> list[Scenario]:
    """Generate coding assistant scenarios."""
    scenarios = []
    languages = ["Python", "JavaScript", "TypeScript", "Go", "Rust"]
    frameworks = ["FastAPI", "React", "Django", "Express", "Flask"]
    lang = rng.choice(languages)
    framework = rng.choice(frameworks)

    turns = [
        Turn(
            user_input=f"I'm working on a {framework} project in {lang}",
            agent_output=f"Great choice! What are you building with {framework}?",
            contains_fact=True,
            fact_content=f"User uses {lang} with {framework}",
            importance_hint=0.7,
        ),
        Turn(
            user_input="I need help optimizing a database query that's taking too long",
            agent_output="Let's look at the query. Common optimizations include adding indexes, reducing joins, and caching results.",
            importance_hint=0.6,
        ),
        Turn(
            user_input="The query joins 4 tables and filters by date range. It takes 3 seconds.",
            agent_output="For a 4-table join with date filtering, I'd suggest: 1) Add a composite index on the date column, 2) Check if any joins can be replaced with subqueries, 3) Consider partitioning by date.",
            contains_fact=True,
            fact_content="User has a slow 4-table join query taking 3 seconds",
            importance_hint=0.7,
        ),
        Turn(
            user_input="I prefer using raw SQL over ORM for complex queries",
            agent_output="That's a solid approach for complex queries. ORMs can generate suboptimal SQL for multi-table joins. Raw SQL gives you full control over the execution plan.",
            contains_fact=True,
            fact_content="User prefers raw SQL over ORM for complex queries",
            importance_hint=0.6,
        ),
    ]

    scenarios.append(
        Scenario(
            scenario_id=f"coding_db_{user.user_id}",
            use_case="coding",
            turns=turns,
            planted_facts=[
                f"User uses {lang} with {framework}",
                "User prefers raw SQL over ORM for complex queries",
            ],
            recall_queries=[
                ("What language does the user program in?", lang),
                ("What does the user prefer for database queries?", "raw SQL"),
            ],
        )
    )

    return scenarios


def _companion_scenarios(user: UserProfile, rng: random.Random) -> list[Scenario]:
    """Generate personal companion scenarios."""
    scenarios = []
    hobbies = ["painting", "running", "cooking", "reading", "gaming", "gardening", "photography"]
    foods = ["sushi", "pizza", "thai food", "tacos", "ramen", "pasta"]
    hobby = rng.choice(hobbies)
    food = rng.choice(foods)

    turns = [
        Turn(
            user_input=f"I just got back from {hobby}. It was amazing today!",
            agent_output=f"That sounds wonderful! What made today's {hobby} session special?",
            contains_fact=True,
            fact_content=f"User enjoys {hobby}",
            expected_emotion="happy",
            importance_hint=0.7,
        ),
        Turn(
            user_input="I finally nailed something I've been practicing for weeks",
            agent_output="That breakthrough feeling is the best! All that practice paid off.",
            expected_emotion="proud",
            importance_hint=0.8,
        ),
        Turn(
            user_input=f"Thinking of celebrating with some {food} tonight",
            agent_output=f"Perfect way to celebrate! {food.title()} sounds delicious.",
            contains_fact=True,
            fact_content=f"User likes {food}",
            importance_hint=0.5,
        ),
        Turn(
            user_input="I've been feeling stressed about work lately though",
            agent_output="I hear you. It's good that you have hobbies to decompress. Want to talk about what's stressing you?",
            expected_emotion="stressed",
            importance_hint=0.7,
        ),
        Turn(
            user_input="My project deadline got moved up by two weeks",
            agent_output="That's a lot of pressure. Have you been able to adjust your plan?",
            contains_fact=True,
            fact_content="User is stressed about a project deadline moved up by two weeks",
            expected_emotion="anxious",
            importance_hint=0.8,
        ),
    ]

    scenarios.append(
        Scenario(
            scenario_id=f"companion_daily_{user.user_id}",
            use_case="companion",
            turns=turns,
            planted_facts=[
                f"User enjoys {hobby}",
                f"User likes {food}",
                "User is stressed about a project deadline moved up by two weeks",
            ],
            recall_queries=[
                ("What hobby does the user enjoy?", hobby),
                ("What food does the user like?", food),
                ("What is the user stressed about?", "deadline"),
            ],
        )
    )

    return scenarios


def _knowledge_scenarios(user: UserProfile, rng: random.Random) -> list[Scenario]:
    """Generate knowledge worker scenarios."""
    scenarios = []
    domains = [
        "machine learning",
        "marketing analytics",
        "financial modeling",
        "UX research",
        "content strategy",
    ]
    tools = ["Excel", "Python", "Tableau", "Notion", "Figma"]
    domain = rng.choice(domains)
    tool = rng.choice(tools)

    turns = [
        Turn(
            user_input=f"I'm researching {domain} for a report due next week",
            agent_output=f"What angle are you taking on {domain}? I can help you structure the research.",
            contains_fact=True,
            fact_content=f"User is researching {domain}",
            importance_hint=0.7,
        ),
        Turn(
            user_input=f"I mainly use {tool} for my analysis work",
            agent_output=f"{tool} is a solid choice. What specific analysis are you running?",
            contains_fact=True,
            fact_content=f"User uses {tool} for analysis",
            importance_hint=0.6,
        ),
        Turn(
            user_input="I need to compare 3 different approaches and recommend one",
            agent_output="A comparison framework would help. Consider evaluating each approach on: effectiveness, cost, implementation complexity, and time to results.",
            importance_hint=0.5,
        ),
        Turn(
            user_input="My boss prefers data-driven recommendations with clear visuals",
            agent_output="Got it. I'd suggest leading with a summary table, then supporting each recommendation with 2-3 key data points and a chart.",
            contains_fact=True,
            fact_content="User's boss prefers data-driven recommendations with visuals",
            importance_hint=0.7,
        ),
    ]

    scenarios.append(
        Scenario(
            scenario_id=f"knowledge_research_{user.user_id}",
            use_case="knowledge",
            turns=turns,
            planted_facts=[
                f"User is researching {domain}",
                f"User uses {tool} for analysis",
                "User's boss prefers data-driven recommendations with visuals",
            ],
            recall_queries=[
                ("What is the user researching?", domain),
                ("What tool does the user prefer?", tool),
            ],
        )
    )

    return scenarios


SCENARIO_GENERATORS = {
    "support": _support_scenarios,
    "coding": _coding_scenarios,
    "companion": _companion_scenarios,
    "knowledge": _knowledge_scenarios,
}


def generate_scenarios(
    user: UserProfile,
    use_case: str,
    seed: int = 42,
) -> list[Scenario]:
    """Generate all scenarios for a user in a given use case."""
    rng = random.Random(seed + user.user_id)
    generator = SCENARIO_GENERATORS.get(use_case)
    if not generator:
        raise ValueError(f"Unknown use case: {use_case}")
    return generator(user, rng)
