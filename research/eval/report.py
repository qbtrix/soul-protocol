# report.py — Soul Health Score dashboard renderer.
# Created: 2026-03-12 — Markdown + JSON + comparison table + ANSI terminal dashboard
# for SHS evaluation results. No external dependencies (no rich, no tabulate).
# Updated: 2026-03-12 — Fixed _score_label tiers: distinct symbols per tier,
# simplified to 4 tiers (>=90 Production Ready ●, >=75 Strong ◐, >=50 Developing ○, <50 Needs Work ✗).

from __future__ import annotations

import json
import sys
from datetime import datetime

from .suite import (
    DIMENSION_WEIGHTS,
    DimensionResult,
    SoulHealthReport,
)

# Dimension display names (mirrors weight keys in suite.py)
DIMENSION_NAMES: dict[int, str] = {
    1: "Memory Recall",
    2: "Emotional Intelligence",
    3: "Personality Expression",
    4: "Bond / Relationship",
    5: "Self-Model",
    6: "Identity Continuity",
    7: "Portability",
}

# ---------------------------------------------------------------------------
# ANSI color codes (disabled when not a TTY)
# ---------------------------------------------------------------------------

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"


def _use_color() -> bool:
    """Return True if stdout supports ANSI color."""
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


# ---------------------------------------------------------------------------
# Score labels and status symbols
# ---------------------------------------------------------------------------


def _score_label(score: float) -> tuple[str, str]:
    """Return (label, symbol) for a given 0-100 score."""
    if score >= 90:
        return "Production Ready", "●"
    elif score >= 75:
        return "Strong", "◐"
    elif score >= 50:
        return "Developing", "○"
    else:
        return "Needs Work", "✗"


def _score_color(score: float) -> str:
    """Return ANSI color code for a score."""
    if score >= 75:
        return GREEN
    elif score >= 60:
        return YELLOW
    else:
        return RED


# ---------------------------------------------------------------------------
# 1. Markdown report
# ---------------------------------------------------------------------------


def render_markdown(report: SoulHealthReport) -> str:
    """Render a SoulHealthReport as a pretty markdown table for terminal or whitepaper."""
    label, emoji = _score_label(report.soul_health_score)
    lines: list[str] = []

    # Header
    lines.append("# Soul Health Score Report")
    lines.append("")
    lines.append(f"Run: {report.run_id} | Seed: {report.seed} | Version: {report.version}")
    lines.append(f"Date: {report.timestamp.isoformat()}")
    lines.append("")
    lines.append(f"## Overall Score: {report.soul_health_score}/100 — {label}")
    lines.append("")

    # Summary table
    lines.append("| # | Dimension | Score | Pass | Fail | Status |")
    lines.append("|---|-----------|-------|------|------|--------|")

    for r in report.dimension_results:
        _, status = _score_label(r.score)
        lines.append(
            f"| {r.dimension_id} | {r.dimension_name} | {r.score:.1f} "
            f"| {len(r.passed)} | {len(r.failed)} | {status} |"
        )

    lines.append(f"| — | **Soul Health Score** | **{report.soul_health_score}** | | | {emoji} |")
    lines.append("")

    # Dimension details
    lines.append("## Dimension Details")
    lines.append("")

    for r in report.dimension_results:
        lines.append(f"### D{r.dimension_id}: {r.dimension_name} ({r.score:.1f}/100)")
        if r.metrics:
            lines.append("Metrics:")
            for name, value in r.metrics.items():
                check = "✓" if name in r.passed else ("✗" if name in r.failed else "—")
                lines.append(f"  - {name}: {value:.2f} {check}")
        if r.notes:
            lines.append(f"Notes: {r.notes}")
        lines.append("")

    # Interpretation
    lines.append("## Interpretation")
    shs = report.soul_health_score
    if shs >= 90:
        lines.append(
            "**Production Ready (90-100):** The soul demonstrates excellent performance "
            "across all dimensions. Ready for real-world deployment with confidence."
        )
    elif shs >= 75:
        lines.append(
            "**Strong (75-89):** The soul performs well across most dimensions. "
            "Minor improvements possible but overall robust."
        )
    elif shs >= 60:
        lines.append(
            "**Developing (60-74):** The soul shows promising capability but has "
            "room for growth in several dimensions."
        )
    elif shs >= 40:
        lines.append(
            "**Early Stage (40-59):** The soul has basic functionality but needs "
            "significant development across multiple dimensions."
        )
    else:
        lines.append(
            "**Baseline (0-39):** The soul is at baseline capability. Most dimensions "
            "need substantial work before deployment."
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. JSON report
# ---------------------------------------------------------------------------


def render_json(report: SoulHealthReport) -> str:
    """Serialize a SoulHealthReport to JSON with pretty-printing."""

    def _default(obj: object) -> str:
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(report.to_dict(), indent=2, default=_default)


# ---------------------------------------------------------------------------
# 3. Whitepaper comparison table (Full Soul vs RAG Only)
# ---------------------------------------------------------------------------


def render_comparison_table(report: SoulHealthReport) -> str:
    """Render a comparison table: Full Soul vs RAG Only baseline.

    RAG Only scoring:
      - D1: rag_recall_precision metric * 50 (if available), else 0
      - D2-D7: 0 (RAG has no personality, bonds, identity, etc.)
      - RAG SHS: D1_rag_score * 0.20
    """
    lines: list[str] = []
    lines.append("| Dimension | Full Soul | RAG Only | Delta |")
    lines.append("|-----------|-----------|----------|-------|")

    # Build a lookup for quick access
    dim_map: dict[int, DimensionResult] = {r.dimension_id: r for r in report.dimension_results}

    rag_shs = 0.0

    for dim_id in range(1, 8):
        name = DIMENSION_NAMES.get(dim_id, f"D{dim_id}")
        result = dim_map.get(dim_id)
        full_score = result.score if result else 0.0

        if dim_id == 1:
            # D1: RAG gets partial credit for recall_precision
            rag_recall = 0.0
            if result and "rag_recall_precision" in result.metrics:
                rag_recall = result.metrics["rag_recall_precision"] * 50
            rag_score_str = f"{rag_recall:.1f}"
            delta = full_score - rag_recall
            delta_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
            rag_shs = rag_recall * DIMENSION_WEIGHTS.get(1, 0.20)
        else:
            # D2-D7: RAG scores 0
            rag_score_str = "0.0"
            delta_str = f"+{full_score:.1f}" if full_score > 0 else "—"
            if full_score == 0.0:
                rag_score_str = "N/A"
                delta_str = "—"

        lines.append(f"| {name} (D{dim_id}) | {full_score:.1f} | {rag_score_str} | {delta_str} |")

    # Summary row
    full_shs = report.soul_health_score
    rag_shs_rounded = round(rag_shs, 1)
    delta_shs = full_shs - rag_shs_rounded
    delta_shs_str = f"+{delta_shs:.1f}" if delta_shs >= 0 else f"{delta_shs:.1f}"

    lines.append(
        f"| **Soul Health Score** | **{full_shs}** | **{rag_shs_rounded}** | **{delta_shs_str}** |"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Terminal dashboard with ANSI colors and bar charts
# ---------------------------------------------------------------------------


def _bar(score: float, width: int = 20) -> str:
    """Render a bar chart: [████████░░] score/100."""
    filled = round(score / 100 * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


def print_dashboard(report: SoulHealthReport) -> None:
    """Print a colorful terminal dashboard for a SoulHealthReport.

    Colors are disabled when stdout is not a TTY.
    """
    color = _use_color()

    def c(code: str, text: str) -> str:
        return f"{code}{text}{RESET}" if color else text

    def score_colored(score: float, text: str) -> str:
        return c(_score_color(score), text) if color else text

    label, emoji = _score_label(report.soul_health_score)

    print()
    print(c(BOLD + CYAN, "═══════════════════════════════════════════════════════"))
    print(c(BOLD + CYAN, "           SOUL HEALTH SCORE DASHBOARD"))
    print(c(BOLD + CYAN, "═══════════════════════════════════════════════════════"))
    print()
    print(f"  {c(DIM, 'Run:')}  {report.run_id}")
    print(f"  {c(DIM, 'Seed:')} {report.seed}  {c(DIM, '|  Version:')} {report.version}")
    print(f"  {c(DIM, 'Date:')} {report.timestamp.isoformat()}")
    print()

    # Dimension bars
    for r in report.dimension_results:
        bar = _bar(r.score)
        dim_label = f"  D{r.dimension_id} {r.dimension_name:<25s}"
        score_str = f"{r.score:5.1f}/100"
        pass_fail = f"({len(r.passed)}✓ {len(r.failed)}✗)"

        colored_bar = score_colored(r.score, bar)
        colored_score = score_colored(r.score, score_str)

        print(f"{c(DIM, dim_label)} {colored_bar} {colored_score}  {c(DIM, pass_fail)}")

    # Overall SHS
    print()
    print(c(DIM, "  " + "─" * 53))
    shs = report.soul_health_score
    shs_bar = _bar(shs)
    shs_str = f"{shs:.1f}/100"

    print(
        f"  {c(BOLD, 'SOUL HEALTH SCORE'):25s}    "
        f"{score_colored(shs, shs_bar)} "
        f"{c(BOLD, score_colored(shs, shs_str))}  {emoji} {c(BOLD, label)}"
    )
    print()
    print(c(BOLD + CYAN, "═══════════════════════════════════════════════════════"))
    print()
