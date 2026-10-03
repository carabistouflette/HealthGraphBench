"""Behavioral safeguards for CMS validation and comparable annual streams."""

from __future__ import annotations

import unittest

from healthgraphbench.q2.cms import _pool_annual_predictions, select_validation


class Q2CmsSelectionTests(unittest.TestCase):
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
