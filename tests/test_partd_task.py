"""Raw-input, temporal, ranking, and extension tests for Part D."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from healthgraphbench import load_task
from healthgraphbench.core import PredictionSet
from healthgraphbench.data import sha256_file
from healthgraphbench.models import SpecialtyPopularity
from healthgraphbench.tasks.partd import PartDTask


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
NPIS = tuple(f"100000000{index}" for index in range(1, 6))


def _write_fixture(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    p1, p2, p3, p4, p5 = NPIS
    rows_by_year = {
        2019: [(p1, "A", " G-A ", "X"), (p2, "B", "G-B", "X"),
               (p3, "B", "G-B", "Y"), (p4, "C", "G-C", "Y"),
               (p5, "A", "G-A", "Z")],
        2020: [(p1, "A2", "G-A", "X"), (p2, "B", "G-B", "X"),
               (p3, "B", "G-B", "Y"), (p4, "C", "G-C", "Y"),
               (p5, "A", "G-A", "Z")],
        2021: [(p1, "A", "G-A", "X"), (p2, "B", "G-B", "X"),
               (p3, "B", "G-B", "Y"), (p4, "C", "G-C", "Y"),
               (p5, "A", "G-A", "Z")],
        2022: [(p1, "A", "G-A", "X"), (p2, "B", "G-B", "X"),
               (p3, "C", "G-C", "Y"), (p4, "C", "G-C", "Y"),
               (p5, "A", "G-A", "Z")],
        2023: [(p1, "B", "G-B", "X"), (p2, "C", "G-C", "X"),
               (p3, "A", "G-A", "Y"), (p4, "B", "G-B", "Y"),
               (p5, "A", "G-A", "Z"), (p5, "D", "G-D", "Z")],
        2024: [(p1, "C", "G-C", "X"), (p2, "A", "G-A", "X"),
               (p3, "C", "G-C", "Y"), (p4, "A", "G-A", "Y"),
               (p5, "B", "G-B", "Z")],
    }
    entries: list[dict[str, object]] = []
    for year, edges in rows_by_year.items():
        path = root / f"partd_{year}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
            writer.writeheader()
            writer.writerows(
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
                for npi, brand, generic, specialty in edges
            )
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
    manifest = root / "manifest.json"
    manifest.write_text(
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
    return manifest


class PartDTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.raw = self.root / "raw"
        self.manifest = _write_fixture(self.raw)
        self.prepared = self.root / "prepared"
        self.task = load_task(
            "partd",
            self.raw,
            manifest_path=self.manifest,
            preparation_dir=self.prepared,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_raw_preparation_fits_only_requested_baseline_and_evaluates_new_ranks(self) -> None:
        task = self.task
        self.assertIsInstance(task, PartDTask)
        self.assertEqual(task.report["record_kind"], "partd_execution_preparation")
        self.assertTrue((self.prepared / "edges.csv").is_file())
        self.assertEqual(task.report["configuration"]["years"], list(range(2019, 2025)))

        train, validation, test = (task.get_split(name) for name in ("train", "validation", "test"))
        prediction = SpecialtyPopularity().fit_predict(train, validation, test)
        self.assertEqual(prediction.task_name, "partd_prescriber_drug")
        self.assertEqual(len(prediction.payload["validation_predictions"]), 5)
        self.assertEqual(len(prediction.payload["test_predictions"]), 5)
        self.assertEqual(
            prediction.payload["validation"]["all_provider_years"]["positive_empty_provider_year_count"],
            1,
        )
        self.assertEqual(task.evaluate(prediction), prediction.payload["test"])

    def test_public_history_callback_has_only_prior_rows_and_scores_every_candidate(self) -> None:
        task = self.task
        train, validation, test = (task.get_split(name) for name in ("train", "validation", "test"))
        seen_years: set[int] = set()

        def score(view, npi, candidates):
            seen_years.add(view.target_year)
            self.assertNotIn("G-D", view.drugs if view.target_year == 2023 else ())
            self.assertEqual(candidates, tuple(sorted(set(candidates))))
            return {drug: 0.0 for drug in candidates}

        prediction = task.predict_ranker("out_of_tree_equal_score", train, validation, test, score)
        self.assertEqual(seen_years, {2023, 2024})
        validation_rows = {row["npi"]: row for row in prediction.payload["validation_predictions"]}
        self.assertEqual(validation_rows[NPIS[0]]["candidate_count"], 2)
        self.assertEqual(validation_rows[NPIS[0]]["positive_ranks"], [1])
        self.assertEqual(validation_rows[NPIS[1]]["positive_ranks"], [2])
        self.assertEqual(validation_rows[NPIS[4]]["positive_count"], 0)

        view = task.history_view("validation")
        self.assertEqual(view.target_year, 2023)
        self.assertEqual(view.prior_years, (2019, 2020, 2021, 2022))
        self.assertNotIn("G-D", view.drugs)
        self.assertEqual(view.provider_history(NPIS[0]), frozenset({"G-A"}))
        with self.assertRaises(TypeError):
            view.provider_drugs[NPIS[0]] = frozenset()  # type: ignore[index]

        poisoned = dict(prediction.payload)
        poisoned["test"] = {"positive_containing_provider_years": {"micro_recall_at_10": 0.0}}
        independent = PredictionSet(prediction.task_name, prediction.method, "test", poisoned)
        evaluated = task.evaluate(independent)
        self.assertEqual(
            evaluated["positive_containing_provider_years"]["micro_recall_at_10"],
            1.0,
        )

    def test_ranker_and_evaluation_reject_incomplete_candidates_and_mixed_splits(self) -> None:
        task = self.task
        train, validation, test = (task.get_split(name) for name in ("train", "validation", "test"))
        with self.assertRaisesRegex(ValueError, "ordered train, validation, and test"):
            task.fit_predict("specialty_popularity", train, test, validation)
        with self.assertRaisesRegex(ValueError, "every Part D candidate"):
            task.predict_ranker(
                "missing-score",
                train,
                validation,
                test,
                lambda view, npi, candidates: {},
            )

        prediction = task.predict_ranker(
            "all-candidates", train, validation, test,
            lambda view, npi, candidates: {drug: 0.0 for drug in candidates},
        )
        mixed_rows = [*prediction.payload["test_predictions"], prediction.payload["validation_predictions"][0]]
        payload = dict(prediction.payload)
        payload["test_predictions"] = mixed_rows
        with self.assertRaisesRegex(ValueError, "mixed target years"):
            task.evaluate(PredictionSet(task.name, prediction.method, "test", payload))

    def test_existing_preparation_cannot_be_overwritten(self) -> None:
        with self.assertRaises(FileExistsError):
            PartDTask.from_source_root(
                self.raw,
                manifest_path=self.manifest,
                preparation_dir=self.prepared,
            )


if __name__ == "__main__":
    unittest.main()
