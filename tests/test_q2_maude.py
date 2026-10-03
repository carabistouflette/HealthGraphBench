"""Behavioral preflights for the MAUDE Q2 graph comparisons."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from healthgraphbench.q2.maude import _family_seeds, _rank_candidates
from healthgraphbench.q2.maude_backend import (
    fit_bpr,
    fit_graphsage,
    fit_spectral,
    graphsage_gradient_preflight,
    load_bpr_checkpoint,
    load_graphsage_checkpoint,
    load_spectral_checkpoint,
    save_bpr_checkpoint,
    save_graphsage_checkpoint,
    save_spectral_checkpoint,
)
from healthgraphbench.tasks.maude.data import QuarterSnapshot
from healthgraphbench.tasks.maude.models import History


SEEDS = (103, 211, 307)


def _history(edge_rows: tuple[tuple[str, str], ...]) -> History:
    products = sorted({product for product, _ in edge_rows})
    snapshot = QuarterSnapshot(
        "2019Q1",
        len(edge_rows),
        {product: 1 for product in products},
        {product: frozenset({f"maker-{product}"}) for product in products},
        frozenset(edge_rows),
        {edge: 1 for edge in edge_rows},
    )
    history = History.empty()
    history.add(snapshot, {})
    return history


class Q2MaudeBehaviorTests(unittest.TestCase):
    def test_graphsage_mean_and_none_gradients_match_finite_differences(self) -> None:
        reports = graphsage_gradient_preflight()
        self.assertEqual(set(reports), {"mean", "none"})
        for report in reports.values():
            self.assertLess(report["absolute_error"], 1e-6)

    def test_none_uses_no_neighbors_learns_for_every_seed_and_roundtrips(self) -> None:
        history = _history((("A", "10"), ("B", "10"), ("C", "20"), ("D", "20")))
        none_results = {}
        for seed in SEEDS:
            ranker, diagnostics = fit_graphsage(
                history,
                dimension=8,
                regularization=0.0005,
                seed=seed,
                epochs=30,
                learning_rate=0.02,
                fanout=8,
                aggregation="none",
                probe_limit=20_000,
                minimum_probe_loss_reduction=0.01,
            )
            self.assertTrue(diagnostics["state_changed"])
            self.assertGreaterEqual(diagnostics["probe_relative_loss_drop"], 0.01)
            self.assertTrue(diagnostics["learning_gate_passed"])
            self.assertEqual(diagnostics["probe_triplets"], 4)
            self.assertEqual(diagnostics["configuration"]["active_transform_parameters"], 64)
            self.assertEqual(diagnostics["configuration"]["fanout"], 0)
            none_results[seed] = (ranker, diagnostics)

        raw = none_results[103][1]["raw_checkpoint"]
        self.assertEqual(raw["product_neighbors"].shape[1], 0)
        self.assertEqual(raw["problem_neighbors"].shape[1], 0)
        expected_products = np.tanh(raw["product_inputs"] @ raw["self_weights"].T)
        expected_problems = np.tanh(raw["problem_inputs"] @ raw["self_weights"].T)
        np.testing.assert_allclose(
            np.asarray([none_results[103][0].product_vectors[node] for node in raw["products"]]),
            expected_products,
            rtol=0.0,
            atol=1e-12,
        )
        np.testing.assert_allclose(
            np.asarray([none_results[103][0].problem_vectors[node] for node in raw["problems"]]),
            expected_problems,
            rtol=0.0,
            atol=1e-12,
        )

        mean_ranker, mean_diagnostics = fit_graphsage(
            history,
            dimension=8,
            regularization=0.0005,
            seed=103,
            epochs=30,
            learning_rate=0.02,
            fanout=8,
            aggregation="mean",
            probe_limit=20_000,
            minimum_probe_loss_reduction=0.01,
        )
        self.assertEqual(
            none_results[103][1]["initialization_sha256"],
            mean_diagnostics["initialization_sha256"],
        )
        self.assertEqual(none_results[103][1]["probe"], mean_diagnostics["probe"])
        self.assertNotEqual(
            none_results[103][0].score("A", "10"),
            mean_ranker.score("A", "10"),
        )

        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "graphsage-none.npz"
            save_graphsage_checkpoint(checkpoint, raw)
            restored = load_graphsage_checkpoint(checkpoint)
        for product in raw["products"]:
            for problem in raw["problems"]:
                self.assertAlmostEqual(
                    none_results[103][0].score(product, problem),
                    restored.score(product, problem),
                    places=12,
                )

    def test_bpr_and_spectral_checkpoints_reconstruct_scores(self) -> None:
        history = _history((("A", "10"), ("B", "10"), ("C", "20"), ("D", "20")))
        fitted = (
            (
                "bpr",
                fit_bpr(
                    history,
                    dimension=8,
                    regularization=0.0001,
                    seed=103,
                    epochs=30,
                    learning_rate=0.03,
                ),
                save_bpr_checkpoint,
                load_bpr_checkpoint,
            ),
            (
                "spectral",
                fit_spectral(history, rank=2, power_iterations=12, seed=103),
                save_spectral_checkpoint,
                load_spectral_checkpoint,
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for family, (ranker, diagnostics), save_checkpoint, load_checkpoint in fitted:
                checkpoint = Path(temporary) / f"{family}.npz"
                save_checkpoint(checkpoint, diagnostics["raw_checkpoint"])
                restored = load_checkpoint(checkpoint)
                for product in history.product_problems:
                    for problem in history.problem_products:
                        self.assertAlmostEqual(
                            ranker.score(product, problem),
                            restored.score(product, problem),
                            places=12,
                        )

    def test_candidate_ties_keep_popularity_then_code_order(self) -> None:
        history = _history(
            (("A", "10"), ("B", "20"), ("C", "20"), ("D", "30"), ("E", "40"))
        )
        ranked = _rank_candidates(
            history,
            "2019Q2",
            "A",
            ("20", "30", "40"),
            "neighbor_frequency",
            None,
            {},
        )
        self.assertEqual([problem for problem, _ in ranked], ["20", "30", "40"])

    def test_boosted_repetitions_follow_actual_training_row_count(self) -> None:
        policy = {"seeds": list(SEEDS), "boosted_seed_threshold": 200_000}
        self.assertEqual(_family_seeds(policy, "boosted", 200_000), (0,))
        self.assertEqual(_family_seeds(policy, "boosted", 200_001), SEEDS)
        self.assertEqual(_family_seeds(policy, "bpr", 0), SEEDS)


if __name__ == "__main__":
    unittest.main()
