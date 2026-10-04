import unittest

import numpy as np

from healthgraphbench.rc31.analysis import (
    _auc, ranking_vectors, ranking_contrast, support_band, neighbor_band,
)


class RelationalAnalysisTests(unittest.TestCase):
    def test_zero_positive_rows_and_short_candidate_lists_count_in_precision(self):
        rows = [dict(entity_id='a', period=2024, candidate_count=2,
                     positive_count=1, positive_ranks=[2], history_support=3),
                dict(entity_id='b', period=2024, candidate_count=1,
                     positive_count=0, positive_ranks=[], history_support=3)]
        hits, positives, slots, selected = ranking_vectors(rows, 10)
        self.assertEqual(hits.sum() / slots.sum(), 1 / 3)
        self.assertEqual(hits.sum() / positives.sum(), 1)
        self.assertEqual(slots.tolist(), [2, 1])

    def test_paired_ratio_averages_training_stream_hits_not_provider_recalls(self):
        a = [dict(entity_id='a', period=2024, candidate_count=5, positive_count=1,
                  positive_ranks=[1], history_support=3),
             dict(entity_id='b', period=2024, candidate_count=5, positive_count=3,
                  positive_ranks=[1, 2, 3], history_support=3)]
        b = [{**row, 'positive_ranks': [4] if row['entity_id'] == 'a' else [3, 4, 5]} for row in a]
        result = ranking_contrast([a, b], [b], k=1, draws=32)
        self.assertEqual(result['delta_micro_recall_at_1'], .25)
        self.assertEqual(result['left_seed_metrics'], [.5, 0])

    def test_changed_targets_refuse_paired_comparison(self):
        row = dict(entity_id='a', period=2024, candidate_count=2,
                   positive_count=1, positive_ranks=[1], history_support=2)
        with self.assertRaisesRegex(ValueError, 'changed targets'):
            ranking_contrast([[row]], [[{**row, 'positive_count': 0, 'positive_ranks': []}]], draws=8)

    def test_empty_positive_denominator_is_not_metric_zero(self):
        row = dict(entity_id='a', period=2024, candidate_count=2,
                   positive_count=0, positive_ranks=[], history_support=2)
        result = ranking_contrast([[row]], [[row]], draws=8)
        self.assertIsNone(result['delta_micro_recall_at_10'])
        self.assertIsNone(result['conditional_paired_cluster_interval_95'])
        self.assertEqual(result['valid_draws'], 0)

    def test_weighted_auc_counts_ties_as_half_pairs(self):
        labels = np.asarray([0, 1, 0, 1])
        scores = np.asarray([.2, .2, .8, .9])
        weights = np.asarray([1., 2., 3., 1.])
        # Positive at.2: half of1negative×weight2; positive at.9:4negatives.
        self.assertEqual(_auc(labels, scores, weights), 5 / 12)
        self.assertIsNone(_auc(labels, scores, np.asarray([1., 0., 1., 0.])))

    def test_item_strata_use_pre_target_support_and_keep_boundary_values(self):
        row = dict(entity_id='a', period=2024, candidate_count=3, positive_count=2,
                   positive_ranks=[1, 2], history_support=10,
                   positive_items=[dict(rank=1, prior_support=5, neighbor_support=0),
                                   dict(rank=2, prior_support=6, neighbor_support=1)],
                   recommendations=[dict(rank=1, prior_support=5, neighbor_support=0),
                                    dict(rank=2, prior_support=6, neighbor_support=1)])
        hits, positives, _, _ = ranking_vectors([row], 1, ('candidate_support', '<=5'))
        self.assertEqual((hits.sum(), positives.sum()), (1, 1))
        self.assertEqual([support_band(v) for v in (5, 6, 50, 51)], ['<=5', '6-50', '6-50', '>50'])
        self.assertEqual([neighbor_band(v) for v in (0, 1, 2, 3)], ['0', '1-2', '1-2', '3+'])


if __name__ == '__main__':
    unittest.main()
