# scripts/e2e_paw_integration.py — E2E integration test simulating PocketPaw's
# usage of soul-protocol: birth, observe, remember, recall, reflect, export,
# awaken, core memory editing, and MCP server tool smoke tests.
#
# Created: 2026-03-02 — Full lifecycle validation plus paw-bridge simulation.
#
# Usage:
#   uv run python scripts/e2e_paw_integration.py

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Ensure the package is importable when running from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from soul_protocol.soul import Soul
from soul_protocol.types import Interaction, MemoryType, Mood

console = Console()

RESULTS_DIR = Path(__file__).resolve().parent.parent / ".results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    elapsed_ms: float = 0.0


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
# Realistic paw-like interaction datasets
# ---------------------------------------------------------------------------

PROJECT_SCAN_INTERACTIONS = [
    (
        "I just opened a new Python project with FastAPI and SQLAlchemy",
        "Interesting stack! FastAPI is great for building APIs, and SQLAlchemy "
        "is a solid ORM. Let me help you get oriented.",
    ),
    (
        "The project uses Docker for deployment and has a Makefile",
        "Docker + Makefile is a clean setup. That makes builds reproducible "
        "and deployment straightforward.",
    ),
    (
        "There's a pyproject.toml with hatchling as the build backend",
        "Hatchling is lightweight and modern. It pairs well with uv for dependency management.",
    ),
]

CODING_INTERACTIONS = [
    (
        "How do I add a health check endpoint in FastAPI?",
        "You can add a simple GET /health route that returns a 200 with a JSON body.",
    ),
    (
        "I keep getting a 422 error when posting JSON to my endpoint",
        "422 means validation failed. Check your Pydantic model — the field "
        "names and types must match the incoming JSON exactly.",
    ),
    (
        "I prefer using async def for all my route handlers",
        "Good practice! FastAPI handles async natively, so you get better "
        "concurrency with async handlers.",
    ),
]

PREFERENCE_INTERACTIONS = [
    (
        "I prefer dark mode in all my editors",
        "Dark mode is easier on the eyes during long coding sessions.",
    ),
    (
        "I like using type hints everywhere in my Python code",
        "Type hints improve readability and catch bugs early with mypy.",
    ),
    (
        "My favorite testing framework is pytest with asyncio support",
        "pytest-asyncio is perfect for testing async code. Clean fixtures too.",
    ),
]


# ---------------------------------------------------------------------------
# Scenario: Full lifecycle (birth -> observe -> remember -> recall ->
#           reflect -> export -> awaken -> verify)
# ---------------------------------------------------------------------------


async def scenario_full_lifecycle() -> ScenarioResult:
    result = ScenarioResult(name="full_lifecycle")
    t0 = time.perf_counter()

    try:
        # 1. Birth
        soul = await Soul.birth(
            "PawAssistant",
            archetype="The Technical Helper",
            personality="I help developers write better code.",
            values=["helpfulness", "accuracy", "empathy"],
            ocean={"openness": 0.8, "conscientiousness": 0.9, "extraversion": 0.4},
        )
        result.checks.append(CheckResult("birth", True, f"name={soul.name}, did={soul.did}"))

        # 2. Observe project scanning interactions
        for user_msg, agent_msg in PROJECT_SCAN_INTERACTIONS:
            await soul.observe(
                Interaction(
                    user_input=user_msg,
                    agent_output=agent_msg,
                    channel="paw",
                )
            )
        result.checks.append(
            CheckResult(
                "observe_project_scan",
                True,
                f"{len(PROJECT_SCAN_INTERACTIONS)} interactions observed",
            )
        )

        # 3. Observe coding interactions
        for user_msg, agent_msg in CODING_INTERACTIONS:
            await soul.observe(
                Interaction(
                    user_input=user_msg,
                    agent_output=agent_msg,
                    channel="paw",
                )
            )
        result.checks.append(
            CheckResult(
                "observe_coding",
                True,
                f"{len(CODING_INTERACTIONS)} interactions observed",
            )
        )

        # 4. Remember explicit preferences
        for user_msg, agent_msg in PREFERENCE_INTERACTIONS:
            await soul.observe(
                Interaction(
                    user_input=user_msg,
                    agent_output=agent_msg,
                    channel="paw",
                )
            )
        result.checks.append(
            CheckResult(
                "observe_preferences",
                True,
                f"{len(PREFERENCE_INTERACTIONS)} interactions observed",
            )
        )

        # 5. Also store a direct semantic memory
        mem_id = await soul.remember(
            "User's primary language is Python 3.12",
            type=MemoryType.SEMANTIC,
            importance=8,
        )
        result.checks.append(
            CheckResult(
                "remember_direct",
                bool(mem_id),
                f"memory_id={mem_id}",
            )
        )

        # 6. Recall: query for FastAPI knowledge
        recall_results = await soul.recall("FastAPI endpoint")
        found_fastapi = any(
            "FastAPI" in r.content or "fastapi" in r.content.lower() for r in recall_results
        )
        result.checks.append(
            CheckResult(
                "recall_fastapi",
                found_fastapi,
                f"found={len(recall_results)} results, match={found_fastapi}",
            )
        )

        # 7. Recall: query for preferences
        pref_results = await soul.recall("dark mode")
        found_pref = any("dark" in r.content.lower() for r in pref_results)
        result.checks.append(
            CheckResult(
                "recall_preferences",
                found_pref,
                f"found={len(pref_results)} results, match={found_pref}",
            )
        )

        # 8. Reflect (without CognitiveEngine, returns None — that's OK)
        reflect_result = await soul.reflect()
        result.checks.append(
            CheckResult(
                "reflect",
                True,
                f"result={'None (no engine)' if reflect_result is None else 'reflected'}",
            )
        )

        # 9. Self-model should have emerged
        self_model = soul.self_model
        images = self_model.get_active_self_images(limit=5)
        has_images = len(images) >= 1
        domains = [img.domain for img in images]
        result.checks.append(
            CheckResult(
                "self_model_emerged",
                has_images,
                f"domains={domains}",
            )
        )

        # 10. System prompt includes soul info
        prompt = soul.to_system_prompt()
        has_name = "PawAssistant" in prompt
        result.checks.append(
            CheckResult(
                "system_prompt",
                has_name and len(prompt) > 100,
                f"length={len(prompt)}, has_name={has_name}",
            )
        )

        # 11. Export to .soul file
        with tempfile.TemporaryDirectory() as tmpdir:
            soul_path = Path(tmpdir) / "paw_assistant.soul"
            await soul.export(str(soul_path))
            file_exists = soul_path.exists()
            file_size = soul_path.stat().st_size if file_exists else 0
            result.checks.append(
                CheckResult(
                    "export",
                    file_exists and file_size > 0,
                    f"path={soul_path}, size={file_size} bytes",
                )
            )

            # 12. Awaken from exported .soul file
            restored = await Soul.awaken(str(soul_path))
            identity_match = (
                restored.name == soul.name
                and restored.did == soul.did
                and restored.archetype == soul.archetype
            )
            result.checks.append(
                CheckResult(
                    "awaken_identity",
                    identity_match,
                    f"name={restored.name}, did_match={restored.did == soul.did}",
                )
            )

            # 13. Verify recall works on restored soul
            restored_recall = await restored.recall("FastAPI")
            restored_ok = any(
                "fastapi" in r.content.lower() or "FastAPI" in r.content for r in restored_recall
            )
            result.checks.append(
                CheckResult(
                    "awaken_recall",
                    restored_ok,
                    f"found={len(restored_recall)} results after awaken",
                )
            )

            # 14. Memory count should be non-trivial
            original_count = soul.memory_count
            restored_count = restored.memory_count
            result.checks.append(
                CheckResult(
                    "memory_count_preserved",
                    restored_count >= 1,
                    f"original={original_count}, restored={restored_count}",
                )
            )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    return result


# ---------------------------------------------------------------------------
# Scenario: Core memory editing (persona + human fields)
# ---------------------------------------------------------------------------


async def scenario_core_memory_editing() -> ScenarioResult:
    result = ScenarioResult(name="core_memory_editing")
    t0 = time.perf_counter()

    try:
        soul = await Soul.birth(
            "Aria",
            archetype="The Creative Writer",
            persona="I am Aria, a creative writing assistant.",
        )

        # Initial core memory
        core = soul.get_core_memory()
        result.checks.append(
            CheckResult(
                "initial_persona",
                "Aria" in core.persona,
                f"persona='{core.persona[:60]}...'",
            )
        )

        # Edit persona
        await soul.edit_core_memory(persona="I also enjoy poetry and storytelling.")
        core = soul.get_core_memory()
        has_poetry = "poetry" in core.persona or "storytelling" in core.persona
        result.checks.append(
            CheckResult(
                "edit_persona",
                has_poetry,
                f"persona='{core.persona[:80]}...'",
            )
        )

        # Edit human field
        await soul.edit_core_memory(human="The user is a novelist named Alex.")
        core = soul.get_core_memory()
        has_alex = "Alex" in core.human
        result.checks.append(
            CheckResult(
                "edit_human",
                has_alex,
                f"human='{core.human}'",
            )
        )

        # Core memory survives export/awaken
        with tempfile.TemporaryDirectory() as tmpdir:
            soul_path = Path(tmpdir) / "aria_core.soul"
            await soul.export(str(soul_path))
            restored = await Soul.awaken(str(soul_path))
            restored_core = restored.get_core_memory()

            persona_ok = (
                "poetry" in restored_core.persona or "storytelling" in restored_core.persona
            )
            human_ok = "Alex" in restored_core.human
            result.checks.append(
                CheckResult(
                    "core_memory_survives_export",
                    persona_ok and human_ok,
                    f"persona_ok={persona_ok}, human_ok={human_ok}",
                )
            )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    return result


# ---------------------------------------------------------------------------
# Scenario: State management (mood, energy, social battery)
# ---------------------------------------------------------------------------


async def scenario_state_management() -> ScenarioResult:
    result = ScenarioResult(name="state_management")
    t0 = time.perf_counter()

    try:
        soul = await Soul.birth("Aria")

        # Default state
        result.checks.append(
            CheckResult(
                "initial_state",
                soul.state.mood == Mood.NEUTRAL and soul.state.energy == 100.0,
                f"mood={soul.state.mood.value}, energy={soul.state.energy}",
            )
        )

        # Feel updates mood
        soul.feel(mood=Mood.CURIOUS)
        result.checks.append(
            CheckResult(
                "feel_mood",
                soul.state.mood == Mood.CURIOUS,
                f"mood={soul.state.mood.value}",
            )
        )

        # Energy drains with interactions
        initial_energy = soul.state.energy
        for _ in range(5):
            await soul.observe(
                Interaction(
                    user_input="Tell me about something interesting",
                    agent_output="Here's something cool!",
                )
            )
        result.checks.append(
            CheckResult(
                "energy_drain",
                soul.state.energy < initial_energy,
                f"before={initial_energy}, after={soul.state.energy}",
            )
        )

        # Social battery drains too
        result.checks.append(
            CheckResult(
                "social_battery_drain",
                soul.state.social_battery < 100.0,
                f"social_battery={soul.state.social_battery}",
            )
        )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    return result


# ---------------------------------------------------------------------------
# Scenario: MCP server tools (programmatic, requires fastmcp)
# ---------------------------------------------------------------------------


async def scenario_mcp_tools() -> ScenarioResult:
    result = ScenarioResult(name="mcp_tools")
    t0 = time.perf_counter()

    try:
        # Check if fastmcp is available
        try:
            import fastmcp  # noqa: F401

            has_fastmcp = True
        except ImportError:
            has_fastmcp = False

        if not has_fastmcp:
            result.checks.append(
                CheckResult(
                    "fastmcp_available",
                    True,
                    "fastmcp not installed — skipping MCP tests (not a failure)",
                )
            )
            result.elapsed_ms = (time.perf_counter() - t0) * 1000
            return result

        # Import the MCP server module and test tools programmatically
        import soul_protocol.mcp.server as mcp_module
        from soul_protocol.mcp.server import (
            soul_birth,
            soul_feel,
            soul_observe,
            soul_prompt,
            soul_recall,
            soul_remember,
            soul_state,
        )

        # soul_birth
        birth_json = await soul_birth(name="McpTestSoul", archetype="The Tester")
        birth_data = json.loads(birth_json)
        result.checks.append(
            CheckResult(
                "mcp_soul_birth",
                birth_data.get("status") == "born" and birth_data.get("name") == "McpTestSoul",
                f"response={birth_data}",
            )
        )

        # soul_observe
        observe_json = await soul_observe(
            user_input="I use Python for data science",
            agent_output="Python is excellent for data science!",
        )
        observe_data = json.loads(observe_json)
        result.checks.append(
            CheckResult(
                "mcp_soul_observe",
                observe_data.get("status") == "observed",
                f"response={observe_data}",
            )
        )

        # soul_remember
        remember_json = await soul_remember(
            content="User's favorite IDE is VSCode",
            importance=7,
            memory_type="semantic",
        )
        remember_data = json.loads(remember_json)
        result.checks.append(
            CheckResult(
                "mcp_soul_remember",
                bool(remember_data.get("memory_id")),
                f"response={remember_data}",
            )
        )

        # soul_recall
        recall_json = await soul_recall(query="VSCode IDE", limit=5)
        recall_data = json.loads(recall_json)
        found = any(
            "VSCode" in m.get("content", "") or "vscode" in m.get("content", "").lower()
            for m in recall_data.get("memories", [])
        )
        result.checks.append(
            CheckResult(
                "mcp_soul_recall",
                found,
                f"count={recall_data.get('count')}, found_vscode={found}",
            )
        )

        # soul_state
        state_json = await soul_state()
        state_data = json.loads(state_json)
        result.checks.append(
            CheckResult(
                "mcp_soul_state",
                "mood" in state_data and "energy" in state_data,
                f"response={state_data}",
            )
        )

        # soul_feel
        feel_json = await soul_feel(mood="excited", energy=10.0)
        feel_data = json.loads(feel_json)
        result.checks.append(
            CheckResult(
                "mcp_soul_feel",
                feel_data.get("mood") == "excited",
                f"response={feel_data}",
            )
        )

        # soul_prompt
        prompt_text = await soul_prompt()
        result.checks.append(
            CheckResult(
                "mcp_soul_prompt",
                len(prompt_text) > 50 and "McpTestSoul" in prompt_text,
                f"prompt_length={len(prompt_text)}",
            )
        )

        # Cleanup global state
        mcp_module._soul = None
        mcp_module._soul_path = None

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    return result


# ---------------------------------------------------------------------------
# Scenario: Paw bridge simulation (SoulBridge + SoulBootstrapProvider patterns)
# ---------------------------------------------------------------------------


async def scenario_paw_bridge_simulation() -> ScenarioResult:
    """Simulate what PocketPaw's SoulBridge and SoulBootstrapProvider do,
    using the soul-protocol API directly (no pocketpaw dependency required)."""
    result = ScenarioResult(name="paw_bridge_simulation")
    t0 = time.perf_counter()

    try:
        soul = await Soul.birth(
            "PawCompanion",
            archetype="The Coding Partner",
            values=["helpfulness", "reliability"],
            ocean={"openness": 0.7, "conscientiousness": 0.85},
        )

        # Simulate SoulBridge.observe() — wraps soul.observe(Interaction(...))
        bridge_interactions = [
            ("How do I set up a virtual environment?", "Use python -m venv .venv to create one."),
            ("I prefer using uv for package management", "uv is fast and modern. Good choice!"),
            (
                "My project is a REST API for managing tasks",
                "A task management API is a great project to learn with.",
            ),
        ]
        for user_msg, agent_msg in bridge_interactions:
            await soul.observe(
                Interaction(
                    user_input=user_msg,
                    agent_output=agent_msg,
                )
            )

        result.checks.append(
            CheckResult(
                "bridge_observe",
                True,
                f"observed {len(bridge_interactions)} interactions",
            )
        )

        # Simulate SoulBridge.recall() — returns [m.content for m in soul.recall(...)]
        memories = await soul.recall("virtual environment", limit=5)
        content_strings = [m.content for m in memories]
        found = any("venv" in c.lower() or "virtual" in c.lower() for c in content_strings)
        result.checks.append(
            CheckResult(
                "bridge_recall",
                found,
                f"content_count={len(content_strings)}, found_venv={found}",
            )
        )

        # Simulate SoulBootstrapProvider.get_context() — builds context from soul state
        system_prompt = soul.to_system_prompt()
        state = soul.state
        mood_hint = f"Current mood: {state.mood}" if hasattr(state, "mood") else ""
        energy_hint = f"Energy: {state.energy}" if hasattr(state, "energy") else ""

        knowledge: list[str] = []
        if soul.self_model:
            images = soul.self_model.get_active_self_images(limit=5)
            for img in images:
                knowledge.append(f"[{img.domain}] confidence={img.confidence}")

        # Build a context dict like BootstrapContext
        context = {
            "name": soul.name,
            "identity": system_prompt,
            "soul": "I am a persistent AI companion powered by soul-protocol.",
            "style": "; ".join([s for s in [mood_hint, energy_hint] if s])
            or "Helpful and attentive.",
            "knowledge": knowledge,
        }

        result.checks.append(
            CheckResult(
                "bootstrap_context",
                context["name"] == "PawCompanion" and len(context["identity"]) > 50,
                f"name={context['name']}, identity_len={len(context['identity'])}, "
                f"knowledge_count={len(context['knowledge'])}",
            )
        )

        # Simulate heuristic_scan — store project facts
        facts = [
            "Project uses Python 3.12 with FastAPI",
            "Build tool: hatchling via pyproject.toml",
            "Top-level directories: src, tests, scripts",
        ]
        for fact in facts:
            await soul.remember(fact, importance=8)

        # Verify scan facts are recallable
        scan_results = await soul.recall("pyproject.toml build tool")
        found_build = any(
            "hatchling" in r.content.lower() or "pyproject" in r.content.lower()
            for r in scan_results
        )
        result.checks.append(
            CheckResult(
                "scan_facts_stored",
                found_build,
                f"found={len(scan_results)} results, build_match={found_build}",
            )
        )

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    return result


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def main():
    console.print(
        Panel(
            "[bold]Soul Protocol — Paw Integration E2E Tests[/bold]\n"
            "Simulates PocketPaw's usage patterns against the soul-protocol API.",
            box=box.DOUBLE,
        )
    )

    scenarios = [
        scenario_full_lifecycle,
        scenario_core_memory_editing,
        scenario_state_management,
        scenario_mcp_tools,
        scenario_paw_bridge_simulation,
    ]

    all_results: list[ScenarioResult] = []
    for scenario_fn in scenarios:
        name = scenario_fn.__name__.replace("scenario_", "")
        console.print(f"\n[bold cyan]Running:[/bold cyan] {name}...")
        result = await scenario_fn()
        all_results.append(result)

        # Show inline results
        status = "[bold green]PASS[/bold green]" if result.passed else "[bold red]FAIL[/bold red]"
        console.print(
            f"  {status} ({result.pass_count}/{len(result.checks)} checks, "
            f"{result.elapsed_ms:.0f}ms)"
        )
        if result.error:
            console.print(f"  [red]Error: {result.error[:200]}[/red]")
        for check in result.checks:
            icon = "[green]OK[/green]" if check.passed else "[red]FAIL[/red]"
            console.print(f"    {icon} {check.name}: {check.detail[:120]}")

    # Summary table
    console.print()
    table = Table(title="Paw Integration E2E Summary", box=box.ROUNDED)
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
        console.print("[bold green]All E2E integration tests passed.[/bold green]")
    else:
        console.print(f"[bold red]{total_fail} checks failed.[/bold red]")

    # Write results JSON
    output = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "all_passed": all_passed,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "scenarios": [
            {
                "name": r.name,
                "passed": r.passed,
                "pass_count": r.pass_count,
                "fail_count": r.fail_count,
                "elapsed_ms": round(r.elapsed_ms, 1),
                "error": r.error,
                "checks": [
                    {
                        "name": c.name,
                        "passed": c.passed,
                        "detail": c.detail,
                    }
                    for c in r.checks
                ],
            }
            for r in all_results
        ],
    }
    results_path = RESULTS_DIR / "e2e_paw_integration.json"
    results_path.write_text(json.dumps(output, indent=2))
    console.print(f"\nResults written to: {results_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
