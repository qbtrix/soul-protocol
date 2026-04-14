# cli/org.py — `soul org init` command: bootstrap an org.
# Renamed: feat/paw-os-init — was cli/paw_os.py. Flattened the Click group from
#   `soul paw os <cmd>` to `soul org <cmd>` and moved the default data dir from
#   ~/.pocketpaw/org/ to ~/.soul/. Set SOUL_DATA_DIR to override. Governance
#   persona description updated from "Paw OS instance" to "org instance".
# Created: feat/paw-os-init — Workstream A slice 3 of the Org Architecture RFC (#164).
#
# This command brings an org into existence from nothing:
#   1. Create the org directory (default ~/.soul/, or $SOUL_DATA_DIR)
#   2. Birth a root governance soul and save it as root.soul
#   3. Generate an Ed25519 signing keypair for the root identity
#   4. Initialize the SQLite journal via open_journal()
#   5. Append the genesis event chain: org.created + scope.created(org:*)
#
# Scope is intentionally narrow — this is not the full 8-step wizard from the
# RFC. It is the minimum viable bootstrap so follow-up slices (starter fleet,
# user joins, policy bootstrap) have a real org to build on.
#
# TODO(slice #163 integration): when `load_template("governance")` ships in
# the installed package, replace the hardcoded persona below with a template
# load so organizations can customize their root agent prior to init.

from __future__ import annotations

import asyncio
import getpass
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import click
from rich.console import Console
from rich.panel import Panel

from soul_protocol.engine.journal import open_journal
from soul_protocol.spec.journal import Actor, EventEntry

console = Console()


# --- Governance persona fallback -------------------------------------------
# TODO(#163): replace with load_template("governance") once that API lands.
GOVERNANCE_PERSONA_NAME = "Root"
GOVERNANCE_PERSONA_DESC = (
    "The governance identity for this org instance. Root holds the signing key, "
    "approves admin grants, authors scope.created events, and refuses to chat. "
    "It exists to make the org's decisions verifiable, not to participate in them."
)
GOVERNANCE_OCEAN = {
    "openness": 0.2,
    "conscientiousness": 0.95,
    "extraversion": 0.1,
    "agreeableness": 0.5,
    "neuroticism": 0.1,
}
GOVERNANCE_VALUES = ["audit", "durability", "minimal surface", "verifiable decisions"]
GOVERNANCE_MISSION = (
    "Govern this org instance. Sign what must be signed. Stay out of conversations."
)


# --- Helpers ----------------------------------------------------------------


def _default_data_dir() -> Path:
    """Default org data directory.

    Honors the ``SOUL_DATA_DIR`` env var when set. Otherwise falls back to
    ``~/.soul/``. The whole directory IS the org — there is no extra nesting.
    """
    env = os.environ.get("SOUL_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".soul"


def _default_users_dir() -> Path:
    """Default directory for user-owned soul data (nested under the org dir)."""
    return _default_data_dir() / "users"


def _default_archives_dir() -> Path:
    """Default directory for archived/exported org data (nested under the org dir)."""
    return _default_data_dir() / "archives"


def _dir_is_non_empty(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def _current_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER", "unknown")


def _generate_ed25519_keypair() -> tuple[bytes, bytes]:
    """Return (private_key_pem, public_key_raw_bytes)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_pem, public_raw


def _write_private_key(path: Path, data: bytes) -> None:
    """Write private key with 0600 permissions (best-effort on platforms without chmod)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Create with restrictive permissions from the start
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows / exotic filesystems — accept best effort
        pass


def _build_governance_soul(org_name: str, purpose: str | None):
    """Birth the root governance soul.

    Returns the awaited Soul instance. Imported lazily so the CLI loads fast
    for callers who only use other subcommands.
    """
    from soul_protocol.runtime.soul import Soul

    persona_text = (
        f"{GOVERNANCE_PERSONA_DESC}\n\n"
        f"Organization: {org_name}\n"
        f"Mission: {GOVERNANCE_MISSION}"
    )
    if purpose:
        persona_text += f"\nOrg purpose: {purpose}"

    return Soul.birth(
        name=GOVERNANCE_PERSONA_NAME,
        archetype="governance",
        personality=persona_text,
        values=list(GOVERNANCE_VALUES),
        ocean=GOVERNANCE_OCEAN,
        persona=persona_text,
    )


def _remove_tree(path: Path) -> None:
    """Best-effort recursive delete for --force. Preserves the directory itself."""
    import shutil

    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


# --- Commands --------------------------------------------------------------


@click.group("org")
def org_group() -> None:
    """Org management commands."""


@click.group("user")
def user_group() -> None:
    """User management commands."""


@org_group.command("init")
@click.option("--org-name", type=str, default=None, help="Organization name.")
@click.option("--purpose", type=str, default=None, help="Optional mission statement for the root soul.")
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to create the org (default: ~/.soul/, or $SOUL_DATA_DIR).",
)
@click.option("--force", is_flag=True, help="Overwrite an existing org directory.")
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Fail instead of prompting. Requires --org-name.",
)
def org_init(
    org_name: str | None,
    purpose: str | None,
    data_dir: Path | None,
    force: bool,
    non_interactive: bool,
) -> None:
    """Bootstrap a new org: root soul, signing key, journal, genesis events.

    \b
    Example:
      soul org init --org-name "Acme Ventures" --purpose "A software company"
    """
    data_dir = Path(data_dir) if data_dir else _default_data_dir()

    # -- Resolve org_name --------------------------------------------------
    if not org_name:
        if non_interactive:
            click.echo("error: --org-name is required with --non-interactive", err=True)
            sys.exit(2)
        org_name = click.prompt("Organization name", type=str).strip()
        if not org_name:
            click.echo("error: org name cannot be empty", err=True)
            sys.exit(2)

    # -- Check existing dir ------------------------------------------------
    if _dir_is_non_empty(data_dir):
        if not force:
            click.echo(
                f"error: {data_dir} already exists and is non-empty. "
                "Pass --force to overwrite.",
                err=True,
            )
            sys.exit(1)
        _remove_tree(data_dir)

    data_dir.mkdir(parents=True, exist_ok=True)
    keys_dir = data_dir / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Bootstrapping org[/bold] at [cyan]{data_dir}[/cyan]")

    # -- Root soul ---------------------------------------------------------
    console.print("  [1/5] Birthing root governance soul…")
    soul = asyncio.run(_build_governance_soul(org_name, purpose))
    root_did = soul.did
    root_soul_path = data_dir / "root.soul"
    asyncio.run(soul.export(str(root_soul_path)))
    console.print(f"        [green]OK[/green] {root_soul_path.name}")

    # -- Keypair -----------------------------------------------------------
    console.print("  [2/5] Generating Ed25519 signing keypair…")
    private_pem, public_raw = _generate_ed25519_keypair()
    private_path = keys_dir / "root.ed25519"
    public_path = keys_dir / "root.ed25519.pub"
    did_path = keys_dir / "root.did"
    _write_private_key(private_path, private_pem)
    public_path.write_bytes(public_raw)
    did_path.write_text(root_did + "\n", encoding="utf-8")
    console.print(f"        [green]OK[/green] {private_path.relative_to(data_dir)} (0600)")

    # -- Journal -----------------------------------------------------------
    console.print("  [3/5] Initializing journal…")
    journal_path = data_dir / "journal.db"
    journal = open_journal(journal_path)
    console.print(f"        [green]OK[/green] {journal_path.name}")

    # -- Genesis events ----------------------------------------------------
    console.print("  [4/5] Writing genesis events…")
    try:
        actor = Actor(kind="root", id=root_did, scope_context=["org:*"])
        now = datetime.now(timezone.utc)
        created_by = _current_user()
        org_created = EventEntry(
            id=uuid4(),
            ts=now,
            actor=actor,
            action="org.created",
            scope=["org:*"],
            payload={
                "org_name": org_name,
                "purpose": purpose,
                "created_by_user": created_by,
                "root_did": root_did,
            },
        )
        journal.append(org_created)

        scope_created = EventEntry(
            id=uuid4(),
            ts=datetime.now(timezone.utc),
            actor=actor,
            action="scope.created",
            scope=["org:*"],
            causation_id=org_created.id,
            payload={"scope": "org:*", "label": "organization root scope"},
        )
        journal.append(scope_created)
    finally:
        journal.close()
    console.print("        [green]OK[/green] 2 events appended")

    # -- Summary -----------------------------------------------------------
    console.print("  [5/5] Done.")
    summary = (
        f"[bold]Org:[/bold]      {org_name}\n"
        f"[bold]Root DID:[/bold] {root_did}\n"
        f"[bold]Data dir:[/bold] {data_dir}\n"
        f"[bold]Journal:[/bold]  {journal_path} (2 events)\n"
        f"[bold]Root key:[/bold] {private_path} (0600)\n\n"
        "[dim]Next:[/dim] install a starter fleet with [cyan]soul org fleet install[/cyan] "
        "(coming in Workstream B)."
    )
    console.print(Panel(summary, title="Org ready", border_style="green"))
