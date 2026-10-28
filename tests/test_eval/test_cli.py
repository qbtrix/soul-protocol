# test_cli.py — End-to-end tests for the `soul eval` CLI command (#160).
# Created: 2026-04-29 — Uses Click's CliRunner to drive the real CLI
#   against tempdir fixtures and the shipped example YAMLs. Validates
#   exit codes (0 on all-pass, 1 on any-fail), --json output shape, and
#   --filter narrowing.
# Updated: 2026-05-21 (paw-workspace#47) — Added an end-to-end test that
#   runs the humanizer_skill.yaml prompt-mode spec through the CLI with a
#   deterministic judge engine. `make_fake_judge_engine` is module-level
#   so the CLI's `--judge-engine module:attr` can import it.

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner

from soul_protocol.cli.main import cli

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "eval_examples"


# ---------------------------------------------------------------------------
# Deterministic judge engine — importable via --judge-engine module:attr
# ---------------------------------------------------------------------------


class _FakeJudgeEngine:
    """CognitiveEngine stand-in that always returns a passing judge verdict.

    Lets the CLI exercise judge-mode cases without API credentials. The
    canned JSON scores above every threshold in the shipped specs, so a
    structurally sound spec run reports all-pass.
    """

    async def think(self, prompt: str) -> str:
        return '{"score": 0.92, "reasoning": "meets the criteria"}'


def make_fake_judge_engine() -> _FakeJudgeEngine:
    """Factory the CLI resolves from `--judge-engine ...:make_fake_judge_engine`."""
    return _FakeJudgeEngine()


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


# ---------------------------------------------------------------------------
# Prompt-mode skill eval — humanizer_skill.yaml end-to-end (paw-workspace#47)
# ---------------------------------------------------------------------------

HUMANIZER_SPEC = EXAMPLES_DIR / "humanizer_skill.yaml"

# Module path the CLI uses to import the deterministic judge engine.
_FAKE_ENGINE_REF = "tests.test_eval.test_cli:make_fake_judge_engine"


def test_humanizer_spec_no_engine_skips_judge_exits_zero() -> None:
    """The humanizer spec runs with no engine: the regex case passes, the
    judge cases skip, and the run exits 0 (skips do not fail a run)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["eval", str(HUMANIZER_SPEC)])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output  # the regex gate
    assert "SKIP" in result.output  # the judge cases


def test_humanizer_spec_with_judge_engine_all_pass_exits_zero() -> None:
    """Wired with a deterministic judge engine, every case in the humanizer
    spec passes and the CLI exits 0 — the success path of a skill eval."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["eval", str(HUMANIZER_SPEC), "--judge-engine", _FAKE_ENGINE_REF, "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["fail_count"] == 0
    assert payload["error_count"] == 0
    # 5 cases: 1 regex + 4 judge, all of them score a pass with the engine.
    assert payload["pass_count"] == 5
    assert payload["skip_count"] == 0
    spec = payload["specs"][0]
    assert spec["spec_name"].startswith("Humanizer skill")
    judge_cases = [c for c in spec["cases"] if c["name"].startswith("judge_")]
    assert len(judge_cases) == 4
    assert all(c["passed"] for c in judge_cases)


def test_humanizer_spec_filter_runs_single_case() -> None:
    """`--filter` narrows the humanizer spec to one case end-to-end."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "eval",
            str(HUMANIZER_SPEC),
            "--filter",
            "regex_no_curly",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    cases = payload["specs"][0]["cases"]
    assert len(cases) == 1
    assert cases[0]["name"] == "regex_no_curly_quotes_or_emoji"
    assert cases[0]["passed"]
