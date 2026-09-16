"""Behavioral tests for the CMS Part D feasibility gate."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from healthgraphbench.candidates.partd import run_gate
from healthgraphbench.candidates.partd_model import run_model_gate
from healthgraphbench.data import sha256_file

HEADER = [
    "Prscrbr_NPI",
    "Brnd_Name",
    "Gnrc_Name",
    "Prscrbr_Type",
    "Prscrbr_State_Abrvtn",
    "Tot_Clms",
    "Tot_Drug_Cst",
    "Tot_Benes",
]
NPIS = [
    "1000000001",
    "1000000002",
    "1000000003",
    "1000000004",
    "1000000005",
]
BASE_2021 = {
    "1000000001": [("A", "A")],
    "1000000002": [("B", "B")],
    "1000000003": [("B", "B")],
    "1000000004": [("C", "C")],
    "1000000005": [("A", "A"), ("C", "C")],
}


def _rows_for_year(
    year: int,
    *,
    blank_p1_specialty: bool = False,
    empty_positive_window: bool = False,
    future_npi: bool = False,
    duplicate_first_row: bool = False,
    low_claims: bool = False,
) -> list[dict[str, str]]:
    if year == 2021 or empty_positive_window or year == 2023 and future_npi:
        drugs = {npi: list(values) for npi, values in BASE_2021.items()}
    elif year == 2022:
        drugs = {npi: list(values) for npi, values in BASE_2021.items()}
        drugs[NPIS[0]] = [("C", "C"), ("D", "D")]
    elif year == 2023:
        drugs = {npi: list(values) for npi, values in BASE_2021.items()}
        drugs[NPIS[0]] = [("A", "A"), ("B", "B"), ("D", "D")]
    else:
        raise AssertionError(year)
    rows: list[dict[str, str]] = []
    for npi in NPIS:
        specialty = "X" if npi in {NPIS[0], NPIS[3], NPIS[4]} else "Y"
        if blank_p1_specialty and npi == NPIS[0]:
            specialty = ""
        for brand, generic in drugs[npi]:
            rows.append(
                {
                    "Prscrbr_NPI": npi,
                    "Brnd_Name": brand,
                    "Gnrc_Name": generic,
                    "Prscrbr_Type": specialty,
                    "Prscrbr_State_Abrvtn": "TX",
                    "Tot_Clms": "10" if low_claims and npi == NPIS[0] else "11",
                    "Tot_Drug_Cst": "100",
                    "Tot_Benes": "",
                }
            )
    if future_npi and year == 2023:
        rows.append(
            {
                "Prscrbr_NPI": "1000000006",
                "Brnd_Name": "Z",
                "Gnrc_Name": "Z",
                "Prscrbr_Type": "Z",
                "Prscrbr_State_Abrvtn": "TX",
                "Tot_Clms": "11",
                "Tot_Drug_Cst": "100",
                "Tot_Benes": "",
            }
        )
    if duplicate_first_row:
        rows.append(dict(rows[0]))
    return rows


def _write_fixture(
    root: Path,
    *,
    blank_p1_specialty: bool = False,
    empty_positive_window: bool = False,
    future_npi: bool = False,
    duplicate_first_row: bool = False,
    low_claims: bool = False,
    missing_header: bool = False,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    actual_header = [column for column in HEADER if not (missing_header and column == "Prscrbr_Type")]
    entries: list[dict[str, object]] = []
    for year in (2021, 2022, 2023):
        path = root / f"partd_{year}.csv"
        rows = _rows_for_year(
            year,
            blank_p1_specialty=blank_p1_specialty,
            empty_positive_window=empty_positive_window,
            future_npi=future_npi,
            duplicate_first_row=duplicate_first_row and year == 2021,
            low_claims=low_claims and year == 2021,
        )
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=actual_header, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({column: row[column] for column in actual_header})
        entries.append(
            {
                "path": path.name,
                "year": year,
                "url": f"https://fixture.invalid/partd_{year}.csv",
                "dataset_id": f"fixture-{year}",
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "header": actual_header,
                "retrieved_at": "2026-09-01T00:00:00Z",
                "historical_published_at": None,
            }
        )
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "0.2-candidate",
                "dataset": "partd_prescriber_drug",
                "landing_url": "https://fixture.invalid/landing",
                "dictionary_url": "https://fixture.invalid/dictionary",
                "methodology_url": "https://fixture.invalid/methodology",
                "files": entries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _write_lookback_fixture(root: Path, *, future_change: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    npi1 = "1000000011"
    npi2 = "1000000012"
    npi3 = "1000000013"
    npi4 = "1000000014"
    npi5 = "1000000015"
    definitions: dict[int, list[tuple[str, str, str, str]]] = {
        2019: [
            (npi1, "A", "G-A", "X"),
            (npi2, "B", "G-B", "X"),
            (npi3, "C", "G-C", "Y"),
        ],
        2020: [
            (npi1, "A2", "G-A", "X"),
            (npi2, "B", "G-B", "X"),
            (npi3, "C", "G-C", "Y"),
            (npi4, "D", "G-D", "Y"),
        ],
        2021: [
            (npi1, "A2", "g-a", "X"),
            (npi2, "B", "G-B", "X"),
            (npi3, "C", "G-C", "Y"),
            (npi4, "D", "G-D", "Y"),
        ],
        2022: [
            (npi1, "D", "G-D", "X"),
            (npi2, "B", "G-B", "X"),
            (npi3, "E", "G-E", "Y"),
            (npi4, "D", "G-D", "Y"),
        ],
        2023: [
            (npi1, "D2", "G-D", "X"),
            (npi2, "E", "G-E", "X"),
            (npi3, "E", "G-E", "Y"),
            (npi4, "D", "G-D", "Y"),
            (npi5, "C", "G-C", "Z"),
        ],
        2024: [
            (
                npi1,
                "F2" if future_change else "F",
                "G-F2" if future_change else "G-F",
                "X",
            ),
            (npi2, "E", "G-E", "X"),
            (npi3, "E", "G-E", "Y"),
            (npi4, "D", "G-D", "Y"),
            (npi5, "A", "G-A", "Z"),
        ],
    }
    entries: list[dict[str, object]] = []
    for year in range(2019, 2025):
        path = root / f"partd_{year}.csv"
        rows = [
            {
                "Prscrbr_NPI": npi,
                "Brnd_Name": brand,
                "Gnrc_Name": generic,
                "Prscrbr_Type": specialty,
                "Prscrbr_State_Abrvtn": "TX",
                "Tot_Clms": "11",
                "Tot_Drug_Cst": "100",
                "Tot_Benes": "",
            }
            for npi, brand, generic, specialty in definitions[year]
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        entries.append(
            {
                "path": path.name,
                "year": year,
                "url": f"https://fixture.invalid/partd_{year}.csv",
                "dataset_id": f"fixture-{year}",
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "header": HEADER,
                "retrieved_at": "2026-09-01T00:00:00Z",
                "historical_published_at": None,
            }
        )
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "0.2-candidate",
                "dataset": "partd_prescriber_drug",
                "landing_url": "https://fixture.invalid/landing",
                "dictionary_url": "https://fixture.invalid/dictionary",
                "methodology_url": "https://fixture.invalid/methodology",
                "files": entries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _read_rankings(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class PartDFeasibilityTests(unittest.TestCase):
    def test_six_year_window_uses_prior_history_dynamic_cohorts_and_identity_diagnostics(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            manifest = _write_lookback_fixture(root)
            output = Path(temporary) / "run"
            report = run_gate(root, manifest, output, cohort_size=2000)

            self.assertEqual(report["decision"], "REVIEW_REQUIRED")
            configuration = report["configuration"]
            self.assertEqual(configuration["warmup_years"], [2019, 2020, 2021])
            self.assertEqual(configuration["score_years"], [2022, 2023, 2024])
            self.assertEqual(
                configuration["evaluation_roles"],
                {"2022": "train_target", "2023": "validation", "2024": "held_out_test"},
            )
            annual = report["audits"]["annual"]
            self.assertFalse(annual["2021"]["scored"])
            for year in ("2022", "2023", "2024"):
                self.assertTrue(annual[year]["scored"])
                self.assertGreater(annual[year]["eligible_positive_edges"], 0)
            self.assertEqual(annual["2024"]["target_cohort_size"], 5)

            rankings = _read_rankings(output / "rankings.jsonl")
            rankings_by_year = {
                year: {row["npi"] for row in rankings if row["year"] == year}
                for year in (2022, 2023, 2024)
            }
            self.assertNotIn("1000000015", rankings_by_year[2023])
            self.assertIn("1000000015", rankings_by_year[2024])
            self.assertEqual(
                report["label_definition"]["name"],
                "first_observed_published_provider_drug_relationship",
            )
            self.assertIn(
                "10 or fewer Part D claims",
                report["label_definition"]["suppression_limit"],
            )
            identity = report["identity_diagnostics"]
            self.assertEqual(
                identity["identity_policy"],
                "source_native_exact_brand_generic_signature_v1",
            )
            self.assertGreater(
                identity["temporal_instability"][
                    "normalized_generic_tokens_with_multiple_spellings"
                ],
                0,
            )
            self.assertGreater(
                identity["generic_only_alternative"][
                    "provider_edges_collapsed_from_exact_brand_generic"
                ],
                0,
            )

    def test_six_year_future_rows_do_not_change_prior_target_rankings(self) -> None:
        with TemporaryDirectory() as temporary:
            base_root = Path(temporary) / "base"
            changed_root = Path(temporary) / "changed"
            base_manifest = _write_lookback_fixture(base_root)
            changed_manifest = _write_lookback_fixture(changed_root, future_change=True)
            base_output = Path(temporary) / "base-run"
            changed_output = Path(temporary) / "changed-run"
            base_report = run_gate(base_root, base_manifest, base_output)
            changed_report = run_gate(changed_root, changed_manifest, changed_output)

            base_rankings = _read_rankings(base_output / "rankings.jsonl")
            changed_rankings = _read_rankings(changed_output / "rankings.jsonl")
            self.assertEqual(
                [row for row in base_rankings if row["year"] in (2022, 2023)],
                [row for row in changed_rankings if row["year"] in (2022, 2023)],
            )
            self.assertEqual(
                base_report["metrics"]["by_year"]["2022"],
                changed_report["metrics"]["by_year"]["2022"],
            )
            self.assertEqual(
                base_report["metrics"]["by_year"]["2023"],
                changed_report["metrics"]["by_year"]["2023"],
            )


    def test_non_utf8_source_bytes_are_preserved_for_anchored_rows(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            manifest = _write_lookback_fixture(root)
            source_path = root / "partd_2020.csv"
            original = source_path.read_bytes()
            mutated = original.replace(b",TX,", b",\xe3\x9c,", 1)
            self.assertNotEqual(original, mutated)
            source_path.write_bytes(mutated)
            manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
            for entry in manifest_value["files"]:
                if entry["year"] == 2020:
                    entry["sha256"] = sha256_file(source_path)
            manifest.write_text(
                json.dumps(manifest_value, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            report = run_gate(root, manifest, Path(temporary) / "run")
            self.assertIn(
                "surrogateescape",
                report["sources"]["text_decoding"],
            )


    def test_fixture_gate_metrics_edges_and_immutable_output(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            manifest = _write_fixture(root)
            output = Path(temporary) / "run"
            report = run_gate(root, manifest, output, cohort_size=2000)
            self.assertEqual(report["decision"], "REVIEW_REQUIRED")
            self.assertEqual(report["cohort"]["npis"], NPIS)
            self.assertFalse(report["historical_availability_verified"])
            self.assertEqual(report["configuration"]["cohort_size"], 2000)
            configuration_json = json.dumps(
                report["configuration"],
                sort_keys=True,
                separators=(",", ":"),
            )
            self.assertEqual(
                report["configuration_sha256"],
                hashlib.sha256(configuration_json.encode("utf-8")).hexdigest(),
            )
            annual = report["audits"]["annual"]
            self.assertEqual(annual["2022"]["eligible_positive_edges"], 1)
            self.assertEqual(annual["2023"]["eligible_positive_edges"], 1)
            self.assertEqual(annual["2023"]["recurrent_edges_excluded_after_gap"], 1)
            self.assertEqual(annual["2022"]["globally_new_drugs_excluded"], 1)

            p1_rankings = {
                row["year"]: row
                for row in _read_rankings(output / "rankings.jsonl")
                if row["npi"] == NPIS[0]
            }
            self.assertEqual(p1_rankings[2022]["candidate_count"], 2)
            positive_2022 = p1_rankings[2022]["positives"]
            self.assertEqual(len(positive_2022), 1)
            self.assertEqual(positive_2022[0]["brand_name"], "C")
            self.assertEqual(
                positive_2022[0]["ranks"],
                {
                    "global_popularity": 2,
                    "history_overlap": 1,
                    "specialty_popularity": 1,
                },
            )
            self.assertEqual(
                p1_rankings[2023]["positives"][0]["ranks"],
                {
                    "global_popularity": 1,
                    "history_overlap": 1,
                    "specialty_popularity": 1,
                },
            )
            global_2022 = report["metrics"]["by_year"]["2022"]["global_popularity"][
                "all_eligible_positives"
            ]
            specialty_2022 = report["metrics"]["by_year"]["2022"]["specialty_popularity"][
                "all_eligible_positives"
            ]
            overlap_2022 = report["metrics"]["by_year"]["2022"]["history_overlap"][
                "all_eligible_positives"
            ]
            self.assertEqual(global_2022["mrr"], 0.5)
            self.assertEqual(specialty_2022["mrr"], 1.0)
            self.assertEqual(overlap_2022["mrr"], 1.0)
            for metrics in (global_2022, specialty_2022, overlap_2022):
                self.assertEqual(metrics["micro_recall_at_5"], 1.0)
                self.assertEqual(metrics["micro_recall_at_10"], 1.0)
                self.assertEqual(metrics["micro_recall_at_20"], 1.0)
            self.assertEqual(
                report["audits"]["claim_bands"]["eligible_positives"]["11-20"], 2
            )

            with (output / "edges.csv").open(encoding="utf-8", newline="") as handle:
                edge = next(csv.DictReader(handle))
            source_path = root / edge["source_path"]
            with source_path.open(encoding="utf-8", newline="") as handle:
                source_rows = list(csv.DictReader(handle))
            source_row = int(edge["source_row"])
            self.assertEqual(edge["npi"], source_rows[source_row - 1]["Prscrbr_NPI"])
            self.assertEqual(edge["claims"], source_rows[source_row - 1]["Tot_Clms"])
            self.assertEqual(edge["cost"], source_rows[source_row - 1]["Tot_Drug_Cst"])
            self.assertEqual(edge["source_sha256"], sha256_file(source_path))
            self.assertEqual(edge["valid_from"], f"{edge['year']}-01-01")
            self.assertEqual(edge["valid_to"], f"{int(edge['year']) + 1}-01-01")
            self.assertEqual(edge["observed_at"], "2026-09-01T00:00:00Z")
            self.assertEqual(edge["transformation"], "partd_provider_drug_edge_v1")

            first_report_bytes = (output / "report.json").read_bytes()
            with self.assertRaises(FileExistsError):
                run_gate(root, manifest, output, cohort_size=2000)
            self.assertEqual(first_report_bytes, (output / "report.json").read_bytes())

    def test_future_provider_and_later_changes_do_not_change_prior_rankings(self) -> None:
        with TemporaryDirectory() as temporary:
            base_root = Path(temporary) / "base"
            changed_root = Path(temporary) / "changed"
            base_manifest = _write_fixture(base_root)
            changed_manifest = _write_fixture(changed_root, future_npi=True)
            base_report = run_gate(base_root, base_manifest, Path(temporary) / "base-run")
            changed_report = run_gate(changed_root, changed_manifest, Path(temporary) / "changed-run")
            self.assertEqual(base_report["cohort"], changed_report["cohort"])
            self.assertEqual(
                base_report["audits"]["annual"]["2022"],
                changed_report["audits"]["annual"]["2022"],
            )
            base_rankings = _read_rankings(Path(temporary) / "base-run" / "rankings.jsonl")
            changed_rankings = _read_rankings(Path(temporary) / "changed-run" / "rankings.jsonl")
            self.assertEqual(
                [row for row in base_rankings if row["year"] == 2022],
                [row for row in changed_rankings if row["year"] == 2022],
            )
            self.assertNotIn("1000000006", changed_report["cohort"]["npis"])

    def test_cli_smoke_reads_real_fixture_artifacts(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            manifest = _write_fixture(root)
            output = Path(temporary) / "cli-run"
            repo_root = Path(__file__).resolve().parents[1]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(repo_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_partd_gate.py",
                    "--source-root",
                    str(root),
                    "--manifest",
                    str(manifest),
                    "--output-dir",
                    str(output),
                    "--cohort-size",
                    "2000",
                ],
                cwd=repo_root,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            rankings = _read_rankings(output / "rankings.jsonl")
            self.assertEqual(report["decision"], "REVIEW_REQUIRED")
            self.assertEqual(len(rankings), 10)
            self.assertEqual(report["artifact_hashes"]["edges.csv"], sha256_file(output / "edges.csv"))

    def test_validation_rejects_duplicate_header_claims_and_hash_drift(self) -> None:
        with TemporaryDirectory() as temporary:
            duplicate_root = Path(temporary) / "duplicate"
            duplicate_manifest = _write_fixture(duplicate_root, duplicate_first_row=True)
            with self.assertRaisesRegex(ValueError, "duplicate selected"):
                run_gate(duplicate_root, duplicate_manifest, Path(temporary) / "duplicate-run")

            missing_root = Path(temporary) / "missing-header"
            missing_manifest = _write_fixture(missing_root, missing_header=True)
            with self.assertRaisesRegex(ValueError, "missing required"):
                run_gate(missing_root, missing_manifest, Path(temporary) / "missing-run")

            low_claim_root = Path(temporary) / "low-claims"
            low_claim_manifest = _write_fixture(low_claim_root, low_claims=True)
            with self.assertRaisesRegex(ValueError, "must be >= 11"):
                run_gate(low_claim_root, low_claim_manifest, Path(temporary) / "low-claims-run")

            drift_root = Path(temporary) / "drift"
            drift_manifest = _write_fixture(drift_root)
            with (drift_root / "partd_2022.csv").open("a", encoding="utf-8") as handle:
                handle.write("\n")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                run_gate(drift_root, drift_manifest, Path(temporary) / "drift-run")

    def test_blank_specialty_falls_back_and_blank_beneficiaries_are_ignored(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            manifest = _write_fixture(root, blank_p1_specialty=True)
            output = Path(temporary) / "run"
            report = run_gate(root, manifest, output)
            self.assertEqual(report["audits"]["annual"]["2022"]["specialty_fallback_provider_years"], 1)
            self.assertEqual(report["audits"]["annual"]["2023"]["specialty_fallback_provider_years"], 1)
            with (output / "edges.csv").open(encoding="utf-8", newline="") as handle:
                edge_rows = list(csv.DictReader(handle))
            self.assertTrue(edge_rows)
            self.assertTrue(all(row["claims"] == "11" for row in edge_rows))
            self.assertNotIn("Tot_Benes", edge_rows[0])

    def test_empty_positive_window_is_insufficient_with_null_metrics(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            manifest = _write_fixture(root, empty_positive_window=True)
            report = run_gate(root, manifest, Path(temporary) / "run")
            self.assertEqual(report["decision"], "INSUFFICIENT_OBSERVED_SUPPORT")
            for year in ("2022", "2023"):
                for method in ("global_popularity", "specialty_popularity", "history_overlap"):
                    metrics = report["metrics"]["by_year"][year][method][
                        "all_eligible_positives"
                    ]
                    self.assertIsNone(metrics["micro_recall_at_10"])
                    self.assertIsNone(metrics["provider_macro_recall_at_10"])
                    self.assertIsNone(metrics["mrr"])


    def test_model_gate_compares_generic_primary_and_variant_with_all_provider_metrics(
        self,
    ) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            manifest = _write_lookback_fixture(root)
            feasibility_output = Path(temporary) / "feasibility"
            run_gate(root, manifest, feasibility_output, cohort_size=2000)

            output = Path(temporary) / "model-gate"
            report = run_model_gate(feasibility_output, output)

            self.assertEqual(report["record_kind"], "partd_model_gate")
            self.assertEqual(report["decision"], "MODEL_GATE_REVIEW_REQUIRED")
            self.assertEqual(report["admission_status"], "model_gate_pending")
            configuration = report["configuration"]
            self.assertEqual(configuration["primary_representation"], "generic")
            self.assertEqual(
                configuration["evaluation_roles"],
                {
                    "2022": "train_target",
                    "2023": "validation",
                    "2024": "held_out_test",
                },
            )
            self.assertEqual(
                configuration["methods"],
                [
                    "specialty_popularity",
                    "history_overlap",
                    "tabular_logistic",
                    "graph_bpr",
                ],
            )
            representations = report["metrics"]["representations"]
            self.assertEqual(
                report["evaluation"]["generic"]["2023"]["positive_edges"],
                1,
            )
            self.assertEqual(
                report["evaluation"]["variant"]["2023"]["positive_edges"],
                1,
            )
            for representation in ("generic", "variant"):
                for year in ("2023", "2024"):
                    all_provider = representations[representation]["by_year"][year][
                        "by_method"
                    ]["graph_bpr"]["all_provider_years"]
                    self.assertGreater(
                        all_provider["target_cohort_provider_year_count"],
                        0,
                    )
                    self.assertGreater(
                        all_provider["positive_empty_provider_year_count"],
                        0,
                    )
                    self.assertIsNotNone(all_provider["precision_at_10"])
                    self.assertIn(
                        "fraction_zero_positive_provider_years_recommended_at_10",
                        all_provider,
                    )
                    self.assertIn(
                        "fraction_zero_positive_provider_years_high_confidence_recommended_at_10",
                        all_provider,
                    )
                    self.assertGreaterEqual(
                        all_provider[
                            "fraction_zero_positive_provider_years_high_confidence_recommended_at_10"
                        ],
                        0.0,
                    )
            rankings = _read_rankings(output / "rankings.jsonl")
            self.assertEqual(len(rankings), 18)
            self.assertEqual(
                {row["representation"] for row in rankings},
                {"generic", "variant"},
            )
            self.assertTrue(
                all("recommendations" in row for row in rankings)
            )
            first_report_bytes = (output / "report.json").read_bytes()
            with self.assertRaises(FileExistsError):
                run_model_gate(feasibility_output, output)
            self.assertEqual(first_report_bytes, (output / "report.json").read_bytes())

    def test_model_gate_cli_smoke_and_input_hash_validation(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            manifest = _write_lookback_fixture(root)
            feasibility_output = Path(temporary) / "feasibility"
            run_gate(root, manifest, feasibility_output, cohort_size=2000)
            cli_output = Path(temporary) / "cli-model-gate"
            repo_root = Path(__file__).resolve().parents[1]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(repo_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_partd_model_gate.py",
                    "--feasibility-dir",
                    str(feasibility_output),
                    "--output-dir",
                    str(cli_output),
                ],
                cwd=repo_root,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            cli_report = json.loads((cli_output / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(cli_report["decision"], "MODEL_GATE_REVIEW_REQUIRED")
            self.assertEqual(
                cli_report["artifact_hashes"]["rankings.jsonl"],
                sha256_file(cli_output / "rankings.jsonl"),
            )

            edges_path = feasibility_output / "edges.csv"
            original = edges_path.read_bytes()
            edges_path.write_bytes(original + b"\\n")
            with self.assertRaisesRegex(ValueError, "edge hash mismatch"):
                run_model_gate(feasibility_output, Path(temporary) / "hash-drift")
if __name__ == "__main__":
    unittest.main()
