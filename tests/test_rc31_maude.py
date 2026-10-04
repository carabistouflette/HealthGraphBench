"""Deterministic synthetic RC3.1 MAUDE boundaries; no health experiment execution."""
from __future__ import annotations

import gzip
import json
import pickle
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path

import numpy as np

from healthgraphbench.q2 import maude_backend as backend
from healthgraphbench.rc31 import maude
from healthgraphbench.tasks.maude.data import DataAudit, DataBundle, ProblemStats, QuarterSnapshot
from healthgraphbench.tasks.maude.evaluate import first_edges
from healthgraphbench.tasks.maude.models import History


def snapshot(quarter, edges=(), reports=None):
    edge_set = frozenset(edges)
    if reports is None:
        reports = {p: 1 for p, _ in edge_set}
    return QuarterSnapshot(quarter, sum(reports.values()), reports, {}, edge_set, {edge: 1 for edge in edge_set})


def bundle(snapshots):
    audit_values = {field.name: 0 for field in fields(DataAudit)}
    audit_values.update(device_stats={}, problem_stats=ProblemStats())
    return DataBundle(tuple(snapshots), DataAudit(**audit_values), ())


def prepare(root, data):
    root.mkdir()
    with gzip.open(root / "maude_raw_bundle.pkl.gz", "wb") as output:
        pickle.dump({"bundle": data, "problem_parent_map": {}, "raw_sources": [], "task_manifest": {"synthetic": True}}, output)


class MaudeTargetedBoundaryTests(unittest.TestCase):
    def test_reassignment_is_deterministic_typed_degree_preserving_and_nonmutating(self):
        history = maude._synthetic_history()
        original = maude._edges(history)
        candidates = {p: history.candidate_problems(p) for p in history.product_reports}
        for seed in (303, 17):
            adjacency, stats = maude.reassign_adjacency(history, seed=seed)
            again, repeated = maude.reassign_adjacency(history, seed=seed)
            self.assertEqual(stats, repeated)
            self.assertEqual(maude._edges(adjacency), maude._edges(again))
            self.assertEqual(maude._edges(history), original)
            self.assertEqual({p: len(ds) for p, ds in history.product_problems.items()},
                             {p: len(ds) for p, ds in adjacency.product_problems.items()})
            self.assertEqual({d: len(ps) for d, ps in history.problem_products.items()},
                             {d: len(ps) for d, ps in adjacency.problem_products.items()})
            edges = maude._edges(adjacency)
            self.assertEqual(len(edges), len(set(edges)))
            self.assertTrue(all(p in history.product_problems and d in history.problem_products for p, d in edges))
            self.assertEqual(stats["attempted_swaps"], stats["accepted_swaps"] + stats["rejected_same_endpoint"] + stats["rejected_duplicate"])
            changed = len(set(original) - set(edges))
            self.assertEqual(stats["changed_fraction"], changed / len(original))
            self.assertGreater(stats["accepted_swaps"], 0)
        self.assertEqual(candidates, {p: history.candidate_problems(p) for p in history.product_reports})

    def test_unswitchable_and_empty_graph_boundaries(self):
        for edges in ((), (("A", "10"),), (("A", "10"), ("B", "10")),
                      (("A", "10"), ("A", "20"), ("B", "10"), ("B", "20"))):
            history = History.empty()
            history.add(snapshot("2022Q4", edges), {})
            reassigned, stats = maude.reassign_adjacency(history)
            self.assertEqual(maude._edges(reassigned), maude._edges(history))
            self.assertEqual(stats["accepted_swaps"], 0)
            self.assertEqual(stats["changed_fraction"], 0.0)
        with self.assertRaises(ValueError):
            maude.reassign_adjacency(History.empty(), attempts_per_edge=-1)

    def test_reassigned_fit_keeps_q2_initialization_probe_labels_and_raw_checkpoint(self):
        history = maude._synthetic_history()
        originals = maude._edges(history)
        with tempfile.TemporaryDirectory() as temporary:
            for seed in maude.SEEDS:
                real, real_diagnostics = backend.fit_graphsage(history, dimension=16,
                    regularization=0.000005, seed=seed, epochs=30, learning_rate=0.02, fanout=8)
                alternate, diagnostics = maude._fit_reassigned(history, seed, 20000, 0.01)
                self.assertEqual(real_diagnostics["probe"], diagnostics["probe"])
                self.assertEqual(real_diagnostics["initialization_sha256"], diagnostics["initialization_sha256"])
                self.assertEqual([r["steps"] for r in real_diagnostics["trace"]], [r["steps"] for r in diagnostics["trace"]])
                self.assertEqual(maude._edges(history), originals)
                self.assertEqual(len(diagnostics["trace"]), 30)
                self.assertTrue(diagnostics["state_changed"])
                self.assertTrue(diagnostics["learning_gate_passed"])
                self.assertGreater(diagnostics["probe_relative_loss_drop"], 0.01)
                raw = diagnostics["raw_checkpoint"]
                self.assertEqual(raw["product_inputs"].shape, (4, 16))
                self.assertEqual(raw["self_weights"].shape, (16, 16))
                checkpoint = Path(temporary) / f"seed{seed}.bin"
                backend.save_graphsage_checkpoint(checkpoint, raw)
                loaded = backend.load_graphsage_checkpoint(checkpoint)
                for p in history.product_problems:
                    for d in history.problem_products:
                        self.assertAlmostEqual(alternate.score(p, d), loaded.score(p, d), places=12)
                self.assertEqual(set(real.product_vectors), set(alternate.product_vectors))

    def test_workload_includes_known_products_without_labels_or_graph_edges(self):
        history = maude._synthetic_history()
        history.add(snapshot("2022Q4", reports={"EMPTY": 2, "ZERO": 0}), {})
        history.add(snapshot("2022Q4", (("FULL", "10"), ("FULL", "20"))), {})
        zero = backend.GraphSageRanker({}, {}, {})
        target = frozenset((("A", "20"), ("NEW", "10"), ("A", "NEW_CODE")))
        rows, scores, metrics = maude._quarter_rows(history, "2023Q1", target, {}, "graphsage_mean", zero)
        by_product = {row["entity_id"]: row for row in rows}
        self.assertEqual(set(by_product), set("ABCD") | {"EMPTY"})
        self.assertEqual(by_product["A"]["positive_ranks"], [1])
        self.assertEqual(by_product["EMPTY"]["positive_ranks"], [])
        self.assertEqual(by_product["EMPTY"]["candidate_count"], 2)
        self.assertEqual(metrics["workload"]["zero_positive_product_quarters"], 4)
        self.assertEqual(metrics["workload"]["top_k"]["100"]["proposal_slots"], 6)
        self.assertEqual(metrics["thresholds"]["1"]["positive_edges"], 1)
        for row, complete in zip(rows, scores, strict=True):
            self.assertEqual(len(complete["item_ids"]), row["candidate_count"])
            self.assertEqual(len(complete["scores"]), row["candidate_count"])
            self.assertEqual(row["positive_count"], len(row["positive_items"]))
            for item in row["positive_items"] + row["recommendations"]:
                self.assertGreaterEqual(item["prior_support"], 1)
                self.assertGreaterEqual(item["neighbor_support"], 0)
        self.assertNotIn("NEW", history.product_reports)
        self.assertNotIn("NEW_CODE", history.problem_products)

    def test_all_positive_ranks_beyond_top100_and_history_name_ties(self):
        history = History.empty()
        edges = [("A", "OWN")] + [("B", f"{i:03d}") for i in range(110)] + [("C", "002")]
        history.add(snapshot("2022Q4", edges), {})
        zero = backend.GraphSageRanker({}, {}, {})
        rows, complete, _ = maude._quarter_rows(history, "2023Q1", frozenset((("A", "109"),)), {}, "graphsage_mean", zero)
        row = next(r for r in rows if r["entity_id"] == "A")
        all_scores = next(r for r in complete if r["entity_id"] == "A")
        self.assertEqual(all_scores["item_ids"][:4], ["002", "000", "001", "003"])
        self.assertEqual(row["positive_ranks"], [110])
        self.assertEqual(row["positive_items"][0]["rank"], 110)
        self.assertEqual(len(row["recommendations"]), 100)
        self.assertEqual(row["workload_top_k"]["100"], {"proposal_slots": 100, "retrieved_links": 0})

    def test_bpr_raw_and_smoothing_reuse_identical_state_and_reject_wrong_history(self):
        history = maude._synthetic_history()
        published, diagnostics = backend.fit_bpr(history, dimension=16, regularization=0, seed=103, epochs=3)
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "checkpoint.bin"
            backend.save_bpr_checkpoint(checkpoint, diagnostics["raw_checkpoint"])
            digest = maude.sha256_file(checkpoint)
            (raw, smoothed), reused = maude._check_bpr_history(checkpoint, history, 103)
            self.assertFalse(reused["retrained"])
            self.assertEqual(digest, maude.sha256_file(checkpoint))
            state = diagnostics["raw_checkpoint"]
            for p, product in enumerate(state["products"]):
                self.assertEqual(raw.product_vectors[product], tuple(state["product_inputs"][p]))
                self.assertEqual(smoothed.product_vectors[product], published.product_vectors[product])
                neighbors = history.product_problems[product]
                indices = [state["problems"].index(d) for d in sorted(neighbors)]
                expected = 0.5 * state["product_inputs"][p] + 0.5 * np.mean(state["problem_inputs"][indices], axis=0)
                np.testing.assert_allclose(smoothed.product_vectors[product], expected, rtol=0, atol=1e-12)
            with self.assertRaises(ValueError):
                maude._check_bpr_history(checkpoint, history, 211)
            wrong = History.empty()
            wrong.add(snapshot("2022Q4", (("A", "20"), ("B", "10"), ("C", "20"), ("D", "10"))), {})
            with self.assertRaises(ValueError):
                maude._check_bpr_history(checkpoint, wrong, 103)

    def test_run_phase_checkpoint_input_hook_and_quarter_history_boundary(self):
        initial = snapshot("2022Q4", (("A", "10"), ("B", "10"), ("C", "20"), ("D", "20")))
        data = bundle((initial, snapshot("2023Q1", (("A", "20"), ("NEW", "30"))),
                       snapshot("2023Q2"), snapshot("2023Q3"), snapshot("2023Q4")))
        history = History.empty()
        history.add(initial, {})
        _, diagnostics = backend.fit_bpr(history, dimension=16, regularization=0, seed=103, epochs=3)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared = root / "prepared"
            prepare(prepared, data)
            source = root / "published.bin"
            backend.save_bpr_checkpoint(source, diagnostics["raw_checkpoint"])
            records = []
            for family in ("bpr_raw", "bpr_smoothed"):
                output = root / family
                output.mkdir()
                result = maude.run_phase(str(source), 2023, family, {}, 103, {"prepared_path": str(prepared)}, output)
                self.assertEqual(result["checkpoint_sha256"], maude.sha256_file(source))
                self.assertEqual(result["fit_cutoff"], "2022Q4")
                self.assertEqual(json.loads((output / "result.json").read_text())["primary_metric"], result["primary_metric"])
                with gzip.open(output / "predictions.jsonl.gz", "rt") as infile:
                    rows = [json.loads(line) for line in infile]
                with gzip.open(output / "all_candidate_scores.jsonl.gz", "rt") as infile:
                    score_rows = [json.loads(line) for line in infile]
                self.assertEqual(len(score_rows), len(rows))
                q1 = {r["entity_id"]: r for r in rows if r["period"] == "2023Q1"}
                q2 = {r["entity_id"]: r for r in rows if r["period"] == "2023Q2"}
                self.assertNotIn("NEW", q1)
                self.assertIn("NEW", q2)
                self.assertEqual(q1["A"]["candidate_count"], 1)
                self.assertEqual(q2["A"]["candidate_count"], 1)  # 20 removed only after Q1; 30 now known.
                self.assertEqual(q2["A"]["positive_count"], 0)
                self.assertEqual(q2["A"]["recommendations"][0]["item_id"], "30")
                self.assertEqual(q2["A"]["recommendations"][0]["score"], 0.0)
                self.assertEqual(result["workload"]["zero_positive_product_quarters"], len(rows) - 1)
                records.append(result)
            self.assertEqual(records[0]["candidate_fingerprint"], records[1]["candidate_fingerprint"])
            self.assertEqual(records[0]["target_fingerprint"], records[1]["target_fingerprint"])
            self.assertEqual(records[0]["checkpoint_sha256"], records[1]["checkpoint_sha256"])
            self.assertEqual(records[0]["training_edge_sha256"], records[1]["training_edge_sha256"])

    def test_origin_cutoff_uses_no_current_or_future_edges(self):
        data = bundle((snapshot("2022Q4", (("A", "10"),)), snapshot("2023Q1", (("B", "20"),)),
                       snapshot("2024Q1", (("C", "30"),))))
        observed = first_edges(data)
        history = maude.q2._history_before(data, "2023Q1", {})
        self.assertEqual(maude._edges(history), [("A", "10")])
        self.assertEqual(observed["2023Q1"], frozenset((("B", "20"),)))
        reassigned, _ = maude.reassign_adjacency(history)
        self.assertNotIn("B", reassigned.product_problems)
        self.assertNotIn("30", reassigned.problem_products)

    def test_protocol_boundaries_reject_unplanned_year_seed_family_and_graph_levels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared = root / "prepared"
            data = bundle((snapshot("2022Q4", (("A", "10"),)),))
            prepare(prepared, data)
            for year, seed, family, config in (
                (2026, 103, "bpr_raw", {}), (2023, 0, "bpr_raw", {}),
                (2023, 103, "bpr", {}), (2023, 103, "graphsage_mean", {"dimension": 32}),
                (2023, 103, "graphsage_mean", {"regularization": 0}),
                (2023, 103, "graphsage_mean", {"fanout": 3}),
                (2023, 103, "graphsage_mean", {"adjacency": "reassigned", "fanout": 16}),
                (2023, 103, "graphsage_mean", {"epochs": 1}),
                (2023, 103, "graphsage_mean", {"learning_rate": 0.03}),
                (2023, 103, "bpr_raw", {}),
            ):
                with self.subTest(year=year, seed=seed, family=family, config=config):
                    with self.assertRaises(ValueError):
                        maude.run_phase(str(prepared), year, family, config, seed, {}, root)

    def test_failed_training_only_gate_retains_state_before_any_ranking(self):
        data = bundle((snapshot("2022Q4", (("A", "10"), ("B", "10"), ("C", "20"), ("D", "20"))),
                       *(snapshot(f"2023Q{i}") for i in range(1, 5))))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared = root / "prepared"
            prepare(prepared, data)
            output = root / "phase"
            output.mkdir()
            with self.assertRaises(RuntimeError):
                maude.run_phase(str(prepared), 2023, "graphsage_mean",
                    dict(maude.GRAPH_CONFIGURATIONS[0]), 103,
                    {"learning_gate": {"minimum_relative_bpr_data_loss_reduction": 1.0}}, output)
            self.assertTrue((output / "checkpoint.bin").exists())
            failure = json.loads((output / "failed_learning_gate.json").read_text())
            self.assertFalse(failure["learning_gate_passed"])
            self.assertEqual(len(failure["trace"]), 30)
            self.assertEqual(failure["probe_triplets"], 4)
            self.assertTrue(failure["state_changed"])
            self.assertFalse((output / "predictions.jsonl.gz").exists())
            self.assertFalse((output / "all_candidate_scores.jsonl.gz").exists())


if __name__ == "__main__":
    unittest.main()
