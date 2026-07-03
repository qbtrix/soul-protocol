# cli/did.py — CLI commands for DID (Decentralized Identifier) management.
# Created: 2026-06-27 — Phase 1 of the trust/digital-id CLI feature.
#   Adds `soul did show` and `soul did verify` subcommands for inspecting
#   and verifying a soul's decentralized identity and trust chain.

from __future__ import annotations

import asyncio
import base64
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Windows-safe symbols (cp1252 doesn't support Unicode checkmarks)
if sys.platform == "win32":
    _OK = "[green]OK[/green]"
    _FAIL = "[red]FAIL[/red]"
    _WARN = "[yellow]!![/yellow]"
else:
    _OK = "[green]\u2713[/green]"
    _FAIL = "[red]\u2717[/red]"
    _WARN = "[yellow]\u26a0[/yellow]"


@click.group("did")
def did_group():
    """Manage Decentralized Identifiers (DIDs) for souls.

    Inspect identity, public keys, and verify trust chain integrity.

    \b
    Examples:
      soul did show aria.soul
      soul did show .soul/
      soul did verify aria.soul
    """
    pass


@did_group.command("show")
@click.argument("source", type=click.Path(exists=True))
def did_show(source):
    """Display the DID and identity info of a soul.

    Shows the soul's name, DID, public key, archetype, trust chain
    length, and key rotation status.

    \b
    Examples:
      soul did show aria.soul
      soul did show .soul/
    """

    async def _show():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(source)

        # Gather identity info
        pub_bytes = soul._keystore.public_key_bytes
        pub_b64 = base64.b64encode(pub_bytes).decode("ascii") if pub_bytes else None
        has_private = soul._keystore.has_private_key
        chain_len = len(soul.trust_chain.entries)
        prev_keys = len(soul._keystore.previous_public_keys)

        # Build the identity table
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 2),
            expand=False,
        )
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("Name", f"[bold]{soul.name}[/bold]")
        table.add_row("DID", f"[cyan]{soul.did}[/cyan]")

        if soul.archetype:
            table.add_row("Archetype", soul.archetype)

        if soul.born:
            table.add_row("Born", str(soul.born))

        # Public key (truncated for display)
        if pub_b64:
            display_key = f"{pub_b64[:16]}...{pub_b64[-8:]}" if len(pub_b64) > 24 else pub_b64
            table.add_row("Public Key", f"[green]{display_key}[/green]")
            table.add_row("Algorithm", "Ed25519")
        else:
            table.add_row("Public Key", "[red]none[/red]")

        # Key status
        if has_private:
            table.add_row("Private Key", "[green]present[/green] (can sign)")
        else:
            table.add_row("Private Key", "[yellow]absent[/yellow] (verify only)")

        # Key rotation
        if prev_keys > 0:
            table.add_row("Rotated Keys", f"{prev_keys} previous key(s)")

        # Trust chain
        table.add_row("Trust Chain", f"{chain_len} entries")

        console.print(
            Panel(
                table,
                title=f"[bold]DID Identity — {soul.name}[/bold]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    asyncio.run(_show())


@did_group.command("verify")
@click.argument("source", type=click.Path(exists=True))
@click.option("--verbose", "-v", is_flag=True, help="Show detailed verification steps")
def did_verify(source, verbose):
    """Verify the trust chain and DID integrity of a soul.

    Checks that all trust chain entries have valid Ed25519 signatures,
    the hash chain is intact, and public keys match the keystore.

    Exits with code 1 if any check fails.

    \b
    Examples:
      soul did verify aria.soul
      soul did verify .soul/ --verbose
    """

    async def _verify():
        from soul_protocol.runtime.soul import Soul

        soul = await Soul.awaken(source)

        # Basic info
        console.print(f"\n[dim]Verifying:[/dim] [bold]{soul.name}[/bold] ({soul.did})\n")

        chain = soul.trust_chain
        chain_len = len(chain.entries)

        # Step 1: Check DID format
        did_valid = soul.did.startswith("did:soul:")
        if did_valid:
            console.print(f"  {_OK} DID format valid")
        else:
            console.print(f"  {_FAIL} DID format invalid -- expected did:soul:...")

        # Step 2: Check public key present
        pub_bytes = soul._keystore.public_key_bytes
        if pub_bytes:
            console.print(f"  {_OK} Public key present (Ed25519)")
        else:
            console.print(f"  {_WARN} No public key -- cannot verify signatures")

        # Step 3: Verify trust chain
        chain_valid = True
        if chain_len == 0:
            console.print(f"  {_WARN} Trust chain is empty (no signed actions)")
        else:
            chain_valid, error = soul.verify_chain()
            if chain_valid:
                console.print(f"  {_OK} Trust chain valid -- {chain_len} entries verified")
            else:
                console.print(f"  {_FAIL} Trust chain INVALID -- {error}")

        # Step 4: Show chain summary if verbose
        if verbose and chain_len > 0:
            console.print()
            table = Table(title="Trust Chain Entries", show_lines=True)
            table.add_column("#", style="dim", width=4)
            table.add_column("Action", style="cyan")
            table.add_column("Timestamp", style="dim")
            table.add_column("Signature", width=20)

            for entry in chain.entries:
                sig_short = f"{entry.signature[:12]}..." if entry.signature else "none"
                ts_str = (
                    entry.timestamp.isoformat()
                    if hasattr(entry.timestamp, "isoformat")
                    else str(entry.timestamp)
                )
                table.add_row(
                    str(entry.seq),
                    entry.action,
                    ts_str,
                    sig_short,
                )

            console.print(table)

        # Final verdict
        console.print()
        all_ok = did_valid and (chain_len == 0 or chain_valid)
        if all_ok:
            console.print(
                Panel(
                    "[green]All checks passed[/green]",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    "[red]Verification failed[/red]",
                    border_style="red",
                )
            )
            sys.exit(1)

    asyncio.run(_verify())


__all__ = ["did_group"]
