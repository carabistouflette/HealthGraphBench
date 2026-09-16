"""Common-interface tests for the admitted Part D task."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from healthgraphbench import load_task
from healthgraphbench.models import SpecialtyPopularity
from healthgraphbench.tasks.partd import PartDTask


METHODS = ["specialty_popularity", "history_overlap", "tabular_logistic", "graph_bpr"]


def _metric() -> dict[str, object]:
    return {
        "positive_containing_provider_years": {"mrr": 0.5},
        "all_provider_years": {"precision_at_10": 0.25},
    }


class PartDTaskTests(unittest.TestCase):
    def test_model_gate_artifact_uses_common_split_and_model_interface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifact_dir = Path(temporary)
            rankings_path = artifact_dir / "rankings.jsonl"
            rows = []
            for year in (2023, 2024):
                rows.append(
                    {
                        "representation": "generic",
                        "year": year,
                        "npi": "1000000001",
                        "eligible": True,
                        "candidate_count": 3,
                        "positive_count": 1,
                        "positives": [
                            {
                                "drug": {"generic_name": "Drug A"},
                                "ranks": {method: 1 for method in METHODS},
                            }
                        ],
                        "recommendations": {
                            method: [
                                {"drug": {"generic_name": "Drug A"}, "rank": 1, "score": 1.0}
                            ]
                            for method in METHODS
                        },
                    }
                )
            rankings_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
            by_year = {
                str(year): {"by_method": {method: _metric() for method in METHODS}}
                for year in (2023, 2024)
            }
            report = {
                "record_kind": "partd_model_gate",
                "configuration": {
                    "primary_representation": "generic",
                    "methods": METHODS,
                },
                "artifact_hashes": {
                    "rankings.jsonl": hashlib.sha256(rankings_path.read_bytes()).hexdigest()
                },
                "metrics": {
                    "representations": {
                        "generic": {
                            "by_year": by_year,
                            "pooled_provider_year": {"by_method": {method: _metric() for method in METHODS}},
                        }
                    }
                },
            }
            (artifact_dir / "report.json").write_text(
                json.dumps(report), encoding="utf-8"
            )

            task = load_task("partd", artifact_dir)
            train, validation, test = (
                task.get_split(name) for name in ("train", "validation", "test")
            )
            prediction = SpecialtyPopularity().fit_predict(train, validation, test)

            self.assertIsInstance(task, PartDTask)
            self.assertEqual(prediction.task_name, "partd_prescriber_drug")
            self.assertEqual(prediction.payload["validation"]["positive_containing_provider_years"]["mrr"], 0.5)
            self.assertEqual(len(prediction.payload["predictions"]), 2)
            self.assertEqual(task.evaluate(prediction)["all_provider_years"]["precision_at_10"], 0.25)


if __name__ == "__main__":
    unittest.main()
