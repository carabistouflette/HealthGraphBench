"""Consumer-visible RC3.1 CMS boundaries; synthetic fixtures, never executed on import."""
from __future__ import annotations

import csv
import gzip
import json
import pickle
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
from threadpoolctl import threadpool_limits

from healthgraphbench.data import sha256_file
from healthgraphbench.rc31 import cms
from healthgraphbench.tasks.cms_nursing.prepare import CmsPrepared, CmsSources, _episode_histories, normalize_owner_name
from healthgraphbench.tasks.cms_nursing.task import CmsNursingTask


def _prepared(records: dict, episodes: set | None = None, serious: set | None = None) -> CmsPrepared:
    first: dict = {}
    for ccn, values in records.items():
        for owner, association, _role, _kind in values:
            first.setdefault(owner, {})[ccn] = min(association, first.get(owner, {}).get(ccn, association))
    return CmsPrepared((), CmsSources(*([Path("unused")] * 7)), frozenset(episodes or ()),
                       frozenset(serious or ()), {}, records, first, {}, ())


def _record(owner: str, when: date) -> tuple:
    return owner, when, "5% OR GREATER DIRECT OWNERSHIP INTEREST", "O"


def _event(enrollment: str, ccn: str, when: str) -> dict:
    return {"EFFECTIVE DATE": when, "ENROLLMENT ID - BUYER": enrollment, "CCN - BUYER": ccn}


def _owner(enrollment: str, associate: str, when: str) -> dict:
    return {"ENROLLMENT ID": enrollment, "ASSOCIATE ID - OWNER": associate,
            "ASSOCIATION DATE - OWNER": when, "ROLE TEXT - OWNER": "5% OR GREATER DIRECT OWNERSHIP INTEREST", "TYPE - OWNER": "O"}


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _raw_fixture(root: Path) -> tuple[Path, Path]:
    """Actual source schemas, full Q2 preparation, and hash-verified manifest."""
    survey = []
    citations = []
    for ccn in ("A", "B", "C"):
        for year in (2018, 2019, 2022, 2023, 2024, 2025):
            when = f"{year}-01-01"
            survey.append({"CMS Certification Number (CCN)": ccn, "Survey Date": when, "Type of Survey": "Health Standard"})
            if (year + ord(ccn)) % 2:
                citations.append({"CMS Certification Number (CCN)": ccn, "Survey Date": when,
                                  "Survey Type": "Health", "Standard Deficiency": "Y", "Scope Severity Code": "G"})
    _write_csv(root / "survey_dates.csv", ["CMS Certification Number (CCN)", "Survey Date", "Type of Survey"], survey)
    _write_csv(root / "health_citations.csv", ["CMS Certification Number (CCN)", "Survey Date", "Survey Type", "Standard Deficiency", "Scope Severity Code"], citations)
    _write_csv(root / "provider_info.csv", ["CMS Certification Number (CCN)", "State", "Provider Type", "Date First Approved to Provide Medicare and Medicaid Services"], [
        {"CMS Certification Number (CCN)": ccn, "State": "X", "Provider Type": "Both", "Date First Approved to Provide Medicare and Medicaid Services": "2010-01-01"}
        for ccn in ("A", "B", "C")
    ])
    _write_csv(root / "ownership.csv", ["CMS Certification Number (CCN)", "Association Date", "Owner Type", "Owner Name", "Role played by Owner or Manager in Facility"], [
        {"CMS Certification Number (CCN)": "C", "Association Date": "since 01/01/2010", "Owner Type": "Organization", "Owner Name": "Source Name",
         "Role played by Owner or Manager in Facility": "5% OR GREATER DIRECT OWNERSHIP INTEREST"}
    ])
    _write_csv(root / "penalties.csv", ["unused"], [])
    (root / "chow.json").write_text(json.dumps([_event("EA", "A", "2019-01-01"), _event("EB", "B", "2020-01-01")]))
    (root / "chow_owners_full.json").write_text(json.dumps([
        _owner("EA", "shared", "2010-01-01"), _owner("EB", "shared", "2010-01-01"),
        _owner("EA", "same_day", "2023-01-01"), _owner("EB", "same_day", "2023-01-01"),
    ]))
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"cms": {"files": [
        {"path": name, "bytes": (root / name).stat().st_size, "sha256": sha256_file(root / name)} for name in cms.SOURCE_FILES
    ]}}))
    baseline = root / "q2-rows.jsonl.gz"
    prepared = CmsNursingTask.from_source_root(root).prepared
    with gzip.open(baseline, "wt") as stream:
        for row in prepared.rows:
            stream.write(json.dumps({**row, "date": row["date"].isoformat()}) + "\n")
    return manifest, baseline


class CmsDocumentationBoundaryTests(unittest.TestCase):
    def test_focal_peer_and_history_same_day_are_excluded(self) -> None:
        target = date(2023, 1, 1)
        records = {
            "A": [_record("shared", date(2020, 1, 1)), _record("focal_same_day", target)],
            "B": [_record("shared", date(2020, 1, 1))],
            "C": [_record("shared", target)],
            "D": [_record("focal_same_day", date(2020, 1, 1))],
        }
        episodes = {("B", date(2022, 1, 1)), ("B", target), ("B", date(2024, 1, 1))}
        prepared = _prepared(records, episodes, {("B", target), ("B", date(2024, 1, 1))})
        histories = _episode_histories(episodes, set(prepared.serious_episodes))
        stats = cms._peer_stats("A", target, records, prepared.combined_first, histories, {})
        self.assertEqual(stats["owner_count"], 1)
        self.assertEqual(stats["peer_count"], 1)
        self.assertEqual(stats["peer_prior_inspections"], 1)
        self.assertEqual(stats["peer_prior_serious"], 0)

    def test_proxy_requires_actual_preinspection_event_on_both_endpoints(self) -> None:
        records = {ccn: [_record("PAC:id", date(2010, 1, 1))] for ccn in ("A", "B")}
        prepared = _prepared(records)
        evidence, counts = cms._documented_evidence(
            [_event("EA", "A", "2020-01-01"), _event("EB", "B", "2023-01-01")],
            [_owner("EA", "id", "2010-01-01"), _owner("EB", "id", "2010-01-01")], prepared,
        )
        stats = cms._peer_stats("A", date(2023, 1, 1), records, prepared.combined_first, {}, {}, evidence)
        self.assertEqual(stats["owner_count"], 1)
        self.assertEqual(stats["peer_count"], 0)
        stats_after = cms._peer_stats("A", date(2023, 1, 2), records, prepared.combined_first, {}, {}, evidence)
        self.assertEqual(stats_after["peer_count"], 1)
        self.assertEqual(counts["unique_candidate_documented_facility_owner_pairs"], 2)

    def test_future_enrollment_ambiguity_does_not_revoke_earlier_link(self) -> None:
        prepared = _prepared({"A": [_record("PAC:id", date(2010, 1, 1))]})
        owners = [_owner("E", "id", "2010-01-01")]
        earlier, _ = cms._documented_evidence([_event("E", "A", "2020-01-01")], owners, prepared)
        extended, _ = cms._documented_evidence([
            _event("E", "A", "2020-01-01"), _event("E", "B", "2024-01-01")], owners, prepared)
        for when in (date(2023, 1, 1), date(2024, 1, 1)):
            self.assertEqual(cms._documented(earlier, "A", "PAC:id", when), cms._documented(extended, "A", "PAC:id", when))
        self.assertFalse(cms._documented(extended, "A", "PAC:id", date(2024, 1, 2)))

    def test_proxy_excludes_missing_dates_roles_ids_names_and_unmatched_enrollments(self) -> None:
        name = normalize_owner_name("Organization", "A Name")
        prepared = _prepared({"A": [_record("PAC:id", date(2010, 1, 1)), _record(name, date(2010, 1, 1))]})
        rows = [
            _owner("E", "id", ""), _owner("E", "", "2010-01-01"),
            {**_owner("E", "id", "2010-01-01"), "ROLE TEXT - OWNER": "W-2 MANAGING EMPLOYEE"},
            _owner("unknown", "id", "2010-01-01"),
        ]
        evidence, counts = cms._documented_evidence([_event("E", "A", "2020-01-01")], rows, prepared)
        self.assertFalse(cms._documented(evidence, "A", "PAC:id", date(2023, 1, 1)))
        self.assertFalse(cms._documented(evidence, "A", name, date(2023, 1, 1)))
        self.assertEqual(counts["owner_rows_excluded_missing_id_date_or_role"], 3)
        self.assertEqual(counts["current_name_pairs_excluded_from_documentation_proxy"], 1)

    def test_owner_association_cannot_be_backdated_by_earlier_chow_event(self) -> None:
        prepared = _prepared({"A": [_record("PAC:id", date(2023, 1, 1))]})
        evidence, _ = cms._documented_evidence([_event("E", "A", "2020-01-01")], [_owner("E", "id", "2023-01-01")], prepared)
        self.assertFalse(cms._documented(evidence, "A", "PAC:id", date(2023, 1, 1)))
        self.assertTrue(cms._documented(evidence, "A", "PAC:id", date(2023, 1, 2)))

    def test_quality_bins_are_preinspection_retention_not_verified_truth(self) -> None:
        self.assertEqual(cms._quality_bin(0, 0), "no_combined_links")
        self.assertEqual(cms._quality_bin(2, 0), "none_retained")
        self.assertEqual(cms._quality_bin(2, 1), "some_retained")
        self.assertEqual(cms._quality_bin(2, 2), "all_retained")
        with self.assertRaises(ValueError):
            cms._quality_bin(1, 2)
        self.assertEqual([cms._history_bin(n) for n in (1, 2, 3, 4)], ["1", "2-3", "2-3", ">3"])


class CmsPreparationAndFitTests(unittest.TestCase):
    def test_preparation_preserves_every_q2_base_row_and_equal_feature_set_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, baseline = _raw_fixture(root)
            phase = root / "preparation"
            phase.mkdir()
            result = cms.prepare_phase(root, manifest, baseline, phase)
            old, new = cms._load_rows(baseline), cms._load_rows(phase / "rows.jsonl.gz")
            self.assertEqual(len(old), len(new))
            for old_row, new_row in zip(old, new, strict=True):
                for key, value in cms._base(old_row).items():
                    self.assertEqual(new_row[key], value)
            self.assertEqual(len(set(result["feature_set_row_fingerprints"].values())), 1)
            self.assertEqual(result["prepared_path"], str((phase / "rows.jsonl.gz").resolve()))
            self.assertEqual(result["primary_metric"], "roc_auc")
            self.assertEqual(result["row_layout_fingerprint"], result["ordered_inspection_fingerprint"])
            self.assertEqual(result["stratum_fields"], {"quality": "quality_bin", "history": "history_bin"})
            self.assertIn("old Q2 metrics and outputs are unchanged", result["relation_cutoff_change_from_q2"])
            self.assertEqual(result["inspection_restriction_counts"]["rows_changed_by_strict_combined_cutoff"], 2)
            row = next(row for row in new if row["ccn"] == "A" and row["year"] == 2019)
            self.assertEqual(row["owner_count"], 1)
            self.assertEqual(row["documented_owner_count"], 0)
            row_2023 = next(row for row in new if row["ccn"] == "A" and row["year"] == 2023)
            self.assertEqual(row_2023["owner_count"], 1)
            self.assertEqual(row_2023["documented_peer_count"], 1)
            self.assertEqual(json.loads((phase / "result.json").read_text()), result)

    def test_preparation_rejects_any_changed_base_row_or_raw_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, baseline = _raw_fixture(root)
            rows = cms._load_rows(baseline)
            rows[0]["prior_serious_rate"] = 123
            with gzip.open(baseline, "wt") as stream:
                for row in rows:
                    stream.write(json.dumps(row) + "\n")
            phase = root / "bad"
            phase.mkdir()
            with self.assertRaisesRegex(ValueError, "EVERY ordered"):
                cms.prepare_phase(root, manifest, baseline, phase)
            (root / "ownership.csv").write_text("changed")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                cms.prepare_phase(root, manifest, baseline, phase)

    def test_states_rows_and_features_use_the_same_strict_training_windows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, baseline = _raw_fixture(root)
            phase = root / "prepared"
            phase.mkdir()
            cms.prepare_phase(root, manifest, baseline, phase)
            rows = cms._load_rows(phase / "rows.jsonl.gz")
            for row in rows:
                if row["year"] >= 2023:
                    row["state"] = "TARGET_ONLY"
            for year in (2023, 2024, 2025):
                identities = []
                for feature_set in cms.FEATURE_SETS:
                    xs, labels, targets, training, target, states = cms._matrices(rows, year, feature_set)
                    self.assertTrue(all(row["year"] < year for row in training))
                    self.assertTrue(all(row["year"] == year for row in target))
                    self.assertEqual(xs.shape[1], len(cms.BASE_FEATURE_NAMES) + len(states) + (0 if feature_set == "facility_history" else len(cms.GRAPH_FEATURE_NAMES)))
                    identities.append((cms._fingerprint(training, ("ccn", "date", "label")), cms._fingerprint(target, ("ccn", "date", "label"))))
                    if year == 2023:
                        self.assertEqual(states, ("X",))
                        self.assertTrue(np.all(targets[:, -1] == 0))
                self.assertEqual(len(set(identities)), 1)

    def test_fixed_settings_reject_feature_set_tuning_and_seed_selection(self) -> None:
        for feature_set in cms.FEATURE_SETS:
            for family, configuration, fixed in (("logistic", cms.LOGISTIC_CONFIGURATION, cms.LOGISTIC_FIXED), ("boosted", cms.BOOSTED_CONFIGURATION, cms.BOOSTED_FIXED)):
                cms._parameters(family, {"feature_set": feature_set, **configuration}, dict(fixed))
                bad = {"feature_set": feature_set, **configuration, "C": 1}
                with self.assertRaises(ValueError):
                    cms._parameters(family, bad, dict(fixed))
        self.assertEqual(cms.expected_seeds("boosted", 200000), [None])
        self.assertEqual(cms.expected_seeds("boosted", 200001), [103, 211, 307])
        self.assertEqual(cms.expected_seeds("logistic", 300000), [None])

    def test_logistic_checkpoint_scaler_portable_predictions_and_loss(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, threadpool_limits(1):
            root = Path(temporary)
            manifest, baseline = _raw_fixture(root)
            preparation = root / "prepared"
            preparation.mkdir()
            cms.prepare_phase(root, manifest, baseline, preparation)
            input_path = preparation / "rows.jsonl.gz"
            results = []
            for feature_set in cms.FEATURE_SETS:
                phase = root / feature_set
                phase.mkdir()
                result = cms.run_phase(str(input_path), 2023, "logistic", {"feature_set": feature_set, **cms.LOGISTIC_CONFIGURATION}, None, dict(cms.LOGISTIC_FIXED), phase)
                predictions = cms._load_rows(phase / "predictions.jsonl.gz")
                self.assertTrue(all(row["year"] == 2023 for row in predictions))
                self.assertTrue(all(0 <= row["score"] <= 1 for row in predictions))
                self.assertTrue(all("history_bin" in row and "quality_bin" in row for row in predictions))
                self.assertEqual(result["primary_metric"], "roc_auc")
                self.assertEqual(result["row_layout_fingerprint"], result["target_row_fingerprint"])
                self.assertEqual(result["stratum_fields"], {"quality": "quality_bin", "history": "history_bin"})
                self.assertEqual(json.loads((phase / "result.json").read_text()), result)
                self.assertEqual(sha256_file(phase / "checkpoint.pkl"), result["checkpoint"]["sha256"])
                with (phase / "checkpoint.pkl").open("rb") as stream:
                    checkpoint = pickle.load(stream)
                xs, _, target_xs, _, _, states = cms._matrices(cms._load_rows(input_path), 2023, feature_set)
                np.testing.assert_allclose(checkpoint["model"][0].mean_, xs.mean(axis=0))
                np.testing.assert_allclose(checkpoint["model"].predict_proba(target_xs)[:, 1], [row["score"] for row in predictions])
                state = json.loads((phase / "model_state.json").read_text())
                scaled = (target_xs - np.asarray(state["scaler_mean"])) / np.asarray(state["scaler_scale"])
                logits = scaled @ np.asarray(state["coefficients"])[0] + state["intercept"][0]
                np.testing.assert_allclose(1 / (1 + np.exp(-logits)), [row["score"] for row in predictions])
                self.assertEqual(checkpoint["state_values"], states)
                self.assertTrue(np.isfinite(result["losses"]["trained"]))
                results.append(result)
            for field in ("training_row_fingerprint", "target_row_fingerprint", "row_layout_fingerprint", "training_facility_fingerprint", "target_facility_fingerprint", "training_rows", "target_rows", "state_values"):
                self.assertTrue(all(result[field] == results[0][field] for result in results))

    def test_boosted_records_exact_shared_configuration_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, threadpool_limits(1):
            root = Path(temporary)
            manifest, baseline = _raw_fixture(root)
            preparation = root / "prepared"
            preparation.mkdir()
            cms.prepare_phase(root, manifest, baseline, preparation)
            phase = root / "boosted"
            phase.mkdir()
            result = cms.run_phase(str(preparation / "rows.jsonl.gz"), 2024, "boosted", {"feature_set": cms.FEATURE_SETS[2], **cms.BOOSTED_CONFIGURATION}, None, dict(cms.BOOSTED_FIXED), phase)
            self.assertEqual(result["training_years"], [2019, 2022, 2023])
            self.assertEqual(result["iterations"], 100)
            self.assertEqual(result["configuration"]["l2_regularization"], 1)
            self.assertEqual(result["scaler_source"], "not_used")
            self.assertTrue((phase / "model_state.json").is_file())
            self.assertEqual(sha256_file(phase / "predictions.jsonl.gz"), result["prediction_sha256"])

    def test_future_labels_do_not_change_training_arrays_or_preinspection_bins(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, baseline = _raw_fixture(root)
            phase = root / "prepared"
            phase.mkdir()
            cms.prepare_phase(root, manifest, baseline, phase)
            rows = cms._load_rows(phase / "rows.jsonl.gz")
            changed = [{**row, "label": 1 - row["label"]} if row["year"] >= 2023 else dict(row) for row in rows]
            for feature_set in cms.FEATURE_SETS:
                original = cms._matrices(rows, 2023, feature_set)
                altered = cms._matrices(changed, 2023, feature_set)
                for index in (0, 1, 2):
                    np.testing.assert_array_equal(original[index], altered[index])
                self.assertEqual([row["quality_bin"] for row in original[4]], [row["quality_bin"] for row in altered[4]])

    def test_preflight_verifies_dependencies_without_fitting_or_predicting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, baseline = _raw_fixture(root)
            with patch.object(cms.LogisticRegression, "fit", side_effect=AssertionError("health fit")), \
                 patch.object(cms.HistGradientBoostingClassifier, "fit", side_effect=AssertionError("health fit")), \
                 patch.object(cms.LogisticRegression, "predict_proba", side_effect=AssertionError("health scoring")), \
                 patch.object(cms.HistGradientBoostingClassifier, "predict_proba", side_effect=AssertionError("health scoring")):
                result = cms.preflight(root, manifest, baseline)
            self.assertFalse(result["health_fit_executed"])
            self.assertEqual(len(result["source_files"]), 7)
            self.assertEqual(result["feature_sets"], list(cms.FEATURE_SETS))
            self.assertEqual(result["raw_bytes"], sum((root / name).stat().st_size for name in cms.SOURCE_FILES))


if __name__ == "__main__":
    unittest.main()
