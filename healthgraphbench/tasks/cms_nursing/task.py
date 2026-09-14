"""Common-interface adapter for CMS nursing-home serious-deficiency prediction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from ...core import PredictionSet, Split
from .models import fit_logistic_gate, model_metrics, predict_logistic, prevalence_scores
from .prepare import CmsPrepared, CmsSources, prepare_sources


_ALLOWED_METHODS = {
    "prevalence",
    "facility_history",
    "facility_plus_combined_ownership",
}


@dataclass
class CmsNursingTask:
    """A loaded, expanding-window CMS task."""

    prepared: CmsPrepared
    source_root: Path
    _cached_predictions: dict[str, PredictionSet] | None = None

    name = "cms_nursing"

    @classmethod
    def from_source_root(cls, source_root: Path, **_: Any) -> "CmsNursingTask":
        root = source_root / "cms" if (source_root / "cms").is_dir() else source_root
        sources = CmsSources(
            root / "health_citations.csv",
            root / "ownership.csv",
            root / "provider_info.csv",
            root / "survey_dates.csv",
            root / "penalties.csv",
            root / "chow.json",
            root / "chow_owners_full.json",
        )
        missing = [str(path) for path in (getattr(sources, field.name) for field in fields(sources)) if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "CMS source files are missing; run scripts/download_cms.py. Missing: "
                + ", ".join(missing)
            )
        return cls(prepare_sources(sources), root)

    @classmethod
    def from_prepared(cls, prepared: CmsPrepared, source_root: Path = Path(".")) -> "CmsNursingTask":
        """Construct a task from an already verified preparation result."""

        return cls(prepared, source_root)

    def get_split(self, name: str) -> Split:
        """Return a frozen CMS temporal split by name."""

        normalized = name.strip().lower()
        if normalized == "train":
            return Split(
                self,
                "train",
                {"years": list(range(2019, 2023)), "cutoff": "2022-12-31"},
            )
        if normalized == "validation":
            return Split(self, "validation", {"years": [2023], "cutoff": "2023-12-31"})
        if normalized == "test":
            return Split(self, "test", {"years": [2024, 2025], "cutoff": "2025-12-31"})
        raise ValueError(f"Unknown CMS split {name!r}; expected train, validation, or test")

    def _run_all(self) -> dict[str, PredictionSet]:
        if self._cached_predictions is not None:
            return self._cached_predictions
        rows = self.prepared.rows
        all_results: dict[str, PredictionSet] = {}
        for method in sorted(_ALLOWED_METHODS):
            annual: dict[str, dict[str, Any]] = {}
            predictions: list[dict[str, Any]] = []
            for year in (2023, 2024, 2025):
                train_rows = [row for row in rows if 2019 <= row["year"] <= year - 1]
                target_rows = [row for row in rows if row["year"] == year]
                if method == "prevalence":
                    scores = prevalence_scores(train_rows, target_rows)
                else:
                    model = fit_logistic_gate(
                        train_rows,
                        graph=method == "facility_plus_combined_ownership",
                        state_values=self.prepared.state_values,
                    )
                    scores = predict_logistic(model, target_rows, self.prepared.state_values)
                labels = [row["label"] for row in target_rows]
                annual[str(year)] = {
                    "train_rows": len(train_rows),
                    "eval_rows": len(target_rows),
                    "metrics": model_metrics(labels, scores),
                }
                predictions.extend(
                    {
                        "ccn": row["ccn"],
                        "date": row["date"].isoformat(),
                        "year": year,
                        "label": row["label"],
                        "score": score,
                    }
                    for row, score in zip(target_rows, scores, strict=True)
                )
            validation_rows = [row for row in predictions if row["year"] == 2023]
            test_rows = [row for row in predictions if row["year"] in (2024, 2025)]
            all_results[method] = PredictionSet(
                self.name,
                method,
                "test",
                {
                    "annual": annual,
                    "validation": model_metrics(
                        [row["label"] for row in validation_rows],
                        [row["score"] for row in validation_rows],
                    ),
                    "test": model_metrics(
                        [row["label"] for row in test_rows],
                        [row["score"] for row in test_rows],
                    ),
                    "predictions": predictions,
                },
            )
        self._cached_predictions = all_results
        return all_results

    def fit_predict(
        self, method: str, train: Split, validation: Split, test: Split
    ) -> PredictionSet:
        if method not in _ALLOWED_METHODS:
            raise ValueError(f"Unknown CMS method {method!r}")
        if {train.name, validation.name, test.name} != {"train", "validation", "test"}:
            raise ValueError("CMS requires train, validation, and test splits")
        if train.task is not self or validation.task is not self or test.task is not self:
            raise ValueError("all splits must belong to this CMS task")
        return self._run_all()[method]

    def evaluate(self, predictions: PredictionSet) -> dict[str, Any]:
        if predictions.task_name != self.name or predictions.split != "test":
            raise ValueError("CMS evaluation requires test predictions for this task")
        return dict(predictions.payload["test"])

    def manifest(self) -> dict[str, Any]:
        rows = self.prepared.rows
        return {
            "benchmark_version": "0.1",
            "task": self.name,
            "entity": "CMS Certification Number (CCN)",
            "target": "serious G-L health deficiency at the target Health Standard inspection",
            "observation_cutoff": "features use records strictly before the target inspection for facility history and CHOW counts; ownership associations are active at the target date",
            "training_years": "2019-2022",
            "validation_years": "2023",
            "test_years": "2024-2025",
            "negative_semantics": "no serious G-L citation observed in the target episode; not evidence of safety",
            "metrics": ["ROC AUC", "average precision", "top-decile precision", "top-decile recall", "Brier"],
            "clusters": "CCN",
            "standard_episodes": len(self.prepared.standard_episodes),
            "serious_episodes": len(self.prepared.serious_episodes),
            "model_rows": len(rows),
            "model_positives": sum(row["label"] for row in rows),
        }

    def source_manifest(self) -> list[dict[str, Any]]:
        result = []
        for field in fields(self.prepared.sources):
            path = getattr(self.prepared.sources, field.name)
            result.append(
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        return result
