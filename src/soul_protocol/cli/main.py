# cli/main.py — Click CLI for the Soul Protocol (37 commands)
# Updated: 2026-03-27 — Added --full and --json flags to `soul recall` for untruncated
#   and machine-readable output (v0.2.8).
# Updated: 2026-03-26 — Added 3 soul maintenance commands: health, cleanup, repair.
#   health: audit memory tiers, duplicates, orphan nodes, skills, bond sanity.
#   cleanup: remove duplicates, stale evals, orphan graph nodes, low-importance memories.
#   repair: reset energy/bond, rebuild graph, clear evals/skills/procedural.
# Updated: 2026-03-24 — Added 13 commands for full runtime/MCP feature parity:
#   observe, reflect, feel, prompt, forget, edit-core, evolve, evaluate, learn,
#   skills, bond, events, context. Total: 34 commands.
# Updated: 2026-03-23 — Added `soul import-soulspec`, `soul import-tavernai`,
#   `soul export-soulspec`, `soul export-tavernai` commands for cross-format
#   import/export (SoulSpec directories and TavernAI Character Card V2 JSON/PNG).
# Updated: 2026-03-23 — Added `soul export-a2a` and `soul import-a2a` commands
#   for A2A Agent Card ↔ Soul Protocol interop. Export generates Agent Card JSON
#   from a soul; import creates a soul from an Agent Card file.
# Updated: 2026-03-13 — Added --traits/-t compact OCEAN shorthand to `soul birth`.
# Updated: 2026-03-13 — Added `soul inject <target>` command for fast CLI-based
#   soul context injection into agent config files (claude-code, cursor, vscode,
#   windsurf, cline, continue). Idempotent with marker-based replacement.
# Updated: 2026-03-13 — Added --format option (dir/zip) to soul init.
# Updated: 2026-03-10 — Added `soul remember` and `soul recall` commands (issue #14).
# Updated: 2026-03-02 — Removed dashboard/open commands (replaced by rich TUI in inspect/status).
#   Enhanced `soul inspect` with OCEAN bars, memory stats, core memory, self-model panels.
#   Enhanced `soul status` with progress bars for energy/social battery.
#   v0.3.0 — Added --config/-c option, OCEAN trait flags, `soul init`.
#   v0.2.2 — Fixed version_option to read from package __version__.
# Created: 2026-02-22 — Commands: birth, inspect, status, export, migrate
# Updated: 2026-03-06 — eternal-status reads manifest; archive persists results to manifest

from __future__ import annotations

import asyncio
import builtins
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

import click
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def _safe_name(name: str) -> str:
    """Sanitize a soul name for use in file paths (no traversal)."""
    return Path(name.lower().replace(" ", "-")).name or "soul"


def _ocean_bar(label: str, value: float) -> Text:
    """Render a single OCEAN trait as a labeled bar."""
    pct = int(value * 100)
    filled = int(value * 20)
    bar = "█" * filled + "░" * (20 - filled)
    return Text.from_markup(f"  {label:<20s} [cyan]{bar}[/] {pct:>3d}%")


def _pct_color(value: float) -> str:
    """Pick color based on percentage value."""
    if value > 70:
        return "green"
    if value > 30:
        return "yellow"
    return "red"


@click.group()
@click.version_option(package_name="soul-protocol", prog_name="soul")
def cli():
    """Soul Protocol — Portable identity and memory for AI agents."""
    pass


@cli.command()
@click.argument("name", required=False)
@click.option("--archetype", "-a", help="Soul archetype (e.g. 'The Companion')")
@click.option(
    "--from-file", "-f", type=click.Path(exists=True), help="Create from soul.md/yaml/json"
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    help="Config YAML/JSON with full soul parameters",
)
@click.option("--openness", type=float, help="OCEAN openness (0.0-1.0)")
@click.option("--conscientiousness", type=float, help="OCEAN conscientiousness (0.0-1.0)")
@click.option("--extraversion", type=float, help="OCEAN extraversion (0.0-1.0)")
@click.option("--agreeableness", type=float, help="OCEAN agreeableness (0.0-1.0)")
@click.option("--neuroticism", type=float, help="OCEAN neuroticism (0.0-1.0)")
@click.option(
    "--traits", "-t", type=str,
    help='Compact OCEAN traits: "O:0.9,C:0.8,E:0.4,A:0.6,N:0.2"',
)
@click.option("--output", "-o", type=click.Path(), help="Output path for .soul file")
def birth(
    name,
    archetype,
    from_file,
    config_file,
    openness,
    conscientiousness,
    extraversion,
    agreeableness,
    neuroticism,
    traits,
    output,
):
    """Birth a new Soul.

    Create a soul with custom personality using OCEAN trait flags,
    a config file (--config), or an existing soul file (--from-file).

    \b
    Examples:
      soul birth "Aria" --openness 0.9 --neuroticism 0.2
      soul birth "Architect" -a systems-thinker -t "O:0.9,C:0.8,E:0.4,A:0.6,N:0.2"
    """

    # Parse --traits shorthand before entering async (avoids closure scope issues)
    _trait_keys = {
        "O": "openness", "C": "conscientiousness",
        "E": "extraversion", "A": "agreeableness", "N": "neuroticism",
    }
    ocean_flags = {
        "openness": openness, "conscientiousness": conscientiousness,
        "extraversion": extraversion, "agreeableness": agreeableness,
        "neuroticism": neuroticism,
    }
    if traits:
        for pair in traits.split(","):
            pair = pair.strip()
            if ":" not in pair:
                raise click.BadParameter(
                    f"Invalid trait format '{pair}'. Use 'O:0.9,C:0.8,...'",
                    param_hint="--traits",
                )
            key, val = pair.split(":", 1)
            key = key.strip().upper()
            if key not in _trait_keys:
                raise click.BadParameter(
                    f"Unknown trait '{key}'. Use O, C, E, A, or N.",
                    param_hint="--traits",
                )
            attr = _trait_keys[key]
            if ocean_flags[attr] is None:
                ocean_flags[attr] = float(val.strip())

    ocean = {k: v for k, v in ocean_flags.items() if v is not None}

    async def _birth():
        from soul_protocol.runtime.soul import Soul

        if config_file:
            soul = await Soul.birth_from_config(config_file)
            console.print(
                f"[green]Birthed[/green] [bold]{soul.name}[/bold] "
                f"from config {config_file} ({soul.did})"
            )
        elif from_file:
            soul = await Soul.awaken(from_file)
            console.print(f"[green]Birthed[/green] {soul.name} from {from_file}")
        else:
            if not name:
                name_input = click.prompt("What should your soul be called?")
            else:
                name_input = name

            archetype_input = archetype or "The Companion"

            soul = await Soul.birth(
                name=name_input,
                archetype=archetype_input,
                ocean=ocean or None,
            )
            console.print(f"[green]Birthed[/green] [bold]{soul.name}[/bold] ({soul.did})")

            if ocean:
                p = soul.dna.personality
                console.print(
                    f"[dim]OCEAN: O={p.openness:.1f} C={p.conscientiousness:.1f} "
                    f"E={p.extraversion:.1f} A={p.agreeableness:.1f} "
                    f"N={p.neuroticism:.1f}[/dim]"
                )

        out = output or f"./{_safe_name(soul.name)}.soul"
        await soul.export(out)
        console.print(f"[dim]Saved to {out}[/dim]")

    asyncio.run(_birth())


@cli.command()
@click.argument("name", required=False)
@click.option("--archetype", "-a", default="The Companion", help="Soul archetype")
@click.option(
    "--values",
    "-v",
    default="curiosity,empathy,honesty",
    help="Comma-separated core values",
)
@click.option(
    "--from-file",
    "-f",
    "from_file",
    type=click.Path(exists=True),
    help="Initialize from existing .soul file",
)
@click.option(
    "--dir",
    "-d",
    "soul_dir",
    default=".soul",
    help="Directory to create (default: .soul)",
)
@click.option(
    "--format",
    "soul_format",
    type=click.Choice(["dir", "zip"], case_sensitive=False),
    default="dir",
    help="Storage format: 'dir' for browsable directory (default), 'zip' for portable .soul file",
)
@click.option(
    "--setup",
    "-s",
    "setup_targets",
    default=None,
    help=(
        "Configure agent platform integration. "
        "Use 'auto' to detect installed tools, or specify platforms: "
        "claude-code,cursor,vscode,windsurf,cline,continue,gemini,codex,amazon-q"
    ),
)
def init(name, archetype, values, from_file, soul_dir, soul_format, setup_targets):
    """Initialize a .soul/ folder in the current directory.

    \b
    Examples:
      soul init "Aria"                    # basic init
      soul init "Aria" --setup auto       # init + auto-detect platforms
      soul init "Aria" -s claude-code     # init + Claude Code only
      soul init "Aria" -s cursor,vscode   # init + specific platforms
    """

    async def _init():
        from soul_protocol.runtime.soul import Soul

        soul_path = Path(soul_dir) if Path(soul_dir).is_absolute() else Path.cwd() / soul_dir
        existing = soul_path.exists() and (soul_path / "soul.json").exists()

        if existing and setup_targets is not None:
            # Soul already exists, --setup just configures platforms around it
            if from_file:
                console.print(
                    "[yellow]Warning:[/yellow] --from-file ignored; existing soul "
                    f"found at {soul_path}/. Remove the existing soul to replace it."
                )
            soul = await Soul.awaken(str(soul_path))
            console.print(
                f"\n[green]Found[/green] existing soul [bold]{soul.name}[/bold] "
                f"in {soul_path}/\n"
            )
        else:
            # Create new soul
            if existing:
                if not click.confirm(f"{soul_path}/ already contains a soul. Overwrite?"):
                    console.print("[dim]Cancelled.[/dim]")
                    return

            if from_file:
                soul = await Soul.awaken(from_file)
                console.print(f"[green]Loaded[/green] {soul.name} from {from_file}")
            else:
                if not name:
                    name_input = click.prompt("Soul name")
                else:
                    name_input = name

                values_list = [v.strip() for v in values.split(",")]
                soul = await Soul.birth(
                    name=name_input,
                    archetype=archetype,
                    values=values_list,
                )

            if soul_format == "zip":
                # ZIP format: append .soul extension if not already there
                zip_path = soul_path if str(soul_path).endswith(".soul") else Path(f"{soul_path}.soul")
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                await soul.export(str(zip_path))
                console.print(f"\n[green]OK[/green] Soul exported to [bold]{zip_path}[/bold]\n")
            else:
                await soul.save_local(str(soul_path))
                console.print(f"\n[green]OK[/green] Soul initialized in [bold]{soul_path}/[/bold]\n")

            console.print(f"  Name:      [bold]{soul.name}[/bold]")
            console.print(f"  Archetype: {soul.archetype or '(none)'}")
            console.print(f"  DID:       [dim]{soul.did}[/dim]")
            console.print(f"  Values:    {', '.join(soul.identity.core_values)}")

        if setup_targets is not None:
            from .setup import setup_integrations

            console.print()
            console.print("[bold]Setting up agent integrations...[/bold]")
            console.print()

            if setup_targets == "auto":
                platform_list = None  # auto-detect
            else:
                platform_list = [s.strip() for s in setup_targets.split(",")]

            messages = setup_integrations(
                soul_path=soul_path,
                soul_name=soul.name,
                cwd=Path.cwd(),
                platforms=platform_list,
            )
            for msg in messages:
                console.print(msg)

            console.print()
            console.print("[green]Ready![/green] Restart your editors to activate.")
        else:
            console.print()
            console.print("[dim]Next steps:[/dim]")
            console.print(f"  [cyan]soul inspect {soul_dir}/[/cyan]     -- view soul details")
            console.print(
                f"  [cyan]soul init {name or 'MyAgent'} --setup auto[/cyan]"
                "  -- configure all detected agent platforms"
            )

    asyncio.run(_init())


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def inspect(path):
    """Inspect a Soul — identity, OCEAN, memory, state, self-model."""

    async def _inspect():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        age = (datetime.now() - soul.born).days
        p = soul.dna.personality
        mem = soul._memory

        # ── Identity panel ──
        identity_lines = [
            f"[bold]{soul.name}[/bold]",
            f"[dim]{soul.archetype or '(no archetype)'}[/dim]",
            "",
            f"DID        [dim]{soul.did}[/dim]",
            f"Born       {soul.born.strftime('%Y-%m-%d %H:%M')}",
            f"Age        {age} day{'s' if age != 1 else ''}",
            f"Lifecycle  [{'green' if soul.lifecycle.value == 'active' else 'yellow'}]"
            f"{soul.lifecycle.value}[/]",
        ]
        if soul.identity.core_values:
            identity_lines.append(f"Values     {', '.join(soul.identity.core_values)}")

        identity_panel = Panel(
            "\n".join(identity_lines),
            title="Identity",
            border_style="blue",
        )

        # ── OCEAN panel ──
        ocean_lines = [
            _ocean_bar("Openness", p.openness),
            _ocean_bar("Conscientiousness", p.conscientiousness),
            _ocean_bar("Extraversion", p.extraversion),
            _ocean_bar("Agreeableness", p.agreeableness),
            _ocean_bar("Neuroticism", p.neuroticism),
        ]
        ocean_panel = Panel(
            Group(*ocean_lines),
            title="OCEAN Personality",
            border_style="blue",
        )

        # ── State panel ──
        mood = soul.state.mood.value
        energy = soul.state.energy
        social = soul.state.social_battery
        e_color = _pct_color(energy)
        s_color = _pct_color(social)

        state_lines = [
            f"  Mood            [cyan]{mood}[/]",
            f"  Energy          [{e_color}]{energy:.0f}%[/]  "
            f"[{e_color}]{'█' * int(energy / 5)}{'░' * (20 - int(energy / 5))}[/]",
            f"  Social Battery  [{s_color}]{social:.0f}%[/]  "
            f"[{s_color}]{'█' * int(social / 5)}{'░' * (20 - int(social / 5))}[/]",
            f"  Focus           {soul.state.focus}",
        ]
        state_panel = Panel(
            "\n".join(state_lines),
            title="Current State",
            border_style="blue",
        )

        # ── Memory stats panel ──
        episodic_ct = len(mem._episodic.entries())
        semantic_ct = len(mem._semantic.facts())
        procedural_ct = len(mem._procedural.entries())
        total = soul.memory_count

        mem_table = Table(show_header=False, box=None, padding=(0, 2))
        mem_table.add_column("Tier", style="cyan")
        mem_table.add_column("Count", justify="right")
        mem_table.add_row("Episodic", str(episodic_ct))
        mem_table.add_row("Semantic", str(semantic_ct))
        mem_table.add_row("Procedural", str(procedural_ct))
        mem_table.add_row("", "")
        mem_table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

        mem_panel = Panel(mem_table, title="Memory", border_style="blue")

        # ── Core memory panel ──
        core = mem.get_core()
        persona_text = core.persona if core.persona else "[dim]empty[/dim]"
        human_text = core.human if core.human else "[dim]empty[/dim]"
        core_panel = Panel(
            f"[cyan]Persona[/]\n  {persona_text}\n\n[cyan]Human[/]\n  {human_text}",
            title="Core Memory",
            border_style="blue",
        )

        # ── Self-model panel ──
        sm = soul.self_model
        images = sm.get_active_self_images()
        if images:
            si_lines = []
            for img in images:
                conf = int(img.confidence * 100)
                bar = "█" * int(img.confidence * 15) + "░" * (15 - int(img.confidence * 15))
                label = img.domain.replace("_", " ")
                si_lines.append(f"  {label:<18s} [cyan]{bar}[/] {conf}%  ({img.evidence_count} ev)")
            sm_text = "\n".join(si_lines)
        else:
            sm_text = "[dim]No self-images yet (interact more)[/dim]"

        sm_panel = Panel(sm_text, title="Self-Model", border_style="blue")

        # ── Communication style ──
        comm = soul.dna.communication
        comm_lines = [
            f"  Warmth     {comm.warmth}",
            f"  Verbosity  {comm.verbosity}",
            f"  Humor      {comm.humor_style}",
            f"  Emoji      {comm.emoji_usage}",
        ]
        comm_panel = Panel("\n".join(comm_lines), title="Communication", border_style="blue")

        # ── Render everything ──
        console.print()
        console.print(identity_panel)
        console.print(ocean_panel)
        console.print(state_panel)
        console.print(Columns([mem_panel, comm_panel], equal=True))
        console.print(core_panel)
        console.print(sm_panel)
        console.print()

    asyncio.run(_inspect())


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def status(path):
    """Show a Soul's current status (quick view)."""

    async def _status():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        mood = soul.state.mood.value
        energy = soul.state.energy
        social = soul.state.social_battery
        e_color = _pct_color(energy)
        s_color = _pct_color(social)

        lines = [
            f"[bold]{soul.name}[/bold] is feeling [cyan]{mood}[/]",
            "",
            f"  Energy          [{e_color}]{energy:.0f}%[/]  "
            f"[{e_color}]{'█' * int(energy / 5)}{'░' * (20 - int(energy / 5))}[/]",
            f"  Social Battery  [{s_color}]{social:.0f}%[/]  "
            f"[{s_color}]{'█' * int(social / 5)}{'░' * (20 - int(social / 5))}[/]",
            f"  Focus           {soul.state.focus}",
            f"  Memories        {soul.memory_count}",
        ]

        console.print(
            Panel(
                "\n".join(lines),
                title="Soul Status",
                border_style="blue",
            )
        )

    asyncio.run(_status())


@cli.command("export")
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output path (default: <name>.<format>)")
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["soul", "json", "yaml", "md"]),
    default="soul",
    help="Export format",
)
def export_cmd(source, output, fmt):
    """Export a Soul to a different format."""

    async def _export():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(source)
        out = output or f"{_safe_name(soul.name)}.{fmt}"

        if fmt == "soul":
            await soul.export(out)
        elif fmt == "json":
            Path(out).write_text(soul.serialize().model_dump_json(indent=2))
        elif fmt == "yaml":
            import yaml

            Path(out).write_text(
                yaml.dump(soul.serialize().model_dump(), default_flow_style=False)
            )
        elif fmt == "md":
            from soul_protocol.runtime.dna.prompt import dna_to_markdown

            Path(out).write_text(dna_to_markdown(soul.identity, soul.dna))

        console.print(f"[green]Exported[/green] {soul.name} to {out} ({fmt})")

    asyncio.run(_export())


@cli.command("unpack")
@click.argument("source", type=click.Path(exists=True))
@click.option("--dir", "-d", "soul_dir", default=None, help="Target directory (default: .soul/<name>/)")
def unpack_cmd(source, soul_dir):
    """Unpack a .soul file into a browsable directory.

    \b
    Creates a folder with readable YAML/JSON files you can
    browse in VS Code, diff with git, and edit directly.

    \b
    Examples:
      soul unpack guardian.soul              # → .soul/soul/
      soul unpack guardian.soul -d guardian/  # → guardian/
    """

    async def _unpack():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(source)
        target = soul_dir or f".soul/{_safe_name(soul.name)}"
        await soul.save_local(target)
        console.print(f"[green]Unpacked[/green] {soul.name} → {target}/")
        console.print("[dim]Browse the folder in VS Code or any editor.[/dim]")

    asyncio.run(_unpack())


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), required=True, help="Output .soul file")
def migrate(source, output):
    """Migrate from SOUL.md to .soul format."""

    async def _migrate():
        from soul_protocol.runtime.soul import Soul

        content = Path(source).read_text()
        soul = await Soul.from_markdown(content)
        await soul.export(output)
        console.print(f"[green]Migrated[/green] {soul.name} from SOUL.md to {output}")

    asyncio.run(_migrate())


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--preserve-memories", is_flag=True, default=True, help="Save memories before retiring"
)
def retire(path, preserve_memories):
    """Retire a Soul with dignity."""

    async def _retire():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        name = soul.name

        if not click.confirm(f"Are you sure you want to retire {name}?"):
            console.print("[dim]Cancelled.[/dim]")
            return

        await soul.retire(preserve_memories=preserve_memories)
        console.print(f"[yellow]{name}[/yellow] has been retired. Thank you for the memories.")

    asyncio.run(_retire())


@cli.command()
def list():
    """List all saved souls."""

    async def _list():
        from soul_protocol.runtime.storage.file import FileStorage

        storage = FileStorage()
        souls = await storage.list_souls()

        if not souls:
            console.print("[dim]No souls found in ~/.soul/[/dim]")
            return

        table = Table(title="Saved Souls", border_style="blue")
        table.add_column("Soul ID", style="cyan")

        for soul_id in souls:
            table.add_row(soul_id)

        console.print(table)

    asyncio.run(_list())


def _update_soul_manifest(soul_path, archive_results):
    """Update the manifest.json inside a .soul archive with archive results."""
    # Read existing zip contents
    with zipfile.ZipFile(soul_path, "r") as zf:
        existing_files = {}
        for name in zf.namelist():
            existing_files[name] = zf.read(name)

    # Update manifest
    manifest = json.loads(existing_files.get("manifest.json", b"{}"))
    if "eternal" not in manifest:
        manifest["eternal"] = {}

    for result in archive_results:
        tier = result.tier
        manifest["eternal"][tier] = {
            "reference": result.reference,
            "url": result.url,
            "cost": result.cost,
            "permanent": result.permanent,
            "archived_at": result.archived_at.isoformat(),
        }

    existing_files["manifest.json"] = json.dumps(manifest, indent=2)

    # Rewrite the zip
    with zipfile.ZipFile(soul_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in existing_files.items():
            if isinstance(data, str):
                zf.writestr(name, data)
            else:
                zf.writestr(name, data)


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--tiers",
    "-t",
    multiple=True,
    help="Storage tiers to archive to (default: all mock providers)",
)
def archive(path, tiers):
    """Archive a .soul file to eternal storage."""
    # Capture Click's multiple-value tuple before entering async context
    # NOTE: Cannot use `list()` builtin here because the `list` CLI command
    # shadows the builtin in this module's scope.
    tier_list = [t for t in tiers] if tiers else None

    async def _archive():
        from soul_protocol.runtime.soul import Soul
        from soul_protocol.runtime.eternal.manager import EternalStorageManager
        from soul_protocol.runtime.eternal.providers import (
            MockIPFSProvider,
            MockArweaveProvider,
            MockBlockchainProvider,
        )

        soul = await Soul.awaken(path)
        soul_data = Path(path).read_bytes()

        manager = EternalStorageManager()
        manager.register(MockIPFSProvider())
        manager.register(MockArweaveProvider())
        manager.register(MockBlockchainProvider())
        results = await manager.archive(soul_data, soul.did, tiers=tier_list)

        # Persist archive results into the .soul manifest
        _update_soul_manifest(path, results)

        table = Table(title=f"Archived {soul.name}", border_style="green")
        table.add_column("Tier", style="cyan")
        table.add_column("Reference", style="dim")
        table.add_column("Cost", style="yellow")
        table.add_column("Permanent", style="green")

        for r in results:
            table.add_row(
                r.tier,
                r.reference[:40] + ("..." if len(r.reference) > 40 else ""),
                r.cost,
                "Yes" if r.permanent else "No",
            )

        console.print(table)

    asyncio.run(_archive())


@cli.command()
@click.argument("reference")
@click.option(
    "--tier",
    "-t",
    default="ipfs",
    type=click.Choice(["ipfs", "arweave", "blockchain"]),
    help="Which tier to recover from (default: ipfs)",
)
@click.option("--output", "-o", type=click.Path(), required=True, help="Output file path")
def recover(reference, tier, output):
    """Recover a soul from eternal storage by reference."""

    async def _recover():
        from soul_protocol.runtime.eternal.manager import EternalStorageManager
        from soul_protocol.runtime.eternal.protocol import RecoverySource
        from soul_protocol.runtime.eternal.providers import (
            MockIPFSProvider,
            MockArweaveProvider,
            MockBlockchainProvider,
        )

        manager = EternalStorageManager()
        manager.register(MockIPFSProvider())
        manager.register(MockArweaveProvider())
        manager.register(MockBlockchainProvider())

        source = RecoverySource(tier=tier, reference=reference)

        try:
            data = await manager.recover([source])
            Path(output).write_bytes(data)
            console.print(
                f"[green]Recovered[/green] soul from {tier} to {output} "
                f"({len(data)} bytes)"
            )
        except RuntimeError as exc:
            console.print(f"[red]Recovery failed:[/red] {exc}")

    asyncio.run(_recover())


@cli.command("eternal-status")
@click.argument("path", type=click.Path(exists=True))
def eternal_status(path):
    """Show eternal storage status for a .soul file."""

    async def _eternal_status():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)

        # Read manifest from .soul archive
        eternal_data = {}
        try:
            with zipfile.ZipFile(path, "r") as zf:
                if "manifest.json" in zf.namelist():
                    manifest_raw = json.loads(zf.read("manifest.json"))
                    eternal_data = manifest_raw.get("eternal", {})
        except Exception:
            pass

        table = Table(
            title=f"Eternal Storage — {soul.name}",
            border_style="blue",
        )
        table.add_column("Tier", style="cyan")
        table.add_column("Status", style="dim")
        table.add_column("Details")

        tiers_info = {
            "ipfs": {"label": "IPFS", "desc": "Content-addressed, requires pinning"},
            "arweave": {"label": "Arweave", "desc": "Permanent, pay-once storage"},
            "blockchain": {"label": "Blockchain", "desc": "On-chain soul registry"},
        }

        for tier_key, info in tiers_info.items():
            tier_data = eternal_data.get(tier_key)
            if tier_data:
                ref = tier_data.get("reference", "unknown")
                table.add_row(
                    info["label"],
                    "[green]Archived[/green]",
                    ref,
                )
            else:
                table.add_row(
                    info["label"],
                    "[dim]Not archived[/dim]",
                    info["desc"],
                )

        console.print(table)
        if not eternal_data:
            console.print(
                "\n[dim]Use 'soul archive' to archive this soul to eternal storage.[/dim]"
            )

    asyncio.run(_eternal_status())


@cli.command("remember")
@click.argument("path", type=click.Path(exists=True))
@click.argument("text")
@click.option(
    "--importance",
    "-i",
    type=click.IntRange(1, 10),
    default=5,
    help="Importance score 1-10 (default: 5)",
)
@click.option("--emotion", "-e", type=str, default=None, help="Emotion tag (e.g. happy, sad)")
def remember_cmd(path, text, importance, emotion):
    """Store a memory in a Soul.

    \b
    Examples:
      soul remember aria.soul "User prefers dark mode"
      soul remember aria.soul "Likes Python" --importance 7
      soul remember aria.soul "Had a great day" --emotion happy
    """

    async def _remember():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        memory_id = await soul.remember(
            text,
            importance=importance,
            emotion=emotion,
        )
        if Path(path).is_dir():
            await soul.save_local(path)
        else:
            await soul.export(path)

        console.print(
            Panel(
                f"[bold]{soul.name}[/bold] will remember:\n\n"
                f"  [cyan]{text}[/cyan]\n\n"
                f"  Importance  [yellow]{importance}/10[/yellow]\n"
                f"  Emotion     {emotion or '[dim]none[/dim]'}\n"
                f"  ID          [dim]{memory_id}[/dim]",
                title="Memory Stored",
                border_style="green",
            )
        )

    asyncio.run(_remember())


@cli.command("recall")
@click.argument("path", type=click.Path(exists=True))
@click.argument("query", required=False, default=None)
@click.option(
    "--recent",
    "-r",
    type=int,
    default=None,
    help="Show N most recent memories instead of searching",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=10,
    help="Max number of results (default: 10)",
)
@click.option(
    "--min-importance",
    "-m",
    type=click.IntRange(0, 10),
    default=0,
    help="Minimum importance threshold (0 = no filter)",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Show complete memory content without truncation",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Output results as a JSON array (machine-readable)",
)
def recall_cmd(path, query, recent, limit, min_importance, full, as_json):
    """Query a Soul's memories.

    \b
    Examples:
      soul recall aria.soul "user preferences"
      soul recall aria.soul --recent 10
      soul recall aria.soul "python" --min-importance 5
      soul recall aria.soul "python" --full
      soul recall aria.soul --recent 5 --json
    """

    async def _recall():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)

        if recent is not None:
            # Show N most recent memories across all stores
            all_memories = (
                soul._memory._episodic.entries()
                + soul._memory._semantic.facts()
                + soul._memory._procedural.entries()
            )
            all_memories.sort(
                key=lambda m: m.created_at or "",
                reverse=True,
            )
            entries = all_memories[:recent]
            title = f"Recent Memories — {soul.name} (last {recent})"
        elif query:
            entries = await soul.recall(
                query,
                limit=limit,
                min_importance=min_importance,
            )
            title = f'Recall — {soul.name} — "{query}"'
        else:
            console.print("[red]Provide a search query or use --recent N[/red]")
            raise SystemExit(1)

        if not entries:
            if as_json:
                click.echo("[]")
            else:
                console.print(f"[dim]No memories found for {soul.name}.[/dim]")
            return

        # --json: machine-readable JSON array
        if as_json:
            items = [
                {
                    "type": entry.type.value,
                    "content": entry.content,
                    "importance": entry.importance,
                    "emotion": entry.emotion,
                    "created": entry.created_at.isoformat(),
                }
                for entry in entries
            ]
            click.echo(json.dumps(items, indent=2))
            return

        # --full: untruncated plain text output
        if full:
            for idx, entry in enumerate(entries, 1):
                created = entry.created_at.strftime("%Y-%m-%d")
                click.echo(
                    f"--- Memory {idx} ({entry.type.value}, "
                    f"importance: {entry.importance}, "
                    f"created: {created}) ---"
                )
                click.echo(entry.content)
                click.echo()
            return

        # Default: Rich table with truncation
        table = Table(title=title, border_style="blue")
        table.add_column("#", style="dim", width=3)
        table.add_column("Type", style="cyan", width=10)
        table.add_column("Content")
        table.add_column("Imp", justify="center", width=3)
        table.add_column("Emotion", style="yellow", width=10)
        table.add_column("Created", style="dim", width=16)

        for idx, entry in enumerate(entries, 1):
            content = entry.content
            if len(content) > 80:
                content = content[:77] + "..."
            table.add_row(
                str(idx),
                entry.type.value,
                content,
                str(entry.importance),
                entry.emotion or "",
                entry.created_at.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)
        console.print(
            f"[dim]{len(entries)} memor{'y' if len(entries) == 1 else 'ies'} found[/dim]"
        )

    asyncio.run(_recall())


@cli.command("inject")
@click.argument(
    "target",
    type=click.Choice(
        ["claude-code", "cursor", "vscode", "windsurf", "cline", "continue"],
        case_sensitive=False,
    ),
)
@click.option("--soul", "soul_name", default=None, help="Soul name to inject (default: first found)")
@click.option(
    "--dir",
    "-d",
    "soul_dir",
    default=".soul",
    help="Soul directory path (default: .soul/ in cwd)",
)
@click.option(
    "--memories",
    "-m",
    type=int,
    default=10,
    help="Number of recent memories to include (default: 10)",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress output")
def inject_cmd(target, soul_name, soul_dir, memories, quiet):
    """Inject soul context into an agent platform's config file.

    Reads the active soul and writes identity, core memory, state, and
    recent memories into the target platform's configuration file.
    Idempotent — safe to re-run without duplicating content.

    \b
    Examples:
      soul inject claude-code                # inject into .claude/CLAUDE.md
      soul inject cursor --soul Aria         # inject specific soul
      soul inject vscode --memories 20       # include more memories
      soul inject windsurf --dir ~/my-soul   # custom soul directory
    """

    async def _inject():
        from .inject import (
            build_context_block,
            find_soul,
            inject_context_block,
            resolve_target_path,
        )

        # Resolve soul directory
        dir_path = Path(soul_dir)
        if not dir_path.is_absolute():
            dir_path = Path.cwd() / soul_dir

        # Find the soul
        try:
            soul_path = find_soul(dir_path, soul_name)
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)

        # Build context block
        try:
            block = await build_context_block(soul_path, memory_limit=memories)
        except Exception as e:
            console.print(f"[red]Error reading soul:[/red] {e}")
            raise SystemExit(1)

        # Resolve target config file and inject
        target_path = resolve_target_path(target, Path.cwd())
        inject_context_block(target_path, block)

        if not quiet:
            console.print(
                f"[green]Injected[/green] soul context into "
                f"[bold]{target_path.relative_to(Path.cwd())}[/bold]"
            )

    asyncio.run(_inject())


# ============ SoulSpec Import/Export Commands ============


@cli.command("import-soulspec")
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output .soul path")
def import_soulspec_cmd(source, output):
    """Import a soul from a SoulSpec directory.

    Reads SOUL.md, IDENTITY.md, STYLE.md, and soul.json from the given
    directory and creates a new Soul with the mapped data.

    \b
    Examples:
      soul import-soulspec ./my-character/          # -> <name>.soul
      soul import-soulspec ./specs/ -o aria.soul
    """

    async def _import():
        from soul_protocol.runtime.importers.soulspec import SoulSpecImporter

        soul = await SoulSpecImporter.from_directory(source)
        out = output or f"{_safe_name(soul.name)}.soul"
        await soul.export(out)
        console.print(
            f"[green]Imported[/green] SoulSpec [bold]{soul.name}[/bold] from {source} -> {out}"
        )

    asyncio.run(_import())


@cli.command("export-soulspec")
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output directory")
def export_soulspec_cmd(source, output):
    """Export a soul to SoulSpec directory format.

    Creates a directory with SOUL.md, IDENTITY.md, STYLE.md, and soul.json
    files compatible with the SoulSpec format (soulspec.org).

    \b
    Examples:
      soul export-soulspec aria.soul              # -> aria-soulspec/
      soul export-soulspec .soul/ -o ./output/
    """

    async def _export():
        from soul_protocol.runtime.importers.soulspec import SoulSpecImporter
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(source)
        out = output or f"{_safe_name(soul.name)}-soulspec"
        result = await SoulSpecImporter.to_soulspec(soul, out)
        console.print(
            f"[green]Exported[/green] {soul.name} to SoulSpec directory -> {result}/"
        )

    asyncio.run(_export())


# ============ TavernAI Import/Export Commands ============


@cli.command("import-tavernai")
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output .soul path")
def import_tavernai_cmd(source, output):
    """Import a soul from a TavernAI Character Card V2.

    Reads a Character Card V2 JSON file or PNG with embedded character data.
    Automatically detects whether the source is JSON or PNG.

    \b
    Examples:
      soul import-tavernai character.json          # -> <name>.soul
      soul import-tavernai avatar.png -o aria.soul
    """

    async def _import():
        from soul_protocol.runtime.importers.tavernai import TavernAIImporter

        source_path = Path(source)
        if source_path.suffix.lower() == ".png":
            soul = await TavernAIImporter.from_png(source)
        else:
            data = json.loads(source_path.read_text())
            soul = await TavernAIImporter.from_json(data)

        out = output or f"{_safe_name(soul.name)}.soul"
        await soul.export(out)
        console.print(
            f"[green]Imported[/green] TavernAI card [bold]{soul.name}[/bold] from {source} -> {out}"
        )

    asyncio.run(_import())


@cli.command("export-tavernai")
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output JSON path")
@click.option("--png", type=click.Path(), default=None, help="Also export as PNG with embedded card")
def export_tavernai_cmd(source, output, png):
    """Export a soul to TavernAI Character Card V2 format.

    Creates a Character Card V2 JSON. Optionally embeds the card in a
    PNG file with --png.

    \b
    Examples:
      soul export-tavernai aria.soul                      # -> aria-card.json
      soul export-tavernai .soul/ -o card.json --png avatar.png
    """

    async def _export():
        from soul_protocol.runtime.importers.tavernai import TavernAIImporter
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(source)
        card = await TavernAIImporter.to_character_card(soul)

        out = output or f"{_safe_name(soul.name)}-card.json"
        Path(out).write_text(json.dumps(card, indent=2, ensure_ascii=False))
        console.print(
            f"[green]Exported[/green] {soul.name} to TavernAI Card V2 -> {out}"
        )

        if png:
            png_path = await TavernAIImporter.to_png(soul, png)
            console.print(
                f"[green]Exported[/green] TavernAI PNG with embedded card -> {png_path}"
            )

    asyncio.run(_export())


# ============ A2A Agent Card Commands ============


@cli.command("export-a2a")
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output JSON path")
@click.option("--url", "-u", default="", help="Agent endpoint URL for the card")
def export_a2a_cmd(source, output, url):
    """Generate an A2A Agent Card from a soul.

    Reads a .soul file or directory and outputs a JSON Agent Card
    compatible with Google's Agent-to-Agent protocol.

    \b
    Examples:
      soul export-a2a .soul/               # → <name>-agent-card.json
      soul export-a2a aria.soul -o card.json --url https://aria.example.com
    """

    async def _export():
        from soul_protocol.runtime.bridges.a2a import A2AAgentCardBridge
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(source)
        card = A2AAgentCardBridge.soul_to_agent_card(soul, url=url)
        out = output or f"{_safe_name(soul.name)}-agent-card.json"
        Path(out).write_text(json.dumps(card, indent=2, default=str))
        console.print(f"[green]Exported[/green] A2A Agent Card for {soul.name} → {out}")

    asyncio.run(_export())



@cli.command("import-a2a")
@click.argument("file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output .soul path")
def import_a2a_cmd(file, output):
    """Create a soul from an A2A Agent Card JSON file.

    Reads an Agent Card and creates a new soul with the card's
    identity, personality (from extensions.soul), and skills.

    \b
    Examples:
      soul import-a2a agent-card.json              # → <name>.soul
      soul import-a2a card.json -o my-agent.soul
    """

    async def _import():
        from soul_protocol.runtime.bridges.a2a import A2AAgentCardBridge

        card_data = json.loads(Path(file).read_text())
        soul = A2AAgentCardBridge.agent_card_to_soul(card_data)
        out = output or f"{_safe_name(soul.name)}.soul"
        await soul.export(out)
        console.print(
            f"[green]Imported[/green] soul [bold]{soul.name}[/bold] from Agent Card → {out}"
        )

    asyncio.run(_import())


# ============ Runtime Feature Parity Commands ============


def _save_soul(soul, path):
    """Save soul back to its source (directory or .soul file)."""

    async def _do_save():
        if Path(path).is_dir():
            await soul.save_local(path)
        else:
            await soul.export(path)

    asyncio.run(_do_save())


@cli.command("observe")
@click.argument("path", type=click.Path(exists=True))
@click.option("--user-input", "user_input", required=True, help="User's message")
@click.option("--agent-output", "agent_output", required=True, help="Agent's response")
@click.option("--channel", default="cli", help="Channel name (default: cli)")
def observe_cmd(path, user_input, agent_output, channel):
    """Process an interaction through the full cognitive pipeline.

    Runs sentiment detection, significance gating, memory storage,
    entity extraction, self-model updates, and evolution triggers.

    \b
    Examples:
      soul observe .soul/ --user-input "Hello" --agent-output "Hi there!"
      soul observe aria.soul --user-input "Tell me a joke" --agent-output "Why did..." --channel discord
    """

    async def _observe():
        from soul_protocol.runtime.soul import Soul
        from soul_protocol.runtime.types import Interaction

        soul = await Soul.awaken(path)
        interaction = Interaction(
            user_input=user_input,
            agent_output=agent_output,
            channel=channel,
        )
        await soul.observe(interaction)

        # Save
        if Path(path).is_dir():
            await soul.save_local(path)
        else:
            await soul.export(path)

        mood = soul.state.mood.value
        energy = soul.state.energy
        console.print(
            f"[green]Observed[/green] interaction for [bold]{soul.name}[/bold]\n"
            f"  Mood:   [cyan]{mood}[/cyan]\n"
            f"  Energy: {energy:.0f}%"
        )

    asyncio.run(_observe())


@cli.command("reflect")
@click.argument("path", type=click.Path(exists=True))
@click.option("--no-apply", is_flag=True, default=False, help="Don't consolidate results into memory")
def reflect_cmd(path, no_apply):
    """Trigger memory consolidation and reflection.

    The soul reviews recent interactions, extracts themes, creates
    summaries, and updates its self-understanding. Call periodically
    (e.g., every 10-20 interactions, or at session end).

    \b
    Examples:
      soul reflect .soul/
      soul reflect aria.soul --no-apply
    """

    async def _reflect():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        result = await soul.reflect(apply=not no_apply)

        if result is None:
            console.print(
                "[yellow]No engine available[/yellow] — reflection requires a "
                "CognitiveEngine (LLM). Set one up to enable reflection."
            )
            return

        # Save if we applied
        if not no_apply:
            if Path(path).is_dir():
                await soul.save_local(path)
            else:
                await soul.export(path)

        lines = []
        if result.themes:
            lines.append("[cyan]Themes:[/cyan]")
            for theme in result.themes:
                lines.append(f"  • {theme}")
        if result.summaries:
            lines.append("[cyan]Summaries:[/cyan]")
            for summary in result.summaries:
                content = summary.get("summary", str(summary))
                lines.append(f"  • {content}")
        if result.emotional_patterns:
            lines.append(f"[cyan]Emotional patterns:[/cyan]\n  {result.emotional_patterns}")
        if result.self_insight:
            lines.append(f"[cyan]Self-insight:[/cyan]\n  {result.self_insight}")

        if not lines:
            lines.append("[dim]No notable reflections from recent episodes.[/dim]")

        console.print(
            Panel(
                "\n".join(lines),
                title=f"Reflection — {soul.name}",
                border_style="blue",
            )
        )

    asyncio.run(_reflect())


@cli.command("feel")
@click.argument("path", type=click.Path(exists=True))
@click.option("--mood", type=str, default=None, help="Set mood (neutral, curious, focused, tired, excited, contemplative, satisfied, concerned)")
@click.option("--energy", type=float, default=None, help="Adjust energy (can be negative, e.g. -10)")
def feel_cmd(path, mood, energy):
    """Update a soul's emotional state.

    \b
    Examples:
      soul feel .soul/ --mood excited
      soul feel aria.soul --energy -10
      soul feel .soul/ --mood focused --energy 5
    """

    async def _feel():
        from soul_protocol.runtime.soul import Soul
        from soul_protocol.runtime.types import Mood

        soul = await Soul.awaken(path)

        kwargs = {}
        if mood is not None:
            try:
                kwargs["mood"] = Mood(mood)
            except ValueError:
                valid = ", ".join(m.value for m in Mood)
                console.print(f"[red]Invalid mood:[/red] '{mood}'. Valid: {valid}")
                raise SystemExit(1)
        if energy is not None:
            kwargs["energy"] = energy

        if not kwargs:
            console.print("[red]Provide at least --mood or --energy[/red]")
            raise SystemExit(1)

        soul.feel(**kwargs)

        # Save
        if Path(path).is_dir():
            await soul.save_local(path)
        else:
            await soul.export(path)

        state = soul.state
        console.print(
            f"[green]Updated[/green] [bold]{soul.name}[/bold]\n"
            f"  Mood:   [cyan]{state.mood.value}[/cyan]\n"
            f"  Energy: {state.energy:.0f}%"
        )

    asyncio.run(_feel())


@cli.command("prompt")
@click.argument("path", type=click.Path(exists=True))
def prompt_cmd(path):
    """Generate and print the system prompt for a soul.

    Outputs the full system prompt to stdout with no Rich formatting,
    so it can be piped to other commands or captured in a variable.

    \b
    Examples:
      soul prompt .soul/
      soul prompt aria.soul > prompt.txt
      soul prompt .soul/ | pbcopy
    """

    async def _prompt():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        click.echo(soul.to_system_prompt())

    asyncio.run(_prompt())


@cli.command("forget")
@click.argument("path", type=click.Path(exists=True))
@click.argument("query", required=False, default=None)
@click.option("--entity", type=str, default=None, help="Delete by entity name instead of query")
@click.option("--before", type=str, default=None, help="Delete before ISO timestamp")
@click.option("--confirm", "skip_confirm", is_flag=True, default=False, help="Skip confirmation prompt")
def forget_cmd(path, query, entity, before, skip_confirm):
    """Delete memories by query, entity, or timestamp (GDPR-compliant).

    Searches and deletes matching memories across all tiers. Records
    a deletion audit entry without storing deleted content.

    \b
    Examples:
      soul forget .soul/ "credit card"
      soul forget aria.soul --entity "John Doe"
      soul forget .soul/ --before 2026-01-01T00:00:00 --confirm
    """

    async def _forget():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)

        if entity:
            description = f"entity '{entity}'"
            if not skip_confirm and not click.confirm(
                f"Delete all memories related to {description}?"
            ):
                console.print("[dim]Cancelled.[/dim]")
                return
            result = await soul.forget_entity(entity)
        elif before:
            from datetime import datetime as dt

            try:
                timestamp = dt.fromisoformat(before)
            except ValueError:
                console.print(f"[red]Invalid ISO timestamp:[/red] '{before}'")
                raise SystemExit(1)
            description = f"memories before {before}"
            if not skip_confirm and not click.confirm(
                f"Delete all {description}?"
            ):
                console.print("[dim]Cancelled.[/dim]")
                return
            result = await soul.forget_before(timestamp)
        elif query:
            description = f"query '{query}'"
            if not skip_confirm and not click.confirm(
                f"Delete memories matching {description}?"
            ):
                console.print("[dim]Cancelled.[/dim]")
                return
            result = await soul.forget(query)
        else:
            console.print("[red]Provide a QUERY, --entity, or --before[/red]")
            raise SystemExit(1)

        total = result.get("total_deleted", 0)

        # Save
        if Path(path).is_dir():
            await soul.save_local(path)
        else:
            await soul.export(path)

        console.print(
            f"[yellow]Forgot[/yellow] {total} memor{'y' if total == 1 else 'ies'} "
            f"from [bold]{soul.name}[/bold] ({description})"
        )
        if result.get("tiers"):
            for tier, count in result["tiers"].items():
                if count > 0:
                    console.print(f"  {tier}: {count}")

    asyncio.run(_forget())


@cli.command("edit-core")
@click.argument("path", type=click.Path(exists=True))
@click.option("--persona", type=str, default=None, help="Set persona text")
@click.option("--human", type=str, default=None, help="Set human knowledge text")
def edit_core_cmd(path, persona, human):
    """Edit a soul's core memory (always-loaded persona and human knowledge).

    \b
    Examples:
      soul edit-core .soul/ --persona "I am a helpful coding assistant"
      soul edit-core aria.soul --human "User prefers Python and dark mode"
      soul edit-core .soul/ --persona "New persona" --human "New human"
    """

    async def _edit_core():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)

        if persona is None and human is None:
            console.print("[red]Provide at least --persona or --human[/red]")
            raise SystemExit(1)

        await soul.edit_core_memory(persona=persona, human=human)

        # Save
        if Path(path).is_dir():
            await soul.save_local(path)
        else:
            await soul.export(path)

        core = soul.get_core_memory()
        console.print(
            Panel(
                f"[cyan]Persona[/]\n  {core.persona or '[dim]empty[/dim]'}\n\n"
                f"[cyan]Human[/]\n  {core.human or '[dim]empty[/dim]'}",
                title=f"Core Memory — {soul.name}",
                border_style="green",
            )
        )

    asyncio.run(_edit_core())


@cli.command("evolve")
@click.argument("path", type=click.Path(exists=True))
@click.option("--propose", is_flag=True, default=False, help="Propose a new mutation")
@click.option("--trait", type=str, default=None, help="Trait to mutate (with --propose)")
@click.option("--value", type=str, default=None, help="New value for trait (with --propose)")
@click.option("--reason", type=str, default=None, help="Reason for mutation (with --propose)")
@click.option("--approve", "approve_id", type=str, default=None, help="Approve a pending mutation by ID")
@click.option("--reject", "reject_id", type=str, default=None, help="Reject a pending mutation by ID")
@click.option("--list", "list_mutations", is_flag=True, default=False, help="List pending mutations and history")
def evolve_cmd(path, propose, trait, value, reason, approve_id, reject_id, list_mutations):
    """Manage soul evolution — propose, approve, reject, or list mutations.

    \b
    Examples:
      soul evolve .soul/ --propose --trait communication.warmth --value high --reason "User prefers warmth"
      soul evolve .soul/ --list
      soul evolve .soul/ --approve abc123
      soul evolve .soul/ --reject abc123
    """

    async def _evolve():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)

        if propose:
            if not all([trait, value, reason]):
                console.print("[red]--propose requires --trait, --value, and --reason[/red]")
                raise SystemExit(1)
            mutation = await soul.propose_evolution(trait, value, reason)
            if Path(path).is_dir():
                await soul.save_local(path)
            else:
                await soul.export(path)
            console.print(
                f"[green]Proposed[/green] mutation [bold]{mutation.id}[/bold]\n"
                f"  Trait:  {mutation.trait}\n"
                f"  Old:    {mutation.old_value}\n"
                f"  New:    {mutation.new_value}\n"
                f"  Reason: {mutation.reason}"
            )
        elif approve_id:
            result = await soul.approve_evolution(approve_id)
            if result:
                if Path(path).is_dir():
                    await soul.save_local(path)
                else:
                    await soul.export(path)
                console.print(f"[green]Approved[/green] mutation {approve_id}")
            else:
                console.print(f"[red]Could not approve[/red] mutation {approve_id}")
        elif reject_id:
            result = await soul.reject_evolution(reject_id)
            if result:
                if Path(path).is_dir():
                    await soul.save_local(path)
                else:
                    await soul.export(path)
                console.print(f"[yellow]Rejected[/yellow] mutation {reject_id}")
            else:
                console.print(f"[red]Could not reject[/red] mutation {reject_id}")
        elif list_mutations:
            pending = soul.pending_mutations
            history = soul.evolution_history

            if pending:
                table = Table(title="Pending Mutations", border_style="yellow")
                table.add_column("ID", style="cyan", width=12)
                table.add_column("Trait")
                table.add_column("Old → New")
                table.add_column("Reason", style="dim")
                for m in pending:
                    table.add_row(m.id[:12], m.trait, f"{m.old_value} → {m.new_value}", m.reason)
                console.print(table)
            else:
                console.print("[dim]No pending mutations.[/dim]")

            if history:
                htable = Table(title="Evolution History", border_style="blue")
                htable.add_column("ID", style="dim", width=12)
                htable.add_column("Trait")
                htable.add_column("Change")
                htable.add_column("Status")
                htable.add_column("Date", style="dim")
                for m in history:
                    status = "[green]Approved[/]" if m.approved else "[red]Rejected[/]"
                    date = m.approved_at.strftime("%Y-%m-%d") if m.approved_at else ""
                    htable.add_row(m.id[:12], m.trait, f"{m.old_value} → {m.new_value}", status, date)
                console.print(htable)
            else:
                console.print("[dim]No evolution history.[/dim]")
        else:
            console.print("[red]Use --propose, --approve ID, --reject ID, or --list[/red]")
            raise SystemExit(1)

    asyncio.run(_evolve())


@cli.command("evaluate")
@click.argument("path", type=click.Path(exists=True))
@click.option("--user-input", "user_input", required=True, help="User's message")
@click.option("--agent-output", "agent_output", required=True, help="Agent's response")
@click.option("--domain", type=str, default=None, help="Domain for rubric selection")
def evaluate_cmd(path, user_input, agent_output, domain):
    """Evaluate an interaction against a rubric.

    Scores the interaction, stores learning as procedural memory,
    and adjusts skill XP based on the score.

    \b
    Examples:
      soul evaluate .soul/ --user-input "Explain recursion" --agent-output "Recursion is..."
      soul evaluate aria.soul --user-input "Fix this bug" --agent-output "Here's the fix" --domain coding
    """

    async def _evaluate():
        from soul_protocol.runtime.soul import Soul
        from soul_protocol.runtime.types import Interaction

        soul = await Soul.awaken(path)
        interaction = Interaction(
            user_input=user_input,
            agent_output=agent_output,
        )

        try:
            result = await soul.evaluate(interaction, domain=domain)
        except Exception as e:
            console.print(f"[red]Evaluation failed:[/red] {e}")
            raise SystemExit(1)

        # Save
        if Path(path).is_dir():
            await soul.save_local(path)
        else:
            await soul.export(path)

        # Display results
        lines = [
            f"[bold]Overall Score:[/bold] {result.overall_score:.2f}",
            f"[bold]Rubric:[/bold] {result.rubric_id}",
        ]
        if result.criterion_results:
            lines.append("")
            lines.append("[cyan]Criteria:[/cyan]")
            for cr in result.criterion_results:
                icon = "[green]✓[/]" if cr.passed else "[red]✗[/]"
                lines.append(f"  {icon} {cr.criterion}: {cr.score:.2f}")
                if cr.reasoning:
                    lines.append(f"      [dim]{cr.reasoning}[/dim]")
        if result.learning:
            lines.append(f"\n[cyan]Learning:[/cyan]\n  {result.learning}")

        console.print(
            Panel("\n".join(lines), title=f"Evaluation — {soul.name}", border_style="blue")
        )

    asyncio.run(_evaluate())


@cli.command("learn")
@click.argument("path", type=click.Path(exists=True))
@click.option("--user-input", "user_input", required=True, help="User's message")
@click.option("--agent-output", "agent_output", required=True, help="Agent's response")
@click.option("--domain", type=str, default=None, help="Domain for rubric selection")
def learn_cmd(path, user_input, agent_output, domain):
    """Evaluate an interaction and create a learning event if notable.

    Combines evaluation with the learning pipeline — extracts lessons,
    grants XP, and stores procedural memory.

    \b
    Examples:
      soul learn .soul/ --user-input "Explain recursion" --agent-output "Recursion is..."
      soul learn aria.soul --user-input "Fix this bug" --agent-output "Here's the fix" --domain coding
    """

    async def _learn():
        from soul_protocol.runtime.soul import Soul
        from soul_protocol.runtime.types import Interaction

        soul = await Soul.awaken(path)
        interaction = Interaction(
            user_input=user_input,
            agent_output=agent_output,
        )

        try:
            event = await soul.learn(interaction, domain=domain)
        except Exception as e:
            console.print(f"[red]Learning failed:[/red] {e}")
            raise SystemExit(1)

        # Save
        if Path(path).is_dir():
            await soul.save_local(path)
        else:
            await soul.export(path)

        if event is None:
            console.print("[dim]No notable learning from this interaction.[/dim]")
            return

        score_str = f"{event.evaluation_score:.2f}" if event.evaluation_score is not None else "n/a"
        console.print(
            Panel(
                f"[cyan]Lesson:[/cyan]\n  {event.lesson}\n\n"
                f"  Domain:     {event.domain}\n"
                f"  Confidence: {event.confidence:.0%}\n"
                f"  Score:      {score_str}\n"
                f"  Skill:      {event.skill_id or '[dim]none[/dim]'}",
                title=f"Learning Event — {soul.name}",
                border_style="green",
            )
        )

    asyncio.run(_learn())


@cli.command("skills")
@click.argument("path", type=click.Path(exists=True))
def skills_cmd(path):
    """View a soul's skills with level, XP, and progress.

    \b
    Examples:
      soul skills .soul/
      soul skills aria.soul
    """

    async def _skills():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        registry = soul.skills

        if not registry.skills:
            console.print(f"[dim]{soul.name} has no skills yet. Interact more![/dim]")
            return

        table = Table(title=f"Skills — {soul.name}", border_style="blue")
        table.add_column("Skill", style="cyan")
        table.add_column("Level", justify="center")
        table.add_column("XP", justify="right")
        table.add_column("Next", justify="right", style="dim")
        table.add_column("Progress")

        for skill in registry.skills:
            pct = skill.xp / skill.xp_to_next if skill.xp_to_next > 0 else 1.0
            filled = int(pct * 15)
            bar = "█" * filled + "░" * (15 - filled)
            table.add_row(
                skill.name,
                str(skill.level),
                str(skill.xp),
                str(skill.xp_to_next),
                f"[cyan]{bar}[/] {int(pct * 100)}%",
            )

        console.print(table)

    asyncio.run(_skills())


@cli.command("bond")
@click.argument("path", type=click.Path(exists=True))
@click.option("--strengthen", type=float, default=None, help="Strengthen bond by this amount")
def bond_cmd(path, strengthen):
    """View or modify the soul's bond with its bonded entity.

    \b
    Examples:
      soul bond .soul/
      soul bond aria.soul --strengthen 5.0
    """

    async def _bond():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        bond = soul.bond

        if strengthen is not None:
            bond.strengthen(amount=strengthen)
            if Path(path).is_dir():
                await soul.save_local(path)
            else:
                await soul.export(path)
            console.print(f"[green]Strengthened[/green] bond for [bold]{soul.name}[/bold]")

        strength = bond.bond_strength
        s_color = _pct_color(strength)
        filled = int(strength / 5)
        bar = "█" * filled + "░" * (20 - filled)

        lines = [
            f"  Bonded to:    {bond.bonded_to or '[dim]nobody[/dim]'}",
            f"  Strength:     [{s_color}]{strength:.1f}%[/]  [{s_color}]{bar}[/]",
            f"  Interactions: {bond.interaction_count}",
            f"  Since:        {bond.bonded_at.strftime('%Y-%m-%d %H:%M')}",
        ]

        console.print(
            Panel("\n".join(lines), title=f"Bond — {soul.name}", border_style="blue")
        )

    asyncio.run(_bond())


@cli.command("events")
@click.argument("path", type=click.Path(exists=True))
@click.option("--recent", "-n", type=int, default=10, help="Number of recent events (default: 10)")
def events_cmd(path, recent):
    """View general events (Conway's autobiographical memory hierarchy).

    \b
    Examples:
      soul events .soul/
      soul events aria.soul --recent 20
    """

    async def _events():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        all_events = soul.general_events

        if not all_events:
            console.print(f"[dim]{soul.name} has no general events yet.[/dim]")
            return

        # Sort by last_updated descending
        all_events.sort(key=lambda e: e.last_updated, reverse=True)
        events = all_events[:recent]

        table = Table(title=f"General Events — {soul.name}", border_style="blue")
        table.add_column("#", style="dim", width=3)
        table.add_column("Theme", style="cyan")
        table.add_column("Episodes", justify="center", width=8)
        table.add_column("Started", style="dim", width=16)
        table.add_column("Updated", style="dim", width=16)

        for idx, event in enumerate(events, 1):
            table.add_row(
                str(idx),
                event.theme or "[dim]untitled[/dim]",
                str(len(event.episode_ids)),
                event.started_at.strftime("%Y-%m-%d %H:%M"),
                event.last_updated.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table)
        console.print(f"[dim]{len(events)} of {len(all_events)} event(s)[/dim]")

    asyncio.run(_events())


@cli.command("context")
@click.argument("path", type=click.Path(exists=True), required=False, default=None)
@click.option("--ingest", is_flag=True, default=False, help="Ingest a message into context")
@click.option("--role", type=str, default=None, help="Message role (with --ingest)")
@click.option("--content", "msg_content", type=str, default=None, help="Message content (with --ingest)")
@click.option("--assemble", is_flag=True, default=False, help="Assemble context window")
@click.option("--max-tokens", type=int, default=None, help="Token budget (with --assemble)")
@click.option("--grep", "grep_pattern", type=str, default=None, help="Search context history by pattern")
@click.option("--describe", "describe_flag", is_flag=True, default=False, help="Show context store metadata")
def context_cmd(path, ingest, role, msg_content, assemble, max_tokens, grep_pattern, describe_flag):
    """LCM (Lossless Context Management) — ingest, assemble, search, and describe context.

    Works standalone with an in-memory SQLite store. Pass a .soul path to use
    the soul's context store (if available).

    \b
    Examples:
      soul context --ingest --role user --content "Hello there"
      soul context --assemble --max-tokens 4000
      soul context --grep "hello"
      soul context --describe
    """

    async def _context():
        from soul_protocol.runtime.context.lcm import LCMContext

        # Create standalone LCMContext (in-memory)
        lcm = LCMContext(db_path=":memory:")
        await lcm.initialize()

        if ingest:
            if not role or not msg_content:
                console.print("[red]--ingest requires --role and --content[/red]")
                raise SystemExit(1)
            msg_id = await lcm.ingest(role, msg_content)
            console.print(f"[green]Ingested[/green] message [dim]{msg_id}[/dim] (role={role})")

        elif assemble:
            result = await lcm.assemble(max_tokens=max_tokens)
            console.print(
                Panel(
                    f"Nodes:            {len(result.nodes)}\n"
                    f"Total tokens:     {result.total_tokens}\n"
                    f"Compaction:       {'yes' if result.compaction_applied else 'no'}",
                    title="Assembled Context",
                    border_style="blue",
                )
            )
            for node in result.nodes:
                content = node.content[:80] if node.content else ""
                console.print(f"  [{node.level.value}] {content}...")

        elif grep_pattern:
            results = await lcm.grep(grep_pattern)
            if not results:
                console.print(f"[dim]No matches for '{grep_pattern}'[/dim]")
                return
            table = Table(title=f"Context Search — '{grep_pattern}'", border_style="blue")
            table.add_column("ID", style="dim", width=12)
            table.add_column("Role", style="cyan", width=10)
            table.add_column("Snippet")
            for hit in results:
                table.add_row(hit.message_id, hit.role, hit.content_snippet[:80])
            console.print(table)

        elif describe_flag:
            info = await lcm.describe()
            earliest, latest = info.date_range
            console.print(
                Panel(
                    f"Messages:     {info.total_messages}\n"
                    f"Nodes:        {info.total_nodes}\n"
                    f"Total tokens: {info.total_tokens}\n"
                    f"Date range:   {earliest or 'n/a'} → {latest or 'n/a'}",
                    title="Context Store",
                    border_style="blue",
                )
            )
        else:
            console.print("[red]Use --ingest, --assemble, --grep PATTERN, or --describe[/red]")
            raise SystemExit(1)

    asyncio.run(_context())


# ---------------------------------------------------------------------------
# soul health / cleanup / repair — soul maintenance commands (v0.2.7)
# ---------------------------------------------------------------------------


@cli.command("health")
@click.argument("path", type=click.Path(exists=True))
def health_cmd(path):
    """Audit a soul's health — memory tiers, duplicates, skills, graph, bond."""

    async def _health():
        from soul_protocol.runtime.soul import Soul
        from soul_protocol.runtime.memory.compression import MemoryCompressor

        soul = await Soul.awaken(path)
        mm = soul._memory

        episodic = builtins.list(mm._episodic.entries())
        semantic = builtins.list(mm._semantic.facts())
        procedural = builtins.list(mm._procedural.entries())
        graph_nodes = mm._graph.entities()
        skills = soul.skills.skills
        evals = soul.evaluator._history
        total = len(episodic) + len(semantic) + len(procedural)

        # Detect duplicates
        compressor = MemoryCompressor()
        all_mems = episodic + semantic + procedural
        deduped = compressor.deduplicate(all_mems, similarity_threshold=0.8)
        dup_count = len(all_mems) - len(deduped)

        # Detect low-importance memories
        low_imp = [m for m in all_mems if m.importance <= 2]

        # Detect stale procedural (evaluation scores)
        stale_proc = [p for p in procedural if p.content.startswith("Scored ")]

        # Orphan graph nodes (nodes not referenced in any memory)
        all_content = " ".join(m.content for m in all_mems)
        orphan_nodes = [n for n in graph_nodes if n.lower() not in all_content.lower() and len(n) > 2]

        # Bond sanity
        bond = soul.bond
        bond_issues = []
        if bond.bond_strength > 100:
            bond_issues.append(f"Bond strength {bond.bond_strength:.0f} exceeds 100")
        if bond.bond_strength < 0:
            bond_issues.append(f"Bond strength {bond.bond_strength:.0f} is negative")

        # Skill sanity
        skill_issues = []
        for s in skills:
            if s.xp < 0:
                skill_issues.append(f"Skill {s.id} has negative XP ({s.xp})")
            if s.level < 1 or s.level > 10:
                skill_issues.append(f"Skill {s.id} has invalid level ({s.level})")

        # Build report
        lines = [
            f"[bold]{soul.name}[/bold] — Soul Health Report",
            "",
            "[bold]Memory Tiers[/bold]",
            f"  Episodic:    {len(episodic):>5}",
            f"  Semantic:    {len(semantic):>5}",
            f"  Procedural:  {len(procedural):>5}",
            f"  [bold]Total:       {total:>5}[/bold]",
            "",
            "[bold]Knowledge & Skills[/bold]",
            f"  Graph nodes: {len(graph_nodes):>5}",
            f"  Skills:      {len(skills):>5}",
            f"  Eval history:{len(evals):>5}",
            "",
            "[bold]Bond[/bold]",
            f"  Strength:    {bond.bond_strength:>5.1f}",
            f"  Interactions:{bond.interaction_count:>5}",
            "",
            "[bold]Issues Found[/bold]",
        ]

        issues_found = 0
        if dup_count > 0:
            lines.append(f"  [yellow]⚠ {dup_count} duplicate memories (>80% overlap)[/]")
            issues_found += 1
        if low_imp:
            lines.append(f"  [dim]ℹ {len(low_imp)} low-importance memories (≤2)[/]")
        if stale_proc:
            lines.append(f"  [dim]ℹ {len(stale_proc)} evaluation procedural entries[/]")
        if orphan_nodes and len(orphan_nodes) > 10:
            lines.append(f"  [yellow]⚠ {len(orphan_nodes)} orphan graph nodes (not in any memory)[/]")
            issues_found += 1
        for issue in bond_issues:
            lines.append(f"  [red]✗ {issue}[/]")
            issues_found += 1
        for issue in skill_issues:
            lines.append(f"  [red]✗ {issue}[/]")
            issues_found += 1

        if issues_found == 0 and not low_imp and not stale_proc:
            lines.append("  [green]✓ No issues found — soul is healthy[/]")
        elif issues_found == 0:
            lines.append("  [green]✓ No critical issues[/]")

        color = "green" if issues_found == 0 else "yellow" if issues_found < 3 else "red"
        console.print(Panel("\n".join(lines), title="Soul Health", border_style=color))

    asyncio.run(_health())


@cli.command("cleanup")
@click.argument("path", type=click.Path(exists=True))
@click.option("--auto", "auto_mode", is_flag=True, help="Apply all cleanups without prompting.")
@click.option("--dry-run", is_flag=True, help="Show what would be cleaned without changing anything.")
@click.option("--dedup/--no-dedup", default=True, help="Remove near-duplicate memories.")
@click.option("--stale-evals/--no-stale-evals", default=True, help="Remove low-value evaluation procedurals.")
@click.option("--orphan-nodes/--no-orphan-nodes", default=True, help="Remove orphan graph nodes.")
@click.option("--low-importance", type=int, default=0, help="Remove memories with importance ≤ N (0=skip).")
def cleanup_cmd(path, auto_mode, dry_run, dedup, stale_evals, orphan_nodes, low_importance):
    """Clean up a soul — remove duplicates, stale evals, orphan nodes."""

    async def _cleanup():
        from soul_protocol.runtime.soul import Soul
        from soul_protocol.runtime.memory.compression import MemoryCompressor

        soul = await Soul.awaken(path)
        mm = soul._memory
        actions = []

        # 1. Deduplicate
        if dedup:
            compressor = MemoryCompressor()
            for tier_name, store in [("episodic", mm._episodic), ("semantic", mm._semantic), ("procedural", mm._procedural)]:
                if tier_name == "semantic":
                    entries = builtins.list(store.facts())
                else:
                    entries = builtins.list(store.entries())
                if not entries:
                    continue
                deduped = compressor.deduplicate(entries, similarity_threshold=0.8)
                removed_ids = {m.id for m in entries} - {m.id for m in deduped}
                if removed_ids:
                    actions.append(("dedup", tier_name, removed_ids))

        # 2. Stale evaluation procedurals
        if stale_evals:
            procedural = builtins.list(mm._procedural.entries())
            stale = [p for p in procedural if p.content.startswith("Scored ") and p.importance <= 5]
            if stale:
                actions.append(("stale_evals", "procedural", {p.id for p in stale}))

        # 3. Orphan graph nodes
        if orphan_nodes:
            all_mems = builtins.list(mm._episodic.entries()) + builtins.list(mm._semantic.facts()) + builtins.list(mm._procedural.entries())
            all_content = " ".join(m.content for m in all_mems).lower()
            nodes = mm._graph.entities()
            orphans = [n for n in nodes if n.lower() not in all_content and len(n) > 2]
            if orphans:
                actions.append(("orphan_nodes", "graph", orphans))

        # 4. Low importance
        if low_importance > 0:
            for tier_name, store in [("episodic", mm._episodic), ("semantic", mm._semantic)]:
                if tier_name == "semantic":
                    entries = builtins.list(store.facts())
                else:
                    entries = builtins.list(store.entries())
                low = [m for m in entries if m.importance <= low_importance]
                if low:
                    actions.append(("low_importance", tier_name, {m.id for m in low}))

        if not actions:
            console.print("[green]✓ Nothing to clean up — soul is tidy[/]")
            return

        # Show plan
        total_removals = 0
        for action_type, target, items in actions:
            count = len(items)
            total_removals += count
            if action_type == "dedup":
                console.print(f"  [yellow]Remove {count} duplicates from {target}[/]")
            elif action_type == "stale_evals":
                console.print(f"  [yellow]Remove {count} stale evaluation entries[/]")
            elif action_type == "orphan_nodes":
                console.print(f"  [yellow]Remove {count} orphan graph nodes[/]")
                if count <= 10:
                    for n in items:
                        console.print(f"    - {n}")
            elif action_type == "low_importance":
                console.print(f"  [yellow]Remove {count} low-importance memories from {target}[/]")

        console.print(f"\n  [bold]Total: {total_removals} items to remove[/]")

        if dry_run:
            console.print("\n[dim]Dry run — no changes made.[/]")
            return

        # Confirm
        if not auto_mode:
            if not click.confirm("\nProceed with cleanup?"):
                console.print("[dim]Cancelled.[/]")
                return

        # Execute
        removed = 0
        for action_type, target, items in actions:
            if action_type == "orphan_nodes":
                for node in items:
                    mm._graph.remove_entity(node)
                    removed += 1
            elif action_type in ("dedup", "stale_evals", "low_importance"):
                for mid in items:
                    if target == "episodic":
                        await mm._episodic.remove(mid)
                    elif target == "semantic":
                        await mm._semantic.remove(mid)
                    elif target == "procedural":
                        await mm._procedural.remove(mid)
                    removed += 1

        # Save
        await soul.export(path)
        console.print(f"\n[green]✓ Cleaned {removed} items. Soul saved.[/]")

    asyncio.run(_cleanup())


@cli.command("repair")
@click.argument("path", type=click.Path(exists=True))
@click.option("--reset-energy", is_flag=True, help="Reset energy and social battery to 100%.")
@click.option("--reset-bond", is_flag=True, help="Reset bond strength to 50.0.")
@click.option("--rebuild-graph", is_flag=True, help="Rebuild knowledge graph from memory content.")
@click.option("--clear-evals", is_flag=True, help="Clear evaluation history.")
@click.option("--clear-skills", is_flag=True, help="Clear all learned skills.")
@click.option("--clear-procedural", is_flag=True, help="Clear all procedural memories.")
def repair_cmd(path, reset_energy, reset_bond, rebuild_graph, clear_evals, clear_skills, clear_procedural):
    """Repair a soul — reset state, rebuild graph, clear stale data."""

    async def _repair():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)
        changes = []

        if reset_energy:
            soul._state.current.energy = 100.0
            soul._state.current.social_battery = 100.0
            changes.append("Reset energy and social battery to 100%")

        if reset_bond:
            soul._identity.bond.bond_strength = 50.0
            changes.append("Reset bond strength to 50.0")

        if rebuild_graph:
            # Clear and rebuild from all memories
            mm = soul._memory
            old_count = len(mm._graph.entities())
            mm._graph._entities.clear()
            mm._graph._edges.clear()

            all_mems = builtins.list(mm._episodic.entries()) + builtins.list(mm._semantic.facts())
            from soul_protocol.runtime.types import Interaction
            for mem in all_mems:
                # Extract entities from memory content using the heuristic extractor
                interaction = Interaction(user_input=mem.content, agent_output="")
                entities = mm.extract_entities(interaction)
                if entities:
                    graph_entities = []
                    for ent in entities:
                        graph_ent = {
                            "name": ent["name"],
                            "entity_type": ent.get("type", "unknown"),
                        }
                        graph_entities.append(graph_ent)
                    await mm.update_graph(graph_entities)

            new_count = len(mm._graph.entities())
            changes.append(f"Rebuilt graph: {old_count} → {new_count} nodes")

        if clear_evals:
            count = len(soul.evaluator._history)
            soul.evaluator._history.clear()
            changes.append(f"Cleared {count} evaluation entries")

        if clear_skills:
            count = len(soul.skills.skills)
            soul.skills.skills.clear()
            changes.append(f"Cleared {count} skills")

        if clear_procedural:
            mm = soul._memory
            procs = builtins.list(mm._procedural.entries())
            for p in procs:
                await mm._procedural.remove(p.id)
            changes.append(f"Cleared {len(procs)} procedural memories")

        if not changes:
            console.print("[yellow]No repair actions specified. Use --help to see options.[/]")
            return

        # Save
        await soul.export(path)

        lines = [f"[bold]{soul.name}[/bold] — Repairs Applied", ""]
        for change in changes:
            lines.append(f"  [green]✓[/] {change}")
        lines.append(f"\n  Soul saved to {path}")

        console.print(Panel("\n".join(lines), title="Soul Repair", border_style="green"))

    asyncio.run(_repair())


if __name__ == "__main__":
    cli()
