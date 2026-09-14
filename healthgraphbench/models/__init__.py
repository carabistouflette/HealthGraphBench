"""Frozen model wrappers exposed through the common benchmark interface."""

from .baselines import (
    BprNeighborAverage,
    BoostedStumps,
    FacilityHistory,
    GlobalPopularity,
    LogisticTabular,
    NeighborFrequency,
    OwnershipAggregates,
    Prevalence,
    SpectralFactorization,
)

__all__ = [
    "BprNeighborAverage",
    "BoostedStumps",
    "FacilityHistory",
    "GlobalPopularity",
    "LogisticTabular",
    "NeighborFrequency",
    "OwnershipAggregates",
    "Prevalence",
    "SpectralFactorization",
]
