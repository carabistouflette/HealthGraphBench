"""Behavioral tests for the historical ClinicalTrials.gov/AACT feasibility gate."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import unittest
import zipfile
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from healthgraphbench.candidates.clinical_trials import (
    REQUIRED_TABLES,
    SNAPSHOT_DATES,
    _archive_url,
    run_gate,
)


HEADERS = {
    "studies.txt": [
        "nct_id",
        "study_first_posted_date",
        "results_first_posted_date",
        "primary_completion_date_type",
        "primary_completion_date",
        "study_type",
        "phase",
        "enrollment",
        "number_of_arms",
        "number_of_groups",
        "start_date",
        "is_fda_regulated_drug",
        "is_fda_regulated_device",
    ],
    "conditions.txt": ["nct_id", "name"],
    "interventions.txt": ["nct_id", "name"],
    "sponsors.txt": ["nct_id", "lead_or_collaborator", "name"],
    "facilities.txt": ["nct_id", "name"],
    "designs.txt": [
        "nct_id",
        "allocation",
        "intervention_model",
        "primary_purpose",
        "time_perspective",
        "masking",
    ],
}

# Each pair has a target at the origin and an observable positive/negative label
# in the immediately following snapshot. The dates are deliberately near the
# first-of-month snapshots so the origin lag rule is exercised.
TARGETS = [
    ("2019-01-01", "NCT00000001", "2019-06-01"),
    ("2019-01-01", "NCT00000011", None),
    ("2020-01-01", "NCT00000002", "2020-06-01"),
    ("2020-01-01", "NCT00000012", None),
    ("2021-01-01", "NCT00000004", "2021-06-01"),
    ("2021-01-01", "NCT00000014", None),
    ("2022-02-01", "NCT00000005", "2022-08-01"),
    ("2022-02-01", "NCT00000015", None),
    ("2023-02-01", "NCT00000006", "2023-06-01"),
    ("2023-02-01", "NCT00000016", None),
    ("2024-02-01", "NCT00000007", "2024-06-01"),
    ("2024-02-01", "NCT00000017", None),
]


def _row_values(header: list[str], row: dict[str, object]) -> list[str]:
    return ["" if row.get(field) is None else str(row[field]) for field in header]


def _study_row(nct_id: str, completion: str, results: str | None) -> dict[str, object]:
    return {
        "nct_id": nct_id,
        "study_first_posted_date": "2017-01-15",
        "results_first_posted_date": results,
        "primary_completion_date_type": "Actual",
        "primary_completion_date": completion,
        "study_type": "Interventional",
        "phase": "Phase 2",
        "enrollment": "100",
        "number_of_arms": "2",
        "number_of_groups": "2",
        "start_date": completion[:4] + "-01-01",
        "is_fda_regulated_drug": "t",
        "is_fda_regulated_device": "f",
    }


def _write_aact_fixture(
    root: Path,
    missing_future: tuple[str, str] | None = None,
    origin_inconsistent_future: tuple[str, str] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    parsed_dates = [date.fromisoformat(value) for value in SNAPSHOT_DATES]
    manifest_entries: list[dict[str, object]] = []
    for index, snapshot_text in enumerate(SNAPSHOT_DATES):
        snapshot = date.fromisoformat(snapshot_text)
        studies: list[dict[str, object]] = [
            _study_row("NCT00000090", "2017-01-01", "2017-06-01"),
        ]
        for origin_text, nct_id, result_date in TARGETS:
            origin = date.fromisoformat(origin_text)
            if snapshot < origin:
                continue
            origin_index = parsed_dates.index(origin)
            future_date = parsed_dates[origin_index + 1]
            if missing_future == (origin_text, nct_id) and snapshot == future_date:
                continue
            if origin_inconsistent_future == (origin_text, nct_id) and snapshot >= future_date:
                visible_result = (origin - timedelta(days=1)).isoformat()
            else:
                visible_result = result_date if result_date and snapshot >= future_date else None
            completion = (
                date(origin.year - 1, 12, 15)
                if origin.month == 1
                else date(origin.year, origin.month - 1, 15)
            )
            studies.append(_study_row(nct_id, completion.isoformat(), visible_result))
        study_ids = [str(row["nct_id"]) for row in studies]
        table_rows: dict[str, list[dict[str, object]]] = {
            "studies.txt": studies,
            "conditions.txt": [{"nct_id": nct_id, "name": "Condition Alpha"} for nct_id in study_ids],
            "interventions.txt": [{"nct_id": nct_id, "name": "Intervention Alpha"} for nct_id in study_ids],
            "sponsors.txt": [
                {"nct_id": nct_id, "lead_or_collaborator": "Lead Sponsor", "name": "Sponsor Alpha"}
                for nct_id in study_ids
            ]
            + [
                {"nct_id": nct_id, "lead_or_collaborator": "Collaborator", "name": "Collaborator Alpha"}
                for nct_id in study_ids
            ],
            "facilities.txt": [{"nct_id": nct_id, "name": "Facility Alpha"} for nct_id in study_ids],
            "designs.txt": [
                {
                    "nct_id": nct_id,
                    "allocation": "Randomized",
                    "intervention_model": "Parallel",
                    "primary_purpose": "Treatment",
                    "time_perspective": "Prospective",
                    "masking": "Double",
                }
                for nct_id in study_ids
            ],
        }
        archive_path = root / f"aact_{snapshot_text}_export_ctgov.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for table_name in REQUIRED_TABLES:
                lines = ["|".join(HEADERS[table_name])]
                lines.extend(
                    "|".join(_row_values(HEADERS[table_name], row))
                    for row in table_rows[table_name]
                )
                archive.writestr(table_name, "\n".join(lines) + "\n")
        manifest_entries.append(
            {
                "snapshot_date": snapshot_text,
                "path": archive_path.name,
                "url": _archive_url(snapshot_text),
                "bytes": archive_path.stat().st_size,
                "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                "headers": HEADERS,
                "retrieved_at": "2026-09-16T00:00:00Z",
                "historical_published_at": None,
            }
        )
    manifest = {
        "dataset": "clinical_trials_reporting",
        "version": "0.2-candidate-clinical-trials",
        "format": "aact_pipe_delimited_flat_file_zip",
        "files": manifest_entries,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


class ClinicalTrialsFeasibilityTests(unittest.TestCase):
    def test_historical_origin_labels_coverage_and_rolling_models(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "aact"
            manifest = _write_aact_fixture(root)
            report = run_gate(root, manifest, Path(temporary) / "run", cohort_size=10)
            self.assertEqual(report["decision"], "REVIEW_REQUIRED")
            self.assertEqual(report["graph_model_status"], "no_go_for_escalation")
            self.assertTrue(report["historical_availability_verified"])
            validation = report["metrics"]["validation_origin"]
            test = report["metrics"]["held_out_test_origin"]
            for metrics in (validation, test):
                self.assertEqual(metrics["trial_local_logistic"]["trial_count"], 2)
                self.assertEqual(metrics["trial_local_logistic"]["positive_count"], 1)
                self.assertIsNotNone(metrics["trial_local_logistic"]["average_precision"])
                self.assertIsNotNone(metrics["sponsor_history_logistic"]["roc_auc"])
                self.assertIsNotNone(metrics["heterogeneous_context_logistic"]["log_loss"])
            self.assertIsInstance(
                report["metric_deltas"]["pooled"]["heterogeneous_context_minus_sponsor_history_average_precision"],
                float,
            )
            self.assertEqual(report["future_label_audits"]["2023-02-01"]["positive_trials"], 1)
            self.assertEqual(report["future_label_audits"]["2024-02-01"]["positive_trials"], 1)
            coverage = report["coverage"]["2023-02-01"]
            self.assertEqual(coverage["sponsor"]["relation_present"], 2)
            self.assertEqual(coverage["sponsor"]["history_present"], 2)
            self.assertEqual(coverage["isolated_target_trials"], 0)
            self.assertIn("sponsor_history_minus_trial_local_average_precision", report["metric_deltas"]["pooled"])
            predictions = [
                json.loads(line)
                for line in (Path(temporary) / "run" / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(predictions), 4)
            self.assertTrue(all(set(row["scores"]) == {
                "trial_local_logistic",
                "sponsor_history_logistic",
                "heterogeneous_context_logistic",
            } for row in predictions))

    def test_missing_future_snapshot_rows_are_excluded(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "aact"
            manifest = _write_aact_fixture(root, missing_future=("2020-01-01", "NCT00000002"))
            report = run_gate(root, manifest, Path(temporary) / "run", cohort_size=10)
            future_audit = report["future_label_audits"]["2020-01-01"]
            self.assertEqual(future_audit["missing_trials"], 1)
            self.assertEqual(future_audit["missing_trial_ids"], ["NCT00000002"])
            self.assertEqual(future_audit["selected_trials"], 2)
            self.assertEqual(future_audit["observed_trials"], 1)
            self.assertEqual(report["training"]["trial_count"], 7)

    def test_future_pre_origin_result_is_excluded(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "aact"
            manifest = _write_aact_fixture(
                root,
                origin_inconsistent_future=("2020-01-01", "NCT00000002"),
            )
            report = run_gate(root, manifest, Path(temporary) / "run", cohort_size=10)
            future_audit = report["future_label_audits"]["2020-01-01"]
            self.assertEqual(future_audit["origin_inconsistent_trials"], 1)
            self.assertEqual(future_audit["origin_inconsistent_trial_ids"], ["NCT00000002"])
            self.assertEqual(future_audit["selected_trials"], 2)
            self.assertEqual(future_audit["future_rows_seen"], 2)
            self.assertEqual(future_audit["observed_trials"], 1)
            self.assertEqual(report["training"]["trial_count"], 7)

    def test_cli_smoke_and_output_immutability(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "aact"
            manifest = _write_aact_fixture(root)
            output = Path(temporary) / "cli-run"
            environment = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
            command = [
                sys.executable,
                "scripts/run_clinical_trials_gate.py",
                "--source-root",
                str(root),
                "--manifest",
                str(manifest),
                "--output-dir",
                str(output),
                "--cohort-size",
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
            self.assertIn(b"REVIEW_REQUIRED", first_report)
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

    def test_source_hash_drift_fails_before_writing_output(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "aact"
            manifest = _write_aact_fixture(root)
            drifted = root / "aact_2023-02-01_export_ctgov.zip"
            with drifted.open("ab") as handle:
                handle.write(b"drift")
            output = Path(temporary) / "drift-run"
            with self.assertRaises(ValueError):
                run_gate(root, manifest, output, cohort_size=10)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
