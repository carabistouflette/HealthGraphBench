"""Raw-source Part D task with temporal prediction and evaluation APIs."""

from __future__ import annotations

import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ...candidates.partd import prepare_execution
from ...candidates.partd_model import (
    _EvaluationAccumulator,
    _FeatureContext,
    _History,
    _ProjectedRow,
    _build_history,
    _candidate_drugs,
    _feature_context,
    _fit_graph_bpr,
    _fit_logistic,
    _overlap_scores,
    _positive_ranks,
    _project_rows,
    _specialty_scores,
    _top_recommendations,
    _load_input,
)
from ...core import PredictionSet, Split
from ...data import sha256_file

DrugId = str
ScoreCallable = Callable[["PartDHistoryView", str, tuple[DrugId, ...]], Mapping[DrugId, float]]


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load Part D preparation {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Part D preparation must contain a JSON object: {path}")
    return value


def _contract_path(path: Path | None) -> Path:
    if path is not None:
        resolved = Path(path)
    else:
        resolved = Path(__file__).resolve().parents[3] / "configs" / "task_contract_v0_2.json"
        if not resolved.is_file():
            resolved = Path(__file__).with_name("task_contract_v0_2.json")
    if not resolved.is_file():
        raise FileNotFoundError(f"Part D admission contract is missing: {resolved}")
    contract = _read_object(resolved)
    task_contract = contract.get("task")
    if (
        contract.get("version") != "0.2"
        or not isinstance(task_contract, dict)
        or task_contract.get("id") != "partd_prescriber_drug"
        or task_contract.get("drug_identity") != "exact_trimmed_generic_name"
    ):
        raise ValueError("Part D preparation is incompatible with the v0.2 task contract")
    return resolved


def _history_view(history: _History, target_year: int, prior_years: tuple[int, ...]) -> "PartDHistoryView":
    provider_drugs = MappingProxyType(
        {provider: frozenset(drugs) for provider, drugs in history.provider_drugs.items()}
    )
    drug_providers = MappingProxyType(
        {drug: frozenset(providers) for drug, providers in history.drug_providers.items()}
    )
    latest_specialties = MappingProxyType(
        {
            provider: specialty
            for provider in history.provider_drugs
            if (specialty := history.latest_specialty(provider)) is not None
        }
    )
    return PartDHistoryView(
        target_year=target_year,
        prior_years=prior_years,
        provider_drugs=provider_drugs,
        drug_providers=drug_providers,
        latest_specialties=latest_specialties,
    )


@dataclass(frozen=True, slots=True)
class PartDHistoryView:
    """Immutable generic-drug history strictly before one target service year."""

    target_year: int
    prior_years: tuple[int, ...]
    provider_drugs: Mapping[str, frozenset[DrugId]]
    drug_providers: Mapping[DrugId, frozenset[str]]
    latest_specialties: Mapping[str, str]

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self.provider_drugs))

    @property
    def drugs(self) -> tuple[DrugId, ...]:
        return tuple(sorted(self.drug_providers))

    def provider_history(self, npi: str) -> frozenset[DrugId]:
        return self.provider_drugs.get(npi, frozenset())

    def candidate_ids(self, npi: str) -> tuple[DrugId, ...]:
        own_history = self.provider_history(npi)
        return tuple(drug for drug in self.drugs if drug not in own_history)

    def prior_specialty(self, npi: str) -> str | None:
        return self.latest_specialties.get(npi)

    def global_support(self, drug: DrugId) -> int:
        return len(self.drug_providers.get(drug, ()))

    def tie_key(self, drug: DrugId) -> tuple[int, str]:
        """Ascending sort key implementing support-descending then ID-ascending ties."""
        return (-self.global_support(drug), drug)


@dataclass(slots=True)
class PartDTask:
    """Part D task loaded from raw CMS snapshots or their verified preparation."""

    prepared_dir: Path
    report: dict[str, Any]
    contract_path: Path
    cohorts: dict[int, set[str]]
    rows_by_year: dict[int, list[_ProjectedRow]]
    _temporary_directory: tempfile.TemporaryDirectory[str] | None = None

    name = "partd_prescriber_drug"

    @classmethod
    def from_source_root(
        cls,
        source_root: Path,
        *,
        manifest_path: Path | None = None,
        preparation_dir: Path | None = None,
        contract_path: Path | None = None,
        cohort_size: int = 2000,
    ) -> "PartDTask":
        """Verify raw snapshots and prepare edges without fitting any model.

        Pass ``preparation_dir`` to retain the generated, provenance-checked
        ``edges.csv`` and ``report.json``; when omitted, a private temporary
        preparation is retained for the lifetime of this task.
        """
        if manifest_path is None:
            manifest_path = (
                Path(__file__).resolve().parents[3]
                / "data"
                / "manifests"
                / "partd_feasibility_v0_2_lookback.json"
            )
        temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        if preparation_dir is None:
            temporary_directory = tempfile.TemporaryDirectory(prefix="healthgraphbench-partd-")
            preparation_dir = Path(temporary_directory.name) / "prepared"
        try:
            prepare_execution(
                Path(source_root),
                Path(manifest_path),
                Path(preparation_dir),
                cohort_size=cohort_size,
            )
            task = cls.from_prepared_input(preparation_dir, contract_path=contract_path)
        except BaseException:
            if temporary_directory is not None:
                temporary_directory.cleanup()
            raise
        task._temporary_directory = temporary_directory
        return task

    @classmethod
    def from_prepared_input(
        cls,
        prepared_dir: Path,
        *,
        contract_path: Path | None = None,
        allow_feasibility: bool = False,
    ) -> "PartDTask":
        prepared_dir = Path(prepared_dir)
        report, input_rows, cohorts, _ = _load_input(
            prepared_dir,
            allow_execution_preparation=True,
        )
        expected_kind = (
            {"partd_execution_preparation", "partd_feasibility"}
            if allow_feasibility
            else {"partd_execution_preparation"}
        )
        if report.get("record_kind") not in expected_kind:
            raise ValueError(
                "PartDTask requires raw execution preparation"
                + (" or explicitly enabled prepared feasibility input" if allow_feasibility else "")
            )
        projected_rows, _ = _project_rows(input_rows, "generic")
        return cls(
            prepared_dir=prepared_dir,
            report=report,
            contract_path=_contract_path(contract_path),
            cohorts=cohorts,
            rows_by_year=projected_rows,
        )

    def get_split(self, name: str) -> Split:
        normalized = name.strip().lower()
        if normalized == "train":
            return Split(
                self,
                "train",
                {"history_years": [2019, 2020, 2021, 2022], "cutoff": 2022},
            )
        if normalized == "validation":
            return Split(self, "validation", {"target_year": 2023, "history_through": 2022})
        if normalized == "test":
            return Split(self, "test", {"target_year": 2024, "history_through": 2023})
        raise ValueError(f"Unknown Part D split {name!r}; expected train, validation, or test")

    def _validate_splits(self, train: Split, validation: Split, test: Split) -> None:
        expected = (self.get_split("train"), self.get_split("validation"), self.get_split("test"))
        actual = (train, validation, test)
        if any(split.task is not self for split in actual):
            raise ValueError("all Part D splits must belong to this task")
        if any(split.name != required.name or split.metadata != required.metadata
               for split, required in zip(actual, expected, strict=True)):
            raise ValueError("Part D requires the ordered train, validation, and test splits")

    def _target_history(self, year: int) -> tuple[_History, tuple[int, ...], set[str]]:
        if year == 2023:
            prior_years = (2019, 2020, 2021, 2022)
        elif year == 2024:
            prior_years = (2019, 2020, 2021, 2022, 2023)
        else:
            raise ValueError(f"unsupported Part D target year {year}")
        cohort = self.cohorts[year]
        history = _build_history(self.rows_by_year, prior_years, cohort)
        return history, prior_years, cohort

    def history_view(self, split: Split | str) -> PartDHistoryView:
        """Return an immutable view containing only strictly prior observations.

        ``train`` and ``validation`` expose the same 2019-2022 history used to
        predict 2023. ``test`` exposes history through 2023 for 2024 prediction.
        Target-year rows and labels are never included in a view.
        """
        if isinstance(split, str):
            split = self.get_split(split)
        if split.task is not self:
            raise ValueError("Part D history view requires a split from this task")
        if split.name not in {"train", "validation", "test"}:
            raise ValueError(f"unknown Part D split {split.name!r}")
        target_year = 2024 if split.name == "test" else 2023
        expected = self.get_split(split.name)
        if split.metadata != expected.metadata:
            raise ValueError("Part D history view rejects altered split metadata")
        history, prior_years, _ = self._target_history(target_year)
        return _history_view(history, target_year, prior_years)

    def _rank_target(
        self,
        year: int,
        scorer: ScoreCallable,
        *,
        retain_candidate_scores: bool = False,
    ) -> list[dict[str, Any]]:
        history, prior_years, cohort = self._target_history(year)
        view = _history_view(history, year, prior_years)
        current_by_provider: dict[str, set[DrugId]] = {}
        for row in self.rows_by_year[year]:
            if row.npi in cohort:
                current_by_provider.setdefault(row.npi, set()).add(row.drug)
        rows: list[dict[str, Any]] = []
        for npi in sorted(cohort):
            own_history = history.provider_drugs.get(npi, set())
            candidates = _candidate_drugs(history, npi)
            candidate_ids = tuple(sorted(candidates))
            positives = {
                drug
                for drug in current_by_provider.get(npi, set())
                if drug not in own_history and drug in history.drug_providers
            }
            raw_scores = scorer(view, npi, candidate_ids)
            if not isinstance(raw_scores, Mapping) or set(raw_scores) != candidates:
                raise ValueError(
                    f"ranker must score every Part D candidate exactly once for NPI {npi} in {year}"
                )
            scores: dict[DrugId, float] = {}
            for drug in candidate_ids:
                raw_score = raw_scores[drug]
                if isinstance(raw_score, bool):
                    raise ValueError(f"ranker returned a boolean score for candidate {drug!r}")
                score = float(raw_score)
                if not math.isfinite(score):
                    raise ValueError(f"ranker returned a non-finite score for candidate {drug!r}")
                scores[drug] = score
            positive_ranks = _positive_ranks(candidates, positives, scores, history)
            recommendations = _top_recommendations(candidates, scores, history)
            row = {
                "year": year,
                "npi": npi,
                "eligible": bool(own_history),
                "candidate_count": len(candidates),
                "positive_count": len(positives),
                "positives": sorted(positives),
                "positive_ranks": sorted(positive_ranks.values()),
                "recommendations": [
                    {"drug": drug, "rank": rank, "score": score}
                    for rank, (drug, score) in enumerate(recommendations, start=1)
                ],
            }
            if retain_candidate_scores:
                row["candidate_scores"] = {
                    drug: scores[drug] for drug in candidate_ids
                }
            rows.append(row)
        return rows

    @staticmethod
    def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
        accumulator = _EvaluationAccumulator()
        for row in rows:
            recommendation_rows = row["recommendations"]
            accumulator.add(
                str(row["npi"]),
                eligible=bool(row["eligible"]),
                candidate_count=int(row["candidate_count"]),
                positives=set(row["positives"]),
                positive_ranks=row["positive_ranks"],
                recommendations=[item["drug"] for item in recommendation_rows],
                recommendation_scores=[float(item["score"]) for item in recommendation_rows],
                high_confidence_threshold=None,
            )
        metrics = accumulator.as_dict()
        all_provider_years = metrics["all_provider_years"]
        for name in tuple(all_provider_years):
            if "high_confidence" in name:
                del all_provider_years[name]
        return metrics

    def predict_ranker(
        self,
        model_name: str,
        train: Split,
        validation: Split,
        test: Split,
        score_callable: ScoreCallable,
    ) -> PredictionSet:
        """Score and evaluate a callable ranker without exposing target labels.

        The callable receives ``(history_view, npi, candidate_ids)`` and must
        return one finite score for every supplied generic-name candidate.
        """
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("Part D ranker name must be a non-empty string")
        if not callable(score_callable):
            raise TypeError("Part D score_callable must be callable")
        self._validate_splits(train, validation, test)
        validation_rows = self._rank_target(2023, score_callable)
        test_rows = self._rank_target(2024, score_callable)
        return PredictionSet(
            task_name=self.name,
            method=model_name,
            split="test",
            payload={
                "representation": "generic",
                "validation": self._metrics(validation_rows),
                "test": self._metrics(test_rows),
                "pooled_provider_year": self._metrics([*validation_rows, *test_rows]),
                "validation_predictions": validation_rows,
                "test_predictions": test_rows,
                "predictions": [*validation_rows, *test_rows],
            },
        )

    def _builtin_scorer(self, method: str) -> ScoreCallable:
        fitted: dict[int, tuple[_History, _FeatureContext, Any]] = {}

        def score(
            view: PartDHistoryView,
            npi: str,
            candidates: tuple[DrugId, ...],
        ) -> Mapping[DrugId, float]:
            year = view.target_year
            if year not in fitted:
                history, _, _ = self._target_history(year)
                context = _feature_context(history, year)
                model: Any = None
                if method == "tabular_logistic":
                    model = _fit_logistic(context)
                elif method == "graph_bpr":
                    model = _fit_graph_bpr(history, year)
                fitted[year] = (history, context, model)
            history, context, model = fitted[year]
            if method == "specialty_popularity":
                scores, _ = _specialty_scores(
                    history,
                    npi,
                    set(candidates),
                    context.latest_specialties,
                    context.specialty_support,
                )
                return scores
            if method == "history_overlap":
                return _overlap_scores(history, npi, set(candidates))
            if method == "tabular_logistic":
                return {drug: model.score(context.features(npi, drug)) for drug in candidates}
            specialty = history.latest_specialty(npi)
            return {drug: model.score(npi, drug, specialty) for drug in candidates}

        return score

    def fit_predict(
        self,
        method: str,
        train: Split,
        validation: Split,
        test: Split,
    ) -> PredictionSet:
        if method not in {
            "specialty_popularity",
            "history_overlap",
            "tabular_logistic",
            "graph_bpr",
        }:
            raise ValueError(f"Unknown Part D method {method!r}")
        return self.predict_ranker(
            method,
            train,
            validation,
            test,
            self._builtin_scorer(method),
        )

    def evaluate(self, predictions: PredictionSet) -> dict[str, Any]:
        if predictions.task_name != self.name or predictions.split != "test":
            raise ValueError("Part D evaluation requires test predictions for this task")
        payload = predictions.payload
        if not isinstance(payload, dict):
            raise ValueError("Part D predictions must contain a mapping payload")
        rows = payload.get("test_predictions")
        if not isinstance(rows, list) or not rows:
            raise ValueError("Part D test predictions are missing")
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("Part D test predictions must be row mappings")
        if any(row.get("year") != 2024 for row in rows):
            raise ValueError("Part D test evaluation rejects mixed target years")
        providers = [str(row.get("npi", "")) for row in rows]
        if len(providers) != len(set(providers)) or set(providers) != self.cohorts[2024]:
            raise ValueError("Part D test predictions must contain every target provider exactly once")
        return self._metrics(rows)

    def manifest(self) -> dict[str, Any]:
        contract = _read_object(self.contract_path)
        task = contract["task"]
        return {
            "benchmark_version": contract["version"],
            "task": self.name,
            "admission_status": task["admission_status"],
            "source": task["source"],
            "target": task["target"],
            "drug_identity": task["drug_identity"],
            "temporal_split": task["temporal_split"],
            "provider_cohort": task["provider_cohort"],
            "candidate_construction": task["candidate_construction"],
            "ranking_tie_policy": task["ranking_tie_policy"],
            "metrics": task["metrics"],
            "preparation_record_kind": self.report["record_kind"],
            "preparation_dir": str(self.prepared_dir),
            "preparation_report_sha256": sha256_file(self.prepared_dir / "report.json"),
            "preparation_edges_sha256": sha256_file(self.prepared_dir / "edges.csv"),
        }

    def source_manifest(self) -> list[dict[str, Any]]:
        report_path = self.prepared_dir / "report.json"
        edges_path = self.prepared_dir / "edges.csv"
        files = [
            {
                "path": str(self.contract_path),
                "bytes": self.contract_path.stat().st_size,
                "sha256": sha256_file(self.contract_path),
            },
            {
                "path": str(report_path),
                "bytes": report_path.stat().st_size,
                "sha256": sha256_file(report_path),
            },
            {
                "path": str(edges_path),
                "bytes": edges_path.stat().st_size,
                "sha256": sha256_file(edges_path),
            },
        ]
        sources = self.report.get("sources", {})
        source_root = Path(str(sources.get("source_root", "")))
        manifest_value = sources.get("manifest_path")
        if isinstance(manifest_value, str) and manifest_value:
            manifest_path = Path(manifest_value)
            if not manifest_path.is_absolute():
                manifest_path = source_root / manifest_path
            if manifest_path.is_file():
                files.append(
                    {
                        "path": str(manifest_path),
                        "bytes": manifest_path.stat().st_size,
                        "sha256": sha256_file(manifest_path),
                    }
                )
        for entry in sources.get("files", []):
            relative = Path(str(entry["path"]))
            path = relative if relative.is_absolute() else source_root / relative
            files.append(
                {
                    "path": str(path),
                    "bytes": int(entry["bytes"]),
                    "sha256": str(entry["sha256"]),
                }
            )
        return files


