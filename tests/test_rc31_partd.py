"""Isolated synthetic numerical and temporal Part D consumer regressions."""
from __future__ import annotations

import gzip
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from healthgraphbench.candidates.partd_model import _ProjectedRow
from healthgraphbench.data import sha256_file
from healthgraphbench.q2.partd import _save_all_candidate_scores
from healthgraphbench.rc31 import partd
from healthgraphbench.tasks.partd.task import PartDHistoryView, PartDTask


def _view(links: dict[str, set[str]]) -> PartDHistoryView:
    drugs = sorted({drug for values in links.values() for drug in values})
    return PartDHistoryView(2023, (2019, 2020, 2021, 2022),
                            {provider: frozenset(values) for provider, values in links.items()},
                            {drug: frozenset(p for p, values in links.items() if drug in values) for drug in drugs},
                            {provider: "X" if provider < "d" else "Y" for provider in links})


def _task(root: Path) -> PartDTask:
    root.mkdir(parents=True, exist_ok=True)
    (root / "edges.csv").write_text("synthetic boundary fixture\n", encoding="utf-8")
    (root / "report.json").write_text('{}\n', encoding="utf-8")
    links = {"a": {"x"}, "b": {"x", "y"}, "c": {"y", "z"}, "d": {"z"}}
    rows = {year: [] for year in range(2019, 2025)}
    for provider, values in links.items():
        for drug in sorted(values):
            rows[2019].append(_ProjectedRow(2019, provider, drug, 11, ("X",)))
            # Duplicate across years and large claims must not alter binary incidence.
            rows[2022].append(_ProjectedRow(2022, provider, drug, 99999, ("X",)))
    rows[2023] = [_ProjectedRow(2023, "a", "y", 11, ("TARGET_ONLY_SPECIALTY",)),
                  _ProjectedRow(2023, "b", "novel", 11, ("X",))]
    rows[2024] = [_ProjectedRow(2024, "a", "z", 11, ("X",))]
    return PartDTask(root, {"sources": {"kind": "synthetic"}}, root / "unused-contract.json",
                     {2023: set(links) | {"empty"}, 2024: set(links) | {"empty"}}, rows)


def _reused_fixture(task: PartDTask, phase: Path) -> None:
    phase.mkdir(parents=True)
    (phase / "model").mkdir()
    view = task.history_view("validation")
    checkpoint = phase / "model/checkpoint.npz"
    np.savez_compressed(checkpoint, providers=np.asarray(view.providers), drugs=np.asarray(view.drugs),
                        specialties=np.asarray(["X"]), provider_embeddings=np.ones((4, 32)),
                        drug_embeddings=np.ones((3, 32)), specialty_embeddings=np.ones((1, 32)))
    rows = task._rank_target(2023, lambda current, npi, candidates: {drug: float(current.global_support(drug)) for drug in candidates},
                             retain_candidate_scores=True)
    summary = _save_all_candidate_scores(task, 2023, rows, phase / "all_candidate_scores.npz")
    for row in rows:
        row.pop("candidate_scores")
    prediction_path = phase / "predictions.jsonl"
    prediction_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = {"family": "bpr", "configuration": partd.BPR_CONFIGURATION, "seed": 103, "target_year": 2023,
              "fit": {"epochs": 30, "specialty_weight": 0.35, "checkpoint_sha256": sha256_file(checkpoint),
                      "loss_before": {"sampled_objective": 1.0}, "loss_after": {"sampled_objective": 0.5}},
              "candidate_score_table": summary, "prediction_file_sha256": sha256_file(prediction_path)}
    (phase / "result.json").write_text(json.dumps(result), encoding="utf-8")


class BinaryNeighborsTests(unittest.TestCase):
    def test_binary_similarities_and_lexical_ties(self) -> None:
        view = _view({"a": {"x", "y"}, "b": {"x", "z"}, "c": {"y", "q"}, "d": {"q"}})
        neighbors = partd.HistoricalNeighbors(view)
        self.assertEqual(neighbors.table("common_count", 8)["a"], (("b", 1.0), ("c", 1.0)))
        self.assertEqual(neighbors.table("jaccard", 8)["a"], (("b", 1 / 3), ("c", 1 / 3)))
        self.assertEqual(neighbors.table("cosine", 8)["a"], (("b", 0.5), ("c", 0.5)))
        for family in partd.NEIGHBOR_FAMILIES:
            self.assertNotIn("a", dict(neighbors.table(family, 8)["a"]))
            self.assertNotIn("d", dict(neighbors.table(family, 8)["a"]))

    def test_weights_not_unweighted_votes_and_no_candidate_reselection(self) -> None:
        view = _view({"a": {"x", "y"}, "b": {"x", "y", "z"}, "c": {"x", "q"}})
        neighbors = partd.HistoricalNeighbors(view)
        score = neighbors.scorer("common_count", 1)
        self.assertEqual(score(view, "a", ("q", "z")), {"q": 0.0, "z": 2.0})
        self.assertEqual(score(view, "a", ("q",)), {"q": 0.0})
        self.assertEqual(score(view, "unknown", ("q", "z")), {"q": 0.0, "z": 0.0})
        with self.assertRaisesRegex(ValueError, "cutoff"):
            score(PartDHistoryView(2024, (), {}, {}, {}), "a", ("z",))

    def test_k_grid_and_fixed_top50_covariates(self) -> None:
        links = {"a": {"x"}, **{f"p{index:03}": {"x", "y"} for index in range(210)}}
        neighbors = partd.HistoricalNeighbors(_view(links))
        for k in partd.NEIGHBOR_KS:
            self.assertEqual(len(neighbors.table("cosine", k)["a"]), k)
        self.assertEqual(neighbors.fixed_support("a")["y"], 50)
        self.assertEqual(neighbors.table("cosine", 8)["a"][0][0], "p000")

    def test_neighbor_checkpoint_contains_actual_fixed_state(self) -> None:
        view = _view({"a": {"x"}, "b": {"x", "y"}, "c": {"z"}})
        neighbors = partd.HistoricalNeighbors(view)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.npz"
            neighbors.save(path, "cosine", 8)
            with np.load(path, allow_pickle=False) as raw:
                self.assertEqual(raw["providers"].tolist(), ["a", "b", "c"])
                self.assertEqual(raw["neighbor_indices"][0, 0], 1)
                self.assertAlmostEqual(raw["neighbor_weights"][0, 0], 1 / math.sqrt(2))
                self.assertTrue(np.all(raw["neighbor_indices"][2] == -1))
                self.assertEqual(raw["incidence_offsets"].tolist(), [0, 1, 3, 4])
                self.assertEqual(raw["year"].item(), 2023)

    def test_global_and_specialty_counts_are_binary(self) -> None:
        view = _view({"a": {"x"}, "b": {"y"}, "d": {"z"}})
        global_score, _ = partd._baseline(view, "global_popularity")
        specialty_score, _ = partd._baseline(view, "specialty_popularity")
        self.assertEqual(global_score(view, "a", ("y", "z")), {"y": 1.0, "z": 1.0})
        self.assertEqual(specialty_score(view, "a", ("y", "z")), {"y": 1.0, "z": 0.0})
        self.assertEqual(specialty_score(view, "unknown", ("y", "z")), {"y": 1.0, "z": 1.0})


class PartDWorkerBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.task = _task(self.root / "prepared")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_single_year_all_provider_zero_positive_portable_full_candidates(self) -> None:
        phase = self.root / "phase"
        phase.mkdir()
        with patch.object(PartDTask, "from_prepared_input", return_value=self.task):
            result = partd.run_phase(str(self.task.prepared_dir), 2023, "cosine", {"k": 8}, None, {}, phase)
        with gzip.open(phase / "predictions.jsonl.gz", "rt", encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream]
        self.assertEqual(len(rows), 5)
        self.assertEqual({row["year"] for row in rows}, {2023})
        by_id = {row["entity_id"]: row for row in rows}
        self.assertEqual(by_id["c"]["positive_items"], [])
        self.assertEqual(by_id["empty"]["history_support"], 0)
        self.assertEqual(by_id["a"]["history_support"], 1)
        self.assertEqual(by_id["a"]["positive_items"],
                         [{"item_id": "y", "rank": 1, "prior_support": 2, "neighbor_support": 1}])
        self.assertNotIn("novel", self.task.history_view("validation").drugs)
        self.assertEqual(self.task.history_view("validation").prior_specialty("a"), "X")
        with np.load(phase / "all_candidate_scores.npz", allow_pickle=False) as raw:
            self.assertEqual(len(raw["provider_ids"]), 5)
            self.assertEqual(len(raw["candidate_scores"]), sum(row["candidate_count"] for row in rows))
            self.assertNotIn("novel", raw["drug_ids"].tolist())

    def test_target_changes_do_not_change_covariates_scores_or_candidates(self) -> None:
        view = self.task.history_view("validation")
        neighbors = partd.HistoricalNeighbors(view)
        score = neighbors.scorer("cosine", 8)
        first = self.task._rank_target(2023, score, retain_candidate_scores=True)
        first_candidates, first_targets = partd._portable_rows(first, view, neighbors)
        self.task.rows_by_year[2023].append(_ProjectedRow(2023, "a", "z", 1000000, ("LEAK",)))
        second = self.task._rank_target(2023, score, retain_candidate_scores=True)
        second_candidates, second_targets = partd._portable_rows(second, self.task.history_view("validation"), neighbors)
        self.assertEqual(first_candidates, second_candidates)
        self.assertNotEqual(first_targets, second_targets)
        self.assertEqual(first[0]["candidate_scores"], second[0]["candidate_scores"])
        self.assertEqual(first[0]["recommendations"], second[0]["recommendations"])
        self.assertEqual(first[0]["positive_items"], second[0]["positive_items"][:1])
        self.assertIn("novel", self.task.history_view("test").drugs)
        self.assertEqual(self.task.history_view("test").prior_specialty("a"), None)

    def test_portable_recommendations_cover_declared_workload_top100(self) -> None:
        links = {"a": {"own"}, "b": {"own", *[f"d{index:03}" for index in range(125)]}}
        view = _view(links)
        scores = {drug: 0.0 for drug in view.candidate_ids("a")}
        row = {"npi": "a", "year": 2023, "positives": ["d124"], "candidate_scores": scores}
        partd._portable_rows([row], view, partd.HistoricalNeighbors(view))
        self.assertEqual(len(row["recommendations"]), 100)
        self.assertEqual(row["positive_items"][0]["rank"], 125)
        self.assertEqual(row["recommendations"][0]["item_id"], "d000")

    def test_selected_bpr_reuse_attaches_covariates_and_does_not_fit(self) -> None:
        source = self.root / "source"
        _reused_fixture(self.task, source)
        phase = self.root / "reused"
        phase.mkdir()
        with patch.object(PartDTask, "from_prepared_input", return_value=self.task), \
             patch.object(partd, "fit_graphsage", side_effect=AssertionError("no fit allowed")):
            result = partd.run_phase(str(self.task.prepared_dir), 2023, "bpr_reuse", partd.BPR_CONFIGURATION,
                                     103, {"reuse_phase_path": str(source),
                                           "reuse_prepared_path": str(self.task.prepared_dir)}, phase)
        self.assertFalse(result["fit"]["fit_performed"])
        self.assertEqual(sha256_file(source / "model/checkpoint.npz"), result["checkpoint_sha256"])
        self.assertEqual(result["parameter_count"], (4 + 3 + 1) * 32)
        with gzip.open(phase / "predictions.jsonl.gz", "rt") as stream:
            self.assertTrue(all("history_support" in json.loads(line) for line in stream))

    def test_reuse_rejects_target_drift_and_different_history(self) -> None:
        source = self.root / "source"
        _reused_fixture(self.task, source)
        other = _task(self.root / "other")
        self.task.rows_by_year[2023].append(_ProjectedRow(2023, "c", "x", 11, ("X",)))
        with patch.object(PartDTask, "from_prepared_input", return_value=other):
            with self.assertRaisesRegex(ValueError, "target/ranking mismatch"):
                partd.consume_reused_bpr(self.task, 2023, source, 103, other.prepared_dir)
        other.rows_by_year[2019].append(_ProjectedRow(2019, "a", "z", 11, ("X",)))
        with patch.object(PartDTask, "from_prepared_input", return_value=other):
            with self.assertRaisesRegex(ValueError, "pre-target history mismatch"):
                partd.consume_reused_bpr(self.task, 2023, source, 103, other.prepared_dir)

    def test_reuse_rejects_corrupt_candidate_mapping_even_with_updated_hash(self) -> None:
        source = self.root / "source"
        _reused_fixture(self.task, source)
        path = source / "all_candidate_scores.npz"
        with np.load(path, allow_pickle=False) as raw:
            values = {key: raw[key].copy() for key in raw.files}
        values["candidate_drug_indices"][0] = 0
        np.savez_compressed(path, **values)
        result_path = source / "result.json"
        result = json.loads(result_path.read_text())
        result["candidate_score_table"]["sha256"] = sha256_file(path)
        result_path.write_text(json.dumps(result))
        with patch.object(PartDTask, "from_prepared_input", return_value=self.task):
            with self.assertRaisesRegex(ValueError, "exact candidate mapping mismatch"):
                partd.consume_reused_bpr(self.task, 2023, source, 103, self.task.prepared_dir)

    def test_request_grid_seed_and_fixed_settings_are_locked(self) -> None:
        for configuration in partd.GRAPH_SAGE_GRID:
            partd._validate_request("graphsage", configuration, 103, {})
        invalid = [("cosine", {"k": 7}, None, {}), ("cosine", {"k": 8}, 103, {}),
                   ("global_popularity", {}, 103, {}),
                   ("graphsage", partd.GRAPH_SAGE_GRID[0], 103, {"fanout": 4}),
                   ("graphsage", partd.GRAPH_SAGE_GRID[0], 999, {}),
                   ("bpr_reuse", partd.BPR_CONFIGURATION, 103, {})]
        for family, configuration, seed, fixed in invalid:
            with self.subTest(family=family, configuration=configuration, seed=seed, fixed=fixed):
                with self.assertRaises(ValueError):
                    partd._validate_request(family, configuration, seed, fixed)

    def test_graphsage_adapter_contains_only_original_binary_history(self) -> None:
        history = partd._graph_history(self.task.history_view("validation"))
        self.assertEqual(history.product_problems["a"], {"x"})
        self.assertEqual(history.problem_products["x"], {"a", "b"})
        self.assertNotIn("novel", history.problem_products)
        self.assertNotIn("empty", history.product_problems)
        self.assertFalse(history.product_manufacturers)

    def test_graphsage_numerical_preflight_learning_and_checkpoint(self) -> None:
        result = partd.preflight()
        self.assertTrue(result["learning_gate_passed"])
        self.assertFalse(result["health_data_executed"])
        self.assertLessEqual(result["checkpoint_max_score_error"], 1e-12)
        self.assertTrue(math.isfinite(result["probe_relative_loss_drop"]))




if __name__ == "__main__":
    unittest.main()
