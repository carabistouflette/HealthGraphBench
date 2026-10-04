"""Exploratory Part D Q2 comparisons over raw temporal source snapshots."""

from __future__ import annotations

import json
import math
import pickle
import time
import traceback
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..candidates.partd_model import (
    FEATURE_NAMES,
    _FeatureContext,
    _History,
    _feature_context,
    _overlap_scores,
    _specialty_scores,
    _training_rows,
)
from ..data import sha256_file
from ..tasks.partd.task import PartDHistoryView, PartDTask

from numba import njit as _njit


LOGISTIC_GRID: tuple[dict[str, Any], ...] = (
    {"C": 0.1, "class_weight": None},
    {"C": 1.0, "class_weight": None},
    {"C": 10.0, "class_weight": None},
    {"C": 0.1, "class_weight": "balanced"},
    {"C": 1.0, "class_weight": "balanced"},
    {"C": 10.0, "class_weight": "balanced"},
)
BPR_GRID: tuple[dict[str, Any], ...] = (
    {"dimension": 16, "learning_rate": 0.01, "regularization": 0.001, "negative_samples": 3},
    {"dimension": 16, "learning_rate": 0.03, "regularization": 0.001, "negative_samples": 3},
    {"dimension": 16, "learning_rate": 0.03, "regularization": 0.01, "negative_samples": 3},
    {"dimension": 32, "learning_rate": 0.01, "regularization": 0.001, "negative_samples": 3},
    {"dimension": 32, "learning_rate": 0.03, "regularization": 0.001, "negative_samples": 3},
    {"dimension": 32, "learning_rate": 0.03, "regularization": 0.001, "negative_samples": 5},
)
BOOSTED_GRID: tuple[dict[str, Any], ...] = (
    {"learning_rate": 0.03, "max_iter": 100, "max_leaf_nodes": 15, "l2_regularization": 0.0},
    {"learning_rate": 0.05, "max_iter": 100, "max_leaf_nodes": 15, "l2_regularization": 0.0},
    {"learning_rate": 0.1, "max_iter": 100, "max_leaf_nodes": 15, "l2_regularization": 0.0},
    {"learning_rate": 0.05, "max_iter": 200, "max_leaf_nodes": 15, "l2_regularization": 0.0},
    {"learning_rate": 0.05, "max_iter": 100, "max_leaf_nodes": 31, "l2_regularization": 0.0},
    {"learning_rate": 0.05, "max_iter": 100, "max_leaf_nodes": 15, "l2_regularization": 1.0},
)
Q2_SEEDS = [103, 211, 307]


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_rows(path: Path, rows: list[dict[str, Any]], *, family: str, config_index: int | None, seed: int | None) -> None:
    with path.open("a", encoding="utf-8", newline="") as handle:
        for row in rows:
            record = {
                "family": family,
                "configuration_index": config_index,
                "seed": seed,
                **row,
            }
            handle.write(_canonical_json(record) + "\n")


def _record_phase_error(phase_dir: Path, error: BaseException) -> None:
    try:
        _write_json(
            phase_dir / "error.json",
            {"error": repr(error), "traceback": traceback.format_exc()},
        )
    except OSError:
        pass


def _primary_metric(metrics: Mapping[str, Any]) -> float:
    value = metrics["positive_containing_provider_years"]["micro_recall_at_10"]
    if value is None or not math.isfinite(float(value)):
        raise ValueError("Part D validation has no finite micro-recall-at-10 value")
    return float(value)


def _select_configuration(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) != 6:
        raise ValueError(f"Part D selection requires all six grid configurations; got {len(records)}")
    scored = []
    for record in records:
        values = record.get("primary_validation_by_seed")
        if not isinstance(values, list) or not values:
            raise ValueError("Part D configuration is missing validation scores")
        score = sum(float(value) for value in values) / len(values)
        if not math.isfinite(score):
            raise ValueError("Part D validation selection score is non-finite")
        scored.append(score)
    best_index = max(range(len(scored)), key=scored.__getitem__)
    return {
        "configuration_index": best_index,
        "configuration": records[best_index]["configuration"],
        "mean_primary_validation": scored[best_index],
        "primary_validation_by_seed": records[best_index]["primary_validation_by_seed"],
        "validation_grid_scores": scored,
        "tie_break": "first configuration in published grid order on exact equality",
    }


def _validate_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    try:
        partd = protocol["tasks"]["partd"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Q2 protocol is missing tasks.partd") from exc
    if not isinstance(partd, dict):
        raise ValueError("Q2 protocol tasks.partd must be an object")
    if partd.get("name") != "partd_prescriber_drug":
        raise ValueError("Q2 Part D protocol has an incompatible task name")
    if partd.get("primary_metric") != "micro_recall_at_10":
        raise ValueError("Q2 Part D protocol must select on validation micro_recall_at_10")
    if partd.get("seeds") != Q2_SEEDS:
        raise ValueError(f"Q2 Part D protocol seeds must be exactly {Q2_SEEDS}")
    grids = partd.get("grids")
    expected = {
        "logistic": [dict(item) for item in LOGISTIC_GRID],
        "bpr": [dict(item) for item in BPR_GRID],
        "boosted": [dict(item) for item in BOOSTED_GRID],
    }
    if grids != expected:
        raise ValueError("Q2 Part D protocol grids differ from the approved ordered six-config grids")
    fixed = partd.get("fixed")
    if not isinstance(fixed, dict):
        raise ValueError("Q2 Part D protocol fixed settings are missing")
    if fixed.get("logistic") != {"solver": "lbfgs", "max_iter": 1000, "tol": 1e-8}:
        raise ValueError("Q2 logistic fixed settings must use lbfgs, max_iter=1000, tol=1e-8")
    if fixed.get("bpr") != {"epochs": 30, "specialty_weight": 0.35}:
        raise ValueError("Q2 BPR fixed settings must use 30 epochs and specialty_weight=0.35")
    if fixed.get("boosted") != {
        "early_stopping": False,
        "max_features": 1.0,
        "max_bins": 255,
        "min_samples_leaf": 20,
        "seed_repetition_condition": "training_rows_gt_200000",
    }:
        raise ValueError("Q2 boosted-tree fixed settings do not match the locked binning policy")
    cohort_size = partd.get("cohort_size")
    if isinstance(cohort_size, bool) or cohort_size != 2000:
        raise ValueError("Q2 Part D protocol cohort_size must remain 2000")
    if partd.get("validation_year") != 2023 or partd.get("test_years") != [2024]:
        raise ValueError("Q2 Part D protocol must use 2023 validation and 2024 test")
    if not isinstance(partd.get("source_manifest"), str) or not partd["source_manifest"]:
        raise ValueError("Q2 Part D protocol source_manifest is required")
    if partd.get("input_level", "raw") not in {"raw", "prepared"}:
        raise ValueError("Q2 Part D input_level must be raw or prepared")
    return partd


def _training_matrix(context: _FeatureContext) -> tuple[np.ndarray, np.ndarray]:
    samples = list(_training_rows(context, negative_ratio=5))
    if not samples:
        raise ValueError(f"Part D tabular fit has no sampled training rows for {context.target_year}")
    features = np.asarray([row for row, _ in samples], dtype=np.float64)
    labels = np.asarray([label for _, label in samples], dtype=np.int64)
    if len(np.unique(labels)) != 2:
        raise ValueError(f"Part D tabular fit requires both classes for {context.target_year}")
    return features, labels


def _training_row_count(task: PartDTask, year: int) -> int:
    history, _, _ = task._target_history(year)
    global_drug_count = len(history.drug_providers)
    total = 0
    for own_drugs in history.provider_drugs.values():
        positive_count = len(own_drugs)
        negative_count = min(global_drug_count - positive_count, 5 * positive_count)
        total += positive_count + negative_count
    return total


def _boosted_seeds(task: PartDTask, year: int) -> list[int | None]:
    if _training_row_count(task, year) > 200_000:
        return list(Q2_SEEDS)
    return [None]


def _weighted_log_loss(logits: np.ndarray, labels: np.ndarray, weights: np.ndarray) -> float:
    losses = np.logaddexp(0.0, logits) - labels * logits
    return float(np.average(losses, weights=weights))


def _fit_logistic(
    task: PartDTask,
    year: int,
    configuration: dict[str, Any],
    fixed: dict[str, Any],
    seed: int | None,
    checkpoint_dir: Path,
) -> tuple[Any, dict[str, Any]]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    if seed is not None:
        raise ValueError("Q2 logistic is deterministic and must not be pseudo-replicated by seed")
    history, _, _ = task._target_history(year)
    context = _feature_context(history, year)
    features, labels = _training_matrix(context)
    scaler = StandardScaler()
    normalized = scaler.fit_transform(features)
    class_weight = configuration["class_weight"]
    weights = (
        np.where(labels == 1, len(labels) / (2 * np.count_nonzero(labels == 1)),
                 len(labels) / (2 * np.count_nonzero(labels == 0)))
        if class_weight == "balanced"
        else np.ones(labels.shape[0], dtype=np.float64)
    )
    classifier = LogisticRegression(
        C=float(configuration["C"]),
        class_weight=class_weight,
        solver=fixed["solver"],
        max_iter=int(fixed["max_iter"]),
        tol=float(fixed["tol"]),
    )
    before_loss = _weighted_log_loss(np.zeros(labels.shape[0]), labels, weights)
    classifier.fit(normalized, labels)
    after_loss = _weighted_log_loss(classifier.decision_function(normalized), labels, weights)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoint_dir / "checkpoint.npz"
    np.savez_compressed(
        checkpoint,
        feature_names=np.asarray(FEATURE_NAMES, dtype=np.str_),
        scaler_mean=scaler.mean_,
        scaler_scale=scaler.scale_,
        coefficients=classifier.coef_,
        intercept=classifier.intercept_,
        classes=classifier.classes_,
    )
    classifier_summary = {
        "n_iter": [int(value) for value in classifier.n_iter_],
        "training_rows": int(labels.shape[0]),
        "positive_training_rows": int(np.count_nonzero(labels == 1)),
        "negative_training_rows": int(np.count_nonzero(labels == 0)),
        "negative_sampling_ratio": 5,
        "class_weight": class_weight,
        "class_weight_effect": (
            "inverse observed class frequencies, each class contributes equal total weight"
            if class_weight == "balanced"
            else "unit sample weights"
        ),
        "loss_before": {
            "name": "weighted logistic loss on the sampled training rows, no L2 term",
            "value": before_loss,
        },
        "loss_after": {
            "name": "weighted logistic loss on the same sampled training rows, no L2 term",
            "value": after_loss,
        },
        "scaler_fit_on": "sampled training rows only",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
    }

    def score(view: PartDHistoryView, npi: str, candidates: tuple[str, ...]) -> Mapping[str, float]:
        if view.target_year != year:
            raise ValueError("logistic checkpoint used at a different temporal cutoff")
        if not candidates:
            return {}
        matrix = np.asarray([context.features(npi, drug) for drug in candidates], dtype=np.float64)
        probability = classifier.predict_proba(scaler.transform(matrix))[:, 1]
        return {drug: float(probability[index]) for index, drug in enumerate(candidates)}

    return score, classifier_summary


def _fit_boosted(
    task: PartDTask,
    year: int,
    configuration: dict[str, Any],
    fixed: dict[str, Any],
    seed: int | None,
    checkpoint_dir: Path,
) -> tuple[Any, dict[str, Any]]:
    from sklearn.ensemble import HistGradientBoostingClassifier

    history, _, _ = task._target_history(year)
    context = _feature_context(history, year)
    features, labels = _training_matrix(context)
    stochastic_binning = labels.shape[0] > 200_000
    if stochastic_binning and seed not in Q2_SEEDS:
        raise ValueError("HistGradientBoosting requires each published seed above 200000 training rows")
    if not stochastic_binning and seed is not None:
        raise ValueError("HistGradientBoosting must not use pseudo-replicate seeds at or below 200000 rows")
    weights = np.ones(labels.shape[0], dtype=np.float64)
    classifier = HistGradientBoostingClassifier(
        learning_rate=float(configuration["learning_rate"]),
        max_iter=int(configuration["max_iter"]),
        max_leaf_nodes=int(configuration["max_leaf_nodes"]),
        l2_regularization=float(configuration["l2_regularization"]),
        early_stopping=bool(fixed["early_stopping"]),
        max_features=float(fixed["max_features"]),
        max_bins=int(fixed["max_bins"]),
        min_samples_leaf=int(fixed["min_samples_leaf"]),
        random_state=int(seed) if seed is not None else 0,
    )
    before_loss = _weighted_log_loss(np.zeros(labels.shape[0]), labels, weights)
    classifier.fit(features, labels)
    probabilities = np.clip(classifier.predict_proba(features)[:, 1], 1e-15, 1 - 1e-15)
    after_loss = float(
        np.average(
            -labels * np.log(probabilities) - (1 - labels) * np.log1p(-probabilities),
            weights=weights,
        )
    )
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoint_dir / "checkpoint.pkl"
    with checkpoint.open("wb") as handle:
        pickle.dump(classifier, handle, protocol=pickle.HIGHEST_PROTOCOL)
    import sklearn

    summary = {
        "training_rows": int(labels.shape[0]),
        "positive_training_rows": int(np.count_nonzero(labels == 1)),
        "negative_training_rows": int(np.count_nonzero(labels == 0)),
        "negative_sampling_ratio": 5,
        "sample_weight_policy": "unit weights; no class reweighting",
        "early_stopping": False,
        "max_features": float(fixed["max_features"]),
        "max_bins": int(fixed["max_bins"]),
        "min_samples_leaf": int(fixed["min_samples_leaf"]),
        "binning_subsample_threshold": 200_000,
        "stochastic_binning": stochastic_binning,
        "seed_repetition_condition": "three seeds only when training_rows > 200000",
        "seed": int(seed) if seed is not None else None,
        "random_state": int(seed) if seed is not None else 0,
        "fit_iterations": int(classifier.n_iter_),
        "loss_before": {
            "name": "unweighted logistic loss on the sampled training rows",
            "value": before_loss,
        },
        "loss_after": {
            "name": "unweighted logistic loss on the same sampled training rows",
            "value": after_loss,
        },
        "sklearn_version": sklearn.__version__,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
    }

    def score(view: PartDHistoryView, npi: str, candidates: tuple[str, ...]) -> Mapping[str, float]:
        if view.target_year != year:
            raise ValueError("boosted-tree checkpoint used at a different temporal cutoff")
        if not candidates:
            return {}
        matrix = np.asarray([context.features(npi, drug) for drug in candidates], dtype=np.float64)
        probability = classifier.predict_proba(matrix)[:, 1]
        return {drug: float(probability[index]) for index, drug in enumerate(candidates)}

    return score, summary


def _bpr_kernel_impl(
    provider_embeddings: np.ndarray,
    drug_embeddings: np.ndarray,
    specialty_embeddings: np.ndarray,
    pair_providers: np.ndarray,
    pair_positives: np.ndarray,
    negative_offsets: np.ndarray,
    negative_pool: np.ndarray,
    specialty_by_provider: np.ndarray,
    epochs: int,
    negative_samples: int,
    learning_rate: float,
    regularization: float,
    specialty_weight: float,
    seed: int,
) -> int:
    np.random.seed(seed)
    update_count = 0
    dimension = provider_embeddings.shape[1]
    for _ in range(epochs):
        for pair_index in range(pair_providers.shape[0]):
            provider = pair_providers[pair_index]
            positive = pair_positives[pair_index]
            start = negative_offsets[provider]
            count = negative_offsets[provider + 1] - start
            if count == 0:
                continue
            specialty = specialty_by_provider[provider]
            for _ in range(negative_samples):
                negative = negative_pool[start + np.random.randint(count)]
                positive_score = 0.0
                negative_score = 0.0
                for feature in range(dimension):
                    user_value = provider_embeddings[provider, feature]
                    positive_value = drug_embeddings[positive, feature]
                    negative_value = drug_embeddings[negative, feature]
                    positive_score += user_value * positive_value
                    negative_score += user_value * negative_value
                    if specialty >= 0:
                        specialty_value = specialty_embeddings[specialty, feature]
                        positive_score += specialty_weight * specialty_value * positive_value
                        negative_score += specialty_weight * specialty_value * negative_value
                difference = positive_score - negative_score
                if difference >= 0.0:
                    exp_value = np.exp(-difference)
                    coefficient = exp_value / (1.0 + exp_value)
                else:
                    coefficient = 1.0 / (1.0 + np.exp(difference))
                for feature in range(dimension):
                    user_value = provider_embeddings[provider, feature]
                    positive_value = drug_embeddings[positive, feature]
                    negative_value = drug_embeddings[negative, feature]
                    specialty_value = (
                        specialty_embeddings[specialty, feature] if specialty >= 0 else 0.0
                    )
                    direction = positive_value - negative_value
                    shared = user_value + specialty_weight * specialty_value
                    provider_embeddings[provider, feature] = user_value + learning_rate * (
                        coefficient * direction - regularization * user_value
                    )
                    drug_embeddings[positive, feature] = positive_value + learning_rate * (
                        coefficient * shared - regularization * positive_value
                    )
                    drug_embeddings[negative, feature] = negative_value + learning_rate * (
                        -coefficient * shared - regularization * negative_value
                    )
                    if specialty >= 0:
                        specialty_embeddings[specialty, feature] = specialty_value + learning_rate * (
                            coefficient * specialty_weight * direction
                            - regularization * specialty_value
                        )
                update_count += 1
    return update_count


_BPR_KERNEL = _njit(_bpr_kernel_impl)


def _bpr_score(
    provider_index: int,
    drug_index: int,
    specialty_index: int,
    provider_embeddings: np.ndarray,
    drug_embeddings: np.ndarray,
    specialty_embeddings: np.ndarray,
    specialty_weight: float,
) -> float:
    score = float(np.dot(provider_embeddings[provider_index], drug_embeddings[drug_index]))
    if specialty_index >= 0:
        score += specialty_weight * float(
            np.dot(specialty_embeddings[specialty_index], drug_embeddings[drug_index])
        )
    return score


def _bpr_diagnostics(
    pairs_provider: np.ndarray,
    pairs_positive: np.ndarray,
    pairs_negative: np.ndarray,
    pairs_specialty: np.ndarray,
    provider_embeddings: np.ndarray,
    drug_embeddings: np.ndarray,
    specialty_embeddings: np.ndarray,
    specialty_weight: float,
    regularization: float,
) -> dict[str, float]:
    if not pairs_provider.size:
        raise ValueError("Part D BPR history has no positive/negative training pairs")
    pair_losses = np.empty(pairs_provider.size, dtype=np.float64)
    penalties = np.empty(pairs_provider.size, dtype=np.float64)
    for index, provider in enumerate(pairs_provider):
        positive = int(pairs_positive[index])
        negative = int(pairs_negative[index])
        specialty = int(pairs_specialty[index])
        positive_score = _bpr_score(
            int(provider), positive, specialty,
            provider_embeddings, drug_embeddings, specialty_embeddings, specialty_weight,
        )
        negative_score = _bpr_score(
            int(provider), negative, specialty,
            provider_embeddings, drug_embeddings, specialty_embeddings, specialty_weight,
        )
        pair_losses[index] = np.logaddexp(0.0, -(positive_score - negative_score))
        penalty = float(np.dot(provider_embeddings[provider], provider_embeddings[provider]))
        penalty += float(np.dot(drug_embeddings[positive], drug_embeddings[positive]))
        penalty += float(np.dot(drug_embeddings[negative], drug_embeddings[negative]))
        if specialty >= 0:
            penalty += float(np.dot(specialty_embeddings[specialty], specialty_embeddings[specialty]))
        penalties[index] = 0.5 * regularization * penalty
    pairwise = float(np.mean(pair_losses))
    l2_penalty = float(np.mean(penalties))
    return {
        "sampled_pairwise_logistic_loss": pairwise,
        "sampled_l2_penalty": l2_penalty,
        "sampled_objective": pairwise + l2_penalty,
    }


def _fit_bpr(
    task: PartDTask,
    year: int,
    configuration: dict[str, Any],
    fixed: dict[str, Any],
    seed: int | None,
    checkpoint_dir: Path,
) -> tuple[Any, dict[str, Any]]:
    if seed is None:
        raise ValueError("Q2 BPR requires each published stochastic seed")
    history, _, _ = task._target_history(year)
    providers = tuple(sorted(history.provider_drugs))
    drugs = tuple(sorted(history.drug_providers))
    specialties = tuple(sorted({
        value for provider in providers
        if (value := history.latest_specialty(provider)) is not None
    }))
    if not providers or not drugs:
        raise ValueError(f"Part D BPR history graph is empty for target {year}")
    provider_index = {value: index for index, value in enumerate(providers)}
    drug_index = {value: index for index, value in enumerate(drugs)}
    specialty_index = {value: index for index, value in enumerate(specialties)}
    provider_drug_sets = history.provider_drugs
    negative_lists = [
        [drug_index[drug] for drug in drugs if drug not in provider_drug_sets[provider]]
        for provider in providers
    ]
    negative_offsets = np.zeros(len(providers) + 1, dtype=np.int64)
    for index, values in enumerate(negative_lists):
        negative_offsets[index + 1] = negative_offsets[index] + len(values)
    negative_pool = np.asarray(
        [index for values in negative_lists for index in values], dtype=np.int64
    )
    pair_providers: list[int] = []
    pair_positives: list[int] = []
    for provider in providers:
        for drug in sorted(provider_drug_sets[provider]):
            pair_providers.append(provider_index[provider])
            pair_positives.append(drug_index[drug])
    if not pair_providers:
        raise ValueError(f"Part D BPR has no observed edges for target {year}")
    specialty_by_provider = np.asarray(
        [specialty_index.get(history.latest_specialty(provider), -1) for provider in providers],
        dtype=np.int64,
    )
    dimension = int(configuration["dimension"])
    rng = np.random.default_rng(seed)
    scale = 1.0 / math.sqrt(dimension)
    provider_embeddings = rng.normal(0.0, scale, (len(providers), dimension)).astype(np.float64)
    drug_embeddings = rng.normal(0.0, scale, (len(drugs), dimension)).astype(np.float64)
    specialty_embeddings = rng.normal(0.0, scale, (len(specialties), dimension)).astype(np.float64)

    diagnostic_rng = np.random.default_rng(seed ^ 0x5A17)
    diagnostic_providers: list[int] = []
    diagnostic_positives: list[int] = []
    diagnostic_negatives: list[int] = []
    diagnostic_specialties: list[int] = []
    for provider, positive in zip(pair_providers, pair_positives, strict=True):
        low = int(negative_offsets[provider])
        size = int(negative_offsets[provider + 1] - low)
        if not size:
            continue
        for _ in range(int(configuration["negative_samples"])):
            diagnostic_providers.append(provider)
            diagnostic_positives.append(positive)
            diagnostic_negatives.append(int(negative_pool[low + diagnostic_rng.integers(size)]))
            diagnostic_specialties.append(int(specialty_by_provider[provider]))
    diagnostic_arrays = (
        np.asarray(diagnostic_providers, dtype=np.int64),
        np.asarray(diagnostic_positives, dtype=np.int64),
        np.asarray(diagnostic_negatives, dtype=np.int64),
        np.asarray(diagnostic_specialties, dtype=np.int64),
    )
    if not diagnostic_arrays[0].size:
        raise ValueError(f"Part D BPR has no negative samples for target {year}")
    specialty_weight = float(fixed["specialty_weight"])
    regularization = float(configuration["regularization"])
    loss_before = _bpr_diagnostics(
        *diagnostic_arrays,
        provider_embeddings,
        drug_embeddings,
        specialty_embeddings,
        specialty_weight,
        regularization,
    )
    update_count = int(
        _BPR_KERNEL(
            provider_embeddings,
            drug_embeddings,
            specialty_embeddings,
            np.asarray(pair_providers, dtype=np.int64),
            np.asarray(pair_positives, dtype=np.int64),
            negative_offsets,
            negative_pool,
            specialty_by_provider,
            int(fixed["epochs"]),
            int(configuration["negative_samples"]),
            float(configuration["learning_rate"]),
            regularization,
            specialty_weight,
            int(seed),
        )
    )
    loss_after = _bpr_diagnostics(
        *diagnostic_arrays,
        provider_embeddings,
        drug_embeddings,
        specialty_embeddings,
        specialty_weight,
        regularization,
    )
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoint_dir / "checkpoint.npz"
    np.savez_compressed(
        checkpoint,
        providers=np.asarray(providers, dtype=np.str_),
        drugs=np.asarray(drugs, dtype=np.str_),
        specialties=np.asarray(specialties, dtype=np.str_),
        provider_embeddings=provider_embeddings,
        drug_embeddings=drug_embeddings,
        specialty_embeddings=specialty_embeddings,
    )
    summary = {
        "objective": "sampled Bayesian personalized ranking logistic loss plus sampled L2 penalty",
        "initialization": "seeded Gaussian embeddings with standard deviation 1/sqrt(dimension)",
        "negative_sampling": "uniform with replacement from each provider's all-history global-drug complement, training only",
        "dimension": dimension,
        "epochs": int(fixed["epochs"]),
        "learning_rate": float(configuration["learning_rate"]),
        "regularization": regularization,
        "negative_samples_per_positive": int(configuration["negative_samples"]),
        "specialty_weight": specialty_weight,
        "seed": int(seed),
        "provider_nodes": len(providers),
        "drug_nodes": len(drugs),
        "specialty_nodes": len(specialties),
        "observed_provider_drug_edges": len(pair_providers),
        "parameter_updates": update_count,
        "loss_before": loss_before,
        "loss_after": loss_after,
        "diagnostic_sample_pair_count": int(diagnostic_arrays[0].size),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "compiled_with_numba": True,
    }

    def score(view: PartDHistoryView, npi: str, candidates: tuple[str, ...]) -> Mapping[str, float]:
        if view.target_year != year:
            raise ValueError("BPR checkpoint used at a different temporal cutoff")
        provider_id = provider_index.get(npi)
        provider_specialty = history.latest_specialty(npi)
        specialty_id = specialty_index.get(provider_specialty, -1)
        result: dict[str, float] = {}
        for drug in candidates:
            drug_id = drug_index[drug]
            if provider_id is None:
                result[drug] = 0.0
            else:
                result[drug] = _bpr_score(
                    provider_id,
                    drug_id,
                    specialty_id,
                    provider_embeddings,
                    drug_embeddings,
                    specialty_embeddings,
                    specialty_weight,
                )
        return result

    return score, summary


def _save_all_candidate_scores(
    task: PartDTask,
    year: int,
    rows: list[dict[str, Any]],
    path: Path,
) -> dict[str, Any]:
    split = "validation" if year == 2023 else "test"
    history_view = task.history_view(split)
    drug_ids = history_view.drugs
    drug_index = {drug: index for index, drug in enumerate(drug_ids)}
    candidate_offsets = np.zeros(len(rows) + 1, dtype=np.int64)
    candidate_indices: list[int] = []
    scores: list[float] = []
    for row_index, row in enumerate(rows):
        row_scores = row["candidate_scores"]
        for drug in sorted(row_scores):
            candidate_indices.append(drug_index[drug])
            scores.append(float(row_scores[drug]))
        candidate_offsets[row_index + 1] = len(candidate_indices)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        provider_ids=np.asarray([row["npi"] for row in rows], dtype=np.str_),
        drug_ids=np.asarray(drug_ids, dtype=np.str_),
        drug_global_support=np.asarray(
            [history_view.global_support(drug) for drug in drug_ids],
            dtype=np.int64,
        ),
        provider_candidate_offsets=candidate_offsets,
        candidate_drug_indices=np.asarray(candidate_indices, dtype=np.int64),
        candidate_scores=np.asarray(scores, dtype=np.float64),
    )
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "provider_count": len(rows),
        "global_prior_drug_count": len(drug_ids),
        "candidate_score_count": len(scores),
        "candidate_set_encoding": (
            "provider_candidate_offsets and candidate_drug_indices index drug_ids; "
            "candidate_scores aligns one-for-one and is the exact inference score"
        ),
        "tie_support_vector": "drug_global_support, aligned with drug_ids",
    }


def _run_fit_phase(
    task: PartDTask,
    stage: str,
    family: str,
    configuration: dict[str, Any] | None,
    seed: int | None,
    fixed: dict[str, Any],
    phase_dir: Path,
) -> dict[str, Any]:
    phase_dir = Path(phase_dir)
    phase_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        year = 2023 if stage == "validation" else 2024
        if family in {"specialty_popularity", "history_overlap"}:
            if configuration is not None or seed is not None:
                raise ValueError("deterministic Part D baselines do not accept tuned configurations or seeds")
            scorer = task._builtin_scorer(family)
            fit_summary = {"fit": "none; deterministic history-only baseline"}
        else:
            if configuration is None:
                raise ValueError("a tuned Part D model phase requires a configuration")
            if family == "logistic":
                scorer, fit_summary = _fit_logistic(
                    task, year, configuration, fixed["logistic"], seed, phase_dir / "model"
                )
            elif family == "bpr":
                scorer, fit_summary = _fit_bpr(
                    task, year, configuration, fixed["bpr"], seed, phase_dir / "model"
                )
            elif family == "boosted":
                scorer, fit_summary = _fit_boosted(
                    task, year, configuration, fixed["boosted"], seed, phase_dir / "model"
                )
            else:
                raise ValueError(f"unknown Part D Q2 family {family!r}")
        rows = task._rank_target(year, scorer, retain_candidate_scores=True)
        metrics = task._metrics(rows)
        candidate_score_file = phase_dir / "all_candidate_scores.npz"
        candidate_score_summary = _save_all_candidate_scores(
            task, year, rows, candidate_score_file
        )
        for row in rows:
            row.pop("candidate_scores")
        prediction_file = phase_dir / "predictions.jsonl"
        _write_rows(prediction_file, rows, family=family, config_index=None, seed=seed)
        result = {
            "stage": stage,
            "target_year": year,
            "family": family,
            "configuration": configuration,
            "seed": seed,
            "fit": fit_summary,
            "metrics": metrics,
            "primary_metric": _primary_metric(metrics),
            "target_provider_years": len(rows),
            "eligible_provider_years": sum(bool(row["eligible"]) for row in rows),
            "evaluated_candidate_total": sum(int(row["candidate_count"]) for row in rows),
            "positive_total": sum(int(row["positive_count"]) for row in rows),
            "candidate_score_table": candidate_score_summary,
            "prediction_file": str(prediction_file),
            "prediction_file_sha256": sha256_file(prediction_file),
            "wall_seconds": time.perf_counter() - started,
        }
        return result
    except BaseException as exc:
        _record_phase_error(phase_dir, exc)
        raise


def _prepare_raw_worker(
    source_root: str,
    manifest_path: str,
    cohort_size: int,
    phase_dir: Path,
) -> dict[str, Any]:
    from ..candidates.partd import prepare_execution

    phase_dir = Path(phase_dir)
    prepared_dir = phase_dir / "prepared"
    report = prepare_execution(
        Path(source_root),
        Path(manifest_path),
        prepared_dir,
        cohort_size=cohort_size,
    )
    return {
        "prepared_dir": str(prepared_dir),
        "record_kind": report["record_kind"],
        "manifest_sha256": report["sources"]["manifest_sha256"],
        "edges_sha256": report["artifact_hashes"]["edges.csv"],
        "retained_edges": report["audits"]["total_retained_edges"],
    }


def _execute_fit_phase(
    task: PartDTask,
    stage: str,
    family: str,
    configuration: dict[str, Any] | None,
    seed: int | None,
    fixed: dict[str, Any],
    phase_dir: Path,
    budget: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    phase_dir.parent.mkdir(parents=True, exist_ok=True)
    supervision = budget.execute(
        _run_fit_phase,
        (task, stage, family, configuration, seed, fixed),
        phase_dir,
        family=family if stage == "validation" else None,
    )
    if not isinstance(supervision, dict) or supervision.get("status") != "complete":
        raise RuntimeError(
            f"Part D fit phase did not complete: family={family}, stage={stage}, seed={seed!r}"
        )
    result_path = phase_dir / "result.json"
    if not result_path.is_file():
        raise RuntimeError(f"Part D phase did not write result.json: {phase_dir}")
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Part D phase result {result_path}: {exc}") from exc
    return result, supervision

def _run_comparison_loaded(
    source_root: Path,
    output_dir: Path,
    protocol: dict[str, Any],
    protocol_sha256: str,
    limits: Mapping[str, int] | None = None,
    prepared_input: Path | None = None,
) -> dict[str, Any]:
    from . import common

    partd_protocol = _validate_protocol(protocol)
    output_dir = Path(output_dir)
    source_root = Path(source_root)
    protocol_limits = protocol.get("limits")
    if not isinstance(protocol_limits, dict) or set(protocol_limits) != set(common.DEFAULT_LIMITS):
        raise ValueError("Q2 Part D execution requires the complete locked protocol limits")
    resolved_limits = dict(common.DEFAULT_LIMITS)
    resolved_limits.update({key: int(value) for key, value in protocol_limits.items()})
    if limits is not None:
        resolved_limits.update({key: int(value) for key, value in limits.items()})
    budget = common.RunBudget(output_dir, resolved_limits)
    started = time.monotonic()
    fixed = partd_protocol["fixed"]
    input_level = partd_protocol.get("input_level", "raw")
    if input_level == "prepared":
        if prepared_input is None:
            raise ValueError("prepared Part D comparison requires prepared_input and input_level='prepared'")
        task = PartDTask.from_prepared_input(prepared_input, allow_feasibility=True)
    else:
        if prepared_input is not None:
            raise ValueError("prepared_input requires protocol input_level='prepared'")
        manifest_value = Path(partd_protocol["source_manifest"])
        if not manifest_value.is_absolute():
            manifest_value = common.REPO_ROOT / manifest_value
        preparation_phase = output_dir / "phases" / "prepare_raw"
        preparation_phase.parent.mkdir(parents=True, exist_ok=True)
        budget.execute(
            _prepare_raw_worker,
            (
                str(source_root),
                str(manifest_value),
                int(partd_protocol["cohort_size"]),
            ),
            preparation_phase,
        )
        task = PartDTask.from_prepared_input(preparation_phase / "prepared")

    validation_families: dict[str, Any] = {}
    for family in ("specialty_popularity", "history_overlap"):
        phase_dir = output_dir / "phases" / "validation" / family
        result, _ = _execute_fit_phase(
            task, "validation", family, None, None, fixed, phase_dir, budget
        )
        validation_families[family] = result

    grids = partd_protocol["grids"]
    validation_boosted_seeds = _boosted_seeds(task, 2023)
    grid_families = (
        ("logistic", grids["logistic"], [None]),
        ("bpr", grids["bpr"], Q2_SEEDS),
        ("boosted", grids["boosted"], validation_boosted_seeds),
    )
    validation_grids: dict[str, list[dict[str, Any]]] = {}
    selected: dict[str, dict[str, Any]] = {}
    for family, grid, seeds in grid_families:
        records: list[dict[str, Any]] = []
        for configuration_index, configuration in enumerate(grid):
            replicate_results: list[dict[str, Any]] = []
            for seed in seeds:
                phase_dir = (
                    output_dir
                    / "phases"
                    / "validation"
                    / family
                    / f"config-{configuration_index:02d}"
                    / (f"seed-{seed}" if seed is not None else "deterministic")
                )
                result, _ = _execute_fit_phase(
                    task,
                    "validation",
                    family,
                    dict(configuration),
                    seed,
                    fixed,
                    phase_dir,
                    budget,
                )
                replicate_results.append(result)
            records.append(
                {
                    "configuration_index": configuration_index,
                    "configuration": dict(configuration),
                    "replicate_seeds": list(seeds) if seeds != [None] else [],
                    "primary_validation_by_seed": [
                        result["primary_metric"] for result in replicate_results
                    ],
                    "replicates": replicate_results,
                }
            )
        validation_grids[family] = records
        selected[family] = _select_configuration(records)

    selection = {
        "criterion": "mean validation micro_recall_at_10 across protocol-required stochastic seeds; one fit for deterministic configurations",
        "validation_year": 2023,
        "test_year": 2024,
        "bpr_stochastic_seeds": Q2_SEEDS,
        "boosted_training_rows": _training_row_count(task, 2023),
        "boosted_seed_repetition_threshold": 200_000,
        "boosted_validation_seeds": [
            seed for seed in validation_boosted_seeds if seed is not None
        ],
        "seeds_are_not_selected": True,
        "grid_order_is_tie_break": True,
        "families": selected,
    }
    _write_json(output_dir / "selection.json", selection)
    test_grid_families = (
        ("logistic", grids["logistic"], [None]),
        ("bpr", grids["bpr"], Q2_SEEDS),
        ("boosted", grids["boosted"], _boosted_seeds(task, 2024)),
    )

    test_families: dict[str, Any] = {}
    for family in ("specialty_popularity", "history_overlap"):
        phase_dir = output_dir / "phases" / "test" / family
        result, _ = _execute_fit_phase(task, "test", family, None, None, fixed, phase_dir, budget)
        test_families[family] = result
    for family, _, seeds in test_grid_families:
        configuration_index = selected[family]["configuration_index"]
        configuration = dict(selected[family]["configuration"])
        replicate_results = []
        for seed in seeds:
            phase_dir = (
                output_dir
                / "phases"
                / "test"
                / family
                / f"config-{configuration_index:02d}"
                / (f"seed-{seed}" if seed is not None else "deterministic")
            )
            result, _ = _execute_fit_phase(
                task,
                "test",
                family,
                configuration,
                seed,
                fixed,
                phase_dir,
                budget,
            )
            replicate_results.append(result)
        test_families[family] = {
            "configuration_index": configuration_index,
            "configuration": configuration,
            "replicate_seeds": list(seeds) if seeds != [None] else [],
            "replicates": replicate_results,
            "mean_primary_test": sum(item["primary_metric"] for item in replicate_results)
            / len(replicate_results),
        }

    output_bytes = sum(path.stat().st_size for path in output_dir.rglob("*") if path.is_file())
    total_output_limit = int(budget.limits["total_output_bytes"])
    if output_bytes > total_output_limit:
        raise ValueError(
            f"Part D comparison outputs exceed total_output_bytes: {output_bytes} > {total_output_limit}"
        )
    report = {
        "record_kind": "partd_q2_comparison",
        "status": "complete",
        "task": "partd_prescriber_drug",
        "input_level": input_level,
        "source_root": str(source_root),
        "prepared_input": str(prepared_input) if prepared_input is not None else str(task.prepared_dir),
        "source_manifest": partd_protocol["source_manifest"],
        "source_manifest_sha256": task.report.get("sources", {}).get("manifest_sha256"),
        "prepared_report_sha256": sha256_file(task.prepared_dir / "report.json"),
        "prepared_edges_sha256": sha256_file(task.prepared_dir / "edges.csv"),
        "protocol_sha256": protocol_sha256,
        "selection": selection,
        "validation_baselines": validation_families,
        "validation_grids": validation_grids,
        "test": test_families,
        "resources": {
            "run_wall_seconds": time.monotonic() - started,
            "supervised_phase_wall_seconds": sum(
                float(item["wall_seconds"]) for item in budget.phases
            ),
            "validation_family_wall_seconds": dict(budget.family_seconds),
            "output_bytes": output_bytes,
            "limits": budget.limits,
            "phases": budget.phases,
        },
        "evaluation": {
            "validation_metric": "micro_recall_at_10",
            "test_scored_after_selection_written": True,
            "evaluation_candidate_sampling": False,
            "target_provider_years_include_zero_positive_rows": True,
            "positive_recall_denominator": "all observable eligible target positives",
            "all_candidate_total_recorded_per_target_provider_year": True,
        },
    }
    _write_json(output_dir / "comparison.json", report)
    return report


def run_comparison(
    source_root: Path,
    output_dir: Path,
    protocol: Path,
    protocol_sha256: str,
    limits: Mapping[str, int] | None = None,
    prepared_input: Path | None = None,
) -> dict[str, Any]:
    """Run the locked Part D comparison, supervising preparation and every fit."""
    from . import common

    source_root = Path(source_root)
    output_dir = Path(output_dir)
    protocol = Path(protocol)
    if output_dir.exists():
        raise FileExistsError(f"refusing to reuse Q2 Part D output directory: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()
    loaded_protocol = common.load_protocol(protocol, protocol_sha256, output_dir)
    return _run_comparison_loaded(
        source_root,
        output_dir,
        loaded_protocol,
        protocol_sha256,
        limits=limits,
        prepared_input=prepared_input,
    )
__all__ = ["run_comparison", "LOGISTIC_GRID", "BPR_GRID", "BOOSTED_GRID"]




