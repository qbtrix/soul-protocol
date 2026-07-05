# conftest.py — make the Nemesis-System example importable under pytest.
#
# Created: 2026-07-05 (feat/nemesis-warband) — the suite's pyproject sets
#   testpaths=["tests"], and this example lives under examples/, whose parent
#   (the repo root) is not on sys.path when pytest collects from a nested dir.
#   Mirrors the existing examples/test_pocketpaw_integration.py convention of
#   fixing up sys.path in-test, but points at the REPO ROOT so the package
#   imports cleanly as ``examples.nemesis_warband.*`` (its modules use
#   package-relative imports between each other). No production code depends on
#   this; it only affects test collection.

from __future__ import annotations

import sys
from pathlib import Path

# examples/nemesis_warband/conftest.py -> parents[2] == repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
