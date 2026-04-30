# test_examples.py — Smoke test the shipped example eval YAMLs (#160).
# Created: 2026-04-29 — Every YAML under tests/eval_examples/ must load
#   cleanly, run with no engine (so judge cases skip), and produce a
#   result where every non-judge case passes. This protects the example
#   files from drift as the soul runtime evolves.

from __future__ import annotations

from pathlib import Path

import pytest

from soul_protocol.eval import load_eval_spec, run_eval

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "eval_examples"


def _example_paths() -> list[Path]:
    return sorted(EXAMPLES_DIR.glob("*.yaml"))


@pytest.mark.parametrize("spec_path", _example_paths(), ids=lambda p: p.stem)
def test_example_spec_loads(spec_path: Path) -> None:
    """Every shipped example must validate against the schema."""
    spec = load_eval_spec(spec_path)
    assert spec.cases, f"{spec_path.name}: no cases"


@pytest.mark.asyncio
@pytest.mark.parametrize("spec_path", _example_paths(), ids=lambda p: p.stem)
async def test_example_spec_passes(spec_path: Path) -> None:
    """Every shipped example must pass cleanly without an engine.

    Judge cases skip (no engine wired), keyword/regex/semantic/structural
    cases must all pass. Skips are allowed; failures and errors are not.
    """
    spec = load_eval_spec(spec_path)
    result = await run_eval(spec)
    assert result.error is None, f"{spec_path.name} seed error: {result.error}"
    failures = [c for c in result.cases if not c.passed and not c.skipped]
    assert not failures, f"{spec_path.name} had {len(failures)} failures: " + ", ".join(
        f"{c.name}: {c.details}" for c in failures
    )
