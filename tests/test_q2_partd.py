"""Protocol-lock and validation-only selection tests for Part D Q2."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from healthgraphbench.q2.partd import (
    BPR_GRID,
    BOOSTED_GRID,
    LOGISTIC_GRID,
    Q2_SEEDS,
    _boosted_seeds,
    _select_configuration,
    _training_row_count,
    _validate_protocol,
)


class _SizedOnly:
    def __init__(self, size: int) -> None:
        self.size = size

    def __len__(self) -> int:
        return self.size


class _CountTask:
    def __init__(self, positive_count: int, global_drug_count: int) -> None:
        self.history = SimpleNamespace(
            provider_drugs={"provider": _SizedOnly(positive_count)},
            drug_providers=_SizedOnly(global_drug_count),
        )

    def _target_history(self, year: int) -> tuple[object, None, None]:
        return self.history, None, None


def _protocol() -> dict[str, object]:
    return {
        "tasks": {
            "partd": {
                "name": "partd_prescriber_drug",
                "primary_metric": "micro_recall_at_10",
                "seeds": Q2_SEEDS,
                "source_manifest": "data/manifests/partd_feasibility_v0_2_lookback.json",
                "cohort_size": 2000,
                "validation_year": 2023,
                "test_years": [2024],
                "grids": {
                    "logistic": [dict(value) for value in LOGISTIC_GRID],
                    "bpr": [dict(value) for value in BPR_GRID],
                    "boosted": [dict(value) for value in BOOSTED_GRID],
                },
                "fixed": {
                    "logistic": {"solver": "lbfgs", "max_iter": 1000, "tol": 1e-8},
                    "bpr": {"epochs": 30, "specialty_weight": 0.35},
                    "boosted": {
                        "early_stopping": False,
                        "max_features": 1.0,
                        "max_bins": 255,
                        "min_samples_leaf": 20,
                        "seed_repetition_condition": "training_rows_gt_200000",
                    },
                },
            }
        }
    }


class PartDQ2ProtocolTests(unittest.TestCase):
    def test_boosted_repetitions_follow_the_exact_training_row_cutoff(self) -> None:
        at_cutoff = _CountTask(positive_count=50_000, global_drug_count=200_000)
        above_cutoff = _CountTask(positive_count=50_000, global_drug_count=200_001)
        self.assertEqual(_training_row_count(at_cutoff, 2023), 200_000)
        self.assertEqual(_boosted_seeds(at_cutoff, 2023), [None])
        self.assertEqual(_training_row_count(above_cutoff, 2023), 200_001)
        self.assertEqual(_boosted_seeds(above_cutoff, 2023), list(Q2_SEEDS))

    def test_incomplete_or_reordered_grid_is_rejected_before_any_scoring(self) -> None:
        protocol = _protocol()
        protocol["tasks"]["partd"]["grids"]["bpr"].pop()
        with self.assertRaisesRegex(ValueError, "approved ordered six-config grids"):
            _validate_protocol(protocol)

    def test_exact_validation_ties_use_first_published_configuration(self) -> None:
        records = [
            {
                "configuration_index": index,
                "configuration": {"index": index},
                "primary_validation_by_seed": [0.5, 0.5, 0.5],
            }
            for index in range(6)
        ]
        selected = _select_configuration(records)
        self.assertEqual(selected["configuration_index"], 0)
        self.assertEqual(selected["mean_primary_validation"], 0.5)

    def test_selection_refuses_a_partial_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "all six grid configurations"):
            _select_configuration(
                [
                    {"configuration": {"index": index}, "primary_validation_by_seed": [0.5]}
                    for index in range(5)
                ]
            )


if __name__ == "__main__":
    unittest.main()
