# cli/main.py — Click CLI for the Soul Protocol
# Updated: 2026-02-23 — Added --config/-c option and OCEAN trait flags
#   (--openness, --conscientiousness, --extraversion, --agreeableness,
#   --neuroticism) to the birth command for flexible soul configuration.
#   Uses Soul.birth_from_config() when --config is provided.
# Created: 2026-02-22 — Commands: birth, inspect, status, export, migrate

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="soul")
def cli():
    """Soul Protocol — Portable identity and memory for AI agents."""
    pass


@cli.command()
@click.argument("name", required=False)
@click.option("--archetype", "-a", help="Soul archetype (e.g. 'The Companion')")
@click.option("--from-file", "-f", type=click.Path(exists=True), help="Create from soul.md/yaml/json")
@click.option(
    "--config", "-c", "config_file",
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
    name, archetype, from_file, config_file,
    openness, conscientiousness, extraversion, agreeableness, neuroticism,
    output,
):
    """Birth a new Soul.

    Create a soul with custom personality using OCEAN trait flags,
    a config file (--config), or an existing soul file (--from-file).
    """

    async def _birth():
        from soul_protocol.soul import Soul

        if config_file:
            # Birth from a full config YAML/JSON file
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

            # Build ocean dict from CLI flags if any are provided
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

            # Show OCEAN values if any were customized
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
@click.argument("path", type=click.Path(exists=True))
def inspect(path):
    """Inspect a Soul file."""

    async def _inspect():
        from soul_protocol.soul import Soul

        soul = await Soul.awaken(path)
        age = (datetime.now() - soul.born).days

        table = Table(title=f"{soul.name}", show_header=False, border_style="blue")
        table.add_column("Field", style="cyan")
        table.add_column("Value")

        table.add_row("DID", soul.did)
        table.add_row("Archetype", soul.archetype or "(none)")
        table.add_row("Born", soul.born.strftime("%Y-%m-%d %H:%M"))
        table.add_row("Age", f"{age} days")
        table.add_row("Lifecycle", soul.lifecycle.value)
        table.add_row("", "")
        table.add_row("Mood", soul.state.mood.value)
        table.add_row("Energy", f"{soul.state.energy:.0f}%")
        table.add_row("Focus", soul.state.focus)
        table.add_row("Social Battery", f"{soul.state.social_battery:.0f}%")
        table.add_row("", "")

        p = soul.dna.personality
        table.add_row("Openness", f"{p.openness:.2f}")
        table.add_row("Conscientiousness", f"{p.conscientiousness:.2f}")
        table.add_row("Extraversion", f"{p.extraversion:.2f}")
        table.add_row("Agreeableness", f"{p.agreeableness:.2f}")
        table.add_row("Neuroticism", f"{p.neuroticism:.2f}")

        console.print(table)

    asyncio.run(_inspect())


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def status(path):
    """Show a Soul's current status."""

    async def _status():
        from soul_protocol.soul import Soul

        soul = await Soul.awaken(path)
        mood_emoji = {
            "neutral": "",
            "curious": "",
            "focused": "",
            "tired": "",
            "excited": "",
            "contemplative": "",
            "satisfied": "",
            "concerned": "",
        }.get(soul.state.mood.value, "")

        console.print(
            Panel(
                f"[bold]{soul.name}[/bold] is feeling "
                f"[cyan]{soul.state.mood.value}[/cyan] {mood_emoji}\n"
                f"Energy: [{'green' if soul.state.energy > 50 else 'red'}]"
                f"{soul.state.energy:.0f}%[/] | "
                f"Focus: {soul.state.focus} | "
                f"Social: {soul.state.social_battery:.0f}%",
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
        from soul_protocol.soul import Soul

        soul = await Soul.awaken(source)

        if fmt == "soul":
            await soul.export(output)
        elif fmt == "json":
            Path(output).write_text(soul.serialize().model_dump_json(indent=2))
        elif fmt == "yaml":
            import yaml

            Path(output).write_text(yaml.dump(soul.serialize().model_dump(), default_flow_style=False))
        elif fmt == "md":
            from soul_protocol.dna.prompt import dna_to_markdown

            Path(output).write_text(dna_to_markdown(soul.identity, soul.dna))

        console.print(f"[green]Exported[/green] {soul.name} to {output} ({fmt})")

    asyncio.run(_export())


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), required=True, help="Output .soul file")
def migrate(source, output):
    """Migrate from SOUL.md to .soul format."""

    async def _migrate():
        from soul_protocol.soul import Soul

        content = Path(source).read_text()
        soul = await Soul.from_markdown(content)
        await soul.export(output)
        console.print(f"[green]Migrated[/green] {soul.name} from SOUL.md to {output}")

    asyncio.run(_migrate())


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--preserve-memories", is_flag=True, default=True, help="Save memories before retiring")
def retire(path, preserve_memories):
    """Retire a Soul with dignity."""

    async def _retire():
        from soul_protocol.soul import Soul

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
        from soul_protocol.storage.file import FileStorage

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


if __name__ == "__main__":
    cli()
