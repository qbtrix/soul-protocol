# test_journal_cmd.py — Tests for `soul journal {init,append,query}` (#189).
# Created: feat/soul-journal-cli — Covers init, single-event append, stdin
#   batching, action-prefix filtering (with and without trailing dot),
#   --json round-trip, and error paths (missing scope, mutually exclusive
#   flags, invalid JSON in stdin).

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from soul_protocol.cli.main import cli


def _journal_path(tmp_path: Path) -> Path:
    return tmp_path / "test.journal.db"


def test_journal_init_creates_file(tmp_path: Path) -> None:
    """`journal init` materializes the SQLite file."""
    runner = CliRunner()
    path = _journal_path(tmp_path)

    result = runner.invoke(cli, ["journal", "init", str(path)])

    assert result.exit_code == 0, result.output
    assert path.exists()
    assert "Initialized" in result.output


def test_journal_init_refuses_overwrite_without_force(tmp_path: Path) -> None:
    """`journal init` against an existing path errors unless --force."""
    runner = CliRunner()
    path = _journal_path(tmp_path)

    runner.invoke(cli, ["journal", "init", str(path)])
    result = runner.invoke(cli, ["journal", "init", str(path)])

    assert result.exit_code != 0
    assert "already exists" in result.output


def test_journal_init_force_overwrites(tmp_path: Path) -> None:
    """--force wipes the existing journal and starts fresh."""
    runner = CliRunner()
    path = _journal_path(tmp_path)

    runner.invoke(cli, ["journal", "init", str(path)])
    # Append something so we can detect that --force re-init clears it
    runner.invoke(
        cli,
        [
            "journal",
            "append",
            str(path),
            "--action",
            "test.action",
            "--scope",
            "test:scope",
            "--payload",
            "{}",
        ],
    )
    # Re-init with --force
    result = runner.invoke(cli, ["journal", "init", str(path), "--force"])
    assert result.exit_code == 0, result.output

    # Query should now return nothing
    q = runner.invoke(cli, ["journal", "query", str(path), "--json"])
    assert q.exit_code == 0
    assert json.loads(q.output) == []


def test_append_single_event_then_query(tmp_path: Path) -> None:
    """A single appended event surfaces via query."""
    runner = CliRunner()
    path = _journal_path(tmp_path)

    runner.invoke(cli, ["journal", "init", str(path)])
    append_result = runner.invoke(
        cli,
        [
            "journal",
            "append",
            str(path),
            "--action",
            "session.pr.merged",
            "--actor",
            '{"kind":"agent","id":"did:soul:test"}',
            "--payload",
            '{"pr": 42}',
            "--scope",
            "session:abc",
            "--scope",
            "repo:test",
        ],
    )
    assert append_result.exit_code == 0, append_result.output

    # Stdout should be a JSON-decodable EventEntry
    committed = json.loads(append_result.output.strip())
    assert committed["action"] == "session.pr.merged"
    assert committed["actor"]["kind"] == "agent"
    assert committed["actor"]["id"] == "did:soul:test"
    assert committed["payload"] == {"pr": 42}
    assert sorted(committed["scope"]) == ["repo:test", "session:abc"]
    assert committed["seq"] == 0  # first event in a fresh journal

    # Query should return the same event
    query_result = runner.invoke(cli, ["journal", "query", str(path), "--json"])
    assert query_result.exit_code == 0
    events = json.loads(query_result.output)
    assert len(events) == 1
    assert events[0]["id"] == committed["id"]


def test_append_requires_scope(tmp_path: Path) -> None:
    """Append without --scope fails fast (events without scope are rejected)."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    result = runner.invoke(
        cli,
        ["journal", "append", str(path), "--action", "test.action"],
    )

    assert result.exit_code != 0
    assert "scope" in result.output.lower()


def test_append_requires_action_or_stdin(tmp_path: Path) -> None:
    """Append without --action or --stdin fails fast."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    result = runner.invoke(
        cli,
        ["journal", "append", str(path), "--scope", "test:scope"],
    )

    assert result.exit_code != 0
    assert "action" in result.output.lower()


def test_stdin_batches_multiple_events(tmp_path: Path) -> None:
    """JSONL on stdin appends multiple events in one Journal session."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    jsonl = "\n".join(
        [
            json.dumps({"action": "stdin.first", "scope": ["s:1"], "payload": {"n": 1}}),
            json.dumps({"action": "stdin.second", "scope": ["s:2"], "payload": {"n": 2}}),
            "",  # blank line should be skipped
            json.dumps({"action": "stdin.third", "scope": ["s:3"], "payload": {"n": 3}}),
        ]
    )

    result = runner.invoke(
        cli,
        ["journal", "append", str(path), "--stdin"],
        input=jsonl,
    )
    assert result.exit_code == 0, result.output

    # Each non-empty stdin line yields one JSON line in stdout
    out_lines = [line for line in result.output.strip().split("\n") if line]
    assert len(out_lines) == 3
    actions = [json.loads(line)["action"] for line in out_lines]
    assert actions == ["stdin.first", "stdin.second", "stdin.third"]

    # Sequences should be 0, 1, 2
    seqs = [json.loads(line)["seq"] for line in out_lines]
    assert seqs == [0, 1, 2]


def test_stdin_invalid_json_aborts_batch(tmp_path: Path) -> None:
    """A malformed stdin line aborts the batch with a non-zero exit code."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    bad = "not valid json"
    result = runner.invoke(cli, ["journal", "append", str(path), "--stdin"], input=bad)

    assert result.exit_code != 0


def test_stdin_mutually_exclusive_with_flags(tmp_path: Path) -> None:
    """--stdin and --action / --scope are mutually exclusive."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    result = runner.invoke(
        cli,
        [
            "journal",
            "append",
            str(path),
            "--stdin",
            "--action",
            "test",
            "--scope",
            "s:1",
        ],
        input="{}\n",
    )

    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_query_action_prefix_matches_namespace(tmp_path: Path) -> None:
    """--action-prefix matches descendants in the dotted namespace."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    for action in [
        "session.pr.merged",
        "session.pr.opened",
        "session.commit.pushed",
        "agent.spawned",
    ]:
        runner.invoke(
            cli,
            [
                "journal",
                "append",
                str(path),
                "--action",
                action,
                "--scope",
                "test:scope",
            ],
        )

    result = runner.invoke(
        cli,
        ["journal", "query", str(path), "--action-prefix", "session.pr", "--json"],
    )
    assert result.exit_code == 0
    events = json.loads(result.output)
    assert len(events) == 2
    assert {e["action"] for e in events} == {"session.pr.merged", "session.pr.opened"}


def test_query_action_prefix_tolerates_trailing_dot(tmp_path: Path) -> None:
    """--action-prefix `session.pr.` works the same as `session.pr`."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    runner.invoke(
        cli,
        [
            "journal",
            "append",
            str(path),
            "--action",
            "session.pr.merged",
            "--scope",
            "test:scope",
        ],
    )

    # With trailing dot
    r1 = runner.invoke(
        cli,
        ["journal", "query", str(path), "--action-prefix", "session.pr.", "--json"],
    )
    assert r1.exit_code == 0
    e1 = json.loads(r1.output)

    # Without trailing dot
    r2 = runner.invoke(
        cli,
        ["journal", "query", str(path), "--action-prefix", "session.pr", "--json"],
    )
    assert r2.exit_code == 0
    e2 = json.loads(r2.output)

    assert len(e1) == 1
    assert e1 == e2


def test_query_json_round_trips_through_json_loads(tmp_path: Path) -> None:
    """--json output is parseable as JSON and contains all key fields."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    runner.invoke(
        cli,
        [
            "journal",
            "append",
            str(path),
            "--action",
            "test.event",
            "--actor",
            '{"kind":"agent","id":"did:soul:tester"}',
            "--scope",
            "test:scope",
            "--payload",
            '{"value": 42}',
        ],
    )

    result = runner.invoke(cli, ["journal", "query", str(path), "--json"])
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
    assert parsed[0]["action"] == "test.event"
    assert parsed[0]["actor"]["id"] == "did:soul:tester"
    assert parsed[0]["scope"] == ["test:scope"]
    assert parsed[0]["payload"] == {"value": 42}
    assert "seq" in parsed[0]
    assert "ts" in parsed[0]


def test_query_action_and_action_prefix_mutually_exclusive(tmp_path: Path) -> None:
    """Passing both --action and --action-prefix errors."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    result = runner.invoke(
        cli,
        [
            "journal",
            "query",
            str(path),
            "--action",
            "x",
            "--action-prefix",
            "y",
        ],
    )

    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_query_at_and_until_mutually_exclusive(tmp_path: Path) -> None:
    """Passing both --at and --until errors."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    result = runner.invoke(
        cli,
        [
            "journal",
            "query",
            str(path),
            "--at",
            "2026-04-29T00:00:00Z",
            "--until",
            "2026-04-29T00:00:00Z",
        ],
    )

    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_query_default_table_output_contains_actions(tmp_path: Path) -> None:
    """Without --json, the table output names appended actions."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    runner.invoke(
        cli,
        [
            "journal",
            "append",
            str(path),
            "--action",
            "ci.build.passed",
            "--scope",
            "ci:1",
        ],
    )

    result = runner.invoke(cli, ["journal", "query", str(path)])
    assert result.exit_code == 0
    assert "ci.build.passed" in result.output


def test_causation_id_threads_through_append(tmp_path: Path) -> None:
    """The committed entry exposes the seq + id so callers can chain causation_id."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    first = runner.invoke(
        cli,
        [
            "journal",
            "append",
            str(path),
            "--action",
            "agent.proposed",
            "--scope",
            "decision:1",
        ],
    )
    parent = json.loads(first.output)

    second = runner.invoke(
        cli,
        [
            "journal",
            "append",
            str(path),
            "--action",
            "human.corrected",
            "--scope",
            "decision:1",
            "--causation-id",
            parent["id"],
        ],
    )
    assert second.exit_code == 0, second.output
    child = json.loads(second.output)
    assert child["causation_id"] == parent["id"]


def test_query_no_results_message(tmp_path: Path) -> None:
    """Empty-result query renders a friendly message in table mode."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    result = runner.invoke(cli, ["journal", "query", str(path)])
    assert result.exit_code == 0
    assert "no events" in result.output.lower()


def test_query_no_results_json_is_empty_list(tmp_path: Path) -> None:
    """Empty-result query in --json mode emits []."""
    runner = CliRunner()
    path = _journal_path(tmp_path)
    runner.invoke(cli, ["journal", "init", str(path)])

    result = runner.invoke(cli, ["journal", "query", str(path), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []
