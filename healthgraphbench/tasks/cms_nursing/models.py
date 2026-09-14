"""Dependency-light frozen CMS models and ranking metrics."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

BASE_FEATURE_NAMES = (
    "log_prior_inspections",
    "log_prior_serious",
    "prior_serious_rate",
    "log_recent365_inspections",
    "log_recent365_serious",
    "log_recent730_inspections",
    "log_recent730_serious",
    "days_since_last_years",
    "facility_age_years",
    "log_chow_prior",
    "log_chow_recent365",
)
GRAPH_FEATURE_NAMES = (
    "log_owner_count",
    "log_peer_count",
    "log_peer_prior_facilities",
    "log_peer_prior_inspections",
    "log_peer_prior_serious",
    "peer_prior_serious_rate",
    "log_peer_recent365_inspections",
    "log_peer_recent365_serious",
    "peer_recent365_serious_rate",
    "log_peer_recent730_serious",
    "peer_any_serious365_count",
    "peer_any_serious730_count",
)


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def row_numeric(row: Mapping[str, Any], graph: bool, state_values: Sequence[str]) -> list[float]:
    values = [
        math.log1p(row["prior_inspections"]),
        math.log1p(row["prior_serious"]),
        row["prior_serious_rate"],
        math.log1p(row["recent365_inspections"]),
        math.log1p(row["recent365_serious"]),
        math.log1p(row["recent730_inspections"]),
        math.log1p(row["recent730_serious"]),
        min(row["days_since_last"], 1460) / 365.25,
        min(row["age_years"], 100.0),
        math.log1p(row["chow_prior"]),
        math.log1p(row["chow_recent365"]),
    ]
    if graph:
        values.extend(
            [
                math.log1p(row["owner_count"]),
                math.log1p(row["peer_count"]),
                math.log1p(row["peer_prior_facilities"]),
                math.log1p(row["peer_prior_inspections"]),
                math.log1p(row["peer_prior_serious"]),
                row["peer_prior_serious"] / row["peer_prior_inspections"]
                if row["peer_prior_inspections"]
                else 0.0,
                math.log1p(row["peer_recent365_inspections"]),
                math.log1p(row["peer_recent365_serious"]),
                row["peer_recent365_serious"] / row["peer_recent365_inspections"]
                if row["peer_recent365_inspections"]
                else 0.0,
                math.log1p(row["peer_recent730_serious"]),
                math.log1p(row["peer_any_serious365"]),
                math.log1p(row["peer_any_serious730"]),
            ]
        )
    values.extend(float(row["state"] == state) for state in state_values)
    return values


def fit_logistic_gate(
    train_rows: Sequence[Mapping[str, Any]],
    graph: bool,
    state_values: Sequence[str],
    epochs: int = 300,
    learning_rate: float = 0.08,
    l2: float = 0.05,
) -> dict[str, Any]:
    raw = [row_numeric(row, graph, state_values) for row in train_rows]
    dim = len(raw[0])
    n = len(raw)
    means = [sum(x[j] for x in raw) / n for j in range(dim)]
    scales = []
    for j in range(dim):
        variance = sum((x[j] - means[j]) ** 2 for x in raw) / n
        scales.append(math.sqrt(variance) if variance > 1e-12 else 1.0)
    xs = [[(x[j] - means[j]) / scales[j] for j in range(dim)] for x in raw]
    ys = [row["label"] for row in train_rows]
    weights = [0.0] * dim
    intercept = 0.0
    for _ in range(epochs):
        gradient = [0.0] * dim
        intercept_gradient = 0.0
        for x, y in zip(xs, ys, strict=True):
            probability = sigmoid(intercept + sum(w * v for w, v in zip(weights, x, strict=True)))
            error = probability - y
            intercept_gradient += error
            for j, value in enumerate(x):
                gradient[j] += error * value
        inv_n = 1.0 / n
        intercept -= learning_rate * intercept_gradient * inv_n
        for j in range(dim):
            weights[j] -= learning_rate * (gradient[j] * inv_n + l2 * weights[j])
    return {
        "graph": graph,
        "means": means,
        "scales": scales,
        "weights": weights,
        "intercept": intercept,
    }


def predict_logistic(
    model: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], state_values: Sequence[str]
) -> list[float]:
    result = []
    for row in rows:
        raw = row_numeric(row, bool(model["graph"]), state_values)
        x = [(value - mean) / scale for value, mean, scale in zip(raw, model["means"], model["scales"], strict=True)]
        result.append(
            sigmoid(
                model["intercept"]
                + sum(weight * value for weight, value in zip(model["weights"], x, strict=True))
            )
        )
    return result


def roc_auc(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    order = sorted(range(len(labels)), key=lambda i: (scores[i], i))
    rank_sum = 0.0
    i = 0
    rank = 1
    while i < len(order):
        j = i + 1
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            j += 1
        average_rank = (rank + rank + (j - i) - 1) / 2
        rank_sum += average_rank * sum(labels[order[k]] for k in range(i, j))
        rank += j - i
        i = j
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def average_precision(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    order = sorted(range(len(labels)), key=lambda i: (-scores[i], i))
    positives = sum(labels)
    if not positives:
        return None
    hit = 0
    total = 0.0
    for rank, index in enumerate(order, 1):
        if labels[index]:
            hit += 1
            total += hit / rank
    return total / positives


def model_metrics(labels: Sequence[int], scores: Sequence[float]) -> dict[str, Any]:
    n = len(labels)
    k = max(1, math.ceil(0.1 * n))
    order = sorted(range(n), key=lambda i: (-scores[i], i))
    top = order[:k]
    hits = sum(labels[i] for i in top)
    positives = sum(labels)
    return {
        "rows": n,
        "positives": positives,
        "prevalence": positives / n,
        "roc_auc": roc_auc(labels, scores),
        "average_precision": average_precision(labels, scores),
        "precision_at_top_10_percent": hits / k,
        "recall_at_top_10_percent": hits / positives if positives else None,
        "brier": sum((score - label) ** 2 for label, score in zip(labels, scores, strict=True)) / n,
    }


def prevalence_scores(train_rows: Sequence[Mapping[str, Any]], target_rows: Sequence[Mapping[str, Any]]) -> list[float]:
    value = sum(row["label"] for row in train_rows) / len(train_rows)
    return [value] * len(target_rows)
