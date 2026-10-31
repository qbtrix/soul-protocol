# test_cli/test_instinct_cmd.py — Tests for `soul instinct` soul discovery and wiring.
# Created: feat/soul-instinct — Path resolution (explicit, nested `soul save`
#   layout, auto-detect in the current folder, ambiguous/missing) and command
#   registration. The model-backed run itself is covered by the live NLI tests.
# Updated: feat/soul-instinct (#322 review) — _quiet_model_loading() restores the
#   env vars, warnings filter and log level it changed.

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner

from soul_protocol.cli.instinct_cmd import _find_soul, _quiet_model_loading
from soul_protocol.cli.main import cli


def _soul_dir(path):
    path.mkdir(parents=True)
    (path / "soul.json").write_text("{}")
    return path


def test_explicit_soul_dir(tmp_path):
    d = _soul_dir(tmp_path / "aria")
    assert _find_soul(str(d)) == d


def test_steps_into_saved_layout(tmp_path):
    inner = _soul_dir(tmp_path / "shekhar.soul" / "did_soul_shekhar-123")
    assert _find_soul(str(tmp_path / "shekhar.soul")) == inner


def test_archive_file_passes_through(tmp_path):
    archive = tmp_path / "aria.soul"
    archive.write_bytes(b"zip")
    assert _find_soul(str(archive)) == archive


def test_autodetects_single_soul_in_cwd(tmp_path, monkeypatch):
    inner = _soul_dir(tmp_path / "me.soul" / "did_x")
    monkeypatch.chdir(tmp_path)
    assert _find_soul(None) == inner


def test_autodetect_refuses_ambiguity(tmp_path, monkeypatch):
    (tmp_path / "a.soul").write_bytes(b"x")
    (tmp_path / "b.soul").write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(click.UsageError, match="a.soul, b.soul"):
        _find_soul(None)


def test_autodetect_with_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(click.UsageError, match="none"):
        _find_soul(None)


def test_command_is_registered():
    result = CliRunner().invoke(cli, ["instinct", "--help"])
    assert result.exit_code == 0
    assert "read-only" in result.output


def test_quiet_model_loading_restores_process_state(monkeypatch):
    import logging
    import os
    import warnings

    monkeypatch.delenv("TRANSFORMERS_VERBOSITY", raising=False)
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "true")
    soul_logger = logging.getLogger("soul_protocol")
    level_before = soul_logger.level
    filters_before = list(warnings.filters)

    with _quiet_model_loading():
        assert os.environ["TRANSFORMERS_VERBOSITY"] == "error"
        assert os.environ["TOKENIZERS_PARALLELISM"] == "true"  # setdefault: user value kept
        assert soul_logger.level == logging.ERROR

    assert "TRANSFORMERS_VERBOSITY" not in os.environ
    assert os.environ["TOKENIZERS_PARALLELISM"] == "true"
    assert soul_logger.level == level_before
    assert warnings.filters == filters_before
