"""Behavioral guards for the MAUDE aggregation ablation runner."""

from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from healthgraphbench.tasks.maude.ablation import (
    COMMON_DURATION_EPOCHS,
    _assert_candidate_sets_match,
    _assert_population_matches,
    _common_duration_lock,
    _verify_artifact,
    _validate_checkpoint,
)
from healthgraphbench.tasks.maude.diagnostic import VALIDATION_POPULATION
from healthgraphbench.tasks.maude.models import History, fit_graphsage


class MaudeAggregationAblationTests(unittest.TestCase):
    @staticmethod
    def _validation(score: float, status: str = "complete") -> dict[str, object]:
        return {
            "status": status,
            "duration_epochs": COMMON_DURATION_EPOCHS,
            "population": dict(VALIDATION_POPULATION),
            "validation": {"thresholds": {"1": {"recall_at_10": score}}},
        }

    def test_incomplete_baseline_population_is_rejected(self) -> None:
        incomplete = dict(VALIDATION_POPULATION)
        incomplete["candidate_pairs"] -= 1

        with self.assertRaisesRegex(ValueError, "candidate_pairs"):
            _assert_population_matches(incomplete, VALIDATION_POPULATION, "C mean30 validation")

    def test_duration_lock_is_common_30_even_when_none_validation_score_is_higher(self) -> None:
        lock = _common_duration_lock(
            mean_validation=self._validation(0.1),
            none_validation=self._validation(0.9),
            none_population=VALIDATION_POPULATION,
            cohorts_match=True,
        )

        self.assertEqual(lock["common_duration_epochs"], COMMON_DURATION_EPOCHS)
        self.assertEqual(lock["validation_micro_recall_at_10"], {"mean30_reused": 0.1, "none30_new": 0.9})
        self.assertIs(lock["test_scores_consulted"], False)

    def test_lock_refuses_incomplete_validation_before_any_test_transition(self) -> None:
        with self.assertRaisesRegex(ValueError, "complete mean and none validation"):
            _common_duration_lock(
                mean_validation=self._validation(0.2, status="incomplete"),
                none_validation=self._validation(0.3),
                none_population=VALIDATION_POPULATION,
                cohorts_match=True,
            )
        with self.assertRaisesRegex(ValueError, "matching validation candidate cohorts"):
            _common_duration_lock(
                mean_validation=self._validation(0.2),
                none_validation=self._validation(0.3),
                none_population=VALIDATION_POPULATION,
                cohorts_match=False,
            )

    def test_changed_labels_or_candidate_universe_blocks_cohort_match(self) -> None:
        base = {
            "quarter": "2023Q1",
            "product": "P1",
            "candidate_ids": ["A", "B"],
            "candidate_set_sha256": "same-candidate-hash",
            "positive_problem_ids": ["B"],
            "history_product_reports": 4,
        }
        changed = dict(base, positive_problem_ids=["A"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_path = root / "baseline.jsonl.gz"
            new_path = root / "none.jsonl.gz"
            for path, record in ((baseline_path, base), (new_path, changed)):
                with gzip.open(path, "wt", encoding="utf-8") as output:
                    output.write(json.dumps(record) + "\n")

            with self.assertRaisesRegex(ValueError, "candidate ids, positives, or support differ"):
                _assert_candidate_sets_match(baseline_path, new_path, "validation_2023/2023Q1")

    def test_modified_pinned_baseline_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "retained.bin").write_bytes(b"modified")
            original_hash = hashlib.sha256(b"original").hexdigest()
            inventory = {
                "retained.bin": {
                    "path": "retained.bin",
                    "size_bytes": len(b"original"),
                    "sha256": original_hash,
                }
            }

            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                _verify_artifact(inventory, root, "retained.bin")

    def test_raw_checkpoint_maps_cover_nodes_and_missing_input_is_rejected(self) -> None:
        history = History.empty()
        for product, problem in (("P1", "A"), ("P2", "B")):
            history.product_problems[product].add(problem)
            history.problem_products[problem].add(product)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "checkpoint.json.gz"
            for aggregation, shared_scalars in (("mean", 128), ("none", 64)):
                states: list[dict[str, object]] = []
                fit_graphsage(
                    history, epochs=30, aggregation=aggregation, on_checkpoint=states.append
                )
                state = states[0]
                with gzip.open(path, "wt", encoding="utf-8") as output:
                    json.dump(state, output)
                capacity = _validate_checkpoint(path, aggregation=aggregation)
                self.assertEqual(32, capacity["active_node_vector_scalars"])
                self.assertEqual(32 + shared_scalars, capacity["active_parameter_scalars"])
                del state["product_inputs"]["P2"]
                with gzip.open(path, "wt", encoding="utf-8") as output:
                    json.dump(state, output)
                with self.assertRaisesRegex(ValueError, "product vectors do not cover"):
                    _validate_checkpoint(path, aggregation=aggregation)


if __name__ == "__main__":
    unittest.main()
