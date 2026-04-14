# tests/test_install/test_base_install.py
# Created: 2026-04-14 — regression tests for issue #157.
# Verify that the CLI's module-level imports (click, rich, pyyaml, cryptography)
# are satisfied by the base dependencies declared in pyproject.toml, so a bare
# `pip install soul-protocol` yields a working `soul` / `soul-mcp` entry point.

from __future__ import annotations

import importlib
import importlib.util
import tomllib
from pathlib import Path


PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _load_pyproject() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_cli_required_deps_are_in_base() -> None:
    """click, rich, pyyaml, cryptography must be in [project].dependencies.

    The CLI imports these at module load time, so a user running bare
    `pip install soul-protocol` and then `soul --help` must have them
    available without needing the `[engine]` extra. Regression test for #157.
    """
    project = _load_pyproject()["project"]
    base_deps = " ".join(project["dependencies"]).lower()

    for pkg in ("click", "rich", "pyyaml", "cryptography"):
        assert pkg in base_deps, (
            f"{pkg!r} must be a base dependency (issue #157) — "
            f"the CLI imports it at module load"
        )


def test_engine_extra_preserved_for_backwards_compat() -> None:
    """The `[engine]` extra must still exist so old pins keep resolving.

    We deliberately kept it as an empty list rather than deleting it so
    that users with `soul-protocol[engine]` in requirements.txt do not
    suddenly see a resolver error after upgrading.
    """
    extras = _load_pyproject()["project"]["optional-dependencies"]
    assert "engine" in extras, "[engine] extra must remain for backwards compat"


def test_cli_module_imports_without_optional_extras() -> None:
    """`soul_protocol.cli.main` must import with only base deps present.

    If any of click / rich / pyyaml / cryptography were still stuck behind
    an optional extra, importing the CLI module in this test process would
    raise ImportError — which is exactly the #157 bug.
    """
    assert importlib.util.find_spec("soul_protocol.cli.main") is not None
    module = importlib.import_module("soul_protocol.cli.main")
    assert hasattr(module, "cli"), "CLI entry point `cli` must be defined"
