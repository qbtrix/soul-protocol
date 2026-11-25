# cli/consent.py — `soul consent {grant,list,revoke,log}`: manage consent passes.
# Created: 2026-11-14 — Owner-side commands for consent passes
#   (runtime/consent). `grant` prints the app token once; `list` shows passes
#   without tokens; `revoke` takes effect on the app's next request; `log`
#   prints the consent access log and, with --verify, checks every line
#   against the signed trust chain.
# Updated: 2026-11-14 (review) — Escape app-supplied text before Rich renders
#   it (a domain like "[/bold]" crashed the tables). --password works on every
#   command for encrypted .soul files, and saves re-encrypt with it. --verify
#   also reports signed entries missing from the log.
# Updated: 2026-11-25 (#326 review) — Uses soul.consent (ConsentManager);
#   `log --verify` also reports pruned lines and folded denials. Docs note that a
#   .soul file exported without its private key cannot grant or serve passes.

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

console = Console()


_PASSWORD_HELP = "Decrypt (and re-encrypt on save) a password-protected .soul file."


def _password(flag: bool) -> str | None:
    return click.prompt("Soul password", hide_input=True) if flag else None


async def _load(path: str, password: str | None = None):
    from soul_protocol.cli.main import _awaken_or_fail

    return await _awaken_or_fail(path, password=password)


async def _save(soul, path: str, password: str | None = None) -> None:
    # Keep the private key: without it the soul cannot sign future grants or reads.
    if Path(path).is_dir():
        await soul.save_local(path)
    else:
        await soul.export(path, include_keys=True, password=password)


def _short_time(iso: str | None) -> str:
    return iso[:16].replace("T", " ") if iso else "-"


_STATUS_STYLE = {"active": "green", "expired": "yellow", "revoked": "red"}


@click.group("consent")
def consent_group():
    """Give apps time-limited access to chosen memory domains."""


@consent_group.command("grant")
@click.argument("path", type=click.Path(exists=True))
@click.option("--password", "-p", "use_password", is_flag=True, help=_PASSWORD_HELP)
@click.option("--app", "app_id", required=True, help="App id, e.g. fitness-app.")
@click.option(
    "--domain",
    "domains",
    multiple=True,
    required=True,
    help="Memory domain the app may use. Repeat for more than one.",
)
@click.option(
    "--for",
    "duration",
    default="7d",
    show_default=True,
    help="How long the pass lasts: 30m, 12h, 7d, 2w (max 365d).",
)
@click.option(
    "--access",
    type=click.Choice(["read", "read-write"]),
    default="read",
    show_default=True,
    help="read, or read-write to also let the app store memories.",
)
@click.option("--note", default="", help="Optional note shown in listings.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit machine-readable JSON.")
def consent_grant(path, use_password, app_id, domains, duration, access, note, as_json):
    """Grant an app a consent pass and print its token (shown once).

    \b
    Examples:
      soul consent grant .soul/ --app fitness-app --domain health --for 7d
      soul consent grant aria.soul --app notes --domain work --domain ideas --access read-write
    """
    from soul_protocol.runtime.exceptions import ConsentError

    password = _password(use_password)

    async def _grant():
        soul = await _load(path, password)
        try:
            consent_pass, token = soul.consent.grant(
                app_id,
                list(domains),
                duration=duration,
                access=access.replace("-", "_"),
                note=note,
            )
        except ConsentError as exc:
            console.print(f"[red]Error:[/red] {escape(str(exc))}")
            sys.exit(1)
        await _save(soul, path, password)

        view = consent_pass.public_view()
        if as_json:
            console.print_json(data={"soul": soul.name, "pass": view, "token": token})
            return
        console.print(
            Panel(
                f"[bold]{escape(view['app_id'])}[/bold] can use "
                f"[cyan]{escape(', '.join(view['domains']))}[/cyan] ({view['access']})\n"
                f"until [magenta]{_short_time(view['expires_at'])} UTC[/magenta]\n\n"
                f"  Pass id  {view['id']}\n"
                f"  Token    [bold yellow]{token}[/bold yellow]\n\n"
                "[dim]Give the token to the app. It is not stored and cannot be "
                "shown again.[/dim]",
                title="Consent Granted",
                border_style="green",
            )
        )

    asyncio.run(_grant())


@consent_group.command("list")
@click.argument("path", type=click.Path(exists=True))
@click.option("--password", "-p", "use_password", is_flag=True, help=_PASSWORD_HELP)
@click.option("--all", "include_inactive", is_flag=True, help="Include expired and revoked passes.")
@click.option("--app", "app_id", default=None, help="Only passes for this app.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit machine-readable JSON.")
def consent_list(path, use_password, include_inactive, app_id, as_json):
    """List consent passes (active only unless --all). Tokens are never shown."""

    password = _password(use_password)

    async def _list():
        soul = await _load(path, password)
        views = [
            p.public_view()
            for p in soul.consent.passes(include_inactive=include_inactive, app_id=app_id)
        ]
        if as_json:
            console.print_json(data={"soul": soul.name, "passes": views})
            return
        if not views:
            which = "" if include_inactive else "active "
            console.print(f"[yellow]No {which}consent passes for {escape(soul.name)}.[/yellow]")
            return
        table = Table(title=f"{soul.name} — Consent Passes")
        table.add_column("Pass id", style="cyan")
        table.add_column("App", style="bold")
        table.add_column("Domains")
        table.add_column("Access")
        table.add_column("Status")
        table.add_column("Expires (UTC)", style="dim")
        table.add_column("Note", style="dim")
        for v in views:
            status = v["status"] if v["signature_valid"] else f"{v['status']} (bad signature)"
            style = _STATUS_STYLE.get(v["status"], "white") if v["signature_valid"] else "red"
            table.add_row(
                v["id"],
                escape(v["app_id"]),
                escape(", ".join(v["domains"])),
                v["access"],
                f"[{style}]{status}[/{style}]",
                _short_time(v["expires_at"]),
                escape(v["note"]),
            )
        console.print(table)

    asyncio.run(_list())


@consent_group.command("revoke")
@click.argument("path", type=click.Path(exists=True))
@click.option("--password", "-p", "use_password", is_flag=True, help=_PASSWORD_HELP)
@click.argument("pass_id")
@click.option("--reason", default="", help="Optional reason, kept in the access log.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit machine-readable JSON.")
def consent_revoke(path, use_password, pass_id, reason, as_json):
    """Revoke a consent pass. The app's next request is refused."""
    from soul_protocol.runtime.exceptions import ConsentError

    password = _password(use_password)

    async def _revoke():
        soul = await _load(path, password)
        try:
            consent_pass = soul.consent.revoke(pass_id, reason=reason)
        except ConsentError as exc:
            console.print(f"[red]Error:[/red] {escape(str(exc))}")
            sys.exit(1)
        await _save(soul, path, password)
        view = consent_pass.public_view()
        if as_json:
            console.print_json(data={"soul": soul.name, "pass": view})
            return
        console.print(
            f"[green]Revoked[/green] {view['id']} ([bold]{escape(view['app_id'])}[/bold]). "
            "Its next request will be refused."
        )

    asyncio.run(_revoke())


@consent_group.command("log")
@click.argument("path", type=click.Path(exists=True))
@click.option("--password", "-p", "use_password", is_flag=True, help=_PASSWORD_HELP)
@click.option("--limit", type=int, default=50, show_default=True, help="Most recent N events.")
@click.option("--app", "app_id", default=None, help="Only events for this app.")
@click.option(
    "--verify",
    is_flag=True,
    default=False,
    help="Check every log line against the signed trust chain.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit machine-readable JSON.")
def consent_log(path, use_password, limit, app_id, verify, as_json):
    """Show what each app was granted, read, wrote, or was refused."""

    password = _password(use_password)

    async def _log():
        soul = await _load(path, password)
        events = [e.public_view() for e in soul.consent.events(limit=max(0, limit), app_id=app_id)]
        report = None
        if verify:
            chain_ok, chain_failure = soul.verify_chain()
            log_report = soul.consent.verify()
            report = {
                "chain_valid": chain_ok,
                "chain_failure": chain_failure,
                "total": log_report["total"],
                "verified": log_report["verified"],
                "unverified": log_report["unverified"],
                "pruned": log_report["pruned"],
                "pending_denials": log_report["pending_denials"],
                "unknown_token_denials": log_report["unknown_token_denials"],
                "missing": log_report["missing"],
                "missing_entries": log_report["missing_entries"],
                "ok": chain_ok and log_report["ok"],
            }
        if as_json:
            data = {"soul": soul.name, "events": events}
            if report is not None:
                data["verification"] = report
            console.print_json(data=data)
            if report is not None and not report["ok"]:
                sys.exit(1)
            return

        if not events:
            console.print(f"[yellow]No consent events for {escape(soul.name)}.[/yellow]")
        else:
            table = Table(title=f"{soul.name} — Consent Log")
            table.add_column("When (UTC)", style="dim")
            table.add_column("Event", style="bold")
            table.add_column("App")
            table.add_column("Domains")
            table.add_column("Count", justify="right")
            table.add_column("Details", style="dim")
            table.add_column("Chain", justify="right", style="cyan")
            styles = {"denied": "red", "revoke": "yellow", "grant": "green"}
            for e in events:
                style = styles.get(e["kind"], "white")
                table.add_row(
                    _short_time(e["at"]),
                    f"[{style}]{e['kind']}[/{style}]",
                    escape(e["app_id"] or "unknown"),
                    escape(", ".join(e["domains"])),
                    str(e["count"]) if e["kind"] in ("read", "write", "denied") else "",
                    escape(e["reason"]),
                    "-" if e["chain_seq"] is None else str(e["chain_seq"]),
                )
            console.print(table)

        if report is not None:
            ok = report["ok"]
            color = "green" if ok else "red"
            console.print(
                f"[{color}]Trust chain {'valid' if report['chain_valid'] else 'INVALID'}; "
                f"{report['verified']} of {report['total']} log lines match signed entries."
                f"[/{color}]"
            )
            if report["pruned"]:
                console.print(
                    f"[yellow]{report['pruned']} log lines point at chain entries removed by "
                    "chain pruning; they can no longer be checked.[/yellow]"
                )
            folded = report["pending_denials"] + report["unknown_token_denials"]
            if folded:
                console.print(
                    f"[dim]{report['pending_denials']} repeated denials are waiting to be folded "
                    f"into the next log line; {report['unknown_token_denials']} requests used an "
                    "unknown token (counted, not logged).[/dim]"
                )
            if report["missing"]:
                console.print(
                    f"[red]{report['missing']} signed consent entries are missing from the "
                    "log (deleted or edited lines):[/red]"
                )
                for entry in report["missing_entries"]:
                    console.print(
                        f"[red]  seq {entry['seq']} {entry['action']}: "
                        f"{escape(entry['summary'] or '')}[/red]"
                    )
            if report["chain_failure"]:
                console.print(f"[red]{escape(report['chain_failure'])}[/red]")
            if not ok:
                sys.exit(1)

    asyncio.run(_log())
