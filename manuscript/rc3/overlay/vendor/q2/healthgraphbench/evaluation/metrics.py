"""Metric helpers shared by uncertainty and control scripts."""

from __future__ import annotations

from collections.abc import Sequence


def ranking_auc(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    order = sorted(range(len(labels)), key=lambda index: (scores[index], index))
    rank_sum = 0.0
    rank = 1
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and scores[order[end]] == scores[order[index]]:
            end += 1
        average_rank = (rank + rank + end - index - 1) / 2
        rank_sum += average_rank * sum(labels[order[k]] for k in range(index, end))
        rank += end - index
        index = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def average_precision(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    positives = sum(labels)
    if not positives:
        return None
    order = sorted(range(len(labels)), key=lambda index: (-scores[index], index))
    hits = 0
    total = 0.0
    for rank, index in enumerate(order, 1):
        if labels[index]:
            hits += 1
            total += hits / rank
    return total / positives
