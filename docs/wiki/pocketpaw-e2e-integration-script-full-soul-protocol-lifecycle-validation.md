---
{
  "title": "PocketPaw E2E Integration Script: Full Soul Protocol Lifecycle Validation",
  "summary": "An end-to-end integration script that validates the complete soul-protocol API lifecycle — birth, observe, remember, recall, reflect, export, awaken, core memory editing, state management, and MCP tool smoke tests — from the perspective of PocketPaw's integration layer, using realistic interaction datasets and Rich-formatted reporting.",
  "concepts": [
    "E2E integration",
    "PocketPaw SoulBridge",
    "SoulBootstrapProvider",
    "full lifecycle",
    "soul birth",
    "observe",
    "recall",
    "reflect",
    "export",
    "awaken",
    "core memory editing",
    "MCP tools",
    "Rich output",
    "interaction datasets"
  ],
  "categories": [
    "scripts",
    "integration-testing",
    "pocketpaw",
    "soul-protocol"
  ],
  "source_docs": [
    "bd4aa02a176e4598"
  ],
  "backlinks": null,
  "word_count": 382,
  "compiled_at": "2026-04-23T18:24:18Z",
  "compiled_with": "agent",
  "version": 1,
  "audience": "human",
  "depth": "deep",
  "target_words": 500
}
---

## Purpose

Unit tests can pass while integration fails. This script exists to validate soul-protocol from the outside: the same sequence of API calls that PocketPaw's `SoulBridge` and `SoulBootstrapProvider` would execute, running against a real `Soul` instance. If this script passes, PocketPaw can safely upgrade the soul-protocol dependency.

## Scenarios

| Scenario | What It Tests |
|---|---|
| `scenario_full_lifecycle` | Birth → observe (30 interactions) → remember → recall → reflect → export → awaken |
| `scenario_core_memory_editing` | Add persona facts, add human profile facts, verify accumulation and export/import survival |
| `scenario_state_management` | Energy drain via observe, mood transitions, `feel()`, rest recovery |
| `scenario_mcp_tools` | MCP server tool smoke: `soul_observe`, `soul_recall`, `soul_remember`, `soul_reflect` |
| `scenario_paw_bridge_simulation` | Full SoulBridge simulation: project scan → coding interactions → preference learning |

## Interaction Datasets

Three curated interaction datasets drive the paw-bridge scenario:

```python
PROJECT_SCAN_INTERACTIONS   # 10 turns: Python + FastAPI project setup
CODING_INTERACTIONS         # 12 turns: debugging, architecture discussion
PREFERENCE_INTERACTIONS     # 8 turns: communication style, work preferences
```

These are not random — they reflect real usage patterns observed in PocketPaw. The project scan sequence plants technical facts (stack, tools) that should be recalled later; the preference sequence plants behavioral facts (verbosity preference, async style) that should influence the soul's communication style.

## Result Tracking

```python
@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    elapsed_ms: float = 0.0

@dataclass
class ScenarioResult:
    name: str
    checks: list[CheckResult]
    error: str | None = None
    elapsed_ms: float = 0.0
```

Each scenario runs a list of named checks. `ScenarioResult.passed` is True only if all checks pass and no exception occurred. Elapsed time per check surfaces slow operations (e.g., a recall that takes >500ms warrants investigation).

## Rich Output

The script uses `rich.console`, `rich.panel`, and `rich.table` for formatted output. This is intentional: the script is run manually by developers before releasing a new soul-protocol version, and readable output reduces the time to diagnose failures.

## Known Gaps

- The MCP scenario tests tool interfaces but not the MCP server process itself — it calls the Python functions directly. An actual MCP socket test would provide stronger confidence.
- `RESULTS_DIR` is created at import time. If the script is imported in a read-only environment, it raises on startup rather than at result-save time.
