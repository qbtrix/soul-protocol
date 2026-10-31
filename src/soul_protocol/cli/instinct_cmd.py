# cli/instinct_cmd.py — `soul instinct`: try Soul Instinct against a soul, read-only.
# Created: feat/soul-instinct — Loads a soul plus the local NLI decider once, then
#   compares the old rules with Soul Instinct for each message (which memory it
#   would replace, and how sure it is). Interactive by default so every answer
#   after the one-time model load is instant. Never saves the soul.
#   Finds the soul automatically when run inside a folder holding one, and
#   accepts the nested ``name.soul/<did>/`` layout that ``soul save`` produces.
# Updated: feat/soul-instinct (#322 review) — Model-loading quieting is a context
#   manager now: HF env vars, the warnings filter and the log level are restored
#   when the command ends instead of leaking into the process. The first run
#   prints a one-line notice with the download size before fetching the models.

from __future__ import annotations

import asyncio
import logging
import os
import time
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import click
from rich.console import Console

console = Console()

_NLI_MODELS = ("cross-encoder--nli-deberta-v3-xsmall", "sentence-transformers--all-MiniLM-L6-v2")
# Combined download size of _NLI_MODELS (weights + tokenizers, measured).
_NLI_DOWNLOAD_SIZE = "about 380 MB"
_QUIET_ENV = {
    "TRANSFORMERS_VERBOSITY": "error",
    "HF_HUB_DISABLE_PROGRESS_BARS": "1",
    "TOKENIZERS_PARALLELISM": "false",
}


def _find_soul(path: str | None) -> Path:
    """Resolve PATH (or the current folder) to something Soul.awaken() accepts."""
    if path is None:
        here = Path.cwd()
        found = sorted(p for p in here.glob("*.soul") if not p.name.startswith("."))
        if (here / "soul.json").exists():
            return here
        if len(found) != 1:
            names = ", ".join(p.name for p in found) or "none"
            raise click.UsageError(
                f"Can't pick a soul automatically (found: {names}). "
                "Pass one, e.g. `soul instinct shekhar.soul`."
            )
        target = found[0]
    else:
        target = Path(path)
    # `soul save` writes name.soul/<did>/soul.json — step into the single child.
    if target.is_dir() and not (target / "soul.json").exists():
        inner = [d for d in target.iterdir() if d.is_dir() and (d / "soul.json").exists()]
        if len(inner) == 1:
            return inner[0]
    return target


def _hf_hub() -> Path:
    return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"


def _models_cached() -> bool:
    hub = _hf_hub()
    return all((hub / f"models--{m}").exists() for m in _NLI_MODELS)


@contextmanager
def _quiet_model_loading() -> Iterator[None]:
    """Hide model-loading noise and skip network checks when models are cached.

    The env vars, warnings filter and soul_protocol log level it changes are
    put back on exit, so code running the command in-process is not affected.
    """
    env = dict(_QUIET_ENV)
    if _models_cached():
        env["HF_HUB_OFFLINE"] = "1"
    saved_env = {key: os.environ.get(key) for key in env}
    for key, value in env.items():
        os.environ.setdefault(key, value)
    soul_logger = logging.getLogger("soul_protocol")
    saved_level = soul_logger.level
    soul_logger.setLevel(logging.ERROR)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield
    finally:
        soul_logger.setLevel(saved_level)
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _quiet_transformers() -> None:
    """Silence transformers' own logger; call once sentence_transformers is imported."""
    try:
        from transformers.utils import logging as hf_logging

        hf_logging.set_verbosity_error()
        hf_logging.disable_progress_bar()
    except Exception:
        pass


def _verdict(decision, facts: dict[str, str]) -> str:
    if not decision.value.findings:
        return "[dim]no change[/dim]"
    return "; ".join(
        f'[yellow]replaces[/yellow] "{facts.get(f.old_memory_id, f.old_memory_id)}" '
        f"[bold]{f.confidence:.0%}[/bold]"
        for f in decision.value.findings
    )


def register(cli):
    """Register the ``soul instinct`` command on the given Click group."""

    @cli.command("instinct")
    @click.argument("path", required=False, type=click.Path(exists=True))
    @click.option(
        "-m",
        "--message",
        "messages",
        multiple=True,
        help="Check this message and exit (repeatable)",
    )
    @click.option(
        "--alias",
        "aliases",
        multiple=True,
        help="Name that means 'you' in memories (default: the soul's name)",
    )
    @click.option("--password", default=None, help="Password for an encrypted .soul file")
    def instinct_cmd(path, messages, aliases, password):
        """Try Soul Instinct on a soul — read-only, nothing is saved.

        Shows, for each message, what the old rules and the local AI would
        replace, and how sure the AI is. Without -m it is interactive: the
        AI loads once and every answer after that is instant.

        \b
        Examples:
          soul instinct                       # soul in the current folder
          soul instinct shekhar.soul
          soul instinct shekhar.soul -m "I hate dosa now"
        """
        # Entered before any ML import: the env vars are read at import time.
        with _quiet_model_loading():
            try:
                import sentence_transformers  # noqa: F401
            except ImportError:
                console.print(
                    "[red]Error:[/red] Soul Instinct's local AI is not installed.\n"
                    "Install it with: [cyan]pip install 'soul-protocol[embeddings-st]'[/cyan]"
                )
                raise SystemExit(1) from None
            _quiet_transformers()
            if not _models_cached():
                console.print(
                    f"[yellow]First run:[/yellow] downloading the local AI models "
                    f"({_NLI_DOWNLOAD_SIZE}) to {_hf_hub()}. Later runs work offline."
                )
            asyncio.run(_run(_find_soul(path), list(messages), list(aliases), password))


async def _run(path: Path, messages: list[str], aliases: list[str], password: str | None) -> None:
    from soul_protocol.cli.main import _awaken_or_fail
    from soul_protocol.runtime.decide import NLIContradictionDecider

    start = time.perf_counter()
    with console.status("Loading soul and local AI (one time)..."):
        old = await _awaken_or_fail(path, password)
        decider = NLIContradictionDecider()
        smart = await _awaken_or_fail(path, password)
        smart.use_deciders([decider])
        # In memory only: "<name> loves ..." is about you.
        smart.instinct.settings.user_aliases = aliases or [smart.name]
        await asyncio.to_thread(decider._get_embedder()._load_model)
        await asyncio.to_thread(decider._get_model)
    facts = {f.id: f.content for f in smart.memory.semantic_facts()}
    console.print(
        f"[green]Ready[/green] — {smart.name}, {len(facts)} memories "
        f"[dim](loaded in {time.perf_counter() - start:.1f} s, read-only)[/dim]"
    )

    async def check(message: str) -> None:
        t = time.perf_counter()
        rules = await old.decide("contradiction", message)
        model = await smart.decide("contradiction", message)
        took = (time.perf_counter() - t) * 1000
        console.print(f'\n[bold]"{message}"[/bold]')
        console.print(f"  Old rules : {_verdict(rules, facts)}")
        console.print(f"  Instinct  : {_verdict(model, facts)}   [dim]({took:.0f} ms)[/dim]")

    if messages:
        for message in messages:
            await check(message)
        return

    console.print("[dim]Type a message and press Enter. Empty line or 'exit' to quit.[/dim]")
    while True:
        try:
            message = console.input("\n[green]You:[/green] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message or message.lower() in {"exit", "quit"}:
            break
        await check(message)
    console.print("\n[dim]Bye. Your soul was not modified.[/dim]")
