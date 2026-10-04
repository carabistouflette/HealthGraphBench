"""Bounded rolling-origin stability and relation ablation analysis."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from statistics import mean, median
from typing import Any

from healthgraphbench.data import sha256_file
from healthgraphbench.evaluation.bootstrap import cluster_bootstrap_indices
from healthgraphbench.evaluation.numpy_metrics import average_precision_numpy

from .clinical_trials import (
    ANALYSIS_VERSION as BASE_ANALYSIS_VERSION,
    SNAPSHOT_DATES,
    SNAPSHOT_ROLES,
    _Example,
    _OriginResult,
    _attach_future_labels,
    _canonical_json,
    _fit_logistic,
    _metrics,
    _parse_origin_snapshot,
    _predict,
    _safe_source_path,
    _source_provenance,
    _validate_manifest,
)


ANALYSIS_VERSION = "clinical_trials_stability_v2_numpy"
COHORT_SIZE = 2000
BOOTSTRAP_RESAMPLES = 1000
TOP_LEVEL_ORIGIN_DATES = tuple(SNAPSHOT_DATES[:-1])
EVALUATION_ORIGIN_DATES = tuple(SNAPSHOT_DATES[1:-1])
LOCAL_GROUP = "trial_local_logistic"
SPONSOR_GROUP = "local_plus_sponsor_logistic"
ALL_CONTEXT_GROUP = "heterogeneous_context_by_entity_logistic"
MODEL_GROUPS: tuple[str, ...] = (
    LOCAL_GROUP,
    SPONSOR_GROUP,
    "local_plus_sponsor_condition_logistic",
    "local_plus_sponsor_facility_logistic",
    "local_plus_sponsor_intervention_logistic",
    "local_plus_sponsor_collaborator_logistic",
    ALL_CONTEXT_GROUP,
)
MODEL_LABELS = {
    LOCAL_GROUP: "trial-local",
    SPONSOR_GROUP: "local + sponsor",
    "local_plus_sponsor_condition_logistic": "local + sponsor + condition",
    "local_plus_sponsor_facility_logistic": "local + sponsor + facility",
    "local_plus_sponsor_intervention_logistic": "local + sponsor + intervention",
    "local_plus_sponsor_collaborator_logistic": "local + sponsor + collaborator",
    ALL_CONTEXT_GROUP: "local + sponsor + condition + facility + intervention + collaborator",
}
RELATION_GROUPS: tuple[str, ...] = (
    "condition",
    "facility",
    "intervention",
    "collaborator",
)


class _UndefinedAveragePrecision(Exception):
    pass


def _percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("bootstrap requires at least one valid resample")
    position = (len(sorted_values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def _ap_difference(
    examples: list[_Example], scores_a: dict[str, float], scores_b: dict[str, float]
) -> float:
    ordered_examples = sorted(examples, key=lambda example: example.nct_id)
    labels = [int(example.label) for example in ordered_examples]
    ap_a = average_precision_numpy(
        labels, [scores_a[example.nct_id] for example in ordered_examples]
    )
    ap_b = average_precision_numpy(
        labels, [scores_b[example.nct_id] for example in ordered_examples]
    )
    if ap_a is None or ap_b is None:
        raise _UndefinedAveragePrecision
    return ap_b - ap_a


def _bootstrap_ap_difference(
    examples: list[_Example],
    scores_a: dict[str, float],
    scores_b: dict[str, float],
    *,
    seed: int,
    resamples: int,
) -> dict[str, Any]:
    if resamples <= 0:
        raise ValueError("bootstrap resamples must be positive")
    if not examples:
        raise ValueError("bootstrap examples must not be empty")
    if len({example.nct_id for example in examples}) != len(examples):
        raise ValueError("trial-cluster bootstrap requires one row per trial")
    try:
        estimate = _ap_difference(examples, scores_a, scores_b)
    except _UndefinedAveragePrecision:
        return {
            "estimate": None,
            "ci95": [None, None],
            "resamples": resamples,
            "valid_resamples": 0,
            "seed": seed,
            "cluster_unit": "trial",
            "clusters": len(examples),
        }

    index_by_trial = {example.nct_id: index for index, example in enumerate(examples)}
    cluster_ids = sorted(index_by_trial)
    cluster_indices = [[index_by_trial[nct_id]] for nct_id in cluster_ids]
    sampled_cluster_positions = cluster_bootstrap_indices(
        cluster_ids,
        resamples=resamples,
        seed=seed,
    )
    estimates: list[float] = []
    for sampled_clusters in sampled_cluster_positions:
        sampled = [
            examples[index]
            for cluster_position in sampled_clusters
            for index in cluster_indices[int(cluster_position)]
        ]
        try:
            estimates.append(_ap_difference(sampled, scores_a, scores_b))
        except _UndefinedAveragePrecision:
            continue
    estimates.sort()
    interval = [None, None] if not estimates else [_percentile(estimates, 0.025), _percentile(estimates, 0.975)]
    return {
        "estimate": estimate,
        "ci95": interval,
        "resamples": resamples,
        "valid_resamples": len(estimates),
        "seed": seed,
        "cluster_unit": "trial",
        "clusters": len(cluster_indices),
    }


def _seed(origin_date: str, comparison: str) -> int:
    token = f"{ANALYSIS_VERSION}|{origin_date}|{comparison}".encode("utf-8")
    return int(hashlib.sha256(token).hexdigest()[:16], 16) % (2**32)


def _load_origins(
    source_root: Path, manifest_path: Path, cohort_size: int
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[date, _OriginResult], dict[str, dict[str, Any]]]:
    manifest, entries = _validate_manifest(manifest_path, source_root)
    entry_by_date = {str(entry["snapshot_date"]): entry for entry in entries}
    origins: dict[date, _OriginResult] = {}
    future_audits: dict[str, dict[str, Any]] = {}
    for snapshot_date in TOP_LEVEL_ORIGIN_DATES:
        origin_entry = entry_by_date[snapshot_date]
        origin_result = _parse_origin_snapshot(
            _safe_source_path(source_root, origin_entry["path"]), origin_entry, cohort_size
        )
        future_date = SNAPSHOT_DATES[SNAPSHOT_DATES.index(snapshot_date) + 1]
        future_entry = entry_by_date[future_date]
        future_audit = _attach_future_labels(
            origin_result.examples,
            _safe_source_path(source_root, future_entry["path"]),
            future_entry,
        )
        origin_result.audit["future_observed_target_trials"] = future_audit["observed_trials"]
        origin_result.audit["future_missing_target_trials"] = future_audit["missing_trials"]
        origin_result.audit["future_origin_inconsistent_trials"] = future_audit["origin_inconsistent_trials"]
        origins[date.fromisoformat(snapshot_date)] = origin_result
        future_audits[snapshot_date] = future_audit
    return manifest, entries, origins, future_audits


def _deltas(
    metrics: dict[str, dict[str, Any]],
) -> dict[str, dict[str, float | None]]:
    local_ap = metrics[LOCAL_GROUP]["average_precision"]
    sponsor_ap = metrics[SPONSOR_GROUP]["average_precision"]
    result: dict[str, dict[str, float | None]] = {}
    for group in MODEL_GROUPS[1:]:
        ap = metrics[group]["average_precision"]
        result[group] = {
            "minus_trial_local_average_precision": None if ap is None or local_ap is None else ap - local_ap,
            "minus_local_plus_sponsor_average_precision": None
            if ap is None or sponsor_ap is None
            else ap - sponsor_ap,
        }
    return result


def _comparison_specs() -> tuple[tuple[str, str, str], ...]:
    return (
        (SPONSOR_GROUP, LOCAL_GROUP, "local_plus_sponsor_minus_trial_local_average_precision"),
        (
            "local_plus_sponsor_condition_logistic",
            LOCAL_GROUP,
            "condition_minus_trial_local_average_precision",
        ),
        (
            "local_plus_sponsor_condition_logistic",
            SPONSOR_GROUP,
            "condition_increment_over_sponsor_average_precision",
        ),
        (
            "local_plus_sponsor_facility_logistic",
            LOCAL_GROUP,
            "facility_minus_trial_local_average_precision",
        ),
        (
            "local_plus_sponsor_facility_logistic",
            SPONSOR_GROUP,
            "facility_increment_over_sponsor_average_precision",
        ),
        (
            "local_plus_sponsor_intervention_logistic",
            LOCAL_GROUP,
            "intervention_minus_trial_local_average_precision",
        ),
        (
            "local_plus_sponsor_intervention_logistic",
            SPONSOR_GROUP,
            "intervention_increment_over_sponsor_average_precision",
        ),
        (
            "local_plus_sponsor_collaborator_logistic",
            LOCAL_GROUP,
            "collaborator_minus_trial_local_average_precision",
        ),
        (
            "local_plus_sponsor_collaborator_logistic",
            SPONSOR_GROUP,
            "collaborator_increment_over_sponsor_average_precision",
        ),
        (ALL_CONTEXT_GROUP, LOCAL_GROUP, "all_context_minus_trial_local_average_precision"),
        (ALL_CONTEXT_GROUP, SPONSOR_GROUP, "all_context_minus_sponsor_average_precision"),
    )


def _summary(values: list[float | None], *, defined_origin_count: int) -> dict[str, Any]:
    defined = [value for value in values if value is not None]
    return {
        "origins_evaluated": defined_origin_count,
        "defined_origins": len(defined),
        "positive_delta_origins": sum(value > 0 for value in defined),
        "nonnegative_delta_origins": sum(value >= 0 for value in defined),
        "strictly_positive_all_origins": len(defined) == defined_origin_count and bool(defined) and all(value > 0 for value in defined),
        "mean_delta": mean(defined) if defined else None,
        "median_delta": median(defined) if defined else None,
        "minimum_delta": min(defined) if defined else None,
        "maximum_delta": max(defined) if defined else None,
        "values_by_origin": values,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(_canonical_json(row) + "\n")


def _configuration(cohort_size: int, bootstrap_resamples: int) -> dict[str, Any]:
    return {
        "analysis_version": ANALYSIS_VERSION,
        "base_analysis_version": BASE_ANALYSIS_VERSION,
        "snapshot_dates": list(SNAPSHOT_DATES),
        "snapshot_roles": dict(SNAPSHOT_ROLES),
        "origins_evaluated": list(EVALUATION_ORIGIN_DATES),
        "training_rule": "For each evaluated origin, fit only on labeled examples from strictly earlier origins.",
        "cohort_size_per_origin": cohort_size,
        "models": [{"name": group, "features": MODEL_LABELS[group]} for group in MODEL_GROUPS],
        "ablation": {
            "incremental_relation_types": list(RELATION_GROUPS),
            "all_context_model": "local plus sponsor, condition, facility, intervention, and collaborator features",
        },
        "uncertainty": {
            "metric": "average_precision_difference",
            "resamples": bootstrap_resamples,
            "cluster_unit": "trial",
            "interval": "paired percentile bootstrap, separately for each origin",
            "undefined_resamples": "omitted and counted rather than converted to zero",
        },
        "admission_rule": "Descriptive stability only; no automatic benchmark admission or graph-model escalation.",
    }


def run_stability_gate(
    source_root: Path,
    manifest_path: Path,
    output_dir: Path,
    *,
    cohort_size: int = COHORT_SIZE,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, Any]:
    """Run rolling-origin entity ablations and paired AP uncertainty intervals."""
    if cohort_size <= 0:
        raise ValueError("cohort_size must be positive")
    if bootstrap_resamples <= 0:
        raise ValueError("bootstrap_resamples must be positive")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output directory: {output_dir}")
    source_root = Path(source_root)
    manifest_path = Path(manifest_path)
    manifest, entries, origins, future_audits = _load_origins(source_root, manifest_path, cohort_size)
    origin_dates = [date.fromisoformat(snapshot_date) for snapshot_date in TOP_LEVEL_ORIGIN_DATES]
    per_origin: dict[str, dict[str, Any]] = {}
    prediction_rows: list[dict[str, Any]] = []

    for evaluation_date in origin_dates[1:]:
        evaluation_text = evaluation_date.isoformat()
        evaluation_examples = sorted(origins[evaluation_date].examples, key=lambda example: example.nct_id)
        training_dates = [origin_date for origin_date in origin_dates if origin_date < evaluation_date]
        training_examples = [
            example
            for origin_date in training_dates
            for example in sorted(origins[origin_date].examples, key=lambda item: item.nct_id)
        ]
        if not training_examples:
            raise ValueError(f"no strictly earlier training examples for stability origin {evaluation_text}")
        if not evaluation_examples:
            raise ValueError(f"no labeled evaluation examples for stability origin {evaluation_text}")

        predictions: dict[str, dict[str, float]] = {}
        metrics: dict[str, dict[str, Any]] = {}
        for group in MODEL_GROUPS:
            encoder, weights = _fit_logistic(group, training_examples)
            predictions[group] = _predict(encoder, weights, evaluation_examples)
            metrics[group] = _metrics(evaluation_examples, predictions[group])
        deltas = _deltas(metrics)
        uncertainty: dict[str, dict[str, Any]] = {}
        for group_b, group_a, comparison in _comparison_specs():
            uncertainty[comparison] = _bootstrap_ap_difference(
                evaluation_examples,
                predictions[group_a],
                predictions[group_b],
                seed=_seed(evaluation_text, comparison),
                resamples=bootstrap_resamples,
            )
        per_origin[evaluation_text] = {
            "origin_role": SNAPSHOT_ROLES[evaluation_text],
            "training_origins": [origin_date.isoformat() for origin_date in training_dates],
            "training_trial_count": len(training_examples),
            "evaluation_trial_count": len(evaluation_examples),
            "origin_audit": origins[evaluation_date].audit,
            "future_label_audit": future_audits[evaluation_text],
            "relation_coverage": origins[evaluation_date].coverage,
            "metrics": metrics,
            "average_precision_deltas": deltas,
            "uncertainty": uncertainty,
        }
        for example in evaluation_examples:
            prediction_rows.append(
                {
                    "origin_date": evaluation_text,
                    "origin_role": example.role,
                    "nct_id": example.nct_id,
                    "primary_completion_date": example.study.completion_date.isoformat(),
                    "completion_lag_days": example.study.completion_lag_days,
                    "label": example.label,
                    "results_first_posted_date": example.result_date.isoformat() if example.result_date else None,
                    "relation_counts": dict(example.relation_counts),
                    "history_relation_counts": dict(example.history_relation_counts),
                    "scores": {group: predictions[group][example.nct_id] for group in MODEL_GROUPS},
                }
            )

    stability_summary: dict[str, Any] = {}
    for group in MODEL_GROUPS[1:]:
        stability_summary[group] = {
            "model": MODEL_LABELS[group],
            "versus_trial_local": _summary(
                [per_origin[origin]["average_precision_deltas"].get(group, {}).get("minus_trial_local_average_precision") for origin in EVALUATION_ORIGIN_DATES],
                defined_origin_count=len(EVALUATION_ORIGIN_DATES),
            ),
            "versus_local_plus_sponsor": _summary(
                [per_origin[origin]["average_precision_deltas"].get(group, {}).get("minus_local_plus_sponsor_average_precision") for origin in EVALUATION_ORIGIN_DATES],
                defined_origin_count=len(EVALUATION_ORIGIN_DATES),
            ),
        }

    configuration = _configuration(cohort_size, bootstrap_resamples)
    output_dir.mkdir(parents=True)
    predictions_path = output_dir / "predictions.jsonl"
    _write_jsonl(predictions_path, prediction_rows)
    report = {
        "record_kind": "clinical_trials_stability",
        "analysis_version": ANALYSIS_VERSION,
        "status": "exploratory",
        "stability_gate_status": "complete",
        "decision": "REVIEW_REQUIRED",
        "admission_status": "deferred",
        "graph_model_status": "paused",
        "historical_availability_verified": True,
        "source_provenance": _source_provenance(Path(__file__).resolve().parents[2]),
        "input": {
            "manifest_path": str(manifest_path),
            "manifest_sha256": sha256_file(manifest_path),
            "format": manifest.get("format"),
            "verified_snapshots": [
                {
                    "snapshot_date": entry["snapshot_date"],
                    "role": SNAPSHOT_ROLES[str(entry["snapshot_date"])],
                    "path": entry["path"],
                    "sha256": entry["sha256"],
                    "bytes": entry["bytes"],
                }
                for entry in entries
            ],
        },
        "configuration": configuration,
        "configuration_sha256": hashlib.sha256(_canonical_json(configuration).encode("utf-8")).hexdigest(),
        "snapshot_audits": [origins[date.fromisoformat(snapshot_date)].audit for snapshot_date in TOP_LEVEL_ORIGIN_DATES],
        "future_label_audits": future_audits,
        "coverage": {
            snapshot_date: origins[date.fromisoformat(snapshot_date)].coverage for snapshot_date in TOP_LEVEL_ORIGIN_DATES
        },
        "rolling_origins": per_origin,
        "stability_summary": stability_summary,
        "recommendation": {
            "status": "stability_review_required",
            "reason": "Use per-origin ablations and uncertainty intervals to decide whether broader heterogeneous context adds stable value; do not pool origins into an admission claim.",
            "benchmark_admission": "deferred",
            "graph_model": "paused",
        },
        "interpretation_limits": [
            "Average-precision intervals are paired percentile bootstrap intervals clustered by trial, separately for each origin; they do not remove all sponsor or network dependence.",
            "The five evaluated origins reuse the bounded cohorts and exact historical-name identity rules of the base feasibility gate.",
            "Rows absent from a paired future snapshot or showing a result date at or before the blank origin are excluded rather than labeled untimely.",
            "This analysis does not establish legal compliance, national representativeness, deployment validity, or benchmark admission.",
        ],
        "artifact_hashes": {"predictions.jsonl": sha256_file(predictions_path)},
    }
    (output_dir / "report.json").write_text(_canonical_json(report) + "\n", encoding="utf-8")
    return report
