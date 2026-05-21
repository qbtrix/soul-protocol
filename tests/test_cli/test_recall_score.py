# test_recall_score.py — Smoke test for `soul recall --json` score field (#247).
# Created: feat/recall-graded-floor (#247) — Fast CLI check that recall --json
#   emits a per-result `score` field and that a recall returns scored results.
#   Companion to the end-to-end coverage in tests/test_retrieval.py.

from __future__ import annotations

import json

from click.testing import CliRunner

from soul_protocol.cli.main import cli


def _birth(path: str, name: str = "ScoreProbe") -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["birth", name, "-o", path])
    assert result.exit_code == 0, result.output


def _remember(soul_path: str, text: str, *, importance: int = 6) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["remember", soul_path, text, "-i", str(importance)])
    assert result.exit_code == 0, result.output


class TestRecallJsonScore:
    """`soul recall --json` surfaces a score per result."""

    def test_recall_json_includes_score_field(self, tmp_path):
        """A queried recall --json carries a numeric `score` on each result."""
        soul_path = str(tmp_path / "score.soul")
        _birth(soul_path)
        _remember(soul_path, "Python deployment uses Docker and Kubernetes")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["recall", soul_path, "python deployment docker", "--json"]
        )
        assert result.exit_code == 0, result.output

        payload = json.loads(result.output)
        assert payload, "expected at least one recalled memory"
        for item in payload:
            assert "score" in item, item
            assert isinstance(item["score"], (int, float))

    def test_recall_returns_scored_results(self, tmp_path):
        """The recalled memory's score is a finite, positive activation value."""
        soul_path = str(tmp_path / "scored.soul")
        _birth(soul_path)
        _remember(soul_path, "The team ships releases every other Friday")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["recall", soul_path, "team ships releases", "--json"]
        )
        assert result.exit_code == 0, result.output

        payload = json.loads(result.output)
        assert len(payload) == 1
        score = payload[0]["score"]
        assert score is not None
        assert score > 0.0

    def test_min_relevance_drops_weak_match(self, tmp_path):
        """`--min-relevance` applies the graded floor: a weak match is dropped."""
        soul_path = str(tmp_path / "floor.soul")
        _birth(soul_path)
        # Strong match — every query token present.
        _remember(soul_path, "Kubernetes orchestration handles pod scaling")
        # Weak match — shares only the token 'kubernetes' with the query.
        _remember(soul_path, "An aside that briefly mentions kubernetes once")

        runner = CliRunner()
        query = "kubernetes orchestration scaling"

        # Default floor keeps both matches.
        wide = runner.invoke(cli, ["recall", soul_path, query, "--json"])
        assert wide.exit_code == 0, wide.output
        assert len(json.loads(wide.output)) == 2

        # A 0.5 floor drops the weak single-token match.
        narrow = runner.invoke(
            cli, ["recall", soul_path, query, "--json", "--min-relevance", "0.5"]
        )
        assert narrow.exit_code == 0, narrow.output
        narrowed = json.loads(narrow.output)
        assert len(narrowed) == 1
        assert "orchestration handles pod scaling" in narrowed[0]["content"]
