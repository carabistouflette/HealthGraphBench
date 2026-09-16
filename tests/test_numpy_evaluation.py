"""Behavioral tests for the NumPy-backed v0.2 evaluation primitives."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from healthgraphbench.evaluation import (
    average_precision,
    average_precision_numpy,
    cluster_bootstrap_indices,
    finite_float_array,
    mean_reciprocal_rank,
    numpy_to_python,
    ranking_auc,
    ranking_auc_numpy,
    recall_at_k,
)



class RankingContractTests(unittest.TestCase):
    def test_v02_registry_declares_canonical_tie_policy(self) -> None:
        contract = json.loads(
            (Path(__file__).parents[1] / "configs" / "task_candidates_v0_2.json").read_text(
                encoding="utf-8"
            )
        )
        policy = contract["ranking_tie_policy"]
        self.assertEqual(policy["primary_key"], "score descending")
        self.assertEqual(policy["secondary_key"], "canonical candidate ID ascending")
        self.assertEqual(
            policy["array_metric_input_order"],
            "canonical candidate ID ascending",
        )
        self.assertEqual(
            set(policy["canonical_candidate_ids"]),
            {
                "maude",
                "cms_nursing",
                "partd_prescriber_drug",
                "clinical_trials_reporting",
                "faers_drug_reaction",
            },
        )
        self.assertEqual(
            policy["canonical_candidate_ids"]["partd_prescriber_drug"],
            "exact trimmed generic_name",
        )


class NumpyMetricTests(unittest.TestCase):
    def test_auc_and_average_precision_match_legacy_metrics(self) -> None:
        cases = (
            ([0, 1, 0, 1, 1], [0.1, 0.9, 0.4, 0.4, 0.2]),
            ([1, 0, 1, 0], [0.7, 0.2, 0.7, 0.6]),
            ([0, 1, 1, 0, 1], [0.3, 0.3, 0.8, 0.8, 0.1]),
        )
        for labels, scores in cases:
            with self.subTest(labels=labels, scores=scores):
                self.assertAlmostEqual(
                    ranking_auc_numpy(np.asarray(labels), np.asarray(scores)),
                    ranking_auc(labels, scores),
                )
                self.assertAlmostEqual(
                    average_precision_numpy(np.asarray(labels), np.asarray(scores)),
                    average_precision(labels, scores),
                )

    def test_score_ties_preserve_input_order(self) -> None:
        labels = np.array([1, 0, 1, 0], dtype=np.int8)
        scores = np.ones(4, dtype=np.float64)
        self.assertAlmostEqual(average_precision_numpy(labels, scores), 5 / 6)
        self.assertEqual(recall_at_k(scores, labels, 1), 0.5)
        self.assertEqual(mean_reciprocal_rank(scores, labels), 1.0)

    def test_empty_and_zero_positive_inputs_return_undefined(self) -> None:
        empty = np.array([], dtype=np.float64)
        labels = np.zeros(3, dtype=np.int8)
        scores = np.array([0.8, 0.2, 0.1])
        self.assertIsNone(ranking_auc_numpy(empty, empty))
        self.assertIsNone(average_precision_numpy(empty, empty))
        self.assertIsNone(ranking_auc_numpy(labels, scores))
        self.assertIsNone(average_precision_numpy(labels, scores))
        self.assertIsNone(recall_at_k(scores, labels, 2))
        self.assertIsNone(mean_reciprocal_rank(scores, labels))

    def test_recall_and_mrr_respect_k_and_ranking_boundaries(self) -> None:
        labels = np.array([0, 1, 1], dtype=np.int8)
        scores = np.array([0.9, 0.8, 0.1])
        self.assertEqual(recall_at_k(scores, labels, 1), 0.0)
        self.assertEqual(recall_at_k(scores, labels, 2), 0.5)
        self.assertEqual(mean_reciprocal_rank(scores, labels), 0.5)
        with self.assertRaises(ValueError):
            recall_at_k(scores, labels, 0)

    def test_invalid_shapes_labels_and_scores_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ranking_auc_numpy([[0, 1]], [0.1, 0.2])
        with self.assertRaises(ValueError):
            average_precision_numpy([0, 1], [[0.1, 0.2]])
        with self.assertRaises(ValueError):
            ranking_auc_numpy([0, 1], [0.1])
        with self.assertRaises(ValueError):
            average_precision_numpy([0, 2], [0.1, 0.2])
        with self.assertRaises(ValueError):
            average_precision_numpy([0, 1], [0.1, np.nan])
        with self.assertRaises(ValueError):
            finite_float_array([0.1, np.inf])


class BootstrapAndSerializationTests(unittest.TestCase):
    def test_cluster_bootstrap_indices_are_seeded_and_bounded(self) -> None:
        cluster_ids = ["trial-b", "trial-a", "trial-b", "trial-c"]
        first = cluster_bootstrap_indices(cluster_ids, resamples=32, seed=19)
        replay = cluster_bootstrap_indices(cluster_ids, resamples=32, seed=19)
        other = cluster_bootstrap_indices(cluster_ids, resamples=32, seed=20)
        self.assertEqual(first.shape, (32, 3))
        np.testing.assert_array_equal(first, replay)
        self.assertFalse(np.array_equal(first, other))
        self.assertGreaterEqual(int(first.min()), 0)
        self.assertLess(int(first.max()), 3)
        with self.assertRaises(ValueError):
            cluster_bootstrap_indices([], resamples=1, seed=19)
        with self.assertRaises(ValueError):
            cluster_bootstrap_indices(["trial-a"], resamples=0, seed=19)

    def test_numpy_values_convert_to_json_safe_python_values(self) -> None:
        payload = {
            np.int64(7): {
                "scalar": np.float64(0.25),
                "integer": np.int64(3),
                "flag": np.bool_(True),
                "array": np.array([1.0, 2.0]),
                "nested": (np.int64(4),),
            }
        }
        converted = numpy_to_python(payload)
        encoded = json.dumps(converted, allow_nan=False, sort_keys=True)
        self.assertEqual(
            json.loads(encoded),
            {
                "7": {
                    "scalar": 0.25,
                    "integer": 3,
                    "flag": True,
                    "array": [1.0, 2.0],
                    "nested": [4],
                }
            },
        )


if __name__ == "__main__":
    unittest.main()
