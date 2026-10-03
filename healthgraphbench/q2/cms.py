"""Preregistered exploratory CMS comparisons from verified raw snapshots."""

from __future__ import annotations

import argparse
import gzip
import json
import pickle
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..data import load_manifest, sha256_file, verify_files
from ..tasks.cms_nursing.models import model_metrics, row_numeric
from ..tasks.cms_nursing.task import CmsNursingTask
from ..tasks.maude import diagnostic
from .common import REPO_ROOT, RunBudget, load_protocol


def _prepare_phase(source_root: Path, manifest_path: Path, phase_dir: Path) -> dict[str, Any]:
    root = source_root / "cms" if (source_root / "cms").is_dir() else source_root
    manifest = load_manifest(manifest_path)
    verified = verify_files(root, manifest["cms"]["files"])
    task = CmsNursingTask.from_source_root(root)
    rows_path = phase_dir / "rows.jsonl.gz"
    with gzip.open(rows_path, "wt", encoding="utf-8") as output:
        for row in task.prepared.rows:
            payload = dict(row)
            payload["date"] = row["date"].isoformat()
            output.write(json.dumps(payload, allow_nan=False) + "\n")
    return {
        "rows": len(task.prepared.rows),
        "source_files": verified,
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "rows_sha256": sha256_file(rows_path),
        "input_level": "raw_verified_then_new_preparation",
        "availability": "retrospective_snapshot_not_origin_verified",
    }


def _load_rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def _matrices(
    rows: list[dict[str, Any]], year: int, graph: bool
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]], tuple[str, ...]]:
    training = [row for row in rows if 2019 <= row["year"] < year]
    target = [row for row in rows if row["year"] == year]
    if not training or not target:
        raise ValueError(f"CMS {year} requires nonempty strictly prior training and target rows")
    states = tuple(sorted({str(row["state"]) for row in training}))
    labels = np.asarray([row["label"] for row in training], dtype=np.int64)
    if np.unique(labels).size != 2:
        raise ValueError(f"CMS {year} training must contain both classes")
    xs = np.asarray([row_numeric(row, graph, states) for row in training], dtype=np.float64)
    targets = np.asarray([row_numeric(row, graph, states) for row in target], dtype=np.float64)
    return xs, labels, targets, target, states


def _fit_phase(
    rows_path: Path,
    year: int,
    feature_set: str,
    family: str,
    configuration: dict[str, Any],
    fixed: dict[str, Any],
    seed: int | None,
    phase_dir: Path,
) -> dict[str, Any]:
    rows = _load_rows(rows_path)
    graph = feature_set == "facility_plus_combined_ownership"
    xs, labels, target_xs, target, states = _matrices(rows, year, graph)
    if family == "logistic":
        parameters = {**fixed, **configuration}
        model = make_pipeline(StandardScaler(), LogisticRegression(**parameters))
    elif family == "boosted":
        parameters = {key: value for key, value in fixed.items() if key != "seed_repetition_condition"}
        parameters.update(configuration)
        model = HistGradientBoostingClassifier(random_state=0 if seed is None else seed, **parameters)
    else:
        raise ValueError(f"unknown CMS family {family!r}")
    with warnings.catch_warnings(record=True) as observed_warnings:
        warnings.simplefilter("always")
        model.fit(xs, labels)
    scores = model.predict_proba(target_xs)[:, 1]
    training_scores = model.predict_proba(xs)[:, 1]
    if observed_warnings:
        diagnostic._write_json(
            phase_dir / "warnings.json",
            [{"category": item.category.__name__, "message": str(item.message)} for item in observed_warnings],
        )
    checkpoint = phase_dir / "checkpoint.pkl"
    with checkpoint.open("xb") as output:
        pickle.dump({"model": model, "state_values": states, "graph_features": graph}, output, protocol=5)
    predictions = []
    for row, score in zip(target, scores.tolist(), strict=True):
        predictions.append({"ccn": row["ccn"], "date": row["date"], "year": year, "label": row["label"], "score": score})
    with gzip.open(phase_dir / "predictions.jsonl.gz", "wt", encoding="utf-8") as output:
        for row in predictions:
            output.write(json.dumps(row, allow_nan=False) + "\n")
    fitted = model[-1] if family == "logistic" else model
    return {
        "family": family,
        "feature_set": feature_set,
        "year": year,
        "configuration": configuration,
        "fixed": fixed,
        "seed": seed,
        "training_rows": int(labels.size),
        "training_positives": int(labels.sum()),
        "target_rows": len(target),
        "feature_dimension": int(xs.shape[1]),
        "state_vocabulary_source": "strictly_prior_training_only",
        "iterations": int(np.max(fitted.n_iter_)),
        "losses": {
            "definition": "unweighted strictly-prior training binary cross-entropy data loss",
            "initial_zero_logit": float(log_loss(labels, np.full(labels.shape, .5), labels=[0, 1])),
            "trained": float(log_loss(labels, training_scores, labels=[0, 1])),
            "full_iteration_trace_available": False,
        },
        "warnings": [{"category": item.category.__name__, "message": str(item.message)} for item in observed_warnings],
        "checkpoint": {"path": "checkpoint.pkl", "sha256": sha256_file(checkpoint), "trusted_internal_pickle_only": True},
        "prediction_sha256": sha256_file(phase_dir / "predictions.jsonl.gz"),
        "metrics": model_metrics([row["label"] for row in target], scores.tolist()),
    }


def select_validation(records: list[dict[str, Any]], grid_size: int) -> dict[str, Any]:
    """Select a configuration, never an initialization, after every declared fit."""
    grouped: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["configuration_index"], []).append(record)
    if set(grouped) != set(range(grid_size)):
        raise ValueError("CMS selection requires a complete configuration grid")
    scores = []
    for index in range(grid_size):
        group = grouped[index]
        expected = group[0]["expected_seeds"]
        if [item["seed"] for item in group] != expected:
            raise ValueError("CMS selection requires every declared seed, without duplicates")
        values = [item["metrics"]["roc_auc"] for item in group]
        if any(value is None or not np.isfinite(value) for value in values):
            raise ValueError("CMS selection requires defined finite validation ROC-AUC")
        scores.append(sum(values) / len(values))
    selected = max(range(grid_size), key=lambda index: (scores[index], -index))
    return {"configuration_index": selected, "mean_validation_roc_auc": scores[selected], "grid_validation_roc_auc": scores, "tie_break": "published_grid_order", "seed_selection": False}


def _pool_annual_predictions(
    annual: dict[int, dict[int | None, list[dict[str, Any]]]],
    declared_seeds: list[int],
) -> dict[str, Any]:
    """Pool comparable years, reusing a deterministic fit rather than refitting it."""
    for predictions in annual.values():
        if set(predictions) != {None} and set(predictions) != set(declared_seeds):
            raise ValueError("CMS pooling requires one deterministic fit or every declared seed")
    streams: list[int | None] = (
        list(declared_seeds) if any(set(predictions) != {None} for predictions in annual.values())
        else [None]
    )
    metrics = {}
    provenance = {}
    for seed in streams:
        rows = []
        reused = []
        for year in sorted(annual):
            key = None if set(annual[year]) == {None} else seed
            rows.extend(annual[year][key])
            if key is None and seed is not None:
                reused.append(year)
        metrics[str(seed)] = model_metrics(
            [row["label"] for row in rows], [row["score"] for row in rows]
        )
        provenance[str(seed)] = {
            "years": sorted(annual),
            "deterministic_fit_reused_years": reused,
            "seed_selection": False,
        }
    return {"pooled_by_seed": metrics, "pooled_streams": provenance}


def _seeds(family: str, training_rows: int, declared_seeds: list[int]) -> list[int | None]:
    return list(declared_seeds) if family == "boosted" and training_rows > 200000 else [None]


def run_comparison(
    source_root: Path,
    output_dir: Path,
    protocol: Path,
    protocol_sha256: str,
    limits: dict[str, int | float] | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to reuse CMS Q2 output: {output_dir}")
    output_dir.mkdir(parents=True)
    try:
        configuration = load_protocol(protocol, protocol_sha256, output_dir)
        task = configuration["tasks"]["cms"]
        if (
            task["name"] != "cms_nursing" or task["primary_metric"] != "roc_auc"
            or task["validation_year"] != 2023 or task["test_years"] != [2024, 2025]
        ):
            raise ValueError("CMS Q2 requires validation2023 ROC-AUC and tests2024/2025")
        effective_limits = dict(configuration["limits"])
        if limits is not None:
            effective_limits.update(limits)
        budget = RunBudget(output_dir, effective_limits)
        preparation_dir = output_dir / "preparation"
        budget.execute(
            _prepare_phase,
            (Path(source_root), REPO_ROOT / Path(task["source_manifest"])),
            preparation_dir,
        )
        rows_path = preparation_dir / "rows.jsonl.gz"
        rows = _load_rows(rows_path)
        validation_year = task["validation_year"]
        validation_training_rows = sum(2019 <= row["year"] < validation_year for row in rows)
        validation: dict[str, list[dict[str, Any]]] = {}
        selection: dict[str, dict[str, Any]] = {}
        for feature_set in task["feature_sets"]:
            for family, grid in task["grids"].items():
                name = f"{feature_set}__{family}"
                validation[name] = []
                seeds = _seeds(family, validation_training_rows, task["seeds"])
                for index, parameters in enumerate(grid):
                    for seed in seeds:
                        phase_dir = output_dir / "validation" / name / f"config{index:02d}" / f"seed{seed}"
                        budget.execute(
                            _fit_phase,
                            (rows_path, validation_year, feature_set, family, parameters, task["fixed"][family], seed),
                            phase_dir,
                            family=name,
                        )
                        result = json.loads((phase_dir / "result.json").read_text())
                        result.update(configuration_index=index, expected_seeds=seeds, phase_path=str(phase_dir.relative_to(output_dir)))
                        validation[name].append(result)
                selection[name] = select_validation(validation[name], len(grid))
        diagnostic._write_json(output_dir / "validation.json", validation)
        diagnostic._write_json(output_dir / "selection.json", {"status": "locked_after_complete_validation_before_test", "selection": selection, "evidence_level": configuration["evidence_level"]})
        test: dict[str, Any] = {}
        for name, chosen in selection.items():
            feature_set, family = name.split("__")
            parameters = task["grids"][family][chosen["configuration_index"]]
            annual = {}
            annual_predictions: dict[int, dict[int | None, list[dict[str, Any]]]] = {}
            for year in task["test_years"]:
                count = sum(2019 <= row["year"] < year for row in rows)
                seeds = _seeds(family, count, task["seeds"])
                annual[str(year)] = []
                annual_predictions[year] = {}
                for seed in seeds:
                    phase_dir = output_dir / "test" / name / str(year) / f"seed{seed}"
                    budget.execute(_fit_phase, (rows_path, year, feature_set, family, parameters, task["fixed"][family], seed), phase_dir)
                    result = json.loads((phase_dir / "result.json").read_text())
                    annual[str(year)].append(result)
                    with gzip.open(phase_dir / "predictions.jsonl.gz", "rt", encoding="utf-8") as source:
                        annual_predictions[year][seed] = [json.loads(line) for line in source]
            test[name] = {"annual": annual, **_pool_annual_predictions(annual_predictions, task["seeds"])}
        # Prevalence has no tuning opportunity and is scored only after the lock.
        prevalence_rows = []
        prevalence_annual = {}
        for year in task["test_years"]:
            training = [row for row in rows if 2019 <= row["year"] < year]
            targets = [row for row in rows if row["year"] == year]
            score = sum(row["label"] for row in training) / len(training)
            prevalence_rows.extend({"ccn": row["ccn"], "date": row["date"], "year": year, "label": row["label"], "score": score} for row in targets)
            prevalence_annual[str(year)] = model_metrics([row["label"] for row in targets], [score] * len(targets))
        diagnostic._write_json(output_dir / "prevalence_predictions.json", prevalence_rows)
        test["prevalence"] = {"annual": prevalence_annual, "pooled": model_metrics([row["label"] for row in prevalence_rows], [row["score"] for row in prevalence_rows])}
        result = {"schema": "healthgraphbench.q2-cms-comparison.v1", "status": "complete", "evidence_level": configuration["evidence_level"], "preparation": json.loads((preparation_dir / "result.json").read_text()), "selection": selection, "validation": validation, "test": test, "availability_limit": task["availability_limit"]}
        diagnostic._write_json(output_dir / "comparison.json", result)
        return result
    except BaseException as exc:
        diagnostic._write_json(output_dir / "run_error.json", {"type": type(exc).__name__, "message": str(exc), "status": "incomplete"})
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    args = parser.parse_args(argv)
    result = run_comparison(args.source_root, args.output_dir, args.protocol, args.protocol_sha256)
    print(json.dumps({"status": result["status"], "selection": result["selection"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
