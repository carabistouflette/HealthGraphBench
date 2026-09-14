"""Task-dispatched baseline models.

The wrappers contain no task-specific feature code. Each task owns cutoffs,
feature availability, candidate generation, and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core import PredictionSet, Split


@dataclass(frozen=True)
class _MethodModel:
    name: str

    def fit_predict(
        self, train: Split, validation: Split, test: Split
    ) -> PredictionSet:
        if train.task is not validation.task or train.task is not test.task:
            raise ValueError("all splits must belong to the same task")
        return train.task.fit_predict(self.name, train, validation, test)


class GlobalPopularity(_MethodModel):
    def __init__(self) -> None:
        super().__init__("global_popularity")


class NeighborFrequency(_MethodModel):
    def __init__(self) -> None:
        super().__init__("neighbor_frequency")


class LogisticTabular(_MethodModel):
    def __init__(self) -> None:
        super().__init__("logistic_tabular")


class BoostedStumps(_MethodModel):
    def __init__(self) -> None:
        super().__init__("boosted_stumps_tabular")


class SpectralFactorization(_MethodModel):
    def __init__(self) -> None:
        super().__init__("matrix_factorization_spectral")


class BprNeighborAverage(_MethodModel):
    def __init__(self) -> None:
        super().__init__("graph_message_passing_bpr")


class Prevalence(_MethodModel):
    def __init__(self) -> None:
        super().__init__("prevalence")


class FacilityHistory(_MethodModel):
    def __init__(self) -> None:
        super().__init__("facility_history")


class OwnershipAggregates(_MethodModel):
    def __init__(self) -> None:
        super().__init__("facility_plus_combined_ownership")
