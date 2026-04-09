# analysis.py — Statistical analysis for Soul Protocol research validation.
# Created 2026-03-06.
# ResultsAnalyzer: summary tables, pairwise comparisons, ablation analysis,
# per-use-case breakdown, and markdown report generation.
# Zero external dependencies — uses only stdlib + research.metrics utilities.

from __future__ import annotations

import csv
import os
import statistics
from typing import Any

from .config import MemoryCondition, UseCase
from .metrics import cohens_d, confidence_interval_95, mann_whitney_u

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Ordered from weakest to strongest (ablation chain)
CONDITION_ORDER: list[str] = [
    MemoryCondition.NONE.value,
    MemoryCondition.RAG_ONLY.value,
    MemoryCondition.RAG_SIGNIFICANCE.value,
    MemoryCondition.FULL_NO_EMOTION.value,
    MemoryCondition.FULL_SOUL.value,
]

CONDITION_LABELS: dict[str, str] = {
    MemoryCondition.NONE.value: "No Memory",
    MemoryCondition.RAG_ONLY.value: "RAG Only",
    MemoryCondition.RAG_SIGNIFICANCE.value: "RAG + Significance",
    MemoryCondition.FULL_NO_EMOTION.value: "Full (no emotion)",
    MemoryCondition.FULL_SOUL.value: "Full Soul",
}

USE_CASE_LABELS: dict[str, str] = {
    UseCase.CUSTOMER_SUPPORT.value: "Customer Support",
    UseCase.CODING_ASSISTANT.value: "Coding Assistant",
    UseCase.PERSONAL_COMPANION.value: "Personal Companion",
    UseCase.KNOWLEDGE_WORKER.value: "Knowledge Worker",
}

# Numeric metric keys from AgentRunMetrics.to_row()
NUMERIC_METRICS: list[str] = [
    "recall_precision",
    "recall_recall",
    "recall_hit_rate",
    "emotion_accuracy",
    "bond_final",
    "bond_growth_rate",
    "personality_drift",
    "memory_compression",
    "memory_count",
    "skills_discovered",
    "skills_max_level",
]

# Subset used in ablation (the most telling metrics)
KEY_METRICS: list[str] = [
    "recall_precision",
    "recall_hit_rate",
    "emotion_accuracy",
    "bond_final",
    "personality_drift",
    "memory_compression",
]

# Significance thresholds
ALPHA = 0.05

# Effect size interpretation (|d|)
EFFECT_THRESHOLDS: list[tuple[float, str]] = [
    (0.2, "negligible"),
    (0.5, "small"),
    (0.8, "medium"),
    (float("inf"), "large"),
]


# ---------------------------------------------------------------------------
# ASCII table formatter
# ---------------------------------------------------------------------------


def format_table(headers: list[str], rows: list[list[str]], align: str | None = None) -> str:
    """Render a markdown-compatible ASCII table.

    Parameters
    ----------
    headers:
        Column headers.
    rows:
        List of rows, each row a list of cell strings.
    align:
        Optional alignment string per column. 'l' = left, 'r' = right, 'c' = center.
        If shorter than headers, remaining columns default to left.
    """
    if not headers:
        return ""

    num_cols = len(headers)
    # Ensure every row has the right number of columns
    normalised_rows = [r + [""] * (num_cols - len(r)) for r in rows]

    # Compute column widths
    col_widths = [len(h) for h in headers]
    for row in normalised_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    # Build alignment spec
    if align is None:
        align = "l" * num_cols
    align = align.ljust(num_cols, "l")

    def _pad(text: str, width: int, a: str) -> str:
        if a == "r":
            return text.rjust(width)
        if a == "c":
            return text.center(width)
        return text.ljust(width)

    def _sep(a: str, width: int) -> str:
        if a == "r":
            return "-" * (width - 1) + ":"
        if a == "c":
            return ":" + "-" * (width - 2) + ":"
        return "-" * width

    # Header row
    header_line = (
        "| " + " | ".join(_pad(h, col_widths[i], align[i]) for i, h in enumerate(headers)) + " |"
    )

    # Separator
    sep_line = "| " + " | ".join(_sep(align[i], col_widths[i]) for i in range(num_cols)) + " |"

    # Data rows
    data_lines = []
    for row in normalised_rows:
        line = (
            "| " + " | ".join(_pad(row[i], col_widths[i], align[i]) for i in range(num_cols)) + " |"
        )
        data_lines.append(line)

    return "\n".join([header_line, sep_line] + data_lines)


def _fmt(val: float, decimals: int = 3) -> str:
    """Format a float to *decimals* places."""
    return f"{val:.{decimals}f}"


def _effect_label(d: float) -> str:
    """Human-readable effect size label for |d|."""
    abs_d = abs(d)
    for threshold, label in EFFECT_THRESHOLDS:
        if abs_d < threshold:
            return label
    return "large"  # pragma: no cover


def _sig_stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < ALPHA:
        return "*"
    return "ns"


# ---------------------------------------------------------------------------
# ResultsAnalyzer
# ---------------------------------------------------------------------------


class ResultsAnalyzer:
    """Analyse a list of flat row dicts produced by ``AgentRunMetrics.to_row()``."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    # -- helpers ----------------------------------------------------------

    def _group_by(self, *keys: str) -> dict[tuple[str, ...], list[dict[str, Any]]]:
        """Group rows by one or more keys, returning ordered dict."""
        groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for row in self.rows:
            key = tuple(str(row[k]) for k in keys)
            groups.setdefault(key, []).append(row)
        return groups

    @staticmethod
    def _extract_metric(rows: list[dict[str, Any]], metric: str) -> list[float]:
        """Pull a list of floats for *metric* from a group of rows."""
        return [float(r[metric]) for r in rows if metric in r]

    def _rows_for_condition(self, condition: str) -> list[dict[str, Any]]:
        return [r for r in self.rows if r["condition"] == condition]

    # -- 1. summary_table ------------------------------------------------

    def summary_table(self) -> list[dict[str, Any]]:
        """Aggregate statistics grouped by condition x use_case.

        Returns one dict per group containing mean, std, median, and 95% CI
        for every numeric metric.
        """
        groups = self._group_by("condition", "use_case")
        results: list[dict[str, Any]] = []

        for (condition, use_case), group_rows in groups.items():
            entry: dict[str, Any] = {
                "condition": condition,
                "use_case": use_case,
                "n": len(group_rows),
            }
            for metric in NUMERIC_METRICS:
                values = self._extract_metric(group_rows, metric)
                if not values:
                    entry[f"{metric}_mean"] = 0.0
                    entry[f"{metric}_std"] = 0.0
                    entry[f"{metric}_median"] = 0.0
                    entry[f"{metric}_ci_lo"] = 0.0
                    entry[f"{metric}_ci_hi"] = 0.0
                    continue

                pure = [float(v) for v in values]
                entry[f"{metric}_mean"] = statistics.mean(pure)
                entry[f"{metric}_std"] = statistics.stdev(pure) if len(pure) > 1 else 0.0
                entry[f"{metric}_median"] = statistics.median(pure)
                ci_lo, ci_hi = confidence_interval_95(values)
                entry[f"{metric}_ci_lo"] = ci_lo
                entry[f"{metric}_ci_hi"] = ci_hi

            results.append(entry)

        return results

    # -- 2. pairwise_comparisons -----------------------------------------

    def pairwise_comparisons(self) -> list[dict[str, Any]]:
        """Compare FULL_SOUL vs every other condition for each numeric metric.

        Returns a list of dicts with condition_a (FULL_SOUL), condition_b,
        metric, cohens_d, effect_label, mann_whitney_u, p_value, significant.
        """
        full_soul = MemoryCondition.FULL_SOUL.value
        soul_rows = self._rows_for_condition(full_soul)

        comparisons: list[dict[str, Any]] = []
        for cond in CONDITION_ORDER:
            if cond == full_soul:
                continue
            other_rows = self._rows_for_condition(cond)
            for metric in NUMERIC_METRICS:
                soul_vals = self._extract_metric(soul_rows, metric)
                other_vals = self._extract_metric(other_rows, metric)

                d = cohens_d(soul_vals, other_vals)
                u_stat, p_val = mann_whitney_u(soul_vals, other_vals)

                comparisons.append(
                    {
                        "condition_a": full_soul,
                        "condition_b": cond,
                        "metric": metric,
                        "cohens_d": d,
                        "effect_label": _effect_label(d),
                        "mann_whitney_u": u_stat,
                        "p_value": p_val,
                        "significant": p_val < ALPHA,
                    }
                )

        return comparisons

    # -- 3. ablation_table -----------------------------------------------

    def ablation_table(self) -> list[dict[str, Any]]:
        """Incremental deltas along the ablation chain for key metrics.

        Each entry shows the delta from the previous condition to the current
        one, plus the absolute mean of each condition.
        """
        # Compute per-condition means for key metrics
        cond_means: dict[str, dict[str, float]] = {}
        for cond in CONDITION_ORDER:
            cond_rows = self._rows_for_condition(cond)
            cond_means[cond] = {}
            for metric in KEY_METRICS:
                vals = self._extract_metric(cond_rows, metric)
                cond_means[cond][metric] = statistics.mean(vals) if vals else 0.0

        results: list[dict[str, Any]] = []
        for i, cond in enumerate(CONDITION_ORDER):
            entry: dict[str, Any] = {
                "condition": cond,
                "label": CONDITION_LABELS.get(cond, cond),
            }
            for metric in KEY_METRICS:
                entry[f"{metric}_mean"] = cond_means[cond][metric]
                if i == 0:
                    entry[f"{metric}_delta"] = 0.0
                else:
                    prev = CONDITION_ORDER[i - 1]
                    entry[f"{metric}_delta"] = cond_means[cond][metric] - cond_means[prev][metric]
            results.append(entry)

        # Identify the biggest jump per metric
        for metric in KEY_METRICS:
            best_idx = 0
            best_delta = 0.0
            for i, entry in enumerate(results):
                d = abs(entry[f"{metric}_delta"])
                if d > best_delta:
                    best_delta = d
                    best_idx = i
            results[best_idx][f"{metric}_biggest_jump"] = True

        return results

    # -- 4. use_case_analysis --------------------------------------------

    def use_case_analysis(self) -> list[dict[str, Any]]:
        """Per-use-case breakdown: best condition per metric + emotion impact.

        Returns one dict per use_case with best condition for each key metric
        and the delta that emotion adds (FULL_SOUL - FULL_NO_EMOTION).
        """
        results: list[dict[str, Any]] = []

        use_case_values = sorted({r["use_case"] for r in self.rows})

        for uc in use_case_values:
            uc_rows = [r for r in self.rows if r["use_case"] == uc]
            entry: dict[str, Any] = {
                "use_case": uc,
                "label": USE_CASE_LABELS.get(uc, uc),
                "n": len(uc_rows),
            }

            # For each key metric, find the best condition (highest mean,
            # except personality_drift where lower is better)
            for metric in KEY_METRICS:
                best_cond = None
                best_val = None
                lower_is_better = metric == "personality_drift"

                for cond in CONDITION_ORDER:
                    cond_uc_rows = [r for r in uc_rows if r["condition"] == cond]
                    vals = self._extract_metric(cond_uc_rows, metric)
                    if not vals:
                        continue
                    m = statistics.mean(vals)
                    if best_val is None:
                        best_cond, best_val = cond, m
                    elif lower_is_better and m < best_val:
                        best_cond, best_val = cond, m
                    elif not lower_is_better and m > best_val:
                        best_cond, best_val = cond, m

                entry[f"{metric}_best_condition"] = best_cond
                entry[f"{metric}_best_value"] = best_val if best_val is not None else 0.0

            # Emotion delta: FULL_SOUL - FULL_NO_EMOTION
            soul_rows = [r for r in uc_rows if r["condition"] == MemoryCondition.FULL_SOUL.value]
            no_emo_rows = [
                r for r in uc_rows if r["condition"] == MemoryCondition.FULL_NO_EMOTION.value
            ]

            for metric in KEY_METRICS:
                soul_vals = self._extract_metric(soul_rows, metric)
                no_emo_vals = self._extract_metric(no_emo_rows, metric)
                soul_mean = statistics.mean(soul_vals) if soul_vals else 0.0
                no_emo_mean = statistics.mean(no_emo_vals) if no_emo_vals else 0.0
                entry[f"{metric}_emotion_delta"] = soul_mean - no_emo_mean

            results.append(entry)

        return results

    # -- 5. generate_report ----------------------------------------------

    def generate_report(self, output_dir: str) -> str:
        """Write a full markdown report + CSV files to *output_dir*.

        Returns the markdown report as a string.
        """
        os.makedirs(output_dir, exist_ok=True)

        summary = self.summary_table()
        pairwise = self.pairwise_comparisons()
        ablation = self.ablation_table()
        use_cases = self.use_case_analysis()

        sections: list[str] = []

        # -- Title ---------------------------------------------------------
        sections.append("# Soul Protocol — Statistical Analysis Report")
        sections.append("")
        sections.append(f"Total data rows: {len(self.rows)}")
        conditions_present = sorted({r["condition"] for r in self.rows})
        use_cases_present = sorted({r["use_case"] for r in self.rows})
        sections.append(f"Conditions: {', '.join(conditions_present)}")
        sections.append(f"Use cases: {', '.join(use_cases_present)}")
        sections.append("")

        # -- Summary Table -------------------------------------------------
        sections.append("## 1. Summary Statistics (Condition x Use Case)")
        sections.append("")

        # One sub-table per metric for readability
        for metric in NUMERIC_METRICS:
            sections.append(f"### {metric}")
            sections.append("")
            headers = ["Condition", "Use Case", "N", "Mean", "Std", "Median", "95% CI"]
            table_rows: list[list[str]] = []
            for s in summary:
                table_rows.append(
                    [
                        CONDITION_LABELS.get(s["condition"], s["condition"]),
                        USE_CASE_LABELS.get(s["use_case"], s["use_case"]),
                        str(s["n"]),
                        _fmt(s[f"{metric}_mean"]),
                        _fmt(s[f"{metric}_std"]),
                        _fmt(s[f"{metric}_median"]),
                        f"[{_fmt(s[f'{metric}_ci_lo'])}, {_fmt(s[f'{metric}_ci_hi'])}]",
                    ]
                )
            sections.append(format_table(headers, table_rows, "llrrrrr"))
            sections.append("")

        # -- Pairwise Comparisons ------------------------------------------
        sections.append("## 2. Pairwise Comparisons (FULL_SOUL vs Others)")
        sections.append("")
        sections.append("Significance: *** p<0.001, ** p<0.01, * p<0.05, ns = not significant")
        sections.append("")

        pw_headers = ["vs Condition", "Metric", "Cohen's d", "Effect", "U", "p-value", "Sig"]
        pw_rows: list[list[str]] = []
        for p in pairwise:
            pw_rows.append(
                [
                    CONDITION_LABELS.get(p["condition_b"], p["condition_b"]),
                    p["metric"],
                    _fmt(p["cohens_d"]),
                    p["effect_label"],
                    _fmt(p["mann_whitney_u"], 1),
                    _fmt(p["p_value"], 4),
                    _sig_stars(p["p_value"]),
                ]
            )
        sections.append(format_table(pw_headers, pw_rows, "llrllrl"))
        sections.append("")

        # -- Ablation Table ------------------------------------------------
        sections.append("## 3. Ablation Analysis")
        sections.append("")
        sections.append(
            "Incremental improvement along the pipeline. "
            "Values marked with (*) indicate the largest single jump for that metric."
        )
        sections.append("")

        abl_headers = ["Condition"]
        for metric in KEY_METRICS:
            abl_headers.extend([f"{metric} (mean)", f"{metric} (delta)"])
        abl_rows: list[list[str]] = []
        for a in ablation:
            row_cells: list[str] = [a["label"]]
            for metric in KEY_METRICS:
                mean_str = _fmt(a[f"{metric}_mean"])
                delta_val = a[f"{metric}_delta"]
                delta_str = _fmt(delta_val)
                if delta_val > 0:
                    delta_str = "+" + delta_str
                if a.get(f"{metric}_biggest_jump"):
                    delta_str += " (*)"
                row_cells.extend([mean_str, delta_str])
            abl_rows.append(row_cells)
        sections.append(format_table(abl_headers, abl_rows))
        sections.append("")

        # -- Use Case Analysis ---------------------------------------------
        sections.append("## 4. Per-Use-Case Analysis")
        sections.append("")

        for uc_entry in use_cases:
            uc_label = uc_entry["label"]
            sections.append(f"### {uc_label} (n={uc_entry['n']})")
            sections.append("")

            uc_headers = ["Metric", "Best Condition", "Best Value", "Emotion Delta"]
            uc_rows: list[list[str]] = []
            for metric in KEY_METRICS:
                best_cond = uc_entry.get(f"{metric}_best_condition", "")
                best_val = uc_entry.get(f"{metric}_best_value", 0.0)
                emo_delta = uc_entry.get(f"{metric}_emotion_delta", 0.0)
                emo_str = _fmt(emo_delta)
                if emo_delta > 0:
                    emo_str = "+" + emo_str
                uc_rows.append(
                    [
                        metric,
                        CONDITION_LABELS.get(best_cond, str(best_cond)) if best_cond else "N/A",
                        _fmt(best_val),
                        emo_str,
                    ]
                )
            sections.append(format_table(uc_headers, uc_rows, "llrr"))
            sections.append("")

        # -- Write report --------------------------------------------------
        report = "\n".join(sections)

        report_path = os.path.join(output_dir, "analysis_report.md")
        with open(report_path, "w") as f:
            f.write(report)

        # -- Write CSVs ----------------------------------------------------
        self._write_csv(
            os.path.join(output_dir, "summary_statistics.csv"),
            summary,
        )
        self._write_csv(
            os.path.join(output_dir, "pairwise_comparisons.csv"),
            pairwise,
        )

        return report

    @staticmethod
    def _write_csv(path: str, rows: list[dict[str, Any]]) -> None:
        """Write a list of dicts to a CSV file."""
        if not rows:
            return
        fieldnames = list(rows[0].keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
