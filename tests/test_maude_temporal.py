"""Regression tests for temporal candidate and ranking boundaries."""

from __future__ import annotations

import unittest

from healthgraphbench.tasks.maude.data import DataAudit, DataBundle, ProblemStats, QuarterSnapshot
from healthgraphbench.tasks.maude.evaluate import eligible_edges, first_edges
from healthgraphbench.tasks.maude.models import History, TrainingRow, fit_logistic


class TemporalGateTests(unittest.TestCase):
    def setUp(self) -> None:
        first = QuarterSnapshot(
            "2019Q1",
            2,
            {"A": 2, "B": 1},
            {"A": frozenset({"M"}), "B": frozenset({"N"})},
            frozenset({("A", "1"), ("B", "2")}),
            {("A", "1"): 2, ("B", "2"): 1},
        )
        second = QuarterSnapshot(
            "2019Q2",
            1,
            {"A": 1},
            {"A": frozenset({"M"})},
            frozenset({("A", "2"), ("A", "3")}),
            {("A", "2"): 1, ("A", "3"): 1},
        )
        self.bundle = DataBundle(
            snapshots=(first, second),
            audit=DataAudit(
                device_stats={},
                problem_stats=ProblemStats(),
                unique_device_mdr_keys=0,
                matched_device_problem_mdr_keys=0,
                problem_only_mdr_keys=0,
                valid_device_rows=0,
                keys_multiple_valid_device_rows=0,
                duplicate_valid_rows_beyond_unique_product_per_key=0,
                keys_multiple_product_codes=0,
                max_valid_rows_per_key=0,
                max_unique_products_per_key=0,
                problem_keys_with_multiple_codes=0,
                max_distinct_problem_codes_per_key=0,
                unique_product_problem_edges=0,
                unique_product_codes=0,
                unique_problem_codes=0,
            ),
            source_paths=(),
        )

    def test_first_edges_and_eligibility_use_history_only(self) -> None:
        observed = first_edges(self.bundle)
        self.assertEqual(observed["2019Q1"], frozenset({("A", "1"), ("B", "2")}))
        self.assertEqual(observed["2019Q2"], frozenset({("A", "2"), ("A", "3")}))
        history = History.empty()
        history.add(self.bundle.snapshots[0], {})
        self.assertEqual(eligible_edges(observed["2019Q2"], history), frozenset({("A", "2")}))

    def test_logistic_score_is_deterministic(self) -> None:
        rows = [
            TrainingRow((0.0, 0.0), 0),
            TrainingRow((1.0, 1.0), 1),
            TrainingRow((2.0, 2.0), 1),
        ]
        first = fit_logistic(rows, epochs=20)
        second = fit_logistic(rows, epochs=20)
        self.assertEqual(first, second)
        self.assertGreater(first.score((2.0, 2.0)), first.score((0.0, 0.0)))


if __name__ == "__main__":
    unittest.main()
