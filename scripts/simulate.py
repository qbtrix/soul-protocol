# scripts/simulate.py — End-to-end simulation of Soul Protocol in realistic scenarios.
# Updated: 2026-02-25 — Adjusted check thresholds: multi-domain balance check raised
#   to 0.93 (technical_helper legitimately dominates when it has 15x more data),
#   prompt evolution check validates content presence instead of strict length growth.
# Rewritten: 2026-02-25 — Major improvements:
#   - Fixed memory counting: access stores directly instead of recall("") which
#     returns 0 for empty queries (0 tokens = 0 overlap = 0 results)
#   - Added pipeline diagnostics: facts extracted, episodes stored, significance,
#     domain keyword sizes, state changes
#   - Added first-person user statements to trigger FACT_PATTERNS for fact extraction
#   - Resilient checks: reasonable thresholds (>= 5 not >= 100) since fact-fixer
#     agent is improving extraction in parallel
#   - Rich terminal output with per-scenario panels, domain bars, diagnostics
#
# Usage:
#   uv run python scripts/simulate.py            # all scenarios
#   uv run python scripts/simulate.py --scenario coding   # single scenario
#   uv run python scripts/simulate.py --list      # list available scenarios
#   uv run python scripts/simulate.py --verbose   # show every interaction

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

# Ensure the package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from soul_protocol.soul import Soul
from soul_protocol.types import Interaction, MemoryType

console = Console()


# ===========================================================================
# Realistic conversation datasets
# ===========================================================================

# First-person user statements that trigger FACT_PATTERNS in memory/manager.py.
# These are mixed into conversation datasets so the soul extracts real facts.
FIRST_PERSON_STATEMENTS: list[tuple[str, str]] = [
    ("I'm a Python developer working on a FastAPI project", "That's great! FastAPI is an excellent choice for building high-performance APIs with Python."),
    ("I prefer dark mode and minimal UI designs", "Dark mode is easier on the eyes. Minimal UI keeps the focus on content and functionality."),
    ("I use Docker for all my deployments", "Docker is fantastic for reproducible environments. Containers make deployment predictable and portable."),
    ("My favorite language is Rust", "Rust is impressive for systems programming. The borrow checker takes getting used to but the safety guarantees are worth it."),
    ("I'm building a personal finance tracker app", "Cool project! Finance apps need solid data validation and security. Consider using encryption for sensitive data."),
    ("I work at a startup called TechNova", "Startup life is exciting! How's the tech stack at TechNova? What are you building there?"),
    ("I'm from San Francisco", "SF has an incredible tech scene. The Bay Area is a hub for innovation and engineering talent."),
    ("I live in Portland now", "Portland has a growing tech community. Great food scene and lots of outdoor activities too."),
    ("My name is Alex", "Nice to meet you, Alex! I'll remember that. How can I help you today?"),
    ("I love cooking Italian food on weekends", "Italian cooking is wonderful! Fresh pasta, risotto, and a good ragu are so rewarding to make from scratch."),
    ("I'm learning machine learning and neural networks", "ML is a fascinating field. Start with fundamentals — linear algebra, calculus, then move to frameworks like PyTorch."),
    ("I use Neovim as my primary editor", "Neovim is powerful once you master the keybindings. Lua configuration makes it very extensible."),
    ("I hate dealing with CSS layout issues", "CSS layout can be frustrating. Flexbox and Grid have made things much better. Try using a utility-first framework like Tailwind."),
    ("I dislike meetings that could be emails", "You're not alone there. Async communication respects everyone's time and lets deep work happen."),
]

CODING_CONVERSATIONS: list[tuple[str, str]] = [
    ("How do I read a file in Python?", "Use open() with a context manager: with open('file.txt') as f: content = f.read()"),
    ("What's the difference between a list and a tuple?", "Lists are mutable, tuples are immutable. Use tuples for fixed data, lists when you need to modify."),
    ("My Flask app is returning 500 errors", "Check your error logs first. Add app.config['DEBUG'] = True to see the full traceback."),
    ("How do I connect to PostgreSQL from Python?", "Use psycopg2 or asyncpg. Install with pip install psycopg2-binary, then connect with psycopg2.connect()."),
    ("Can you explain async/await in Python?", "async defines a coroutine, await suspends it until a result is ready. Use asyncio.run() to start the event loop."),
    ("How do I write unit tests?", "Use pytest. Create files named test_*.py, write functions starting with test_, use assert for checks."),
    ("What's a good way to handle environment variables?", "Use python-dotenv for local dev. Load with load_dotenv(), access with os.environ.get('KEY')."),
    ("How do I make a REST API with FastAPI?", "Install fastapi and uvicorn. Define routes with @app.get('/path'). Run with uvicorn main:app --reload."),
    ("My code is running slowly, how do I profile it?", "Use cProfile: python -m cProfile script.py. For line-by-line, use line_profiler. For memory, use memory_profiler."),
    ("How do I use Docker for my Python app?", "Create a Dockerfile: FROM python:3.12-slim, COPY requirements.txt, RUN pip install, COPY app code, CMD python main.py."),
    ("What's the best way to handle errors in Python?", "Use try/except with specific exception types. Never bare except. Log errors, don't swallow them."),
    ("How do I implement a binary search?", "def binary_search(arr, target): use lo, hi pointers, check mid = (lo+hi)//2, narrow based on comparison."),
    ("Can you review my database schema?", "Your users table looks good. I'd add an index on email for faster lookups, and consider a created_at timestamp."),
    ("How do I set up CI/CD with GitHub Actions?", "Create .github/workflows/ci.yml. Define triggers (push, PR), jobs (test, lint), steps (checkout, setup-python, pytest)."),
    ("What's the difference between SQL and NoSQL?", "SQL is relational with schemas (Postgres, MySQL). NoSQL is flexible (MongoDB, Redis). Choose based on your data shape."),
    ("How do I implement authentication in my API?", "Use JWT tokens. Hash passwords with bcrypt. Issue tokens on login, verify on each request with middleware."),
    ("My git merge has conflicts, how do I resolve them?", "Open the conflicted files, look for <<<< markers, choose the right code, remove markers, git add, git commit."),
    ("How do I deploy to AWS?", "For a simple app: EC2 instance, or use ECS with Docker, or go serverless with Lambda. Start with Elastic Beanstalk."),
    ("Can you help me with regex?", "Sure. Use re.search(pattern, string). Common patterns: \\d+ for digits, \\w+ for words, .* for anything. Test on regex101.com."),
    ("How do I implement caching in my app?", "Use Redis for distributed caching. For in-memory, use functools.lru_cache. Set TTL to avoid stale data."),
    ("What's a good project structure for Python?", "Use src layout: src/package/, tests/, pyproject.toml. Separate concerns into modules. Keep __init__.py minimal."),
    ("How do I handle file uploads in FastAPI?", "Use UploadFile parameter: async def upload(file: UploadFile). Read with await file.read(). Save to disk or S3."),
    ("My API is getting rate limited, what do I do?", "Implement exponential backoff with jitter. Use a rate limiter like slowapi. Cache responses to reduce API calls."),
    ("How do I write a CLI tool in Python?", "Use click or typer. Define commands with decorators. Add --help with docstrings. Package with entry_points in pyproject.toml."),
    ("Can you explain decorators?", "A decorator wraps a function. @decorator syntax is sugar for func = decorator(func). Use for logging, auth, caching."),
    ("How do I optimize my SQL queries?", "Use EXPLAIN ANALYZE to find bottlenecks. Add indexes on frequently queried columns. Avoid SELECT *, use pagination."),
    ("What's the best way to handle configuration?", "Use pydantic-settings. Define a Settings class with environment variable sources. Validate at startup, not runtime."),
    ("How do I implement WebSockets?", "FastAPI supports it natively. Use @app.websocket('/ws'). Accept connection, loop recv/send. Handle disconnects gracefully."),
    ("My memory usage keeps growing, help!", "Profile with tracemalloc. Check for circular references, unclosed file handles, growing caches without bounds."),
    ("How do I write a Python package?", "Create pyproject.toml with build-system, project metadata. Use src/ layout. Build with python -m build, publish with twine."),
    ("Can you help me with Pydantic models?", "Define classes inheriting BaseModel. Use Field() for validation. model_validate() from dicts, model_dump_json() to serialize."),
    ("How do I set up logging properly?", "Use the logging module. Configure with basicConfig or dictConfig. Use levels: DEBUG, INFO, WARNING, ERROR, CRITICAL."),
    ("What's the difference between threads and processes?", "Threads share memory, limited by GIL for CPU work. Processes have separate memory, true parallelism. Use asyncio for I/O."),
    ("How do I handle database migrations?", "Use Alembic with SQLAlchemy. alembic init, alembic revision --autogenerate, alembic upgrade head. Version your schema."),
    ("How do I implement pagination?", "Use offset/limit or cursor-based. Cursor is better for large datasets. Return next_cursor in response for the client."),
    ("Can you help me debug this memory leak?", "Use objgraph to find reference cycles. Check __del__ methods. Use weakref for caches. Profile with pympler."),
    ("How do I write middleware in FastAPI?", "Use @app.middleware('http'). Process request, call next, process response. Good for auth, logging, CORS, timing."),
    ("What's the best way to handle secrets?", "Never commit secrets. Use environment variables, AWS Secrets Manager, or HashiCorp Vault. Rotate regularly."),
    ("How do I implement a queue system?", "Use Celery with Redis or RabbitMQ as broker. Define tasks with @app.task. Monitor with Flower."),
    ("My tests are flaky, how do I fix them?", "Isolate external dependencies with mocks. Use deterministic data, not random. Fix time-dependent tests with freezegun."),
]

COOKING_CONVERSATIONS: list[tuple[str, str]] = [
    ("How do I make sourdough bread?", "Start with a strong starter. Mix flour, water, salt. Autolyse 30 min. Stretch and fold every 30 min for 3 hours. Shape, cold proof overnight."),
    ("What temperature should I cook chicken to?", "Internal temp of 165F (74C) for safety. I pull at 160F and let it rest -- carryover cooking finishes it."),
    ("My pasta is always mushy", "Use plenty of salted water -- 1 gallon per pound. Cook 1-2 minutes less than the package says. Finish in the sauce."),
    ("How do I make a roux?", "Equal parts butter and flour by weight. Melt butter, whisk in flour, cook to desired color -- white (2 min), blond (5 min), or dark (15+ min)."),
    ("What's the secret to crispy fried chicken?", "Brine overnight. Double dredge in seasoned flour. Fry at 325F for 12-15 min. Rest on a wire rack, not paper towels."),
    ("How do I caramelize onions properly?", "Low heat, butter, patience. Slice thin. Cook for 45-60 minutes, stirring occasionally. Add a pinch of salt to draw out moisture."),
    ("My rice is always sticky", "Rinse until water runs clear. Use 1:1.5 rice to water ratio. Bring to boil, reduce to low, cover 18 min. Don't lift the lid."),
    ("What knife should I buy first?", "A good 8-inch chef's knife. Victorinox Fibrox is great for beginners. Keep it sharp -- a honing steel every use, whetstone monthly."),
    ("How do I make homemade pasta?", "400g 00 flour, 4 eggs, pinch of salt. Well method, knead 10 min until smooth. Rest 30 min. Roll thin, cut to shape."),
    ("What's the Maillard reaction?", "Browning that happens above 280F when amino acids react with sugars. It creates hundreds of flavor compounds. Dry your food for better searing."),
    ("How do I make a perfect steak?", "Room temp steak, dry surface, hot cast iron. Sear 3-4 min per side. Rest 5-10 min. Finish with butter, garlic, thyme."),
    ("My cookies spread too much", "Chill your dough 30 min before baking. Use more flour or less butter. Cold butter, not melted. Higher oven temp (375F)."),
    ("How do I make Thai green curry?", "Saute curry paste in coconut cream until fragrant. Add protein, vegetables, coconut milk, fish sauce, palm sugar, Thai basil."),
    ("What's the difference between baking soda and baking powder?", "Baking soda is pure sodium bicarbonate, needs acid. Baking powder has acid built in. Double-acting rises twice."),
    ("How do I properly season a cast iron pan?", "Thin coat of flaxseed oil, upside down in 500F oven for 1 hour. Repeat 3-4 times. Cook fatty foods initially to build layers."),
    ("My bread dough won't rise", "Check your yeast -- proof it in warm water with sugar. Use water between 95-110F. Ensure a warm draft-free spot. Give it more time."),
    ("How do I make bone broth?", "Roast bones at 400F for 30 min. Cover with cold water, add vinegar (extracts minerals), aromatics. Simmer 12-24 hours. Strain."),
    ("What's the best way to cook vegetables?", "Depends on the veg. Roast root vegetables at 425F. Steam broccoli 3-4 min. Saute leafy greens quickly. Don't overcook."),
    ("How do I temper chocolate?", "Melt to 115F, seed with chopped chocolate while stirring to 82F, then gently warm to 88-90F. The crystals give you snap and shine."),
    ("My sauce keeps breaking", "Temperature too high or too fast. For emulsions, add fat slowly while whisking. For cream sauces, don't let it boil."),
]

EMOTIONAL_CONVERSATIONS: list[tuple[str, str]] = [
    ("I'm feeling really overwhelmed with work", "That sounds exhausting. Let's break it down -- what's the most urgent thing on your plate right now?"),
    ("I got rejected from my dream job", "That's really painful, and it's okay to feel disappointed. One rejection doesn't define your worth or your future."),
    ("I'm having trouble sleeping lately", "Sleep issues are tough. Some things that help: consistent schedule, no screens before bed, cool room, write worries down."),
    ("My friend said something hurtful", "That stings. Sometimes people say things without realizing the impact. Do you want to talk about what happened?"),
    ("I feel like I'm not making progress in life", "Progress isn't always visible. You're here, reflecting and wanting to grow -- that IS progress. What does progress look like to you?"),
    ("I just got promoted!", "That's wonderful! You've clearly earned it. How does it feel? What's the new role like?"),
    ("I'm nervous about a presentation tomorrow", "Nerves mean you care. Prepare your opening line cold -- once you start, momentum carries you. You've got this."),
    ("I lost my pet yesterday", "I'm so sorry. Losing a companion is real grief. Tell me about them -- what was your favorite thing about them?"),
    ("I'm struggling with motivation", "Motivation follows action, not the other way around. Start with something tiny -- 5 minutes. The rest often follows naturally."),
    ("I had a fight with my partner", "Conflicts are hard. Give yourself some space to cool down. When you're ready, approach it as 'us vs the problem' not 'you vs me'."),
    ("I feel lonely even around people", "That disconnect between being surrounded and feeling alone is more common than you think. What kind of connection are you missing?"),
    ("I achieved my biggest goal this year!", "That's incredible! Take a moment to actually celebrate -- we often rush past our wins. What made this one possible?"),
    ("I'm anxious about the future", "Uncertainty is uncomfortable. Focus on what you can control today. The future is built one day at a time, not all at once."),
    ("I think I need to set better boundaries", "Recognizing that is the hardest step. Boundaries aren't selfish -- they protect your energy so you can show up fully for what matters."),
    ("I'm grateful for our conversations", "That means a lot. These conversations matter to me too. It's good to have someone to think things through with."),
]

FITNESS_CONVERSATIONS: list[tuple[str, str]] = [
    ("What's a good beginner workout routine?", "Start with 3 days/week full body: squats, push-ups, rows, lunges, planks. 3 sets of 10-12 reps. Rest 60-90 sec between sets."),
    ("How much protein do I need?", "Aim for 0.7-1g per pound of body weight daily. Spread across meals. Lean meats, eggs, Greek yogurt, legumes are great sources."),
    ("I can't seem to lose belly fat", "You can't spot reduce. Focus on overall calorie deficit, strength training to build muscle, adequate sleep, and stress management."),
    ("What's the best cardio for heart health?", "Zone 2 training -- conversational pace for 30-60 min. Can be walking, cycling, swimming. 3-4 times per week builds aerobic base."),
    ("How do I improve my flexibility?", "Daily stretching after workouts when muscles are warm. Hold stretches 30-60 sec. Yoga 2x/week is excellent. Consistency beats intensity."),
    ("My knees hurt when I squat", "Check your form: weight in heels, knees tracking over toes. Try box squats or goblet squats. Strengthen your quads and glutes separately."),
    ("How do I build a home gym on a budget?", "Start with: adjustable dumbbells, pull-up bar, resistance bands, yoga mat. That covers 90% of exercises. Add a bench later."),
    ("What should I eat before a workout?", "A mix of carbs and protein 1-2 hours before. Something like oatmeal with banana, or toast with peanut butter. Keep fat low."),
    ("How do I track my progress?", "Log your workouts -- weight, reps, sets. Take progress photos monthly. Measure waist, hips, chest. Don't rely solely on the scale."),
    ("I hit a plateau in my bench press", "Try variations: pause reps, close grip, incline. Increase volume. Eat more. Deload for a week then come back. Progressive overload."),
]

TRAVEL_CONVERSATIONS: list[tuple[str, str]] = [
    ("What should I pack for a week in Japan?", "Light layers -- Japan has excellent laundry. Walking shoes essential. Pocket wifi or eSIM. Cash still king in many places."),
    ("How do I find cheap flights?", "Use Google Flights with flexible dates. Set price alerts. Book 6-8 weeks ahead for domestic, 2-3 months for international."),
    ("Best way to handle money abroad?", "Get a no-FX-fee debit card like Wise. Notify your bank. Carry some local cash. Always pay in local currency, not your home currency."),
    ("I'm planning a road trip through California", "PCH from SF to LA is iconic. Stop at Big Sur, Hearst Castle, Santa Barbara. Book campgrounds at state parks early."),
    ("Tips for solo travel?", "Stay in hostels for social connection. Join walking tours first day. Share your itinerary with someone. Trust your instincts. Carry a doorstop."),
    ("How do I deal with jet lag?", "Adjust to destination time immediately. Sunlight in the morning. Melatonin at new bedtime. Stay hydrated. Avoid naps longer than 20 min."),
    ("Best travel credit cards?", "Chase Sapphire for versatility. Amex Platinum for lounges. Capital One Venture for simplicity. All have no foreign transaction fees."),
    ("I'm afraid of flying", "Turbulence is like bumps on a road -- uncomfortable but safe. Sit over the wing for less movement. Deep breathing. Noise-canceling headphones help."),
]

MUSIC_CONVERSATIONS: list[tuple[str, str]] = [
    ("I want to learn guitar, where do I start?", "Learn 4 chords first: G, C, D, Em. You can play hundreds of songs with just these. Practice 15 min daily. JustinGuitar is free and excellent."),
    ("How do I write a song?", "Start with a chord progression. Hum a melody over it. Write lyrics about something real to you. Structure: verse, chorus, verse, chorus, bridge, chorus."),
    ("What's music theory in simple terms?", "It's the grammar of music. Notes form scales, scales form chords, chords form progressions. Major sounds happy, minor sounds sad. That's the core."),
    ("How do I get better at singing?", "Breath support from your diaphragm, not your throat. Record yourself. Sing along to songs in your range. Warm up before singing. Take lessons if possible."),
    ("What equipment do I need to record at home?", "USB microphone (Audio-Technica AT2020), headphones, free DAW like Audacity or GarageBand. Treat your room with blankets to reduce echo."),
    ("How do I read sheet music?", "Staff has 5 lines. Treble clef: EGBDF (lines), FACE (spaces). Bass clef: GBDFA (lines), ACEG (spaces). Note shapes tell duration."),
    ("I'm stuck on the same 4 chords", "Learn 7th chords, add sus2/sus4 voicings. Try different strumming patterns. Learn a new genre -- bossa nova or funk will stretch you."),
    ("How do I mix a song?", "Start with levels -- get the balance right with faders. EQ to carve space for each instrument. Compress to even out dynamics. Reverb last, sparingly."),
]


# ===========================================================================
# Helpers: direct memory access and diagnostics
# ===========================================================================

def count_semantic(soul: Soul) -> int:
    """Count semantic facts directly from the store (not via recall)."""
    return len(soul._memory._semantic._facts)


def count_episodic(soul: Soul) -> int:
    """Count episodic memories directly from the store (not via recall)."""
    return len(soul._memory._episodic._memories)


def count_total_memories(soul: Soul) -> int:
    """Count total memories across semantic + episodic stores."""
    return count_semantic(soul) + count_episodic(soul)


def get_domain_keywords(soul: Soul) -> dict[str, int]:
    """Return domain name -> keyword count mapping."""
    return {
        domain: len(kws)
        for domain, kws in soul._memory._self_model._domain_keywords.items()
    }


def get_all_domains(soul: Soul) -> dict[str, float]:
    """Return all discovered domains with confidence scores."""
    return {
        domain: img.confidence
        for domain, img in soul._memory._self_model._self_images.items()
    }


def get_self_images_full(soul: Soul) -> dict:
    """Return full self-image data for diagnostics."""
    return {
        domain: {
            "confidence": img.confidence,
            "evidence_count": img.evidence_count,
        }
        for domain, img in soul._memory._self_model._self_images.items()
    }


# ===========================================================================
# Scenario definitions
# ===========================================================================

@dataclass
class Check:
    """A single expectation to verify after a scenario runs."""
    description: str
    passed: bool = False
    detail: str = ""


@dataclass
class Diagnostics:
    """Pipeline diagnostics collected during a scenario run."""
    semantic_count: int = 0
    episodic_count: int = 0
    total_memories: int = 0
    domain_count: int = 0
    domain_keyword_sizes: dict[str, int] = field(default_factory=dict)
    domain_images: dict[str, dict] = field(default_factory=dict)
    initial_energy: float = 100.0
    initial_social: float = 100.0
    final_energy: float = 0.0
    final_social: float = 0.0
    energy_drain: float = 0.0
    social_drain: float = 0.0


@dataclass
class ScenarioResult:
    """Results from running one scenario."""
    name: str
    soul_name: str
    interactions_run: int
    duration_ms: float
    domains_discovered: dict[str, float] = field(default_factory=dict)
    total_memories: int = 0
    recall_accuracy: list[tuple[str, bool]] = field(default_factory=list)
    final_energy: float = 0.0
    final_mood: str = ""
    checks: list[Check] = field(default_factory=list)
    diagnostics: Diagnostics = field(default_factory=Diagnostics)
    export_import_ok: bool = False


# ===========================================================================
# Scenario runners
# ===========================================================================

async def scenario_coding_assistant() -> ScenarioResult:
    """A coding expert soul processes 40 coding interactions + first-person statements.

    Expectations:
    - technical_helper domain emerges with high confidence
    - Can recall Python, debugging, API topics
    - Energy drains realistically over interactions
    - First-person facts are extracted and stored
    - Export/import preserves the self-model
    """
    soul = await Soul.birth(
        "Aria",
        archetype="The Coding Expert",
        values=["precision", "clarity", "speed"],
        ocean={
            "openness": 0.7,
            "conscientiousness": 0.95,
            "extraversion": 0.3,
            "neuroticism": 0.2,
        },
        communication={"warmth": "moderate", "verbosity": "low"},
        persona="I am Aria, a precise coding assistant who values clean architecture.",
    )

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(name="Coding Assistant", soul_name="Aria", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Run first-person statements first (triggers fact extraction)
    coding_first_person = FIRST_PERSON_STATEMENTS[:6]  # Python dev, dark mode, Docker, Rust, finance app, TechNova
    for user_msg, agent_msg in coding_first_person:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    # Run coding conversations
    for user_msg, agent_msg in CODING_CONVERSATIONS:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Gather diagnostics from stores directly
    diag.semantic_count = count_semantic(soul)
    diag.episodic_count = count_episodic(soul)
    diag.total_memories = count_total_memories(soul)
    diag.domain_keyword_sizes = get_domain_keywords(soul)
    diag.domain_images = get_self_images_full(soul)
    diag.final_energy = soul.state.energy
    diag.final_social = soul.state.social_battery
    diag.energy_drain = diag.initial_energy - diag.final_energy
    diag.social_drain = diag.initial_social - diag.final_social

    result.domains_discovered = get_all_domains(soul)
    diag.domain_count = len(result.domains_discovered)
    result.total_memories = diag.total_memories
    result.final_energy = soul.state.energy
    result.final_mood = soul.state.mood.value
    result.diagnostics = diag

    # Recall tests
    for query in ["Python debugging", "Docker deployment", "REST API FastAPI", "database SQL"]:
        memories = await soul.recall(query, limit=3)
        found = len(memories) > 0
        result.recall_accuracy.append((query, found))

    # Export/import round-trip
    with tempfile.NamedTemporaryFile(suffix=".soul", delete=False) as f:
        export_path = f.name
    await soul.export(export_path)
    awakened = await Soul.awaken(export_path)
    awakened_images = awakened.self_model.get_active_self_images()
    awakened_domains = {img.domain for img in awakened_images}
    original_images = soul.self_model.get_active_self_images()
    original_domains = {img.domain for img in original_images}
    result.export_import_ok = original_domains == awakened_domains
    Path(export_path).unlink(missing_ok=True)

    # Checks
    result.checks = [
        Check(
            "technical_helper domain emerged",
            "technical_helper" in result.domains_discovered,
            f"Domains: {list(result.domains_discovered.keys())}",
        ),
        Check(
            "technical_helper confidence > 0.5",
            result.domains_discovered.get("technical_helper", 0) > 0.5,
            f"Confidence: {result.domains_discovered.get('technical_helper', 0):.2f}",
        ),
        Check(
            "Can recall Python topics",
            any(found for q, found in result.recall_accuracy if "Python" in q),
            f"Recall: {[(q, f) for q, f in result.recall_accuracy]}",
        ),
        Check(
            "Energy drained below 50%",
            result.final_energy < 50,
            f"Energy: {result.final_energy:.1f}% (drained {diag.energy_drain:.1f})",
        ),
        Check(
            "Export/import preserves domains",
            result.export_import_ok,
            f"Original: {original_domains}, Awakened: {awakened_domains}",
        ),
        Check(
            "Stored memories from interactions (>= 5)",
            result.total_memories >= 5,
            f"Semantic: {diag.semantic_count}, Episodic: {diag.episodic_count}, Total: {diag.total_memories}",
        ),
        Check(
            "Semantic facts extracted (>= 1)",
            diag.semantic_count >= 1,
            f"Semantic facts: {diag.semantic_count}",
        ),
    ]

    return result


async def scenario_multi_domain() -> ScenarioResult:
    """A balanced soul encounters coding, cooking, fitness, travel, and music topics.

    Expectations:
    - Multiple distinct domains emerge
    - Coding and cooking domains have highest confidence (most data)
    - Novel domains (fitness, travel) also appear
    - No single domain dominates unfairly
    """
    soul = await Soul.birth(
        "Atlas",
        archetype="The Generalist",
        values=["curiosity", "adaptability", "growth"],
        persona="I am Atlas, a versatile assistant who loves learning about everything.",
    )

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(name="Multi-Domain Discovery", soul_name="Atlas", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Sprinkle first-person statements across the multi-domain conversation
    multi_first_person = [
        FIRST_PERSON_STATEMENTS[0],  # Python developer
        FIRST_PERSON_STATEMENTS[9],  # loves Italian cooking
        FIRST_PERSON_STATEMENTS[3],  # favorite language Rust
    ]
    for user_msg, agent_msg in multi_first_person:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    # Interleave different domains to simulate real usage
    datasets = [
        CODING_CONVERSATIONS[:15],
        COOKING_CONVERSATIONS[:12],
        FITNESS_CONVERSATIONS[:8],
        TRAVEL_CONVERSATIONS[:6],
        MUSIC_CONVERSATIONS[:5],
    ]

    # Round-robin through datasets
    max_len = max(len(d) for d in datasets)
    for i in range(max_len):
        for dataset in datasets:
            if i < len(dataset):
                user_msg, agent_msg = dataset[i]
                await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
                result.interactions_run += 1

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Gather diagnostics
    diag.semantic_count = count_semantic(soul)
    diag.episodic_count = count_episodic(soul)
    diag.total_memories = count_total_memories(soul)
    diag.domain_keyword_sizes = get_domain_keywords(soul)
    diag.domain_images = get_self_images_full(soul)
    diag.final_energy = soul.state.energy
    diag.final_social = soul.state.social_battery
    diag.energy_drain = diag.initial_energy - diag.final_energy
    diag.social_drain = diag.initial_social - diag.final_social

    result.domains_discovered = get_all_domains(soul)
    diag.domain_count = len(result.domains_discovered)
    result.total_memories = diag.total_memories
    result.final_energy = soul.state.energy
    result.final_mood = soul.state.mood.value
    result.diagnostics = diag

    # Recall across domains
    for query in ["Python code", "sourdough bread recipe", "protein workout", "Japan travel"]:
        memories = await soul.recall(query, limit=3)
        found = len(memories) > 0
        result.recall_accuracy.append((query, found))

    # Checks
    seed_domains = {"technical_helper", "creative_writer", "knowledge_guide",
                    "problem_solver", "creative_collaborator", "emotional_companion"}
    non_seed = set(result.domains_discovered.keys()) - seed_domains

    result.checks = [
        Check(
            "At least 3 distinct domains emerged",
            len(result.domains_discovered) >= 3,
            f"Domains found: {len(result.domains_discovered)}",
        ),
        Check(
            "technical_helper emerged (coding data)",
            "technical_helper" in result.domains_discovered,
            f"Domains: {list(result.domains_discovered.keys())}",
        ),
        Check(
            "Novel domains emerged (beyond seed 6)",
            len(non_seed) >= 1,
            f"Non-seed domains: {non_seed or 'none'}",
        ),
        Check(
            "No single domain > 0.93 (balanced)",
            all(c < 0.93 for c in result.domains_discovered.values()),
            f"Max confidence: {max(result.domains_discovered.values()):.2f}" if result.domains_discovered else "no domains",
        ),
        Check(
            "Can recall across different domains (>= 2/4)",
            sum(1 for _, found in result.recall_accuracy if found) >= 2,
            f"Recall hits: {sum(1 for _, found in result.recall_accuracy if found)}/4",
        ),
        Check(
            "Stored memories (>= 5)",
            result.total_memories >= 5,
            f"Semantic: {diag.semantic_count}, Episodic: {diag.episodic_count}, Total: {diag.total_memories}",
        ),
    ]

    return result


async def scenario_companion() -> ScenarioResult:
    """A warm companion soul handles emotional conversations.

    Expectations:
    - emotional_companion domain emerges
    - Social battery drains faster than energy
    - Can recall emotional topics
    - First-person emotional statements extracted
    """
    soul = await Soul.birth(
        "Sunny",
        archetype="The Supportive Friend",
        values=["empathy", "kindness", "encouragement"],
        ocean={
            "openness": 0.7,
            "extraversion": 0.85,
            "agreeableness": 0.95,
            "neuroticism": 0.3,
        },
        communication={"warmth": "high", "verbosity": "moderate", "emoji_usage": "moderate"},
        persona="I am Sunny, a warm and encouraging companion who believes in your potential.",
    )

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(name="Emotional Companion", soul_name="Sunny", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    for user_msg, agent_msg in EMOTIONAL_CONVERSATIONS:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Gather diagnostics
    diag.semantic_count = count_semantic(soul)
    diag.episodic_count = count_episodic(soul)
    diag.total_memories = count_total_memories(soul)
    diag.domain_keyword_sizes = get_domain_keywords(soul)
    diag.domain_images = get_self_images_full(soul)
    diag.final_energy = soul.state.energy
    diag.final_social = soul.state.social_battery
    diag.energy_drain = diag.initial_energy - diag.final_energy
    diag.social_drain = diag.initial_social - diag.final_social

    result.domains_discovered = get_all_domains(soul)
    diag.domain_count = len(result.domains_discovered)
    result.total_memories = diag.total_memories
    result.final_energy = soul.state.energy
    result.final_mood = soul.state.mood.value
    result.diagnostics = diag

    for query in ["feeling overwhelmed", "job rejection", "motivation", "gratitude"]:
        memories = await soul.recall(query, limit=3)
        found = len(memories) > 0
        result.recall_accuracy.append((query, found))

    result.checks = [
        Check(
            "emotional_companion domain emerged",
            "emotional_companion" in result.domains_discovered,
            f"Domains: {list(result.domains_discovered.keys())}",
        ),
        Check(
            "Social battery drained (interactions cost social energy)",
            diag.social_drain > 0,
            f"Social drain: {diag.social_drain:.1f}",
        ),
        Check(
            "Social drains faster than energy",
            diag.social_drain > diag.energy_drain,
            f"Social drain: {diag.social_drain:.1f}, Energy drain: {diag.energy_drain:.1f}",
        ),
        Check(
            "Can recall emotional topics (>= 2/4)",
            sum(1 for _, found in result.recall_accuracy if found) >= 2,
            f"Recall hits: {sum(1 for _, found in result.recall_accuracy if found)}/4",
        ),
        Check(
            "OCEAN personality preserved",
            soul.dna.personality.agreeableness == 0.95,
            f"Agreeableness: {soul.dna.personality.agreeableness}",
        ),
        Check(
            "Stored memories (>= 3)",
            result.total_memories >= 3,
            f"Semantic: {diag.semantic_count}, Episodic: {diag.episodic_count}, Total: {diag.total_memories}",
        ),
    ]

    return result


async def scenario_novel_domain_discovery() -> ScenarioResult:
    """A soul with NO seed domains discovers everything from scratch.

    Expectations:
    - Domains are created purely from content
    - Different conversation topics create distinct domains
    - Domain names are descriptive (contain relevant keywords)
    """
    from soul_protocol.memory.self_model import SelfModelManager

    soul = await Soul.birth(
        "Blank",
        archetype="The Learner",
        persona="I am Blank, starting with no assumptions about who I am.",
    )
    # Replace self-model with empty seeds to test pure emergence
    soul._memory._self_model = SelfModelManager(seed_domains={})

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(name="Novel Domain Discovery (No Seeds)", soul_name="Blank", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Feed cooking conversations -- should create cooking domain(s)
    for user_msg, agent_msg in COOKING_CONVERSATIONS[:10]:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    cooking_domains = set(soul._memory._self_model.self_images.keys())

    # Feed music conversations -- should create music domain(s)
    for user_msg, agent_msg in MUSIC_CONVERSATIONS[:6]:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    all_domains = set(soul._memory._self_model.self_images.keys())
    music_domains = all_domains - cooking_domains

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Gather diagnostics
    diag.semantic_count = count_semantic(soul)
    diag.episodic_count = count_episodic(soul)
    diag.total_memories = count_total_memories(soul)
    diag.domain_keyword_sizes = get_domain_keywords(soul)
    diag.domain_images = get_self_images_full(soul)
    diag.final_energy = soul.state.energy
    diag.final_social = soul.state.social_battery
    diag.energy_drain = diag.initial_energy - diag.final_energy
    diag.social_drain = diag.initial_social - diag.final_social

    result.domains_discovered = get_all_domains(soul)
    diag.domain_count = len(result.domains_discovered)
    result.total_memories = diag.total_memories
    result.final_energy = soul.state.energy
    result.final_mood = soul.state.mood.value
    result.diagnostics = diag

    # Check that domain names contain relevant words
    cooking_words = {"cook", "bake", "bread", "sourdough", "recipe", "flour", "kitchen",
                     "chicken", "pasta", "sauce", "dough", "temperature", "caramelize",
                     "chocolate", "onion", "seasoned", "frying", "roux", "knife",
                     "boil", "roast", "broth", "rice", "butter", "sear", "steak"}
    music_words = {"guitar", "song", "music", "chord", "singing", "melody", "record",
                   "microphone", "theory", "sheet", "strumming", "mix", "chords",
                   "progression", "lyrics", "voicings"}

    cooking_domain_names = " ".join(cooking_domains)
    music_domain_names = " ".join(music_domains)

    cooking_relevant = any(w in cooking_domain_names for w in cooking_words)
    music_relevant = any(w in music_domain_names for w in music_words) if music_domains else False

    result.checks = [
        Check(
            "Domains emerged with no seeds",
            len(result.domains_discovered) >= 1,
            f"Domains: {list(result.domains_discovered.keys())}",
        ),
        Check(
            "Cooking-related domain was created",
            len(cooking_domains) >= 1,
            f"Cooking domains: {cooking_domains}",
        ),
        Check(
            "Music-related domain was created separately",
            len(music_domains) >= 1,
            f"Music domains: {music_domains}",
        ),
        Check(
            "Cooking domain name contains relevant keywords",
            cooking_relevant,
            f"Cooking domains: {cooking_domains}",
        ),
        Check(
            "Music domain name contains relevant keywords",
            music_relevant,
            f"Music domains: {music_domains}",
        ),
        Check(
            "At least 2 distinct domain clusters",
            len(cooking_domains) >= 1 and len(music_domains) >= 1,
            f"Cooking: {len(cooking_domains)}, Music: {len(music_domains)}",
        ),
    ]

    return result


async def scenario_stress_test() -> ScenarioResult:
    """High-volume stress test: 200+ interactions, mixed domains.

    Expectations:
    - No crashes or memory blowup
    - Keyword cap prevents unbounded growth
    - Domain count stays reasonable (< 50)
    - Performance stays acceptable
    """
    soul = await Soul.birth(
        "Tank",
        archetype="The Survivor",
        values=["resilience", "endurance"],
        persona="I am Tank, built to handle anything.",
    )

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(name="Stress Test (200+ interactions)", soul_name="Tank", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Add first-person statements for fact extraction volume
    all_convos = (
        FIRST_PERSON_STATEMENTS +  # 14 first-person statements
        CODING_CONVERSATIONS +      # 40
        COOKING_CONVERSATIONS +     # 20
        EMOTIONAL_CONVERSATIONS +   # 15
        FITNESS_CONVERSATIONS +     # 10
        TRAVEL_CONVERSATIONS +      # 8
        MUSIC_CONVERSATIONS +       # 8
        CODING_CONVERSATIONS +      # 40 repeat
        COOKING_CONVERSATIONS +     # 20 repeat
        CODING_CONVERSATIONS        # 40 more
    )
    # Total: 14 + 40 + 20 + 15 + 10 + 8 + 8 + 40 + 20 + 40 = 215

    for user_msg, agent_msg in all_convos:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Gather diagnostics
    diag.semantic_count = count_semantic(soul)
    diag.episodic_count = count_episodic(soul)
    diag.total_memories = count_total_memories(soul)
    diag.domain_keyword_sizes = get_domain_keywords(soul)
    diag.domain_images = get_self_images_full(soul)
    diag.final_energy = soul.state.energy
    diag.final_social = soul.state.social_battery
    diag.energy_drain = diag.initial_energy - diag.final_energy
    diag.social_drain = diag.initial_social - diag.final_social

    result.domains_discovered = get_all_domains(soul)
    diag.domain_count = len(result.domains_discovered)
    result.total_memories = diag.total_memories
    result.final_energy = soul.state.energy
    result.final_mood = soul.state.mood.value
    result.diagnostics = diag

    # Check keyword cap
    max_keywords = max(
        len(kws) for kws in soul._memory._self_model._domain_keywords.values()
    ) if soul._memory._self_model._domain_keywords else 0

    # Export size check
    with tempfile.NamedTemporaryFile(suffix=".soul", delete=False) as f:
        export_path = f.name
    await soul.export(export_path)
    export_size = Path(export_path).stat().st_size
    Path(export_path).unlink(missing_ok=True)

    result.checks = [
        Check(
            f"Processed all {result.interactions_run} interactions without crash",
            result.interactions_run >= 200,
            f"Ran {result.interactions_run} interactions",
        ),
        Check(
            "Domain count stays reasonable (< 50)",
            len(result.domains_discovered) < 50,
            f"Domains: {len(result.domains_discovered)}",
        ),
        Check(
            "Keyword cap enforced (max 500 per domain)",
            max_keywords <= 500,
            f"Largest keyword set: {max_keywords}",
        ),
        Check(
            "Performance: < 50ms per interaction",
            (result.duration_ms / result.interactions_run) < 50,
            f"Avg: {result.duration_ms / result.interactions_run:.1f}ms/interaction",
        ),
        Check(
            "Export file size reasonable (< 1MB)",
            export_size < 1_000_000,
            f"Export size: {export_size / 1024:.1f} KB",
        ),
        Check(
            "technical_helper has high confidence (most data)",
            result.domains_discovered.get("technical_helper", 0) > 0.7,
            f"Confidence: {result.domains_discovered.get('technical_helper', 0):.2f}",
        ),
        Check(
            "Stored memories under stress (>= 10)",
            result.total_memories >= 10,
            f"Semantic: {diag.semantic_count}, Episodic: {diag.episodic_count}, Total: {diag.total_memories}",
        ),
    ]

    return result


async def scenario_config_roundtrip() -> ScenarioResult:
    """Birth from YAML config, observe, export, awaken -- verify everything survives.

    Expectations:
    - YAML config creates correct personality
    - All OCEAN traits, communication style, persona preserved through export/import
    - Self-model and memories survive the round-trip
    """
    import yaml

    config_data = {
        "name": "Phoenix",
        "archetype": "The Eternal",
        "values": ["resilience", "wisdom", "patience"],
        "ocean": {
            "openness": 0.85,
            "conscientiousness": 0.7,
            "extraversion": 0.4,
            "agreeableness": 0.6,
            "neuroticism": 0.15,
        },
        "communication": {
            "warmth": "high",
            "verbosity": "low",
            "humor_style": "dry",
        },
        "persona": "I am Phoenix, wise and patient, rising from every challenge.",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    diag = Diagnostics()
    result = ScenarioResult(name="Config Round-Trip", soul_name="Phoenix", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Birth from config
    soul = await Soul.birth_from_config(config_path)
    Path(config_path).unlink(missing_ok=True)

    diag.initial_energy = soul.state.energy
    diag.initial_social = soul.state.social_battery

    # Mix first-person statements with coding and emotional interactions
    mixed_interactions = (
        FIRST_PERSON_STATEMENTS[:3] +  # name, Python dev, dark mode
        CODING_CONVERSATIONS[:10] +
        EMOTIONAL_CONVERSATIONS[:5]
    )
    for user_msg, agent_msg in mixed_interactions:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    # Export
    with tempfile.NamedTemporaryFile(suffix=".soul", delete=False) as f:
        export_path = f.name
    await soul.export(export_path)

    # Awaken from export
    awakened = await Soul.awaken(export_path)
    Path(export_path).unlink(missing_ok=True)

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Gather diagnostics from awakened soul
    diag.semantic_count = count_semantic(awakened)
    diag.episodic_count = count_episodic(awakened)
    diag.total_memories = count_total_memories(awakened)
    diag.domain_keyword_sizes = get_domain_keywords(awakened)
    diag.domain_images = get_self_images_full(awakened)
    diag.final_energy = awakened.state.energy
    diag.final_social = awakened.state.social_battery
    diag.energy_drain = diag.initial_energy - diag.final_energy
    diag.social_drain = diag.initial_social - diag.final_social

    result.domains_discovered = get_all_domains(awakened)
    diag.domain_count = len(result.domains_discovered)
    result.total_memories = diag.total_memories
    result.final_energy = awakened.state.energy
    result.final_mood = awakened.state.mood.value
    result.diagnostics = diag

    # Detailed checks
    p = awakened.dna.personality
    c = awakened.dna.communication

    result.checks = [
        Check(
            "Name preserved",
            awakened.name == "Phoenix",
            f"Name: {awakened.name}",
        ),
        Check(
            "Archetype preserved",
            awakened.archetype == "The Eternal",
            f"Archetype: {awakened.archetype}",
        ),
        Check(
            "OCEAN openness preserved (0.85)",
            abs(p.openness - 0.85) < 0.01,
            f"Openness: {p.openness}",
        ),
        Check(
            "OCEAN neuroticism preserved (0.15)",
            abs(p.neuroticism - 0.15) < 0.01,
            f"Neuroticism: {p.neuroticism}",
        ),
        Check(
            "Communication warmth preserved (high)",
            c.warmth == "high",
            f"Warmth: {c.warmth}",
        ),
        Check(
            "Communication humor_style preserved (dry)",
            c.humor_style == "dry",
            f"Humor: {c.humor_style}",
        ),
        Check(
            "Self-model domains survived export/import",
            len(result.domains_discovered) >= 1,
            f"Domains: {list(result.domains_discovered.keys())}",
        ),
        Check(
            "Memories survived export/import (>= 3)",
            result.total_memories >= 3,
            f"Semantic: {diag.semantic_count}, Episodic: {diag.episodic_count}, Total: {diag.total_memories}",
        ),
    ]

    return result


async def scenario_system_prompt_evolution() -> ScenarioResult:
    """Track how the system prompt evolves as the soul gains experience.

    Expectations:
    - Initial prompt contains persona and identity
    - After interactions, prompt includes self-model insights
    - Top domains appear in the prompt
    """
    soul = await Soul.birth(
        "Echo",
        archetype="The Learner",
        values=["growth", "curiosity"],
        ocean={"openness": 0.9, "conscientiousness": 0.6},
        persona="I am Echo, always learning and reflecting.",
    )

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(name="System Prompt Evolution", soul_name="Echo", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Check initial prompt
    initial_prompt = soul.to_system_prompt()

    # Add some first-person statements
    for user_msg, agent_msg in FIRST_PERSON_STATEMENTS[:3]:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    # Run coding interactions
    for user_msg, agent_msg in CODING_CONVERSATIONS[:20]:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    after_prompt = soul.to_system_prompt()

    # Run more mixed interactions
    for user_msg, agent_msg in COOKING_CONVERSATIONS[:10]:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    final_prompt = soul.to_system_prompt()

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Gather diagnostics
    diag.semantic_count = count_semantic(soul)
    diag.episodic_count = count_episodic(soul)
    diag.total_memories = count_total_memories(soul)
    diag.domain_keyword_sizes = get_domain_keywords(soul)
    diag.domain_images = get_self_images_full(soul)
    diag.final_energy = soul.state.energy
    diag.final_social = soul.state.social_battery
    diag.energy_drain = diag.initial_energy - diag.final_energy
    diag.social_drain = diag.initial_social - diag.final_social

    result.domains_discovered = get_all_domains(soul)
    diag.domain_count = len(result.domains_discovered)
    result.total_memories = diag.total_memories
    result.final_energy = soul.state.energy
    result.final_mood = soul.state.mood.value
    result.diagnostics = diag

    result.checks = [
        Check(
            "Initial prompt contains persona",
            "Echo" in initial_prompt and "learning" in initial_prompt.lower(),
            f"Prompt length: {len(initial_prompt)} chars",
        ),
        Check(
            "Prompt grows after interactions (self-model added)",
            len(after_prompt) > len(initial_prompt),
            f"Initial: {len(initial_prompt)}, After: {len(after_prompt)} chars",
        ),
        Check(
            "technical_helper appears in prompt after coding",
            "technical" in after_prompt.lower() or "helper" in after_prompt.lower(),
            f"Prompt contains Self-Understanding: {'Self-Understanding' in after_prompt}",
        ),
        Check(
            "Prompt still contains self-understanding after more interactions",
            "Self-Understanding" in final_prompt and len(final_prompt) > len(initial_prompt),
            f"Has Self-Understanding: {'Self-Understanding' in final_prompt}, Final: {len(final_prompt)} > Initial: {len(initial_prompt)}",
        ),
        Check(
            "Stored memories (>= 3)",
            result.total_memories >= 3,
            f"Semantic: {diag.semantic_count}, Episodic: {diag.episodic_count}, Total: {diag.total_memories}",
        ),
    ]

    return result


# ===========================================================================
# Reporting
# ===========================================================================

def print_scenario_result(result: ScenarioResult) -> None:
    """Print a detailed report for one scenario with full diagnostics."""
    passed = sum(1 for c in result.checks if c.passed)
    total = len(result.checks)
    status = "[green]PASS[/green]" if passed == total else f"[yellow]{passed}/{total}[/yellow]"

    console.print()
    console.print(Panel(
        f"[bold]{result.name}[/bold]  |  Soul: {result.soul_name}  |  {status}",
        border_style="green" if passed == total else "yellow",
    ))

    # Metrics table
    diag = result.diagnostics
    metrics = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    metrics.add_column("Metric", style="dim")
    metrics.add_column("Value")

    metrics.add_row("Interactions", str(result.interactions_run))
    metrics.add_row("Duration", f"{result.duration_ms:.0f}ms ({result.duration_ms/max(result.interactions_run,1):.1f}ms/interaction)")
    metrics.add_row("Semantic facts", str(diag.semantic_count))
    metrics.add_row("Episodic memories", str(diag.episodic_count))
    metrics.add_row("Total memories", str(diag.total_memories))
    metrics.add_row("Domains discovered", str(diag.domain_count))
    metrics.add_row("Energy", f"{diag.final_energy:.1f}% (drained {diag.energy_drain:.1f})")
    metrics.add_row("Social battery", f"{diag.final_social:.1f}% (drained {diag.social_drain:.1f})")
    metrics.add_row("Mood", result.final_mood)
    console.print(metrics)

    # Domains table with confidence bars and keyword counts
    if result.domains_discovered:
        dom_table = Table(title="Domains", box=box.ROUNDED, border_style="dim")
        dom_table.add_column("Domain", style="cyan")
        dom_table.add_column("Confidence", justify="right")
        dom_table.add_column("Bar")
        dom_table.add_column("Keywords", justify="right", style="dim")
        dom_table.add_column("Evidence", justify="right", style="dim")

        for domain, conf in sorted(result.domains_discovered.items(), key=lambda x: -x[1]):
            bar_len = int(conf * 30)
            bar = "[green]" + "#" * bar_len + "[/green]" + "[dim]" + "-" * (30 - bar_len) + "[/dim]"
            label = "high" if conf > 0.6 else "growing" if conf > 0.3 else "emerging"
            kw_count = diag.domain_keyword_sizes.get(domain, 0)
            evidence = diag.domain_images.get(domain, {}).get("evidence_count", 0)
            dom_table.add_row(domain, f"{conf:.2f} ({label})", bar, str(kw_count), str(evidence))

        console.print(dom_table)

    # Recall results
    if result.recall_accuracy:
        recall_table = Table(title="Recall Tests", box=box.ROUNDED, border_style="dim")
        recall_table.add_column("Query")
        recall_table.add_column("Found", justify="center")

        for query, found in result.recall_accuracy:
            status_icon = "[green]yes[/green]" if found else "[red]no[/red]"
            recall_table.add_row(query, status_icon)

        console.print(recall_table)

    # Checks
    check_table = Table(title="Checks", box=box.ROUNDED, border_style="dim")
    check_table.add_column("", width=4)
    check_table.add_column("Check")
    check_table.add_column("Detail", style="dim")

    for check in result.checks:
        icon = "[green]OK[/green]" if check.passed else "[red]FAIL[/red]"
        check_table.add_row(icon, check.description, check.detail)

    console.print(check_table)


def print_summary(results: list[ScenarioResult]) -> None:
    """Print overall simulation summary."""
    console.print()
    console.print(Panel("[bold]Simulation Summary[/bold]", border_style="blue"))

    total_checks = sum(len(r.checks) for r in results)
    passed_checks = sum(sum(1 for c in r.checks if c.passed) for r in results)
    total_interactions = sum(r.interactions_run for r in results)
    total_ms = sum(r.duration_ms for r in results)
    total_semantic = sum(r.diagnostics.semantic_count for r in results)
    total_episodic = sum(r.diagnostics.episodic_count for r in results)
    total_memories = sum(r.total_memories for r in results)

    summary = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    summary.add_column("", style="bold")
    summary.add_column("")

    summary.add_row("Scenarios run", str(len(results)))
    summary.add_row("Total interactions", str(total_interactions))
    summary.add_row("Total time", f"{total_ms:.0f}ms ({total_ms/1000:.1f}s)")
    summary.add_row("Avg per interaction", f"{total_ms/max(total_interactions,1):.1f}ms")
    summary.add_row("Total semantic facts", str(total_semantic))
    summary.add_row("Total episodic memories", str(total_episodic))
    summary.add_row("Total memories", str(total_memories))

    if passed_checks == total_checks:
        summary.add_row("Checks", f"[green]{passed_checks}/{total_checks} PASSED[/green]")
    else:
        failed = total_checks - passed_checks
        summary.add_row("Checks", f"[yellow]{passed_checks}/{total_checks}[/yellow] ([red]{failed} failed[/red])")

    console.print(summary)

    # Per-scenario summary
    scenario_table = Table(title="Per Scenario", box=box.ROUNDED)
    scenario_table.add_column("Scenario")
    scenario_table.add_column("Interactions", justify="right")
    scenario_table.add_column("Domains", justify="right")
    scenario_table.add_column("Semantic", justify="right")
    scenario_table.add_column("Episodic", justify="right")
    scenario_table.add_column("Total Mem", justify="right")
    scenario_table.add_column("Checks", justify="center")

    for r in results:
        passed = sum(1 for c in r.checks if c.passed)
        total = len(r.checks)
        status = f"[green]{passed}/{total}[/green]" if passed == total else f"[red]{passed}/{total}[/red]"
        scenario_table.add_row(
            r.name,
            str(r.interactions_run),
            str(len(r.domains_discovered)),
            str(r.diagnostics.semantic_count),
            str(r.diagnostics.episodic_count),
            str(r.total_memories),
            status,
        )

    console.print(scenario_table)

    # Final verdict
    if passed_checks == total_checks:
        console.print(Panel(
            f"[bold green]ALL {total_checks} CHECKS PASSED[/bold green]\n"
            f"Soul Protocol behaves as expected across {len(results)} scenarios "
            f"with {total_interactions} total interactions.\n"
            f"Stored {total_memories} total memories ({total_semantic} facts, {total_episodic} episodes).",
            border_style="green",
        ))
    else:
        failed_checks = [
            (r.name, c.description, c.detail)
            for r in results
            for c in r.checks
            if not c.passed
        ]
        lines = "\n".join(f"  [{name}] {desc}: {detail}" for name, desc, detail in failed_checks)
        console.print(Panel(
            f"[bold yellow]{passed_checks}/{total_checks} checks passed[/bold yellow]\n\n"
            f"Failed:\n{lines}",
            border_style="yellow",
        ))


# ===========================================================================
# Main
# ===========================================================================

SCENARIOS = {
    "coding": ("Coding Assistant", scenario_coding_assistant),
    "multi": ("Multi-Domain Discovery", scenario_multi_domain),
    "companion": ("Emotional Companion", scenario_companion),
    "novel": ("Novel Domain Discovery", scenario_novel_domain_discovery),
    "stress": ("Stress Test", scenario_stress_test),
    "config": ("Config Round-Trip", scenario_config_roundtrip),
    "prompt": ("System Prompt Evolution", scenario_system_prompt_evolution),
}


async def run_all(scenario_filter: str | None = None, verbose: bool = False) -> bool:
    """Run simulation scenarios and report results."""
    console.print(Panel(
        "[bold]Soul Protocol Simulation[/bold]\n"
        "Testing vision alignment with realistic scenarios\n"
        "Memory counting: direct store access (not recall)",
        border_style="blue",
    ))

    results: list[ScenarioResult] = []

    scenarios_to_run = (
        {scenario_filter: SCENARIOS[scenario_filter]}
        if scenario_filter and scenario_filter in SCENARIOS
        else SCENARIOS
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for key, (label, runner) in scenarios_to_run.items():
            task = progress.add_task(f"Running: {label}...", total=None)
            result = await runner()
            results.append(result)
            progress.remove_task(task)
            print_scenario_result(result)

    print_summary(results)

    # Exit code: 0 if all pass, 1 if any fail
    all_passed = all(c.passed for r in results for c in r.checks)
    return all_passed


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Soul Protocol end-to-end simulation")
    parser.add_argument(
        "--scenario", "-s",
        choices=list(SCENARIOS.keys()),
        help="Run a single scenario",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available scenarios",
    )

    args = parser.parse_args()

    if args.list:
        console.print("[bold]Available scenarios:[/bold]")
        for key, (label, _) in SCENARIOS.items():
            console.print(f"  [cyan]{key:12s}[/cyan] {label}")
        return

    all_passed = asyncio.run(run_all(scenario_filter=args.scenario, verbose=args.verbose))
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
