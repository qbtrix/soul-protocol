# test_cli.py — End-to-end tests for the `soul eval` CLI command (#160).
# Created: 2026-04-29 — Uses Click's CliRunner to drive the real CLI
#   against tempdir fixtures and the shipped example YAMLs. Validates
#   exit codes (0 on all-pass, 1 on any-fail), --json output shape, and
#   --filter narrowing.

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner

from soul_protocol.cli.main import cli

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "eval_examples"


def _write_spec(tmp: Path, name: str, body: str) -> Path:
    """Drop a YAML spec into ``tmp`` and return the path."""
    path = tmp / name
    path.write_text(dedent(body).strip() + "\n")
    return path


# ---------------------------------------------------------------------------
# Single-file run
# ---------------------------------------------------------------------------


def test_eval_passing_spec_exits_zero(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path,
        "passing.yaml",
        """
        name: cli-passing
        cases:
          - name: keyword_pass
            inputs:
              message: hello
            scoring:
              kind: keyword
              expected: ["fallback"]
              mode: any
        """,
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", str(spec)])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


def test_eval_failing_spec_exits_one(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path,
        "failing.yaml",
        """
        name: cli-failing
        cases:
          - name: keyword_miss
            inputs:
              message: hello
            scoring:
              kind: keyword
              expected: ["does-not-appear-anywhere"]
              threshold: 1.0
        """,
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", str(spec)])
    assert result.exit_code == 1, result.output
    assert "FAIL" in result.output


# ---------------------------------------------------------------------------
# Directory run
# ---------------------------------------------------------------------------


def test_eval_directory_run_aggregates(tmp_path: Path) -> None:
    _write_spec(
        tmp_path,
        "first.yaml",
        """
        name: first
        cases:
          - name: c1
            inputs: {message: hi}
            scoring: {kind: keyword, expected: ["fallback"], mode: any}
        """,
    )
    _write_spec(
        tmp_path,
        "second.yaml",
        """
        name: second
        cases:
          - name: c2
            inputs: {message: hi}
            scoring: {kind: keyword, expected: ["fallback"], mode: any}
        """,
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", str(tmp_path)])
    assert result.exit_code == 0
    assert "first" in result.output
    assert "second" in result.output
    assert "2 specs" in result.output


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def test_eval_json_output_parses(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path,
        "json.yaml",
        """
        name: json-out
        cases:
          - name: c1
            inputs: {message: hi}
            scoring: {kind: keyword, expected: ["fallback"], mode: any}
        """,
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", str(spec), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["pass_count"] == 1
    assert payload["fail_count"] == 0
    assert "specs" in payload
    assert payload["specs"][0]["spec_name"].startswith("json-out")


# ---------------------------------------------------------------------------
# --filter
# ---------------------------------------------------------------------------


def test_eval_filter_runs_subset(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path,
        "filter.yaml",
        """
        name: filter
        cases:
          - name: alpha_case
            inputs: {message: hi}
            scoring: {kind: keyword, expected: ["fallback"], mode: any}
          - name: beta_case
            inputs: {message: hi}
            scoring: {kind: keyword, expected: ["fallback"], mode: any}
        """,
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", str(spec), "--filter", "alpha", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["specs"][0]["cases"][0]["name"] == "alpha_case"
    assert len(payload["specs"][0]["cases"]) == 1


# ---------------------------------------------------------------------------
# Empty target
# ---------------------------------------------------------------------------


def test_eval_empty_directory_exits_zero(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", str(tmp_path)])
    assert result.exit_code == 0
    assert "No .yaml eval specs" in result.output


# ---------------------------------------------------------------------------
# Real shipped specs
# ---------------------------------------------------------------------------


def test_eval_runs_shipped_examples_directory() -> None:
    """The shipped example dir must run with exit 0 (all pass + skips OK)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", str(EXAMPLES_DIR)])
    assert result.exit_code == 0, result.output
    # Skipped judge cases should not break the run
    assert "skip" in result.output.lower() or "SKIP" in result.output


# ---------------------------------------------------------------------------
# Bad engine spec
# ---------------------------------------------------------------------------


def test_eval_bad_engine_fails_with_helpful_message(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path,
        "engine.yaml",
        """
        name: engine-test
        cases:
          - name: c1
            inputs: {message: hi}
            scoring: {kind: keyword, expected: ["fallback"], mode: any}
        """,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["eval", str(spec), "--judge-engine", "no_module_here:Nope"],
    )
    assert result.exit_code != 0
    assert "could not import" in result.output or "no module" in result.output.lower()


def test_eval_engine_spec_without_colon_rejected(tmp_path: Path) -> None:
    spec = _write_spec(
        tmp_path,
        "engine2.yaml",
        """
        name: engine-test
        cases:
          - name: c1
            inputs: {message: hi}
            scoring: {kind: keyword, expected: ["fallback"], mode: any}
        """,
    )
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["eval", str(spec), "--judge-engine", "missingcolon"],
    )
    assert result.exit_code != 0
    assert "module:attr" in result.output


# ---------------------------------------------------------------------------
# Heuristic engine wiring
# ---------------------------------------------------------------------------


def test_eval_heuristic_engine_skips_judge() -> None:
    """HeuristicEngine doesn't return JSON-structured judge replies, so
    judge cases should fail (not skip) when wired with it. This documents
    the contract: --judge-engine HeuristicEngine is not a magic free pass
    for judge scoring.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "eval",
            str(EXAMPLES_DIR / "personality_expression.yaml"),
            "--judge-engine",
            "soul_protocol.runtime.cognitive.engine:HeuristicEngine",
        ],
    )
    # The personality eval has 1 judge case; with HeuristicEngine wired
    # the judge will return non-JSON and fail. The other 3 cases pass,
    # so exit code is 1 (any failure).
    assert result.exit_code == 1
