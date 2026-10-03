"""Consumer-visible invariants for the retained-prediction comparison."""
import unittest

from scripts.analyze_maude_paired_comparison import _interval, _pair_quarter, json_digest


class MaudePairedComparisonTests(unittest.TestCase):
    def test_product_blocks_preserve_all_quarters_and_pooled_denominators(self):
        rows = [
            {'product': 'A', 'positive_edges': 1, 'hits_C30_at_10': 1, 'hits_neighbors_at_10': 0},
            {'product': 'A', 'positive_edges': 9, 'hits_C30_at_10': 0, 'hits_neighbors_at_10': 0},
            {'product': 'B', 'positive_edges': 1, 'hits_C30_at_10': 0, 'hits_neighbors_at_10': 1},
        ]
        result, draws = _interval(rows, resamples=200, seed=7)
        self.assertEqual(result['estimate'], 0.0)
        # Each draw contains AA, AB/BA, or BB; independent quarter draws or
        # averaging quarter recalls would produce different possible values.
        self.assertEqual(set(draws), {0.1, 0.0, -1.0})
        self.assertEqual(result['ci95'], [-1.0, 0.1])

    def test_equal_denominators_do_not_hide_different_positive_identities(self):
        ids = ['X', 'Y']
        sets = {'P': {'candidate_ids': ids, 'candidate_set_sha256': json_digest(ids),
                      'positive_problem_ids': ['X'], 'history_product_reports': 2}}
        old = {'P': {'positive_edges': 1, 'history_support': 2, 'hits_at_10': 1}}
        historical_predictions = {'P': {'positive_ids': {'Y'}, 'candidate_counts': {2}, 'support': {2}}}
        predictions = {'P': {'ids': set(ids), 'positive_ids': {'X'}, 'ranks': {1, 2}, 'hits': 1}}
        with self.assertRaises(ValueError):
            _pair_quarter('2024Q1', sets, predictions, old, historical_predictions,
                          {}, set(ids), {'P': 2})

    def test_candidate_identity_mismatch_rejected_even_at_same_cardinality(self):
        ids = ['X', 'Y']
        sets = {'P': {'candidate_ids': ids, 'candidate_set_sha256': json_digest(ids),
                      'positive_problem_ids': ['X'], 'history_product_reports': 2}}
        old = {'P': {'positive_edges': 1, 'history_support': 2, 'hits_at_10': 1}}
        historical_predictions = {'P': {'positive_ids': {'X'}, 'candidate_counts': {2}, 'support': {2}}}
        predictions = {'P': {'ids': set(ids), 'positive_ids': {'X'}, 'ranks': {1, 2}, 'hits': 1}}
        with self.assertRaises(ValueError):
            _pair_quarter('2024Q1', sets, predictions, old, historical_predictions,
                          {}, {'X', 'Z'}, {'P': 2})


if __name__ == '__main__':
    unittest.main()
