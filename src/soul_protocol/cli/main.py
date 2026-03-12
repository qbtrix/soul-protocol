# cli/main.py — Click CLI for the Soul Protocol
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
    output,
):
    """Birth a new Soul.

    Create a soul with custom personality using OCEAN trait flags,
    a config file (--config), or an existing soul file (--from-file).
    """

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

            ocean_flags = {
                "openness": openness,
                "conscientiousness": conscientiousness,
                "extraversion": extraversion,
                "agreeableness": agreeableness,
                "neuroticism": neuroticism,
            }
            ocean = {k: v for k, v in ocean_flags.items() if v is not None}

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

        out = output or f"./{soul.name.lower()}.soul"
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
def init(name, archetype, values, from_file, soul_dir):
    """Initialize a .soul/ folder in the current directory."""

    async def _init():
        from soul_protocol.runtime.soul import Soul

        soul_path = Path(soul_dir) if Path(soul_dir).is_absolute() else Path.cwd() / soul_dir

        if soul_path.exists() and (soul_path / "soul.json").exists():
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

        await soul.save_local(str(soul_path))

        console.print(f"\n[green]OK[/green] Soul initialized in [bold]{soul_path}/[/bold]\n")
        console.print(f"  Name:      [bold]{soul.name}[/bold]")
        console.print(f"  Archetype: {soul.archetype or '(none)'}")
        console.print(f"  DID:       [dim]{soul.did}[/dim]")
        console.print(f"  Values:    {', '.join(soul.identity.core_values)}")
        console.print()
        console.print("[dim]Next steps:[/dim]")
        console.print(f"  [cyan]soul inspect {soul_dir}/[/cyan]     -- view soul details")
        console.print(
            f"  [cyan]soul export {soul_dir}/ -o name.soul[/cyan] -- create portable .soul file"
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
@click.option("--output", "-o", type=click.Path(), required=True, help="Output file path")
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

        if fmt == "soul":
            await soul.export(output)
        elif fmt == "json":
            Path(output).write_text(soul.serialize().model_dump_json(indent=2))
        elif fmt == "yaml":
            import yaml

            Path(output).write_text(
                yaml.dump(soul.serialize().model_dump(), default_flow_style=False)
            )
        elif fmt == "md":
            from soul_protocol.runtime.dna.prompt import dna_to_markdown

            Path(output).write_text(dna_to_markdown(soul.identity, soul.dna))

        console.print(f"[green]Exported[/green] {soul.name} to {output} ({fmt})")

    asyncio.run(_export())


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
def recall_cmd(path, query, recent, limit, min_importance):
    """Query a Soul's memories.

    \b
    Examples:
      soul recall aria.soul "user preferences"
      soul recall aria.soul --recent 10
      soul recall aria.soul "python" --min-importance 5
    """

    async def _recall():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(path)

        if recent is not None:
            # Show N most recent episodic memories
            entries = soul._memory._episodic.entries()[:recent]
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
            console.print(f"[dim]No memories found for {soul.name}.[/dim]")
            return

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


if __name__ == "__main__":
    cli()
