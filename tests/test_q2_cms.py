"""Behavioral safeguards for CMS validation and comparable annual streams."""

from __future__ import annotations

import unittest
import gzip
import json
import tempfile
from pathlib import Path

from threadpoolctl import threadpool_limits

from healthgraphbench.q2.cms import _fit_phase, _pool_annual_predictions, select_validation


class Q2CmsSelectionTests(unittest.TestCase):
    def test_boosted_fit_learns_only_the_pre_target_relationship(self) -> None:
        base = {
            "state": "SYNTH", "prior_inspections": 1, "prior_serious": 0,
            "recent365_inspections": 0, "recent365_serious": 0,
            "recent730_inspections": 0, "recent730_serious": 0,
            "days_since_last": 30, "age_years": 5, "chow_prior": 0,
            "chow_recent365": 0,
        }
        rows = [
            {**base, "ccn": f"SYNTH_{index}", "date": "2022-01-01",
             "year": 2022, "label": index % 2, "prior_serious_rate": index % 2}
            for index in range(100)
        ]
        rows.extend(
            {**base, "ccn": f"TARGET_{value}", "date": "2023-01-01",
             "year": 2023, "label": 1 - value, "prior_serious_rate": value}
            for value in (0, 1)
        )
        with tempfile.TemporaryDirectory() as temporary, threadpool_limits(1):
            root = Path(temporary)
            path = root / "rows.jsonl.gz"
            with gzip.open(path, "wt") as stream:
                for row in rows:
                    stream.write(json.dumps(row) + "\n")
            phase = root / "fit"
            phase.mkdir()
            result = _fit_phase(
                path, 2023, "facility_history", "boosted",
                {"learning_rate": .1, "max_iter": 100, "max_leaf_nodes": 7,
                 "l2_regularization": 0},
                {"early_stopping": False, "max_features": 1, "max_bins": 255,
                 "min_samples_leaf": 20, "seed_repetition_condition": "training_rows_gt_200000"},
                None, phase,
            )
            with gzip.open(phase / "predictions.jsonl.gz", "rt") as stream:
                predictions = [json.loads(line) for line in stream]
            self.assertLess(predictions[0]["score"], .1)
            self.assertGreater(predictions[1]["score"], .9)
            self.assertLess(result["losses"]["trained"], .1)
            self.assertEqual(result["metrics"]["roc_auc"], 0)

    def test_selection_uses_mean_over_all_seeds_not_the_luckiest_fit(self) -> None:
        records = []
        for configuration, values in enumerate(((0.875, 0.125, 0.125), (0.5, 0.5, 0.5))):
            for seed, value in zip((103, 211, 307), values, strict=True):
                records.append({"configuration_index": configuration, "seed": seed,
                                "expected_seeds": [103, 211, 307], "metrics": {"roc_auc": value}})
        self.assertEqual(select_validation(records, 2)["configuration_index"], 1)
        with self.assertRaises(ValueError):
            select_validation(records[:-1], 2)
        with self.assertRaises(ValueError):
            select_validation(records[:3], 2)

    def test_pooling_keeps_both_years_when_hgb_crosses_the_binning_cutoff(self) -> None:
        def rows(negative: float, positive: float):
            return [{"label": 0, "score": negative}, {"label": 1, "score": positive}]

        annual = {
            2024: {None: rows(0.1, 0.9)},
            2025: {103: rows(0.2, 0.8), 211: rows(0.8, 0.2), 307: rows(0.5, 0.5)},
        }
        pooled = _pool_annual_predictions(annual, [103, 211, 307])["pooled_by_seed"]
        self.assertEqual(set(pooled), {"103", "211", "307"})
        self.assertEqual(pooled["103"]["roc_auc"], 1.0)
        self.assertEqual(pooled["211"]["roc_auc"], 0.75)
        self.assertEqual(pooled["307"]["roc_auc"], 0.875)
        with self.assertRaises(ValueError):
            _pool_annual_predictions({2024: annual[2024], 2025: {103: annual[2025][103]}},
                                     [103, 211, 307])


if __name__ == "__main__":
    unittest.main()
