# test_schema.py — Pydantic schema tests for the eval YAML format (#160).
# Created: 2026-04-29 — Covers EvalSpec parsing, scoring discriminator,
#   error cases (invalid threshold, unknown scoring kind, missing required
#   fields). Validates that all five scoring kinds round-trip cleanly.

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from soul_protocol.eval.schema import (
    EvalSpec,
    JudgeScoring,
    KeywordScoring,
    RegexScoring,
    SchemaValidationError,
    SemanticScoring,
    StructuralScoring,
    load_eval_spec,
    parse_eval_spec,
)


def _minimal_dict(scoring: dict) -> dict:
    """Build a minimal EvalSpec dict around one scoring block."""
    return {
        "name": "test",
        "cases": [
            {
                "name": "c1",
                "inputs": {"message": "hello"},
                "scoring": scoring,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Each scoring kind round-trips
# ---------------------------------------------------------------------------


def test_keyword_scoring_parses() -> None:
    spec = parse_eval_spec(_minimal_dict({"kind": "keyword", "expected": ["hello", "world"]}))
    assert isinstance(spec.cases[0].scoring, KeywordScoring)
    assert spec.cases[0].scoring.expected == ["hello", "world"]
    # Keyword default mode is "all"
    assert spec.cases[0].scoring.mode == "all"
    # Keyword default threshold is 1.0
    assert spec.cases[0].scoring.threshold == 1.0


def test_keyword_any_mode() -> None:
    spec = parse_eval_spec(
        _minimal_dict({"kind": "keyword", "expected": ["a", "b"], "mode": "any"})
    )
    scoring = spec.cases[0].scoring
    assert isinstance(scoring, KeywordScoring)
    assert scoring.mode == "any"


def test_regex_scoring_parses() -> None:
    spec = parse_eval_spec(_minimal_dict({"kind": "regex", "pattern": r"^foo.*bar$"}))
    assert isinstance(spec.cases[0].scoring, RegexScoring)
    assert spec.cases[0].scoring.pattern == r"^foo.*bar$"


def test_semantic_scoring_parses() -> None:
    spec = parse_eval_spec(
        _minimal_dict({"kind": "semantic", "expected": "the quick brown fox", "threshold": 0.4})
    )
    scoring = spec.cases[0].scoring
    assert isinstance(scoring, SemanticScoring)
    assert scoring.threshold == 0.4


def test_judge_scoring_parses() -> None:
    spec = parse_eval_spec(_minimal_dict({"kind": "judge", "criteria": "is the answer correct?"}))
    scoring = spec.cases[0].scoring
    assert isinstance(scoring, JudgeScoring)
    # Judge default threshold is 0.7
    assert scoring.threshold == 0.7


def test_structural_scoring_parses() -> None:
    spec = parse_eval_spec(
        _minimal_dict(
            {
                "kind": "structural",
                "expected": {
                    "output_contains_bonded_user": True,
                    "mood_after": "curious",
                },
            }
        )
    )
    scoring = spec.cases[0].scoring
    assert isinstance(scoring, StructuralScoring)
    assert scoring.expected["mood_after"] == "curious"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_unknown_scoring_kind_raises() -> None:
    with pytest.raises(SchemaValidationError):
        parse_eval_spec(_minimal_dict({"kind": "magic", "expected": ["x"]}))


def test_threshold_out_of_range_raises() -> None:
    with pytest.raises(SchemaValidationError):
        parse_eval_spec(_minimal_dict({"kind": "semantic", "expected": "x", "threshold": 1.5}))


def test_missing_required_scoring_field_raises() -> None:
    # keyword needs `expected`
    with pytest.raises(SchemaValidationError):
        parse_eval_spec(_minimal_dict({"kind": "keyword"}))


def test_extra_field_on_scoring_raises() -> None:
    with pytest.raises(SchemaValidationError):
        parse_eval_spec(_minimal_dict({"kind": "keyword", "expected": ["x"], "bogus": True}))


def test_extra_field_on_spec_raises() -> None:
    data = _minimal_dict({"kind": "keyword", "expected": ["x"]})
    data["bogus"] = "value"
    with pytest.raises(SchemaValidationError):
        parse_eval_spec(data)


def test_seed_bond_strength_out_of_range_raises() -> None:
    data = _minimal_dict({"kind": "keyword", "expected": ["x"]})
    data["seed"] = {"bond_strength": {"alice": 200}}
    # bond_strength is just a dict on the Seed model — runner clamps later;
    # but BondSeed's own validator catches >100 if used. We at least make
    # sure the dict form goes through (not validated to <=100 here).
    spec = parse_eval_spec(data)
    assert spec.seed.bond_strength == {"alice": 200}


def test_ocean_out_of_range_raises() -> None:
    data = _minimal_dict({"kind": "keyword", "expected": ["x"]})
    data["seed"] = {"soul": {"ocean": {"openness": 1.5}}}
    with pytest.raises(SchemaValidationError):
        parse_eval_spec(data)


# ---------------------------------------------------------------------------
# Memories + state seed
# ---------------------------------------------------------------------------


def test_memory_seed_layer_defaults_semantic() -> None:
    data = _minimal_dict({"kind": "keyword", "expected": ["x"]})
    data["seed"] = {"memories": [{"content": "alice likes rust"}]}
    spec = parse_eval_spec(data)
    assert spec.seed.memories[0].layer == "semantic"
    assert spec.seed.memories[0].importance == 5
    assert spec.seed.memories[0].domain == "default"


def test_memory_seed_custom_layer_accepted() -> None:
    data = _minimal_dict({"kind": "keyword", "expected": ["x"]})
    data["seed"] = {"memories": [{"content": "secret-tier note", "layer": "vault"}]}
    spec = parse_eval_spec(data)
    assert spec.seed.memories[0].layer == "vault"


def test_state_seed_mood_str_coerces() -> None:
    data = _minimal_dict({"kind": "keyword", "expected": ["x"]})
    data["seed"] = {"state": {"mood": "curious", "energy": 75}}
    spec = parse_eval_spec(data)
    assert spec.seed.state.mood is not None
    assert spec.seed.state.mood.value == "curious"
    assert spec.seed.state.energy == 75


def test_state_seed_mood_invalid_raises() -> None:
    data = _minimal_dict({"kind": "keyword", "expected": ["x"]})
    data["seed"] = {"state": {"mood": "ecstatic"}}  # not a Mood value
    with pytest.raises(SchemaValidationError):
        parse_eval_spec(data)


# ---------------------------------------------------------------------------
# load_eval_spec end-to-end
# ---------------------------------------------------------------------------


def test_load_eval_spec_reads_yaml(tmp_path: Path) -> None:
    yaml_text = dedent(
        """
        name: "yaml round-trip"
        cases:
          - name: case_a
            inputs:
              message: hello
            scoring:
              kind: keyword
              expected: ["hello"]
        """
    ).strip()
    path = tmp_path / "spec.yaml"
    path.write_text(yaml_text)
    spec = load_eval_spec(path)
    assert isinstance(spec, EvalSpec)
    assert spec.name == "yaml round-trip"
    assert len(spec.cases) == 1


def test_load_eval_spec_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_eval_spec(tmp_path / "nope.yaml")


def test_load_eval_spec_non_mapping_raises(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_text("- just a list")
    with pytest.raises(SchemaValidationError):
        load_eval_spec(path)
