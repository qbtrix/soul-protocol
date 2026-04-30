# cli/journal.py — `soul journal {init,append,query}` shell-hook subcommand (#189).
# Created: feat/soul-journal-cli — Wrap the existing org-level journal engine
#   (engine/journal) for shell hooks, CI scripts, and non-Python runtimes that
#   want to append structured events without spinning up a Python session.
#
# Three subcommands cover the shell cases:
#   - `soul journal init <path>` — bootstrap a standalone SQLite WAL journal
#     file. Distinct from `soul org init`: no root soul, no founder, no scope
#     tree. Useful for an event log without the full org bootstrap.
#   - `soul journal append <path>` — append one event built from --action,
#     --actor, --payload, --scope, --causation-id flags. Supports --stdin to
#     batch JSONL events into a single transaction. Echoes the committed
#     EventEntry to stdout (with backend-assigned seq + prev_hash).
#   - `soul journal query <path>` — query events with --action / --action-prefix,
#     --since / --until / --at (point-in-time replay), --scope, --limit. Default
#     output is a Rich table; --json emits a JSON array of EventEntry records.
#
# Reuses spec/journal.py (Actor, EventEntry, DataRef) and engine/journal
# (open_journal, Journal). No new storage format — straight wrapper over the
# Python API the engine already ships.

from __future__ import annotations

import json as _json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import click
from rich.console import Console
from rich.table import Table

from soul_protocol.engine.journal import open_journal
from soul_protocol.engine.journal.exceptions import IntegrityError, JournalError
from soul_protocol.spec.journal import Actor, EventEntry

console = Console()


# --- Helpers --------------------------------------------------------------


def _parse_iso_utc(value: str, *, flag: str) -> datetime:
    """Parse an ISO 8601 timestamp; promote naive datetimes to UTC.

    Naive timestamps are commonly produced by shell tools that don't bother
    with offsets. We accept them and stamp UTC so callers don't need a
    tz-aware date util on the shell side.
    """
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise click.BadParameter(f"{flag}: not an ISO 8601 timestamp ({exc})") from exc
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _parse_actor(raw: str | None) -> Actor:
    """Build an Actor from a JSON blob; default to {kind: 'system', id: 'cli'}.

    Shell hooks that don't know better should still produce a valid event;
    the default actor lets callers pass --action and skip the rest.
    """
    if not raw:
        return Actor(kind="system", id="cli")
    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError as exc:
        raise click.BadParameter(f"--actor: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise click.BadParameter("--actor: must be a JSON object")
    try:
        return Actor.model_validate(data)
    except Exception as exc:
        raise click.BadParameter(f"--actor: {exc}") from exc


def _parse_payload(raw: str | None) -> dict:
    """Parse the --payload JSON blob; empty dict on omission."""
    if raw is None or raw == "":
        return {}
    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError as exc:
        raise click.BadParameter(f"--payload: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise click.BadParameter("--payload: must be a JSON object")
    return data


def _parse_uuid(raw: str | None, *, flag: str) -> UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return UUID(raw)
    except ValueError as exc:
        raise click.BadParameter(f"{flag}: not a valid UUID ({exc})") from exc


def _entry_to_dict(entry: EventEntry) -> dict[str, Any]:
    """Render an EventEntry as a JSON-serializable dict.

    Pydantic's mode='json' handles datetime, UUID, and bytes (base64 via the
    JournalBytes annotation), so the dict round-trips through json.dumps
    without further coaxing.
    """
    return entry.model_dump(mode="json")


# --- Group ----------------------------------------------------------------


@click.group("journal")
def journal_group() -> None:
    """Append-only event journal (shell-hook entry point for #189)."""


# --- init -----------------------------------------------------------------


@journal_group.command("init")
@click.argument("path", type=click.Path(path_type=Path))
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite an existing journal file at PATH.",
)
def journal_init(path: Path, force: bool) -> None:
    """Bootstrap a standalone SQLite WAL journal at PATH.

    \b
    Examples:
      soul journal init ./.journal.db
      soul journal init /tmp/ci-audit.db --force

    The journal is initialized empty — no genesis events. Use this for
    workspace session logs, CI audit trails, or migration scratch pads.
    For the full org bootstrap (root soul, scope tree, founder), see
    `soul org init`.
    """
    if path.exists() and not force:
        click.echo(
            f"error: {path} already exists. Pass --force to overwrite.",
            err=True,
        )
        sys.exit(1)
    if path.exists():
        # WAL leaves -wal and -shm sidecars; clean those too so the new
        # journal opens fresh.
        for sidecar in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
            if sidecar.exists():
                sidecar.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    journal = open_journal(path)
    try:
        # open_journal runs the schema migration on first connect; nothing
        # else to do. Close so the WAL flushes.
        pass
    finally:
        journal.close()
    click.echo(f"Initialized journal at {path}")


# --- append ---------------------------------------------------------------


@journal_group.command("append")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--action", "action", default=None, help="Dot-separated action name.")
@click.option(
    "--actor",
    "actor_raw",
    default=None,
    help='JSON object matching Actor, e.g. \'{"kind":"agent","id":"did:soul:claude"}\'. '
    'Defaults to {"kind":"system","id":"cli"}.',
)
@click.option(
    "--payload",
    "payload_raw",
    default=None,
    help="JSON object stored as the event payload.",
)
@click.option(
    "--scope",
    "scopes",
    multiple=True,
    help="Scope tag (repeatable). At least one required when not using --stdin.",
)
@click.option(
    "--causation-id",
    "causation_raw",
    default=None,
    help="UUID of the prior event that caused this one (for decision-trace chains).",
)
@click.option(
    "--correlation-id",
    "correlation_raw",
    default=None,
    help="UUID grouping this event with related events (session/flow id).",
)
@click.option(
    "--stdin",
    "use_stdin",
    is_flag=True,
    default=False,
    help="Read JSONL events from stdin (one JSON object per line) and batch them.",
)
def journal_append(
    path: Path,
    action: str | None,
    actor_raw: str | None,
    payload_raw: str | None,
    scopes: tuple[str, ...],
    causation_raw: str | None,
    correlation_raw: str | None,
    use_stdin: bool,
) -> None:
    """Append one or more events to the journal at PATH.

    \b
    Single-event mode (flags):
      soul journal append ./.journal.db \\
          --action session.pr.merged.pocketpaw \\
          --actor '{"kind":"agent","id":"did:soul:claude-code"}' \\
          --payload '{"pr":1021,"sha":"abc"}' \\
          --scope session:abc123 --scope repo:pocketpaw

    \b
    Stdin batch mode (one JSON object per line):
      cat events.jsonl | soul journal append ./.journal.db --stdin
      echo '{"action":"foo","scope":["s:1"],"payload":{}}' \\
          | soul journal append ./.journal.db --stdin

    Each stdin line accepts the same fields as the flag form
    (action, actor, payload, scope, causation_id, correlation_id).
    Missing optional fields fall back to the same defaults as the
    flag form. Stdin events all land in a single Journal session;
    failures on a line are reported with that line's number.

    Prints the committed EventEntry as JSON to stdout (one per line),
    with backend-assigned seq and prev_hash, so scripts can capture
    the event id for a follow-up causation_id chain.
    """
    if use_stdin:
        if action or payload_raw or actor_raw or scopes or causation_raw or correlation_raw:
            click.echo(
                "error: --stdin is mutually exclusive with --action / --actor / "
                "--payload / --scope / --causation-id / --correlation-id flags.",
                err=True,
            )
            sys.exit(2)
        _append_from_stdin(path)
        return

    if not action:
        click.echo("error: --action is required (or pass --stdin).", err=True)
        sys.exit(2)
    if not scopes:
        click.echo(
            "error: at least one --scope is required (events without scope are rejected).",
            err=True,
        )
        sys.exit(2)

    actor = _parse_actor(actor_raw)
    payload = _parse_payload(payload_raw)
    causation_id = _parse_uuid(causation_raw, flag="--causation-id")
    correlation_id = _parse_uuid(correlation_raw, flag="--correlation-id")

    entry = EventEntry(
        id=uuid4(),
        ts=datetime.now(UTC),
        actor=actor,
        action=action,
        scope=list(scopes),
        causation_id=causation_id,
        correlation_id=correlation_id,
        payload=payload,
    )

    journal = open_journal(path)
    try:
        committed = journal.append(entry)
    except (IntegrityError, JournalError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    finally:
        journal.close()

    click.echo(_json.dumps(_entry_to_dict(committed), default=str))


def _append_from_stdin(path: Path) -> None:
    """Read JSONL from stdin; append each line as a separate event in one
    Journal session.

    Lines are processed as they arrive (no buffering), but all events use
    the same Journal connection — opening once is faster than opening per
    line, and the WAL groups commits at flush time. A bad line aborts the
    batch with a non-zero exit so callers don't silently skip events.
    """
    journal = open_journal(path)
    committed: list[EventEntry] = []
    try:
        for line_no, raw in enumerate(sys.stdin, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = _json.loads(raw)
            except _json.JSONDecodeError as exc:
                click.echo(f"error: stdin line {line_no}: invalid JSON ({exc})", err=True)
                sys.exit(2)
            if not isinstance(obj, dict):
                click.echo(f"error: stdin line {line_no}: not a JSON object", err=True)
                sys.exit(2)

            action = obj.get("action")
            if not action or not isinstance(action, str):
                click.echo(f"error: stdin line {line_no}: missing or non-string 'action'", err=True)
                sys.exit(2)

            scope = obj.get("scope") or []
            if not isinstance(scope, list) or not scope:
                click.echo(
                    f"error: stdin line {line_no}: 'scope' must be a non-empty list",
                    err=True,
                )
                sys.exit(2)

            actor_data = obj.get("actor") or {"kind": "system", "id": "cli"}
            if not isinstance(actor_data, dict):
                click.echo(f"error: stdin line {line_no}: 'actor' must be a JSON object", err=True)
                sys.exit(2)
            try:
                actor = Actor.model_validate(actor_data)
            except Exception as exc:
                click.echo(f"error: stdin line {line_no}: actor — {exc}", err=True)
                sys.exit(2)

            payload = obj.get("payload") or {}
            if not isinstance(payload, dict):
                click.echo(
                    f"error: stdin line {line_no}: 'payload' must be a JSON object", err=True
                )
                sys.exit(2)

            ts_raw = obj.get("ts")
            ts = (
                _parse_iso_utc(ts_raw, flag=f"stdin line {line_no} 'ts'")
                if ts_raw
                else datetime.now(UTC)
            )

            try:
                entry = EventEntry(
                    id=uuid4() if not obj.get("id") else UUID(obj["id"]),
                    ts=ts,
                    actor=actor,
                    action=action,
                    scope=list(scope),
                    causation_id=_parse_uuid(obj.get("causation_id"), flag="causation_id"),
                    correlation_id=_parse_uuid(obj.get("correlation_id"), flag="correlation_id"),
                    payload=payload,
                )
            except Exception as exc:
                click.echo(f"error: stdin line {line_no}: {exc}", err=True)
                sys.exit(2)

            try:
                committed.append(journal.append(entry))
            except (IntegrityError, JournalError) as exc:
                click.echo(f"error: stdin line {line_no}: {exc}", err=True)
                sys.exit(1)
    finally:
        journal.close()

    for entry in committed:
        click.echo(_json.dumps(_entry_to_dict(entry), default=str))


# --- query ----------------------------------------------------------------


@journal_group.command("query")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--action", default=None, help="Exact action match.")
@click.option(
    "--action-prefix",
    "action_prefix",
    default=None,
    help="Match action and any descendant in the dotted namespace.",
)
@click.option(
    "--scope",
    "scopes",
    multiple=True,
    help="Scope tag to match (repeatable; conjunction).",
)
@click.option(
    "--correlation-id",
    "correlation_raw",
    default=None,
    help="Filter to a single correlation_id (session/flow id).",
)
@click.option(
    "--since",
    "since_raw",
    default=None,
    help="ISO 8601 timestamp lower bound (inclusive).",
)
@click.option(
    "--until",
    "until_raw",
    default=None,
    help="ISO 8601 timestamp upper bound (inclusive).",
)
@click.option(
    "--at",
    "at_raw",
    default=None,
    help="Point-in-time replay — only return events <= this ISO timestamp. "
    "Mutually exclusive with --until.",
)
@click.option("--limit", type=int, default=100, help="Max results (default 100).")
@click.option("--offset", type=int, default=0, help="Pagination offset.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON array.")
def journal_query(
    path: Path,
    action: str | None,
    action_prefix: str | None,
    scopes: tuple[str, ...],
    correlation_raw: str | None,
    since_raw: str | None,
    until_raw: str | None,
    at_raw: str | None,
    limit: int,
    offset: int,
    as_json: bool,
) -> None:
    """Query events from the journal at PATH.

    \b
    Examples:
      soul journal query ./.journal.db --action-prefix session.pr.
      soul journal query ./.journal.db --since 2026-04-24T00:00:00Z
      soul journal query ./.journal.db --at 2026-04-20T12:00:00Z
      soul journal query ./.journal.db --scope session:abc123 --limit 50 --json
    """
    if action and action_prefix:
        click.echo("error: --action and --action-prefix are mutually exclusive.", err=True)
        sys.exit(2)
    if at_raw and until_raw:
        click.echo("error: --at and --until are mutually exclusive.", err=True)
        sys.exit(2)
    # The engine treats action_prefix as a dotted namespace boundary: "session"
    # matches "session" and "session.X.Y". The issue's UX expects a trailing
    # dot to be tolerated ("session.pr."), so normalize before handing to the
    # engine — saves users from a silent empty-result trap.
    if action_prefix is not None and action_prefix.endswith("."):
        action_prefix = action_prefix.rstrip(".")

    since = _parse_iso_utc(since_raw, flag="--since") if since_raw else None
    until = _parse_iso_utc(until_raw, flag="--until") if until_raw else None
    if at_raw:
        until = _parse_iso_utc(at_raw, flag="--at")
    correlation_id = _parse_uuid(correlation_raw, flag="--correlation-id")

    journal = open_journal(path)
    try:
        events = journal.query(
            action=action,
            action_prefix=action_prefix,
            scope=list(scopes) if scopes else None,
            correlation_id=correlation_id,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )
    except (IntegrityError, JournalError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    finally:
        journal.close()

    if as_json:
        click.echo(_json.dumps([_entry_to_dict(e) for e in events], default=str, indent=2))
        return

    if not events:
        scope_text = f" (scope filter: {', '.join(scopes)})" if scopes else ""
        action_text = ""
        if action:
            action_text = f" (action: {action})"
        elif action_prefix:
            action_text = f" (action prefix: {action_prefix})"
        click.echo(f"No events found{action_text}{scope_text}.")
        return

    table = Table(title=f"Journal — {path.name} ({len(events)} events)", border_style="cyan")
    table.add_column("Seq", style="cyan", justify="right")
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="bold")
    table.add_column("Actor")
    table.add_column("Scope", style="dim")
    for ev in events:
        ts = ev.ts.isoformat()
        # Trim microseconds for readable display while keeping tz info
        if "." in ts:
            head, sep, tail = ts.partition(".")
            tz_idx = tail.find("+")
            if tz_idx == -1:
                tz_idx = tail.find("-")
            tail_tz = tail[tz_idx:] if tz_idx != -1 else ""
            ts = f"{head}{tail_tz}"
        actor_text = f"{ev.actor.kind}:{ev.actor.id}"
        scope_text = ", ".join(ev.scope)
        table.add_row(
            str(ev.seq) if ev.seq is not None else "—",
            ts,
            ev.action,
            actor_text,
            scope_text,
        )
    console.print(table)
