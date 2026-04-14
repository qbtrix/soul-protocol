# cli/org.py — `soul org {init,status,destroy}` and `soul user invite` stub.
# Updated: feat/onboarding-full — destroy's tarball writer now filters out
#   archives_dir so it doesn't recurse into the tarball it's mid-writing
#   (which would raise ReadError and leave the org neither archived nor
#   wiped). Also drop founder email from the user.joined journal payload —
#   the journal is append-only and has no right-to-erasure path, so PII
#   stays in the founder's soul file (erasable).
# Renamed: feat/paw-os-init — was cli/paw_os.py. Flattened the Click group
#   from `soul paw os <cmd>` to `soul org <cmd>`, promoted `user` to a
#   top-level sibling group, and moved the default data dir from
#   ~/.pocketpaw/org/ to ~/.soul/. Set SOUL_DATA_DIR to override.
# Created: feat/paw-os-init — Workstream A slice 3 of the Org Architecture RFC (#164).
# Updated: feat/onboarding-full — Workstream B. Extended `init` from the minimal
#   bootstrap into the RFC's 8-step wizard: org values, founder user soul,
#   first-level scope tree, starter fleet placeholder, invite hint. Added
#   `org status` (read-only inspector) and `org destroy` (tarball + wipe).
#   Layer 1 of root undeletability is enforced via Soul.role="root" + Soul.delete()
#   in runtime/soul.py; layer 3 lives in `soul delete` in cli/main.py.

from __future__ import annotations

import asyncio
import getpass
import json as _json
import os
import shutil
import stat
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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
    """Default directory for archived/exported org data.

    Lives as a SIBLING of the data dir, not nested inside it. Reason: ``soul org
    destroy`` tarballs the data dir and then wipes it. If archives lived inside
    the data dir, the tarball would be wiped along with everything else,
    silently destroying the safety net users rely on during destroy.

    Honors ``SOUL_ARCHIVES_DIR`` when set. Otherwise falls back to
    ``~/.soul-archives/`` (sibling of default ``~/.soul/``).
    """
    env = os.environ.get("SOUL_ARCHIVES_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".soul-archives"


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
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _build_governance_soul(org_name: str, purpose: str | None, values: list[str]):
    """Birth the root governance soul (lazy import keeps CLI startup fast)."""
    from soul_protocol.runtime.soul import Soul

    persona_text = (
        f"{GOVERNANCE_PERSONA_DESC}\n\n"
        f"Organization: {org_name}\n"
        f"Mission: {GOVERNANCE_MISSION}"
    )
    if purpose:
        persona_text += f"\nOrg purpose: {purpose}"
    if values:
        persona_text += f"\nOrg values: {', '.join(values)}"

    return Soul.birth(
        name=GOVERNANCE_PERSONA_NAME,
        archetype="governance",
        personality=persona_text,
        values=list(GOVERNANCE_VALUES) + list(values),
        ocean=GOVERNANCE_OCEAN,
        persona=persona_text,
        role="root",
    )


def _build_founder_user_soul(name: str, email: str):
    """Birth the founder user soul. Bare-bones — admin granting is an event, not a flag."""
    from soul_protocol.runtime.soul import Soul

    persona_text = (
        f"I am {name}, the founder of this org instance. "
        f"Reachable at {email}."
    )
    return Soul.birth(
        name=name,
        archetype="user",
        personality=persona_text,
        persona=persona_text,
    )


def _remove_tree(path: Path) -> None:
    """Best-effort recursive delete preserving the directory itself."""
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _parse_csv(raw: str | None, *, max_items: int | None = None) -> list[str]:
    if not raw:
        return []
    items = [s.strip() for s in raw.split(",") if s.strip()]
    if max_items is not None:
        items = items[:max_items]
    return items


VALID_FLEETS = ("sales", "support", "solo", "skip")


# --- Groups ---------------------------------------------------------------


@click.group("org")
def org_group() -> None:
    """Org management commands."""


@click.group("user")
def user_group() -> None:
    """User management commands."""


# --- init ----------------------------------------------------------------


@org_group.command("init")
@click.option("--org-name", type=str, default=None, help="Organization name.")
@click.option("--purpose", type=str, default=None, help="Optional mission statement for the root soul.")
@click.option("--values", "values_csv", type=str, default=None,
              help="Comma-separated org values (3-5 recommended).")
@click.option("--founder-name", type=str, default=None, help="Founder user name.")
@click.option("--founder-email", type=str, default=None, help="Founder user email.")
@click.option("--scopes", "scopes_csv", type=str, default=None,
              help="Comma-separated first-level scopes, e.g. 'org:sales,org:ops'.")
@click.option("--fleet", type=click.Choice(VALID_FLEETS, case_sensitive=False),
              default=None, help="Starter fleet to seed: sales, support, solo, or skip.")
@click.option("--data-dir", type=click.Path(file_okay=False, path_type=Path), default=None,
              help="Where to create the org (default: ~/.soul/, or $SOUL_DATA_DIR).")
@click.option("--users-dir", type=click.Path(file_okay=False, path_type=Path), default=None,
              help="Where founder user souls live (default: ~/.soul/users/, or $SOUL_DATA_DIR/users/).")
@click.option("--force", is_flag=True, help="Overwrite an existing org directory.")
@click.option("--non-interactive", is_flag=True,
              help="Fail instead of prompting. Requires --org-name at minimum.")
def org_init(
    org_name: str | None,
    purpose: str | None,
    values_csv: str | None,
    founder_name: str | None,
    founder_email: str | None,
    scopes_csv: str | None,
    fleet: str | None,
    data_dir: Path | None,
    users_dir: Path | None,
    force: bool,
    non_interactive: bool,
) -> None:
    """Bootstrap an org with root soul, founder, scopes, and a fleet stub.

    Implements the 8-step wizard from RFC #164. Each step emits one or more
    journal events so the final org state is fully reconstructable from the
    event log.

    \b
    Example:
      soul org init --org-name "Acme" --purpose "AI tooling" \
        --values "audit,velocity,kindness" \
        --founder-name "Pat" --founder-email "pat@acme.com" \
        --scopes "org:sales,org:ops" --fleet sales --non-interactive
    """
    data_dir = Path(data_dir) if data_dir else _default_data_dir()
    users_dir = Path(users_dir) if users_dir else _default_users_dir()

    # --- Step 1 — org name -------------------------------------------------
    if not org_name:
        if non_interactive:
            click.echo("error: --org-name is required with --non-interactive", err=True)
            sys.exit(2)
        org_name = click.prompt("Organization name", type=str).strip()
        if not org_name:
            click.echo("error: org name cannot be empty", err=True)
            sys.exit(2)

    # --- Step 1.5 — values -------------------------------------------------
    values = _parse_csv(values_csv, max_items=5)
    if not values and not non_interactive:
        raw = click.prompt(
            "Org values (3-5, comma-separated, blank to skip)", default="", show_default=False
        )
        values = _parse_csv(raw, max_items=5)

    # --- Step 2 — founder user --------------------------------------------
    if not non_interactive:
        if not founder_name:
            founder_name = click.prompt(
                "Founder name (blank to skip)", default="", show_default=False
            ).strip() or None
        if founder_name and not founder_email:
            founder_email = click.prompt("Founder email", type=str).strip()

    # --- Step 6b — scope tree ---------------------------------------------
    extra_scopes = _parse_csv(scopes_csv, max_items=5)
    if not extra_scopes and not non_interactive:
        raw = click.prompt(
            "First-level scopes (up to 5, comma-separated, blank to skip)",
            default="",
            show_default=False,
        )
        extra_scopes = _parse_csv(raw, max_items=5)

    # --- Step 7 — fleet ---------------------------------------------------
    if not fleet and not non_interactive:
        fleet = click.prompt(
            "Starter fleet (sales/support/solo/skip)",
            type=click.Choice(VALID_FLEETS, case_sensitive=False),
            default="skip",
        )
    fleet = (fleet or "skip").lower()

    # --- Pre-flight: existing dir -----------------------------------------
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

    # --- Birth root soul --------------------------------------------------
    console.print("  [1/8] Birthing root governance soul...")
    soul = asyncio.run(_build_governance_soul(org_name, purpose, values))
    root_did = soul.did
    root_soul_path = data_dir / "root.soul"
    asyncio.run(soul.export(str(root_soul_path)))
    console.print(f"        [green]OK[/green] {root_soul_path.name} (role=root)")

    # --- Keypair ----------------------------------------------------------
    console.print("  [2/8] Generating Ed25519 signing keypair...")
    private_pem, public_raw = _generate_ed25519_keypair()
    private_path = keys_dir / "root.ed25519"
    public_path = keys_dir / "root.ed25519.pub"
    did_path = keys_dir / "root.did"
    _write_private_key(private_path, private_pem)
    public_path.write_bytes(public_raw)
    did_path.write_text(root_did + "\n", encoding="utf-8")
    console.print(f"        [green]OK[/green] {private_path.relative_to(data_dir)} (0600)")

    # --- Journal ----------------------------------------------------------
    console.print("  [3/8] Initializing journal...")
    journal_path = data_dir / "journal.db"
    journal = open_journal(journal_path)
    console.print(f"        [green]OK[/green] {journal_path.name}")

    actor = Actor(kind="root", id=root_did, scope_context=["org:*"])
    created_by = _current_user()
    event_count = 0
    founder_user_path: Path | None = None

    try:
        # --- Genesis events -------------------------------------------------
        console.print("  [4/8] Writing genesis events...")
        org_created = EventEntry(
            id=uuid4(),
            ts=datetime.now(timezone.utc),
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
        event_count += 1

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
        event_count += 1

        # --- Step 1.5 — values event ---------------------------------------
        if values:
            journal.append(EventEntry(
                id=uuid4(),
                ts=datetime.now(timezone.utc),
                actor=actor,
                action="org.values_set",
                scope=["org:*"],
                causation_id=org_created.id,
                payload={"values": values},
            ))
            event_count += 1

        # --- Step 2 — founder user soul ------------------------------------
        if founder_name:
            if not founder_email and non_interactive:
                click.echo("error: --founder-email required when --founder-name given", err=True)
                sys.exit(2)
            console.print(f"  [5/8] Creating founder user soul ({founder_name})...")
            users_dir.mkdir(parents=True, exist_ok=True)
            founder_user_path = users_dir / f"{founder_name}.soul"
            founder_soul = asyncio.run(_build_founder_user_soul(founder_name, founder_email or ""))
            asyncio.run(founder_soul.export(str(founder_user_path)))
            user_did = founder_soul.did

            # GDPR: email stays in the founder's soul file (erasable) and is
            # omitted from the journal payload (append-only, no clean
            # right-to-erasure path). The DID alone is enough to reconstruct
            # the link back to the soul for audit purposes.
            joined = EventEntry(
                id=uuid4(),
                ts=datetime.now(timezone.utc),
                actor=actor,
                action="user.joined",
                scope=["org:*"],
                causation_id=org_created.id,
                payload={
                    "user_did": user_did,
                    "name": founder_name,
                    "is_founder": True,
                },
            )
            journal.append(joined)
            event_count += 1

            journal.append(EventEntry(
                id=uuid4(),
                ts=datetime.now(timezone.utc),
                actor=actor,
                action="user.admin_granted",
                scope=["org:*"],
                causation_id=joined.id,
                payload={"user_did": user_did, "name": founder_name, "grant_reason": "founder"},
            ))
            event_count += 1
            console.print(f"        [green]OK[/green] {founder_user_path}")
        else:
            console.print("  [5/8] No founder user supplied (skipped)")

        # --- Step 6b — extra scopes ---------------------------------------
        if extra_scopes:
            console.print(f"  [6/8] Creating {len(extra_scopes)} first-level scope(s)...")
            for label in extra_scopes:
                journal.append(EventEntry(
                    id=uuid4(),
                    ts=datetime.now(timezone.utc),
                    actor=actor,
                    action="scope.created",
                    scope=["org:*"],
                    causation_id=scope_created.id,
                    payload={"scope": label, "parent": "org:*"},
                ))
                event_count += 1
            console.print(f"        [green]OK[/green] {', '.join(extra_scopes)}")
        else:
            console.print("  [6/8] No first-level scopes supplied (skipped)")

        # --- Step 7 — starter fleet stub ----------------------------------
        if fleet != "skip":
            console.print(f"  [7/8] Recording starter fleet placeholder ({fleet})...")
            journal.append(EventEntry(
                id=uuid4(),
                ts=datetime.now(timezone.utc),
                actor=actor,
                action="agent.spawned",
                scope=["org:*"],
                causation_id=org_created.id,
                payload={
                    "fleet": fleet,
                    "placeholder": True,
                    "note": (
                        "Fleet selection recorded. Real installation wires through "
                        "the starter-fleet follow-up PR."
                    ),
                },
            ))
            event_count += 1
            console.print(f"        [green]OK[/green] fleet={fleet} (placeholder)")
        else:
            console.print("  [7/8] Skipped fleet selection")
    finally:
        journal.close()

    # --- Step 8 — invite hint ---------------------------------------------
    console.print("  [8/8] Done.")

    invite_line = "soul user invite <email>  # invite cmd lands in a follow-up PR"

    # --- Summary ----------------------------------------------------------
    summary_lines = [
        f"[bold]Org:[/bold]       {org_name}",
        f"[bold]Root DID:[/bold]  {root_did}",
        f"[bold]Data dir:[/bold]  {data_dir}",
        f"[bold]Journal:[/bold]   {journal_path} ({event_count} events)",
        f"[bold]Root key:[/bold]  {private_path} (0600)",
    ]
    if values:
        summary_lines.append(f"[bold]Values:[/bold]    {', '.join(values)}")
    if founder_user_path:
        summary_lines.append(f"[bold]Founder:[/bold]   {founder_user_path}")
    if extra_scopes:
        summary_lines.append(f"[bold]Scopes:[/bold]    {', '.join(extra_scopes)}")
    summary_lines.append(f"[bold]Fleet:[/bold]     {fleet} (placeholder)")
    summary_lines.append("")
    summary_lines.append(f"[dim]Invite teammates:[/dim] [cyan]{invite_line}[/cyan]")

    console.print(Panel("\n".join(summary_lines), title="Org ready", border_style="green"))


# --- status --------------------------------------------------------------


def _gather_status(data_dir: Path) -> dict[str, Any]:
    """Read the journal and derive a status snapshot. Pure function — no I/O writes."""
    journal_path = data_dir / "journal.db"
    if not journal_path.exists():
        raise FileNotFoundError(f"no journal at {journal_path}")

    journal = open_journal(journal_path)
    try:
        events = journal.query(limit=10_000)
    finally:
        journal.close()

    org_name: str | None = None
    purpose: str | None = None
    values: list[str] = []
    root_did: str | None = None
    created_at: datetime | None = None
    scopes: list[str] = []
    user_dids: set[str] = set()
    agent_count = 0
    last_ts: datetime | None = None

    for ev in events:
        if last_ts is None or ev.ts > last_ts:
            last_ts = ev.ts
        payload = ev.payload if isinstance(ev.payload, dict) else {}
        if ev.action == "org.created":
            org_name = payload.get("org_name")
            purpose = payload.get("purpose")
            root_did = payload.get("root_did")
            created_at = ev.ts
        elif ev.action == "org.values_set":
            values = list(payload.get("values") or [])
        elif ev.action == "scope.created":
            scope_label = payload.get("scope", "")
            if scope_label and scope_label not in scopes:
                scopes.append(scope_label)
        elif ev.action == "user.joined":
            did = payload.get("user_did") or payload.get("did")
            if did:
                user_dids.add(did)
        elif ev.action == "user.left":
            did = payload.get("user_did") or payload.get("did")
            if did:
                user_dids.discard(did)
        elif ev.action == "agent.spawned":
            agent_count += 1
        elif ev.action == "agent.retired":
            agent_count = max(0, agent_count - 1)

    return {
        "org_name": org_name,
        "purpose": purpose,
        "values": values,
        "root_did": root_did,
        "created_at": created_at.isoformat() if created_at else None,
        "event_count": len(events),
        "last_event_ts": last_ts.isoformat() if last_ts else None,
        "user_count": len(user_dids),
        "agent_count": agent_count,
        "scopes": scopes,
        "data_dir": str(data_dir),
    }


@org_group.command("status")
@click.option("--data-dir", type=click.Path(file_okay=False, path_type=Path), default=None,
              help="Org dir to inspect (default: ~/.soul/, or $SOUL_DATA_DIR).")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def org_status(data_dir: Path | None, as_json: bool) -> None:
    """Show a snapshot of the org derived from the journal."""
    data_dir = Path(data_dir) if data_dir else _default_data_dir()
    try:
        snap = _gather_status(data_dir)
    except FileNotFoundError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    if as_json:
        click.echo(_json.dumps(snap, indent=2, sort_keys=True))
        return

    table = Table(title=f"Org — {snap['org_name'] or '(unnamed)'}", border_style="cyan")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Org name", snap["org_name"] or "—")
    table.add_row("Purpose", snap["purpose"] or "—")
    table.add_row("Values", ", ".join(snap["values"]) or "—")
    table.add_row("Root DID", snap["root_did"] or "—")
    table.add_row("Created at", snap["created_at"] or "—")
    table.add_row("Events", str(snap["event_count"]))
    table.add_row("Last event", snap["last_event_ts"] or "—")
    table.add_row("Users", str(snap["user_count"]))
    table.add_row("Agents", str(snap["agent_count"]))
    table.add_row("Scopes", ", ".join(snap["scopes"]) or "—")
    table.add_row("Data dir", snap["data_dir"])
    console.print(table)


# --- destroy --------------------------------------------------------------


def _archive_org(data_dir: Path, archives_dir: Path) -> Path:
    """Tarball the org directory under ``archives_dir`` and return the path.

    When ``archives_dir`` lives inside ``data_dir`` (the default —
    ``<data_dir>/archives/``), tarfile's default recursive walk would
    descend into the archive file we're actively writing and raise a
    ReadError partway through. Leaving the org neither archived nor wiped.
    The filter below short-circuits any path that lives inside the
    archives dir, so the tarball contains everything except its own
    storage location.
    """
    archives_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archives_dir / f"org-destroyed-{stamp}.tar.gz"

    archives_dir_resolved = archives_dir.resolve()

    def _skip_archives(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
        # `tarinfo.name` is relative to the tar root (arcname=data_dir.name).
        # Resolve the on-disk path it refers to and reject anything under
        # archives_dir so we never tar the in-flight archive file or any
        # previously written tarballs in that directory.
        rel = Path(tarinfo.name)
        try:
            parts = rel.parts
            on_disk = data_dir / Path(*parts[1:]) if len(parts) > 1 else data_dir
            on_disk_resolved = on_disk.resolve()
        except OSError:
            return tarinfo
        try:
            on_disk_resolved.relative_to(archives_dir_resolved)
        except ValueError:
            return tarinfo
        return None

    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(data_dir, arcname=data_dir.name, filter=_skip_archives)
    return archive_path


@org_group.command("destroy")
@click.option("--data-dir", type=click.Path(file_okay=False, path_type=Path), default=None,
              help="Org dir to destroy (default: ~/.soul/, or $SOUL_DATA_DIR).")
@click.option("--archives-dir", type=click.Path(file_okay=False, path_type=Path), default=None,
              help="Where to drop the tarball (default: ~/.soul-archives/, a sibling of the org dir — "
                   "so the archive survives the wipe that follows).")
@click.option("--confirm", is_flag=True, help="Required guard rail #1.")
@click.option("--i-mean-it", "i_mean_it", is_flag=True, help="Required guard rail #2.")
@click.option("--non-interactive", is_flag=True,
              help="Skip the typed confirmation prompt (use with care).")
def org_destroy(
    data_dir: Path | None,
    archives_dir: Path | None,
    confirm: bool,
    i_mean_it: bool,
    non_interactive: bool,
) -> None:
    """Tarball and wipe the org directory. Terminal — there is no undo.

    Requires both ``--confirm`` and ``--i-mean-it``. In interactive mode you
    must also type the org name to proceed. The org is archived to the
    archives dir first; only then is the original removed.
    """
    data_dir = Path(data_dir) if data_dir else _default_data_dir()
    archives_dir = Path(archives_dir) if archives_dir else _default_archives_dir()

    if not (confirm and i_mean_it):
        click.echo(
            "error: refusing to destroy. Pass both --confirm and --i-mean-it.",
            err=True,
        )
        sys.exit(1)

    if not data_dir.exists():
        click.echo(f"error: {data_dir} does not exist", err=True)
        sys.exit(1)

    try:
        snap = _gather_status(data_dir)
    except FileNotFoundError:
        snap = {"org_name": None, "event_count": 0, "user_count": 0, "agent_count": 0}

    org_name = snap.get("org_name") or data_dir.name
    console.print(Panel(
        f"[bold red]About to destroy:[/bold red] {data_dir}\n"
        f"Org name:    {org_name}\n"
        f"Events lost: {snap['event_count']}\n"
        f"Users lost:  {snap['user_count']}\n"
        f"Agents lost: {snap['agent_count']}\n\n"
        "A tarball will be written to the archives dir before deletion.",
        title="Org destroy", border_style="red",
    ))

    if not non_interactive:
        typed = click.prompt(f"Type '{org_name}' to proceed", type=str)
        if typed.strip() != org_name:
            click.echo("error: confirmation text did not match. Aborting.", err=True)
            sys.exit(1)

    archive_path = _archive_org(data_dir, archives_dir)
    console.print(f"[green]Archived[/green] {archive_path}")
    shutil.rmtree(data_dir)
    console.print(f"[yellow]Removed[/yellow] {data_dir}")


# --- user invite (placeholder) -------------------------------------------


@user_group.command("invite")
@click.argument("email")
def user_invite(email: str) -> None:
    """Placeholder — real invite flow ships in a follow-up PR."""
    console.print(
        f"[yellow]Not yet implemented.[/yellow] Would invite [cyan]{email}[/cyan].\n"
        "Tracking issue: see Org Architecture RFC #164, step 8."
    )
    sys.exit(1)
