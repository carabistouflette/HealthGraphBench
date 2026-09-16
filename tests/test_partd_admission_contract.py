"""Contract tests for the admitted Part D v0.2 replication task."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class PartDAdmissionContractTests(unittest.TestCase):
    def test_contract_freezes_partd_semantics_and_evaluation(self) -> None:
        contract = json.loads(
            (ROOT / "configs" / "task_contract_v0_2.json").read_text(encoding="utf-8")
        )
        task = contract["task"]
        self.assertEqual(contract["version"], "0.2")
        self.assertEqual(task["id"], "partd_prescriber_drug")
        self.assertEqual(task["admission_status"], "admitted_v0_2_replication_task")
        self.assertEqual(task["drug_identity"], "exact_trimmed_generic_name")
        self.assertEqual(
            task["temporal_split"]["validation"]["history_years"],
            [2019, 2020, 2021, 2022],
        )
        self.assertEqual(
            task["temporal_split"]["held_out_test"]["history_years"],
            [2019, 2020, 2021, 2022, 2023],
        )
        self.assertIn("rank every drug observed globally", task["candidate_construction"])
        self.assertEqual(
            task["metrics"]["positive_containing"],
            [
                "micro Recall@5",
                "micro Recall@10",
                "micro Recall@20",
                "provider-macro Recall@5",
                "provider-macro Recall@10",
                "provider-macro Recall@20",
                "MRR",
            ],
        )
        self.assertEqual(
            task["metrics"]["all_eligible_provider_year"],
            ["precision@5", "precision@10", "precision@20", "recommendation burden at K"],
        )
        self.assertEqual(task["temporal_split"]["target_rows_are_scored_before_history_update"], True)
        self.assertEqual(
            task["ranking_tie_policy"],
            {
                "primary_key": "model score descending",
                "secondary_key": "prior global provider support descending",
                "final_tie_key": "canonical source-native drug key ascending",
                "canonical_candidate_id": "exact trimmed generic_name",
            },
        )
        self.assertEqual(
            [model["name"] for model in task["baselines_and_models_already_run"]],
            ["specialty_popularity", "history_overlap", "tabular_logistic", "graph_bpr"],
        )
        self.assertIn("suppresses provider-drug combinations", task["suppression_limitation"])

    def test_candidate_registry_points_to_admission_contract(self) -> None:
        registry = json.loads(
            (ROOT / "configs" / "task_candidates_v0_2.json").read_text(encoding="utf-8")
        )
        partd = registry["tasks"]["partd_prescriber_drug"]
        self.assertEqual(partd["benchmark_admission"], "admitted_v0_2")
        self.assertEqual(partd["admission_contract"], "configs/task_contract_v0_2.json")
        self.assertEqual(partd["model_gate"], "no_go_for_escalation")


if __name__ == "__main__":
    unittest.main()
