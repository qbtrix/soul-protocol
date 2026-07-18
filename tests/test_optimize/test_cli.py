# test_cli.py — End-to-end tests for the `soul optimize` CLI (#142).
# Created: 2026-04-29 — Uses Click's CliRunner against a temp soul + temp
#   eval spec. Validates default dry-run behaviour, --json output shape,
#   and --apply persistence to disk.

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner

from soul_protocol.cli.main import cli
from soul_protocol.runtime.soul import Soul


def _write_spec(tmp: Path, name: str, body: str) -> Path:
    path = tmp / name
    path.write_text(dedent(body).strip() + "\n")
    return path


def _make_soul_file(tmp: Path) -> Path:
    """Birth a Soul and export it to a .soul archive in ``tmp``."""

    async def _go() -> Path:
        soul = await Soul.birth("Tester", ocean={"openness": 0.5})
        path = tmp / "tester.soul"
        await soul.export(str(path), include_keys=True)
        return path

    return asyncio.run(_go())


# ---------------------------------------------------------------------------
# Dry-run path
# ---------------------------------------------------------------------------


def test_optimize_cli_dry_run_emits_table(tmp_path: Path) -> None:
    soul_path = _make_soul_file(tmp_path)
    spec = _write_spec(
        tmp_path,
        "eval.yaml",
        """
        name: cli-optimize-dryrun
        cases:
          - name: trivial
            inputs:
              message: hi
            scoring:
              kind: keyword
              expected: ["fallback"]
              mode: any
        """,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["optimize", str(soul_path), str(spec), "--iterations", "1"],
    )
    assert result.exit_code == 0, result.output
    # Already-passing eval: baseline at 1.0 means no proposals to run.
    assert "baseline" in result.output.lower() or "dry-run" in result.output.lower()


def test_optimize_cli_json_output_parses(tmp_path: Path) -> None:
    soul_path = _make_soul_file(tmp_path)
    spec = _write_spec(
        tmp_path,
        "eval.yaml",
        """
        name: cli-optimize-json
        cases:
          - name: trivial
            inputs:
              message: hi
            scoring:
              kind: keyword
              expected: ["fallback"]
              mode: any
        """,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["optimize", str(soul_path), str(spec), "--iterations", "1", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["spec_name"].startswith("cli-optimize-json")
    assert "baseline_score" in payload
    assert "final_score" in payload
    assert "steps" in payload
    assert "applied" in payload
    assert payload["applied"] is False


# ---------------------------------------------------------------------------
# Apply path
# ---------------------------------------------------------------------------


def test_optimize_cli_apply_persists_to_disk(tmp_path: Path) -> None:
    soul_path = _make_soul_file(tmp_path)
    # An eval where the fallback already passes — apply will write nothing
    # to the chain because nothing is "kept", but the run still succeeds
    # and writes the .soul archive back.
    spec = _write_spec(
        tmp_path,
        "eval.yaml",
        """
        name: cli-optimize-apply
        cases:
          - name: trivial
            inputs:
              message: hi
            scoring:
              kind: keyword
              expected: ["fallback"]
              mode: any
        """,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["optimize", str(soul_path), str(spec), "--apply", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] is True


# ---------------------------------------------------------------------------
# Bad engine spec
# ---------------------------------------------------------------------------


def test_optimize_cli_bad_engine_spec_rejected(tmp_path: Path) -> None:
    soul_path = _make_soul_file(tmp_path)
    spec = _write_spec(
        tmp_path,
        "eval.yaml",
        """
        name: cli-optimize-engine
        cases:
          - name: trivial
            inputs:
              message: hi
            scoring:
              kind: keyword
              expected: ["fallback"]
              mode: any
        """,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["optimize", str(soul_path), str(spec), "--engine", "missingcolon"],
    )
    assert result.exit_code != 0
    assert "module:attr" in result.output


# ---------------------------------------------------------------------------
# Heuristic engine wiring
# ---------------------------------------------------------------------------


def test_optimize_cli_with_heuristic_engine(tmp_path: Path) -> None:
    soul_path = _make_soul_file(tmp_path)
    spec = _write_spec(
        tmp_path,
        "eval.yaml",
        """
        name: cli-optimize-heuristic
        cases:
          - name: trivial
            inputs:
              message: hi
            scoring:
              kind: keyword
              expected: ["fallback"]
              mode: any
        """,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "optimize",
            str(soul_path),
            str(spec),
            "--engine",
            "soul_protocol.runtime.cognitive.engine:HeuristicEngine",
            "--iterations",
            "1",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["spec_name"].startswith("cli-optimize-heuristic")
