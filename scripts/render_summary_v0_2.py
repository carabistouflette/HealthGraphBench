"""Render a unified long-form result table for the v0.2 task suite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


MAUDE_METHODS = (
    "global_popularity",
    "neighbor_frequency",
    "logistic_tabular",
    "boosted_stumps_tabular",
    "matrix_factorization_spectral",
    "graph_message_passing_bpr",
    "graphsage_link_prediction",
)
CMS_METHODS = ("prevalence", "facility_history", "facility_plus_combined_ownership")
PARTD_METHODS = (
    "specialty_popularity",
    "history_overlap",
    "tabular_logistic",
    "graph_bpr",
)
TOP_KS = (5, 10, 20)


METHOD_FAMILIES = {
    "global_popularity": "local_popularity",
    "neighbor_frequency": "relational_heuristic",
    "logistic_tabular": "learned_tabular",
    "boosted_stumps_tabular": "learned_tabular",
    "matrix_factorization_spectral": "learned_relational",
    "graph_message_passing_bpr": "learned_relational",
    "graphsage_link_prediction": "learned_relational",
    "prevalence": "local_popularity",
    "facility_history": "local_history",
    "facility_plus_combined_ownership": "relational_heuristic",
    "specialty_popularity": "relational_heuristic",
    "history_overlap": "relational_heuristic",
    "tabular_logistic": "learned_tabular",
    "graph_bpr": "learned_relational",
}


TABLE_FIELDS = (
    "task",
    "method",
    "method_family",
    "split",
    "scope",
    "denominator_scope",
    "metric",
    "direction",
    "value",
    "source_artifact",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _method_map(result: Mapping[str, Any], task: str) -> dict[str, Mapping[str, Any]]:
    if "tasks" in result:
        task_record = next(item for item in result["tasks"] if item["task"] == task)
    else:
        task_record = result
    return {str(item["method"]): item for item in task_record["methods"]}


def _row(
    *,
    task: str,
    method: str,
    split: str,
    scope: str,
    denominator_scope: str,
    metric: str,
    value: Any,
    direction: str,
    source_artifact: str,
) -> dict[str, Any]:
    return {
        "task": task,
        "method": method,
        "method_family": METHOD_FAMILIES[method],
        "split": split,
        "scope": scope,
        "denominator_scope": denominator_scope,
        "metric": metric,
        "direction": direction,
        "value": value,
        "source_artifact": source_artifact,
    }


def _maude_rows(result: Mapping[str, Any], source_artifact: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    methods = _method_map(result, "maude")
    for method in MAUDE_METHODS:
        metrics = methods[method]["test"]["thresholds"]["1"]
        for cutoff in TOP_KS:
            rows.append(
                _row(
                    task="maude",
                    method=method,
                    split="test",
                    scope="2024Q1-2025Q4; threshold=1",
                    denominator_scope="eligible positive edges",
                    metric=f"recall_at_{cutoff}",
                    value=metrics[f"recall_at_{cutoff}"],
                    direction="higher_is_better",
                    source_artifact=source_artifact,
                )
            )
            rows.append(
                _row(
                    task="maude",
                    method=method,
                    split="test",
                    scope="2024Q1-2025Q4; threshold=1",
                    denominator_scope="eligible product-quarter macro average",
                    metric=f"macro_recall_at_{cutoff}",
                    value=metrics[f"macro_recall_at_{cutoff}"],
                    direction="higher_is_better",
                    source_artifact=source_artifact,
                )
            )
        rows.append(
            _row(
                task="maude",
                method=method,
                split="test",
                scope="2024Q1-2025Q4; threshold=1",
                denominator_scope="eligible product-quarter observations",
                metric="mrr",
                value=metrics["mrr"],
                direction="higher_is_better",
                source_artifact=source_artifact,
            )
        )
    return rows


def _cms_rows(result: Mapping[str, Any], source_artifact: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    methods = _method_map(result, "cms_nursing")
    for method in CMS_METHODS:
        metrics = methods[method]["test"]
        for metric, source_metric, direction in (
            ("roc_auc", "roc_auc", "higher_is_better"),
            ("average_precision", "average_precision", "higher_is_better"),
            ("top_decile_precision", "precision_at_top_10_percent", "higher_is_better"),
            ("top_decile_recall", "recall_at_top_10_percent", "higher_is_better"),
            ("brier", "brier", "lower_is_better"),
        ):
            rows.append(
                _row(
                    task="cms_nursing",
                    method=method,
                    split="test",
                    scope="2024-2025 pooled",
                    denominator_scope="all retained target inspection rows",
                    metric=metric,
                    value=metrics[source_metric],
                    direction=direction,
                    source_artifact=source_artifact,
                )
            )
    return rows


def _partd_rows(result: Mapping[str, Any], source_artifact: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    methods = _method_map(result, "partd_prescriber_drug")
    for method in PARTD_METHODS:
        metrics = methods[method]["test"]
        positive = metrics["positive_containing_provider_years"]
        all_provider_years = metrics["all_provider_years"]
        for cutoff in TOP_KS:
            for prefix, denominator in (
                ("micro_recall", "positive-containing provider-years; micro positives"),
                (
                    "provider_macro_recall",
                    "positive-containing provider-years; provider macro average",
                ),
            ):
                rows.append(
                    _row(
                        task="partd_prescriber_drug",
                        method=method,
                        split="test",
                        scope="2024 held-out test; generic primary representation",
                        denominator_scope=denominator,
                        metric=f"{prefix}_at_{cutoff}",
                        value=positive[f"{prefix}_at_{cutoff}"],
                        direction="higher_is_better",
                        source_artifact=source_artifact,
                    )
                )
            rows.append(
                _row(
                    task="partd_prescriber_drug",
                    method=method,
                    split="test",
                    scope="2024 held-out test; generic primary representation",
                    denominator_scope="all eligible provider-years; actual recommendation slots",
                    metric=f"precision_at_{cutoff}",
                    value=all_provider_years[f"precision_at_{cutoff}"],
                    direction="higher_is_better",
                    source_artifact=source_artifact,
                )
            )
            rows.append(
                _row(
                    task="partd_prescriber_drug",
                    method=method,
                    split="test",
                    scope="2024 held-out test; generic primary representation",
                    denominator_scope="all eligible provider-years",
                    metric=f"recommendation_burden_at_{cutoff}",
                    value=all_provider_years[
                        f"recommendation_burden_per_eligible_provider_year_at_{cutoff}"
                    ],
                    direction="descriptive_load",
                    source_artifact=source_artifact,
                )
            )
        rows.append(
            _row(
                task="partd_prescriber_drug",
                method=method,
                split="test",
                scope="2024 held-out test; generic primary representation",
                denominator_scope="positive-containing provider-years; first relevant rank",
                metric="mrr",
                value=positive["mrr"],
                direction="higher_is_better",
                source_artifact=source_artifact,
            )
        )
    return rows


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TABLE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _bar_panel(
    lines: list[str],
    rows: Sequence[Mapping[str, Any]],
    metric: str,
    title: str,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    selected = [row for row in rows if row["metric"] == metric]
    maximum = max((float(row["value"]) for row in selected), default=1.0)
    maximum = max(maximum * 1.15, 0.1)
    baseline = y + height
    gap = width / max(1, len(selected))
    bar_width = gap * 0.68
    lines.extend(
        [
            f'<text x="{x}" y="{y - 18}" class="title">{html.escape(title)}</text>',
            f'<line x1="{x}" y1="{baseline}" x2="{x + width}" y2="{baseline}" class="axis"/>',
            f'<line x1="{x}" y1="{y}" x2="{x}" y2="{baseline}" class="axis"/>',
            f'<text x="{x - 8}" y="{baseline + 4}" text-anchor="end" class="tick">0</text>',
            f'<text x="{x - 8}" y="{y + 4}" text-anchor="end" class="tick">{maximum:.2f}</text>',
        ]
    )
    for index, row in enumerate(selected):
        value = float(row["value"])
        bar_height = value / maximum * height
        bar_x = x + index * gap + (gap - bar_width) / 2
        bar_y = baseline - bar_height
        color = "#3973ac" if row["method_family"] == "local_popularity" else "#b23a48" if "learned_relational" in row["method_family"] else "#4f8f62"
        label = str(row["method"])
        lines.extend(
            [
                f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}"/>',
                f'<text x="{bar_x + bar_width / 2:.1f}" y="{bar_y - 5:.1f}" text-anchor="middle" class="value">{value:.3f}</text>',
                f'<text x="{bar_x + bar_width / 2:.1f}" y="{baseline + 18}" text-anchor="end" transform="rotate(-35 {bar_x + bar_width / 2:.1f} {baseline + 18})" class="label">{html.escape(label)}</text>',
            ]
        )


def _write_svg(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="860" viewBox="0 0 1800 860">',
        '<style>.title{font:700 18px sans-serif}.axis{stroke:#333}.tick,.label,.value{font:12px sans-serif}.value{font-weight:700}</style>',
        '<rect width="1800" height="860" fill="white"/>',
        '<text x="40" y="34" class="title">HealthGraphBench v0.2 — unified held-out task summary</text>',
    ]
    _bar_panel(lines, [row for row in rows if row["task"] == "maude"], "recall_at_10", "MAUDE test Recall@10", 80, 100, 500, 420)
    _bar_panel(lines, [row for row in rows if row["task"] == "cms_nursing"], "roc_auc", "CMS test ROC AUC", 650, 100, 500, 420)
    _bar_panel(
        lines,
        [row for row in rows if row["task"] == "partd_prescriber_drug"],
        "micro_recall_at_10",
        "Part D held-out micro Recall@10",
        1220,
        100,
        500,
        420,
    )
    lines.extend(
        [
            '<text x="80" y="620" class="tick">Part D uses exact trimmed generic identity and all eligible candidates.</text>',
            '<text x="650" y="620" class="tick">Raw metric scales differ; panels are task-local, not pooled scores.</text>',
            '<text x="80" y="660" class="tick">Colors distinguish local/popularity, relational heuristic, and learned relational families.</text>',
            '<text x="80" y="700" class="tick">Held-out periods were inspected during development; this is not prospective confirmation.</text>',
            '</svg>',
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maude", type=Path, default=Path("results/maude_execution_v0_1_20260915.json"))
    parser.add_argument("--cms", type=Path, default=Path("results/cms_execution_v0_1_20260915.json"))
    parser.add_argument("--partd", type=Path, default=Path("results/partd_execution_v0_2_20260916.json"))
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-svg", type=Path, required=True)
    args = parser.parse_args()
    outputs = (args.output_json, args.output_csv, args.output_svg)
    if any(path.exists() for path in outputs):
        raise FileExistsError("refusing to overwrite an existing v0.2 summary artifact")
    inputs = (args.maude, args.cms, args.partd)
    if any(not path.is_file() for path in inputs):
        missing = [str(path) for path in inputs if not path.is_file()]
        raise FileNotFoundError("missing result input(s): " + ", ".join(missing))
    maude = _read_object(args.maude)
    cms = _read_object(args.cms)
    partd = _read_object(args.partd)
    rows = [
        *_maude_rows(maude, str(args.maude)),
        *_cms_rows(cms, str(args.cms)),
        *_partd_rows(partd, str(args.partd)),
    ]
    summary = {
        "table_kind": "unified_cross_task_results",
        "benchmark_version": "0.2",
        "suite_status": "admitted_replication_extension",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metric_note": "Rows preserve task-specific denominators and metric direction; values are not pooled across tasks.",
        "source_inputs": {
            str(path): {"sha256": _sha256_file(path), "bytes": path.stat().st_size}
            for path in inputs
        },
        "fields": list(TABLE_FIELDS),
        "rows": rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_svg.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_csv, rows)
    _write_svg(args.output_svg, rows)
    args.output_json.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output_json}, {args.output_csv}, and {args.output_svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
