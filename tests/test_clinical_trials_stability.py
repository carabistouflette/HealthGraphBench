"""Behavioral tests for the rolling-origin ClinicalTrials stability analysis."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from healthgraphbench.candidates.clinical_trials_stability import (
    ALL_CONTEXT_GROUP,
    MODEL_GROUPS,
    run_stability_gate,
)
from tests.test_clinical_trials_feasibility import _write_aact_fixture


class ClinicalTrialsStabilityTests(unittest.TestCase):
    def test_rolling_origins_ablation_and_trial_bootstrap(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "aact"
            manifest = _write_aact_fixture(root)
            report = run_stability_gate(
                root,
                manifest,
                Path(temporary) / "run",
                cohort_size=10,
                bootstrap_resamples=25,
            )
            self.assertEqual(
                list(report["rolling_origins"]),
                ["2020-01-01", "2021-01-01", "2022-02-01", "2023-02-01", "2024-02-01"],
            )
            self.assertNotIn("pooled", report["rolling_origins"])
            for index, (origin, result) in enumerate(report["rolling_origins"].items()):
                self.assertEqual(result["evaluation_trial_count"], 2)
                self.assertEqual(result["training_trial_count"], 2 * (index + 1))
                self.assertEqual(set(result["metrics"]), set(MODEL_GROUPS))
                self.assertIn(ALL_CONTEXT_GROUP, result["average_precision_deltas"])
                uncertainty = result["uncertainty"]["all_context_minus_sponsor_average_precision"]
                self.assertEqual(uncertainty["cluster_unit"], "trial")
                self.assertEqual(uncertainty["resamples"], 25)
                self.assertLess(uncertainty["valid_resamples"], 25)
                self.assertEqual(
                    set(result["uncertainty"]),
                    {
                        "local_plus_sponsor_minus_trial_local_average_precision",
                        "condition_minus_trial_local_average_precision",
                        "condition_increment_over_sponsor_average_precision",
                        "facility_minus_trial_local_average_precision",
                        "facility_increment_over_sponsor_average_precision",
                        "intervention_minus_trial_local_average_precision",
                        "intervention_increment_over_sponsor_average_precision",
                        "collaborator_minus_trial_local_average_precision",
                        "collaborator_increment_over_sponsor_average_precision",
                        "all_context_minus_trial_local_average_precision",
                        "all_context_minus_sponsor_average_precision",
                    },
                )
            summary = report["stability_summary"][ALL_CONTEXT_GROUP]
            self.assertEqual(summary["versus_local_plus_sponsor"]["origins_evaluated"], 5)
            self.assertEqual(len(summary["versus_local_plus_sponsor"]["values_by_origin"]), 5)
            rows = (Path(temporary) / "run" / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 10)

    def test_cli_smoke_and_output_immutability(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "aact"
            manifest = _write_aact_fixture(root)
            output = Path(temporary) / "cli-run"
            environment = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
            command = [
                sys.executable,
                "scripts/run_clinical_trials_stability.py",
                "--source-root",
                str(root),
                "--manifest",
                str(manifest),
                "--output-dir",
                str(output),
                "--cohort-size",
                "10",
                "--bootstrap-resamples",
                "10",
            ]
            completed = subprocess.run(
                command,
                cwd=Path(__file__).parents[1],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            first_report = (output / "report.json").read_bytes()
            first_predictions = (output / "predictions.jsonl").read_bytes()
            parsed = json.loads(first_report)
            self.assertEqual(parsed["stability_gate_status"], "complete")
            replay = subprocess.run(
                command,
                cwd=Path(__file__).parents[1],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(replay.returncode, 0)
            self.assertEqual(first_report, (output / "report.json").read_bytes())
            self.assertEqual(first_predictions, (output / "predictions.jsonl").read_bytes())


if __name__ == "__main__":
    unittest.main()
