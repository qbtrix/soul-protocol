# cli/diff.py — `soul diff <left> <right>` structured comparison (#191).
# Created: feat/soul-diff-cli — Renders a SoulDiff (from runtime/diff.py) into
#   text, json, or markdown. Default output is a Rich panel walking each diff
#   section in order; --format json emits the full SoulDiff dict; --format
#   markdown emits a paste-ready markdown table for PR bodies.
#
# Sections are skipped when empty so a no-op diff stays terse. --section <name>
# narrows to one section. --include-superseded adds the supersession chain
# explicitly. --summary-only collapses to per-section counts.
#
# Schema mismatch raises SchemaMismatchError → exit 1 with a clean message.

from __future__ import annotations

import asyncio
import json as _json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from soul_protocol.runtime.diff import (
    BondDiff,
    CoreMemoryDiff,
    EvolutionDiff,
    IdentityDiff,
    MemoryDiff,
    OceanDiff,
    SchemaMismatchError,
    SelfModelDiff,
    SkillDiff,
    SoulDiff,
    StateDiff,
    TrustChainDiff,
    diff_souls,
)

console = Console()


SECTION_ALIASES: dict[str, str] = {
    "identity": "identity",
    "dna": "ocean",
    "ocean": "ocean",
    "state": "state",
    "core": "core_memory",
    "core-memory": "core_memory",
    "core_memory": "core_memory",
    "memory": "memory",
    "memories": "memory",
    "bond": "bond",
    "bonds": "bond",
    "skills": "skills",
    "trust": "trust_chain",
    "trust-chain": "trust_chain",
    "trust_chain": "trust_chain",
    "self": "self_model",
    "self-model": "self_model",
    "self_model": "self_model",
    "evolution": "evolution",
}
"""User-facing section names → SoulDiff attribute names. Accepts both
hyphenated and underscored forms so `--section trust-chain` and
`--section trust_chain` both work."""


@click.command("diff")
@click.argument("left", type=click.Path(exists=True, dir_okay=True, path_type=Path))
@click.argument("right", type=click.Path(exists=True, dir_okay=True, path_type=Path))
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json", "markdown"], case_sensitive=False),
    default="text",
    help="Output format. Text is the default Rich panel; json emits a SoulDiff dict; "
    "markdown emits a paste-ready table.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Shortcut for --format json. Equivalent to --format json.",
)
@click.option(
    "--section",
    "section",
    default=None,
    help="Limit output to one section. Accepts: identity, ocean (or dna), state, "
    "core (or core-memory), memory, bond, skills, trust (or trust-chain), self "
    "(or self-model), evolution.",
)
@click.option(
    "--include-superseded",
    "include_superseded",
    is_flag=True,
    default=False,
    help="Show the supersession chain explicitly. By default, superseded memories "
    "are filtered out of the removed-memory diff since they still live in the file.",
)
@click.option(
    "--summary-only",
    "summary_only",
    is_flag=True,
    default=False,
    help="Print per-section counts instead of the full diff.",
)
def diff_cmd(
    left: Path,
    right: Path,
    fmt: str,
    as_json: bool,
    section: str | None,
    include_superseded: bool,
    summary_only: bool,
) -> None:
    """Compare two soul files and print a structured diff.

    \b
    Examples:
      soul diff aria.soul aria-after-week.soul
      soul diff aria.soul aria-after-week.soul --json
      soul diff aria.soul aria-after-week.soul --section memory
      soul diff aria.soul aria-after-week.soul --include-superseded
      soul diff aria.soul aria-after-week.soul --format markdown

    Sections covered: identity, OCEAN/DNA, state, core memory, memories
    (per layer + per domain), bond, skills, trust chain, self-model,
    evolution. Each section is omitted from text output when there are
    no changes; --json always emits the full structure.

    Raises a clean error and exits 1 when the two files have different
    schema versions — run `soul migrate <path>` on the older soul first.

    Read-only: never modifies either input.
    """
    if as_json:
        fmt = "json"

    if section:
        normalized = section.lower().strip()
        if normalized not in SECTION_ALIASES:
            click.echo(
                f"error: unknown section '{section}'. Known: "
                f"{', '.join(sorted(set(SECTION_ALIASES.values())))}.",
                err=True,
            )
            sys.exit(2)
        section_attr: str | None = SECTION_ALIASES[normalized]
    else:
        section_attr = None

    diff = asyncio.run(_load_and_diff(left, right, include_superseded=include_superseded))

    if fmt == "json":
        _render_json(diff, section_attr=section_attr, summary_only=summary_only)
        return

    if fmt == "markdown":
        _render_markdown(diff, section_attr=section_attr, summary_only=summary_only)
        return

    _render_text(diff, section_attr=section_attr, summary_only=summary_only)


async def _load_and_diff(
    left_path: Path, right_path: Path, *, include_superseded: bool
) -> SoulDiff:
    """Load both souls and produce the diff. Errors out cleanly on schema
    mismatch so the CLI never exits with a stack trace."""
    from soul_protocol.runtime.soul import Soul

    try:
        left = await Soul.awaken(str(left_path))
        right = await Soul.awaken(str(right_path))
    except Exception as exc:
        click.echo(f"error: failed to load soul — {exc}", err=True)
        sys.exit(1)

    try:
        return diff_souls(left, right, include_superseded=include_superseded)
    except SchemaMismatchError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# JSON renderer
# ---------------------------------------------------------------------------


def _render_json(diff: SoulDiff, *, section_attr: str | None, summary_only: bool) -> None:
    """Emit a JSON payload — full diff, single section, or summary counts."""
    if summary_only:
        click.echo(_json.dumps(diff.summary(), indent=2))
        return
    if section_attr:
        section = getattr(diff, section_attr)
        click.echo(_json.dumps(section.model_dump(mode="json"), indent=2, default=str))
        return
    click.echo(_json.dumps(diff.model_dump(mode="json"), indent=2, default=str))


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------


def _render_markdown(diff: SoulDiff, *, section_attr: str | None, summary_only: bool) -> None:
    """Emit a markdown summary plus per-section tables for PR bodies."""
    lines: list[str] = []
    lines.append(f"## Soul diff: `{diff.left_name}` → `{diff.right_name}`")
    lines.append("")

    if diff.empty:
        lines.append("_No changes detected._")
        click.echo("\n".join(lines))
        return

    summary = diff.summary()
    if summary_only:
        lines.append("| Section | Count |")
        lines.append("|---------|-------|")
        for key, value in summary.items():
            if value:
                lines.append(f"| {key.replace('_', ' ')} | {value} |")
        click.echo("\n".join(lines))
        return

    sections = (
        ("identity", diff.identity, _markdown_identity),
        ("ocean", diff.ocean, _markdown_ocean),
        ("state", diff.state, _markdown_state),
        ("core_memory", diff.core_memory, _markdown_core_memory),
        ("memory", diff.memory, _markdown_memory),
        ("bond", diff.bond, _markdown_bond),
        ("skills", diff.skills, _markdown_skills),
        ("trust_chain", diff.trust_chain, _markdown_trust_chain),
        ("self_model", diff.self_model, _markdown_self_model),
        ("evolution", diff.evolution, _markdown_evolution),
    )

    for name, section, renderer in sections:
        if section_attr and section_attr != name:
            continue
        if section.empty:
            continue
        lines.append(f"### {name.replace('_', ' ').title()}")
        lines.append("")
        lines.extend(renderer(section))
        lines.append("")

    click.echo("\n".join(lines).rstrip())


def _markdown_identity(diff: IdentityDiff) -> list[str]:
    out = ["| Field | Before | After |", "|-------|--------|-------|"]
    for change in diff.changes:
        out.append(f"| {change.field} | `{change.before}` | `{change.after}` |")
    return out


def _markdown_ocean(diff: OceanDiff) -> list[str]:
    out: list[str] = []
    if diff.trait_deltas:
        out.append("OCEAN trait deltas:")
        out.append("")
        out.append("| Trait | Delta |")
        out.append("|-------|-------|")
        for trait, delta in diff.trait_deltas.items():
            arrow = "↑" if delta > 0 else "↓"
            out.append(f"| {trait} | {arrow} {abs(delta):.3f} |")
    if diff.communication_changes or diff.biorhythm_changes:
        out.append("")
        out.append("| Field | Before | After |")
        out.append("|-------|--------|-------|")
        for change in diff.communication_changes + diff.biorhythm_changes:
            out.append(f"| {change.field} | `{change.before}` | `{change.after}` |")
    return out


def _markdown_state(diff: StateDiff) -> list[str]:
    out = ["| Field | Before | After |", "|-------|--------|-------|"]
    for change in diff.changes:
        out.append(f"| {change.field} | `{change.before}` | `{change.after}` |")
    return out


def _markdown_core_memory(diff: CoreMemoryDiff) -> list[str]:
    out: list[str] = []
    if diff.persona_changed:
        out.append(f"- persona: {len(diff.persona_before)} chars → {len(diff.persona_after)} chars")
    if diff.human_changed:
        out.append(f"- human: {len(diff.human_before)} chars → {len(diff.human_after)} chars")
    return out


def _markdown_memory(diff: MemoryDiff) -> list[str]:
    out: list[str] = []
    counts_changed = [c for c in diff.layer_counts if c.before != c.after]
    if counts_changed:
        out.append("Layer counts:")
        out.append("")
        out.append("| Layer | Before | After |")
        out.append("|-------|--------|-------|")
        for c in counts_changed:
            before_total = sum(c.before.values())
            after_total = sum(c.after.values())
            out.append(f"| {c.layer} | {before_total} | {after_total} |")
        out.append("")

    if diff.added:
        out.append(f"**Added ({len(diff.added)}):**")
        out.append("")
        for entry in diff.added:
            out.append(
                f"- `+` `{entry.layer}` id=`{entry.id}` imp={entry.importance}: "
                f"{entry.truncated_content!r}"
            )
        out.append("")

    if diff.removed:
        out.append(f"**Removed ({len(diff.removed)}):**")
        out.append("")
        for entry in diff.removed:
            out.append(
                f"- `-` `{entry.layer}` id=`{entry.id}` imp={entry.importance}: "
                f"{entry.truncated_content!r}"
            )
        out.append("")

    if diff.modified:
        out.append(f"**Modified ({len(diff.modified)}):**")
        out.append("")
        for change in diff.modified:
            fc = ", ".join(f"{c.field}: {c.before!r} → {c.after!r}" for c in change.field_changes)
            out.append(f"- `~` `{change.layer}` id=`{change.id}`: {fc}")
        out.append("")

    if diff.superseded:
        out.append(f"**Superseded chain ({len(diff.superseded)}):**")
        out.append("")
        for entry in diff.superseded:
            out.append(
                f"- `>` `{entry.layer}` id=`{entry.id}` superseded_by=`{entry.superseded_by}`: "
                f"{entry.truncated_content!r}"
            )
    return out


def _markdown_bond(diff: BondDiff) -> list[str]:
    out: list[str] = []
    if diff.changes:
        out.append("| User | Strength | Interactions |")
        out.append("|------|----------|--------------|")
        for change in diff.changes:
            label = change.user_id or "(default)"
            arrow = "↑" if change.strength_after > change.strength_before else "↓"
            out.append(
                f"| `{label}` | {change.strength_before:.1f} {arrow} {change.strength_after:.1f} | "
                f"{change.interaction_count_before} → {change.interaction_count_after} |"
            )
    if diff.added_users:
        out.append("")
        out.append(f"Added bonded users: {', '.join('`' + u + '`' for u in diff.added_users)}")
    if diff.removed_users:
        out.append("")
        out.append(f"Removed bonded users: {', '.join('`' + u + '`' for u in diff.removed_users)}")
    return out


def _markdown_skills(diff: SkillDiff) -> list[str]:
    out: list[str] = []
    if diff.added:
        out.append(f"**Added ({len(diff.added)}):**")
        for s in diff.added:
            out.append(f"- `+` `{s.name}` (level {s.level_after}, {s.xp_after} XP)")
        out.append("")
    if diff.removed:
        out.append(f"**Removed ({len(diff.removed)}):**")
        for s in diff.removed:
            out.append(f"- `-` `{s.name}` (was level {s.level_before}, {s.xp_before} XP)")
        out.append("")
    if diff.changed:
        out.append("**Changed:**")
        for s in diff.changed:
            level_text = (
                f"level {s.level_before} → {s.level_after}"
                if s.level_before != s.level_after
                else f"level {s.level_after}"
            )
            out.append(f"- `~` `{s.name}` ({level_text}, {s.xp_before} → {s.xp_after} XP)")
    return out


def _markdown_trust_chain(diff: TrustChainDiff) -> list[str]:
    out = [f"- entries: {diff.length_before} → {diff.length_after}"]
    if diff.new_actions:
        out.append(f"- new actions: {', '.join('`' + a + '`' for a in diff.new_actions)}")
    if diff.new_entries_sample:
        out.append("")
        out.append("Sample of new entries:")
        out.append("")
        out.append("| Seq | Action | Actor |")
        out.append("|-----|--------|-------|")
        for entry in diff.new_entries_sample:
            out.append(f"| {entry['seq']} | `{entry['action']}` | `{entry['actor_did']}` |")
    return out


def _markdown_self_model(diff: SelfModelDiff) -> list[str]:
    out: list[str] = []
    if diff.added_domains:
        out.append(f"Added domains: {', '.join('`' + d + '`' for d in diff.added_domains)}")
    if diff.removed_domains:
        out.append(f"Removed domains: {', '.join('`' + d + '`' for d in diff.removed_domains)}")
    if diff.changed:
        out.append("")
        out.append("| Domain | Confidence | Evidence |")
        out.append("|--------|------------|----------|")
        for c in diff.changed:
            arrow = "↑" if c.confidence_after > c.confidence_before else "↓"
            out.append(
                f"| `{c.domain}` | {c.confidence_before:.2f} {arrow} {c.confidence_after:.2f} "
                f"| {c.evidence_before} → {c.evidence_after} |"
            )
    return out


def _markdown_evolution(diff: EvolutionDiff) -> list[str]:
    out = []
    for mut in diff.new_mutations:
        out.append(
            f"- `~` `{mut.get('trait', '?')}`: `{mut.get('old_value')}` → `{mut.get('new_value')}` ({mut.get('reason', '')})"
        )
    return out


# ---------------------------------------------------------------------------
# Text (Rich) renderer
# ---------------------------------------------------------------------------


def _render_text(diff: SoulDiff, *, section_attr: str | None, summary_only: bool) -> None:
    """Render the diff as a Rich panel walking each section in order."""
    title = f"Soul diff: {diff.left_name} → {diff.right_name}"
    console.print(Panel(title, border_style="cyan", expand=False))

    if diff.empty:
        console.print("[dim]No changes detected.[/dim]")
        return

    if summary_only:
        _render_text_summary(diff, section_attr=section_attr)
        return

    sections = (
        ("identity", "Identity", diff.identity, _text_identity),
        ("ocean", "OCEAN / DNA", diff.ocean, _text_ocean),
        ("state", "State", diff.state, _text_state),
        ("core_memory", "Core memory", diff.core_memory, _text_core_memory),
        ("memory", "Memories", diff.memory, _text_memory),
        ("bond", "Bond", diff.bond, _text_bond),
        ("skills", "Skills", diff.skills, _text_skills),
        ("trust_chain", "Trust chain", diff.trust_chain, _text_trust_chain),
        ("self_model", "Self-model", diff.self_model, _text_self_model),
        ("evolution", "Evolution", diff.evolution, _text_evolution),
    )

    for attr, label, section, renderer in sections:
        if section_attr and section_attr != attr:
            continue
        if section.empty:
            continue
        console.print()
        console.print(f"[bold cyan]{label}[/bold cyan]")
        renderer(section)


def _render_text_summary(diff: SoulDiff, *, section_attr: str | None) -> None:
    summary = diff.summary()
    table = Table(border_style="dim", show_header=True)
    table.add_column("Section", style="cyan")
    table.add_column("Count", justify="right")
    for key, value in summary.items():
        if value:
            if section_attr and not key.startswith(section_attr):
                continue
            table.add_row(key.replace("_", " "), str(value))
    console.print(table)


def _text_identity(diff: IdentityDiff) -> None:
    table = Table(border_style="dim")
    table.add_column("Field", style="cyan")
    table.add_column("Before")
    table.add_column("After")
    for change in diff.changes:
        table.add_row(change.field, str(change.before), str(change.after))
    console.print(table)


def _text_ocean(diff: OceanDiff) -> None:
    if diff.trait_deltas:
        table = Table(border_style="dim", title="OCEAN trait deltas", title_style="dim")
        table.add_column("Trait", style="cyan")
        table.add_column("Delta", justify="right")
        for trait, delta in diff.trait_deltas.items():
            arrow = "↑" if delta > 0 else "↓"
            color = "green" if delta > 0 else "red"
            table.add_row(trait, f"[{color}]{arrow} {abs(delta):.3f}[/{color}]")
        console.print(table)
    if diff.communication_changes or diff.biorhythm_changes:
        table = Table(border_style="dim", title="DNA fields", title_style="dim")
        table.add_column("Field", style="cyan")
        table.add_column("Before")
        table.add_column("After")
        for change in diff.communication_changes + diff.biorhythm_changes:
            table.add_row(change.field, str(change.before), str(change.after))
        console.print(table)


def _text_state(diff: StateDiff) -> None:
    table = Table(border_style="dim")
    table.add_column("Field", style="cyan")
    table.add_column("Before")
    table.add_column("After")
    for change in diff.changes:
        table.add_row(change.field, str(change.before), str(change.after))
    console.print(table)


def _text_core_memory(diff: CoreMemoryDiff) -> None:
    if diff.persona_changed:
        console.print(
            f"  persona changed: {len(diff.persona_before)} → {len(diff.persona_after)} chars"
        )
    if diff.human_changed:
        console.print(f"  human changed: {len(diff.human_before)} → {len(diff.human_after)} chars")


def _text_memory(diff: MemoryDiff) -> None:
    counts_changed = [c for c in diff.layer_counts if c.before != c.after]
    if counts_changed:
        table = Table(border_style="dim", title="Layer counts", title_style="dim")
        table.add_column("Layer", style="cyan")
        table.add_column("Before", justify="right")
        table.add_column("After", justify="right")
        for c in counts_changed:
            table.add_row(c.layer, str(sum(c.before.values())), str(sum(c.after.values())))
        console.print(table)

    for entry in diff.added:
        console.print(
            f"  [green]+[/green] {entry.layer:<10} id={entry.id} imp={entry.importance}: "
            f"{entry.truncated_content!r}"
        )
    for entry in diff.removed:
        console.print(
            f"  [red]-[/red] {entry.layer:<10} id={entry.id} imp={entry.importance}: "
            f"{entry.truncated_content!r}"
        )
    for change in diff.modified:
        fc = ", ".join(f"{c.field} {c.before!r} → {c.after!r}" for c in change.field_changes)
        console.print(f"  [yellow]~[/yellow] {change.layer:<10} id={change.id}: {fc}")
    for entry in diff.superseded:
        console.print(
            f"  [magenta]>[/magenta] {entry.layer:<10} id={entry.id} "
            f"superseded_by={entry.superseded_by}: {entry.truncated_content!r}"
        )


def _text_bond(diff: BondDiff) -> None:
    table = Table(border_style="dim")
    table.add_column("User", style="cyan")
    table.add_column("Strength")
    table.add_column("Interactions", justify="right")
    for change in diff.changes:
        label = change.user_id or "(default)"
        arrow = "↑" if change.strength_after > change.strength_before else "↓"
        color = "green" if change.strength_after > change.strength_before else "red"
        table.add_row(
            label,
            f"{change.strength_before:.1f} [{color}]{arrow}[/{color}] {change.strength_after:.1f}",
            f"{change.interaction_count_before} → {change.interaction_count_after}",
        )
    if diff.changes:
        console.print(table)
    if diff.added_users:
        console.print(f"  [green]+[/green] new bonded users: {', '.join(diff.added_users)}")
    if diff.removed_users:
        console.print(f"  [red]-[/red] removed bonded users: {', '.join(diff.removed_users)}")


def _text_skills(diff: SkillDiff) -> None:
    for s in diff.added:
        console.print(f"  [green]+[/green] {s.name} (level {s.level_after}, {s.xp_after} XP)")
    for s in diff.removed:
        console.print(f"  [red]-[/red] {s.name} (was level {s.level_before}, {s.xp_before} XP)")
    for s in diff.changed:
        level_part = (
            f"L{s.level_before}→L{s.level_after}"
            if s.level_before != s.level_after
            else f"L{s.level_after}"
        )
        console.print(
            f"  [yellow]~[/yellow] {s.name} ({level_part}, {s.xp_before} → {s.xp_after} XP)"
        )


def _text_trust_chain(diff: TrustChainDiff) -> None:
    console.print(f"  entries: {diff.length_before} → {diff.length_after}")
    if diff.new_actions:
        console.print(f"  new actions: {', '.join(diff.new_actions)}")
    if diff.new_entries_sample:
        table = Table(border_style="dim", title="New entries", title_style="dim")
        table.add_column("Seq", justify="right", style="cyan")
        table.add_column("Action")
        table.add_column("Actor")
        for entry in diff.new_entries_sample:
            table.add_row(str(entry["seq"]), entry["action"], entry["actor_did"])
        console.print(table)


def _text_self_model(diff: SelfModelDiff) -> None:
    if diff.added_domains:
        console.print(f"  [green]+[/green] new domains: {', '.join(diff.added_domains)}")
    if diff.removed_domains:
        console.print(f"  [red]-[/red] removed domains: {', '.join(diff.removed_domains)}")
    for c in diff.changed:
        arrow = "↑" if c.confidence_after > c.confidence_before else "↓"
        color = "green" if c.confidence_after > c.confidence_before else "red"
        console.print(
            f"  [yellow]~[/yellow] {c.domain}: confidence "
            f"{c.confidence_before:.2f} [{color}]{arrow}[/{color}] {c.confidence_after:.2f} "
            f"(evidence {c.evidence_before} → {c.evidence_after})"
        )


def _text_evolution(diff: EvolutionDiff) -> None:
    for mut in diff.new_mutations:
        console.print(
            f"  [yellow]~[/yellow] {mut.get('trait', '?')}: "
            f"{mut.get('old_value')!r} → {mut.get('new_value')!r} "
            f"[dim]({mut.get('reason', '')})[/dim]"
        )
