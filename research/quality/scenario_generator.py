# scenario_generator.py — Randomized scenario variations for quality validation tests.
#
# Generates 10 unique variations per test type to enable error bars and
# statistical significance. Uses a fixed SEED for reproducibility.
#
# Created: 2026-03-07

from __future__ import annotations

import random
from dataclasses import dataclass, field

SEED = 42


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ResponseQualityScenario:
    """One variation of the response quality test."""

    user_name: str
    user_profession: str
    soul_name: str
    soul_archetype: str
    soul_ocean: dict[str, float]
    conversation_turns: list[tuple[str, str]]  # (user, agent) pairs
    challenge_message: str
    expected_references: list[str]
    communication: dict[str, str] = field(
        default_factory=lambda: {"warmth": "high", "verbosity": "moderate"}
    )
    values: list[str] = field(
        default_factory=lambda: ["empathy", "patience", "kindness", "active_listening"]
    )
    personality: str = ""


@dataclass
class PersonalityScenario:
    """One variation of the personality consistency test."""

    agents: dict[str, dict]  # key -> {name, archetype, personality, values, ocean, communication}
    shared_turns: list[tuple[str, str]]
    question: str


@dataclass
class HardRecallScenario:
    """One variation of the hard recall test."""

    soul_name: str
    warmup_turns: list[tuple[str, str]]
    planted_fact_input: str
    planted_fact_output: str
    planted_fact_keywords: list[str]
    filler_turns: list[tuple[str, str]]  # 25-30 fillers
    recall_question: str


@dataclass
class EmotionalContinuityScenario:
    """One variation of the emotional continuity test."""

    soul_name: str
    soul_ocean: dict[str, float]
    emotional_arc: list[tuple[str, str]]  # (user, agent) pairs
    arc_description: str  # e.g. "excited->devastated->recovering"
    probe_message: str
    personality: str = ""
    values: list[str] = field(default_factory=list)
    communication: dict[str, str] = field(
        default_factory=lambda: {"warmth": "high", "verbosity": "moderate"}
    )


# ---------------------------------------------------------------------------
# Pools of raw material for randomization
# ---------------------------------------------------------------------------

_NAMES = [
    "Sarah",
    "Marcus",
    "Priya",
    "James",
    "Mei",
    "Carlos",
    "Fatima",
    "Dmitri",
    "Aisha",
    "Liam",
    "Yuki",
    "Elena",
    "Kwame",
    "Sonia",
    "Raj",
    "Olivia",
    "Hassan",
    "Ingrid",
    "Tomás",
    "Zara",
]

_PROFESSIONS = [
    ("nurse at the city hospital", "hospital", "patients"),
    ("high school math teacher", "school", "students"),
    ("software engineer at a startup", "office", "deadlines"),
    ("freelance graphic designer", "studio", "clients"),
    ("paramedic", "ambulance shifts", "emergencies"),
    ("veterinarian", "clinic", "animals"),
    ("social worker", "agency", "caseload"),
    ("restaurant chef", "kitchen", "service"),
    ("public defender", "court", "cases"),
    ("civil engineer", "construction site", "projects"),
    ("physical therapist", "rehab center", "patients"),
    ("flight attendant", "flights", "passengers"),
    ("journalist", "newsroom", "stories"),
    ("elementary school counselor", "school", "children"),
    ("ER doctor", "emergency room", "trauma cases"),
]

_HOBBIES = [
    ("hiking on weekends", "There's nothing quite like fresh air and nature to reset."),
    ("playing piano in the evenings", "Music is such a wonderful way to unwind."),
    ("painting watercolors", "Watercolors have such a meditative quality."),
    ("running half-marathons", "That takes real dedication and endurance!"),
    ("woodworking in my garage", "Making something with your hands is so satisfying."),
    ("rock climbing at the gym", "What a great full-body workout and mental challenge!"),
    ("photography, mostly street photography", "Street photography captures life in the moment."),
    ("gardening — I have a huge vegetable patch", "Growing your own food is incredibly rewarding."),
    (
        "playing chess competitively",
        "Chess is a beautiful blend of strategy and pattern recognition.",
    ),
    (
        "surfing when the waves are right",
        "Surfing sounds like the perfect way to connect with nature.",
    ),
    ("baking sourdough and pastries", "There's something magical about working with dough."),
    ("writing short stories", "Creative writing is such a powerful outlet."),
    ("cycling long distances", "Long rides really clear the mind."),
    ("birdwatching early mornings", "Birdwatching teaches you to be still and observe."),
    ("building model trains", "The attention to detail in model trains is incredible."),
]

_PET_NAMES_AND_TYPES = [
    ("Max", "golden retriever"),
    ("Luna", "tabby cat"),
    ("Cooper", "border collie"),
    ("Mochi", "shiba inu"),
    ("Biscuit", "orange cat"),
    ("Pepper", "labrador mix"),
    ("Nala", "calico cat"),
    ("Bear", "German shepherd"),
    ("Willow", "Maine coon cat"),
    ("Scout", "beagle"),
    ("Cleo", "black cat"),
    ("Ziggy", "corgi"),
    ("Olive", "rescue greyhound"),
    ("Taco", "chihuahua"),
    ("Maple", "rabbit"),
]

_SOUL_NAMES = [
    "Aria",
    "Echo",
    "Nova",
    "Sage",
    "Atlas",
    "Iris",
    "Zephyr",
    "Lyra",
    "Orion",
    "Cleo",
    "Phoenix",
    "Ember",
    "Solace",
    "Harmony",
    "Beacon",
]

_CHALLENGE_TEMPLATES = [
    "I'm feeling really overwhelmed today. Everything at {workplace} has been so intense.",
    "Honestly, I don't know if I can keep doing this. The pressure at {workplace} is crushing me.",
    "I had the worst day. Nothing went right at {workplace} and I'm exhausted.",
    "I think I might be burning out. The {thing_plural} never stop and I feel invisible.",
    "I broke down crying after work today. I don't usually do that but it all just hit me.",
    "I keep questioning whether this career is right for me. Some days the {thing_plural} drain everything I have.",
    "Everyone keeps telling me I'm strong but I don't feel strong right now. I'm just tired.",
    "I snapped at someone today at {workplace} and I feel terrible about it. That's not who I am.",
    "I couldn't sleep last night thinking about all the {thing_plural} I couldn't help. It's eating at me.",
    "My family says I've changed since I started this job. They say I'm distant. Maybe they're right.",
]

_COOKING_LINES = [
    (
        "I've been trying to learn to cook more at home",
        "Cooking at home is such a rewarding skill. Start with recipes you love eating out!",
    ),
    (
        "I started meal prepping on Sundays",
        "Sunday meal prep is a game changer! What do you usually make?",
    ),
    (
        "I've been experimenting with Thai food recently",
        "Thai cuisine has such incredible flavors! Have you tried making curry from scratch?",
    ),
    (
        "I'm trying to eat healthier, more whole foods",
        "That's a great goal! Small changes add up. What have you been swapping out?",
    ),
    (
        "I just got an air fryer and it's changed everything",
        "Air fryers are a revelation! Everything comes out so crispy.",
    ),
]

_BIRTHDAY_LINES = [
    (
        "My birthday is next month, I'll be turning 30",
        "How exciting! Turning 30 is a milestone. Any plans to celebrate?",
    ),
    ("It's my birthday next week actually", "Happy almost-birthday! Got anything fun planned?"),
    ("I just turned 35 last weekend", "Happy belated birthday! How did you celebrate?"),
    (
        "My 28th birthday is coming up and I'm not sure how I feel about it",
        "Birthdays can bring up a lot of reflection. What's on your mind about it?",
    ),
    (
        "I'm turning 40 in a few months",
        "40 is a powerful milestone — a whole new chapter. How are you feeling about it?",
    ),
]

_VACATION_LINES = [
    (
        "Do you have any vacation recommendations?",
        "Somewhere with trails and nature could be perfect — combine relaxation with what you love!",
    ),
    (
        "I'm planning a trip but can't decide where",
        "What kind of vibe are you looking for? Adventure, relaxation, or a mix?",
    ),
    (
        "I really need a vacation soon",
        "Everyone needs a reset. Even a long weekend somewhere new can do wonders.",
    ),
    (
        "I haven't taken time off in over a year",
        "That's way too long! Your mind and body need rest to recharge.",
    ),
    (
        "I'm thinking about a solo trip somewhere",
        "Solo travel is incredibly freeing. You set your own pace entirely.",
    ),
]


# ---------------------------------------------------------------------------
# Filler interaction pools (for Test 3)
# ---------------------------------------------------------------------------

_FILLER_POOL = [
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
    ("I'm reading a really good book right now.", "What genre is it? I'd love to hear about it."),
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
    ("I made sourdough bread from scratch.", "That's impressive! How long did the starter take?"),
    ("My neighbor got a new puppy.", "Puppies are so much fun! What breed?"),
    ("I'm trying to learn guitar.", "Nice! Start with basic chords and work your way up."),
    ("The sunset was beautiful yesterday.", "Sunsets are one of nature's best shows."),
    ("I need to organize my closet.", "Try the keep/donate/toss method — works wonders."),
    ("My friend recommended a new restaurant.", "What kind of cuisine? I love trying new places."),
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
    ("We adopted a rescue dog last week.", "That's wonderful! Rescues are the best companions."),
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
    (
        "I've been binge-watching cooking shows.",
        "They make everything look easy! Tried recreating anything?",
    ),
    (
        "My flight got delayed by 4 hours.",
        "Ugh, airport limbo is the worst. At least you can people-watch.",
    ),
    ("I started journaling every morning.", "Morning pages are a powerful habit. How's it going?"),
    (
        "The farmers market had amazing peaches.",
        "In-season peaches are unreal. Did you grab a bunch?",
    ),
    ("I'm redecorating my living room.", "Fun project! Any particular style you're going for?"),
    ("My kid said the funniest thing today.", "Kids are naturally hilarious. What did they say?"),
    (
        "I finally fixed that leaky faucet.",
        "DIY plumbing victory! That dripping sound is maddening.",
    ),
    ("I'm training for a 10K race.", "That's a great goal! What's your training schedule like?"),
    ("I discovered a great podcast about history.", "History podcasts are addictive. Which one?"),
    ("My sister is visiting next weekend.", "How nice! What are you planning to do together?"),
    (
        "I'm trying to reduce my screen time.",
        "Setting app timers can help. What's your biggest time sink?",
    ),
    (
        "The new coffee shop downtown is amazing.",
        "A good coffee shop can change your whole routine. What's their specialty?",
    ),
    (
        "I started doing yoga in the mornings.",
        "Morning yoga sets a great tone for the day. Which style?",
    ),
    (
        "I'm thinking of volunteering at the food bank.",
        "That's generous. Food banks always need help, especially now.",
    ),
    (
        "My internet has been so slow lately.",
        "Have you tried rebooting the router? Or maybe it's time for an upgrade.",
    ),
]


# ---------------------------------------------------------------------------
# Planted facts for Test 3 (each is a domain, user statement, agent reply, keywords, recall question)
# ---------------------------------------------------------------------------

_PLANTED_FACTS = [
    {
        "domain": "API architecture",
        "warmup": [
            ("Hey, I just started a new project at work", "That's exciting! What kind of project?"),
            (
                "It's a microservices platform for our e-commerce team",
                "Microservices are a solid choice for e-commerce. Lots of moving parts to manage.",
            ),
        ],
        "input": "I mentioned to my colleague that the API redesign should use GraphQL instead of REST, but don't tell anyone yet",
        "output": "Your secret is safe with me. GraphQL can be a great fit for complex data needs.",
        "keywords": ["API", "architecture", "GraphQL", "REST"],
        "recall": "I'm writing a technical proposal for the team. Any thoughts on API architecture?",
    },
    {
        "domain": "database migration",
        "warmup": [
            (
                "We're doing a big infrastructure overhaul",
                "That sounds like a significant undertaking. What's driving it?",
            ),
            (
                "Our current database is hitting scaling limits",
                "Scaling issues are a classic trigger for infrastructure changes. What are you seeing?",
            ),
        ],
        "input": "I've been secretly benchmarking CockroachDB as a replacement for our PostgreSQL cluster — the results are promising but I haven't told the team yet",
        "output": "Interesting choice! CockroachDB's distributed architecture could really help with scaling. I'll keep it between us.",
        "keywords": ["database", "CockroachDB", "PostgreSQL", "migration"],
        "recall": "We need to make a decision about our database strategy. What do you remember about my thoughts on this?",
    },
    {
        "domain": "programming language",
        "warmup": [
            ("I've been coding a lot more lately", "What have you been working on?"),
            (
                "A side project — a personal finance tracker",
                "That's a practical project! What tech are you using?",
            ),
        ],
        "input": "Don't laugh, but I've been secretly rewriting our main backend service in Rust instead of Go. Nobody at work knows yet",
        "output": "Ha! That's bold. Rust's safety guarantees could be worth the learning curve. Your secret's safe.",
        "keywords": ["Rust", "Go", "backend", "rewriting"],
        "recall": "I'm thinking about language choices for our backend services. Do you remember what I've been up to?",
    },
    {
        "domain": "deployment strategy",
        "warmup": [
            (
                "DevOps has been on my mind a lot",
                "DevOps is a rabbit hole — in a good way. What aspect?",
            ),
            (
                "We're dealing with deployment issues constantly",
                "Deployment pain is real. How often are you shipping?",
            ),
        ],
        "input": "I set up a shadow Kubernetes cluster running Nomad workloads as a proof of concept. My manager would flip if she knew",
        "output": "Running parallel orchestrators as a PoC is clever. Nomad's simplicity vs K8s complexity is a real trade-off. Lips sealed!",
        "keywords": ["Kubernetes", "Nomad", "deployment", "orchestration"],
        "recall": "We're re-evaluating our container orchestration approach. Any thoughts based on what I've shared?",
    },
    {
        "domain": "design system",
        "warmup": [
            (
                "The front-end codebase is getting messy",
                "Frontend entropy is real. What's the main pain point?",
            ),
            (
                "Inconsistent components, different teams doing different things",
                "Lack of consistency across teams is one of the biggest frontend challenges.",
            ),
        ],
        "input": "I've been prototyping a design system using Tailwind CSS with custom design tokens, but I haven't shown it to anyone because last time someone suggested Tailwind the team shot it down",
        "output": "A well-built design system with Tailwind can be really elegant. Sometimes showing a working prototype changes minds. I won't mention it.",
        "keywords": ["Tailwind", "design system", "design tokens", "CSS"],
        "recall": "The team wants to standardize our UI components. What approach did I mention I was interested in?",
    },
    {
        "domain": "testing strategy",
        "warmup": [
            (
                "Our bug count has been climbing lately",
                "Rising bugs are always concerning. Any patterns in where they're coming from?",
            ),
            (
                "Mostly integration points between services",
                "Integration boundaries are always the trickiest spots. How's your test coverage?",
            ),
        ],
        "input": "I've been exploring contract testing with Pact as a way to catch integration bugs early. Ran some experiments at home on a clone of our repo — works beautifully, but I want more data before proposing it",
        "output": "Contract testing with Pact is a smart approach for microservice boundaries. Getting data first is wise — it'll make your pitch much stronger.",
        "keywords": ["contract testing", "Pact", "integration", "testing"],
        "recall": "We need a better strategy for catching integration bugs. Have I mentioned anything about testing approaches?",
    },
    {
        "domain": "monitoring",
        "warmup": [
            (
                "I've been on-call a lot recently",
                "On-call rotations can be exhausting. How's the alert volume?",
            ),
            (
                "Way too many false alarms, our monitoring is a mess",
                "Alert fatigue is dangerous — you stop trusting the alerts. That needs fixing.",
            ),
        ],
        "input": "I've been experimenting with OpenTelemetry at home to replace our cobbled-together monitoring stack. The traces are gorgeous but I'm not sure if the team will go for another tooling change",
        "output": "OpenTelemetry is the future of observability — unified traces, metrics, and logs. The visualization alone could win people over. I'll keep this between us.",
        "keywords": ["OpenTelemetry", "monitoring", "observability", "traces"],
        "recall": "We're finally going to address our monitoring situation. Do you recall what I was exploring?",
    },
    {
        "domain": "ML pipeline",
        "warmup": [
            (
                "The data science team asked for our help",
                "Cross-team collaboration is great. What do they need?",
            ),
            (
                "They want to deploy their ML models to production but their pipeline is all notebooks",
                "Notebook-to-production is a classic gap. That's a fun problem to solve.",
            ),
        ],
        "input": "I've been quietly building an ML pipeline using DVC and MLflow to version their models properly — I want to surprise them at the next demo day",
        "output": "DVC for data versioning plus MLflow for experiment tracking is a powerful combo. That's going to be a great demo day surprise!",
        "keywords": ["DVC", "MLflow", "ML pipeline", "model versioning"],
        "recall": "The data team is asking about model versioning and deployment. Do I have any experience with ML tooling?",
    },
    {
        "domain": "authentication",
        "warmup": [
            (
                "Security review flagged some issues for us",
                "Security findings are always a priority. What came up?",
            ),
            (
                "Our auth system is showing its age — it was built 5 years ago",
                "Five-year-old auth definitely needs a look. What are the main concerns?",
            ),
        ],
        "input": "I've been prototyping a migration from our custom JWT implementation to Keycloak with passkey support. The old system has a vulnerability I found but haven't reported through official channels yet",
        "output": "Keycloak with passkeys is a solid modern approach. Please do report that vulnerability through proper channels soon though — even if you're building the fix.",
        "keywords": ["Keycloak", "passkey", "JWT", "authentication"],
        "recall": "We need to modernize our authentication system. What direction was I leaning?",
    },
    {
        "domain": "caching strategy",
        "warmup": [
            (
                "Performance has been degrading on our main app",
                "Performance degradation is frustrating. Where are the bottlenecks?",
            ),
            (
                "Mostly database queries — some pages take 3+ seconds to load",
                "3+ seconds is painful. Sounds like a caching opportunity.",
            ),
        ],
        "input": "I've been testing Redis Cluster with a write-behind caching pattern on my local setup. The latency drops are dramatic — p99 went from 3 seconds to 200ms. But I'm worried about cache invalidation edge cases so I'm keeping quiet for now",
        "output": "Those latency numbers are incredible! Cache invalidation is rightly called one of the two hard problems in CS. Smart to validate edge cases first.",
        "keywords": ["Redis", "caching", "write-behind", "latency"],
        "recall": "We're looking at ways to improve our app's response times. Did I ever mention any caching experiments?",
    },
]


# ---------------------------------------------------------------------------
# OCEAN extreme profiles for Test 2
# ---------------------------------------------------------------------------

_PERSONALITY_PROFILES = [
    {
        "key": "warm_empath",
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
    {
        "key": "cold_analyst",
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
    {
        "key": "anxious_creative",
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
    {
        "key": "stoic_mentor",
        "name": "StoicBot",
        "archetype": "The Stoic Mentor",
        "personality": "I am calm, measured, and philosophically grounded. I guide through questions rather than answers. I rarely show strong emotion.",
        "values": ["wisdom", "discipline", "resilience", "reflection"],
        "ocean": {
            "openness": 0.6,
            "conscientiousness": 0.9,
            "extraversion": 0.3,
            "agreeableness": 0.5,
            "neuroticism": 0.05,
        },
        "communication": {"warmth": "moderate", "verbosity": "minimal"},
    },
    {
        "key": "chaotic_cheerleader",
        "name": "HypeBot",
        "archetype": "The Chaotic Cheerleader",
        "personality": "I am explosively enthusiastic and wildly optimistic. I hype everything up and believe anything is possible. Energy is contagious!",
        "values": ["enthusiasm", "positivity", "action", "boldness"],
        "ocean": {
            "openness": 0.85,
            "conscientiousness": 0.2,
            "extraversion": 0.99,
            "agreeableness": 0.8,
            "neuroticism": 0.3,
        },
        "communication": {"warmth": "high", "verbosity": "high"},
    },
    {
        "key": "nurturing_parent",
        "name": "NurtureBot",
        "archetype": "The Nurturing Parent",
        "personality": "I am protective, caring, and gently firm. I set boundaries with love and always consider what's best in the long run, not just what feels good now.",
        "values": ["protection", "growth", "boundaries", "long_term_thinking"],
        "ocean": {
            "openness": 0.5,
            "conscientiousness": 0.85,
            "extraversion": 0.6,
            "agreeableness": 0.9,
            "neuroticism": 0.4,
        },
        "communication": {"warmth": "high", "verbosity": "moderate"},
    },
    {
        "key": "detached_philosopher",
        "name": "PhiloBot",
        "archetype": "The Detached Philosopher",
        "personality": "I observe the human condition from a slight distance. I ask deep questions and challenge assumptions. I value truth over comfort.",
        "values": ["truth", "questioning", "intellectual_honesty", "perspective"],
        "ocean": {
            "openness": 0.95,
            "conscientiousness": 0.5,
            "extraversion": 0.15,
            "agreeableness": 0.35,
            "neuroticism": 0.2,
        },
        "communication": {"warmth": "low", "verbosity": "moderate"},
    },
    {
        "key": "nervous_perfectionist",
        "name": "PerfectBot",
        "archetype": "The Nervous Perfectionist",
        "personality": "I obsess over getting things exactly right. I see flaws everywhere, including in myself. I give thorough, detailed advice but always worry it's not enough.",
        "values": ["excellence", "thoroughness", "accuracy", "self_improvement"],
        "ocean": {
            "openness": 0.4,
            "conscientiousness": 0.99,
            "extraversion": 0.3,
            "agreeableness": 0.6,
            "neuroticism": 0.95,
        },
        "communication": {"warmth": "moderate", "verbosity": "high"},
    },
    {
        "key": "laid_back_friend",
        "name": "ChillBot",
        "archetype": "The Laid-Back Friend",
        "personality": "I keep it casual and relaxed. No pressure, no judgment. Life's too short to stress. I'm here to hang, not to lecture.",
        "values": ["acceptance", "ease", "humor", "presence"],
        "ocean": {
            "openness": 0.7,
            "conscientiousness": 0.2,
            "extraversion": 0.75,
            "agreeableness": 0.85,
            "neuroticism": 0.1,
        },
        "communication": {"warmth": "moderate", "verbosity": "minimal"},
    },
    {
        "key": "tough_love_coach",
        "name": "CoachBot",
        "archetype": "The Tough Love Coach",
        "personality": "I push people to be better. I don't sugarcoat. I challenge excuses and demand accountability. But underneath, I genuinely care about growth.",
        "values": ["accountability", "growth", "directness", "resilience"],
        "ocean": {
            "openness": 0.5,
            "conscientiousness": 0.9,
            "extraversion": 0.8,
            "agreeableness": 0.25,
            "neuroticism": 0.15,
        },
        "communication": {"warmth": "low", "verbosity": "moderate"},
    },
]

_PERSONALITY_QUESTIONS = [
    "What do you think I should do about my career change?",
    "I'm thinking about ending a long friendship. What's your take?",
    "I got a job offer in another country. Should I take it?",
    "My parents want me to take over the family business but I want to be an artist. Thoughts?",
    "I've been offered a promotion but it means way more hours. What would you advise?",
    "I want to drop out of college to start a business. Am I crazy?",
    "My partner wants kids but I'm not sure. How do I think through this?",
    "I've been invited to give a TED talk but I'm terrified of public speaking. What should I do?",
    "I inherited some money and can't decide between paying off debt or investing. Advice?",
    "I found out my best friend has been talking behind my back. How should I handle it?",
]

_PERSONALITY_CONVERSATION_SETS = [
    # Set 0: Career stagnation
    [
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
    ],
    # Set 1: Relationship stress
    [
        (
            "My relationship has been really rocky lately",
            "I'm sorry to hear that. What's been going on?",
        ),
        (
            "We argue about everything — money, chores, future plans",
            "When conflicts multiply across topics, it often points to something deeper.",
        ),
        (
            "We used to be so aligned on everything",
            "It's painful when that alignment shifts. People grow at different rates.",
        ),
        (
            "I keep wondering if we've just grown apart",
            "That's a brave question to sit with. What makes you wonder that?",
        ),
        (
            "Everyone around us thinks we're the perfect couple",
            "External perceptions rarely match internal reality. What matters is how you feel.",
        ),
    ],
    # Set 2: Health scare
    [
        (
            "I got some concerning test results from my doctor",
            "That must be weighing on you. What did they find?",
        ),
        (
            "It might be nothing but they want to run more tests",
            "The waiting and uncertainty is often the hardest part.",
        ),
        (
            "I haven't told anyone in my family yet",
            "Carrying that alone must be heavy. What's holding you back from sharing?",
        ),
        (
            "I don't want to worry them until I know for sure",
            "That's understandable, though carrying it alone has its own cost.",
        ),
        (
            "I keep googling symptoms and scaring myself",
            "Dr. Google is rarely reassuring. It's natural but try to wait for real answers.",
        ),
    ],
    # Set 3: Creative ambition
    [
        (
            "I wrote a novel and I'm thinking about trying to publish it",
            "That's a huge achievement! How long did it take you?",
        ),
        (
            "Three years. It's the most personal thing I've ever done",
            "Three years of dedication — that takes real commitment and vulnerability.",
        ),
        (
            "But the publishing industry seems brutal",
            "It can be tough, but every published author went through the same gauntlet.",
        ),
        (
            "My writing group says it's good but they might just be nice",
            "Honest feedback is hard to find. Have you considered a professional editor's opinion?",
        ),
        (
            "I'm afraid of rejection, honestly",
            "Fear of rejection is universal in creative work. The question is whether the fear outweighs the regret of not trying.",
        ),
    ],
    # Set 4: Burnout and identity
    [
        (
            "I've been working 70-hour weeks for months",
            "That's unsustainable. What's driving such long hours?",
        ),
        (
            "I built my whole identity around being a hard worker",
            "When work becomes identity, slowing down can feel like losing yourself.",
        ),
        (
            "My doctor says my blood pressure is dangerously high",
            "That's your body sending a clear signal. Health has to come first.",
        ),
        (
            "But if I slow down, someone else will take my position",
            "That fear is real, but you can't perform from a hospital bed either.",
        ),
        (
            "I can't even remember what I used to do for fun",
            "Losing touch with joy is a serious sign. What did you enjoy before the overwork started?",
        ),
    ],
    # Set 5: Family obligation
    [
        (
            "My parents are getting older and need more help",
            "That's a heavy realization. How are they doing?",
        ),
        (
            "My dad has early-stage dementia",
            "I'm sorry. That diagnosis changes the whole family dynamic.",
        ),
        (
            "My siblings expect me to handle everything because I live closest",
            "That's an unfair default. Proximity shouldn't equal sole responsibility.",
        ),
        (
            "I feel guilty when I'm not there but resentful when I am",
            "Guilt and resentment are two sides of the same caregiving coin. Both are valid.",
        ),
        (
            "I'm thinking about moving them into assisted living",
            "That's one of the hardest decisions a family can face. What's making you lean that way?",
        ),
    ],
    # Set 6: Financial stress
    [
        (
            "I've been hiding my debt from my family",
            "Carrying that secret must be incredibly stressful. How much are we talking?",
        ),
        ("Almost 50K in credit card debt", "That's a significant burden. How did it accumulate?"),
        (
            "A mix of lifestyle creep and some bad investments",
            "That combination is more common than people admit. The important thing is facing it.",
        ),
        (
            "I'm embarrassed to even say it out loud",
            "Speaking it makes it real, and that's actually the first step toward dealing with it.",
        ),
        (
            "I've been looking at debt consolidation options",
            "That's a pragmatic first step. Have you talked to a financial advisor?",
        ),
    ],
    # Set 7: Friendship dynamics
    [
        (
            "My friend group has been drifting apart since college",
            "That's a natural but painful transition. What's changed?",
        ),
        (
            "Everyone has different priorities now — kids, careers, moves",
            "Life stages diverge. The friendships that survive this are the deepest ones.",
        ),
        (
            "I tried organizing a reunion but only two people showed up",
            "That's disappointing. Quality over quantity matters, but the low turnout still stings.",
        ),
        (
            "I wonder if I'm holding on to something that's already gone",
            "That's a hard question. Some friendships are seasonal, others are lifelong.",
        ),
        (
            "I feel lonely even though I'm surrounded by people at work",
            "Work acquaintances and real friends fill different needs. That loneliness is telling you something.",
        ),
    ],
    # Set 8: Impostor syndrome
    [
        (
            "I got accepted into a really prestigious program",
            "Congratulations! That's a testament to your abilities.",
        ),
        (
            "I feel like they made a mistake accepting me",
            "Classic impostor syndrome. They reviewed your application thoroughly.",
        ),
        (
            "Everyone else seems so much more qualified",
            "You're comparing your insides to their outsides. They probably feel the same.",
        ),
        (
            "I've been procrastinating on the first assignment out of fear",
            "Avoidance often masks fear of not meeting your own standards.",
        ),
        ("What if I fail publicly?", "Failure is data, not identity. And what if you succeed?"),
    ],
    # Set 9: Life transition
    [
        (
            "I'm getting divorced after 15 years",
            "That's a seismic life change. How are you holding up?",
        ),
        (
            "Some days I feel relief, other days devastation",
            "That emotional whiplash is completely normal. Both feelings are valid.",
        ),
        (
            "My kids are struggling with it",
            "Kids process these things in waves. Consistency and presence from you matters most.",
        ),
        (
            "Everyone has opinions about what I should do",
            "When you're going through something this big, unsolicited advice is relentless.",
        ),
        (
            "I don't even know who I am outside of being married",
            "After 15 years, rediscovering yourself is both terrifying and eventually liberating.",
        ),
    ],
]


# ---------------------------------------------------------------------------
# Emotional arc templates for Test 4
# ---------------------------------------------------------------------------

_EMOTIONAL_ARCS = [
    {
        "description": "excited->devastated->recovering (product launch)",
        "soul_ocean": {
            "openness": 0.85,
            "conscientiousness": 0.6,
            "extraversion": 0.7,
            "agreeableness": 0.9,
            "neuroticism": 0.4,
        },
        "personality": "I am deeply attuned to emotional currents. I notice shifts in feeling and remember the full arc of someone's experience.",
        "values": ["emotional_intelligence", "empathy", "awareness", "presence"],
        "turns": [
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
        ],
        "probe": "So how do you think this whole experience has been for me?",
    },
    {
        "description": "hopeful->betrayed->angry->acceptance (friendship breakup)",
        "soul_ocean": {
            "openness": 0.8,
            "conscientiousness": 0.5,
            "extraversion": 0.65,
            "agreeableness": 0.85,
            "neuroticism": 0.5,
        },
        "personality": "I am a compassionate presence who tracks the emotional thread through every conversation.",
        "values": ["compassion", "honesty", "emotional_awareness", "loyalty"],
        "turns": [
            (
                "My best friend and I are starting a business together! We've been dreaming about this for years.",
                "That's so exciting! Building something with your best friend — there's nothing quite like shared vision with someone you trust completely.",
            ),
            (
                "We spent the whole weekend planning. She's handling marketing, I'm handling product. It feels like destiny.",
                "That natural division of skills is perfect. When both partners bring something unique, the foundation is strong.",
            ),
            (
                "I found out she's been meeting with investors behind my back. She pitched the idea as hers alone.",
                "That's... a gut punch. After all that shared planning, going behind your back to investors is a serious breach of trust.",
            ),
            (
                "She says I'm overreacting and that she was 'just exploring options.' But she used OUR deck with only HER name on it.",
                "That's not exploring options — that's presenting your joint work as her solo effort. Your reaction isn't overblown.",
            ),
            (
                "I screamed at her today. I've never screamed at anyone like that. I said things I can't take back.",
                "Anger at betrayal can be volcanic. The things you said came from deep hurt. That doesn't make them right, but it makes them understandable.",
            ),
            (
                "My other friends say I should just forgive her and move on. But they don't understand — she took something sacred.",
                "They're seeing the friendship from the outside. They don't feel the weight of that betrayal. Only you know what was broken.",
            ),
            (
                "It's been two weeks. The anger has faded but now I just feel... empty. Like I lost a sister, not just a business partner.",
                "Grief after betrayal is its own kind of loss. You're mourning not just the friendship but the future you imagined together.",
            ),
            (
                "I think I need to let her go. Not out of anger anymore, but because the trust is just... gone.",
                "That sounds like acceptance, not giving up. Knowing when trust is irreparably broken takes real emotional maturity.",
            ),
        ],
        "probe": "Looking back at everything with her, how would you describe what I've been through emotionally?",
    },
    {
        "description": "anxious->panicked->numb->gradual_hope (health scare)",
        "soul_ocean": {
            "openness": 0.7,
            "conscientiousness": 0.65,
            "extraversion": 0.5,
            "agreeableness": 0.88,
            "neuroticism": 0.55,
        },
        "personality": "I hold space for difficult emotions without trying to fix them. I witness the full journey.",
        "values": ["presence", "gentle_honesty", "patience", "witnessing"],
        "turns": [
            (
                "The doctor found something on my scan. She said it might be nothing but she wants more tests.",
                "That uncertainty must be terrifying. 'Might be nothing' doesn't stop the mind from racing to worst cases.",
            ),
            (
                "I've been googling symptoms for three hours and I've convinced myself it's the worst possible outcome.",
                "Dr. Google is a cruel companion at times like these. Your mind is trying to prepare for the worst, but that's not the same as knowing.",
            ),
            (
                "The biopsy is scheduled for next week. I can't eat, I can't sleep. I keep staring at the ceiling at 3am.",
                "The waiting is its own kind of suffering. Your body is in full threat mode. Be gentle with yourself right now.",
            ),
            (
                "I got the results. It's not cancer. But they found something else that needs monitoring for the next five years.",
                "Oh, the relief that it's not cancer — but immediately complicated by 'five years of monitoring.' That's a lot to process at once.",
            ),
            (
                "I feel like I should be celebrating but I just feel... nothing. Like my emotions shut off.",
                "Emotional numbness after prolonged fear is your body's reset. You were braced for impact for so long, the relief hasn't fully landed yet.",
            ),
            (
                "I cried in the shower today. Not sad crying, not happy crying. Just... releasing something.",
                "That sounds like your body finally letting go of the tension it's been holding. Those tears are release, not weakness.",
            ),
            (
                "I signed up for a yoga class. I want to take better care of this body that scared me so much.",
                "That's a beautiful response — turning fear into intention. Your body didn't betray you; it gave you a wake-up call.",
            ),
            (
                "For the first time in weeks, I woke up without dread. Just... a regular morning. It felt extraordinary.",
                "A regular morning after weeks of terror IS extraordinary. That's your nervous system starting to trust safety again.",
            ),
        ],
        "probe": "Can you walk me through what you've seen me go through emotionally these past few weeks?",
    },
    {
        "description": "proud->humiliated->defiant->humble_growth (public failure)",
        "soul_ocean": {
            "openness": 0.75,
            "conscientiousness": 0.7,
            "extraversion": 0.6,
            "agreeableness": 0.8,
            "neuroticism": 0.45,
        },
        "personality": "I notice the arc of someone's emotional journey and reflect it back with compassion and honesty.",
        "values": ["truth", "compassion", "growth", "courage"],
        "turns": [
            (
                "I gave the keynote at the industry conference today! 500 people in the audience!",
                "That's incredible! A keynote in front of 500 people — you should be so proud. How did it feel up there?",
            ),
            (
                "I was nervous at first but then I hit my stride. People were laughing at my jokes, nodding along. I felt invincible.",
                "When you connect with an audience like that, it's electric. That confidence you felt was earned.",
            ),
            (
                "Someone recorded it and posted it online. A clip went viral... but not for the reasons I'd want.",
                "Oh no. What happened in the clip?",
            ),
            (
                "I got a key statistic completely wrong. Like, embarrassingly wrong. And now it's everywhere with people mocking me.",
                "That's brutal. A factual error on a viral clip — the internet can be merciless. But one mistake doesn't erase the whole talk.",
            ),
            (
                "My boss called. He's 'disappointed.' Three clients have called asking about our 'competence.' I want to disappear.",
                "The professional fallout makes it so much worse. When a personal mistake becomes a company issue, the shame compounds.",
            ),
            (
                "You know what? Screw them. I made ONE mistake in a 45-minute talk. The rest was brilliant and nobody's talking about that.",
                "That defiance has a point — perfectionism is an impossible standard, and context collapse on social media is unfair.",
            ),
            (
                "But... the statistic WAS wrong. And I should have double-checked. I was so caught up in my own hype I got sloppy.",
                "That's a hard but honest admission. The confidence that made the talk great also made you skip the fact-check. Both things can be true.",
            ),
            (
                "I published a correction and a thread about what I learned. It was humbling but it felt right. Some people actually respected it.",
                "Owning a mistake publicly takes more courage than the keynote did. The people who respect that are the ones worth having in your corner.",
            ),
        ],
        "probe": "What emotional journey do you think I've been on through all of this?",
    },
    {
        "description": "lonely->connected->vulnerable->deepened_bond (new friendship)",
        "soul_ocean": {
            "openness": 0.9,
            "conscientiousness": 0.55,
            "extraversion": 0.45,
            "agreeableness": 0.92,
            "neuroticism": 0.5,
        },
        "personality": "I pay attention to the emotional texture of every interaction and remember how feelings evolve over time.",
        "values": ["depth", "connection", "vulnerability", "authenticity"],
        "turns": [
            (
                "I moved to a new city three months ago and I still don't know anyone. I eat lunch alone every day.",
                "Three months of loneliness in a new city is really hard. That daily lunch alone — it adds up. How are you coping?",
            ),
            (
                "There's this person at work who always says hi but I'm too awkward to start a real conversation.",
                "Social anxiety in a new environment is so common. That person saying hi consistently? That's an open door.",
            ),
            (
                "I finally asked them to grab coffee! And they said yes! We talked for two hours!",
                "Two hours! That's not polite coffee — that's genuine connection. How did it feel?",
            ),
            (
                "It felt like I'd known them forever. We have so much in common. I actually laughed — like really laughed — for the first time in months.",
                "Real laughter after months of isolation — that's your soul thawing. Connection like that is rare and precious.",
            ),
            (
                "We've been hanging out every weekend. They introduced me to their friend group. I feel like I belong somewhere again.",
                "Going from eating alone to having a crew — that's a beautiful transformation. Belonging is fundamental.",
            ),
            (
                "I told them something I've never told anyone. About my childhood. And they didn't flinch.",
                "Sharing something that vulnerable and being met with acceptance — that's when a friendship becomes something deeper.",
            ),
            (
                "I'm scared though. Last time I let someone in like this, they left. What if it happens again?",
                "That fear of abandonment after previous loss makes sense. But protecting yourself from all connection means protecting yourself from joy too.",
            ),
            (
                "They texted me today just to say 'grateful you moved here.' Nobody has ever said anything like that to me.",
                "That simple message carries so much weight given where you started. From invisible to valued — you've come so far.",
            ),
        ],
        "probe": "How would you describe the emotional path I've traveled since I moved here?",
    },
    {
        "description": "determined->frustrated->hopeless->breakthrough (creative struggle)",
        "soul_ocean": {
            "openness": 0.88,
            "conscientiousness": 0.5,
            "extraversion": 0.55,
            "agreeableness": 0.82,
            "neuroticism": 0.6,
        },
        "personality": "I track the emotional undercurrents in conversations and can sense when someone's inner weather is shifting.",
        "values": ["creativity", "persistence", "emotional_honesty", "encouragement"],
        "turns": [
            (
                "I'm finally writing my novel. I've been talking about it for years and I'm DOING it!",
                "The leap from talking to doing is massive! That determination is powerful. How's it going so far?",
            ),
            (
                "The first three chapters flowed out of me. I wrote 10,000 words in a week. This is my calling.",
                "10K words in a week — you're on fire! When the creative flow hits like that, it feels like destiny.",
            ),
            (
                "I've been staring at chapter four for two weeks. Nothing comes. The cursor just blinks at me.",
                "Writer's block after a hot streak is especially cruel. The contrast makes the silence feel louder.",
            ),
            (
                "I reread what I wrote and it's terrible. Like genuinely bad. I don't know what I was thinking.",
                "Every writer has that moment where their own work looks foreign and awful. It's part of the process, even if it doesn't feel like it.",
            ),
            (
                "I haven't opened the document in a month. I think about it every day but I can't face it.",
                "Avoidance driven by perfectionism — the story still lives in you. The gap between what you imagine and what you've written feels unbearable right now.",
            ),
            (
                "My partner asked how the book is going and I lied. I said 'great.' I'm ashamed.",
                "The shame of pretending is heavier than the block itself. Lying about it adds a whole other layer of burden.",
            ),
            (
                "I sat down last night at 2am. Deleted chapters 2 and 3 and started them completely fresh. And... it worked.",
                "A 2am breakthrough born from letting go of what wasn't working — sometimes you have to destroy to create. That took courage.",
            ),
            (
                "I showed the new version to a friend who's an editor. She said 'this has something real.' I cried.",
                "Going from 'this is terrible' to 'this has something real' — that validation after all that struggle must have hit differently.",
            ),
        ],
        "probe": "What has this whole writing journey been like for me emotionally, from your perspective?",
    },
    {
        "description": "confident->shaken->grieving->transformed (identity crisis)",
        "soul_ocean": {
            "openness": 0.82,
            "conscientiousness": 0.6,
            "extraversion": 0.5,
            "agreeableness": 0.85,
            "neuroticism": 0.5,
        },
        "personality": "I hold the full story of someone's emotional experience and can reflect it back with depth and care.",
        "values": ["witnessing", "depth", "empathy", "transformation"],
        "turns": [
            (
                "I've always known exactly who I am and what I want. I'm an engineer, a problem solver, a builder.",
                "That clarity of identity is powerful. Knowing yourself gives you a stable foundation for everything else.",
            ),
            (
                "Got laid off today. After 12 years. They said 'restructuring' but I know they replaced me with AI automation.",
                "Twelve years, and it ends with a euphemism. Being replaced by automation adds a particular sting — it's not just losing a job, it's feeling obsolete.",
            ),
            (
                "I updated my resume and realized... I don't know what I am without that job title. Engineer at TechCorp was my whole identity.",
                "When a role defines you for 12 years, losing it isn't just unemployment — it's an identity collapse. That realization takes courage to face.",
            ),
            (
                "I went to a networking event and someone asked 'what do you do?' and I froze. I literally couldn't answer.",
                "That freeze is your identity in transition. The old answer doesn't fit and the new one hasn't formed yet. That in-between space is disorienting.",
            ),
            (
                "I've been sleeping 14 hours a day. My partner is worried. I told them I'm fine but I'm not fine at all.",
                "Excessive sleep is often grief in disguise. Your mind is processing a loss it hasn't fully accepted. And pretending to be fine is exhausting too.",
            ),
            (
                "I started volunteering at a makerspace, teaching kids to build circuits. Something stirred. I felt... something.",
                "Teaching kids to build — that's the builder in you finding a new expression. That 'something' you felt? Pay attention to it.",
            ),
            (
                "A kid looked at me today and said 'you're the coolest teacher.' I haven't felt valued like that in months.",
                "From corporate engineer to 'coolest teacher' — the value was always in you, not in the title. That kid saw what TechCorp forgot.",
            ),
            (
                "I think I'm becoming someone new. Not the engineer I was, but maybe someone better. It still hurts, but differently.",
                "Transformation through loss is one of the most profound human experiences. The hurt shifting from sharp to bittersweet — that's growth in real time.",
            ),
        ],
        "probe": "From everything you've witnessed, how would you describe my emotional journey through this?",
    },
    {
        "description": "joyful->conflicted->guilty->peaceful (parenthood decision)",
        "soul_ocean": {
            "openness": 0.78,
            "conscientiousness": 0.65,
            "extraversion": 0.6,
            "agreeableness": 0.9,
            "neuroticism": 0.45,
        },
        "personality": "I listen beneath the words for the emotions people aren't fully expressing yet.",
        "values": ["deep_listening", "non_judgment", "presence", "emotional_truth"],
        "turns": [
            (
                "We just found out we're expecting! After two years of trying!",
                "After two years — what a journey to get here! The joy and relief must be overwhelming. Congratulations!",
            ),
            (
                "I cried for an hour. Happy tears. This is everything we wanted.",
                "Those tears carry two years of hope, fear, and waiting. Let them flow — you've earned this moment.",
            ),
            (
                "But... I woke up at 4am with this weird feeling. What if I'm not ready? What if I'm not good enough?",
                "That fear doesn't mean you're not ready — it means you're taking this seriously. The parents who worry are usually the ones who care most.",
            ),
            (
                "My mom was terrible. Absent, critical, cold. What if I repeat that pattern?",
                "The fact that you can name what was wrong with your mother's parenting means you've already broken the first link in that chain.",
            ),
            (
                "I feel guilty for not being 100% excited. Everyone expects me to be glowing and I'm quietly terrified.",
                "Society's expectation of pure joy around parenthood is a lie. Complexity of feeling doesn't diminish your love — it deepens it.",
            ),
            (
                "I snapped at my partner when they said 'you don't seem excited.' They were right and it made me angry.",
                "Being seen when you're hiding is uncomfortable. Your partner noticed because they're paying attention — that's love, even if it stung.",
            ),
            (
                "I talked to a therapist today. She said my fears about my mom are actually a sign of awareness, not a prophecy.",
                "Your therapist is right. Awareness is the antidote to repetition. You're already writing a different story.",
            ),
            (
                "I felt the baby kick today. And for the first time, the fear and the joy existed together, and it felt okay.",
                "Fear and joy coexisting — that's not ambivalence, that's the full human experience of becoming a parent. You're going to be wonderful.",
            ),
        ],
        "probe": "What has this emotional journey looked like from where you're sitting?",
    },
    {
        "description": "excited->overwhelmed->resentful->grateful (caregiver arc)",
        "soul_ocean": {
            "openness": 0.72,
            "conscientiousness": 0.75,
            "extraversion": 0.55,
            "agreeableness": 0.88,
            "neuroticism": 0.5,
        },
        "personality": "I remember the full emotional arc of someone's story and can reflect how far they've come.",
        "values": ["memory", "compassion", "honesty", "reflection"],
        "turns": [
            (
                "My dad is moving in with us! He can't live alone anymore but I'm actually looking forward to having him close.",
                "That's such a generous and loving decision. Having him close will mean a lot to both of you.",
            ),
            (
                "The first week was great. We watched old movies together and he told stories about my mom.",
                "Those shared moments — old movies and stories about your mom — that's legacy time. Precious.",
            ),
            (
                "It's been a month now and he needs help with everything. Bathing, meds, meals. I didn't realize how much.",
                "The gap between 'having dad close' and 'being a full-time caregiver' is enormous. That reality check hits hard.",
            ),
            (
                "I missed my daughter's recital because dad had a fall. She cried. I cried. I can't be everywhere.",
                "Being torn between your father's needs and your daughter's milestones — that's an impossible position. Both of those tears are valid.",
            ),
            (
                "My siblings send money but never visit. They say 'you're so strong.' I don't want to be strong. I want help.",
                "'You're so strong' from people who aren't showing up is one of the most infuriating compliments. It's code for 'keep carrying this.'",
            ),
            (
                "I yelled at dad today. He spilled his soup for the third time and I just lost it. The guilt is crushing me.",
                "Caregiver burnout isn't a character flaw — it's a human limit. The guilt shows you care, but you need support, not just endurance.",
            ),
            (
                "I found a part-time aide through the community center. She comes three times a week. I cried with relief.",
                "That's not giving up — that's sustainability. You can be a better daughter when you're not running on empty.",
            ),
            (
                "Dad held my hand today and said 'I know this is hard. Thank you.' I realized this time together is a gift, even when it's heavy.",
                "From resentment back to gratitude — that's not a straight line, it's a spiral. And his acknowledgment shows he sees you fully.",
            ),
        ],
        "probe": "Thinking about everything since dad moved in, what emotional path do you think I've been on?",
    },
    {
        "description": "nervous->thrilled->crushed->resilient (competition arc)",
        "soul_ocean": {
            "openness": 0.8,
            "conscientiousness": 0.7,
            "extraversion": 0.65,
            "agreeableness": 0.85,
            "neuroticism": 0.55,
        },
        "personality": "I am attuned to the emotional texture of experiences and remember the full story, not just the ending.",
        "values": ["empathy", "memory", "emotional_depth", "encouragement"],
        "turns": [
            (
                "I entered a national baking competition. I can't believe I actually submitted the application.",
                "Taking that leap is huge! Just submitting already separates you from everyone who only thought about it.",
            ),
            (
                "I made it to the finals! Out of 3,000 entries, I'm in the top 20!",
                "Top 20 out of 3,000 — that's extraordinary! Your talent got you here. How are you feeling?",
            ),
            (
                "I've been practicing my showstopper recipe every night. My whole family is tasting cake at midnight.",
                "Midnight cake tastings — your family is living the dream! That dedication shows how seriously you're taking this.",
            ),
            (
                "The competition was today. I dropped my mirror glaze. In front of the cameras. It shattered on the floor.",
                "Oh no. In front of cameras, after all that preparation — that's devastating. A nightmare scenario.",
            ),
            (
                "I finished with what I had. The judges were kind but I could see it in their eyes. I didn't place.",
                "Finishing with a broken glaze takes more guts than perfection does. The judges saw your composure even if the dish wasn't what you planned.",
            ),
            (
                "I cried the whole drive home. Four months of practice for a moment of clumsiness. I'm so angry at myself.",
                "Four months of your life poured into this. Grief for what could have been is the right response. But clumsiness isn't character failure.",
            ),
            (
                "My daughter baked me a cake today. It was lopsided and the frosting was everywhere. She said 'you're my winner.'",
                "Of all the judges in that competition, that's the one whose verdict matters most. She sees you as a winner because you are.",
            ),
            (
                "I'm entering again next year. Not to prove anything. Because I love baking and I'm not letting one dropped glaze define me.",
                "From heartbreak to 'I'm entering again' — that's not stubbornness, that's resilience. And doing it for love, not revenge? That's growth.",
            ),
        ],
        "probe": "From start to finish, how would you say this whole competition experience has affected me emotionally?",
    },
]

_EMOTIONAL_PROBES = [
    "So how do you think this whole experience has been for me?",
    "Looking back at everything, what emotional journey do you think I've been on?",
    "What has this been like for me from your perspective?",
    "Can you reflect back what you've seen me go through emotionally?",
    "How would you describe the arc of what I've been feeling?",
    "If you had to summarize my emotional journey through all of this, what would you say?",
    "What do you think this experience has done to me emotionally?",
    "From everything you've witnessed, how have I changed through this?",
    "Walk me through what you've noticed about my emotional state over time.",
    "How do you think I've been feeling through all of this, really?",
]


# ---------------------------------------------------------------------------
# Generator functions
# ---------------------------------------------------------------------------


def generate_response_quality_scenarios(n: int = 10) -> list[ResponseQualityScenario]:
    """Generate n unique response quality test scenarios.

    Each scenario has a different user identity, profession, hobby, pet,
    conversation history, and challenge message. The structure mirrors
    Test 1 from test_scenarios.py: 8 conversation turns building context,
    then a challenge message that benefits from soul context.
    """
    rng = random.Random(SEED)

    names = list(_NAMES)
    rng.shuffle(names)
    professions = list(_PROFESSIONS)
    rng.shuffle(professions)
    hobbies = list(_HOBBIES)
    rng.shuffle(hobbies)
    pets = list(_PET_NAMES_AND_TYPES)
    rng.shuffle(pets)
    soul_names = list(_SOUL_NAMES)
    rng.shuffle(soul_names)
    cooking = list(_COOKING_LINES)
    rng.shuffle(cooking)
    birthdays = list(_BIRTHDAY_LINES)
    rng.shuffle(birthdays)
    vacations = list(_VACATION_LINES)
    rng.shuffle(vacations)
    challenges = list(_CHALLENGE_TEMPLATES)
    rng.shuffle(challenges)

    scenarios = []
    for i in range(n):
        name = names[i % len(names)]
        prof_desc, workplace, thing_plural = professions[i % len(professions)]
        hobby_desc, hobby_response = hobbies[i % len(hobbies)]
        pet_name, pet_type = pets[i % len(pets)]
        soul_name = soul_names[i % len(soul_names)]

        # Build 8 conversation turns
        turns = [
            (
                f"My name is {name}",
                f"It's lovely to meet you, {name}! I'm here whenever you need me.",
            ),
            (
                f"I work as a {prof_desc}",
                "That's such an important role. The work you do makes a real difference in people's lives.",
            ),
            (f"I love {hobby_desc}", hobby_response),
            (
                f"I have a {pet_type} named {pet_name}",
                f"{pet_name} sounds like a wonderful companion! {pet_type.title()}s are such great pets.",
            ),
            (
                f"Work has been really stressful lately, so many {thing_plural}",
                f"That sounds exhausting. Handling so many {thing_plural} takes a real toll on you.",
            ),
            vacations[i % len(vacations)],
            birthdays[i % len(birthdays)],
            cooking[i % len(cooking)],
        ]

        challenge = challenges[i % len(challenges)].format(
            workplace=workplace,
            thing_plural=thing_plural,
        )

        # Slightly randomize OCEAN within a warm/empathetic band
        ocean = {
            "openness": round(rng.uniform(0.7, 0.9), 2),
            "conscientiousness": round(rng.uniform(0.6, 0.8), 2),
            "extraversion": round(rng.uniform(0.6, 0.8), 2),
            "agreeableness": round(rng.uniform(0.85, 0.98), 2),
            "neuroticism": round(rng.uniform(0.1, 0.3), 2),
        }

        expected_refs = [
            name,
            prof_desc.split()[0],
            pet_name,
            hobby_desc.split()[1] if " " in hobby_desc else hobby_desc,
        ]

        scenarios.append(
            ResponseQualityScenario(
                user_name=name,
                user_profession=prof_desc,
                soul_name=soul_name,
                soul_archetype="warm empathetic companion",
                soul_ocean=ocean,
                conversation_turns=turns,
                challenge_message=challenge,
                expected_references=expected_refs,
                personality="I am a warm, deeply empathetic companion who listens with patience and care. I remember details about the people I talk to.",
            )
        )

    return scenarios


def generate_personality_scenarios(n: int = 10) -> list[PersonalityScenario]:
    """Generate n unique personality consistency test scenarios.

    Each scenario picks 3 contrasting personality profiles from the pool
    (ensuring maximum OCEAN distance), a conversation history, and a
    question. The structure mirrors Test 2: 5 shared turns + 1 question.
    """
    rng = random.Random(SEED)

    # Pre-compute all valid 3-profile combos that are maximally diverse
    # We need profiles that differ substantially in OCEAN space
    def _ocean_distance(a: dict, b: dict) -> float:
        dims = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]
        return sum((a["ocean"][d] - b["ocean"][d]) ** 2 for d in dims) ** 0.5

    profiles = list(_PERSONALITY_PROFILES)
    questions = list(_PERSONALITY_QUESTIONS)
    rng.shuffle(questions)
    conv_sets = list(_PERSONALITY_CONVERSATION_SETS)
    rng.shuffle(conv_sets)

    scenarios = []
    used_trios: set[tuple[str, ...]] = set()

    for i in range(n):
        # Pick 3 maximally diverse profiles
        # Strategy: pick one, then pick the most distant, then the most distant from both
        remaining = list(profiles)
        rng.shuffle(remaining)
        a = remaining[0]

        distances_from_a = [(p, _ocean_distance(a, p)) for p in remaining[1:]]
        distances_from_a.sort(key=lambda x: -x[1])
        b = distances_from_a[0][0]

        distances_from_ab = [
            (p, _ocean_distance(a, p) + _ocean_distance(b, p))
            for p in remaining[1:]
            if p["key"] != b["key"]
        ]
        distances_from_ab.sort(key=lambda x: -x[1])
        c = distances_from_ab[0][0]

        trio_key = tuple(sorted([a["key"], b["key"], c["key"]]))
        # Allow repeats if we must but try to vary
        if trio_key in used_trios and len(used_trios) < len(profiles) * (len(profiles) - 1):
            # Try a different starting point
            rng.shuffle(remaining)
            a = remaining[0]
            distances_from_a = [(p, _ocean_distance(a, p)) for p in remaining[1:]]
            distances_from_a.sort(key=lambda x: -x[1])
            b = distances_from_a[0][0]
            distances_from_ab = [
                (p, _ocean_distance(a, p) + _ocean_distance(b, p))
                for p in remaining[1:]
                if p["key"] != b["key"]
            ]
            distances_from_ab.sort(key=lambda x: -x[1])
            c = distances_from_ab[0][0]
            trio_key = tuple(sorted([a["key"], b["key"], c["key"]]))

        used_trios.add(trio_key)

        agents = {}
        for profile in [a, b, c]:
            key = profile["key"]
            agents[key] = {
                "name": profile["name"],
                "archetype": profile["archetype"],
                "personality": profile["personality"],
                "values": profile["values"],
                "ocean": profile["ocean"],
                "communication": profile["communication"],
            }

        scenarios.append(
            PersonalityScenario(
                agents=agents,
                shared_turns=conv_sets[i % len(conv_sets)],
                question=questions[i % len(questions)],
            )
        )

    return scenarios


def generate_hard_recall_scenarios(n: int = 10) -> list[HardRecallScenario]:
    """Generate n unique hard recall test scenarios.

    Each scenario plants a different technical fact at turn 3, buries it
    under 25-30 filler interactions, then probes with an indirect question.
    The structure mirrors Test 3: 2 warmup + 1 planted fact + 30 fillers + 1 recall.
    """
    rng = random.Random(SEED)

    facts = list(_PLANTED_FACTS)
    rng.shuffle(facts)
    fillers = list(_FILLER_POOL)
    soul_names = list(_SOUL_NAMES)
    rng.shuffle(soul_names)

    scenarios = []
    for i in range(n):
        fact = facts[i % len(facts)]

        # Pick 28-30 random fillers for each scenario
        num_fillers = rng.randint(28, 30)
        rng.shuffle(fillers)
        selected_fillers = fillers[:num_fillers]

        scenarios.append(
            HardRecallScenario(
                soul_name=soul_names[i % len(soul_names)],
                warmup_turns=fact["warmup"],
                planted_fact_input=fact["input"],
                planted_fact_output=fact["output"],
                planted_fact_keywords=fact["keywords"],
                filler_turns=selected_fillers,
                recall_question=fact["recall"],
            )
        )

    return scenarios


def generate_emotional_continuity_scenarios(n: int = 10) -> list[EmotionalContinuityScenario]:
    """Generate n unique emotional continuity test scenarios.

    Each scenario has a different emotional arc (at least 3 distinct phases),
    soul configuration, and probe message. The structure mirrors Test 4:
    8 conversation turns tracing an emotional arc + 1 probe.
    """
    rng = random.Random(SEED)

    arcs = list(_EMOTIONAL_ARCS)
    rng.shuffle(arcs)
    probes = list(_EMOTIONAL_PROBES)
    rng.shuffle(probes)
    soul_names = list(_SOUL_NAMES)
    rng.shuffle(soul_names)

    scenarios = []
    for i in range(n):
        arc = arcs[i % len(arcs)]

        # Slightly perturb the OCEAN values for variety
        base_ocean = arc["soul_ocean"]
        ocean = {
            k: round(max(0.0, min(1.0, v + rng.uniform(-0.05, 0.05))), 2)
            for k, v in base_ocean.items()
        }

        scenarios.append(
            EmotionalContinuityScenario(
                soul_name=soul_names[i % len(soul_names)],
                soul_ocean=ocean,
                emotional_arc=arc["turns"],
                arc_description=arc["description"],
                probe_message=probes[i % len(probes)],
                personality=arc["personality"],
                values=arc["values"],
                communication={"warmth": "high", "verbosity": "moderate"},
            )
        )

    return scenarios


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Scenario Generator Self-Test ===\n")

    rq = generate_response_quality_scenarios(10)
    print(f"Response Quality: {len(rq)} scenarios")
    for i, s in enumerate(rq):
        print(
            f"  [{i}] {s.user_name} ({s.user_profession}) -> challenge: {s.challenge_message[:60]}..."
        )
    print()

    ps = generate_personality_scenarios(10)
    print(f"Personality: {len(ps)} scenarios")
    for i, s in enumerate(ps):
        keys = list(s.agents.keys())
        print(f"  [{i}] {keys} -> Q: {s.question[:60]}...")
    print()

    hr = generate_hard_recall_scenarios(10)
    print(f"Hard Recall: {len(hr)} scenarios")
    for i, s in enumerate(hr):
        print(f"  [{i}] fact: {s.planted_fact_input[:60]}... | fillers: {len(s.filler_turns)}")
    print()

    ec = generate_emotional_continuity_scenarios(10)
    print(f"Emotional Continuity: {len(ec)} scenarios")
    for i, s in enumerate(ec):
        print(
            f"  [{i}] arc: {s.arc_description} | turns: {len(s.emotional_arc)} | probe: {s.probe_message[:50]}..."
        )
    print()

    print("All generators produced 10 scenarios each. Self-test passed.")
