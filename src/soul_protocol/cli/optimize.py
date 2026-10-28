# cli/optimize.py — `soul optimize` CLI: run the autonomous improvement loop.
# Created: 2026-04-29 (#142) — Wires the optimize loop into the soul CLI.
#   Two arguments: a soul file path and an eval YAML path. Loads the
#   soul, runs the eval-improve-eval loop, prints a Rich table of steps
#   plus a final summary. Defaults to dry-run (``--apply`` to keep the
#   winning trajectory). ``--engine module:Class`` wires a CognitiveEngine
#   for judge cases + LLM-assisted proposals.
#
# Output:
#   - Default: per-iteration Rich table (knob, before, after, score
#     change, kept), plus a summary line with baseline -> final.
#   - ``--json``: full OptimizeResult Pydantic dump for machine consumers.

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _resolve_engine(spec: str | None):
    """Load a CognitiveEngine from a ``module:attr`` string.

    Mirrors :func:`soul_protocol.cli.eval_cmd._resolve_engine` — if the
    attribute is a class, instantiate it; if it's a callable, call it.
    """
    if not spec:
        return None
    if ":" not in spec:
        raise click.BadParameter(
            f"--engine must be 'module:attr', got {spec!r}",
            param_hint="--engine",
        )
    module_name, attr = spec.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        raise click.BadParameter(
            f"could not import {module_name}: {e}",
            param_hint="--engine",
        ) from e
    obj = getattr(module, attr, None)
    if obj is None:
        raise click.BadParameter(
            f"{module_name} has no attribute {attr!r}",
            param_hint="--engine",
        )
    if isinstance(obj, type):
        return obj()
    if callable(obj):
        return obj()
    return obj


def _format_value(v) -> str:
    """Render a knob value for the Rich table without overflowing the column."""
    if isinstance(v, str):
        s = v.replace("\n", " ")
        return (s[:60] + "...") if len(s) > 60 else s
    if isinstance(v, list):
        return "[" + ", ".join(_format_value(x) for x in v) + "]"
    if isinstance(v, float):
        return f"{v:.3f}"
    return repr(v)


def _render_steps_table(result) -> Table:
    """Render an OptimizeResult's steps as a Rich table."""
    table = Table(
        title=f"{result.spec_name} — optimize trajectory",
        show_lines=False,
        title_style="bold",
    )
    table.add_column("It", justify="right")
    table.add_column("Knob", style="cyan", overflow="fold")
    table.add_column("Before", overflow="fold")
    table.add_column("After", overflow="fold")
    table.add_column("Δ", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Kept", justify="center")

    for step in result.steps:
        delta = step.delta
        delta_str = f"{delta:+.3f}" if delta else "0.000"
        delta_color = "green" if delta > 0 else ("red" if delta < 0 else "dim")
        kept_str = "[green]YES[/]" if step.kept else "[red]no[/]"
        table.add_row(
            str(step.iteration),
            step.knob_name,
            _format_value(step.before),
            _format_value(step.after),
            f"[{delta_color}]{delta_str}[/]",
            f"{step.score_before:.3f}→{step.score_after:.3f}",
            kept_str,
        )
    return table


def _print_summary(result) -> None:
    """Render a one-line summary of the final state."""
    delta = result.final_score - result.baseline_score
    delta_color = "green" if delta > 0 else ("yellow" if delta == 0 else "red")
    convergence = (
        f"converged at iter {result.convergence_iteration}"
        if result.convergence_iteration is not None
        else f"ran {result.iterations_run}/{result.iterations_run} iters"
    )
    console.print(
        f"[bold]baseline {result.baseline_score:.3f}[/bold] → "
        f"[bold]{result.final_score:.3f}[/bold] "
        f"([{delta_color}]{delta:+.3f}[/{delta_color}]) · "
        f"{convergence} · "
        f"{len(result.knobs_touched)} knob(s) touched · "
        f"{result.duration_ms / 1000:.2f}s · "
        f"{'APPLIED' if result.applied else 'dry-run'}"
    )


def register(cli):
    """Register the ``soul optimize`` command on the given Click group."""

    @cli.command("optimize")
    @click.argument("soul_path", type=click.Path(exists=True))
    @click.argument("eval_spec_path", type=click.Path(exists=True))
    @click.option(
        "--iterations",
        "-n",
        type=int,
        default=10,
        show_default=True,
        help="Maximum optimization iterations.",
    )
    @click.option(
        "--target",
        "target_score",
        type=float,
        default=1.0,
        show_default=True,
        help="Stop early when the eval score reaches this threshold.",
    )
    @click.option(
        "--apply",
        is_flag=True,
        default=False,
        help=(
            "Keep the winning trajectory and append soul.optimize.applied trust "
            "chain entries. Default is dry-run — every change reverts at end."
        ),
    )
    @click.option(
        "--engine",
        "engine_spec",
        default=None,
        help=(
            "Engine for judge cases / LLM-assisted proposer as 'module:attr' "
            "(e.g. soul_protocol.runtime.cognitive.engine:HeuristicEngine)."
        ),
    )
    @click.option(
        "--json",
        "as_json",
        is_flag=True,
        default=False,
        help="Emit the full OptimizeResult as JSON.",
    )
    def optimize_cmd(
        soul_path, eval_spec_path, iterations, target_score, apply, engine_spec, as_json
    ):
        """Run the autonomous improvement loop against a soul.

        \b
        Examples:
          soul optimize aria.soul tests/eval_examples/personality_expression.yaml
          soul optimize aria.soul eval.yaml --iterations 20 --target 0.9
          soul optimize aria.soul eval.yaml --apply
          soul optimize aria.soul eval.yaml --json

        Eval cases are scored, proposals are generated against failures,
        candidate knob changes are applied and re-scored. Improvements are
        kept; everything else is reverted. ``--apply`` keeps the winning
        trajectory in the soul (and on disk via the trust chain); the
        default dry-run leaves the soul byte-identical.
        """
        from soul_protocol.optimize import optimize as run_optimize  # lazy
        from soul_protocol.runtime.soul import Soul

        engine = _resolve_engine(engine_spec)

        async def _run():
            soul = await Soul.awaken(soul_path)
            if engine is not None:
                soul.set_engine(engine)
            result = await run_optimize(
                soul,
                eval_spec_path,
                iterations=iterations,
                target_score=target_score,
                engine=engine,
                apply=apply,
            )
            if apply:
                # Persist the winning trajectory plus any chain entries.
                # Round-trip back to the same path shape: zip files via
                # export(), unpacked directories via save_local().
                src = Path(soul_path)
                if src.is_file():
                    await soul.export(str(src), include_keys=True)
                else:
                    await soul.save_local(str(src))
            return result

        try:
            result = asyncio.run(_run())
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(2)

        if as_json:
            console.print_json(data=result.model_dump(mode="json"))
            sys.exit(0 if result.improved or result.converged else 0)

        if result.steps:
            console.print(_render_steps_table(result))
        else:
            console.print(
                "[yellow]No proposals were generated — baseline already at target "
                "or no knob has candidates.[/]"
            )
        _print_summary(result)
        # Soft success — the loop is informational; we don't fail the CLI
        # when a soul doesn't improve. Use --json + jq for hard checks.
        sys.exit(0)

    return optimize_cmd
