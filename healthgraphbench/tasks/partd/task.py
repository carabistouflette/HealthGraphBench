"""Common-interface adapter for the admitted Part D replication task."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...core import PredictionSet, Split


_ALLOWED_METHODS = (
    "specialty_popularity",
    "history_overlap",
    "tabular_logistic",
    "graph_bpr",
)
_TARGET_YEARS = (2023, 2024)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load Part D artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Part D artifact must contain an object: {path}")
    return value


@dataclass(slots=True)
class PartDTask:
    """A Part D task backed by a verified model-gate result artifact.

    The model-gate run is intentionally consumed as an immutable result input.
    It contains the primary generic-name rankings and the aggregate metrics for
    the 2023 validation and 2024 held-out target years.
    """

    artifact_dir: Path
    report: dict[str, Any]
    contract_path: Path
    _rankings_by_year: dict[int, list[dict[str, Any]]] | None = None

    name = "partd_prescriber_drug"

    @classmethod
    def from_source_root(
        cls,
        source_root: Path,
        *,
        model_gate_dir: Path | None = None,
        contract_path: Path | None = None,
        **_: Any,
    ) -> "PartDTask":
        """Load a task from a model-gate artifact directory.

        ``source_root`` may itself be the model-gate directory.  The explicit
        ``model_gate_dir`` keyword is useful when a caller keeps raw downloads
        and generated results in separate locations; raw source conversion is
        performed by the dedicated Part D gate scripts.
        """

        artifact_dir = Path(model_gate_dir) if model_gate_dir is not None else Path(source_root)
        return cls.from_model_gate(artifact_dir, contract_path=contract_path)

    @classmethod
    def from_model_gate(
        cls,
        artifact_dir: Path,
        *,
        contract_path: Path | None = None,
    ) -> "PartDTask":
        artifact_dir = Path(artifact_dir)
        report_path = artifact_dir / "report.json"
        rankings_path = artifact_dir / "rankings.jsonl"
        if not report_path.is_file() or not rankings_path.is_file():
            raise FileNotFoundError(
                "Part D common interface requires report.json and rankings.jsonl in the "
                f"model-gate directory: {artifact_dir}"
            )
        report = _read_object(report_path)
        if report.get("record_kind") != "partd_model_gate":
            raise ValueError("Part D artifact report must be a partd_model_gate record")
        configuration = report.get("configuration")
        if not isinstance(configuration, dict):
            raise ValueError("Part D model-gate report is missing configuration")
        if configuration.get("primary_representation") != "generic":
            raise ValueError("Part D common interface requires the generic primary representation")
        if configuration.get("methods") != list(_ALLOWED_METHODS):
            raise ValueError(
                "Part D model-gate methods do not match the admitted method order: "
                f"{configuration.get('methods')!r}"
            )
        expected_hash = report.get("artifact_hashes", {}).get("rankings.jsonl")
        actual_hash = _sha256_file(rankings_path)
        if expected_hash != actual_hash:
            raise ValueError(
                f"Part D ranking artifact hash mismatch: expected {expected_hash}, got {actual_hash}"
            )
        if contract_path is not None:
            resolved_contract = Path(contract_path)
        else:
            resolved_contract = (
                Path(__file__).resolve().parents[3] / "configs" / "task_contract_v0_2.json"
            )
            if not resolved_contract.is_file():
                resolved_contract = Path(__file__).resolve().with_name(
                    "task_contract_v0_2.json"
                )
        if not resolved_contract.is_file():
            raise FileNotFoundError(f"Part D admission contract is missing: {resolved_contract}")
        contract = _read_object(resolved_contract)
        task_contract = contract.get("task")
        if (
            contract.get("version") != "0.2"
            or not isinstance(task_contract, dict)
            or task_contract.get("id") != cls.name
            or task_contract.get("drug_identity") != "exact_trimmed_generic_name"
        ):
            raise ValueError("Part D model-gate artifact is incompatible with the v0.2 admission contract")
        return cls(artifact_dir, report, resolved_contract)

    def get_split(self, name: str) -> Split:
        """Return the admitted Part D temporal split by name."""

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

    def _rankings(self) -> dict[int, list[dict[str, Any]]]:
        if self._rankings_by_year is not None:
            return self._rankings_by_year
        rankings_path = self.artifact_dir / "rankings.jsonl"
        by_year: dict[int, list[dict[str, Any]]] = {year: [] for year in _TARGET_YEARS}
        try:
            with rankings_path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError(f"ranking row {line_number} is not an object")
                    if row.get("representation") != "generic":
                        continue
                    year = row.get("year")
                    if year not in _TARGET_YEARS:
                        raise ValueError(f"unexpected Part D ranking year at row {line_number}: {year!r}")
                    by_year[year].append(row)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"unable to load Part D rankings {rankings_path}: {exc}") from exc
        for year, rows in by_year.items():
            rows.sort(key=lambda row: str(row.get("npi", "")))
            if not rows:
                raise ValueError(f"Part D ranking artifact has no generic rows for {year}")
        self._rankings_by_year = by_year
        return by_year

    def _prediction_rows(self, year: int, method: str) -> list[dict[str, Any]]:
        rows = []
        for row in self._rankings()[year]:
            positives = row.get("positives", [])
            recommendations = row.get("recommendations", {}).get(method, [])
            rows.append(
                {
                    "year": year,
                    "npi": str(row["npi"]),
                    "eligible": bool(row["eligible"]),
                    "candidate_count": int(row["candidate_count"]),
                    "positive_count": int(row["positive_count"]),
                    "positive_ranks": sorted(
                        int(positive["ranks"][method]) for positive in positives
                    ),
                    "recommendations": list(recommendations),
                }
            )
        return rows

    def _metrics(self, year: int, method: str) -> dict[str, Any]:
        representation = self.report["metrics"]["representations"]["generic"]
        return dict(representation["by_year"][str(year)]["by_method"][method])

    def fit_predict(
        self, method: str, train: Split, validation: Split, test: Split
    ) -> PredictionSet:
        if method not in _ALLOWED_METHODS:
            raise ValueError(f"Unknown Part D method {method!r}")
        if {train.name, validation.name, test.name} != {"train", "validation", "test"}:
            raise ValueError("Part D requires train, validation, and test splits")
        if train.task is not self or validation.task is not self or test.task is not self:
            raise ValueError("all splits must belong to this Part D task")
        return PredictionSet(
            self.name,
            method,
            "test",
            {
                "representation": "generic",
                "validation": self._metrics(2023, method),
                "test": self._metrics(2024, method),
                "pooled_provider_year": dict(
                    self.report["metrics"]["representations"]["generic"]["pooled_provider_year"]
                    ["by_method"][method]
                ),
                "predictions": [
                    *self._prediction_rows(2023, method),
                    *self._prediction_rows(2024, method),
                ],
            },
        )

    def evaluate(self, predictions: PredictionSet) -> dict[str, Any]:
        if predictions.task_name != self.name or predictions.split != "test":
            raise ValueError("Part D evaluation requires test predictions for this task")
        return dict(predictions.payload["test"])

    def manifest(self) -> dict[str, Any]:
        contract = _read_object(self.contract_path)
        task = contract["task"]
        return {
            "benchmark_version": contract["version"],
            "task": self.name,
            "admission_status": task["admission_status"],
            "model_gate_status": "no_go_for_escalation",
            "source": task["source"],
            "target": task["target"],
            "drug_identity": task["drug_identity"],
            "temporal_split": task["temporal_split"],
            "provider_cohort": task["provider_cohort"],
            "candidate_construction": task["candidate_construction"],
            "ranking_tie_policy": task["ranking_tie_policy"],
            "metrics": task["metrics"],
            "methods": list(_ALLOWED_METHODS),
            "suppression_limitation": task["suppression_limitation"],
            "artifact_dir": str(self.artifact_dir),
            "report_sha256": _sha256_file(self.artifact_dir / "report.json"),
            "rankings_sha256": _sha256_file(self.artifact_dir / "rankings.jsonl"),
        }

    def source_manifest(self) -> list[dict[str, Any]]:
        return [
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for path in (
                self.contract_path,
                self.artifact_dir / "report.json",
                self.artifact_dir / "rankings.jsonl",
            )
        ]
