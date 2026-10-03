"""Raw-data MAUDE comparison cycle for Q2."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import pickle
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..tasks.maude.data import DataBundle, QUARTERS
from ..tasks.maude.evaluate import (
    MetricAccumulator,
    SUPPORT_BANDS,
    SUPPORT_THRESHOLDS,
    _aggregate_metric_rows,
    eligible_edges,
    first_edges,
    support_band,
)
from ..tasks.maude.models import FEATURE_NAMES, FeatureContext, History, TrainingRow, sample_training_rows
from ..tasks.maude.task import MaudeTask
from . import common
from .maude_backend import (
    fit_bpr,
    fit_graphsage,
    fit_spectral,
    save_bpr_checkpoint,
    save_graphsage_checkpoint,
    save_spectral_checkpoint,
)


DEFAULT_LIMITS: dict[str, int] = {
    "timeout_seconds": 1_800,
    "max_rss_bytes": 4 * 1024**3,
    "max_output_bytes": 1024**3,
    "family_validation_wall_seconds": 21_600,
    "run_wall_seconds": 86_400,
    "total_output_bytes": 16 * 1024**3,
}

FAMILY_METHODS: dict[str, str] = {
    "logistic": "logistic_tabular",
    "boosted": "boosted_trees_tabular",
    "spectral": "matrix_factorization_spectral",
    "bpr": "graph_message_passing_bpr",
    "graphsage_mean": "graphsage_mean_bpr",
    "graphsage_none": "graphsage_none_bpr",
}
_LATENT_FAMILIES = frozenset({"spectral", "bpr", "graphsage_mean", "graphsage_none"})


def _numpy() -> Any:
    try:
        import numpy as np
    except ImportError as error:
        raise RuntimeError("The MAUDE Q2 runner requires NumPy from the optional `q2` extra") from error
    return np


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _json_read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _extract_protocol(loaded: Mapping[str, Any]) -> dict[str, Any]:
    candidate: Any = loaded.get("protocol")
    if candidate is None:
        candidate = loaded.get("protocol_json")
    if candidate is None and isinstance(loaded.get("tasks"), Mapping):
        candidate = loaded
    if not isinstance(candidate, dict):
        raise ValueError("common.load_protocol did not return the executed protocol JSON")
    tasks = candidate.get("tasks")
    if not isinstance(tasks, Mapping) or not isinstance(tasks.get("maude"), dict):
        raise ValueError("executed protocol must define tasks.maude")
    return candidate


def _protocol_config(protocol: Mapping[str, Any]) -> dict[str, Any]:
    task = protocol["tasks"]["maude"]
    if task.get("name") != "maude":
        raise ValueError("tasks.maude.name must be 'maude'")
    if task.get("primary_metric") != "micro_recall_at_10":
        raise ValueError("MAUDE Q2 selection metric must be micro_recall_at_10")
    if (
        task.get("train_through") != "2022Q4"
        or task.get("validation_year") != 2023
        or task.get("test_years") != [2024, 2025]
    ):
        raise ValueError("MAUDE Q2 requires training through2022, validation2023, tests2024/2025")
    if task.get("selection") != "mean_validation_2023_micro_recall_at_10":
        raise ValueError("unsupported MAUDE Q2 selection rule")
    grids = task.get("grids")
    fixed = task.get("fixed")
    if not isinstance(grids, Mapping) or not isinstance(fixed, Mapping):
        raise ValueError("MAUDE protocol must contain grids and fixed model settings")
    expected_grid_fields = {
        "logistic": {"C"},
        "boosted": {"max_iter", "max_leaf_nodes", "l2_regularization"},
        "spectral": {"rank", "power_iterations"},
        "bpr": {"dimension", "regularization"},
    }
    parsed_grids: dict[str, list[dict[str, int | float]]] = {}
    for family, fields in expected_grid_fields.items():
        rows = grids.get(family)
        if not isinstance(rows, list) or len(rows) != 6:
            raise ValueError(f"MAUDE {family} grid must contain exactly six configurations")
        parsed: list[dict[str, int | float]] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != fields:
                raise ValueError(f"invalid MAUDE {family} grid configuration")
            normalized: dict[str, int | float] = {}
            for name, value in row.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"invalid {family}.{name} value")
                if not math.isfinite(float(value)):
                    raise ValueError(f"non-finite {family}.{name} value")
                normalized[name] = value
            parsed.append(normalized)
        parsed_grids[family] = parsed
    seeds = task.get("seeds")
    if seeds != [103, 211, 307]:
        raise ValueError("MAUDE task seeds must be [103, 211, 307]")
    if protocol.get("evidence_level") != "exploratory_on_previously_consulted_2023_2025":
        raise ValueError("MAUDE 2023-2025 results must remain explicitly exploratory")
    learning_gate = protocol.get("learning_gate")
    if learning_gate != {
        "variants": ["mean", "none"],
        "fixed_historical_probe_max_triplets": 20000,
        "minimum_relative_bpr_data_loss_reduction": 0.01,
        "required_for_every_seed": True,
        "changed_checkpoint_required": True,
        "capacity_equal_causal_claim": False,
        "selection_requires_all_seed_learning_gates": True,
    }:
        raise ValueError("MAUDE GraphSAGE learning gate differs from the published contract")
    logistic_fixed = fixed.get("logistic")
    boosted_fixed = fixed.get("boosted")
    spectral_fixed = fixed.get("spectral")
    bpr_fixed = fixed.get("bpr")
    if logistic_fixed != {
        "solver": "lbfgs",
        "class_weight": "balanced",
        "max_iter": 1000,
        "tol": 1e-8,
    }:
        raise ValueError("MAUDE logistic fixed settings differ from the published contract")
    if boosted_fixed != {
        "learning_rate": 0.1,
        "early_stopping": False,
        "max_features": 1,
        "max_bins": 255,
        "min_samples_leaf": 20,
        "seed_repetition_condition": "training_rows_gt_200000",
    }:
        raise ValueError("MAUDE boosted fixed settings differ from the published contract")
    if bpr_fixed != {"epochs": 30, "learning_rate": 0.03}:
        raise ValueError("MAUDE BPR fixed settings differ from the published contract")
    if spectral_fixed != {"seeded_initialization": True}:
        raise ValueError("MAUDE spectral initialization must be seeded")
    graph = task.get("graphsage")
    if not isinstance(graph, dict):
        raise ValueError("MAUDE protocol must define GraphSAGE mean/none settings")
    if set(graph) != {
        "dimension",
        "regularization",
        "epochs",
        "learning_rate",
        "fanout",
        "seeds",
        "initialization",
    }:
        raise ValueError("invalid MAUDE GraphSAGE settings")
    if graph["dimension"] != [8, 16] or graph["regularization"] != [0.0005, 0.000005, 0.0]:
        raise ValueError("MAUDE GraphSAGE grid must be dimension [8,16] × regularization [0.0005,0.000005,0]")
    if graph["epochs"] != 30 or graph["learning_rate"] != 0.02 or graph["fanout"] != 8:
        raise ValueError("MAUDE GraphSAGE fixed settings differ from the published contract")
    if graph["seeds"] != seeds or graph["initialization"] != {"distribution": "normal", "sigma": 0.05}:
        raise ValueError("MAUDE GraphSAGE seeds/initialization differ from the published contract")
    graph_configs = [
        {"dimension": dimension, "regularization": regularization}
        for dimension in graph["dimension"]
        for regularization in graph["regularization"]
    ]
    if len({json.dumps(config, sort_keys=True) for config in graph_configs}) != 6:
        raise ValueError("MAUDE GraphSAGE grid must contain six distinct configurations")
    independent = protocol.get("independent_evaluation")
    if not isinstance(independent, Mapping):
        raise ValueError("Q2 MAUDE protocol must state independent-evaluation status")
    if independent.get("status") != "gated_pending_availability_and_independence_evidence":
        raise ValueError("Q2 MAUDE results cannot claim independent evaluation")
    if (
        independent.get("previously_consulted_periods_remain_exploratory") is not True
        or independent.get("unavailable_data_or_missing_human_attestation_is_not_a_pass") is not True
    ):
        raise ValueError("Q2 MAUDE independent-evaluation gate differs from the protocol")
    return {
        "task": task,
        "grids": parsed_grids,
        "graph_configs": graph_configs,
        "seeds": tuple(seeds),
        "fixed": fixed,
        "learning_gate": learning_gate,
        "boosted_seed_threshold": 200000,
        "independent_evaluation": dict(independent),
    }


def _to_arrays(rows: Sequence[TrainingRow]) -> tuple[Any, Any]:
    np = _numpy()
    if not rows:
        return np.empty((0, len(FEATURE_NAMES)), dtype=np.float64), np.empty((0,), dtype=np.int8)
    features = np.empty((len(rows), len(FEATURE_NAMES)), dtype=np.float64)
    labels = np.empty((len(rows),), dtype=np.int8)
    for index, row in enumerate(rows):
        if len(row.features) != len(FEATURE_NAMES):
            raise ValueError("MAUDE training feature width changed")
        features[index] = row.features
        labels[index] = row.label
    return features, labels


def _concat_years(archive: Any, first: int, last: int) -> tuple[Any, Any]:
    np = _numpy()
    features = [archive[f"x{year}"] for year in range(first, last + 1) if f"x{year}" in archive]
    labels = [archive[f"y{year}"] for year in range(first, last + 1) if f"y{year}" in archive]
    if not features:
        return np.empty((0, len(FEATURE_NAMES)), dtype=np.float64), np.empty((0,), dtype=np.int8)
    return np.concatenate(features, axis=0), np.concatenate(labels, axis=0)


def _training_data(path: Path, first_year: int, last_year: int) -> tuple[Any, Any]:
    np = _numpy()
    with np.load(path, allow_pickle=False) as archive:
        return _concat_years(archive, first_year, last_year)


def _source_manifest(paths: Sequence[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for value in dict.fromkeys(paths):
        path = Path(value)
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        result.append(
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": digest.hexdigest(),
            }
        )
    return result


def _prepare_worker(source_root: str, phase_dir: Path) -> None:
    """Parse immutable raw MAUDE inputs and cache history-only train examples."""
    np = _numpy()
    task = MaudeTask.from_source_root(Path(source_root))
    bundle: DataBundle = task.bundle
    observed = first_edges(bundle)
    history = History.empty()
    rows_by_year: dict[int, list[tuple[Any, Any]]] = defaultdict(list)
    for snapshot in bundle.snapshots:
        year = int(snapshot.quarter[:4])
        if year <= 2024:
            rows = sample_training_rows(
                snapshot.quarter,
                eligible_edges(observed[snapshot.quarter], history),
                FeatureContext(history, snapshot.quarter, task.problem_parent_map),
                negative_ratio=1,
            )
            x, y = _to_arrays(rows)
            if len(y):
                rows_by_year[year].append((x, y))
        history.add(snapshot, task.problem_parent_map)
    raw_sources = _source_manifest(
        [str(path) for path in (*bundle.source_paths, task.problem_code_map)]
    )
    cached: dict[str, Any] = {
        "bundle": bundle,
        "problem_parent_map": task.problem_parent_map,
        "code_to_imdrf": task.code_to_imdrf,
        "source_root": str(Path(source_root)),
        "task_manifest": task.manifest(),
        "raw_sources": raw_sources,
    }
    phase_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(phase_dir / "maude_raw_bundle.pkl.gz", "wb", compresslevel=1) as output:
        pickle.dump(cached, output, protocol=pickle.HIGHEST_PROTOCOL)
    arrays: dict[str, Any] = {}
    for year in range(2019, 2025):
        chunks = rows_by_year.get(year, [])
        if chunks:
            arrays[f"x{year}"] = np.concatenate([item[0] for item in chunks], axis=0)
            arrays[f"y{year}"] = np.concatenate([item[1] for item in chunks], axis=0)
        else:
            arrays[f"x{year}"] = np.empty((0, len(FEATURE_NAMES)), dtype=np.float64)
            arrays[f"y{year}"] = np.empty((0,), dtype=np.int8)
    with (phase_dir / "training_rows.npz").open("wb") as output:
        np.savez_compressed(output, **arrays)
    _json_write(
        phase_dir / "prepared.json",
        {
            "task_manifest": cached["task_manifest"],
            "training_rows_by_year": {
                str(year): int(len(arrays[f"y{year}"])) for year in range(2019, 2025)
            },
            "feature_names": list(FEATURE_NAMES),
            "raw_sources": cached["raw_sources"],
        },
    )


def _load_prepared(bundle_path: Path) -> dict[str, Any]:
    with gzip.open(bundle_path, "rb") as source:
        value = pickle.load(source)
    if not isinstance(value, dict) or not isinstance(value.get("bundle"), DataBundle):
        raise ValueError("invalid raw MAUDE bundle cache")
    return value


def _history_before(bundle: DataBundle, quarter: str, parent_map: Mapping[str, str]) -> History:
    history = History.empty()
    for snapshot in bundle.snapshots:
        if snapshot.quarter >= quarter:
            break
        history.add(snapshot, parent_map)
    return history


def _rank_candidates(
    history: History,
    quarter: str,
    product: str,
    candidates: Sequence[str],
    model_family: str,
    model: Any,
    parent_map: Mapping[str, str],
) -> list[tuple[str, float]]:
    if model_family in {"logistic", "boosted"}:
        np = _numpy()
        context = FeatureContext(history, quarter, parent_map)
        neighbor_scores = context.neighbor_scores(product)
        features = np.empty((len(candidates), len(FEATURE_NAMES)), dtype=np.float64)
        for index, problem in enumerate(candidates):
            features[index] = context.features_for(product, problem, neighbor_scores)
        scores = model.predict_proba(features)[:, 1] if candidates else np.empty((0,))
        values = [(problem, float(scores[index])) for index, problem in enumerate(candidates)]
    elif model_family == "global_popularity":
        values = [(problem, float(len(history.problem_products[problem]))) for problem in candidates]
    elif model_family == "neighbor_frequency":
        context = FeatureContext(history, quarter, parent_map)
        neighbors = context.neighbor_scores(product)
        values = [(problem, float(neighbors.get(problem, 0))) for problem in candidates]
    else:
        values = [(problem, float(model.score(product, problem))) for problem in candidates]
    popularity = history.problem_products
    values.sort(key=lambda pair: (-pair[1], -len(popularity[pair[0]]), pair[0]))
    return values


def _candidate_fingerprint(candidates: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for candidate in candidates:
        encoded = candidate.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _evaluate_quarter(
    bundle: DataBundle,
    first: Mapping[str, frozenset[tuple[str, str]]],
    history: History,
    parent_map: Mapping[str, str],
    quarter: str,
    method: str,
    family: str,
    model: Any,
    predictions_path: Path | None,
) -> dict[str, Any]:
    eligible = eligible_edges(first[quarter], history)
    positives_by_product: dict[str, set[str]] = defaultdict(set)
    for product, problem in eligible:
        positives_by_product[product].add(problem)
    thresholds = {threshold: MetricAccumulator() for threshold in SUPPORT_THRESHOLDS}
    bands = {band: MetricAccumulator() for band in SUPPORT_BANDS}
    prediction_file = None
    if predictions_path is not None:
        predictions_path.parent.mkdir(parents=True, exist_ok=True)
        prediction_file = gzip.open(predictions_path, "wt", encoding="utf-8", newline="\\n")
    try:
        for product in sorted(positives_by_product):
            positives = positives_by_product[product]
            candidates = history.candidate_problems(product)
            if not positives.issubset(candidates):
                raise RuntimeError(f"eligible MAUDE positives are outside candidate universe in {quarter}")
            ranking = _rank_candidates(
                history, quarter, product, candidates, family, model, parent_map
            )
            ranks = {problem: index + 1 for index, (problem, _) in enumerate(ranking)}
            positive_ranks = [ranks[problem] for problem in positives]
            support = history.product_reports.get(product, 0)
            for threshold, accumulator in thresholds.items():
                selected = [
                    ranks[problem]
                    for problem in positives
                    if support >= threshold
                ]
                if selected:
                    accumulator.add_product(selected, len(selected))
            bands[support_band(support)].add_product(positive_ranks, len(positive_ranks))
            if prediction_file is not None:
                universe = sorted(candidates)
                record = {
                    "record_kind": "product_ranking",
                    "quarter": quarter,
                    "method": method,
                    "product": product,
                    "history_support": support,
                    "positive_edges": len(positives),
                    "candidate_count": len(universe),
                    "candidate_universe_sha256_length_prefixed_utf8": _candidate_fingerprint(universe),
                    "positive_ranks": [
                        {
                            "problem": problem,
                            "rank": ranks[problem],
                            "score": ranking[ranks[problem] - 1][1],
                        }
                        for problem in sorted(positives)
                    ],
                    "top20": [
                        {"problem": problem, "rank": rank, "score": score}
                        for rank, (problem, score) in enumerate(ranking[:20], start=1)
                    ],
                }
                prediction_file.write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                    + "\\n"
                )
    finally:
        if prediction_file is not None:
            prediction_file.close()
    threshold_rows = {str(key): value.as_dict() for key, value in thresholds.items()}
    band_rows = {key: value.as_dict() for key, value in bands.items()}
    return {
        "thresholds": threshold_rows,
        "support_bands": band_rows,
        "primary_micro_recall_at_10": threshold_rows["1"]["recall_at_10"],
        "eligible_positive_edges": len(eligible),
    }


def _fit_tabular(
    family: str,
    configuration: Mapping[str, Any],
    x: Any,
    y: Any,
    fixed: Mapping[str, Any],
    seed: int,
    boosted_seed_threshold: int,
) -> Any:
    if len(x) == 0 or len(set(int(value) for value in y)) != 2:
        raise ValueError(f"{family} requires training examples from both classes")
    if family == "logistic":
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
        except ImportError as error:
            raise RuntimeError("scikit-learn is required by the MAUDE Q2 logistic baseline") from error
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=float(configuration["C"]),
                solver=str(fixed["solver"]),
                class_weight=str(fixed["class_weight"]),
                max_iter=int(fixed["max_iter"]),
                tol=float(fixed["tol"]),
            ),
        )
    elif family == "boosted":
        try:
            from sklearn.ensemble import HistGradientBoostingClassifier
        except ImportError as error:
            raise RuntimeError("scikit-learn is required by the MAUDE Q2 boosted-tree baseline") from error
        model = HistGradientBoostingClassifier(
            loss="log_loss",
            learning_rate=float(fixed["learning_rate"]),
            max_iter=int(configuration["max_iter"]),
            max_leaf_nodes=int(configuration["max_leaf_nodes"]),
            l2_regularization=float(configuration["l2_regularization"]),
            early_stopping=bool(fixed["early_stopping"]),
            max_features=float(fixed["max_features"]),
            max_bins=int(fixed["max_bins"]),
            min_samples_leaf=int(fixed["min_samples_leaf"]),
            random_state=seed if len(x) > boosted_seed_threshold else None,
        )
    else:
        raise ValueError(f"not a tabular model family: {family}")
    model.fit(x, y)
    return model


def _fit_model(
    family: str,
    configuration: Mapping[str, Any],
    seed: int,
    x: Any,
    y: Any,
    history: History,
    task_config: Mapping[str, Any],
) -> tuple[Any, dict[str, Any]]:
    fixed = task_config["fixed"]
    if family == "boosted" and seed not in _family_seeds(task_config, family, len(x)):
        raise ValueError("boosted-model seed does not match its training-row repetition condition")
    if family in {"logistic", "boosted"}:
        return _fit_tabular(
            family,
            configuration,
            x,
            y,
            fixed[family],
            seed,
            int(task_config["boosted_seed_threshold"]),
        ), {
            "configuration": dict(configuration),
            "fit_seed": seed,
            "fit_rows": len(x),
            "estimator_random_state": (
                seed if family == "boosted" and len(x) > int(task_config["boosted_seed_threshold"]) else None
            ),
        }
    if family == "spectral":
        return fit_spectral(
            history,
            rank=int(configuration["rank"]),
            power_iterations=int(configuration["power_iterations"]),
            seed=seed,
        )
    if family == "bpr":
        return fit_bpr(
            history,
            dimension=int(configuration["dimension"]),
            regularization=float(configuration["regularization"]),
            seed=seed,
            epochs=int(fixed["bpr"]["epochs"]),
            learning_rate=float(fixed["bpr"]["learning_rate"]),
        )
    if family in {"graphsage_mean", "graphsage_none"}:
        graph = task_config["task"]["graphsage"]
        return fit_graphsage(
            history,
            dimension=int(configuration["dimension"]),
            regularization=float(configuration["regularization"]),
            seed=seed,
            epochs=int(graph["epochs"]),
            learning_rate=float(graph["learning_rate"]),
            fanout=int(graph["fanout"]),
            aggregation="mean" if family == "graphsage_mean" else "none",
            probe_limit=int(task_config["learning_gate"]["fixed_historical_probe_max_triplets"]),
            minimum_probe_loss_reduction=float(
                task_config["learning_gate"]["minimum_relative_bpr_data_loss_reduction"]
            ),
        )
    raise ValueError(f"unknown MAUDE Q2 model family {family!r}")


def _save_model(path: Path, family: str, model: Any, diagnostics: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if family in {"logistic", "boosted"}:
        with path.open("wb") as output:
            pickle.dump(model, output, protocol=pickle.HIGHEST_PROTOCOL)
        return
    raw = diagnostics.get("raw_checkpoint")
    if not isinstance(raw, Mapping):
        raise ValueError(f"{family} did not provide a reconstructible checkpoint")
    if family == "spectral":
        save_spectral_checkpoint(path, raw)
    elif family == "bpr":
        save_bpr_checkpoint(path, raw)
    else:
        save_graphsage_checkpoint(path, raw)


def _fit_result_worker(
    prepared_dir: str,
    task_config: dict[str, Any],
    family: str,
    configuration: dict[str, Any],
    seed: int,
    phase_dir: Path,
) -> None:
    cached = _load_prepared(Path(prepared_dir) / "maude_raw_bundle.pkl.gz")
    bundle: DataBundle = cached["bundle"]
    parent_map: Mapping[str, str] = cached["problem_parent_map"]
    x, y = _training_data(Path(prepared_dir) / "training_rows.npz", 2019, 2022)
    fit_quarter = "2023Q1"
    evaluation_quarters = tuple(q for q in QUARTERS if q.startswith("2023"))
    history = _history_before(bundle, fit_quarter, parent_map)
    model, diagnostics = _fit_model(family, configuration, seed, x, y, history, task_config)
    checkpoint_path = phase_dir / "checkpoint.bin"
    _save_model(checkpoint_path, family, model, diagnostics)
    quarterly: dict[str, Any] = {}
    history = _history_before(bundle, evaluation_quarters[0], parent_map)
    snapshots = {snapshot.quarter: snapshot for snapshot in bundle.snapshots}
    first = first_edges(bundle)
    for quarter in evaluation_quarters:
        quarterly[quarter] = _evaluate_quarter(
            bundle,
            first,
            history,
            parent_map,
            quarter,
            FAMILY_METHODS[family],
            family,
            model,
            None,
        )
        history.add(snapshots[quarter], parent_map)
    config_record = dict(configuration)
    primary = _aggregate_primary(quarterly)
    record = {
        "family": family,
        "method": FAMILY_METHODS[family],
        "configuration": config_record,
        "seed": seed,
        "fit_cutoff": "2022Q4",
        "fit_training_rows": int(len(y)),
        "validation_quarters": quarterly,
        "annual_metrics": _aggregate_metrics(quarterly),
        "validation_micro_recall_at_10": primary,
        "checkpoint": checkpoint_path.name,
        "diagnostics": _public_diagnostics(diagnostics),
    }
    _json_write(phase_dir / "result.json", record)


def _public_diagnostics(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in diagnostics.items() if key != "raw_checkpoint"}
    for key in ("probe_loss_before", "probe_loss_after"):
        value = result.get(key)
        if isinstance(value, float) and not math.isfinite(value):
            result[key] = None
    return result


def _aggregate_primary(quarters: Mapping[str, Mapping[str, Any]]) -> float:
    positives = sum(int(value["thresholds"]["1"]["positive_edges"]) for value in quarters.values())
    hits = sum(int(value["thresholds"]["1"]["hits_at_10"]) for value in quarters.values())
    return hits / positives if positives else 0.0

def _aggregate_metrics(quarters: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    thresholds = {
        str(threshold): _aggregate_metric_rows(
            {quarter: value["thresholds"][str(threshold)] for quarter, value in quarters.items()}
        )
        for threshold in SUPPORT_THRESHOLDS
    }
    bands = {
        band: _aggregate_metric_rows(
            {quarter: value["support_bands"][band] for quarter, value in quarters.items()}
        )
        for band in SUPPORT_BANDS
    }
    return {"thresholds": thresholds, "support_bands": bands}


def _heuristics_worker(prepared_dir: str, validation: bool, year: int, phase_dir: Path) -> None:
    cached = _load_prepared(Path(prepared_dir) / "maude_raw_bundle.pkl.gz")
    bundle: DataBundle = cached["bundle"]
    parent_map: Mapping[str, str] = cached["problem_parent_map"]
    if validation:
        quarters = tuple(q for q in QUARTERS if q.startswith("2023"))
        start = quarters[0]
        record_scope = "validation"
    else:
        quarters = tuple(q for q in QUARTERS if q.startswith(str(year)))
        start = quarters[0]
        record_scope = "test"
    snapshots = {snapshot.quarter: snapshot for snapshot in bundle.snapshots}
    first = first_edges(bundle)
    output: dict[str, Any] = {"scope": record_scope, "year": year, "methods": {}}
    for family in ("global_popularity", "neighbor_frequency"):
        history = _history_before(bundle, start, parent_map)
        quarterly: dict[str, Any] = {}
        for quarter in quarters:
            prediction_path = (
                phase_dir / "predictions" / f"{family}" / f"{quarter}.jsonl.gz"
                if not validation
                else None
            )
            quarterly[quarter] = _evaluate_quarter(
                bundle,
                first,
                history,
                parent_map,
                quarter,
                family,
                family,
                None,
                prediction_path,
            )
            history.add(snapshots[quarter], parent_map)
        output["methods"][family] = {
            "quarters": quarterly,
            "annual_metrics": _aggregate_metrics(quarterly),
            "micro_recall_at_10": _aggregate_primary(quarterly),
        }
    _json_write(phase_dir / "result.json", output)


def _test_worker(
    prepared_dir: str,
    task_config: dict[str, Any],
    family: str,
    configuration: dict[str, Any],
    seed: int,
    year: int,
    phase_dir: Path,
) -> None:
    cached = _load_prepared(Path(prepared_dir) / "maude_raw_bundle.pkl.gz")
    bundle: DataBundle = cached["bundle"]
    parent_map: Mapping[str, str] = cached["problem_parent_map"]
    x, y = _training_data(
        Path(prepared_dir) / "training_rows.npz", 2019, 2023 if year == 2024 else 2024
    )
    fit_quarter = f"{year}Q1"
    history = _history_before(bundle, fit_quarter, parent_map)
    model, diagnostics = _fit_model(family, configuration, seed, x, y, history, task_config)
    checkpoint_path = phase_dir / "checkpoint.bin"
    _save_model(checkpoint_path, family, model, diagnostics)
    if family in {"graphsage_mean", "graphsage_none"} and not diagnostics["learning_gate_passed"]:
        _json_write(phase_dir / "failed_learning_gate.json", _public_diagnostics(diagnostics))
        raise RuntimeError(f"selected {family} refit{year}, seed{seed} fails the training-only learning gate")
    quarters = tuple(q for q in QUARTERS if q.startswith(str(year)))
    snapshots = {snapshot.quarter: snapshot for snapshot in bundle.snapshots}
    history = _history_before(bundle, quarters[0], parent_map)
    first = first_edges(bundle)
    quarterly: dict[str, Any] = {}
    for quarter in quarters:
        prediction_path = phase_dir / "predictions" / f"{quarter}.jsonl.gz"
        quarterly[quarter] = _evaluate_quarter(
            bundle,
            first,
            history,
            parent_map,
            quarter,
            FAMILY_METHODS[family],
            family,
            model,
            prediction_path,
        )
        history.add(snapshots[quarter], parent_map)
    _json_write(
        phase_dir / "result.json",
        {
            "family": family,
            "method": FAMILY_METHODS[family],
            "year": year,
            "seed": seed,
            "configuration": dict(configuration),
            "fit_cutoff": f"{year - 1}Q4",
            "fit_training_rows": int(len(y)),
            "quarters": quarterly,
            "annual_metrics": _aggregate_metrics(quarterly),
            "primary_micro_recall_at_10": _aggregate_primary(quarterly),
            "checkpoint": checkpoint_path.name,
            "diagnostics": _public_diagnostics(diagnostics),
        },
    )




def _run_phase(
    budget: Any,
    target: Any,
    args: tuple[Any, ...],
    phase_dir: Path,
    *,
    family: str | None = None,
) -> dict[str, Any]:
    phase_dir.parent.mkdir(parents=True, exist_ok=True)
    result = budget.execute(target, args, phase_dir, family=family)
    if not isinstance(result, dict) or result.get("status") != "complete":
        raise RuntimeError(f"Q2 phase did not complete successfully: {phase_dir}")
    if not (phase_dir / "result.json").exists() and target is not _prepare_worker:
        raise RuntimeError(f"Q2 phase did not write its result record: {phase_dir}")
    return result


def _phase_result(phase_dir: Path) -> dict[str, Any]:
    return _json_read(phase_dir / "result.json")


def _grid_for(task_config: Mapping[str, Any], family: str) -> list[dict[str, Any]]:
    if family == "graphsage_mean" or family == "graphsage_none":
        return [dict(config) for config in task_config["graph_configs"]]
    return [dict(config) for config in task_config["grids"][family]]


def _family_seeds(
    task_config: Mapping[str, Any], family: str, training_row_count: int
) -> tuple[int, ...]:
    if family in _LATENT_FAMILIES:
        return tuple(task_config["seeds"])
    if family == "boosted" and training_row_count > int(task_config["boosted_seed_threshold"]):
        return tuple(task_config["seeds"])
    return (0,)


def _phase_config_dir(root: Path, family: str, index: int) -> Path:
    return root / family / f"config{index + 1:02d}"




def _save_execution_records(output_dir: Path, records: Sequence[Mapping[str, Any]]) -> None:
    _json_write(output_dir / "execution_phases.json", list(records))


def _run_comparison(
    source_root: str | Path,
    output_dir: str | Path,
    protocol: str | Path,
    protocol_sha256: str,
    limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Run protocol-locked validation selection, then annual test refits/evaluation."""
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f"refusing to reuse Q2 MAUDE output directory {output}")
    output.mkdir(parents=True)
    resolved_limits = dict(DEFAULT_LIMITS)
    if limits is not None:
        resolved_limits.update({key: int(value) for key, value in limits.items()})
    for key in DEFAULT_LIMITS:
        if resolved_limits[key] < 1:
            raise ValueError(f"invalid Q2 resource limit {key}")
    started = time.monotonic()
    loaded_protocol = common.load_protocol(Path(protocol), protocol_sha256, output)
    protocol_json = _extract_protocol(loaded_protocol)
    task_config = _protocol_config(protocol_json)
    budget = common.RunBudget(output, resolved_limits)
    prepared_dir = output / "prepared"
    records: list[dict[str, Any]] = []
    records.append(
        {
            "phase": "prepare_raw_maude",
            "supervisor": _run_phase(
                budget,
                _prepare_worker,
                (str(Path(source_root)),),
                prepared_dir,
            ),
        }
    )
    prepared = _json_read(prepared_dir / "prepared.json")
    training_rows_by_year = {
        str(year): int(count)
        for year, count in prepared["training_rows_by_year"].items()
    }
    validation_training_rows = sum(
        training_rows_by_year[str(year)] for year in range(2019, 2023)
    )
    test_training_rows = {
        year: sum(training_rows_by_year[str(train_year)] for train_year in range(2019, year))
        for year in (2024, 2025)
    }
    _save_execution_records(output, records)
    family_results: dict[str, Any] = {}
    for family in FAMILY_METHODS:
        configurations = (
            _grid_for(task_config, family)
            if family not in {"global_popularity", "neighbor_frequency"}
            else []
        )
        if family in {"global_popularity", "neighbor_frequency"}:
            continue
        config_records: list[dict[str, Any]] = []
        for config_index, configuration in enumerate(configurations):
            by_seed: dict[str, Any] = {}
            for seed in _family_seeds(task_config, family, validation_training_rows):
                phase_dir = _phase_config_dir(output / "validation", family, config_index) / f"seed{seed:03d}"
                supervisor = _run_phase(
                    budget,
                    _fit_result_worker,
                    (
                        str(prepared_dir),
                        task_config,
                        family,
                        configuration,
                        seed,
                    ),
                    phase_dir,
                    family=family,
                )
                result = _phase_result(phase_dir)
                by_seed[str(seed)] = result
                records.append(
                    {
                        "phase": "validation",
                        "family": family,
                        "config_id": f"config{config_index + 1:02d}",
                        "seed": seed,
                        "supervisor": supervisor,
                    }
                )
                _save_execution_records(output, records)
            seed_values = [float(value["validation_micro_recall_at_10"]) for value in by_seed.values()]
            config_records.append(
                {
                    "config_id": f"config{config_index + 1:02d}",
                    "configuration": configuration,
                    "by_seed": by_seed,
                    "mean_validation_micro_recall_at_10": sum(seed_values) / len(seed_values),
                }
            )
        if len(config_records) != 6:
            raise RuntimeError(f"MAUDE {family} grid did not finish all six configurations")
        _json_write(output / "validation" / family / "grid.json", config_records)
        eligible = config_records
        if family in {"graphsage_mean", "graphsage_none"}:
            eligible = [
                row for row in config_records
                if all(
                    seed_result["diagnostics"]["learning_gate_passed"]
                    for seed_result in row["by_seed"].values()
                )
            ]
        if not eligible:
            raise RuntimeError(f"no {family} configuration passes the learning gate for every seed")
        best_score = max(float(row["mean_validation_micro_recall_at_10"]) for row in eligible)
        selected = next(
            row for row in eligible if float(row["mean_validation_micro_recall_at_10"]) == best_score
        )
        family_results[family] = {
            "method": FAMILY_METHODS[family],
            "selection_metric": "mean_validation_2023_micro_recall_at_10",
            "configurations": config_records,
            "selected_config_id": selected["config_id"],
            "selected_configuration": selected["configuration"],
            "selected_validation_score": best_score,
            "tie_break": "first configuration in published grid order",
        }
        if family in {"graphsage_mean", "graphsage_none"}:
            family_results[family]["learning_qualified_config_ids"] = [
                row["config_id"] for row in eligible
            ]
    heuristics_phase = output / "validation" / "heuristics" / "config01" / "seed000"
    heuristics_supervisor = _run_phase(
        budget,
        _heuristics_worker,
        (str(prepared_dir), True, 2023),
        heuristics_phase,
        family="heuristics",
    )
    heuristics_validation = _phase_result(heuristics_phase)
    records.append({"phase": "validation", "family": "heuristics", "supervisor": heuristics_supervisor})
    boosted_seed_policy = {
        "condition": "training_rows_gt_200000",
        "validation_training_rows": validation_training_rows,
        "validation_seeds": list(
            _family_seeds(task_config, "boosted", validation_training_rows)
        ),
        "test_refits": {
            str(year): {
                "training_rows": test_training_rows[year],
                "seeds": list(_family_seeds(task_config, "boosted", test_training_rows[year])),
            }
            for year in (2024, 2025)
        },
    }
    selection = {
        "record_kind": "Q2_MAUDE_VALIDATION_SELECTION",
        "status": "LOCKED",
        "selection_locked_before_test_scoring": True,
        "protocol_sha256": protocol_sha256,
        "source_root": str(Path(source_root)),
        "primary_metric": "micro_recall_at_10",
        "validation_quarters": [q for q in QUARTERS if q.startswith("2023")],
        "evidence_level": protocol_json["evidence_level"],
        "independent_evaluation": task_config["independent_evaluation"],
        "interpretation": (
            "Exploratory results on 2023-2025 periods previously consulted; "
            "not an independent confirmation."
        ),
        "boosted_seed_policy": boosted_seed_policy,
        "graphsage_capacity_equal_causal_claim": task_config["learning_gate"][
            "capacity_equal_causal_claim"
        ],
        "families": family_results,
        "heuristics": heuristics_validation["methods"],
        "graphsage_learning_gate_validation": {
            family: {
                "all_configuration_seed_gates_passed": all(
                    bool(seed_result["diagnostics"].get("learning_gate_passed", False))
                    for config in result["configurations"]
                    for seed_result in config["by_seed"].values()
                ),
                "per_configuration_seed_results": {
                    config["config_id"]: {
                        seed: seed_result["diagnostics"]
                        for seed, seed_result in config["by_seed"].items()
                    }
                    for config in result["configurations"]
                },
            }
            for family, result in family_results.items()
            if family in {"graphsage_mean", "graphsage_none"}
        },
    }
    _json_write(output / "selection.json", selection)
    _save_execution_records(output, records)
    if time.monotonic() - started > resolved_limits["run_wall_seconds"]:
        raise TimeoutError("Q2 MAUDE run exceeded its run wall budget before test scoring")
    test_results: dict[str, Any] = {"heuristics": {}}
    for year in (2024, 2025):
        phase_dir = output / "test" / "heuristics" / f"year{year}" / "seed000"
        supervisor = _run_phase(
            budget,
            _heuristics_worker,
            (str(prepared_dir), False, year),
            phase_dir,
        )
        result = _phase_result(phase_dir)
        test_results["heuristics"][str(year)] = result["methods"]
        records.append({"phase": "test", "family": "heuristics", "year": year, "supervisor": supervisor})
        _save_execution_records(output, records)
        for family, result in family_results.items():
            config = result["selected_configuration"]
            family_test: dict[str, Any] = {}
            for seed in _family_seeds(task_config, family, test_training_rows[year]):
                test_phase = output / "test" / family / f"year{year}" / f"seed{seed:03d}"
                phase_supervisor = _run_phase(
                    budget,
                    _test_worker,
                    (
                        str(prepared_dir),
                        task_config,
                        family,
                        config,
                        seed,
                        year,
                    ),
                    test_phase,
                )
                phase_result = _phase_result(test_phase)
                family_test[str(seed)] = phase_result
                records.append(
                    {
                        "phase": "test",
                        "family": family,
                        "year": year,
                        "seed": seed,
                        "supervisor": phase_supervisor,
                    }
                )
                _save_execution_records(output, records)
            test_results.setdefault(family, {})[str(year)] = family_test
        if time.monotonic() - started > resolved_limits["run_wall_seconds"]:
            raise TimeoutError("Q2 MAUDE run exceeded its run wall budget")
    result = {
        "record_kind": "Q2_MAUDE_COMPARISON",
        "status": "COMPLETE",
        "protocol_sha256": protocol_sha256,
        "protocol_metadata": loaded_protocol,
        "source_manifest": prepared["raw_sources"],
        "task_manifest": prepared["task_manifest"],
        "selection": selection,
        "test_results": test_results,
        "resource_limits": resolved_limits,
        "execution_phases": records,
    }
    _json_write(output / "result.json", result)
    return result


def run_comparison(
    source_root: str | Path,
    output_dir: str | Path,
    protocol: str | Path,
    protocol_sha256: str,
    limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Preserve controller errors without modifying any pre-existing output."""
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f"refusing to reuse Q2 MAUDE output directory {output}")
    try:
        return _run_comparison(source_root, output, protocol, protocol_sha256, limits)
    except BaseException as error:
        import traceback

        if output.is_dir():
            _json_write(
                output / "run_error.json",
                {"status": "incomplete", "type": type(error).__name__,
                 "message": str(error), "traceback": traceback.format_exc()},
            )
        raise


def _parse_limits(args: argparse.Namespace) -> dict[str, int]:
    return {
        "timeout_seconds": args.timeout_seconds,
        "max_rss_bytes": args.max_rss_bytes,
        "max_output_bytes": args.max_output_bytes,
        "family_validation_wall_seconds": args.family_validation_wall_seconds,
        "run_wall_seconds": args.run_wall_seconds,
        "total_output_bytes": args.total_output_bytes,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_LIMITS["timeout_seconds"])
    parser.add_argument("--max-rss-bytes", type=int, default=DEFAULT_LIMITS["max_rss_bytes"])
    parser.add_argument("--max-output-bytes", type=int, default=DEFAULT_LIMITS["max_output_bytes"])
    parser.add_argument(
        "--family-validation-wall-seconds",
        type=int,
        default=DEFAULT_LIMITS["family_validation_wall_seconds"],
    )
    parser.add_argument("--run-wall-seconds", type=int, default=DEFAULT_LIMITS["run_wall_seconds"])
    parser.add_argument("--total-output-bytes", type=int, default=DEFAULT_LIMITS["total_output_bytes"])
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run_comparison(
        args.source_root,
        args.output_dir,
        args.protocol,
        args.protocol_sha256,
        limits=_parse_limits(args),
    )
    sys.stdout.write(json.dumps(
        {"status": result["status"], "output_dir": str(args.output_dir),
         "selected": {
             family: {"configuration": record["selected_configuration"],
                      "validation_micro_recall_at_10": record["selected_validation_score"]}
             for family, record in result["selection"]["families"].items()
         }},
        ensure_ascii=False, allow_nan=False,
    ) + "\n")
    return 0
