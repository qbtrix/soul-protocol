# soul_protocol.eval — YAML-driven evals for memory-driven agents.
# Created: 2026-04-29 (#160) — Soul-aware evaluation framework. Evals seed
#   a soul with explicit state (memories, OCEAN, bonds, mood, energy) and
#   then run cases against that state. Built so #142 (soul optimize) can
#   measure agent quality against a known-good signal.

from __future__ import annotations

from .runner import (
    CaseResult,
    EvalResult,
    run_eval,
    run_eval_against_soul,
    run_eval_file,
)
from .schema import (
    BondSeed,
    EvalCase,
    EvalSpec,
    JudgeScoring,
    KeywordScoring,
    MemorySeed,
    RegexScoring,
    SchemaValidationError,
    Scoring,
    SemanticScoring,
    SoulSeed,
    StateSeed,
    StructuralScoring,
    load_eval_spec,
    parse_eval_spec,
)

__all__ = [
    # Schema
    "EvalSpec",
    "EvalCase",
    "SoulSeed",
    "StateSeed",
    "MemorySeed",
    "BondSeed",
    "Scoring",
    "KeywordScoring",
    "RegexScoring",
    "SemanticScoring",
    "JudgeScoring",
    "StructuralScoring",
    "SchemaValidationError",
    "load_eval_spec",
    "parse_eval_spec",
    # Runner
    "EvalResult",
    "CaseResult",
    "run_eval",
    "run_eval_against_soul",
    "run_eval_file",
]
