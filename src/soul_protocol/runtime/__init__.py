# runtime/__init__.py — Reference implementation of the Soul Protocol.
# The "nginx" to the protocol's "HTTP" — opinionated, batteries-included.
# Everything here builds on top of spec/ primitives.
# Updated: feat/soul-diff-cli (#191) — Re-export SoulDiff, diff_souls,
#   SchemaMismatchError so external tooling (PR review bots, CI checks) can
#   programmatically diff two souls without reaching into runtime.diff.
# Updated: Added LCMContext and SQLiteContextStore exports for Lossless Context Management.
# Updated: Added Evaluator, DEFAULT_RUBRICS, heuristic_evaluate exports.

from __future__ import annotations

from .context import LCMContext, SQLiteContextStore
from .diff import SchemaMismatchError, SoulDiff, diff_souls
from .evaluation import DEFAULT_RUBRICS, Evaluator, heuristic_evaluate

__all__ = [
    "DEFAULT_RUBRICS",
    "Evaluator",
    "LCMContext",
    "SQLiteContextStore",
    "SchemaMismatchError",
    "SoulDiff",
    "diff_souls",
    "heuristic_evaluate",
]
