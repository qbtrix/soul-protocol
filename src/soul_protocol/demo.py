# demo.py — Interactive Rich TUI demo for Soul Protocol.
# Rewritten: 2026-03-13 — 5-act step-by-step walkthrough with Rich panels,
#   tables, syntax highlighting, OCEAN bar charts, and "Press Enter" pauses.
#   Designed for GIF recording (README/launch). No LLM or API keys needed.
#   Set SOUL_DEMO_NO_PAUSE=1 to skip pauses (for CI/testing).
# Run: python -m soul_protocol

"""
Soul Protocol Demo — Watch an AI soul remember, feel, and grow.

No LLM required. No API keys. Just the psychology pipeline doing its thing.

Run it:
    python -m soul_protocol
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

# ── Rich dependency check ─────────────────────────────────────────────────────

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ── Configuration ─────────────────────────────────────────────────────────────

IS_TTY = sys.stdout.isatty()


def _no_pause() -> bool:
    """Check at call time so monkeypatch/env changes take effect."""
    return os.environ.get("SOUL_DEMO_NO_PAUSE", "0") == "1"


def _make_console() -> Console:
    """Create a console, disabling markup/color when not a TTY."""
    if not IS_TTY:
        return Console(force_terminal=False, no_color=True, highlight=False)
    return Console()


# ── Somatic emoji map ─────────────────────────────────────────────────────────

SOMATIC_EMOJI: dict[str, str] = {
    "neutral": "😐",
    "joy": "😊",
    "curiosity": "🧐",
    "interest": "🤔",
    "excitement": "🎉",
    "stress": "😰",
    "concern": "😟",
    "distress": "😣",
    "sadness": "😢",
    "empathy": "💛",
    "gratitude": "🙏",
    "relief": "😌",
    "warmth": "🤗",
    "trust": "🤝",
    "surprise": "😲",
    "anxiety": "😧",
}


def _emoji_for(label: str) -> str:
    return SOMATIC_EMOJI.get(label.lower(), "💭")


# ── Conversations ─────────────────────────────────────────────────────────────

CONVERSATIONS = [
    {
        "label": "Casual intro",
        "user": "Hey Aria, I'm Marcus. I'm a backend engineer at a startup in Austin.",
        "agent": "Nice to meet you, Marcus! Austin's a great city for startups. What are you working on?",
    },
    {
        "label": "Technical",
        "user": "We're building a real-time analytics platform. I mostly write Python and Go.",
        "agent": "That's a solid stack for real-time work. Python for the data layer, Go for the hot path?",
    },
    {
        "label": "Emotional",
        "user": "Exactly! But honestly, I've been feeling overwhelmed. We just lost two engineers and I'm carrying the whole backend alone.",
        "agent": "That sounds really tough, carrying a whole backend solo after losing teammates. That kind of pressure wears on you. How are you holding up?",
    },
    {
        "label": "Breakthrough",
        "user": "Not great. I haven't taken a day off in three months. My partner keeps saying I need to slow down.",
        "agent": "Three months without a break while carrying a team's worth of work — your partner is right to worry. You matter more than the sprint board.",
    },
    {
        "label": "Reflection",
        "user": "Thanks, that actually helps to hear. Oh, and I'm allergic to shellfish, so don't ever suggest a seafood restaurant.",
        "agent": "Noted — no shellfish, ever. And seriously, Marcus, consider taking even one day. You've earned it ten times over.",
    },
]


# ── OCEAN bar helper ──────────────────────────────────────────────────────────


def _ocean_bars(console: Console, personality) -> None:
    """Print OCEAN personality as horizontal bar chart."""
    traits = [
        ("Openness", personality.openness),
        ("Conscientiousness", personality.conscientiousness),
        ("Extraversion", personality.extraversion),
        ("Agreeableness", personality.agreeableness),
        ("Neuroticism", personality.neuroticism),
    ]
    for name, val in traits:
        bar_width = 30
        filled = int(val * bar_width)
        empty = bar_width - filled
        bar = f"[bold green]{'█' * filled}[/][dim]{'░' * empty}[/]"
        label = f"  {name:<20s}"
        console.print(f"{label} {bar} [bold]{val:.2f}[/]")


# ── Pause helper ──────────────────────────────────────────────────────────────


def _pause(console: Console) -> None:
    """Wait for Enter key unless pauses are disabled."""
    if _no_pause() or not IS_TTY:
        return
    console.print()
    console.input("[dim]  Press Enter to continue...[/]")


# ── Main demo ─────────────────────────────────────────────────────────────────


async def run_demo() -> None:
    if not HAS_RICH:
        print(
            "Rich library required for the interactive demo.\n"
            "Install it with: pip install soul-protocol[engine]"
        )
        sys.exit(1)

    from soul_protocol import Interaction, Soul

    console = _make_console()

    # ── Title ─────────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            "[bold]Soul Protocol[/bold]\n"
            "[dim]Portable AI companion identity — memory, personality, feelings.[/dim]\n\n"
            "No LLM needed. No API keys. Just psychology-informed memory.",
            title="[bold cyan]~ Digital Soul Protocol ~[/]",
            border_style="cyan",
            padding=(1, 4),
        )
    )
    _pause(console)

    # ══════════════════════════════════════════════════════════════════════
    # ACT 1: Birth
    # ══════════════════════════════════════════════════════════════════════

    console.print()
    console.print(
        Panel(
            "[bold]Act 1: Birth[/]  [dim]— Creating a soul from scratch[/]", border_style="yellow"
        )
    )
    console.print()

    code = """\
soul = await Soul.birth(
    name="Aria",
    archetype="The Curious Companion",
    values=["empathy", "curiosity", "honesty"],
    ocean={
        "openness": 0.9,
        "conscientiousness": 0.7,
        "extraversion": 0.6,
        "agreeableness": 0.85,
        "neuroticism": 0.25,
    },
    communication={"warmth": "high", "verbosity": "moderate", "humor_style": "dry"},
    persona="I'm Aria. I pay attention to what matters to people.",
)"""

    console.print(Syntax(code, "python", theme="monokai", line_numbers=False, padding=1))
    console.print()

    soul = await Soul.birth(
        name="Aria",
        archetype="The Curious Companion",
        values=["empathy", "curiosity", "honesty"],
        ocean={
            "openness": 0.9,
            "conscientiousness": 0.7,
            "extraversion": 0.6,
            "agreeableness": 0.85,
            "neuroticism": 0.25,
        },
        communication={"warmth": "high", "verbosity": "moderate", "humor_style": "dry"},
        persona="I'm Aria. I pay attention to what matters to people.",
    )

    # Show result
    result_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    result_table.add_column("Key", style="bold")
    result_table.add_column("Value")
    result_table.add_row("Name", soul.name)
    result_table.add_row("Archetype", soul._identity.archetype or "—")
    result_table.add_row("Values", ", ".join(soul._identity.core_values))
    result_table.add_row(
        "Communication",
        f"warmth={soul.dna.communication.warmth}, verbosity={soul.dna.communication.verbosity}, humor={soul.dna.communication.humor_style}",
    )
    result_table.add_row("Bond strength", f"{soul.bond.bond_strength:.0f}")
    console.print(result_table)

    console.print()
    console.print("  [bold]OCEAN Personality Profile[/]")
    _ocean_bars(console, soul.dna.personality)

    _pause(console)

    # ══════════════════════════════════════════════════════════════════════
    # ACT 2: Experience
    # ══════════════════════════════════════════════════════════════════════

    console.print()
    console.print(
        Panel(
            "[bold]Act 2: Experience[/]  [dim]— 5 conversations through the psychology pipeline[/]",
            border_style="yellow",
        )
    )
    console.print()

    initial_bond = soul.bond.bond_strength

    for i, conv in enumerate(CONVERSATIONS, 1):
        # Get pre-observation episodic count to compute delta
        pre_episodic = len(soul._memory._episodic._memories)

        # Process through pipeline — access memory manager for pipeline details
        result = await soul._memory.observe(
            Interaction(
                user_input=conv["user"],
                agent_output=conv["agent"],
            )
        )

        # Do the remaining Soul.observe steps (bond, state, graph, evolution)
        somatic = result.get("somatic")
        if somatic and somatic.valence >= 0:
            soul._identity.bond.strengthen(amount=1.0 + somatic.valence)
        else:
            soul._identity.bond.strengthen(amount=0.5)
        soul._state.on_interaction(
            Interaction(user_input=conv["user"], agent_output=conv["agent"]),
            somatic=somatic,
        )

        # Build display
        post_episodic = len(soul._memory._episodic._memories)
        stored_episodic = post_episodic - pre_episodic
        facts = result.get("facts", [])

        conv_panel_lines = []
        conv_panel_lines.append(
            f"[bold blue]User:[/] {conv['user'][:100]}{'...' if len(conv['user']) > 100 else ''}"
        )
        conv_panel_lines.append(
            f"[bold green]Aria:[/] {conv['agent'][:100]}{'...' if len(conv['agent']) > 100 else ''}"
        )
        conv_panel_lines.append("")

        # Somatic marker
        if somatic:
            emoji = _emoji_for(somatic.label)
            conv_panel_lines.append(
                f"  {emoji}  [bold]Somatic marker:[/] {somatic.label}  "
                f"[dim](valence={somatic.valence:+.2f}, arousal={somatic.arousal:.2f})[/]"
            )

        # Significance gate
        sig = result.get("significance", 0)
        passed = result.get("is_significant", False)
        gate_icon = "[bold green]PASSED[/]" if passed else "[dim]filtered[/]"
        conv_panel_lines.append(
            f"  🚪 [bold]Significance gate:[/] {gate_icon}  [dim](score={sig:.2f})[/]"
        )

        # Memories stored
        mem_parts = []
        if stored_episodic > 0:
            mem_parts.append(f"{stored_episodic} episodic")
        if facts:
            mem_parts.append(f"{len(facts)} facts")
        if mem_parts:
            conv_panel_lines.append(f"  💾 [bold]Stored:[/] {', '.join(mem_parts)}")
        else:
            conv_panel_lines.append("  💾 [bold]Stored:[/] [dim]nothing new[/]")

        console.print(
            Panel(
                "\n".join(conv_panel_lines),
                title=f"[bold]#{i} {conv['label']}[/]",
                border_style="blue" if i <= 2 else ("red" if i <= 4 else "green"),
                padding=(0, 2),
            )
        )

    # Show bond growth
    console.print()
    final_bond = soul.bond.bond_strength
    console.print(
        f"  [bold]Bond strength:[/] {initial_bond:.0f} → [bold green]{final_bond:.1f}[/]  [dim](+{final_bond - initial_bond:.1f} from 5 interactions)[/]"
    )

    _pause(console)

    # ══════════════════════════════════════════════════════════════════════
    # ACT 3: Memory & Recall
    # ══════════════════════════════════════════════════════════════════════

    console.print()
    console.print(
        Panel(
            "[bold]Act 3: Memory & Recall[/]  [dim]— What did the soul actually store?[/]",
            border_style="yellow",
        )
    )
    console.print()

    # Memory stats
    episodic_count = len(soul._memory._episodic._memories)
    semantic_count = len(soul._memory._semantic._facts)
    procedural_count = len(soul._memory._procedural._procedures)

    stats_table = Table(title="Memory Stats", box=box.ROUNDED, border_style="magenta")
    stats_table.add_column("Tier", style="bold")
    stats_table.add_column("Count", justify="right")
    stats_table.add_column("Description", style="dim")
    stats_table.add_row("Episodic", str(episodic_count), "Significant experiences (LIDA gate)")
    stats_table.add_row("Semantic", str(semantic_count), "Extracted facts")
    stats_table.add_row("Procedural", str(procedural_count), "Learned procedures")
    stats_table.add_row("[bold]Total[/]", f"[bold]{soul.memory_count}[/]", "")
    console.print(stats_table)
    console.print()

    # Recall queries
    queries = [
        "What does Marcus do for work?",
        "shellfish allergy",
        "feeling overwhelmed stressed",
    ]

    recall_table = Table(title="Recall Queries", box=box.ROUNDED, border_style="cyan")
    recall_table.add_column("Query", style="bold")
    recall_table.add_column("Type", style="dim")
    recall_table.add_column("Result")

    for q in queries:
        results = await soul.recall(q, limit=3)
        if results:
            for j, r in enumerate(results[:2]):
                query_col = q if j == 0 else ""
                recall_table.add_row(query_col, r.type, r.content[:80])
        else:
            recall_table.add_row(q, "—", "[dim](no results)[/]")

    console.print(recall_table)
    console.print()

    # Self-model
    images = soul.self_model.get_active_self_images()
    if images:
        console.print("  [bold]Self-Model Domains (Klein)[/]")
        for img in images[:5]:
            bar_width = 20
            filled = int(img.confidence * bar_width)
            bar = f"[bold magenta]{'█' * filled}[/][dim]{'░' * (bar_width - filled)}[/]"
            console.print(f"    {img.domain:<25s} {bar} {img.confidence:.0%}")
    else:
        console.print("  [dim]Self-model still forming (needs more interactions)[/]")

    _pause(console)

    # ══════════════════════════════════════════════════════════════════════
    # ACT 4: Portability
    # ══════════════════════════════════════════════════════════════════════

    console.print()
    console.print(
        Panel(
            "[bold]Act 4: Portability[/]  [dim]— Export to .soul file, reload, verify[/]",
            border_style="yellow",
        )
    )
    console.print()

    with tempfile.TemporaryDirectory() as tmp:
        soul_path = os.path.join(tmp, "aria.soul")

        # Export
        await soul.export(soul_path)
        file_size = os.path.getsize(soul_path)

        console.print(f"  [bold]Exported:[/] aria.soul  [dim]({file_size:,} bytes)[/]")
        console.print()

        # Import
        reloaded = await Soul.awaken(soul_path)

        # Comparison table
        cmp_table = Table(title="Original vs. Reloaded", box=box.ROUNDED, border_style="green")
        cmp_table.add_column("Property", style="bold")
        cmp_table.add_column("Original")
        cmp_table.add_column("Reloaded")
        cmp_table.add_column("Match", justify="center")

        checks = [
            ("Name", soul.name, reloaded.name),
            ("Memories", str(soul.memory_count), str(reloaded.memory_count)),
            (
                "Bond strength",
                f"{soul.bond.bond_strength:.1f}",
                f"{reloaded.bond.bond_strength:.1f}",
            ),
            (
                "Openness",
                f"{soul.dna.personality.openness:.2f}",
                f"{reloaded.dna.personality.openness:.2f}",
            ),
            (
                "Agreeableness",
                f"{soul.dna.personality.agreeableness:.2f}",
                f"{reloaded.dna.personality.agreeableness:.2f}",
            ),
        ]

        for label, orig, rel in checks:
            match = "[bold green]✓[/]" if orig == rel else "[bold red]✗[/]"
            cmp_table.add_row(label, orig, rel, match)

        console.print(cmp_table)

    _pause(console)

    # ══════════════════════════════════════════════════════════════════════
    # ACT 5: System Prompt
    # ══════════════════════════════════════════════════════════════════════

    console.print()
    console.print(
        Panel(
            "[bold]Act 5: System Prompt[/]  [dim]— What an LLM would receive[/]",
            border_style="yellow",
        )
    )
    console.print()

    prompt = soul.system_prompt
    # Truncate for display if very long
    max_display = 1200
    display_prompt = (
        prompt if len(prompt) <= max_display else prompt[:max_display] + "\n\n... (truncated)"
    )

    console.print(
        Syntax(
            display_prompt,
            "markdown",
            theme="monokai",
            line_numbers=False,
            padding=1,
            word_wrap=True,
        )
    )

    console.print()

    # ── Final summary ─────────────────────────────────────────────────────

    summary_lines = [
        "[bold]What just happened:[/]\n",
        "  • 5 interactions processed through the psychology pipeline",
        "  • Somatic markers tagged emotional context [dim](Damasio)[/]",
        "  • Significance gate filtered what's worth remembering [dim](LIDA)[/]",
        "  • Facts extracted and stored in semantic memory",
        f"  • Bond strength grew from {initial_bond:.0f} → {final_bond:.1f}",
        "  • Self-model started forming identity domains [dim](Klein)[/]",
        "  • Everything saved to a portable .soul file and reloaded",
        "  • [bold]Zero LLM calls. Zero API keys. Zero cost.[/]\n",
        "[dim]https://github.com/qbtrix/soul-protocol[/]",
    ]

    console.print(
        Panel(
            "\n".join(summary_lines),
            title="[bold cyan]~ That's Soul Protocol ~[/]",
            border_style="cyan",
            padding=(1, 3),
        )
    )
    console.print()


def main() -> None:
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
