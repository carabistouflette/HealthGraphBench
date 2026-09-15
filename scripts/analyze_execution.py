"""Produce clustered uncertainty intervals and temporal/history slices."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from healthgraphbench.evaluation.bootstrap import paired_cluster_bootstrap
from healthgraphbench.evaluation.metrics import average_precision, ranking_auc


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _source_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metric_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    labels = [int(row["label"]) for row in rows]
    scores = [float(row["score"]) for row in rows]
    if not labels:
        return {"rows": 0, "positives": 0, "prevalence": None}
    auc = ranking_auc(labels, scores)
    ap = average_precision(labels, scores)
    return {
        "rows": len(labels),
        "positives": sum(labels),
        "prevalence": sum(labels) / len(labels),
        "roc_auc": auc,
        "average_precision": ap,
        "brier": sum((score - label) ** 2 for score, label in zip(scores, labels, strict=True))
        / len(labels),
    }


def _group_metrics(
    rows: Iterable[Mapping[str, Any]],
    key: Callable[[Mapping[str, Any]], str],
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return {name: _metric_rows(groups[name]) for name in sorted(groups)}


def _method_map(result: Mapping[str, Any], task_name: str) -> dict[str, Mapping[str, Any]]:
    task = next(item for item in result["tasks"] if item["task"] == task_name)
    return {item["method"]: item for item in task["methods"]}


def _pair_rows(
    rows_a: Sequence[Mapping[str, Any]],
    rows_b: Sequence[Mapping[str, Any]],
    key_fields: Sequence[str],
) -> list[dict[str, Any]]:
    grouped_a: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    grouped_b: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows_a:
        grouped_a[tuple(str(row[field]) for field in key_fields)].append(row)
    for row in rows_b:
        grouped_b[tuple(str(row[field]) for field in key_fields)].append(row)
    paired: list[dict[str, Any]] = []
    for key in sorted(set(grouped_a).intersection(grouped_b)):
        left = sorted(grouped_a[key], key=lambda row: (int(row["label"]), str(row.get("problem", ""))))
        right = sorted(grouped_b[key], key=lambda row: (int(row["label"]), str(row.get("problem", ""))))
        for row_a, row_b in zip(left, right, strict=False):
            if int(row_a["label"]) != int(row_b["label"]):
                continue
            paired.append(
                {
                    "cluster": str(row_a.get("cluster", row_a.get("ccn"))),
                    "label": int(row_a["label"]),
                    "score_a": float(row_a["score"]),
                    "score_b": float(row_b["score"]),
                }
            )
    return paired


def _pair_entity_rows(
    rows_a: Sequence[Mapping[str, Any]],
    rows_b: Sequence[Mapping[str, Any]],
    key_fields: Sequence[str],
) -> list[dict[str, Mapping[str, Any] | str]]:
    grouped_a: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    grouped_b: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows_a:
        grouped_a[tuple(str(row[field]) for field in key_fields)].append(row)
    for row in rows_b:
        grouped_b[tuple(str(row[field]) for field in key_fields)].append(row)
    paired: list[dict[str, Mapping[str, Any] | str]] = []
    for key in sorted(set(grouped_a).intersection(grouped_b)):
        left = sorted(grouped_a[key], key=lambda row: str(row.get("product", "")))
        right = sorted(grouped_b[key], key=lambda row: str(row.get("product", "")))
        for row_a, row_b in zip(left, right, strict=False):
            paired.append(
                {
                    "cluster": str(row_a.get("cluster", row_a.get("product", row_a.get("ccn")))),
                    "a": row_a,
                    "b": row_b,
                }
            )
    return paired


def _brier_difference(rows: list[Mapping[str, Any]]) -> float:
    return sum(
        (float(row["score_b"]) - int(row["label"])) ** 2
        - (float(row["score_a"]) - int(row["label"])) ** 2
        for row in rows
    ) / len(rows)


def _pairwise_auc_difference(rows: list[Mapping[str, Any]]) -> float:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["cluster"])].append(row)
    wins_a = 0.0
    wins_b = 0.0
    pairs = 0
    for cluster_rows in grouped.values():
        positives = [row for row in cluster_rows if int(row["label"]) == 1]
        negatives = [row for row in cluster_rows if int(row["label"]) == 0]
        for positive in positives:
            for negative in negatives:
                score_a = float(positive["score_a"]) - float(negative["score_a"])
                score_b = float(positive["score_b"]) - float(negative["score_b"])
                wins_a += 1.0 if score_a > 0 else 0.5 if score_a == 0 else 0.0
                wins_b += 1.0 if score_b > 0 else 0.5 if score_b == 0 else 0.0
                pairs += 1
    if not pairs:
        raise ValueError("pairwise ranking requires both labels in each bootstrap sample")
    return (wins_b - wins_a) / pairs


def _maude_entity_difference(
    rows: list[Mapping[str, Any]],
    metric: str,
) -> float:
    positive_edges = sum(int(row["a"]["positive_edges"]) for row in rows)
    if not positive_edges:
        raise ValueError("MAUDE bootstrap sample has no positive edges")
    if metric == "recall_at_10":
        hits_a = sum(int(row["a"]["hits_at_10"]) for row in rows)
        hits_b = sum(int(row["b"]["hits_at_10"]) for row in rows)
        return hits_b / positive_edges - hits_a / positive_edges
    if metric == "macro_recall_at_10":
        return sum(
            float(row["b"]["recall_at_10"]) - float(row["a"]["recall_at_10"])
            for row in rows
        ) / len(rows)
    if metric == "mrr":
        return sum(
            float(row["b"]["mrr"]) - float(row["a"]["mrr"]) for row in rows
        ) / len(rows)
    raise ValueError(f"unsupported MAUDE metric {metric!r}")


def _classification_difference(
    rows: list[Mapping[str, Any]],
    metric: str,
) -> float:
    labels = [int(row["label"]) for row in rows]
    scores_a = [float(row["score_a"]) for row in rows]
    scores_b = [float(row["score_b"]) for row in rows]
    if metric == "roc_auc":
        value_a = ranking_auc(labels, scores_a)
        value_b = ranking_auc(labels, scores_b)
    elif metric == "average_precision":
        value_a = average_precision(labels, scores_a)
        value_b = average_precision(labels, scores_b)
    else:
        raise ValueError(f"unsupported classification metric {metric!r}")
    if value_a is None or value_b is None:
        raise ValueError(f"{metric} is undefined for a bootstrap sample")
    return value_b - value_a


def _bootstrap(
    rows: Sequence[Mapping[str, Any]],
    statistic: Callable[[list[Mapping[str, Any]]], float],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("paired uncertainty requires overlapping prediction rows")
    return paired_cluster_bootstrap(
        rows,
        lambda row: str(row["cluster"]),
        statistic,
        resamples=resamples,
        seed=seed,
    ).as_dict()


def _maude_support_band(value: int) -> str:
    if value < 10:
        return "1-9"
    if value < 50:
        return "10-49"
    if value < 200:
        return "50-199"
    return "200+"


def _maude_analysis(
    result: Mapping[str, Any],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    methods = _method_map(result, "maude")
    exported = {
        name: list(item.get("prediction_rows", []))
        for name, item in methods.items()
        if item.get("prediction_rows")
    }
    entity_exported = {
        name: list(item.get("entity_metrics", []))
        for name, item in methods.items()
        if item.get("entity_metrics")
    }
    neighbor_name = "neighbor_frequency"
    bpr_name = "graph_message_passing_bpr"
    graphsage_name = "graphsage_link_prediction"
    test_rows = {
        name: [row for row in rows if str(row["quarter"]) >= "2024Q1"]
        for name, rows in exported.items()
    }
    paired = _pair_rows(
        test_rows.get(bpr_name, []),
        test_rows.get(graphsage_name, []),
        ("quarter", "product", "problem", "label"),
    )
    support_slices = {
        name: _group_metrics(
            [row for row in rows if str(row["quarter"]) >= "2024Q1"],
            lambda row: _maude_support_band(int(row["history_support"])),
        )
        for name, rows in exported.items()
    }
    quarterly = {
        name: item.get("quarters", {})
        for name, item in methods.items()
    }
    entity_test_rows = {
        name: [row for row in rows if str(row["quarter"]) >= "2024Q1"]
        for name, rows in entity_exported.items()
    }
    primary_paired = _pair_entity_rows(
        entity_test_rows.get(neighbor_name, []),
        entity_test_rows.get(graphsage_name, []),
        ("quarter", "product"),
    )
    primary_metrics = {}
    for offset, metric in enumerate(("recall_at_10", "macro_recall_at_10", "mrr")):
        primary_metrics[metric] = {
            "comparison": f"{graphsage_name} minus {neighbor_name}",
            "metric": metric,
            "scope": "2024Q1-2025Q4",
            "rows": len(primary_paired),
            "interval": _bootstrap(
                primary_paired,
                lambda rows, metric=metric: _maude_entity_difference(rows, metric),
                resamples=resamples,
                seed=seed + offset,
            ),
        }
    return {
        "quarterly_ranking_metrics": quarterly,
        "test_support_slices": support_slices,
        "prediction_row_methods": sorted(exported),
        "primary_metric_bootstrap": primary_metrics,
        "cluster_bootstrap": {
            "comparison": f"{graphsage_name} minus {bpr_name}",
            "metric": "pairwise_auc",
            "scope": "2024Q1-2025Q4",
            "rows": len(paired),
            "interval": _bootstrap(
                paired, _pairwise_auc_difference, resamples=resamples, seed=seed + 3
            ),
        },
    }
def _cms_history_band(value: int) -> str:
    if value <= 1:
        return "sparse_1"
    return "higher_history_2+"


def _cms_analysis(
    result: Mapping[str, Any],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    methods = _method_map(result, "cms_nursing")
    rows_by_method = {
        name: list(item.get("prediction_rows", [])) for name, item in methods.items()
    }
    annual = {
        name: _group_metrics(rows, lambda row: str(row["year"]))
        for name, rows in rows_by_method.items()
    }
    history_slices = {
        name: _group_metrics(
            [row for row in rows if int(row["year"]) >= 2024],
            lambda row: _cms_history_band(int(row["prior_inspections"])),
        )
        for name, rows in rows_by_method.items()
    }
    nonrelational = rows_by_method.get("facility_history", [])
    relational = rows_by_method.get("facility_plus_combined_ownership", [])
    test_nonrelational = [row for row in nonrelational if int(row["year"]) >= 2024]
    test_relational = [row for row in relational if int(row["year"]) >= 2024]
    paired = _pair_rows(test_nonrelational, test_relational, ("year", "ccn", "date", "label"))
    primary_metrics = {}
    for offset, metric in enumerate(("roc_auc", "average_precision")):
        primary_metrics[metric] = {
            "comparison": "facility_plus_combined_ownership minus facility_history",
            "metric": metric,
            "scope": "2024-2025",
            "rows": len(paired),
            "interval": _bootstrap(
                paired,
                lambda rows, metric=metric: _classification_difference(rows, metric),
                resamples=resamples,
                seed=seed + 4 + offset,
            ),
        }
    return {
        "annual_metrics": annual,
        "test_facility_history_slices": history_slices,
        "primary_metric_bootstrap": primary_metrics,
        "cluster_bootstrap": {
            "comparison": "facility_plus_combined_ownership minus facility_history",
            "metric": "brier",
            "scope": "2024-2025",
            "rows": len(paired),
            "interval": _bootstrap(
                paired, _brier_difference, resamples=resamples, seed=seed + 1
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maude-input", type=Path, required=True)
    parser.add_argument("--cms-input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=_repo_root() / "data" / "manifests" / "v0.1.json")
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=410)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {args.output}")
    started_at_utc = datetime.now(timezone.utc).isoformat()
    maude_result = json.loads(args.maude_input.read_text(encoding="utf-8"))
    cms_result = json.loads(args.cms_input.read_text(encoding="utf-8"))
    result = {
        "analysis_kind": "temporal_slices_and_entity_clustered_uncertainty",
        "benchmark_version": "0.1",
        "row_semantics": {
            "maude": "each eligible positive plus one deterministic historically-known non-positive candidate per positive",
            "cms_nursing": "all retained target inspection rows",
        },
        "execution": {
            "source_commit": _source_commit(),
            "manifest_sha256": _sha256_file(args.manifest),
            "started_at_utc": started_at_utc,
            "model_config": {
                "bootstrap_metric": "task-specific",
                "statistics": {
                    "maude_primary": [
                        "recall_at_10_difference",
                        "macro_recall_at_10_difference",
                        "mrr_difference",
                    ],
                    "maude_secondary": "pairwise_auc_difference",
                    "cms_primary": ["roc_auc_difference", "average_precision_difference"],
                    "cms_secondary": "brier_difference",
                },
                "resamples": args.resamples,
                "seed": args.seed,
                "cluster_units": {"maude": "product", "cms_nursing": "ccn"},
            },
        },
        "inputs": {
            "maude": {
                "path": str(args.maude_input),
                "sha256": _sha256_file(args.maude_input),
                "source_commit": maude_result.get("execution", {}).get("source_commit"),
            },
            "cms_nursing": {
                "path": str(args.cms_input),
                "sha256": _sha256_file(args.cms_input),
                "source_commit": cms_result.get("execution", {}).get("source_commit"),
            },
        },
        "maude": _maude_analysis(maude_result, resamples=args.resamples, seed=args.seed),
        "cms_nursing": _cms_analysis(cms_result, resamples=args.resamples, seed=args.seed),
    }
    result["execution"]["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
