"""Paired entity-clustered bootstrap estimators.

Rows from the same product/CCN are resampled together. This is the minimum
uncertainty correction used by the v0.1 exploratory comparisons; it does not
remove all network dependence.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    estimate: float
    lower: float
    upper: float
    resamples: int
    seed: int
    clusters: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "estimate": self.estimate,
            "ci95": [self.lower, self.upper],
            "resamples": self.resamples,
            "seed": self.seed,
            "clusters": self.clusters,
        }


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("bootstrap requires at least one resample")
    position = (len(sorted_values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def paired_cluster_bootstrap(
    rows: Iterable[T],
    cluster_of: Callable[[T], str],
    statistic: Callable[[list[T]], float],
    *,
    resamples: int = 5000,
    seed: int = 0,
) -> BootstrapInterval:
    """Return an entity-clustered percentile interval for a row statistic."""

    if resamples <= 0:
        raise ValueError("resamples must be positive")
    clusters: dict[str, list[T]] = defaultdict(list)
    for row in rows:
        clusters[cluster_of(row)].append(row)
    if not clusters:
        raise ValueError("rows must not be empty")
    cluster_rows = tuple(clusters.values())
    original = statistic([row for group in cluster_rows for row in group])
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(resamples):
        sampled = [cluster_rows[generator.randrange(len(cluster_rows))] for _ in cluster_rows]
        estimates.append(statistic([row for group in sampled for row in group]))
    estimates.sort()
    return BootstrapInterval(
        original,
        _percentile(estimates, 0.025),
        _percentile(estimates, 0.975),
        resamples,
        seed,
        len(cluster_rows),
    )
