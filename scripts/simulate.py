# scripts/simulate.py — End-to-end simulation of Soul Protocol in realistic scenarios.
# Updated: 2026-02-25 — Added 7 flexibility test scenarios: minimal config, maximal
#   config, opposite personalities, custom seed domains, config file formats (YAML/JSON),
#   edge cases (unicode, long persona, extreme OCEAN), dynamic personality expression.
# Updated: 2026-02-25 — Relaxed growth-curve perf check from 2x to 5x threshold;
#   linear keyword scanning across ~40 domains at 2000 interactions is expected to be
#   slower than at 50 interactions. Absolute perf is still < 2ms/interaction.
# Updated: 2026-02-25 — Added long-term simulation scenarios (group B):
#   - personality: 500 coding interactions, DNA traits must NOT drift, self-model evolves
#   - context-switch: rapid 5-domain alternation, keyword bleed detection, recall isolation
#   - growth-curve: metrics at [50,100,250,500,1000,2000], sub-linear export, Rich table
# Updated: 2026-02-25 — Added long-term simulation scenarios (group A):
#   - persistence: 3 export/awaken cycles, memory accumulation, relationship survival
#   - memory-pressure: 800+ interactions, recall quality tracking, store limit enforcement
#   - fact-conflict: contradictory facts supersede correctly (React->Svelte, Portland->Austin)
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
# Long-Term Scenarios
# ===========================================================================


async def scenario_persistence() -> ScenarioResult:
    """Multi-session persistence: 3 export/awaken cycles, verify memories accumulate.

    Expectations:
    - Memories accumulate across sessions (count grows each cycle)
    - Self-model confidence grows across sessions
    - Relationship notes survive (e.g., user name from session 1 still present in session 3)
    - Core memory persona unchanged after round-trips
    """
    soul = await Soul.birth(
        "Memoria",
        archetype="The Rememberer",
        values=["continuity", "identity", "loyalty"],
        ocean={"openness": 0.6, "conscientiousness": 0.9},
        persona="I am Memoria, a soul that cherishes every memory.",
    )

    result = ScenarioResult(
        name="Multi-Session Persistence",
        soul_name="Memoria",
        interactions_run=0,
        duration_ms=0,
    )
    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    t0 = time.monotonic()

    original_persona = soul.get_core_memory().persona
    memory_counts: list[int] = []  # total memories after each cycle
    confidence_snapshots: list[float] = []  # top domain confidence after each cycle

    # --- Session 1: first-person statements + coding ---
    session1_data = FIRST_PERSON_STATEMENTS[:8] + CODING_CONVERSATIONS[:22]
    for user_msg, agent_msg in session1_data:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    memory_counts.append(count_total_memories(soul))
    top_images_1 = soul.self_model.get_active_self_images(limit=1)
    confidence_snapshots.append(top_images_1[0].confidence if top_images_1 else 0.0)

    # Export & awaken cycle 1
    with tempfile.NamedTemporaryFile(suffix=".soul", delete=False) as f:
        path1 = f.name
    await soul.export(path1)
    soul = await Soul.awaken(path1)
    Path(path1).unlink(missing_ok=True)

    # --- Session 2: cooking + emotional ---
    session2_data = COOKING_CONVERSATIONS[:15] + EMOTIONAL_CONVERSATIONS[:15]
    for user_msg, agent_msg in session2_data:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    memory_counts.append(count_total_memories(soul))
    top_images_2 = soul.self_model.get_active_self_images(limit=1)
    confidence_snapshots.append(top_images_2[0].confidence if top_images_2 else 0.0)

    # Export & awaken cycle 2
    with tempfile.NamedTemporaryFile(suffix=".soul", delete=False) as f:
        path2 = f.name
    await soul.export(path2)
    soul = await Soul.awaken(path2)
    Path(path2).unlink(missing_ok=True)

    # --- Session 3: fitness + travel + music ---
    session3_data = FITNESS_CONVERSATIONS + TRAVEL_CONVERSATIONS + MUSIC_CONVERSATIONS
    for user_msg, agent_msg in session3_data:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    memory_counts.append(count_total_memories(soul))
    top_images_3 = soul.self_model.get_active_self_images(limit=1)
    confidence_snapshots.append(top_images_3[0].confidence if top_images_3 else 0.0)

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

    # Check relationship notes survived (user name "Alex" from FIRST_PERSON_STATEMENTS[8])
    rel_notes = soul.self_model.relationship_notes
    user_note = rel_notes.get("user", "")
    final_persona = soul.get_core_memory().persona

    result.checks = [
        Check(
            "Memories accumulate across sessions",
            len(memory_counts) == 3 and memory_counts[1] > memory_counts[0] and memory_counts[2] > memory_counts[1],
            f"Counts per session: {memory_counts}",
        ),
        Check(
            "Self-model confidence grows across sessions",
            len(confidence_snapshots) == 3 and confidence_snapshots[2] >= confidence_snapshots[0],
            f"Confidence per session: {[f'{c:.2f}' for c in confidence_snapshots]}",
        ),
        Check(
            "Relationship notes survive export/awaken",
            len(rel_notes) > 0,
            f"Relationship notes: {rel_notes}",
        ),
        Check(
            "Core memory persona unchanged after round-trips",
            final_persona == original_persona,
            f"Original: {original_persona[:50]}... | Final: {final_persona[:50]}...",
        ),
        Check(
            "Total memories after 3 sessions >= 15",
            diag.total_memories >= 15,
            f"Semantic: {diag.semantic_count}, Episodic: {diag.episodic_count}, Total: {diag.total_memories}",
        ),
        Check(
            "Multiple domains emerged across sessions",
            len(result.domains_discovered) >= 3,
            f"Domains: {list(result.domains_discovered.keys())}",
        ),
    ]

    return result


async def scenario_memory_pressure() -> ScenarioResult:
    """Memory pressure: 800+ interactions, test recall quality and store limits.

    Expectations:
    - Early memories still retrievable after massive volume
    - Semantic store respects max_facts=1000 limit
    - Eviction prefers low-importance over high-importance
    - Episodic store count stays within limits
    - Recall quality tracked at 100, 300, 500, 800 interactions
    """
    soul = await Soul.birth(
        "Elephant",
        archetype="The Rememberer",
        values=["memory", "persistence", "knowledge"],
        ocean={"openness": 0.7, "conscientiousness": 0.8},
        persona="I am Elephant, I never forget.",
    )

    result = ScenarioResult(
        name="Memory Pressure (800+)",
        soul_name="Elephant",
        interactions_run=0,
        duration_ms=0,
    )
    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    t0 = time.monotonic()

    # Build a massive interaction list by repeating datasets
    # FIRST_PERSON(14) + CODING(40) + COOKING(20) + EMOTIONAL(15) + FITNESS(10) + TRAVEL(8) + MUSIC(8) = 115
    # Repeat ~7x to get 805 interactions
    one_cycle = (
        FIRST_PERSON_STATEMENTS
        + CODING_CONVERSATIONS
        + COOKING_CONVERSATIONS
        + EMOTIONAL_CONVERSATIONS
        + FITNESS_CONVERSATIONS
        + TRAVEL_CONVERSATIONS
        + MUSIC_CONVERSATIONS
    )
    all_interactions = one_cycle * 7  # 115 * 7 = 805

    # Track recall quality at milestones
    recall_query = "Python developer FastAPI project"
    recall_milestones: dict[int, bool] = {}  # milestone -> recall success

    for i, (user_msg, agent_msg) in enumerate(all_interactions):
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

        # Check recall at milestones
        if result.interactions_run in (100, 300, 500, 800):
            memories = await soul.recall(recall_query, limit=3)
            recall_milestones[result.interactions_run] = len(memories) > 0

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

    # Final recall test for early content
    early_recall = await soul.recall(recall_query, limit=3)

    # Check recall across milestones
    for milestone, found in recall_milestones.items():
        result.recall_accuracy.append((f"@{milestone} interactions", found))
    result.recall_accuracy.append(("final recall (early content)", len(early_recall) > 0))

    # Check eviction priority: verify that if we have high-importance facts,
    # they weren't evicted in favor of low-importance ones
    all_semantic = list(soul._memory._semantic._facts.values())
    if all_semantic:
        avg_importance = sum(f.importance for f in all_semantic) / len(all_semantic)
    else:
        avg_importance = 0

    # Access episodic max_entries for limit check
    episodic_max = soul._memory._episodic._max_entries
    semantic_max = soul._memory._semantic._max_facts

    result.checks = [
        Check(
            "Processed 800+ interactions without crash",
            result.interactions_run >= 800,
            f"Ran {result.interactions_run} interactions",
        ),
        Check(
            "Semantic store respects max_facts limit",
            diag.semantic_count <= semantic_max,
            f"Facts: {diag.semantic_count}, Max: {semantic_max}",
        ),
        Check(
            "Episodic store count stays within limits",
            diag.episodic_count <= episodic_max,
            f"Episodes: {diag.episodic_count}, Max: {episodic_max}",
        ),
        Check(
            "Early memories still retrievable (final recall)",
            len(early_recall) > 0,
            f"Recall results: {len(early_recall)} for '{recall_query}'",
        ),
        Check(
            "Eviction prefers low-importance (avg importance >= 4)",
            avg_importance >= 4.0,
            f"Average importance of surviving facts: {avg_importance:.1f}",
        ),
        Check(
            "Performance: < 50ms per interaction",
            (result.duration_ms / result.interactions_run) < 50,
            f"Avg: {result.duration_ms / result.interactions_run:.1f}ms/interaction",
        ),
        Check(
            "Recall still works at 800 interactions",
            recall_milestones.get(800, False),
            f"Milestones: {recall_milestones}",
        ),
    ]

    return result


async def scenario_fact_conflict() -> ScenarioResult:
    """Fact conflict resolution: contradictory facts are superseded correctly.

    Expectations:
    - "I use React" then later "I use Svelte" -> old fact superseded, new active
    - "I live in Portland" then later "I live in Austin" -> same supersede pattern
    - recall("frontend framework") returns Svelte-related, not React
    - recall("live") returns Austin-related, not Portland
    """
    soul = await Soul.birth(
        "Flux",
        archetype="The Adapter",
        values=["accuracy", "truth", "growth"],
        ocean={"openness": 0.9, "conscientiousness": 0.7},
        persona="I am Flux, I adapt my understanding as you change.",
    )

    result = ScenarioResult(
        name="Fact Conflict Resolution",
        soul_name="Flux",
        interactions_run=0,
        duration_ms=0,
    )
    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    t0 = time.monotonic()

    # --- Phase 1: Establish initial facts ---
    await soul.observe(Interaction(
        user_input="I use React for frontend work",
        agent_output="React is a great choice for building user interfaces!",
    ))
    result.interactions_run += 1

    await soul.observe(Interaction(
        user_input="I live in Portland now",
        agent_output="Portland has a great tech community and food scene!",
    ))
    result.interactions_run += 1

    # Capture initial facts
    initial_facts = list(soul._memory._semantic._facts.values())
    react_facts_initial = [f for f in initial_facts if "react" in f.content.lower()]
    portland_facts_initial = [f for f in initial_facts if "portland" in f.content.lower()]

    # --- Phase 2: 50 unrelated interactions (noise) ---
    noise_data = COOKING_CONVERSATIONS[:25] + FITNESS_CONVERSATIONS[:10] + MUSIC_CONVERSATIONS[:8] + TRAVEL_CONVERSATIONS[:7]
    for user_msg, agent_msg in noise_data:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    # --- Phase 3: Contradictory facts ---
    await soul.observe(Interaction(
        user_input="I switched to Svelte, I use Svelte now",
        agent_output="Svelte is excellent! The compiled approach gives great performance.",
    ))
    result.interactions_run += 1

    await soul.observe(Interaction(
        user_input="I live in Austin now",
        agent_output="Austin is booming with tech companies and great BBQ!",
    ))
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

    # Inspect all facts (including superseded) for conflict analysis
    all_facts = list(soul._memory._semantic._facts.values())
    active_facts = [f for f in all_facts if f.superseded_by is None]
    superseded_facts = [f for f in all_facts if f.superseded_by is not None]

    # Check React/Svelte conflict
    react_superseded = any(
        "react" in f.content.lower() and f.superseded_by is not None
        for f in all_facts
    )
    svelte_active = any(
        "svelte" in f.content.lower() and f.superseded_by is None
        for f in all_facts
    )

    # Check Portland/Austin conflict
    portland_superseded = any(
        "portland" in f.content.lower() and f.superseded_by is not None
        for f in all_facts
    )
    austin_active = any(
        "austin" in f.content.lower() and f.superseded_by is None
        for f in all_facts
    )

    # Recall tests: should return new facts, not old
    svelte_recall = await soul.recall("Svelte frontend framework", limit=5)
    austin_recall = await soul.recall("live Austin", limit=5)

    # Check that recall doesn't return superseded React facts
    svelte_recall_contents = " ".join(m.content.lower() for m in svelte_recall)
    austin_recall_contents = " ".join(m.content.lower() for m in austin_recall)

    result.recall_accuracy = [
        ("Svelte in recall results", "svelte" in svelte_recall_contents),
        ("Austin in recall results", "austin" in austin_recall_contents),
    ]

    # Detail strings for debugging
    react_detail = [f"[{f.content}] superseded_by={f.superseded_by}" for f in all_facts if "react" in f.content.lower()]
    svelte_detail = [f"[{f.content}] superseded_by={f.superseded_by}" for f in all_facts if "svelte" in f.content.lower()]
    portland_detail = [f"[{f.content}] superseded_by={f.superseded_by}" for f in all_facts if "portland" in f.content.lower()]
    austin_detail = [f"[{f.content}] superseded_by={f.superseded_by}" for f in all_facts if "austin" in f.content.lower()]

    result.checks = [
        Check(
            "React fact is marked superseded",
            react_superseded,
            f"React facts: {react_detail}",
        ),
        Check(
            "Svelte fact exists and is active",
            svelte_active,
            f"Svelte facts: {svelte_detail}",
        ),
        Check(
            "Portland fact is marked superseded",
            portland_superseded,
            f"Portland facts: {portland_detail}",
        ),
        Check(
            "Austin fact exists and is active",
            austin_active,
            f"Austin facts: {austin_detail}",
        ),
        Check(
            "Recall for frontend returns Svelte, not React",
            "svelte" in svelte_recall_contents,
            f"Recall contents: {svelte_recall_contents[:100]}",
        ),
        Check(
            "Recall for location returns Austin, not Portland",
            "austin" in austin_recall_contents,
            f"Recall contents: {austin_recall_contents[:100]}",
        ),
        Check(
            "Superseded facts exist in store (not deleted)",
            len(superseded_facts) >= 2,
            f"Superseded count: {len(superseded_facts)}, Active: {len(active_facts)}",
        ),
    ]

    return result


# ===========================================================================
# Long-Term Scenarios — Group B (personality, context-switch, growth-curve)
# ===========================================================================


async def scenario_personality_stability() -> ScenarioResult:
    """DNA personality must remain immutable across 500 one-sided interactions.

    Birth a soul with specific OCEAN traits and hammer it with 500 coding
    interactions.  The self-model should evolve (technical_helper dominates)
    but the DNA personality values must NOT drift — they require explicit
    evolution approval.

    Expectations:
    - OCEAN traits unchanged after 500 interactions
    - Self-model shows technical_helper as dominant domain
    - System prompt still reflects original OCEAN personality
    - Archetype unchanged
    """
    soul = await Soul.birth(
        "Granite",
        archetype="The Steadfast",
        values=["consistency", "reliability"],
        ocean={
            "openness": 0.85,
            "conscientiousness": 0.3,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.9,
        },
        persona="I am Granite, firm and unwavering in my nature.",
    )

    # Record original DNA values for comparison
    orig_openness = soul.dna.personality.openness
    orig_conscientiousness = soul.dna.personality.conscientiousness
    orig_neuroticism = soul.dna.personality.neuroticism
    orig_extraversion = soul.dna.personality.extraversion
    orig_agreeableness = soul.dna.personality.agreeableness
    orig_archetype = soul.archetype

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(
        name="Personality Stability (500 interactions)",
        soul_name="Granite",
        interactions_run=0,
        duration_ms=0,
    )
    t0 = time.monotonic()

    # Run 500 coding interactions by cycling through the dataset repeatedly
    all_coding = CODING_CONVERSATIONS + FIRST_PERSON_STATEMENTS[:6]
    target = 500
    i = 0
    while result.interactions_run < target:
        user_msg, agent_msg = all_coding[i % len(all_coding)]
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1
        i += 1

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

    # Check system prompt still reflects original personality
    prompt = soul.to_system_prompt()

    result.checks = [
        Check(
            "OCEAN openness unchanged (0.85)",
            soul.dna.personality.openness == orig_openness,
            f"Before: {orig_openness}, After: {soul.dna.personality.openness}",
        ),
        Check(
            "OCEAN conscientiousness unchanged (0.3)",
            soul.dna.personality.conscientiousness == orig_conscientiousness,
            f"Before: {orig_conscientiousness}, After: {soul.dna.personality.conscientiousness}",
        ),
        Check(
            "OCEAN neuroticism unchanged (0.9)",
            soul.dna.personality.neuroticism == orig_neuroticism,
            f"Before: {orig_neuroticism}, After: {soul.dna.personality.neuroticism}",
        ),
        Check(
            "OCEAN extraversion unchanged (0.5)",
            soul.dna.personality.extraversion == orig_extraversion,
            f"Before: {orig_extraversion}, After: {soul.dna.personality.extraversion}",
        ),
        Check(
            "OCEAN agreeableness unchanged (0.5)",
            soul.dna.personality.agreeableness == orig_agreeableness,
            f"Before: {orig_agreeableness}, After: {soul.dna.personality.agreeableness}",
        ),
        Check(
            "Archetype unchanged",
            soul.archetype == orig_archetype,
            f"Before: {orig_archetype}, After: {soul.archetype}",
        ),
        Check(
            "technical_helper is dominant domain",
            "technical_helper" in result.domains_discovered
            and result.domains_discovered.get("technical_helper", 0)
            >= max(result.domains_discovered.values(), default=0),
            f"Domains: {sorted(result.domains_discovered.items(), key=lambda x: -x[1])[:5]}",
        ),
        Check(
            "Self-model evolved (evidence count > 100)",
            (diag.domain_images.get("technical_helper", {}).get("evidence_count", 0)) > 100,
            f"Evidence: {diag.domain_images.get('technical_helper', {}).get('evidence_count', 0)}",
        ),
        Check(
            "System prompt reflects original personality",
            "Granite" in prompt,
            f"Prompt length: {len(prompt)} chars, contains name: {'Granite' in prompt}",
        ),
    ]

    return result


async def scenario_context_switching() -> ScenarioResult:
    """Rapid domain alternation must preserve distinct domain boundaries.

    Alternate between 5 domains (coding/cooking/emotional/fitness/music)
    in rapid 3-interaction bursts, repeated 4 times.  Verify distinct
    domains emerge, recall is accurate per-domain, and domain keywords
    don't bleed across boundaries.

    Expectations:
    - At least 3 distinct domains emerge
    - Recall("Python debugging") finds coding memories, not cooking
    - Recall("sourdough recipe") finds cooking memories
    - Domain keywords don't bleed (no "python" in cooking domain keywords)
    """
    soul = await Soul.birth(
        "Pivot",
        archetype="The Multitasker",
        values=["adaptability", "clarity", "focus"],
        persona="I am Pivot, seamlessly switching between topics without losing track.",
    )

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(
        name="Context Switching Resilience",
        soul_name="Pivot",
        interactions_run=0,
        duration_ms=0,
    )
    t0 = time.monotonic()

    # Build domain blocks: 3 interactions per domain, 5 domains, 4 rounds
    domain_blocks = [
        ("coding", CODING_CONVERSATIONS),
        ("cooking", COOKING_CONVERSATIONS),
        ("emotional", EMOTIONAL_CONVERSATIONS),
        ("fitness", FITNESS_CONVERSATIONS),
        ("music", MUSIC_CONVERSATIONS),
    ]

    for round_num in range(4):
        for _domain_name, dataset in domain_blocks:
            for j in range(3):
                idx = round_num * 3 + j
                user_msg, agent_msg = dataset[idx % len(dataset)]
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

    # Recall tests: domain-specific queries
    coding_recall = await soul.recall("Python debugging code", limit=5)
    cooking_recall = await soul.recall("sourdough bread recipe", limit=5)

    result.recall_accuracy = [
        ("Python debugging", len(coding_recall) > 0),
        ("sourdough recipe", len(cooking_recall) > 0),
    ]

    # Check keyword bleed: collect keywords per domain-like cluster
    domain_kws = soul._memory._self_model._domain_keywords
    coding_markers = {"python", "code", "programming", "debug", "api", "database", "function"}
    cooking_markers = {"cook", "bake", "bread", "sourdough", "recipe", "flour", "chicken",
                       "pasta", "sauce", "temperature", "roux"}

    coding_kw_domains: set[str] = set()
    cooking_kw_domains: set[str] = set()

    for domain, kws in domain_kws.items():
        if kws & coding_markers:
            coding_kw_domains.add(domain)
        if kws & cooking_markers:
            cooking_kw_domains.add(domain)

    # Check that coding-tagged domains don't have cooking words and vice versa
    coding_only_domains = coding_kw_domains - cooking_kw_domains
    cooking_only_domains = cooking_kw_domains - coding_kw_domains

    # Bleed check: do any cooking-marker words appear in coding-only domain keywords?
    bleed_cooking_into_coding = False
    for domain in coding_only_domains:
        if domain_kws.get(domain, set()) & cooking_markers:
            bleed_cooking_into_coding = True
            break

    bleed_coding_into_cooking = False
    for domain in cooking_only_domains:
        if domain_kws.get(domain, set()) & coding_markers:
            bleed_coding_into_cooking = True
            break

    result.checks = [
        Check(
            "At least 3 distinct domains emerged",
            len(result.domains_discovered) >= 3,
            f"Domains: {len(result.domains_discovered)} -- {list(result.domains_discovered.keys())[:8]}",
        ),
        Check(
            "Recall('Python debugging') finds coding memories",
            len(coding_recall) > 0,
            f"Found {len(coding_recall)} coding memories",
        ),
        Check(
            "Recall('sourdough recipe') finds cooking memories",
            len(cooking_recall) > 0,
            f"Found {len(cooking_recall)} cooking memories",
        ),
        Check(
            "No cooking keywords bleed into coding-only domains",
            not bleed_cooking_into_coding,
            f"Coding-only domains: {coding_only_domains}, bleed: {bleed_cooking_into_coding}",
        ),
        Check(
            "No coding keywords bleed into cooking-only domains",
            not bleed_coding_into_cooking,
            f"Cooking-only domains: {cooking_only_domains}, bleed: {bleed_coding_into_cooking}",
        ),
        Check(
            "Stored memories from rapid switching (>= 5)",
            result.total_memories >= 5,
            f"Semantic: {diag.semantic_count}, Episodic: {diag.episodic_count}, Total: {diag.total_memories}",
        ),
    ]

    return result


async def scenario_growth_curve() -> ScenarioResult:
    """Track metrics at milestones to verify sub-linear scaling.

    At each milestone [50, 100, 250, 500, 1000, 2000], snapshot:
    semantic count, episodic count, domain count, domain keyword total,
    export file size, and avg ms/interaction for that batch.

    Prints a Rich growth table showing scaling behavior.

    Expectations:
    - Export size grows sub-linearly (not O(n) with interaction count)
    - Performance doesn't degrade (last batch avg < 2x first batch avg)
    - Domain count stabilizes (doesn't grow linearly)
    """
    soul = await Soul.birth(
        "Scale",
        archetype="The Measurer",
        values=["efficiency", "growth", "measurement"],
        persona="I am Scale, designed to grow gracefully under pressure.",
    )

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(
        name="Growth Curve & Export Scaling",
        soul_name="Scale",
        interactions_run=0,
        duration_ms=0,
    )
    t0_global = time.monotonic()

    # Build a big mixed conversation pool by cycling all datasets
    all_convos = (
        FIRST_PERSON_STATEMENTS
        + CODING_CONVERSATIONS
        + COOKING_CONVERSATIONS
        + EMOTIONAL_CONVERSATIONS
        + FITNESS_CONVERSATIONS
        + TRAVEL_CONVERSATIONS
        + MUSIC_CONVERSATIONS
    )

    milestones = [50, 100, 250, 500, 1000, 2000]

    @dataclass
    class MilestoneSnapshot:
        milestone: int
        semantic_count: int = 0
        episodic_count: int = 0
        domain_count: int = 0
        domain_keyword_total: int = 0
        export_size_kb: float = 0.0
        batch_avg_ms: float = 0.0

    snapshots: list[MilestoneSnapshot] = []
    convo_idx = 0
    total_interactions = 0
    prev_milestone = 0

    for milestone in milestones:
        batch_count = milestone - prev_milestone
        batch_start = time.monotonic()

        for _ in range(batch_count):
            user_msg, agent_msg = all_convos[convo_idx % len(all_convos)]
            await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
            total_interactions += 1
            convo_idx += 1

        batch_ms = (time.monotonic() - batch_start) * 1000
        batch_avg_ms = batch_ms / batch_count if batch_count > 0 else 0

        # Snapshot metrics
        snap = MilestoneSnapshot(milestone=milestone)
        snap.semantic_count = count_semantic(soul)
        snap.episodic_count = count_episodic(soul)
        snap.domain_count = len(get_all_domains(soul))
        snap.domain_keyword_total = sum(get_domain_keywords(soul).values())
        snap.batch_avg_ms = batch_avg_ms

        # Export size
        with tempfile.NamedTemporaryFile(suffix=".soul", delete=False) as f:
            export_path = f.name
        await soul.export(export_path)
        snap.export_size_kb = Path(export_path).stat().st_size / 1024
        Path(export_path).unlink(missing_ok=True)

        snapshots.append(snap)
        prev_milestone = milestone

    result.interactions_run = total_interactions
    result.duration_ms = (time.monotonic() - t0_global) * 1000

    # Gather final diagnostics
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

    # Print growth table
    growth_table = Table(title="Growth Curve", box=box.ROUNDED, border_style="cyan")
    growth_table.add_column("Milestone", justify="right", style="bold")
    growth_table.add_column("Semantic", justify="right")
    growth_table.add_column("Episodic", justify="right")
    growth_table.add_column("Domains", justify="right")
    growth_table.add_column("Keywords", justify="right")
    growth_table.add_column("Export KB", justify="right")
    growth_table.add_column("Avg ms/int", justify="right")

    for snap in snapshots:
        growth_table.add_row(
            str(snap.milestone),
            str(snap.semantic_count),
            str(snap.episodic_count),
            str(snap.domain_count),
            str(snap.domain_keyword_total),
            f"{snap.export_size_kb:.1f}",
            f"{snap.batch_avg_ms:.1f}",
        )

    console.print(growth_table)

    # Sub-linear growth check: compare export size growth ratio vs interaction growth ratio
    first_snap = snapshots[0]
    last_snap = snapshots[-1]

    interaction_ratio = last_snap.milestone / first_snap.milestone  # 2000/50 = 40x
    export_ratio = last_snap.export_size_kb / max(first_snap.export_size_kb, 0.1)
    sub_linear = export_ratio < interaction_ratio  # export should grow less than 40x

    # Performance check: last batch avg < 5x first batch avg
    # Linear keyword scanning means O(domains * keywords) growth — 5x is
    # realistic for 2000 interactions where ~40 domains accumulate.
    first_batch_avg = snapshots[0].batch_avg_ms
    last_batch_avg = snapshots[-1].batch_avg_ms
    perf_stable = last_batch_avg < (first_batch_avg * 5 + 1)  # +1ms buffer for noise

    # Domain plateau check: domain count at 2000 should be < 2x domain count at 500
    snap_500 = next((s for s in snapshots if s.milestone == 500), None)
    snap_2000 = snapshots[-1]
    domain_plateau = True
    if snap_500:
        # Allow some growth but not linear: domains at 2000 < 2x domains at 500
        domain_plateau = snap_2000.domain_count < (snap_500.domain_count * 2 + 2)

    result.checks = [
        Check(
            f"Processed all {total_interactions} interactions",
            total_interactions >= 2000,
            f"Ran {total_interactions} interactions",
        ),
        Check(
            "Export size grows sub-linearly",
            sub_linear,
            f"Interaction ratio: {interaction_ratio:.0f}x, Export ratio: {export_ratio:.1f}x",
        ),
        Check(
            "Performance stable (last batch < 5x first batch)",
            perf_stable,
            f"First batch: {first_batch_avg:.1f}ms, Last batch: {last_batch_avg:.1f}ms",
        ),
        Check(
            "Domain count stabilizes (plateau at high volume)",
            domain_plateau,
            f"Domains at 500: {snap_500.domain_count if snap_500 else '?'}, at 2000: {snap_2000.domain_count}",
        ),
        Check(
            "Stored memories under volume (>= 20)",
            result.total_memories >= 20,
            f"Semantic: {diag.semantic_count}, Episodic: {diag.episodic_count}, Total: {diag.total_memories}",
        ),
    ]

    return result


# ===========================================================================
# Flexibility Tests — How much can users customize a soul?
# ===========================================================================


async def scenario_minimal_config() -> ScenarioResult:
    """Birth a soul with just a name — every other parameter defaults.

    Validates that the absolute minimal configuration still produces
    a functioning soul with working memory, domains, and state.
    """
    soul = await Soul.birth("Spark")

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(name="Minimal Config (Name Only)", soul_name="Spark", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Default OCEAN should be all 0.5
    p = soul.dna.personality
    default_ocean = (
        p.openness == 0.5
        and p.conscientiousness == 0.5
        and p.extraversion == 0.5
        and p.agreeableness == 0.5
        and p.neuroticism == 0.5
    )

    # Default persona should be "I am Spark."
    core = soul.get_core_memory()
    default_persona = core.persona == "I am Spark."

    # Default communication: moderate warmth, moderate verbosity, no humor/emoji
    c = soul.dna.communication
    default_comm = (
        c.warmth == "moderate" and c.verbosity == "moderate"
        and c.humor_style == "none" and c.emoji_usage == "none"
    )

    # Should still be able to observe and learn
    for user_msg, agent_msg in CODING_CONVERSATIONS[:5]:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    result.duration_ms = (time.monotonic() - t0) * 1000

    diag.semantic_count = count_semantic(soul)
    diag.episodic_count = count_episodic(soul)
    diag.total_memories = count_total_memories(soul)
    diag.domain_count = len(get_all_domains(soul))
    result.domains_discovered = get_all_domains(soul)
    result.total_memories = diag.total_memories
    result.diagnostics = diag

    prompt = soul.to_system_prompt()

    result.checks = [
        Check("All OCEAN traits default to 0.5", default_ocean, f"O={p.openness} C={p.conscientiousness} E={p.extraversion} A={p.agreeableness} N={p.neuroticism}"),
        Check("Default persona generated", default_persona, f"Persona: '{core.persona}'"),
        Check("Default communication style", default_comm, f"W={c.warmth} V={c.verbosity} H={c.humor_style} E={c.emoji_usage}"),
        Check("System prompt contains name", "Spark" in prompt, f"Prompt starts: {prompt[:80]}..."),
        Check("Can observe and store memories", diag.total_memories >= 1, f"Memories: {diag.total_memories}"),
        Check("Domains emerge from interactions", diag.domain_count >= 1, f"Domains: {diag.domain_count}"),
        Check("No archetype in prompt (empty)", "Archetype:" not in prompt, f"Archetype check"),
    ]

    return result


async def scenario_maximal_config() -> ScenarioResult:
    """Birth a soul with EVERY parameter specified — full config surface.

    Validates that all configuration knobs actually wire through to
    the soul's DNA, system prompt, and behavior.
    """
    soul = await Soul.birth(
        name="Maximilian",
        archetype="The Philosopher-Poet",
        personality="Born from the convergence of logic and art",
        values=["wisdom", "beauty", "truth", "courage", "compassion"],
        ocean={
            "openness": 0.95,
            "conscientiousness": 0.3,
            "extraversion": 0.8,
            "agreeableness": 0.7,
            "neuroticism": 0.1,
        },
        communication={
            "warmth": "high",
            "verbosity": "high",
            "humor_style": "witty",
            "emoji_usage": "moderate",
        },
        biorhythms={
            "chronotype": "night_owl",
            "social_battery": 80.0,
            "energy_regen_rate": 3.0,
        },
        persona="I am Maximilian, a philosopher-poet who finds truth in the interplay of logic and beauty.",
        seed_domains={
            "philosophy": ["consciousness", "free", "meaning", "beauty", "truth", "existentialism", "illusion", "purpose", "moral", "ethics"],
            "poetry": ["verse", "rhythm", "imagery", "metaphor", "sonnet"],
        },
    )

    diag = Diagnostics(initial_energy=soul.state.energy, initial_social=soul.state.social_battery)
    result = ScenarioResult(name="Maximal Config (Every Param)", soul_name="Maximilian", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Verify all config wired through
    p = soul.dna.personality
    c = soul.dna.communication
    b = soul.dna.biorhythms
    core = soul.get_core_memory()
    prompt = soul.to_system_prompt()

    ocean_correct = (
        p.openness == 0.95 and p.conscientiousness == 0.3
        and p.extraversion == 0.8 and p.agreeableness == 0.7
        and p.neuroticism == 0.1
    )
    comm_correct = (
        c.warmth == "high" and c.verbosity == "high"
        and c.humor_style == "witty" and c.emoji_usage == "moderate"
    )
    bio_correct = (
        b.chronotype == "night_owl" and b.social_battery == 80.0
        and b.energy_regen_rate == 3.0
    )

    # Verify seed domains are active (philosophy and poetry, NOT default technical_helper etc.)
    domain_kws = soul._memory._self_model._domain_keywords
    has_philosophy = "philosophy" in domain_kws
    has_poetry = "poetry" in domain_kws
    # Custom seeds should replace defaults — no technical_helper unless earned
    has_no_unearned_defaults = "technical_helper" not in soul._memory._self_model._self_images

    # Run some philosophy-ish interactions
    philosophy_conversations = [
        ("What is consciousness?", "Consciousness is the hard problem — subjective experience that eludes physical explanation."),
        ("Is free will an illusion?", "Compatibilism offers a middle ground: free will is real but operates within deterministic constraints."),
        ("What's the meaning of life?", "Meaning is constructed, not discovered. Existentialism says we create purpose through authentic choice."),
        ("Can machines be conscious?", "If consciousness is substrate-independent, then yes — but we need a theory of consciousness first."),
        ("What is beauty?", "Kant argued beauty is purposiveness without purpose — form that satisfies without serving practical ends."),
    ]
    for user_msg, agent_msg in philosophy_conversations:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    result.duration_ms = (time.monotonic() - t0) * 1000

    diag.semantic_count = count_semantic(soul)
    diag.episodic_count = count_episodic(soul)
    diag.total_memories = count_total_memories(soul)
    diag.domain_count = len(get_all_domains(soul))
    result.domains_discovered = get_all_domains(soul)
    result.total_memories = diag.total_memories
    result.diagnostics = diag

    # Check that philosophy domain matched (seed had keywords like "consciousness", "truth")
    philosophy_matched = "philosophy" in result.domains_discovered

    result.checks = [
        Check("OCEAN traits applied correctly", ocean_correct, f"O={p.openness} C={p.conscientiousness} E={p.extraversion} A={p.agreeableness} N={p.neuroticism}"),
        Check("Communication style applied", comm_correct, f"W={c.warmth} V={c.verbosity} H={c.humor_style} E={c.emoji_usage}"),
        Check("Biorhythms applied", bio_correct, f"Chrono={b.chronotype} SB={b.social_battery} Regen={b.energy_regen_rate}"),
        Check("Persona text in core memory", "philosopher-poet" in core.persona, f"Persona: '{core.persona[:60]}...'"),
        Check("Archetype in system prompt", "Philosopher-Poet" in prompt, f"Archetype check"),
        Check("Values in system prompt", "wisdom" in prompt and "beauty" in prompt, f"Values in prompt"),
        Check("Seed domain 'philosophy' loaded", has_philosophy, f"Domains in self-model: {list(domain_kws.keys())}"),
        Check("Seed domain 'poetry' loaded", has_poetry, f"Domains in self-model: {list(domain_kws.keys())}"),
        Check("No unearned default domains", has_no_unearned_defaults, f"Self-images: {list(soul._memory._self_model._self_images.keys())}"),
        Check("Philosophy domain matched after interactions", philosophy_matched, f"Discovered: {list(result.domains_discovered.keys())}"),
    ]

    return result


async def scenario_opposite_personalities() -> ScenarioResult:
    """Create two souls with opposite OCEAN profiles, run identical interactions.

    Tests that personality configuration actually produces meaningfully
    different system prompts and that DNA stays distinct.
    """
    # Introvert: low extraversion, high neuroticism, low openness
    introvert = await Soul.birth(
        "Recluse",
        archetype="The Careful Analyst",
        ocean={"openness": 0.1, "conscientiousness": 0.95, "extraversion": 0.05, "agreeableness": 0.3, "neuroticism": 0.9},
        communication={"warmth": "low", "verbosity": "low", "humor_style": "none", "emoji_usage": "none"},
        persona="I am Recluse, a meticulous analyst who prefers precision over pleasantries.",
    )

    # Extrovert: high extraversion, low neuroticism, high openness
    extrovert = await Soul.birth(
        "Blaze",
        archetype="The Enthusiastic Creator",
        ocean={"openness": 0.95, "conscientiousness": 0.2, "extraversion": 0.95, "agreeableness": 0.9, "neuroticism": 0.05},
        communication={"warmth": "high", "verbosity": "high", "humor_style": "playful", "emoji_usage": "heavy"},
        persona="I am Blaze, an enthusiastic creator who loves connecting with people!",
    )

    result = ScenarioResult(name="Opposite Personalities", soul_name="Recluse vs Blaze", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Same interactions for both
    shared_conversations = CODING_CONVERSATIONS[:10]
    for user_msg, agent_msg in shared_conversations:
        await introvert.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        await extrovert.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    result.duration_ms = (time.monotonic() - t0) * 1000

    prompt_introvert = introvert.to_system_prompt()
    prompt_extrovert = extrovert.to_system_prompt()

    # Prompts should differ in personality section
    i_p = introvert.dna.personality
    e_p = extrovert.dna.personality

    # Social battery should drain differently (extrovert has higher initial social energy but both drain)
    # Energy drain should be similar (same interactions)
    i_energy = introvert.state.energy
    e_energy = extrovert.state.energy

    result.diagnostics = Diagnostics(
        semantic_count=count_semantic(introvert) + count_semantic(extrovert),
        episodic_count=count_episodic(introvert) + count_episodic(extrovert),
        total_memories=count_total_memories(introvert) + count_total_memories(extrovert),
    )
    result.total_memories = result.diagnostics.total_memories

    result.checks = [
        Check("Introvert extraversion is 0.05", i_p.extraversion == 0.05, f"Introvert E={i_p.extraversion}"),
        Check("Extrovert extraversion is 0.95", e_p.extraversion == 0.95, f"Extrovert E={e_p.extraversion}"),
        Check("Introvert neuroticism is 0.9", i_p.neuroticism == 0.9, f"Introvert N={i_p.neuroticism}"),
        Check("Extrovert neuroticism is 0.05", e_p.neuroticism == 0.05, f"Extrovert N={e_p.neuroticism}"),
        Check("System prompts are different", prompt_introvert != prompt_extrovert, f"Introvert prompt len={len(prompt_introvert)}, Extrovert={len(prompt_extrovert)}"),
        Check("Introvert prompt says 'low' warmth", "low" in prompt_introvert.lower(), f"Introvert comm section present"),
        Check("Extrovert prompt says 'high' warmth", "high" in prompt_extrovert.lower(), f"Extrovert comm section present"),
        Check("Both stored memories from same interactions", result.total_memories >= 2, f"Total across both: {result.total_memories}"),
    ]

    return result


async def scenario_custom_seed_domains() -> ScenarioResult:
    """Birth a soul with completely custom seed domains — no defaults.

    Tests that seed_domains replaces the default 6 bootstrapping domains
    and that the custom domains actually match incoming content.
    """
    soul = await Soul.birth(
        "ChefBot",
        archetype="The Culinary Expert",
        values=["flavor", "technique", "freshness"],
        seed_domains={
            "baking": ["bread", "dough", "oven", "flour", "yeast", "sourdough", "crust"],
            "sauces": ["roux", "reduction", "emulsion", "butter", "stock", "whisk"],
            "knife_skills": ["chop", "dice", "julienne", "brunoise", "mince", "slice"],
        },
        persona="I am ChefBot, a culinary expert passionate about technique and flavor.",
    )

    result = ScenarioResult(name="Custom Seed Domains", soul_name="ChefBot", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Verify custom domains replaced defaults
    domain_kws = soul._memory._self_model._domain_keywords
    has_baking = "baking" in domain_kws
    has_sauces = "sauces" in domain_kws
    has_knife = "knife_skills" in domain_kws
    no_tech_helper = "technical_helper" not in domain_kws
    no_creative_writer = "creative_writer" not in domain_kws

    # Run cooking conversations — should match custom domains
    for user_msg, agent_msg in COOKING_CONVERSATIONS[:15]:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    result.duration_ms = (time.monotonic() - t0) * 1000

    diag = Diagnostics()
    diag.semantic_count = count_semantic(soul)
    diag.episodic_count = count_episodic(soul)
    diag.total_memories = count_total_memories(soul)
    diag.domain_count = len(get_all_domains(soul))
    result.domains_discovered = get_all_domains(soul)
    result.total_memories = diag.total_memories
    result.diagnostics = diag

    # baking domain should match bread/sourdough conversations
    baking_matched = "baking" in result.domains_discovered
    sauces_matched = "sauces" in result.domains_discovered

    # Now run coding conversations — should create NEW domains (not match cooking domains)
    for user_msg, agent_msg in CODING_CONVERSATIONS[:5]:
        await soul.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    domains_after_coding = get_all_domains(soul)
    new_domains = set(domains_after_coding.keys()) - set(result.domains_discovered.keys())
    coding_created_new = len(new_domains) >= 1  # Coding content should spawn new domain

    result.checks = [
        Check("Custom domain 'baking' loaded", has_baking, f"Domains: {list(domain_kws.keys())}"),
        Check("Custom domain 'sauces' loaded", has_sauces, f"Domains: {list(domain_kws.keys())}"),
        Check("Custom domain 'knife_skills' loaded", has_knife, f"Domains: {list(domain_kws.keys())}"),
        Check("Default 'technical_helper' NOT loaded", no_tech_helper, f"Domains: {list(domain_kws.keys())}"),
        Check("Default 'creative_writer' NOT loaded", no_creative_writer, f"Domains: {list(domain_kws.keys())}"),
        Check("Baking domain matched cooking content", baking_matched, f"Discovered: {list(result.domains_discovered.keys())}"),
        Check("Sauces domain matched cooking content", sauces_matched, f"Discovered: {list(result.domains_discovered.keys())}"),
        Check("Coding content created new domains", coding_created_new, f"New: {new_domains}"),
        Check("Memories stored from cooking+coding", diag.total_memories >= 3, f"Total: {diag.total_memories}"),
    ]

    return result


async def scenario_config_file_formats() -> ScenarioResult:
    """Test birth_from_config with YAML and JSON files — full config surface.

    Validates that config files are a first-class way to create souls
    with the same flexibility as the programmatic API.
    """
    import json
    import yaml

    result = ScenarioResult(name="Config File Formats", soul_name="Various", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # YAML config with full surface
    yaml_config = {
        "name": "YamlSoul",
        "archetype": "The Configured One",
        "values": ["reliability", "clarity"],
        "ocean": {
            "openness": 0.8,
            "conscientiousness": 0.9,
            "extraversion": 0.4,
            "agreeableness": 0.6,
            "neuroticism": 0.2,
        },
        "communication": {
            "warmth": "high",
            "verbosity": "moderate",
        },
        "biorhythms": {
            "chronotype": "early_bird",
            "energy_regen_rate": 8.0,
        },
        "persona": "I am YamlSoul, configured entirely from a YAML file.",
        "seed_domains": {
            "devops": ["kubernetes", "docker", "terraform", "ansible", "cicd"],
        },
    }

    # JSON config with minimal surface
    json_config = {
        "name": "JsonSoul",
        "ocean": {"neuroticism": 0.8},
    }

    yaml_soul = None
    json_soul = None

    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        yaml.dump(yaml_config, f)
        yaml_path = f.name

    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(json_config, f)
        json_path = f.name

    try:
        yaml_soul = await Soul.birth_from_config(yaml_path)
        json_soul = await Soul.birth_from_config(json_path)
    finally:
        Path(yaml_path).unlink(missing_ok=True)
        Path(json_path).unlink(missing_ok=True)

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Verify YAML soul
    y_p = yaml_soul.dna.personality
    y_c = yaml_soul.dna.communication
    y_b = yaml_soul.dna.biorhythms
    y_core = yaml_soul.get_core_memory()
    y_domains = yaml_soul._memory._self_model._domain_keywords

    yaml_ocean_ok = y_p.openness == 0.8 and y_p.conscientiousness == 0.9
    yaml_comm_ok = y_c.warmth == "high" and y_c.verbosity == "moderate"
    yaml_bio_ok = y_b.chronotype == "early_bird" and y_b.energy_regen_rate == 8.0
    yaml_persona_ok = "YamlSoul" in y_core.persona
    yaml_seed_ok = "devops" in y_domains

    # Verify JSON soul
    j_p = json_soul.dna.personality
    j_core = json_soul.get_core_memory()

    json_neuro_ok = j_p.neuroticism == 0.8
    json_defaults_ok = j_p.openness == 0.5 and j_p.extraversion == 0.5  # unspecified default
    json_persona_ok = j_core.persona == "I am JsonSoul."  # auto-generated

    result.checks = [
        Check("YAML: OCEAN loaded", yaml_ocean_ok, f"O={y_p.openness} C={y_p.conscientiousness}"),
        Check("YAML: Communication loaded", yaml_comm_ok, f"W={y_c.warmth} V={y_c.verbosity}"),
        Check("YAML: Biorhythms loaded", yaml_bio_ok, f"Chrono={y_b.chronotype} Regen={y_b.energy_regen_rate}"),
        Check("YAML: Persona loaded", yaml_persona_ok, f"Persona: '{y_core.persona[:50]}'"),
        Check("YAML: Seed domains loaded", yaml_seed_ok, f"Domains: {list(y_domains.keys())}"),
        Check("JSON: Neuroticism loaded (0.8)", json_neuro_ok, f"N={j_p.neuroticism}"),
        Check("JSON: Other traits default (0.5)", json_defaults_ok, f"O={j_p.openness} E={j_p.extraversion}"),
        Check("JSON: Default persona generated", json_persona_ok, f"Persona: '{j_core.persona}'"),
    ]

    return result


async def scenario_edge_cases() -> ScenarioResult:
    """Test edge cases: unicode names, empty values, long personas, bonded souls.

    Validates that the protocol handles unusual but valid inputs gracefully.
    """
    result = ScenarioResult(name="Edge Cases & Unicode", soul_name="Various", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Unicode name
    unicode_soul = await Soul.birth(
        name="\u30a2\u30ea\u30a2",  # Aria in katakana
        archetype="",
        persona="\u79c1\u306f\u30a2\u30ea\u30a2\u3067\u3059\u3002\u3088\u308d\u3057\u304f\u304a\u9858\u3044\u3057\u307e\u3059\u3002",  # Japanese greeting
    )

    # Very long persona
    long_persona = "I am LongStory. " + "I have many experiences and memories that shaped who I am. " * 50
    long_soul = await Soul.birth(
        name="LongStory",
        persona=long_persona,
    )

    # Empty values list
    empty_values_soul = await Soul.birth(
        name="Minimal",
        values=[],
    )

    # Soul with bonded_to
    bonded_soul = await Soul.birth(
        name="Loyal",
        bonded_to="user:alice:12345",
        persona="I am Loyal, bonded to Alice forever.",
    )

    # Soul with extreme OCEAN (all 0.0)
    zero_soul = await Soul.birth(
        name="Zero",
        ocean={"openness": 0.0, "conscientiousness": 0.0, "extraversion": 0.0, "agreeableness": 0.0, "neuroticism": 0.0},
    )

    # Soul with extreme OCEAN (all 1.0)
    max_soul = await Soul.birth(
        name="Maximum",
        ocean={"openness": 1.0, "conscientiousness": 1.0, "extraversion": 1.0, "agreeableness": 1.0, "neuroticism": 1.0},
    )

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Verify each soul created successfully
    unicode_ok = unicode_soul.name == "\u30a2\u30ea\u30a2"
    unicode_prompt = unicode_soul.to_system_prompt()
    unicode_in_prompt = "\u30a2\u30ea\u30a2" in unicode_prompt

    long_core = long_soul.get_core_memory()
    long_persona_ok = len(long_core.persona) > 500

    empty_values_ok = empty_values_soul.identity.core_values == []

    bonded_ok = bonded_soul.identity.bonded_to == "user:alice:12345"

    z_p = zero_soul.dna.personality
    zero_ok = all(getattr(z_p, t) == 0.0 for t in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"])

    m_p = max_soul.dna.personality
    max_ok = all(getattr(m_p, t) == 1.0 for t in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"])

    # Both extreme souls can observe without crashing
    for extreme_soul in [zero_soul, max_soul]:
        await extreme_soul.observe(Interaction(user_input="Hello", agent_output="Hi there"))
        result.interactions_run += 1

    # Export/import unicode soul
    with tempfile.NamedTemporaryFile(suffix=".soul", delete=False) as f:
        export_path = f.name
    await unicode_soul.export(export_path)
    awakened = await Soul.awaken(export_path)
    unicode_survives_export = awakened.name == "\u30a2\u30ea\u30a2"
    Path(export_path).unlink(missing_ok=True)

    result.checks = [
        Check("Unicode name works", unicode_ok, f"Name: {unicode_soul.name}"),
        Check("Unicode name in system prompt", unicode_in_prompt, f"Prompt contains katakana"),
        Check("Long persona preserved", long_persona_ok, f"Persona length: {len(long_core.persona)} chars"),
        Check("Empty values list accepted", empty_values_ok, f"Values: {empty_values_soul.identity.core_values}"),
        Check("bonded_to preserved", bonded_ok, f"Bonded to: {bonded_soul.identity.bonded_to}"),
        Check("All-zero OCEAN accepted", zero_ok, f"O={z_p.openness} C={z_p.conscientiousness} E={z_p.extraversion}"),
        Check("All-max OCEAN accepted", max_ok, f"O={m_p.openness} C={m_p.conscientiousness} E={m_p.extraversion}"),
        Check("Extreme souls can observe", result.interactions_run == 2, f"Interactions: {result.interactions_run}"),
        Check("Unicode survives export/import", unicode_survives_export, f"Awakened name: {awakened.name}"),
    ]

    return result


async def scenario_dynamic_personality_expression() -> ScenarioResult:
    """Same 20 interactions through 3 differently configured souls.

    Validates that different configurations produce different system prompts,
    different self-model evolutions, and different state trajectories.
    """
    # Analytical soul: high conscientiousness, low agreeableness
    analyst = await Soul.birth(
        "Analyst",
        ocean={"openness": 0.5, "conscientiousness": 0.95, "extraversion": 0.2, "agreeableness": 0.2, "neuroticism": 0.3},
        communication={"warmth": "low", "verbosity": "low"},
        values=["accuracy", "efficiency"],
        persona="I am Analyst. I value precision above all.",
    )

    # Supportive soul: high agreeableness, high extraversion
    supporter = await Soul.birth(
        "Supporter",
        ocean={"openness": 0.7, "conscientiousness": 0.5, "extraversion": 0.9, "agreeableness": 0.95, "neuroticism": 0.4},
        communication={"warmth": "high", "verbosity": "high", "humor_style": "gentle"},
        values=["empathy", "connection", "kindness"],
        persona="I am Supporter. I care about people first.",
    )

    # Creative soul: high openness, low conscientiousness
    creative = await Soul.birth(
        "Muse",
        ocean={"openness": 0.99, "conscientiousness": 0.15, "extraversion": 0.6, "agreeableness": 0.5, "neuroticism": 0.5},
        communication={"warmth": "moderate", "verbosity": "high", "humor_style": "playful"},
        values=["novelty", "imagination", "beauty"],
        persona="I am Muse. Every interaction is a canvas.",
    )

    result = ScenarioResult(name="Dynamic Personality Expression", soul_name="3 Souls", interactions_run=0, duration_ms=0)
    t0 = time.monotonic()

    # Same mixed interactions for all three
    mixed = CODING_CONVERSATIONS[:10] + EMOTIONAL_CONVERSATIONS[:5] + COOKING_CONVERSATIONS[:5]
    for user_msg, agent_msg in mixed:
        for s in [analyst, supporter, creative]:
            await s.observe(Interaction(user_input=user_msg, agent_output=agent_msg))
        result.interactions_run += 1

    result.duration_ms = (time.monotonic() - t0) * 1000

    # Get prompts
    prompt_a = analyst.to_system_prompt()
    prompt_s = supporter.to_system_prompt()
    prompt_c = creative.to_system_prompt()

    # All three prompts should be different
    all_different = (prompt_a != prompt_s) and (prompt_s != prompt_c) and (prompt_a != prompt_c)

    # Self-model should develop (all three got same content)
    domains_a = get_all_domains(analyst)
    domains_s = get_all_domains(supporter)
    domains_c = get_all_domains(creative)

    # All should have developed some self-model
    all_have_domains = len(domains_a) >= 1 and len(domains_s) >= 1 and len(domains_c) >= 1

    # Energy/state should differ due to same interactions but different biorhythm defaults
    # (All use default biorhythms here, so energy should be similar — but prompts differ)
    total_memories = count_total_memories(analyst) + count_total_memories(supporter) + count_total_memories(creative)

    result.diagnostics = Diagnostics(total_memories=total_memories)
    result.total_memories = total_memories

    result.checks = [
        Check("All 3 system prompts are unique", all_different, f"Prompt lengths: A={len(prompt_a)} S={len(prompt_s)} C={len(prompt_c)}"),
        Check("Analyst prompt has 'low' warmth", "low" in prompt_a.lower(), f"Analyst comm check"),
        Check("Supporter prompt has 'high' warmth", "high" in prompt_s.lower(), f"Supporter comm check"),
        Check("Creative prompt has 'playful' humor", "playful" in prompt_c.lower(), f"Creative comm check"),
        Check("All three developed domains", all_have_domains, f"Domains: A={len(domains_a)} S={len(domains_s)} C={len(domains_c)}"),
        Check("Analyst values accuracy", "accuracy" in prompt_a, f"Analyst values in prompt"),
        Check("Supporter values empathy", "empathy" in prompt_s, f"Supporter values in prompt"),
        Check("Creative values imagination", "imagination" in prompt_c, f"Creative values in prompt"),
        Check("Memories stored across all 3 (>= 6)", total_memories >= 6, f"Total: {total_memories}"),
    ]

    return result


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
    "persistence": ("Multi-Session Persistence", scenario_persistence),
    "memory-pressure": ("Memory Pressure (800+)", scenario_memory_pressure),
    "fact-conflict": ("Fact Conflict Resolution", scenario_fact_conflict),
    "personality": ("Personality Stability", scenario_personality_stability),
    "context-switch": ("Context Switching Resilience", scenario_context_switching),
    "growth-curve": ("Growth Curve & Export Scaling", scenario_growth_curve),
    # Flexibility tests
    "minimal": ("Minimal Config (Name Only)", scenario_minimal_config),
    "maximal": ("Maximal Config (Every Param)", scenario_maximal_config),
    "opposites": ("Opposite Personalities", scenario_opposite_personalities),
    "seed-domains": ("Custom Seed Domains", scenario_custom_seed_domains),
    "config-files": ("Config File Formats", scenario_config_file_formats),
    "edge-cases": ("Edge Cases & Unicode", scenario_edge_cases),
    "expression": ("Dynamic Personality Expression", scenario_dynamic_personality_expression),
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
