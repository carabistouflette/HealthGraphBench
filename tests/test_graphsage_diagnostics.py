"""Contract tests for GraphSAGE optimization diagnostics and checkpoints."""

from __future__ import annotations

import json
import math
import unittest

from healthgraphbench.tasks.maude.models import GraphSageRanker, History, fit_graphsage


def _history(edges: tuple[tuple[str, str], ...]) -> History:
    history = History.empty()
    for product, problem in edges:
        history.product_problems[product].add(problem)
        history.problem_products[problem].add(product)
    return history


def _message(
    own: tuple[float, ...],
    neighbors: list[tuple[float, ...]],
    self_weights: list[list[float]],
    neighbor_weights: list[list[float]],
) -> tuple[float, ...]:
    dimension = len(own)
    mean = tuple(
        sum(values[index] for values in neighbors) / len(neighbors)
        if neighbors
        else 0.0
        for index in range(dimension)
    )
    return tuple(
        math.tanh(
            sum(self_weights[row][column] * own[column] for column in range(dimension))
            + sum(
                neighbor_weights[row][column] * mean[column]
                for column in range(dimension)
            )
        )
        for row in range(dimension)
    )


class GraphSageDiagnosticsTests(unittest.TestCase):
    def test_callbacks_preserve_three_epoch_ranker_and_checkpoint_rebuilds_scores(self) -> None:
        history = _history((('A', '1'), ('B', '2')))
        expected = fit_graphsage(history, epochs=3)
        epoch_events: list[dict[str, int | float | None]] = []
        checkpoints: list[dict[str, object]] = []

        observed = fit_graphsage(
            history,
            epochs=3,
            on_epoch=epoch_events.append,
            on_checkpoint=checkpoints.append,
        )

        self.assertEqual(expected, observed)
        self.assertEqual(3, len(epoch_events))
        self.assertEqual([1, 2, 3], [event['epoch'] for event in epoch_events])
        for event in epoch_events:
            self.assertEqual(2, event['steps'])
            self.assertEqual(0, event['positive_edges_skipped'])
            self.assertEqual(2, event['triplets_visited'])
            self.assertIsInstance(event['mean_bpr_data_loss'], float)
        self.assertEqual(1, len(checkpoints))

        serialized = json.loads(json.dumps(checkpoints[0]))
        self.assertEqual('healthgraphbench.graphsage-checkpoint.v1', serialized['schema'])
        self.assertEqual(3, serialized['epochs_completed'])
        self.assertIs(serialized['resume_supported'], False)
        serialized['product_embeddings']['A'] = [99.0] * len(serialized['product_embeddings']['A'])
        serialized['problem_embeddings']['1'] = [99.0] * len(serialized['problem_embeddings']['1'])
        restored = GraphSageRanker.from_checkpoint(serialized)
        self.assertEqual(expected, restored)
        self.assertEqual(expected.score('missing', '1'), restored.score('missing', '1'))
        self.assertEqual(expected.score('A', 'missing'), restored.score('A', 'missing'))
        self.assertEqual(0.0, restored.score('missing', '1'))
        self.assertEqual(0.0, restored.score('A', 'missing'))

    def test_zero_epoch_checkpoint_rebuilds_initial_ranker_without_loss_event(self) -> None:
        history = _history((('A', '1'), ('B', '2')))
        epoch_events: list[dict[str, int | float | None]] = []
        checkpoints: list[dict[str, object]] = []

        initial = fit_graphsage(
            history,
            epochs=0,
            on_epoch=epoch_events.append,
            on_checkpoint=checkpoints.append,
        )

        self.assertEqual([], epoch_events)
        self.assertEqual(1, len(checkpoints))
        self.assertEqual(0, checkpoints[0]['epochs_completed'])
        self.assertEqual(initial, GraphSageRanker.from_checkpoint(checkpoints[0]))

    def test_saturated_products_are_skipped_without_manufactured_loss(self) -> None:
        history = _history(
            (('A', '1'), ('A', '2'), ('B', '1'), ('B', '2'))
        )
        epoch_events: list[dict[str, int | float | None]] = []

        fit_graphsage(history, epochs=2, on_epoch=epoch_events.append)

        self.assertEqual(2, len(epoch_events))
        for event in epoch_events:
            self.assertEqual(0, event['steps'])
            self.assertEqual(4, event['positive_edges_skipped'])
            self.assertEqual(4, event['triplets_visited'])
            self.assertIsNone(event['mean_bpr_data_loss'])

    def test_bpr_data_loss_is_measured_before_each_update(self) -> None:
        history = _history((('A', '1'), ('B', '1'), ('B', '2')))
        initial_checkpoints: list[dict[str, object]] = []
        fit_graphsage(history, epochs=0, on_checkpoint=initial_checkpoints.append)
        initial = initial_checkpoints[0]
        product = initial['product_inputs']['A']
        positive = initial['problem_inputs']['1']
        negative = initial['problem_inputs']['2']
        product_hidden = _message(
            tuple(product),
            [tuple(initial['problem_inputs'][key]) for key in initial['product_neighbors']['A']],
            initial['self_weights'],
            initial['neighbor_weights'],
        )
        positive_hidden = _message(
            tuple(positive),
            [tuple(initial['product_inputs'][key]) for key in initial['problem_neighbors']['1']],
            initial['self_weights'],
            initial['neighbor_weights'],
        )
        negative_hidden = _message(
            tuple(negative),
            [tuple(initial['product_inputs'][key]) for key in initial['problem_neighbors']['2']],
            initial['self_weights'],
            initial['neighbor_weights'],
        )
        margin = sum(left * right for left, right in zip(product_hidden, positive_hidden)) - sum(
            left * right for left, right in zip(product_hidden, negative_hidden)
        )
        expected_loss = math.log1p(math.exp(-margin))
        epoch_events: list[dict[str, int | float | None]] = []

        fit_graphsage(history, epochs=1, on_epoch=epoch_events.append)

        self.assertEqual(1, epoch_events[0]['steps'])
        self.assertEqual(2, epoch_events[0]['positive_edges_skipped'])
        self.assertEqual(3, epoch_events[0]['triplets_visited'])
        self.assertAlmostEqual(expected_loss, epoch_events[0]['mean_bpr_data_loss'])


if __name__ == '__main__':
    unittest.main()
