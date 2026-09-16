"""Task model wrappers exposed through the common benchmark interface."""

from .baselines import (
    BprNeighborAverage,
    BoostedStumps,
    FacilityHistory,
    GlobalPopularity,
    GraphSageLinkPrediction,
    HistoryOverlap,
    LogisticTabular,
    NeighborFrequency,
    OwnershipAggregates,
    PartDGraphBpr,
    PartDTabularLogistic,
    Prevalence,
    SpecialtyPopularity,
    SpectralFactorization,
)

__all__ = [
    "BprNeighborAverage",
    "BoostedStumps",
    "FacilityHistory",
    "GlobalPopularity",
    "GraphSageLinkPrediction",
    "HistoryOverlap",
    "LogisticTabular",
    "NeighborFrequency",
    "OwnershipAggregates",
    "PartDGraphBpr",
    "PartDTabularLogistic",
    "Prevalence",
    "SpecialtyPopularity",
    "SpectralFactorization",
]
