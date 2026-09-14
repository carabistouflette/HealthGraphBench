"""Behavioral tests for the CMS task contract and metric boundaries."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from healthgraphbench.models import FacilityHistory
from healthgraphbench.tasks.cms_nursing.models import average_precision, model_metrics, roc_auc
from healthgraphbench.tasks.cms_nursing.prepare import history_stats
from healthgraphbench.tasks.cms_nursing.task import CmsNursingTask


class CmsTemporalTests(unittest.TestCase):
    def test_history_cutoff_excludes_target_and_includes_window_boundary(self) -> None:
        histories = {
            "A": (
                (date(2020, 1, 1), date(2020, 1, 2), date(2021, 1, 1)),
                (0, 0, 1, 2),
            )
        }
        stats = history_stats(histories, "A", date(2021, 1, 1))
        self.assertEqual(stats["prior_inspections"], 2)
        self.assertEqual(stats["prior_serious"], 1)
        self.assertEqual(stats["recent365_inspections"], 1)
        self.assertEqual(stats["recent365_serious"], 1)

    def test_auc_average_precision_and_tie_boundaries(self) -> None:
        labels = [0, 1]
        self.assertEqual(roc_auc(labels, [0.1, 0.9]), 1.0)
        self.assertEqual(roc_auc(labels, [0.9, 0.1]), 0.0)
        self.assertEqual(roc_auc(labels, [0.5, 0.5]), 0.5)
        self.assertEqual(average_precision(labels, [0.1, 0.9]), 1.0)
        metrics = model_metrics([1, 0, 0, 0], [0.5, 0.5, 0.5, 0.5])
        self.assertEqual(metrics["precision_at_top_10_percent"], 1.0)

    def test_common_interface_returns_test_metrics(self) -> None:
        rows = []
        for year, label in (
            (2019, 0),
            (2020, 1),
            (2021, 0),
            (2022, 1),
            (2023, 0),
            (2024, 1),
            (2025, 0),
        ):
            rows.append(
                {
                    "ccn": f"{year}",
                    "date": date(year, 1, 1),
                    "year": year,
                    "label": label,
                    "state": "AA",
                    "provider_type": "Test",
                    "age_years": 10.0,
                    "prior_inspections": 1,
                    "prior_serious": 0,
                    "prior_serious_rate": 0.0,
                    "recent365_inspections": 0,
                    "recent365_serious": 0,
                    "recent730_inspections": 0,
                    "recent730_serious": 0,
                    "days_since_last": 400,
                    "chow_prior": 0,
                    "chow_recent365": 0,
                    "owner_count": 0,
                    "peer_count": 0,
                    "peer_prior_facilities": 0,
                    "peer_prior_inspections": 0,
                    "peer_prior_serious": 0,
                    "peer_recent365_inspections": 0,
                    "peer_recent365_serious": 0,
                    "peer_recent730_serious": 0,
                    "peer_any_serious365": 0,
                    "peer_any_serious730": 0,
                }
            )
        from healthgraphbench.tasks.cms_nursing.prepare import CmsPrepared, CmsSources

        empty_sources = CmsSources(*((Path("."),) * 7))
        prepared = CmsPrepared(
            rows=tuple(rows),
            sources=empty_sources,
            standard_episodes=frozenset(),
            serious_episodes=frozenset(),
            provider_static={},
            combined_records={},
            combined_first={},
            chow_dates={},
            state_values=("AA",),
            current_records={},
        )
        task = CmsNursingTask.from_prepared(prepared)
        prediction = FacilityHistory().fit_predict(task.train(), task.validation(), task.test())
        metrics = task.evaluate(prediction)
        self.assertEqual(metrics["rows"], 2)
        self.assertEqual(metrics["positives"], 1)

    def test_prepare_preserves_current_and_chow_fields(self) -> None:
        from tempfile import TemporaryDirectory

        from healthgraphbench.tasks.cms_nursing.prepare import CmsSources, prepare_sources

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "survey_dates.csv").write_text(
                "CMS Certification Number (CCN),Type of Survey,Survey Date\n"
                "A,Health Standard,01/01/2020\n"
                "A,Health Standard,01/01/2021\n",
                encoding="utf-8",
            )
            (root / "health_citations.csv").write_text(
                "Survey Type,CMS Certification Number (CCN),Survey Date,"
                "Standard Deficiency,Scope Severity Code\n"
                "Health,A,01/01/2021,Y,G\n",
                encoding="utf-8",
            )
            (root / "provider_info.csv").write_text(
                "CMS Certification Number (CCN),"
                "Date First Approved to Provide Medicare and Medicaid Services,"
                "State,Provider Type\n"
                "A,01/01/2010,AA,Test\n",
                encoding="utf-8",
            )
            (root / "ownership.csv").write_text(
                '"CMS Certification Number (CCN)","Owner Type","Owner Name",'
                '"Role played by Owner or Manager in Facility","Association Date"\n'
                '"A","Individual","OWNER","CORPORATE OFFICER","since 01/01/2010"\n',
                encoding="utf-8",
            )
            (root / "penalties.csv").write_text("", encoding="utf-8")
            (root / "chow.json").write_text("[]", encoding="utf-8")
            (root / "chow_owners_full.json").write_text("[]", encoding="utf-8")
            sources = CmsSources(
                root / "health_citations.csv",
                root / "ownership.csv",
                root / "provider_info.csv",
                root / "survey_dates.csv",
                root / "penalties.csv",
                root / "chow.json",
                root / "chow_owners_full.json",
            )

            prepared = prepare_sources(sources)

        self.assertIn("A", prepared.current_records)
        self.assertEqual(len(prepared.current_records["A"]), 1)
        self.assertEqual(prepared.chow_dates, {})
        self.assertEqual(len(prepared.rows), 1)
        self.assertEqual(prepared.rows[0]["label"], 1)


if __name__ == "__main__":
    unittest.main()
