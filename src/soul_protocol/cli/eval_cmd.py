# cli/eval_cmd.py — `soul eval` command for running YAML-driven soul evals.
# Created: 2026-04-29 (#160) — Wires the eval framework into the soul CLI.
#   Single command: ``soul eval <path>`` runs one spec file or every .yaml
#   in a directory. Output is a Rich table per spec with a summary footer.
#   Exit code 0 when every case passes (skipped cases don't fail the run);
#   exit 1 when any case fails or errors.

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _discover_specs(target: Path) -> list[Path]:
    """Return sorted .yaml/.yml paths under ``target``.

    A file argument resolves to itself. A directory argument resolves to
    every .yaml/.yml beneath it (recursive). Hidden files are skipped.
    """
    if target.is_file():
        return [target]
    paths: list[Path] = []
    for ext in ("*.yaml", "*.yml"):
        paths.extend(target.rglob(ext))
    return sorted(p for p in paths if not p.name.startswith("."))


def _resolve_engine(spec: str | None):
    """Load a CognitiveEngine from a ``module:attr`` string.

    Examples:

    - ``soul_protocol.runtime.cognitive.engine:HeuristicEngine`` —
      instantiates :class:`HeuristicEngine` (zero-dep fallback).
    - ``my.module:make_engine`` — calls the callable; expects an
      engine instance back.
    """
    if not spec:
        return None
    if ":" not in spec:
        raise click.BadParameter(
            f"--judge-engine must be 'module:attr', got {spec!r}",
            param_hint="--judge-engine",
        )
    module_name, attr = spec.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        raise click.BadParameter(
            f"could not import {module_name}: {e}",
            param_hint="--judge-engine",
        ) from e
    obj = getattr(module, attr, None)
    if obj is None:
        raise click.BadParameter(
            f"{module_name} has no attribute {attr!r}",
            param_hint="--judge-engine",
        )
    if isinstance(obj, type):
        return obj()
    if callable(obj):
        return obj()
    return obj


def _render_result_table(result, *, verbose: bool) -> Table:
    """Render one EvalResult as a Rich table."""
    table = Table(
        title=f"{result.spec_name}",
        show_lines=False,
        title_style="bold",
    )
    table.add_column("Case", style="cyan", overflow="fold")
    table.add_column("Status", justify="center")
    table.add_column("Score", justify="right")
    table.add_column("Time", justify="right", style="dim")
    if verbose:
        table.add_column("Details", style="dim", overflow="fold")

    for case in result.cases:
        status = case.status
        if status == "pass":
            badge = "[green]PASS[/]"
        elif status == "fail":
            badge = "[red]FAIL[/]"
        elif status == "skip":
            badge = "[yellow]SKIP[/]"
        else:
            badge = "[red]ERR[/]"

        row = [
            case.name,
            badge,
            f"{case.score:.2f}",
            f"{case.duration_ms}ms",
        ]
        if verbose:
            if case.error:
                row.append(case.error)
            else:
                row.append(json.dumps(case.details, default=str)[:200])
        table.add_row(*row)
    return table


def _print_summary(results: list, *, total_ms: int) -> None:
    """Render the cross-spec summary footer."""
    pass_count = sum(r.pass_count for r in results)
    fail_count = sum(r.fail_count for r in results)
    skip_count = sum(r.skip_count for r in results)
    error_count = sum(r.error_count for r in results)
    spec_errors = sum(1 for r in results if r.error)
    total = sum(r.total for r in results)

    summary = (
        f"[bold]{len(results)}[/bold] specs, [bold]{total}[/bold] cases — "
        f"[green]{pass_count} pass[/green], "
        f"[red]{fail_count} fail[/red], "
        f"[yellow]{skip_count} skip[/yellow], "
        f"[red]{error_count} error[/red]"
    )
    if spec_errors:
        summary += f", [red]{spec_errors} spec failed to seed[/red]"
    summary += f"  ·  {total_ms / 1000:.2f}s"
    console.print(summary)


def register(cli):
    """Register the ``soul eval`` command on the given Click group.

    Done lazily from main.py so we don't pull eval imports until the
    command is touched. The function takes the cli group and attaches.
    """

    @cli.command("eval")
    @click.argument("target", type=click.Path(exists=True))
    @click.option(
        "--filter",
        "case_filter",
        default=None,
        help="Substring filter — only cases whose name contains this run.",
    )
    @click.option(
        "--judge-engine",
        "judge_engine",
        default=None,
        help=(
            "Engine for judge / respond cases as 'module:attr' (e.g. "
            "soul_protocol.runtime.cognitive.engine:HeuristicEngine). When "
            "unset, judge cases skip and respond cases use a fallback."
        ),
    )
    @click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON output.")
    @click.option(
        "--verbose",
        "-v",
        is_flag=True,
        default=False,
        help="Include per-case details / errors in table rows.",
    )
    def eval_cmd(target, case_filter, judge_engine, as_json, verbose):
        """Run YAML soul evals against a freshly seeded soul.

        \b
        Examples:
          soul eval tests/eval_examples/personality_expression.yaml
          soul eval tests/eval_examples/                          # all .yaml in dir
          soul eval tests/eval_examples/ --filter "creative"
          soul eval my_eval.yaml --json
          soul eval my_eval.yaml --judge-engine my.module:make_engine

        Exits 0 when every case passes (skipped cases do not fail the
        run); 1 when any case fails or any spec errors out.
        """
        from soul_protocol.eval import run_eval_file  # lazy import

        target_path = Path(target)
        spec_paths = _discover_specs(target_path)
        if not spec_paths:
            console.print(f"[yellow]No .yaml eval specs found under {target_path}[/]")
            sys.exit(0)

        engine = _resolve_engine(judge_engine)

        async def _run_all():
            results = []
            for path in spec_paths:
                try:
                    result = await run_eval_file(
                        path,
                        engine=engine,
                        case_filter=case_filter,
                    )
                    result.spec_name = f"{result.spec_name}  ({path.name})"
                    results.append(result)
                except Exception as e:
                    # Build a placeholder result so we still report the failure
                    from soul_protocol.eval.runner import EvalResult

                    placeholder = EvalResult(
                        spec_name=f"{path.name} (load error)",
                        error=f"{type(e).__name__}: {e}",
                    )
                    results.append(placeholder)
            return results

        import time

        started = time.monotonic()
        results = asyncio.run(_run_all())
        elapsed_ms = int((time.monotonic() - started) * 1000)

        if as_json:
            payload: dict[str, Any] = {
                "specs": [r.model_dump(mode="json") for r in results],
                "duration_ms": elapsed_ms,
                "pass_count": sum(r.pass_count for r in results),
                "fail_count": sum(r.fail_count for r in results),
                "skip_count": sum(r.skip_count for r in results),
                "error_count": sum(r.error_count for r in results),
            }
            console.print_json(data=payload)
        else:
            for result in results:
                if result.error:
                    console.print(f"[red]✗[/red] {result.spec_name} — {result.error}")
                    continue
                console.print(_render_result_table(result, verbose=verbose))
            _print_summary(results, total_ms=elapsed_ms)

        # Exit code: 0 only when all cases pass and no specs errored
        any_failure = any(r.error or r.fail_count > 0 or r.error_count > 0 for r in results)
        sys.exit(1 if any_failure else 0)
