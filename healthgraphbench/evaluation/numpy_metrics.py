"""NumPy numerical primitives for unreleased v0.2 development.

Equal-score candidates retain caller order; callers must provide candidates in
canonical candidate-ID order.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def _validated_arrays(
    labels: Sequence[int] | np.ndarray,
    scores: Sequence[float] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    raw_labels = np.asarray(labels)
    score_array = np.asarray(scores, dtype=np.float64)
    if raw_labels.ndim != 1 or score_array.ndim != 1:
        raise ValueError("labels and scores must be one-dimensional")
    if raw_labels.size != score_array.size:
        raise ValueError("labels and scores must have equal length")
    if not np.all(np.isin(raw_labels, (0, 1))):
        raise ValueError("labels must contain only 0 and 1")
    if not np.isfinite(score_array).all():
        raise ValueError("scores must be finite")
    return raw_labels.astype(np.int8, copy=False), score_array


def finite_float_array(values: Sequence[float] | np.ndarray, *, name: str = "values") -> np.ndarray:
    """Return a one-dimensional finite float64 array."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must be finite")
    return array


def ranking_auc_numpy(
    labels: Sequence[int] | np.ndarray,
    scores: Sequence[float] | np.ndarray,
) -> float | None:
    """Compute ROC AUC with canonical caller-order tie handling."""
    label_array, score_array = _validated_arrays(labels, scores)
    positives = int(label_array.sum(dtype=np.int64))
    negatives = int(label_array.size) - positives
    if not positives or not negatives:
        return None
    order = np.argsort(score_array, kind="stable")
    ordered_scores = score_array[order]
    boundaries = np.flatnonzero(ordered_scores[1:] != ordered_scores[:-1]) + 1
    starts = np.concatenate((np.array([0], dtype=np.intp), boundaries))
    ends = np.concatenate((boundaries, np.array([order.size], dtype=np.intp)))
    rank_sum = 0.0
    for start, end in zip(starts, ends, strict=True):
        average_rank = (int(start) + 1 + int(end)) / 2.0
        rank_sum += average_rank * int(label_array[order[start:end]].sum(dtype=np.int64))
    return float((rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives))


def average_precision_numpy(
    labels: Sequence[int] | np.ndarray,
    scores: Sequence[float] | np.ndarray,
) -> float | None:
    """Compute average precision with canonical caller-order ties."""
    label_array, score_array = _validated_arrays(labels, scores)
    positives = int(label_array.sum(dtype=np.int64))
    if not positives:
        return None
    order = np.argsort(-score_array, kind="stable")
    ordered_labels = label_array[order]
    cumulative_hits = np.cumsum(ordered_labels, dtype=np.int64)
    positive_positions = ordered_labels == 1
    ranks = np.arange(1, ordered_labels.size + 1, dtype=np.float64)
    precision_at_hit = cumulative_hits[positive_positions] / ranks[positive_positions]
    return float(precision_at_hit.sum(dtype=np.float64) / positives)


def recall_at_k(
    scores: Sequence[float] | np.ndarray,
    positives: Sequence[int] | np.ndarray,
    k: int,
) -> float | None:
    """Return recall among the top ``k`` canonically ordered candidates."""
    if k <= 0:
        raise ValueError("k must be positive")
    positive_array, score_array = _validated_arrays(positives, scores)
    positive_count = int(positive_array.sum(dtype=np.int64))
    if not positive_count or not score_array.size:
        return None
    top_order = np.argsort(-score_array, kind="stable")[:k]
    hits = int(positive_array[top_order].sum(dtype=np.int64))
    return float(hits / positive_count)


def mean_reciprocal_rank(
    scores: Sequence[float] | np.ndarray,
    positives: Sequence[int] | np.ndarray,
) -> float | None:
    """Return reciprocal rank of the first positive in canonical order."""
    positive_array, score_array = _validated_arrays(positives, scores)
    if not int(positive_array.sum(dtype=np.int64)) or not score_array.size:
        return None
    order = np.argsort(-score_array, kind="stable")
    positive_positions = np.flatnonzero(positive_array[order] == 1)
    return float(1.0 / (int(positive_positions[0]) + 1)) if positive_positions.size else None


def numpy_to_python(value: Any) -> Any:
    """Recursively convert NumPy values to JSON-serializable Python values."""
    if isinstance(value, np.ndarray):
        return [numpy_to_python(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {numpy_to_python(key): numpy_to_python(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [numpy_to_python(item) for item in value]
    return value
