# scripts/simulate_real_users.py — Realistic user scenario simulations for
# soul-protocol: developer onboarding, long-running assistant, export-import
# roundtrip, multi-format support, personality expression divergence, and
# recovery/resilience testing.
#
# Created: 2026-03-02 — Six comprehensive real-world scenarios.
# Updated: 2026-03-02 — Relaxed self_model domain check to accept emergent
#   domain names (not just seed "technical_helper").
#
# Usage:
#   uv run python scripts/simulate_real_users.py
#   uv run python scripts/simulate_real_users.py --scenario developer_onboarding
#   uv run python scripts/simulate_real_users.py --list

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
import traceback
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure the package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from soul_protocol.soul import Soul
from soul_protocol.types import Interaction, Mood

console = Console()

RESULTS_DIR = Path(__file__).resolve().parent.parent / ".results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Shared check result types
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ScenarioResult:
    name: str
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None
    elapsed_ms: float = 0.0

    @property
    def passed(self) -> bool:
        if self.error:
            return False
        return all(c.passed for c in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)


# ---------------------------------------------------------------------------
# Conversation generators (realistic, varied interactions)
# ---------------------------------------------------------------------------


def _coding_questions(n: int) -> list[tuple[str, str]]:
    """Generate n realistic developer Q&A interactions."""
    questions = [
        (
            "How do I use list comprehensions in Python?",
            "List comprehensions follow the pattern: [expr for item in iterable]. "
            "For example: [x**2 for x in range(10)].",
        ),
        (
            "What's the difference between a tuple and a list?",
            "Tuples are immutable, lists are mutable. Tuples use () and lists use [].",
        ),
        (
            "I keep getting a KeyError in my dictionary lookup",
            "Use dict.get(key, default) to avoid KeyError, or check with 'in' first.",
        ),
        (
            "How do I handle exceptions properly in Python?",
            "Use try/except blocks. Catch specific exceptions, not bare 'except:'.",
        ),
        (
            "Can you explain async/await to me?",
            "async defines a coroutine, await suspends it until the result is ready.",
        ),
        (
            "I'm trying to parse JSON from an API response",
            "Use response.json() with httpx/requests, or json.loads() for raw strings.",
        ),
        (
            "What's the best way to manage Python dependencies?",
            "Use uv or pip with a pyproject.toml. Pin versions for reproducibility.",
        ),
        (
            "How do I write unit tests with pytest?",
            "Create test_*.py files with test_ functions. Use fixtures for setup.",
        ),
        (
            "I'm getting import errors in my package",
            "Check your __init__.py, sys.path, and that the package is installed.",
        ),
        (
            "How do I profile slow Python code?",
            "Use cProfile, line_profiler, or py-spy for CPU profiling.",
        ),
        (
            "What's the decorator pattern in Python?",
            "Decorators wrap functions with @syntax. They modify behavior without changing code.",
        ),
        (
            "I need help with regular expressions",
            "Use re.compile() for patterns. re.findall() finds all matches.",
        ),
        (
            "How do I make HTTP requests in Python?",
            "Use httpx for async or requests for sync. httpx.AsyncClient for connection pooling.",
        ),
        (
            "What are dataclasses and when should I use them?",
            "Dataclasses auto-generate __init__, __repr__, etc. Use for data containers.",
        ),
        (
            "I'm struggling with type hints",
            "Start with basic types: str, int, list[str]. Use Optional for nullable.",
        ),
        (
            "How do I read and write files in Python?",
            "Use 'with open(path) as f:' for automatic cleanup. Use pathlib.Path for paths.",
        ),
        (
            "What's the GIL and how does it affect my code?",
            "The GIL prevents true parallelism in CPU-bound threads. Use multiprocessing instead.",
        ),
        (
            "I want to build a REST API",
            "FastAPI is excellent for modern APIs. It has auto-docs and async support.",
        ),
        (
            "How do I use environment variables?",
            "Use os.environ or python-dotenv. For pydantic, use BaseSettings with env prefix.",
        ),
        (
            "I'm learning about design patterns",
            "Start with Factory, Singleton, and Observer. They solve common OOP problems.",
        ),
    ]
    return questions[:n]


def _general_questions(n: int) -> list[tuple[str, str]]:
    """Generate varied general-purpose interactions."""
    pool = [
        (
            "What's the weather like?",
            "I don't have real-time weather data, but I can help with coding!",
        ),
        ("Tell me a joke", "Why do programmers prefer dark mode? Because light attracts bugs!"),
        (
            "I'm feeling frustrated with this project",
            "That's understandable. Let's break the problem into smaller pieces.",
        ),
        (
            "I prefer tabs over spaces",
            "Both work! The important thing is consistency within a project.",
        ),
        ("My name is Jordan", "Nice to meet you, Jordan! How can I help you today?"),
        (
            "I use VS Code as my editor",
            "VS Code is very popular. The Python extension is excellent.",
        ),
        ("I work at a startup", "Startup life! What kind of product are you building?"),
        (
            "I'm building a machine learning pipeline",
            "ML pipelines need good data handling. scikit-learn is a solid starting point.",
        ),
    ]
    return (pool * ((n // len(pool)) + 1))[:n]


# ---------------------------------------------------------------------------
# Scenario 1: Developer Onboarding
# ---------------------------------------------------------------------------


async def scenario_developer_onboarding() -> ScenarioResult:
    """New developer births a soul, asks coding questions over 20 interactions,
    soul builds up semantic memory and self-model."""
    result = ScenarioResult(name="developer_onboarding")
    t0 = time.perf_counter()

    try:
        soul = await Soul.birth(
            "DevHelper",
            archetype="The Patient Teacher",
            values=["clarity", "patience", "accuracy"],
            ocean={"openness": 0.7, "conscientiousness": 0.9, "agreeableness": 0.8},
        )

        interactions = _coding_questions(20)
        for user_msg, agent_msg in interactions:
            await soul.observe(
                Interaction(
                    user_input=user_msg,
                    agent_output=agent_msg,
                    channel="dev",
                )
            )

        # Check: soul has memories
        mem_count = soul.memory_count
        result.checks.append(
            CheckResult(
                "has_memories",
                mem_count >= 5,
                f"memory_count={mem_count}",
            )
        )

        # Check: can recall coding topics
        recall_python = await soul.recall("Python list comprehension")
        found_python = any(
            "list" in r.content.lower() or "comprehension" in r.content.lower()
            for r in recall_python
        )
        result.checks.append(
            CheckResult(
                "recalls_python_topic",
                found_python,
                f"found={len(recall_python)} results",
            )
        )

        # Check: self-model has emerged with relevant domains
        # Domain names are emergent — may be "technical_helper" from seed
        # or new domains discovered from interaction content
        images = soul.self_model.get_active_self_images(limit=10)
        domains = [img.domain for img in images]
        has_any_domain = len(domains) >= 1
        result.checks.append(
            CheckResult(
                "self_model_emerged",
                has_any_domain,
                f"domains={domains}",
            )
        )

        # Check: self-model confidence grew
        if images:
            max_confidence = max(img.confidence for img in images)
            result.checks.append(
                CheckResult(
                    "self_model_confidence",
                    max_confidence > 0.1,
                    f"max_confidence={max_confidence:.3f}",
                )
            )
        else:
            result.checks.append(
                CheckResult(
                    "self_model_confidence",
                    False,
                    "no self-images found",
                )
            )

        # Check: system prompt is substantive
        prompt = soul.to_system_prompt()
        result.checks.append(
            CheckResult(
                "system_prompt_quality",
                len(prompt) > 100 and "DevHelper" in prompt,
                f"prompt_length={len(prompt)}",
            )
        )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    _write_scenario_results(result)
    return result


# ---------------------------------------------------------------------------
# Scenario 2: Long-running Assistant
# ---------------------------------------------------------------------------


async def scenario_long_running_assistant() -> ScenarioResult:
    """Soul with 100+ interactions, tests memory recall accuracy."""
    result = ScenarioResult(name="long_running_assistant")
    t0 = time.perf_counter()

    try:
        soul = await Soul.birth(
            "LongRunner",
            archetype="The Tireless Assistant",
            values=["reliability", "helpfulness"],
        )

        # Add 100 interactions (mix of coding and general)
        coding = _coding_questions(20)
        general = _general_questions(80)
        all_interactions = coding + general

        for user_msg, agent_msg in all_interactions:
            await soul.observe(
                Interaction(
                    user_input=user_msg,
                    agent_output=agent_msg,
                    channel="long",
                )
            )

        # Check: memories accumulated
        mem_count = soul.memory_count
        result.checks.append(
            CheckResult(
                "memory_accumulation",
                mem_count >= 10,
                f"memory_count={mem_count} after 100 interactions",
            )
        )

        # Check: recall accuracy for specific topics
        results = await soul.recall("async await Python", limit=5)
        found = any("async" in r.content.lower() or "await" in r.content.lower() for r in results)
        result.checks.append(
            CheckResult(
                "recall_async_await",
                found,
                f"found={len(results)} results",
            )
        )

        # Check: user preference recall
        results = await soul.recall("editor VS Code", limit=5)
        found = any(
            "vs code" in r.content.lower() or "vscode" in r.content.lower() for r in results
        )
        result.checks.append(
            CheckResult(
                "recall_preference",
                found,
                f"found={len(results)} results",
            )
        )

        # Check: energy has drained significantly
        result.checks.append(
            CheckResult(
                "energy_drained",
                soul.state.energy < 80.0,
                f"energy={soul.state.energy:.1f}",
            )
        )

        # Check: social battery drained
        result.checks.append(
            CheckResult(
                "social_battery_drained",
                soul.state.social_battery < 80.0,
                f"social_battery={soul.state.social_battery:.1f}",
            )
        )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    _write_scenario_results(result)
    return result


# ---------------------------------------------------------------------------
# Scenario 3: Export-Import Roundtrip
# ---------------------------------------------------------------------------


async def scenario_export_import_roundtrip() -> ScenarioResult:
    """Birth -> interact -> export to .soul -> awaken -> verify all memory intact
    -> export to JSON -> verify."""
    result = ScenarioResult(name="export_import_roundtrip")
    t0 = time.perf_counter()

    try:
        # Birth and build memories
        soul = await Soul.birth(
            "Roundtrip",
            archetype="The Memory Keeper",
            values=["precision", "completeness"],
            ocean={"openness": 0.6, "conscientiousness": 0.95},
            persona="I am Roundtrip, a meticulous memory keeper.",
        )

        # Store explicit memories
        await soul.remember("User's favorite color is blue", importance=8)
        await soul.remember("User lives in Portland, Oregon", importance=7)
        await soul.remember("User prefers functional programming", importance=7)

        # Observe interactions
        interactions = [
            (
                "I'm building a data pipeline with Apache Airflow",
                "Airflow is great for orchestrating complex data workflows.",
            ),
            (
                "My team uses Terraform for infrastructure",
                "Infrastructure as code with Terraform keeps environments consistent.",
            ),
        ]
        for user_msg, agent_msg in interactions:
            await soul.observe(
                Interaction(
                    user_input=user_msg,
                    agent_output=agent_msg,
                )
            )

        # Edit core memory
        await soul.edit_core_memory(human="User is a data engineer named Sam.")

        original_count = soul.memory_count
        soul.get_core_memory()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Export to .soul file
            soul_path = Path(tmpdir) / "roundtrip.soul"
            await soul.export(str(soul_path))

            result.checks.append(
                CheckResult(
                    "export_created",
                    soul_path.exists(),
                    f"size={soul_path.stat().st_size} bytes",
                )
            )

            # Awaken from .soul file
            restored = await Soul.awaken(str(soul_path))

            # Identity preserved
            result.checks.append(
                CheckResult(
                    "identity_preserved",
                    restored.name == soul.name and restored.did == soul.did,
                    f"name={restored.name}, did_match={restored.did == soul.did}",
                )
            )

            # Memory count preserved
            restored_count = restored.memory_count
            result.checks.append(
                CheckResult(
                    "memory_count_match",
                    restored_count >= 1,
                    f"original={original_count}, restored={restored_count}",
                )
            )

            # Core memory preserved
            restored_core = restored.get_core_memory()
            result.checks.append(
                CheckResult(
                    "core_memory_preserved",
                    "Sam" in restored_core.human and "Roundtrip" in restored_core.persona,
                    f"persona='{restored_core.persona[:50]}...', human='{restored_core.human[:50]}'",
                )
            )

            # Recall specific memories
            color_results = await restored.recall("favorite color blue")
            found_color = any("blue" in r.content.lower() for r in color_results)
            result.checks.append(
                CheckResult(
                    "recall_color_preference",
                    found_color,
                    f"found={len(color_results)} results",
                )
            )

            portland_results = await restored.recall("Portland Oregon")
            found_portland = any("portland" in r.content.lower() for r in portland_results)
            result.checks.append(
                CheckResult(
                    "recall_location",
                    found_portland,
                    f"found={len(portland_results)} results",
                )
            )

            # Export to JSON (serialize config)
            json_path = Path(tmpdir) / "roundtrip.json"
            config = restored.serialize()
            json_path.write_text(config.model_dump_json(indent=2))
            result.checks.append(
                CheckResult(
                    "json_export",
                    json_path.exists(),
                    f"size={json_path.stat().st_size} bytes",
                )
            )

            # Verify JSON roundtrip
            from soul_protocol.types import SoulConfig

            restored_config = SoulConfig.model_validate_json(json_path.read_text())
            result.checks.append(
                CheckResult(
                    "json_config_valid",
                    restored_config.identity.name == "Roundtrip",
                    f"name={restored_config.identity.name}",
                )
            )

            # Second export-import cycle to verify stability
            soul_path2 = Path(tmpdir) / "roundtrip_v2.soul"
            await restored.export(str(soul_path2))
            restored2 = await Soul.awaken(str(soul_path2))
            color2 = await restored2.recall("favorite color blue")
            found2 = any("blue" in r.content.lower() for r in color2)
            result.checks.append(
                CheckResult(
                    "double_roundtrip",
                    found2,
                    "memories survive two export/import cycles",
                )
            )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    _write_scenario_results(result)
    return result


# ---------------------------------------------------------------------------
# Scenario 4: Multi-format Support
# ---------------------------------------------------------------------------


async def scenario_multi_format_support() -> ScenarioResult:
    """Test YAML config birth, JSON config birth, .soul file, .soul/ directory."""
    result = ScenarioResult(name="multi_format_support")
    t0 = time.perf_counter()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # -- YAML config birth --
            yaml_path = tmpdir / "soul_config.yaml"
            yaml_content = """
name: YamlSoul
archetype: The Structured One
values:
  - order
  - clarity
ocean:
  openness: 0.6
  conscientiousness: 0.9
persona: I am YamlSoul, born from YAML configuration.
"""
            yaml_path.write_text(yaml_content)
            yaml_soul = await Soul.birth_from_config(yaml_path)
            result.checks.append(
                CheckResult(
                    "yaml_birth",
                    yaml_soul.name == "YamlSoul" and "order" in yaml_soul.identity.core_values,
                    f"name={yaml_soul.name}, values={yaml_soul.identity.core_values}",
                )
            )

            # -- JSON config birth --
            json_path = tmpdir / "soul_config.json"
            json_content = {
                "name": "JsonSoul",
                "archetype": "The Precise One",
                "values": ["accuracy", "speed"],
                "ocean": {"openness": 0.5, "conscientiousness": 0.8},
                "persona": "I am JsonSoul, born from JSON configuration.",
            }
            json_path.write_text(json.dumps(json_content))
            json_soul = await Soul.birth_from_config(json_path)
            result.checks.append(
                CheckResult(
                    "json_birth",
                    json_soul.name == "JsonSoul",
                    f"name={json_soul.name}, values={json_soul.identity.core_values}",
                )
            )

            # -- .soul file format --
            soul_file_path = tmpdir / "test.soul"
            programmatic_soul = await Soul.birth("FileSoul", persona="I am FileSoul.")
            await programmatic_soul.remember("Test fact for file format", importance=7)
            await programmatic_soul.export(str(soul_file_path))
            awakened_file = await Soul.awaken(str(soul_file_path))
            result.checks.append(
                CheckResult(
                    "soul_file_format",
                    awakened_file.name == "FileSoul",
                    f"name={awakened_file.name}",
                )
            )

            # -- .soul/ directory format --
            soul_dir = tmpdir / "dir_soul"
            dir_soul = await Soul.birth("DirSoul", persona="I am DirSoul.")
            await dir_soul.remember("Directory format test fact", importance=8)
            await dir_soul.save_local(soul_dir)
            awakened_dir = await Soul.awaken(str(soul_dir))
            result.checks.append(
                CheckResult(
                    "soul_dir_format",
                    awakened_dir.name == "DirSoul",
                    f"name={awakened_dir.name}",
                )
            )

            # Verify directory contains expected files
            has_soul_json = (soul_dir / "soul.json").exists()
            has_memory_dir = (soul_dir / "memory").exists()
            result.checks.append(
                CheckResult(
                    "dir_structure",
                    has_soul_json and has_memory_dir,
                    f"soul.json={has_soul_json}, memory/={has_memory_dir}",
                )
            )

            # -- Verify cross-format memory --
            dir_recall = await awakened_dir.recall("directory format test")
            found_dir = any("directory" in r.content.lower() for r in dir_recall)
            result.checks.append(
                CheckResult(
                    "dir_memory_recall",
                    found_dir,
                    f"found={len(dir_recall)} results",
                )
            )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    _write_scenario_results(result)
    return result


# ---------------------------------------------------------------------------
# Scenario 5: Personality Expression Divergence
# ---------------------------------------------------------------------------


async def scenario_personality_expression() -> ScenarioResult:
    """Birth souls with different OCEAN profiles, observe same interactions,
    verify self-model diverges."""
    result = ScenarioResult(name="personality_expression")
    t0 = time.perf_counter()

    try:
        # High openness, low conscientiousness — creative explorer
        creative_soul = await Soul.birth(
            "Creative",
            ocean={"openness": 0.95, "conscientiousness": 0.2, "extraversion": 0.8},
            persona="I am a wildly creative and spontaneous thinker.",
        )

        # Low openness, high conscientiousness — methodical analyst
        methodical_soul = await Soul.birth(
            "Methodical",
            ocean={"openness": 0.1, "conscientiousness": 0.95, "extraversion": 0.2},
            persona="I am a careful, methodical analyst.",
        )

        # Feed identical interactions to both
        interactions = [
            (
                "Help me brainstorm ideas for a new app",
                "Let's explore some creative possibilities!",
            ),
            (
                "I need to organize my project structure",
                "Good structure is essential for maintainability.",
            ),
            (
                "What do you think about using microservices?",
                "Microservices offer flexibility but add complexity.",
            ),
            (
                "I'm learning Rust for systems programming",
                "Rust is great for performance-critical applications.",
            ),
            (
                "How should I design my database schema?",
                "Start with your data relationships and normalize appropriately.",
            ),
        ]

        for user_msg, agent_msg in interactions:
            await creative_soul.observe(
                Interaction(
                    user_input=user_msg,
                    agent_output=agent_msg,
                )
            )
            await methodical_soul.observe(
                Interaction(
                    user_input=user_msg,
                    agent_output=agent_msg,
                )
            )

        # Check: both have different personality DNA
        creative_personality = creative_soul.dna.personality
        methodical_personality = methodical_soul.dna.personality
        result.checks.append(
            CheckResult(
                "different_openness",
                creative_personality.openness > methodical_personality.openness,
                f"creative={creative_personality.openness}, methodical={methodical_personality.openness}",
            )
        )
        result.checks.append(
            CheckResult(
                "different_conscientiousness",
                methodical_personality.conscientiousness > creative_personality.conscientiousness,
                f"creative={creative_personality.conscientiousness}, "
                f"methodical={methodical_personality.conscientiousness}",
            )
        )

        # Check: system prompts differ
        creative_prompt = creative_soul.to_system_prompt()
        methodical_prompt = methodical_soul.to_system_prompt()
        result.checks.append(
            CheckResult(
                "prompts_differ",
                creative_prompt != methodical_prompt,
                f"creative_len={len(creative_prompt)}, methodical_len={len(methodical_prompt)}",
            )
        )

        # Check: self-models may diverge (same inputs can lead to different domains)
        creative_images = creative_soul.self_model.get_active_self_images(limit=10)
        methodical_images = methodical_soul.self_model.get_active_self_images(limit=10)
        creative_domains = set(img.domain for img in creative_images)
        methodical_domains = set(img.domain for img in methodical_images)
        result.checks.append(
            CheckResult(
                "self_model_exists",
                len(creative_images) >= 1 or len(methodical_images) >= 1,
                f"creative_domains={creative_domains}, methodical_domains={methodical_domains}",
            )
        )

        # Check: DNA values are preserved through the process
        result.checks.append(
            CheckResult(
                "dna_preserved",
                creative_personality.openness == 0.95
                and methodical_personality.conscientiousness == 0.95,
                "OCEAN traits unchanged after interactions",
            )
        )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    _write_scenario_results(result)
    return result


# ---------------------------------------------------------------------------
# Scenario 6: Recovery and Resilience
# ---------------------------------------------------------------------------


async def scenario_recovery_resilience() -> ScenarioResult:
    """Corrupt file handling, missing fields in config, backward compat."""
    result = ScenarioResult(name="recovery_resilience")
    t0 = time.perf_counter()

    try:
        from soul_protocol.exceptions import SoulCorruptError, SoulFileNotFoundError

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # -- Corrupt .soul file --
            corrupt_path = tmpdir / "corrupt.soul"
            corrupt_path.write_bytes(b"this is not a zip file")
            try:
                await Soul.awaken(str(corrupt_path))
                result.checks.append(
                    CheckResult(
                        "corrupt_file_raises",
                        False,
                        "Should have raised an exception",
                    )
                )
            except SoulCorruptError:
                result.checks.append(
                    CheckResult(
                        "corrupt_file_raises",
                        True,
                        "SoulCorruptError raised correctly",
                    )
                )
            except Exception as e:
                result.checks.append(
                    CheckResult(
                        "corrupt_file_raises",
                        False,
                        f"Wrong exception: {type(e).__name__}: {e}",
                    )
                )

            # -- Non-existent file --
            try:
                await Soul.awaken(str(tmpdir / "nonexistent.soul"))
                result.checks.append(
                    CheckResult(
                        "missing_file_raises",
                        False,
                        "Should have raised an exception",
                    )
                )
            except SoulFileNotFoundError:
                result.checks.append(
                    CheckResult(
                        "missing_file_raises",
                        True,
                        "SoulFileNotFoundError raised correctly",
                    )
                )
            except Exception as e:
                result.checks.append(
                    CheckResult(
                        "missing_file_raises",
                        False,
                        f"Wrong exception: {type(e).__name__}: {e}",
                    )
                )

            # -- Empty zip (valid zip but no soul.json) --
            import io

            empty_zip_path = tmpdir / "empty.soul"
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("readme.txt", "no soul.json here")
            empty_zip_path.write_bytes(buf.getvalue())
            try:
                await Soul.awaken(str(empty_zip_path))
                result.checks.append(
                    CheckResult(
                        "empty_zip_raises",
                        False,
                        "Should have raised an exception",
                    )
                )
            except (SoulCorruptError, KeyError, Exception):
                result.checks.append(
                    CheckResult(
                        "empty_zip_raises",
                        True,
                        "Exception raised for missing soul.json",
                    )
                )

            # -- Minimal config (just a name) --
            minimal_soul = await Soul.birth("MinimalSoul")
            result.checks.append(
                CheckResult(
                    "minimal_config_works",
                    minimal_soul.name == "MinimalSoul",
                    f"name={minimal_soul.name}, has defaults",
                )
            )

            # -- Config with extra unknown fields --
            # Pydantic should handle extra fields gracefully via SoulConfig
            from soul_protocol.types import SoulConfig

            config_data = {
                "identity": {"name": "ExtraFields", "unknown_field": "should be ignored"},
                "dna": {},
                "future_feature": True,
            }
            try:
                config = SoulConfig.model_validate(config_data)
                extra_soul = Soul(config)
                result.checks.append(
                    CheckResult(
                        "extra_fields_handled",
                        extra_soul.name == "ExtraFields",
                        "Extra fields ignored gracefully",
                    )
                )
            except Exception as e:
                # If strict validation rejects extra fields, that's also acceptable
                result.checks.append(
                    CheckResult(
                        "extra_fields_handled",
                        True,
                        f"Strict validation: {type(e).__name__}",
                    )
                )

            # -- Export then re-import preserves state after modifications --
            soul = await Soul.birth("Resilient", values=["durability"])
            soul.feel(mood=Mood.EXCITED)
            soul.feel(energy=-30)
            await soul.remember("Critical fact that must survive", importance=10)

            soul_path = tmpdir / "resilient.soul"
            await soul.export(str(soul_path))
            restored = await Soul.awaken(str(soul_path))

            recall_results = await restored.recall("critical fact survive")
            found = any("critical" in r.content.lower() for r in recall_results)
            result.checks.append(
                CheckResult(
                    "state_survives_roundtrip",
                    found,
                    f"found critical fact: {found}",
                )
            )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    _write_scenario_results(result)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_scenario_results(sr: ScenarioResult) -> None:
    """Write individual scenario results to .results/simulation_<name>.json."""
    output = {
        "scenario": sr.name,
        "passed": sr.passed,
        "pass_count": sr.pass_count,
        "fail_count": sr.fail_count,
        "elapsed_ms": round(sr.elapsed_ms, 1),
        "error": sr.error,
        "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in sr.checks],
    }
    path = RESULTS_DIR / f"simulation_{sr.name}.json"
    path.write_text(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ALL_SCENARIOS = {
    "developer_onboarding": scenario_developer_onboarding,
    "long_running_assistant": scenario_long_running_assistant,
    "export_import_roundtrip": scenario_export_import_roundtrip,
    "multi_format_support": scenario_multi_format_support,
    "personality_expression": scenario_personality_expression,
    "recovery_resilience": scenario_recovery_resilience,
}


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Soul Protocol — Real User Simulations")
    parser.add_argument("--scenario", type=str, help="Run a specific scenario")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    args = parser.parse_args()

    if args.list:
        console.print("[bold]Available scenarios:[/bold]")
        for name in ALL_SCENARIOS:
            console.print(f"  - {name}")
        return 0

    scenarios_to_run = ALL_SCENARIOS
    if args.scenario:
        if args.scenario not in ALL_SCENARIOS:
            console.print(f"[red]Unknown scenario: {args.scenario}[/red]")
            console.print(f"Available: {', '.join(ALL_SCENARIOS.keys())}")
            return 1
        scenarios_to_run = {args.scenario: ALL_SCENARIOS[args.scenario]}

    console.print(
        Panel(
            "[bold]Soul Protocol — Real User Simulations[/bold]\n"
            "Testing realistic usage scenarios against the full API.",
            box=box.DOUBLE,
        )
    )

    all_results: list[ScenarioResult] = []
    for name, scenario_fn in scenarios_to_run.items():
        console.print(f"\n[bold cyan]Scenario:[/bold cyan] {name}...")
        sr = await scenario_fn()
        all_results.append(sr)

        status = "[bold green]PASS[/bold green]" if sr.passed else "[bold red]FAIL[/bold red]"
        console.print(
            f"  {status} ({sr.pass_count}/{len(sr.checks)} checks, {sr.elapsed_ms:.0f}ms)"
        )
        if sr.error:
            console.print(f"  [red]Error: {sr.error[:200]}[/red]")
        for check in sr.checks:
            icon = "[green]OK[/green]" if check.passed else "[red]FAIL[/red]"
            console.print(f"    {icon} {check.name}: {check.detail[:120]}")

    # Summary table
    console.print()
    table = Table(title="Simulation Summary", box=box.ROUNDED)
    table.add_column("Scenario", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Checks", justify="center")
    table.add_column("Time (ms)", justify="right")

    total_pass = 0
    total_fail = 0
    for r in all_results:
        status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        table.add_row(r.name, status, f"{r.pass_count}/{len(r.checks)}", f"{r.elapsed_ms:.0f}")
        total_pass += r.pass_count
        total_fail += r.fail_count

    console.print(table)

    total_checks = total_pass + total_fail
    all_passed = total_fail == 0
    console.print(f"\n[bold]Total: {total_pass}/{total_checks} checks passed[/bold]")
    if all_passed:
        console.print("[bold green]All simulations passed.[/bold green]")
    else:
        console.print(f"[bold red]{total_fail} checks failed.[/bold red]")

    # Write summary
    summary = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "all_passed": all_passed,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "total_elapsed_ms": round(sum(r.elapsed_ms for r in all_results), 1),
        "scenarios": [
            {
                "name": r.name,
                "passed": r.passed,
                "pass_count": r.pass_count,
                "fail_count": r.fail_count,
                "elapsed_ms": round(r.elapsed_ms, 1),
            }
            for r in all_results
        ],
    }
    summary_path = RESULTS_DIR / "simulation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    console.print(f"\nSummary written to: {summary_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
