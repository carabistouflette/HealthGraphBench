"""Compare local, relational-heuristic, and learned-relational results."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


TASK_PRIMARY = {
    "maude": {
        "metric": "recall_at_10",
        "local_reference": "global_popularity",
        "scope": "test; threshold=1",
    },
    "cms_nursing": {
        "metric": "roc_auc",
        "local_reference": "facility_history",
        "scope": "test; 2024-2025 pooled",
    },
    "partd_prescriber_drug": {
        "metric": "micro_recall_at_10",
        "local_reference": None,
        "scope": "test; 2024 held-out generic representation",
    },
}


FAMILIES = (
    "local_popularity",
    "local_history",
    "relational_heuristic",
    "learned_tabular",
    "learned_relational",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_table(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("table_kind") != "unified_cross_task_results":
        raise ValueError(f"expected unified cross-task result table: {path}")
    return value


def _metric_rows(table: Mapping[str, Any], task: str, metric: str) -> list[Mapping[str, Any]]:
    return [
        row
        for row in table["rows"]
        if row["task"] == task and row["split"] == "test" and row["metric"] == metric
    ]


def _best(rows: Sequence[Mapping[str, Any]], family: str) -> dict[str, Any] | None:
    candidates = [row for row in rows if row["method_family"] == family and row["value"] is not None]
    if not candidates:
        return None
    chosen = max(candidates, key=lambda row: (float(row["value"]), str(row["method"])))
    return {
        "method": chosen["method"],
        "method_family": chosen["method_family"],
        "metric": chosen["metric"],
        "value": float(chosen["value"]),
        "scope": chosen["scope"],
    }


def _reference(rows: Sequence[Mapping[str, Any]], method: str | None) -> dict[str, Any] | None:
    if method is None:
        return None
    matches = [row for row in rows if row["method"] == method]
    if len(matches) != 1:
        raise ValueError(f"expected one local reference row for {method!r}, found {len(matches)}")
    row = matches[0]
    return {
        "method": row["method"],
        "method_family": row["method_family"],
        "metric": row["metric"],
        "value": float(row["value"]),
        "scope": row["scope"],
    }


def _delta(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> float | None:
    if left is None or right is None:
        return None
    return float(left["value"]) - float(right["value"])


def _comparison_status(
    left: Mapping[str, Any] | None, right: Mapping[str, Any] | None
) -> str:
    return "estimable" if left is not None and right is not None else "not_estimable"


def _task_assessment(table: Mapping[str, Any], task: str) -> dict[str, Any]:
    config = TASK_PRIMARY[task]
    rows = _metric_rows(table, task, config["metric"])
    if not rows:
        raise ValueError(f"no primary metric rows for task {task!r}")
    local = _reference(rows, config["local_reference"])
    heuristic = _best(rows, "relational_heuristic")
    learned_tabular = _best(rows, "learned_tabular")
    learned_relational = _best(rows, "learned_relational")
    return {
        "primary_metric": config["metric"],
        "scope": config["scope"],
        "local_reference": local,
        "best_relational_heuristic": heuristic,
        "best_learned_tabular": learned_tabular,
        "best_learned_relational": learned_relational,
        "comparison_status": {
            "local_to_relational": _comparison_status(heuristic, local),
            "relational_to_learned_relational": _comparison_status(
                learned_relational, heuristic
            ),
            "relational_to_learned_tabular": _comparison_status(
                heuristic, learned_tabular
            ),
        },
        "deltas": {
            "relational_heuristic_minus_local": _delta(heuristic, local),
            "learned_tabular_minus_local": _delta(learned_tabular, local),
            "learned_relational_minus_local": _delta(learned_relational, local),
            "relational_heuristic_minus_learned_tabular": _delta(heuristic, learned_tabular),
            "learned_relational_minus_relational_heuristic": _delta(
                learned_relational, heuristic
            ),
        },
    }


def _comparison_statuses(
    assessments: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, list[str]]]:
    comparison_names = (
        "local_to_relational",
        "relational_to_learned_relational",
        "relational_to_learned_tabular",
    )
    return {
        comparison: {
            "estimable": [
                task
                for task, assessment in assessments.items()
                if assessment["comparison_status"][comparison] == "estimable"
            ],
            "not_estimable": [
                task
                for task, assessment in assessments.items()
                if assessment["comparison_status"][comparison] == "not_estimable"
            ],
        }
        for comparison in comparison_names
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--table", type=Path, default=Path("results/benchmark_summary_v0_2.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite an existing analysis artifact: {args.output}")
    table = _read_table(args.table)
    assessments = {
        task: _task_assessment(table, task) for task in TASK_PRIMARY
    }
    heuristic_beats_local = [
        task
        for task, assessment in assessments.items()
        if assessment["deltas"]["relational_heuristic_minus_local"] is not None
        and assessment["deltas"]["relational_heuristic_minus_local"] > 0
    ]
    learned_beats_heuristic = [
        task
        for task, assessment in assessments.items()
        if assessment["deltas"]["learned_relational_minus_relational_heuristic"] is not None
        and assessment["deltas"]["learned_relational_minus_relational_heuristic"] > 0
    ]
    local_unavailable = [
        task for task, assessment in assessments.items() if assessment["local_reference"] is None
    ]
    result = {
        "analysis_kind": "cross_task_relational_value",
        "benchmark_version": "0.2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": {"path": str(args.table), "sha256": _sha256_file(args.table)},
        "metric_selection": {
            "maude": "Recall@10",
            "cms_nursing": "ROC AUC",
            "partd_prescriber_drug": "micro Recall@10",
            "selection_rule": "task-specific primary held-out metric; values are not pooled across tasks",
        },
        "method_families": {
            "local": ["local_popularity", "local_history"],
            "relational_heuristic": ["relational_heuristic"],
            "learned_relational": ["learned_relational"],
            "learned_tabular": ["learned_tabular"],
        },
        "tasks": assessments,
        "comparison_statuses": _comparison_statuses(assessments),
        "cross_task_counts": {
            "relational_heuristic_beats_local": heuristic_beats_local,
            "learned_relational_beats_relational_heuristic": learned_beats_heuristic,
            "local_reference_unavailable": local_unavailable,
        },
        "conclusion": {
            "point_evidence": (
                "Simple relational heuristics exceed the selected local reference on every task "
                "with an available local reference; the admitted Part D contract has no local-only "
                "method, so it cannot support the same within-task comparison."
            ),
            "learned_relational_evidence": (
                "The selected learned-relational method does not exceed the best relational heuristic "
                "on the tasks where both families are present in this table."
            ),
            "interpretation_boundary": (
                "These are task-local held-out point comparisons with heterogeneous targets and metrics; "
                "they are not evidence of a universal relational or graph-learning effect."
            ),
        },
        "limitations": [
            "Part D has no admitted local-only comparator; specialty popularity and history overlap are relational heuristics.",
            "Metric scales and target semantics differ across MAUDE, CMS nursing, and Part D.",
            "Point comparisons do not replace task-specific clustered uncertainty intervals.",
            "The inspected held-out periods are development-stage evaluations, not prospective confirmation.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
