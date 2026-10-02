"""Run the fixed-duration MAUDE GraphSAGE aggregation ablation against retained C evidence."""

from __future__ import annotations

import argparse
import contextlib
import gzip
import io
import json
import math
import os
import platform
import re
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any

from . import diagnostic
from .models import (
    GRAPHSAGE_DIMENSION,
    GRAPHSAGE_LEARNING_RATE,
    GRAPHSAGE_NEIGHBOR_SAMPLE,
    GRAPHSAGE_REGULARIZATION,
)

PINNED_PROTOCOL_SHA256 = "78d1408a96da81fceb85b1f3f91034592b3b96dd95fbe4d508906e121c1efaca"
PINNED_INPUT_SHA256 = "1cba7f84ff24131715c68a985d9302c96c7bab4a4b2a27d906559a41104fbd36"
PINNED_BASELINE_SHA256 = "0c8a610991e313d49a9fba03736d225897620cec86779989c8b243665942dff2"
PINNED_BASELINE_MANIFEST = Path("results/maude_duration_diagnostic_20261002T172405Z.json")
PINNED_INPUT = Path(
    "results/generated/consolidation-post-RC1/core-verification-20261002/inputs/"
    "HealthGraphBench_RC1/data/real_R6/maude_B/prepared_snapshots.json.gz"
)
PROTOCOL_PATH = Path("docs/consolidation-post-RC1/aggregation_protocol.md")
BASELINE_RUN_DIRECTORY = Path(
    "results/generated/consolidation-post-RC1/maude-duration-20261002T172405Z"
)
COMMON_DURATION_EPOCHS = 30
TEST_YEAR_POPULATIONS: dict[int, dict[str, int]] = {
    2024: {
        "products_with_positives": 2950,
        "positive_edges": 6003,
        "candidate_pairs": 1_367_736,
    },
    2025: {
        "products_with_positives": 3420,
        "positive_edges": 7171,
        "candidate_pairs": 1_607_420,
    },
}
POOLED_TEST_POPULATION = {
    "products_with_positives": 6370,
    "positive_edges": 13174,
    "candidate_pairs": 2_975_156,
}
_COHORT_FIELDS = (
    "quarter",
    "product",
    "candidate_ids",
    "candidate_set_sha256",
    "positive_problem_ids",
    "history_product_reports",
)
_SENSITIVE_ENVIRONMENT_NAME = re.compile(
    r"(?:SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|PRIVATE|AUTH|API_KEY|ACCESS_KEY)",
    re.IGNORECASE,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha256_file(path: Path) -> str:
    return diagnostic._sha256_file(path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _assert_population_matches(
    actual: object, expected: Mapping[str, int], label: str
) -> dict[str, int]:
    if not isinstance(actual, Mapping):
        raise ValueError(f"{label} population is missing")
    normalized: dict[str, int] = {}
    for name, expected_value in expected.items():
        value = actual.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} population field {name} must be an integer")
        normalized[name] = value
        if value != expected_value:
            raise ValueError(
                f"{label} population differs from the fixed protocol: "
                f"{name}={value}, expected {expected_value}"
            )
    if set(actual) != set(expected):
        raise ValueError(f"{label} population has unexpected or missing fields")
    return normalized


def _expected_training_configuration(aggregation: str) -> dict[str, object]:
    return {
        "dimension": GRAPHSAGE_DIMENSION,
        "neighbor_sample": GRAPHSAGE_NEIGHBOR_SAMPLE if aggregation == "mean" else 0,
        "learning_rate": GRAPHSAGE_LEARNING_RATE,
        "regularization": GRAPHSAGE_REGULARIZATION,
        "objective": "bpr",
        "activation": "tanh",
        **({"aggregation": "none"} if aggregation == "none" else {}),
    }


def _required_baseline_paths() -> tuple[str, ...]:
    paths = {
        "run_manifest.json",
        "report.json",
        "selection.json",
        "validation_2023/validation_summary.json",
        "validation_2023/fit_epochs_30/fit_result.json",
        "validation_2023/fit_epochs_30/checkpoint.json.gz",
        "validation_2023/fit_epochs_30/epochs.jsonl.gz",
        "test_aggregate_2024_2025.json",
    }
    for quarter in ("2023Q1", "2023Q2", "2023Q3", "2023Q4"):
        prefix = f"validation_2023/fit_epochs_30/{quarter}"
        paths.update(
            {
                f"{prefix}/candidate_sets.jsonl.gz",
                f"{prefix}/candidate_predictions.jsonl.gz",
                f"{prefix}/quarter_result.json",
            }
        )
    for year in (2024, 2025):
        paths.update(
            {
                f"test_{year}/phase_summary.json",
                f"test_{year}/fit_epochs_30/checkpoint.json.gz",
                f"test_{year}/fit_epochs_30/epochs.jsonl.gz",
            }
        )
        for quarter in range(1, 5):
            prefix = f"test_{year}/{year}Q{quarter}"
            paths.update(
                {
                    f"{prefix}/candidate_sets.jsonl.gz",
                    f"{prefix}/candidate_predictions.jsonl.gz",
                    f"{prefix}/quarter_result.json",
                }
            )
    return tuple(sorted(paths))


def _verify_artifact(
    artifact_index: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
    relative_path: str,
) -> tuple[Path, dict[str, object]]:
    entry = artifact_index.get(relative_path)
    if not isinstance(entry, Mapping):
        raise ValueError(f"pinned C manifest does not inventory {relative_path}")
    expected_hash = entry.get("sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError(f"pinned C artifact has an invalid SHA-256: {relative_path}")
    path = (repo_root / relative_path).resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"pinned C artifact is not a file: {relative_path}")
    expected_size = entry.get("size_bytes")
    actual_size = path.stat().st_size
    if isinstance(expected_size, bool) or not isinstance(expected_size, int) or actual_size != expected_size:
        raise ValueError(f"pinned C artifact size mismatch: {relative_path}")
    actual_hash = _sha256_file(path)
    if actual_hash != expected_hash:
        raise ValueError(f"pinned C artifact SHA-256 mismatch: {relative_path}")
    return path, {"path": relative_path, "sha256": actual_hash, "size_bytes": actual_size}


def _load_checkpoint(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"checkpoint root must be a JSON object: {path}")
    return value


def _matrix_scalar_count(value: object, label: str) -> int:
    if not isinstance(value, list) or len(value) != GRAPHSAGE_DIMENSION:
        raise ValueError(f"checkpoint {label} must have {GRAPHSAGE_DIMENSION} rows")
    count = 0
    for row in value:
        if not isinstance(row, list) or len(row) != GRAPHSAGE_DIMENSION:
            raise ValueError(f"checkpoint {label} must be a square dimension-8 matrix")
        for scalar in row:
            if isinstance(scalar, bool) or not isinstance(scalar, (int, float)) or not math.isfinite(float(scalar)):
                raise ValueError(f"checkpoint {label} contains an invalid scalar")
            count += 1
    return count


def _validate_checkpoint(
    path: Path,
    *,
    aggregation: str,
    mean_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    state = _load_checkpoint(path)
    configuration = _require_mapping(state.get("configuration"), f"{aggregation} checkpoint configuration")
    recorded_aggregation = configuration.get("aggregation", "mean")
    if recorded_aggregation != aggregation:
        raise ValueError(f"checkpoint aggregation marker is not {aggregation!r}: {path}")
    if configuration.get("epochs") != COMMON_DURATION_EPOCHS:
        raise ValueError(f"checkpoint duration is inconsistent: {path}")
    expected_sample = GRAPHSAGE_NEIGHBOR_SAMPLE if aggregation == "mean" else 0
    if configuration.get("dimension") != GRAPHSAGE_DIMENSION:
        raise ValueError(f"checkpoint dimension is inconsistent: {path}")
    if configuration.get("neighbor_sample") != expected_sample:
        raise ValueError(f"checkpoint effective neighbor fanout is inconsistent: {path}")
    if configuration.get("learning_rate") != GRAPHSAGE_LEARNING_RATE:
        raise ValueError(f"checkpoint learning rate is inconsistent: {path}")
    if configuration.get("regularization") != GRAPHSAGE_REGULARIZATION:
        raise ValueError(f"checkpoint regularization is inconsistent: {path}")
    if configuration.get("objective") != "bpr" or configuration.get("activation") != "tanh":
        raise ValueError(f"checkpoint objective or activation is inconsistent: {path}")
    if state.get("resume_supported") is not False:
        raise ValueError(f"checkpoint must explicitly disable resume: {path}")
    products = state.get("products")
    problems = state.get("problems")
    if not isinstance(products, list) or not all(isinstance(value, str) for value in products):
        raise ValueError(f"checkpoint product ids are malformed: {path}")
    if not isinstance(problems, list) or not all(isinstance(value, str) for value in problems):
        raise ValueError(f"checkpoint problem ids are malformed: {path}")
    product_inputs = state.get("product_inputs")
    problem_inputs = state.get("problem_inputs")
    for ids, vectors, label in (
        (products, product_inputs, "product"),
        (problems, problem_inputs, "problem"),
    ):
        if not isinstance(vectors, Mapping) or set(vectors) != set(ids):
            raise ValueError(f"checkpoint {label} vectors do not cover the {label} ids: {path}")
        for vector in vectors.values():
            if not isinstance(vector, list) or len(vector) != GRAPHSAGE_DIMENSION:
                raise ValueError(f"checkpoint node vector dimension is inconsistent: {path}")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in vector
            ):
                raise ValueError(f"checkpoint node vector contains an invalid scalar: {path}")
    self_scalars = _matrix_scalar_count(state.get("self_weights"), "self_weights")
    neighbor_scalars = _matrix_scalar_count(state.get("neighbor_weights"), "neighbor_weights")
    if self_scalars != 64 or neighbor_scalars != 64:
        raise ValueError(f"checkpoint shared transformation dimensions are inconsistent: {path}")
    if aggregation == "none":
        for key in ("product_neighbors", "problem_neighbors"):
            if state.get(key) != {}:
                raise ValueError(f"none checkpoint contains active neighbor lists: {path}")
        neighbor_weights = state["neighbor_weights"]
        if any(float(value) != 0.0 for row in neighbor_weights for value in row):
            raise ValueError(f"none checkpoint has nonzero neighbor weights: {path}")
    if mean_checkpoint is not None:
        if products != mean_checkpoint.get("products") or problems != mean_checkpoint.get("problems"):
            raise ValueError(f"mean and none checkpoint node ids differ: {path}")
    return {
        "products": len(products),
        "problems": len(problems),
        "active_node_vector_scalars": GRAPHSAGE_DIMENSION * (len(products) + len(problems)),
        "active_shared_transform_scalars": 128 if aggregation == "mean" else 64,
        "active_parameter_scalars": GRAPHSAGE_DIMENSION * (len(products) + len(problems)) + (128 if aggregation == "mean" else 64),
    }


def _assert_fit_record(fit_result: object, aggregation: str, label: str) -> Mapping[str, Any]:
    fit = _require_mapping(fit_result, label)
    requested = fit.get("epochs_requested")
    completed = fit.get("epochs_completed")
    if requested != COMMON_DURATION_EPOCHS or completed != COMMON_DURATION_EPOCHS:
        raise ValueError(f"{label} did not complete the fixed 30 epochs")
    expected = _expected_training_configuration(aggregation)
    training_configuration = fit.get("training_configuration")
    if not isinstance(training_configuration, Mapping) or dict(training_configuration) != expected:
        raise ValueError(f"{label} training configuration is inconsistent with {aggregation}")
    return fit


def _assert_candidate_sets_match(baseline_path: Path, new_path: Path, label: str) -> dict[str, int]:
    population = {"products_with_positives": 0, "positive_edges": 0, "candidate_pairs": 0}
    products_seen: set[tuple[str, str]] = set()
    with gzip.open(baseline_path, "rt", encoding="utf-8") as baseline_source, gzip.open(
        new_path, "rt", encoding="utf-8"
    ) as new_source:
        for index, pair in enumerate(zip_longest(baseline_source, new_source), start=1):
            baseline_line, new_line = pair
            if baseline_line is None or new_line is None:
                raise ValueError(f"{label} candidate-set row count differs at row {index}")
            baseline_record = json.loads(baseline_line)
            new_record = json.loads(new_line)
            if not isinstance(baseline_record, dict) or not isinstance(new_record, dict):
                raise ValueError(f"{label} candidate-set row {index} is malformed")
            if any(baseline_record.get(key) != new_record.get(key) for key in _COHORT_FIELDS):
                raise ValueError(f"{label} candidate ids, positives, or support differ at row {index}")
            quarter = baseline_record.get("quarter")
            product = baseline_record.get("product")
            candidates = baseline_record.get("candidate_ids")
            positives = baseline_record.get("positive_problem_ids")
            if not isinstance(quarter, str) or not isinstance(product, str):
                raise ValueError(f"{label} candidate-set key is malformed at row {index}")
            if (quarter, product) in products_seen:
                raise ValueError(f"{label} candidate sets contain a duplicate product")
            products_seen.add((quarter, product))
            if not isinstance(candidates, list) or not isinstance(positives, list):
                raise ValueError(f"{label} candidate or positive ids are malformed at row {index}")
            population["products_with_positives"] += 1
            population["positive_edges"] += len(positives)
            population["candidate_pairs"] += len(candidates)
    return population


def _metric_at_10(value: object, label: str) -> float:
    metrics = _require_mapping(value, label)
    thresholds = _require_mapping(metrics.get("thresholds"), f"{label} thresholds")
    support_one = _require_mapping(thresholds.get("1"), f"{label} support-1 metrics")
    score = support_one.get("recall_at_10")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
        raise ValueError(f"{label} micro recall@10 is invalid")
    return float(score)


def _common_duration_lock(
    *,
    mean_validation: Mapping[str, Any],
    none_validation: Mapping[str, Any],
    none_population: object,
    cohorts_match: bool,
) -> dict[str, object]:
    if mean_validation.get("status") != "complete" or none_validation.get("status") != "complete":
        raise ValueError("common 30-epoch lock requires complete mean and none validation")
    if mean_validation.get("duration_epochs") != COMMON_DURATION_EPOCHS or none_validation.get("duration_epochs") != COMMON_DURATION_EPOCHS:
        raise ValueError("common 30-epoch lock requires both validation fits at 30 epochs")
    _assert_population_matches(mean_validation.get("population"), diagnostic.VALIDATION_POPULATION, "C mean30 validation")
    _assert_population_matches(none_population, diagnostic.VALIDATION_POPULATION, "none validation")
    if not cohorts_match:
        raise ValueError("common 30-epoch lock requires matching validation candidate cohorts")
    mean_score = _metric_at_10(mean_validation.get("validation"), "mean validation")
    none_score = _metric_at_10(none_validation.get("validation"), "none validation")
    return {
        "status": "locked",
        "common_duration_epochs": COMMON_DURATION_EPOCHS,
        "variants": ["mean", "none"],
        "duration_source": "fixed by C selection and the pinned D1 protocol; no D1 tuning grid",
        "validation_micro_recall_at_10": {"mean30_reused": mean_score, "none30_new": none_score},
        "validation_population": dict(diagnostic.VALIDATION_POPULATION),
        "validation_candidate_cohorts_match": True,
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_scores_consulted": False,
        "tests_may_start_after_this_lock": True,
    }


def _capture_environment() -> dict[str, object]:
    variables: dict[str, str] = {}
    redacted: list[str] = []
    for name, value in sorted(os.environ.items()):
        if _SENSITIVE_ENVIRONMENT_NAME.search(name):
            variables[name] = "<redacted>"
            redacted.append(name)
        else:
            variables[name] = value
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "environment_variables": variables,
        "redacted_environment_names": redacted,
        "effective_thread_environment": {
            name: os.environ.get(name) for name in diagnostic._THREAD_ENV_VARIABLES
        },
        "supervisor": "one controller process plus one serial worker per phase",
    }


def _current_code_hashes(repo_root: Path) -> dict[str, dict[str, str]]:
    paths = {
        "ablation_runner": Path(__file__).resolve(),
        "diagnostic_runner": repo_root / "healthgraphbench" / "tasks" / "maude" / "diagnostic.py",
        "cli": repo_root / "scripts" / "run_maude_aggregation_ablation.py",
        "evaluation": repo_root / "healthgraphbench" / "tasks" / "maude" / "evaluate.py",
        "models": repo_root / "healthgraphbench" / "tasks" / "maude" / "models.py",
        "data": repo_root / "healthgraphbench" / "tasks" / "maude" / "data.py",
    }
    return {
        name: {"path": str(path.resolve()), "sha256": _sha256_file(path)}
        for name, path in paths.items()
    }


def _load_pinned_baseline(
    *, repo_root: Path, manifest_path: Path, expected_sha256: str
) -> dict[str, Any]:
    pinned_path = (repo_root / PINNED_BASELINE_MANIFEST).resolve(strict=True)
    manifest_path = manifest_path.resolve(strict=True)
    if manifest_path != pinned_path:
        raise ValueError(f"baseline-manifest must be the pinned C manifest at {pinned_path}")
    if expected_sha256.lower() != PINNED_BASELINE_SHA256:
        raise ValueError("baseline-sha256 does not match the pinned C mean30 manifest")
    actual_manifest_hash = _sha256_file(manifest_path)
    if actual_manifest_hash != PINNED_BASELINE_SHA256:
        raise ValueError("pinned C mean30 manifest SHA-256 mismatch")
    baseline = _read_json(manifest_path)
    if baseline.get("schema") != "healthgraphbench.maude-duration-evidence.v1":
        raise ValueError("pinned baseline is not the C duration evidence manifest")
    if baseline.get("status") != "complete" or baseline.get("run_id") != "maude-duration-20261002T172405Z":
        raise ValueError("pinned C mean30 run is not complete")
    if baseline.get("code_commit") != "4a22c2addc8203efd2b38a60c416270855c3bf3b":
        raise ValueError("pinned C code commit is inconsistent")
    input_record = _require_mapping(baseline.get("prepared_input"), "C prepared input")
    if input_record.get("sha256") != PINNED_INPUT_SHA256:
        raise ValueError("C baseline used a different prepared input")
    configuration = _require_mapping(baseline.get("configuration"), "C configuration")
    expected_mean = _expected_training_configuration("mean")
    if dict(configuration) != expected_mean:
        raise ValueError("C baseline configuration differs from the fixed mean30 protocol")
    interpretation = _require_mapping(baseline.get("interpretation"), "C interpretation")
    if interpretation.get("independent_confirmation") is not False:
        raise ValueError("C baseline does not record the required exploratory status")
    selection = _require_mapping(_require_mapping(baseline.get("validation"), "C validation").get("selection"), "C selection")
    if selection.get("selected_epochs") != COMMON_DURATION_EPOCHS or selection.get("test_scores_consulted") is not False:
        raise ValueError("pinned C selection did not lock 30 before tests")
    artifact_rows = baseline.get("artifacts")
    if not isinstance(artifact_rows, list):
        raise ValueError("pinned C manifest has no artifact inventory")
    artifact_index: dict[str, Mapping[str, Any]] = {}
    for row in artifact_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("path"), str):
            raise ValueError("pinned C artifact inventory is malformed")
        path = row["path"]
        if path in artifact_index:
            raise ValueError(f"pinned C artifact inventory repeats {path}")
        artifact_index[path] = row
    verified_artifacts: dict[str, dict[str, object]] = {}
    artifact_paths: dict[str, Path] = {}
    for relative in _required_baseline_paths():
        manifest_relative = (BASELINE_RUN_DIRECTORY / relative).as_posix()
        artifact_path, artifact_record = _verify_artifact(artifact_index, repo_root, manifest_relative)
        artifact_paths[relative] = artifact_path
        verified_artifacts[manifest_relative] = artifact_record
    run_manifest = _read_json(artifact_paths["run_manifest.json"])
    report = _read_json(artifact_paths["report.json"])
    selection_file = _read_json(artifact_paths["selection.json"])
    validation_summary = _read_json(artifact_paths["validation_2023/validation_summary.json"])
    if run_manifest.get("status") != "complete" or report.get("status") != "complete":
        raise ValueError("verified C output files are not complete")
    run_input = _require_mapping(run_manifest.get("prepared_input"), "C output prepared input")
    if run_input.get("sha256") != PINNED_INPUT_SHA256:
        raise ValueError("verified C run manifest input hash is inconsistent")
    baseline_code = _require_mapping(baseline.get("code_sha256"), "C source code hashes")
    run_code = _require_mapping(run_manifest.get("code_sha256"), "C run source code hashes")
    for name in ("runner", "cli", "evaluation", "models", "data"):
        code_record = _require_mapping(baseline_code.get(name), f"C {name} source hash")
        if code_record.get("sha256") != run_code.get(name):
            raise ValueError(f"C baseline and retained run manifest disagree on {name} code hash")
    if selection_file.get("selected_epochs") != COMMON_DURATION_EPOCHS or selection_file.get("test_scores_consulted") is not False:
        raise ValueError("verified C selection artifact is inconsistent")
    if validation_summary.get("status") != "complete":
        raise ValueError("verified C validation phase is incomplete")
    baseline_fit = _require_mapping(
        _require_mapping(validation_summary.get("fits"), "C validation fits").get("30"),
        "C mean30 validation fit",
    )
    if baseline_fit.get("status") != "complete":
        raise ValueError("C mean30 validation fit is incomplete")
    _assert_population_matches(baseline_fit.get("population"), diagnostic.VALIDATION_POPULATION, "C mean30 validation")
    _assert_fit_record(baseline_fit.get("fit"), "mean", "C mean30 validation fit")
    validation_fit_file = _read_json(artifact_paths["validation_2023/fit_epochs_30/fit_result.json"])
    if validation_fit_file != baseline_fit:
        raise ValueError("C mean30 validation summary and fit_result artifact disagree")
    c_report_validation = _require_mapping(report.get("validation"), "C report validation")
    c_report_scores = _require_mapping(c_report_validation.get("micro_recall_at_10_by_epochs"), "C report validation scores")
    if c_report_scores.get("30") != _metric_at_10(baseline_fit.get("validation"), "C mean30 validation"):
        raise ValueError("C manifest score and retained validation output disagree")
    validation_population = baseline_fit.get("population")
    _assert_population_matches(validation_summary.get("population"), diagnostic.VALIDATION_POPULATION, "C validation summary")
    test_summaries: dict[str, dict[str, Any]] = {}
    for year in (2024, 2025):
        summary_path = artifact_paths[f"test_{year}/phase_summary.json"]
        summary = _read_json(summary_path)
        if summary.get("status") != "complete" or summary.get("year") != year:
            raise ValueError(f"C {year} test phase is incomplete")
        _assert_population_matches(summary.get("population"), TEST_YEAR_POPULATIONS[year], f"C {year} test")
        _assert_fit_record(summary.get("fit"), "mean", f"C {year} mean30 test fit")
        test_summaries[str(year)] = summary
    pooled_path = artifact_paths["test_aggregate_2024_2025.json"]
    pooled = _read_json(pooled_path)
    _assert_population_matches(pooled.get("population"), POOLED_TEST_POPULATION, "C pooled test")
    c_report_score = _metric_at_10(pooled, "C pooled test output")
    root_c_test = _require_mapping(baseline.get("test"), "C manifest tests")
    root_c_pooled = _require_mapping(root_c_test.get("pooled_2024_2025"), "C pooled test manifest")
    if _metric_at_10(root_c_pooled, "C pooled test manifest") != c_report_score:
        raise ValueError("C pinned manifest and retained pooled test output disagree")
    c_checkpoint_metadata: dict[str, dict[str, int]] = {}
    c_checkpoint_states: dict[str, dict[str, Any]] = {}
    for name, relative in (
        ("validation_2023", "validation_2023/fit_epochs_30/checkpoint.json.gz"),
        ("test_2024", "test_2024/fit_epochs_30/checkpoint.json.gz"),
        ("test_2025", "test_2025/fit_epochs_30/checkpoint.json.gz"),
    ):
        state = _load_checkpoint(artifact_paths[relative])
        c_checkpoint_metadata[name] = _validate_checkpoint(
            artifact_paths[relative], aggregation="mean"
        )
        c_checkpoint_states[name] = state
    return {
        "manifest": baseline,
        "manifest_sha256": actual_manifest_hash,
        "manifest_path": manifest_path,
        "run_directory": (repo_root / BASELINE_RUN_DIRECTORY).resolve(),
        "run_manifest": run_manifest,
        "report": report,
        "selection": selection_file,
        "validation_summary": validation_summary,
        "validation_fit": baseline_fit,
        "validation_population": validation_population,
        "test_summaries": test_summaries,
        "pooled_test": pooled,
        "artifact_paths": artifact_paths,
        "verified_artifacts": verified_artifacts,
        "checkpoint_metadata": c_checkpoint_metadata,
        "checkpoint_states": c_checkpoint_states,
    }


def _compare_phase_cohorts(
    *,
    baseline: Mapping[str, Any],
    phase_summary: Mapping[str, Any],
    output_dir: Path,
    phase: str,
    quarters: Sequence[str],
    expected_population: Mapping[str, int],
) -> dict[str, int]:
    baseline_quarters: Mapping[str, Any]
    if phase == "validation_2023":
        base_fit = baseline["validation_fit"]
        baseline_quarters = _require_mapping(base_fit.get("quarters"), "C validation quarter results")
        none_fits = _require_mapping(phase_summary.get("fits"), "none validation fits")
        none_fit = _require_mapping(none_fits.get("30"), "none30 validation fit")
        none_quarters = _require_mapping(none_fit.get("quarters"), "none validation quarter results")
        relative_base = Path("validation_2023/fit_epochs_30")
        relative_new = Path("validation_2023/fit_epochs_30")
    else:
        year = int(phase[-4:])
        baseline_summary = baseline["test_summaries"][str(year)]
        baseline_quarters = _require_mapping(baseline_summary.get("quarters"), f"C {year} quarter results")
        none_quarters = _require_mapping(phase_summary.get("quarters"), f"none {year} quarter results")
        relative_base = Path(f"test_{year}")
        relative_new = Path(f"test_{year}")
    total = {"products_with_positives": 0, "positive_edges": 0, "candidate_pairs": 0}
    for quarter in quarters:
        base_quarter = _require_mapping(baseline_quarters.get(quarter), f"C {quarter} quarter")
        new_quarter = _require_mapping(none_quarters.get(quarter), f"none {quarter} quarter")
        base_population = {
            "products_with_positives": base_quarter.get("products_with_positives"),
            "positive_edges": base_quarter.get("positive_edges"),
            "candidate_pairs": base_quarter.get("candidate_pairs"),
        }
        new_population = {
            "products_with_positives": new_quarter.get("products_with_positives"),
            "positive_edges": new_quarter.get("positive_edges"),
            "candidate_pairs": new_quarter.get("candidate_pairs"),
        }
        if base_population != new_population:
            raise ValueError(f"{phase}/{quarter} cohort population differs from C")
        sets_population = _assert_candidate_sets_match(
            baseline["run_directory"] / relative_base / quarter / "candidate_sets.jsonl.gz",
            output_dir / relative_new / quarter / "candidate_sets.jsonl.gz",
            f"{phase}/{quarter}",
        )
        if sets_population != base_population:
            raise ValueError(f"{phase}/{quarter} exported candidate sets disagree with quarter metrics")
        for name in total:
            total[name] += int(sets_population[name])
    summary_population = _assert_population_matches(
        phase_summary.get("population"), expected_population, phase
    )
    _assert_population_matches(total, expected_population, f"{phase} exported cohorts")
    if total != summary_population:
        raise ValueError(f"{phase} exported cohorts disagree with its phase summary")
    return total


def _output_artifact_hashes(output_dir: Path) -> dict[str, dict[str, object]]:
    hashes: dict[str, dict[str, object]] = {}
    for root, _directories, filenames in os.walk(output_dir):
        for filename in sorted(filenames):
            path = Path(root) / filename
            relative = path.relative_to(output_dir).as_posix()
            if relative in {"run_manifest.json", "report.json", "stdout.txt"}:
                continue
            hashes[relative] = {"sha256": _sha256_file(path), "size_bytes": path.stat().st_size}
    return hashes


def _phase_costs(phases: Mapping[str, Mapping[str, Any]]) -> dict[str, object]:
    return {
        "phase_wall_seconds": sum(float(value.get("wall_seconds", 0.0)) for value in phases.values()),
        "worker_cpu_seconds": sum(float(value.get("worker_cpu_seconds", 0.0)) for value in phases.values()),
        "peak_aggregate_rss_bytes": max(
            (int(value.get("peak_aggregate_rss_bytes", 0)) for value in phases.values()), default=0
        ),
        "phases": dict(phases),
    }
def _reused_c_costs(baseline: Mapping[str, Any]) -> dict[str, object]:
    c_manifest = baseline["manifest"]
    c_run_manifest = baseline["run_manifest"]
    phase_records = _require_mapping(c_run_manifest.get("phases"), "C phase costs")
    fit_records = {
        "validation_2023_mean30": baseline["validation_fit"]["fit"],
        "test_2024_mean30": baseline["test_summaries"]["2024"]["fit"],
        "test_2025_mean30": baseline["test_summaries"]["2025"]["fit"],
    }
    return {
        "origin": "measured in C and reused; no mean30 D1 refit",
        "mean30_fit_wall_and_cpu_seconds": {
            name: {
                "wall_seconds": record["wall_seconds"],
                "cpu_seconds": record["cpu_seconds"],
            }
            for name, record in fit_records.items()
        },
        "C_validation_phase_supervisor_includes_duration_grid": phase_records["validation_2023"],
        "C_test_phase_supervisors": {
            year: phase_records[f"test_{year}"] for year in ("2024", "2025")
        },
        "full_C_diagnostic_costs_including_validation_grid": c_manifest.get("costs"),
    }


def run_ablation(
    *,
    prepared_input: Path,
    output_dir: Path,
    protocol: Path,
    protocol_sha256: str,
    baseline_manifest: Path,
    baseline_sha256: str,
    phase_timeout_seconds: float = diagnostic.MAX_TIMEOUT_SECONDS,
    max_rss_mib: int = 512,
    max_output_mib: int = 512,
) -> dict[str, Any]:
    repo_root = _repo_root()
    prepared_input = prepared_input.resolve(strict=True)
    protocol = protocol.resolve(strict=True)
    output_dir = output_dir.resolve()
    baseline_manifest = baseline_manifest.resolve(strict=True)
    if not prepared_input.is_file() or not protocol.is_file():
        raise ValueError("prepared input and protocol must be files")
    if protocol_sha256.lower() != PINNED_PROTOCOL_SHA256:
        raise ValueError("protocol SHA-256 is not the pinned D1 protocol hash")
    actual_protocol_sha256 = _sha256_file(protocol)
    if actual_protocol_sha256 != PINNED_PROTOCOL_SHA256:
        raise ValueError("aggregation protocol SHA-256 mismatch")
    if prepared_input != (repo_root / PINNED_INPUT).resolve(strict=True):
        raise ValueError("prepared-input must be the pinned C/D1 input path")
    actual_input_sha256 = _sha256_file(prepared_input)
    if actual_input_sha256 != PINNED_INPUT_SHA256:
        raise ValueError("prepared input SHA-256 differs from the pinned C input")
    if not 0 < phase_timeout_seconds <= diagnostic.MAX_TIMEOUT_SECONDS:
        raise ValueError(f"phase timeout must be in (0, {diagnostic.MAX_TIMEOUT_SECONDS}] seconds")
    if not 0 < max_rss_mib <= diagnostic.MAX_RSS_BYTES // (1024 * 1024):
        raise ValueError("max RSS must be in (0, 512] MiB")
    if not 0 < max_output_mib <= diagnostic.MAX_OUTPUT_BYTES // (1024 * 1024):
        raise ValueError("max output must be in (0, 512] MiB")
    baseline = _load_pinned_baseline(
        repo_root=repo_root, manifest_path=baseline_manifest, expected_sha256=baseline_sha256
    )
    diagnostic._assert_new_output(output_dir, repo_root)
    output_dir.mkdir(parents=True, exist_ok=False)
    launch_environment = _capture_environment()
    diagnostic._limit_library_threads()
    started_at = datetime.now(timezone.utc).isoformat()
    started_monotonic = time.monotonic()
    max_rss_bytes = max_rss_mib * 1024 * 1024
    max_output_bytes = max_output_mib * 1024 * 1024
    phases: dict[str, dict[str, Any]] = {
        "validation_2023": {"status": "pending"},
        "test_2024": {"status": "pending"},
        "test_2025": {"status": "pending"},
    }
    costs_by_phase: dict[str, Mapping[str, Any]] = {}
    command_argv = list(getattr(sys, "orig_argv", sys.argv))
    run_manifest: dict[str, Any] = {
        "schema": "healthgraphbench.maude-aggregation-ablation-run.v1",
        "run_id": output_dir.name,
        "status": "running",
        "started_at_utc": started_at,
        "command": {
            "argv": command_argv,
            "api_arguments": {
                "prepared_input": str(prepared_input),
                "output_dir": str(output_dir),
                "protocol": str(protocol),
                "protocol_sha256": actual_protocol_sha256,
                "baseline_manifest": str(baseline_manifest),
                "baseline_sha256": baseline["manifest_sha256"],
                "phase_timeout_seconds": phase_timeout_seconds,
                "max_rss_mib": max_rss_mib,
                "max_output_mib": max_output_mib,
            },
            "stdout_capture": {
                "status": "not_captured_in_library_api",
                "path": None,
            },
        },
        "prepared_input": {"path": str(prepared_input), "sha256": actual_input_sha256},
        "protocol": {"path": str(protocol), "expected_sha256": protocol_sha256.lower(), "sha256": actual_protocol_sha256},
        "baseline": {
            "path": str(baseline_manifest),
            "sha256": baseline["manifest_sha256"],
            "run_id": baseline["manifest"].get("run_id"),
            "code_commit": baseline["manifest"].get("code_commit"),
            "source_code_sha256": baseline["manifest"].get("code_sha256"),
            "reused_artifacts": baseline["verified_artifacts"],
            "training_origin": "mean30 reused from C; not retrained in D1",
        },
        "code_sha256": _current_code_hashes(repo_root),
        "limits": {
            "phase_timeout_seconds": phase_timeout_seconds,
            "aggregate_rss_bytes_per_phase": max_rss_bytes,
            "new_output_bytes_per_phase": max_output_bytes,
            "automatic_retries": 0,
            "worker_count": 1,
            "thread_count_per_library": 1,
        },
        "enforcement": {
            "platform": "Linux /proc",
            "poll_interval_seconds": diagnostic._POLL_SECONDS,
            "aggregate_rss": "controller current RSS plus worker VmHWM/current RSS; inherited diagnostic supervisor terminates worker on limit",
            "worker_termination": "SIGTERM, then SIGKILL after 2 seconds if still alive",
            "phase_output": "inherited diagnostic worker byte budget plus controller directory polling",
        },
        "environment": {
            **launch_environment,
            "effective_thread_environment": {
                name: os.environ.get(name) for name in diagnostic._THREAD_ENV_VARIABLES
            },
        },
        "configuration": {
            "aggregation_variants": {"reused_baseline": "mean", "new_fit": "none"},
            "duration_epochs": COMMON_DURATION_EPOCHS,
            "dimension": GRAPHSAGE_DIMENSION,
            "learning_rate": GRAPHSAGE_LEARNING_RATE,
            "regularization": GRAPHSAGE_REGULARIZATION,
            "objective": "bpr",
            "activation": "tanh",
            "mean_neighbor_sample": GRAPHSAGE_NEIGHBOR_SAMPLE,
            "none_effective_neighbor_sample": 0,
            "none_validation_epochs": [COMMON_DURATION_EPOCHS],
            "resume_supported": False,
        },
        "phases": phases,
        "cohort_checks": {},
        "interpretation": {
            "independent_confirmation": False,
            "no_new_confidence_interval": True,
            "mean30_origin": "reused C evidence",
            "none30_origin": "new D1 fit",
        },
    }
    costs: dict[str, Any] = {
        "wall_seconds": 0.0,
        "phase_wall_seconds": 0.0,
        "worker_cpu_seconds": 0.0,
        "peak_aggregate_rss_bytes": 0,
    }
    diagnostic._write_json(output_dir / "run_manifest.json", run_manifest)

    def execute_phase(name: str, worker_args: tuple[object, ...]) -> dict[str, Any]:
        phase_dir = output_dir / name
        phase_dir.mkdir()
        phases[name] = {"status": "running"}
        diagnostic._write_json(output_dir / "run_manifest.json", run_manifest)
        try:
            supervisor = diagnostic._supervise_worker(
                diagnostic._worker_entry,
                worker_args,
                phase_dir,
                timeout_seconds=phase_timeout_seconds,
                max_rss_bytes=max_rss_bytes,
                max_output_bytes=max_output_bytes,
            )
        except diagnostic.PhaseExecutionError as exc:
            diagnostic._add_phase_costs(costs, exc.supervisor)
            costs_by_phase[name] = exc.supervisor
            phases[name] = dict(exc.supervisor)
            diagnostic._write_json(output_dir / "run_manifest.json", run_manifest)
            raise
        diagnostic._add_phase_costs(costs, supervisor)
        costs_by_phase[name] = supervisor
        phases[name] = dict(supervisor)
        diagnostic._write_json(output_dir / "run_manifest.json", run_manifest)
        return _read_json(phase_dir / ("validation_summary.json" if name == "validation_2023" else "phase_summary.json"))

    try:
        validation_dir = output_dir / "validation_2023"
        validation_summary = execute_phase(
            "validation_2023",
            (
                "validation",
                str(prepared_input),
                str(validation_dir),
                max_output_bytes,
                None,
                None,
                "none",
                (COMMON_DURATION_EPOCHS,),
            ),
        )
        if validation_summary.get("status") != "complete":
            raise ValueError("none validation phase did not complete")
        fits = _require_mapping(validation_summary.get("fits"), "none validation fits")
        if set(fits) != {str(COMMON_DURATION_EPOCHS)}:
            raise ValueError("D1 validation must contain only the fixed 30-epoch fit, not a grid")
        if validation_summary.get("validation_epochs") != [COMMON_DURATION_EPOCHS]:
            raise ValueError("D1 validation summary does not record the fixed single 30-epoch fit")
        none_validation = _require_mapping(fits.get("30"), "none30 validation fit")
        if none_validation.get("status") != "complete":
            raise ValueError("none30 validation fit did not complete")
        _assert_population_matches(none_validation.get("population"), diagnostic.VALIDATION_POPULATION, "none30 validation fit")
        _assert_population_matches(validation_summary.get("population"), diagnostic.VALIDATION_POPULATION, "none validation summary")
        _assert_fit_record(none_validation.get("fit"), "none", "none30 validation fit")
        none_validation_checkpoint = output_dir / "validation_2023/fit_epochs_30/checkpoint.json.gz"
        none_validation_capacity = _validate_checkpoint(
            none_validation_checkpoint,
            aggregation="none",
            mean_checkpoint=baseline["checkpoint_states"]["validation_2023"],
        )
        _assert_population_matches(
            _compare_phase_cohorts(
                baseline=baseline,
                phase_summary=validation_summary,
                output_dir=output_dir,
                phase="validation_2023",
                quarters=("2023Q1", "2023Q2", "2023Q3", "2023Q4"),
                expected_population=diagnostic.VALIDATION_POPULATION,
            ),
            diagnostic.VALIDATION_POPULATION,
            "none validation exported cohorts",
        )
        run_manifest["cohort_checks"]["validation_2023"] = {
            "status": "complete",
            "baseline_population": dict(diagnostic.VALIDATION_POPULATION),
            "none_population": dict(diagnostic.VALIDATION_POPULATION),
            "candidate_ids_labels_support_and_candidate_hashes_match": True,
        }
        mean_validation_score = _metric_at_10(baseline["validation_fit"].get("validation"), "C mean30 validation")
        none_validation_score = _metric_at_10(none_validation.get("validation"), "none30 validation")
        selection_lock = _common_duration_lock(
            mean_validation=baseline["validation_fit"],
            none_validation=none_validation,
            none_population=none_validation.get("population"),
            cohorts_match=True,
        )
        diagnostic._write_json(output_dir / "selection_locked_before_test.json", selection_lock)
        run_manifest["selection"] = {
            "artifact": "selection_locked_before_test.json",
            "locked_at_utc": selection_lock["locked_at_utc"],
            "common_duration_epochs": COMMON_DURATION_EPOCHS,
            "test_scores_consulted": False,
        }
        diagnostic._write_json(output_dir / "run_manifest.json", run_manifest)

        none_test_summaries: dict[str, Mapping[str, Any]] = {}
        none_checkpoint_capacities: dict[str, dict[str, int]] = {
            "validation_2023": none_validation_capacity
        }
        for year in (2024, 2025):
            name = f"test_{year}"
            phase_dir = output_dir / name
            summary = execute_phase(
                name,
                (
                    "test",
                    str(prepared_input),
                    str(phase_dir),
                    max_output_bytes,
                    year,
                    COMMON_DURATION_EPOCHS,
                    "none",
                ),
            )
            if summary.get("status") != "complete" or summary.get("year") != year:
                raise ValueError(f"none {year} test phase is incomplete")
            _assert_population_matches(summary.get("population"), TEST_YEAR_POPULATIONS[year], f"none {year} test")
            _assert_fit_record(summary.get("fit"), "none", f"none {year} test fit")
            none_checkpoint_capacities[name] = _validate_checkpoint(
                phase_dir / "fit_epochs_30/checkpoint.json.gz",
                aggregation="none",
                mean_checkpoint=baseline["checkpoint_states"][name],
            )
            _compare_phase_cohorts(
                baseline=baseline,
                phase_summary=summary,
                output_dir=output_dir,
                phase=name,
                quarters=tuple(f"{year}Q{quarter}" for quarter in range(1, 5)),
                expected_population=TEST_YEAR_POPULATIONS[year],
            )
            run_manifest["cohort_checks"][name] = {
                "status": "complete",
                "baseline_population": TEST_YEAR_POPULATIONS[year],
                "none_population": TEST_YEAR_POPULATIONS[year],
                "candidate_ids_labels_support_and_candidate_hashes_match": True,
            }
            diagnostic._write_json(output_dir / "run_manifest.json", run_manifest)
            none_test_summaries[str(year)] = summary

        pooled_none = diagnostic._combined_test_metrics(none_test_summaries)
        _assert_population_matches(pooled_none.get("population"), POOLED_TEST_POPULATION, "none pooled test")
        pooled_mean = baseline["pooled_test"]
        mean_primary = _metric_at_10(pooled_mean, "C mean30 pooled test")
        none_primary = _metric_at_10(pooled_none, "none30 pooled test")
        primary_contrast = mean_primary - none_primary
        diagnostic._write_json(output_dir / "test_aggregate_2024_2025.json", pooled_none)
        diagnostic._write_json(
            output_dir / "cohort_comparison.json",
            {
                "status": "complete",
                "validation_2023": run_manifest["cohort_checks"]["validation_2023"],
                "test_2024": run_manifest["cohort_checks"]["test_2024"],
                "test_2025": run_manifest["cohort_checks"]["test_2025"],
                "pooled_test_population": POOLED_TEST_POPULATION,
            },
        )
        costs["wall_seconds"] = time.monotonic() - started_monotonic
        costs["origin"] = "none30 phase costs measured in D1; mean30 costs reused from C and kept separately"
        costs["none30"] = _phase_costs(costs_by_phase)
        costs["mean30_reused_C"] = _reused_c_costs(baseline)
        capacity_by_fit: dict[str, dict[str, int]] = {}
        for phase_name, none_capacity in none_checkpoint_capacities.items():
            mean_capacity = baseline["checkpoint_metadata"][phase_name]
            if none_capacity["active_node_vector_scalars"] != mean_capacity["active_node_vector_scalars"]:
                raise ValueError(f"mean and none node-vector capacity differs for {phase_name}")
            capacity_by_fit[phase_name] = {
                "products": none_capacity["products"],
                "problems": none_capacity["problems"],
                "active_node_vector_scalars_each": none_capacity["active_node_vector_scalars"],
                "mean_active_shared_transform_scalars": mean_capacity["active_shared_transform_scalars"],
                "none_active_shared_transform_scalars": none_capacity["active_shared_transform_scalars"],
                "mean_total_active_parameter_scalars": mean_capacity["active_parameter_scalars"],
                "none_total_active_parameter_scalars": none_capacity["active_parameter_scalars"],
                "mean_minus_none_active_parameter_scalars": mean_capacity["active_parameter_scalars"] - none_capacity["active_parameter_scalars"],
            }
        report: dict[str, Any] = {
            "schema": "healthgraphbench.maude-aggregation-ablation-report.v1",
            "status": "complete",
            "started_at_utc": started_at,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "duration_epochs": COMMON_DURATION_EPOCHS,
            "selection_lock": selection_lock,
            "validation": {
                "population": diagnostic.VALIDATION_POPULATION,
                "mean30_reused_micro_recall_at_10": mean_validation_score,
                "none30_new_micro_recall_at_10": none_validation_score,
                "candidate_cohorts_match": True,
                "none_fit": none_validation,
            },
            "test": {
                "population": POOLED_TEST_POPULATION,
                "mean30_reused": pooled_mean,
                "none30_new": pooled_none,
                "annual_none_summaries": none_test_summaries,
            },
            "primary_contrast": {
                "metric": "micro recall@10, historical product support >=1, pooled 2024Q1-2025Q4",
                "definition": "mean30 - none30",
                "mean30": mean_primary,
                "none30": none_primary,
                "signed_mean_minus_none": primary_contrast,
                "direction_interpreted_as_observed": True,
                "new_confidence_interval": False,
            },
            "capacity": {
                "dimension": GRAPHSAGE_DIMENSION,
                "active_shared_transformation_scalars": {"mean": 128, "none": 64},
                "inactive_neighbor_matrix_checkpoint_scalars_none": 64,
                "by_fit": capacity_by_fit,
                "interpretation": "none has 64 fewer active shared transformation scalars; node-identity vectors remain trainable in both",
            },
            "costs": costs,
            "provenance": {
                "mean30": {
                    "origin": "reused from pinned C; not retrained in D1",
                    "manifest": str(baseline_manifest),
                    "manifest_sha256": baseline["manifest_sha256"],
                    "code_commit": baseline["manifest"].get("code_commit"),
                    "artifact_hashes": baseline["verified_artifacts"],
                },
                "none30": {
                    "origin": "new D1 fit and serial test phases",
                    "input_sha256": actual_input_sha256,
                    "protocol_sha256": actual_protocol_sha256,
                    "new_artifact_hashes": "run_manifest.json artifact_hashes",
                },
                "resume_supported": False,
                "independent_confirmation": False,
                "candidate_exports": "candidate sets, scores, ranks, labels and raw checkpoints are retained in this run directory",
            },
            "limitations": [
                "C's mean30 costs and results are reused; they are not new D1 work",
                "mean and none have different active shared transformation capacity and gradient paths",
                "the analysis is not independent confirmation and has no new confidence interval",
                "positive-only historical candidate cohorts do not measure precision or general clinical utility",
            ],
        }
        run_manifest["artifact_hashes"] = _output_artifact_hashes(output_dir)
        run_manifest["costs"] = costs
        run_manifest["status"] = "complete"
        run_manifest["finished_at_utc"] = report["finished_at_utc"]
        diagnostic._write_json(output_dir / "report.json", report)
        diagnostic._write_json(output_dir / "run_manifest.json", run_manifest)
        return report
    except BaseException as exc:
        costs["wall_seconds"] = time.monotonic() - started_monotonic
        costs["origin"] = "partial none30 phase costs; mean30 remains reused C evidence"
        costs["none30"] = _phase_costs(costs_by_phase)
        costs["mean30_reused_C"] = _reused_c_costs(baseline)
        run_manifest["status"] = "incomplete"
        run_manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        run_manifest["error"] = f"{type(exc).__name__}: {exc}"
        run_manifest["costs"] = costs
        for phase in phases.values():
            if phase.get("status") == "running":
                phase.update(status="incomplete", reason=run_manifest["error"])
        run_manifest["artifact_hashes"] = _output_artifact_hashes(output_dir)
        diagnostic._write_json(output_dir / "run_manifest.json", run_manifest)
        diagnostic._write_json(
            output_dir / "report.json",
            {
                "schema": "healthgraphbench.maude-aggregation-ablation-report.v1",
                "status": "incomplete",
                "started_at_utc": started_at,
                "finished_at_utc": run_manifest["finished_at_utc"],
                "error": run_manifest["error"],
                "phases": phases,
                "selection_lock": run_manifest.get("selection"),
                "cohort_checks": run_manifest.get("cohort_checks", {}),
                "costs": costs,
                "interpretation": "no pooled contrast is published unless all fixed validation and test cohorts complete and match C",
            },
        )
        raise


def _record_cli_stdout(output_dir: Path, content: str) -> None:
    stdout_path = output_dir / "stdout.txt"
    stdout_path.write_text(content, encoding="utf-8")
    manifest_path = output_dir / "run_manifest.json"
    manifest = _read_json(manifest_path)
    record = {
        "status": "captured",
        "path": "stdout.txt",
        "sha256": _sha256_file(stdout_path),
        "size_bytes": stdout_path.stat().st_size,
    }
    manifest["command"]["stdout_capture"] = record
    manifest.setdefault("artifact_hashes", {})["stdout.txt"] = {
        "sha256": record["sha256"],
        "size_bytes": record["size_bytes"],
    }
    diagnostic._write_json(manifest_path, manifest)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    repo_root = _repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-input", type=Path, default=repo_root / PINNED_INPUT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--protocol", type=Path, default=repo_root / PROTOCOL_PATH)
    parser.add_argument("--protocol-sha256", default=PINNED_PROTOCOL_SHA256)
    parser.add_argument("--baseline-manifest", type=Path, default=repo_root / PINNED_BASELINE_MANIFEST)
    parser.add_argument("--baseline-sha256", default=PINNED_BASELINE_SHA256)
    parser.add_argument("--phase-timeout-seconds", type=float, default=diagnostic.MAX_TIMEOUT_SECONDS)
    parser.add_argument("--max-rss-mib", type=int, default=512)
    parser.add_argument("--max-output-mib", type=int, default=512)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = args.output_dir
    if output_dir is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = _repo_root() / "results/generated/consolidation-post-RC1" / f"maude-aggregation-{run_id}"
    output_dir = output_dir.resolve()
    captured = io.StringIO()
    failure: Exception | None = None
    with contextlib.redirect_stdout(captured):
        try:
            report = run_ablation(
                prepared_input=args.prepared_input,
                output_dir=output_dir,
                protocol=args.protocol,
                protocol_sha256=args.protocol_sha256,
                baseline_manifest=args.baseline_manifest,
                baseline_sha256=args.baseline_sha256,
                phase_timeout_seconds=args.phase_timeout_seconds,
                max_rss_mib=args.max_rss_mib,
                max_output_mib=args.max_output_mib,
            )
            print(f"wrote {output_dir / 'report.json'}")
            print(f"mean30 reused micro recall@10: {report['primary_contrast']['mean30']:.12f}")
            print(f"none30 new micro recall@10: {report['primary_contrast']['none30']:.12f}")
            print(f"signed mean30 - none30: {report['primary_contrast']['signed_mean_minus_none']:+.12f}")
        except Exception as exc:
            failure = exc
    stdout = captured.getvalue()
    if output_dir.is_dir() and (output_dir / "run_manifest.json").is_file():
        _record_cli_stdout(output_dir, stdout)
    sys.stdout.write(stdout)
    if failure is not None:
        print(f"MAUDE aggregation ablation failed: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
