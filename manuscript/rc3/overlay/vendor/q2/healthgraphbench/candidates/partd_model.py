"""Bounded learned-model gate for the CMS Part D feasibility artifacts."""

from __future__ import annotations

import csv
import hashlib
import heapq
import json
import math
import struct
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

from healthgraphbench.data import sha256_file

from .partd import EDGE_COLUMNS

MODEL_GATE_RECORD_KIND = "partd_model_gate"
MODEL_GATE_VERSION = "partd_model_gate_v1"
REPRESENTATIONS: tuple[str, ...] = ("generic", "variant")
METHOD_NAMES: tuple[str, ...] = (
    "specialty_popularity",
    "history_overlap",
    "tabular_logistic",
    "graph_bpr",
)
TOP_KS: tuple[int, ...] = (5, 10, 20)
FEATURE_NAMES: tuple[str, ...] = (
    "log_global_provider_support",
    "log_global_claim_total",
    "log_global_claim_mean",
    "log_provider_history_size",
    "log_provider_claim_total",
    "log_drug_history_year_count",
    "log_drug_age_years",
    "log_specialty_provider_support",
    "specialty_provider_fraction",
    "target_specialty_available",
)

TABULAR_NEGATIVE_RATIO = 5
TABULAR_EPOCHS = 18
TABULAR_LEARNING_RATE = 0.10
TABULAR_L2 = 0.01
GRAPH_DIMENSION = 12
GRAPH_BPR_EPOCHS = 5
GRAPH_BPR_NEGATIVE_SAMPLES = 3
GRAPH_BPR_LEARNING_RATE = 0.03
GRAPH_BPR_REGULARIZATION = 0.001
GRAPH_SPECIALTY_WEIGHT = 0.35
HIGH_SCORE_QUANTILE = 0.95

DrugId = str | tuple[str, str]


@dataclass(frozen=True, slots=True)
class _InputEdge:
    year: int
    npi: str
    brand_name: str
    generic_name: str
    claims: int
    specialty: str


@dataclass(slots=True)
class _ProjectedAggregate:
    claims: int = 0
    specialties: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class _ProjectedRow:
    year: int
    npi: str
    drug: DrugId
    claims: int
    specialties: tuple[str, ...]


@dataclass(slots=True)
class _History:
    provider_drugs: dict[str, set[DrugId]] = field(
        default_factory=lambda: defaultdict(set)
    )
    drug_providers: dict[DrugId, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    provider_year_drugs: dict[tuple[int, str], set[DrugId]] = field(
        default_factory=lambda: defaultdict(set)
    )
    provider_year_specialties: dict[tuple[int, str], set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    provider_years: dict[str, set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )
    latest_observed_year: dict[str, int] = field(default_factory=dict)
    drug_claim_totals: dict[DrugId, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    provider_drug_claims: dict[tuple[str, DrugId], int] = field(
        default_factory=lambda: defaultdict(int)
    )
    provider_claim_totals: dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    drug_years: dict[DrugId, set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )
    drug_last_year: dict[DrugId, int] = field(default_factory=dict)

    def add(self, row: _ProjectedRow) -> None:
        drug = row.drug
        self.provider_drugs[row.npi].add(drug)
        self.drug_providers[drug].add(row.npi)
        self.provider_year_drugs[(row.year, row.npi)].add(drug)
        self.provider_years[row.npi].add(row.year)
        self.drug_claim_totals[drug] += row.claims
        self.provider_drug_claims[(row.npi, drug)] += row.claims
        self.provider_claim_totals[row.npi] += row.claims
        self.drug_years[drug].add(row.year)
        previous_last = self.drug_last_year.get(drug)
        if previous_last is None or row.year > previous_last:
            self.drug_last_year[drug] = row.year
        for specialty in row.specialties:
            if specialty:
                self.provider_year_specialties[(row.year, row.npi)].add(specialty)
        previous_provider_year = self.latest_observed_year.get(row.npi)
        if previous_provider_year is None or row.year > previous_provider_year:
            self.latest_observed_year[row.npi] = row.year

    def latest_specialty(self, npi: str) -> str | None:
        year = self.latest_observed_year.get(npi)
        if year is None:
            return None
        values = self.provider_year_specialties.get((year, npi), set())
        if len(values) != 1:
            return None
        return next(iter(values))


@dataclass(slots=True)
class _FeatureContext:
    history: _History
    target_year: int
    latest_specialties: dict[str, str | None]
    specialty_support: dict[str, dict[DrugId, int]]

    def features(self, npi: str, drug: DrugId) -> tuple[float, ...]:
        own_drugs = self.history.provider_drugs.get(npi, set())
        own_support = 1 if npi in self.history.drug_providers.get(drug, set()) else 0
        global_support = len(self.history.drug_providers.get(drug, set())) - own_support
        own_claims = self.history.provider_drug_claims.get((npi, drug), 0)
        global_claim_total = self.history.drug_claim_totals.get(drug, 0) - own_claims
        provider_year_count = len(self.history.provider_years.get(npi, set()))
        target_specialty = self.latest_specialties.get(npi)
        if target_specialty is None:
            specialty_support = 0
            specialty_fraction = 0.0
            specialty_available = 0.0
        else:
            specialty_support = self.specialty_support.get(target_specialty, {}).get(drug, 0)
            if own_support and self.history.latest_specialty(npi) == target_specialty:
                specialty_support -= 1
            specialty_fraction = specialty_support / max(1, global_support)
            specialty_available = 1.0
        last_year = self.history.drug_last_year.get(drug, self.target_year)
        drug_age = max(0, self.target_year - last_year)
        values = (
            math.log1p(max(0, global_support)),
            math.log1p(max(0, global_claim_total)),
            math.log1p(max(0.0, global_claim_total / max(1, global_support))),
            math.log1p(len(own_drugs)),
            math.log1p(self.history.provider_claim_totals.get(npi, 0)),
            math.log1p(len(self.history.drug_years.get(drug, set()))),
            math.log1p(drug_age),
            math.log1p(max(0, specialty_support)),
            specialty_fraction,
            specialty_available,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError(f"non-finite tabular feature for provider={npi}, drug={drug!r}")
        return values


@dataclass(frozen=True, slots=True)
class _LogisticModel:
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    intercept: float
    summary: dict[str, object]

    def score(self, features: Sequence[float]) -> float:
        value = self.intercept + sum(
            weight * ((feature - mean) / scale)
            for feature, mean, scale, weight in zip(
                features, self.means, self.scales, self.weights, strict=True
            )
        )
        if not math.isfinite(value):
            raise ValueError("non-finite tabular logistic score")
        return value


@dataclass(slots=True)
class _GraphBprModel:
    provider_embeddings: dict[str, np.ndarray]
    drug_embeddings: dict[DrugId, np.ndarray]
    specialty_embeddings: dict[str, np.ndarray]
    specialty_weight: float
    summary: dict[str, object]

    def score(self, npi: str, drug: DrugId, specialty: str | None) -> float:
        provider = self.provider_embeddings.get(npi)
        target = self.drug_embeddings.get(drug)
        if provider is None or target is None:
            return 0.0
        value = float(np.dot(provider, target))
        if specialty is not None:
            specialty_vector = self.specialty_embeddings.get(specialty)
            if specialty_vector is not None:
                value += self.specialty_weight * float(np.dot(specialty_vector, target))
        if not math.isfinite(value):
            raise ValueError(f"non-finite graph score for provider={npi}, drug={drug!r}")
        return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _stable_integer(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _stable_vector(kind: str, key: object, dimension: int) -> list[float]:
    return [
        0.05 * ((_stable_integer("initial", kind, key, index) / 2**64) * 2.0 - 1.0)
        for index in range(dimension)
    ]


def _sigmoid(value: float) -> float:
    if value >= 0:
        exponent = math.exp(-value) if value < 700 else 0.0
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(value) if value > -700 else 0.0
    return exponent / (1.0 + exponent)


def _drug_sort_key(drug: DrugId) -> tuple[str, ...]:
    return drug if isinstance(drug, tuple) else (drug,)


def _drug_token(drug: DrugId) -> str:
    return "\x1f".join(_drug_sort_key(drug))


def _drug_payload(drug: DrugId) -> dict[str, str]:
    if isinstance(drug, tuple):
        return {"brand_name": drug[0], "generic_name": drug[1]}
    return {"generic_name": drug}


def _validate_npi(value: object, *, path: Path, row_number: int) -> str:
    npi = "" if value is None else str(value)
    if len(npi) != 10 or not npi.isascii() or any(char < "0" or char > "9" for char in npi):
        raise ValueError(f"invalid npi in model input: file={path}, row={row_number}, value={npi!r}")
    return npi


def _load_input(
    feasibility_dir: Path,
    *,
    allow_execution_preparation: bool = False,
) -> tuple[
    dict[str, Any],
    dict[int, list[_InputEdge]],
    dict[int, set[str]],
    dict[str, object],
]:
    report_path = feasibility_dir / "report.json"
    edges_path = feasibility_dir / "edges.csv"
    if not report_path.is_file() or not edges_path.is_file():
        raise FileNotFoundError(
            f"model input must contain report.json and edges.csv: {feasibility_dir}"
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load Part D model input report {report_path}: {exc}") from exc
    accepted_kinds = {"partd_feasibility"}
    if allow_execution_preparation:
        accepted_kinds.add("partd_execution_preparation")
    if not isinstance(report, dict) or report.get("record_kind") not in accepted_kinds:
        raise ValueError(
            "model input report must be a partd_feasibility record"
            + (" or partd_execution_preparation record" if allow_execution_preparation else "")
        )
    configuration = report.get("configuration")
    if not isinstance(configuration, dict):
        raise ValueError("Part D model input report is missing configuration")
    years = configuration.get("years")
    score_years = configuration.get("score_years")
    roles = configuration.get("evaluation_roles")
    if years != [2019, 2020, 2021, 2022, 2023, 2024]:
        raise ValueError(
            "Part D model input requires the frozen 2019-2024 source; "
            f"got years={years!r}"
        )
    if score_years != [2022, 2023, 2024] or roles != {
        "2022": "train_target",
        "2023": "validation",
        "2024": "held_out_test",
    }:
        raise ValueError(
            "Part D model input requires 2022 train_target, 2023 validation, and "
            f"2024 held_out_test; got score_years={score_years!r}, roles={roles!r}"
        )
    cohort_value = report.get("cohort")
    if not isinstance(cohort_value, dict) or not isinstance(
        cohort_value.get("by_target_year"), dict
    ):
        raise ValueError("Part D model input report is missing target-year cohorts")
    cohorts: dict[int, set[str]] = {}
    for year in (2022, 2023, 2024):
        values = cohort_value["by_target_year"].get(str(year))
        if not isinstance(values, list) or not values:
            raise ValueError(f"missing non-empty target cohort for year {year}")
        cohorts[year] = set(values)
        if any(
            len(str(npi)) != 10
            or not str(npi).isascii()
            or any(char < "0" or char > "9" for char in str(npi))
            for npi in values
        ):
            raise ValueError(f"invalid target cohort NPI for year {year}")
    expected_edge_hash = report.get("artifact_hashes", {}).get("edges.csv")
    actual_edge_hash = sha256_file(edges_path)
    if expected_edge_hash != actual_edge_hash:
        raise ValueError(
            f"model input edge hash mismatch for {edges_path}: "
            f"expected {expected_edge_hash}, got {actual_edge_hash}"
        )
    rows_by_year: dict[int, list[_InputEdge]] = {year: [] for year in years}
    seen: set[tuple[int, str, str, str]] = set()
    try:
        with edges_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames != list(EDGE_COLUMNS):
                raise ValueError(
                    f"model input edge header mismatch: got {reader.fieldnames!r}, "
                    f"expected {list(EDGE_COLUMNS)!r}"
                )
            for row_number, raw in enumerate(reader, start=1):
                if None in raw:
                    raise ValueError(f"malformed model input edge row={row_number}")
                try:
                    year = int(str(raw["year"]).strip())
                    npi = _validate_npi(raw.get("npi"), path=edges_path, row_number=row_number)
                    brand_name = str(raw.get("brand_name") or "").strip()
                    generic_name = str(raw.get("generic_name") or "").strip()
                    claims = int(str(raw.get("claims") or "").strip())
                    specialty = str(raw.get("specialty") or "").strip()
                except (TypeError, ValueError, KeyError) as exc:
                    raise ValueError(
                        f"invalid model input edge: file={edges_path}, row={row_number}: {exc}"
                    ) from exc
                if year not in rows_by_year:
                    raise ValueError(f"unexpected model input service year {year}")
                if claims < 11:
                    raise ValueError(
                        f"model input claims must be >= 11: file={edges_path}, row={row_number}"
                    )
                if not brand_name and not generic_name:
                    raise ValueError(
                        f"model input edge has blank drug identity: file={edges_path}, row={row_number}"
                    )
                key = (year, npi, brand_name, generic_name)
                if key in seen:
                    raise ValueError(f"duplicate model input edge: file={edges_path}, row={row_number}")
                seen.add(key)
                rows_by_year[year].append(
                    _InputEdge(year, npi, brand_name, generic_name, claims, specialty)
                )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"unable to parse model input edges {edges_path}: {exc}") from exc
    expected_count = report.get("audits", {}).get("total_retained_edges")
    actual_count = sum(len(rows) for rows in rows_by_year.values())
    if expected_count != actual_count:
        raise ValueError(
            f"model input edge count mismatch: report={expected_count}, parsed={actual_count}"
        )
    union_cohort = set().union(*cohorts.values())
    unknown_providers = {
        row.npi for rows in rows_by_year.values() for row in rows if row.npi not in union_cohort
    }
    if unknown_providers:
        raise ValueError(
            f"model input contains providers outside target cohorts: {sorted(unknown_providers)[:3]}"
        )
    if report.get("record_kind") == "partd_feasibility":
        provenance = {
            "feasibility_dir": str(feasibility_dir),
            "feasibility_report": str(report_path),
            "feasibility_report_sha256": sha256_file(report_path),
            "feasibility_edges": str(edges_path),
            "feasibility_edges_sha256": actual_edge_hash,
            "source_manifest_sha256": report.get("sources", {}).get("manifest_sha256"),
            "source_commit": report.get("source_commit"),
        }
    else:
        provenance = {
            "prepared_dir": str(feasibility_dir),
            "prepared_report": str(report_path),
            "prepared_report_sha256": sha256_file(report_path),
            "prepared_edges": str(edges_path),
            "prepared_edges_sha256": actual_edge_hash,
            "source_manifest_sha256": report.get("sources", {}).get("manifest_sha256"),
            "source_commit": report.get("source_commit"),
        }
    return report, rows_by_year, cohorts, provenance


def _project_rows(
    rows_by_year: Mapping[int, Sequence[_InputEdge]], representation: str
) -> tuple[dict[int, list[_ProjectedRow]], dict[str, object]]:
    if representation not in REPRESENTATIONS:
        raise ValueError(f"unsupported Part D model representation: {representation!r}")
    projected: dict[int, list[_ProjectedRow]] = {}
    excluded_blank_generic = 0
    aggregate_count = 0
    raw_count = 0
    for year in sorted(rows_by_year):
        grouped: dict[tuple[str, DrugId], _ProjectedAggregate] = {}
        for row in rows_by_year[year]:
            raw_count += 1
            if representation == "generic":
                if not row.generic_name:
                    excluded_blank_generic += 1
                    continue
                drug: DrugId = row.generic_name
            else:
                drug = (row.brand_name, row.generic_name)
            key = (row.npi, drug)
            aggregate = grouped.setdefault(key, _ProjectedAggregate())
            aggregate.claims += row.claims
            if row.specialty:
                aggregate.specialties.add(row.specialty)
        aggregate_count += len(grouped)
        projected[year] = [
            _ProjectedRow(year, npi, drug, aggregate.claims, tuple(sorted(aggregate.specialties)))
            for (npi, drug), aggregate in sorted(
                grouped.items(), key=lambda item: (item[0][0], _drug_sort_key(item[0][1]))
            )
        ]
    return projected, {
        "representation": representation,
        "drug_node": "generic_name" if representation == "generic" else "(brand_name, generic_name)",
        "blank_generic_policy": (
            "exclude rows with blank generic_name from the primary generic representation"
            if representation == "generic"
            else "retain exact source-native brand_name and generic_name"
        ),
        "raw_edge_rows": raw_count,
        "projected_provider_drug_year_rows": aggregate_count,
        "rows_excluded_blank_generic": excluded_blank_generic,
        "aggregation": "sum claims and union nonblank specialties within each projected provider-drug-year key",
    }


def _build_history(
    rows_by_year: Mapping[int, Sequence[_ProjectedRow]],
    prior_years: Sequence[int],
    cohort: set[str],
) -> _History:
    history = _History()
    for year in prior_years:
        for row in rows_by_year[year]:
            if row.npi in cohort:
                history.add(row)
    return history


def _specialty_support(history: _History) -> dict[str, dict[DrugId, int]]:
    latest = {npi: history.latest_specialty(npi) for npi in history.provider_drugs}
    support: dict[str, dict[DrugId, int]] = defaultdict(dict)
    for drug, providers in history.drug_providers.items():
        for npi in sorted(providers):
            specialty = latest.get(npi)
            if specialty is None:
                continue
            values = support[specialty]
            values[drug] = values.get(drug, 0) + 1
    return dict(support)


def _feature_context(history: _History, target_year: int) -> _FeatureContext:
    return _FeatureContext(
        history=history,
        target_year=target_year,
        latest_specialties={npi: history.latest_specialty(npi) for npi in history.provider_drugs},
        specialty_support=_specialty_support(history),
    )


def _candidate_drugs(history: _History, npi: str) -> set[DrugId]:
    return set(history.drug_providers).difference(history.provider_drugs.get(npi, set()))


def _training_rows(
    context: _FeatureContext,
    *,
    negative_ratio: int,
) -> Iterable[tuple[tuple[float, ...], int]]:
    history = context.history
    for npi in sorted(history.provider_drugs):
        positives = sorted(history.provider_drugs[npi], key=_drug_sort_key)
        if not positives:
            continue
        candidates = sorted(
            _candidate_drugs(history, npi),
            key=lambda drug: (
                _stable_integer("tabular-negative", context.target_year, npi, _drug_token(drug)),
                _drug_sort_key(drug),
            ),
        )
        negatives = candidates[: min(len(candidates), negative_ratio * len(positives))]
        for drug in positives:
            yield context.features(npi, drug), 1
        for drug in negatives:
            yield context.features(npi, drug), 0


def _fit_logistic(context: _FeatureContext) -> _LogisticModel:
    width = len(FEATURE_NAMES)
    count = 0
    positive_count = 0
    negative_count = 0
    totals = [0.0] * width
    squares = [0.0] * width
    for features, label in _training_rows(context, negative_ratio=TABULAR_NEGATIVE_RATIO):
        count += 1
        if label:
            positive_count += 1
        else:
            negative_count += 1
        for index, value in enumerate(features):
            totals[index] += value
            squares[index] += value * value
    if not count or not positive_count:
        raise ValueError(
            f"tabular logistic training has no positive history examples for year {context.target_year}"
        )
    means = tuple(total / count for total in totals)
    scales = tuple(
        max(math.sqrt(max(0.0, squares[index] / count - means[index] ** 2)), 1e-9)
        for index in range(width)
    )
    positive_weight = negative_count / positive_count if positive_count else 1.0
    normalizer = negative_count + positive_weight * positive_count
    weights = [0.0] * width
    intercept = 0.0
    for _ in range(TABULAR_EPOCHS):
        gradient = [0.0] * width
        intercept_gradient = 0.0
        for features, label in _training_rows(context, negative_ratio=TABULAR_NEGATIVE_RATIO):
            normalized = [
                (value - means[index]) / scales[index]
                for index, value in enumerate(features)
            ]
            logit = intercept + sum(
                weight * value for weight, value in zip(weights, normalized, strict=True)
            )
            class_weight = positive_weight if label else 1.0
            error = (_sigmoid(logit) - label) * class_weight
            intercept_gradient += error
            for index, value in enumerate(normalized):
                gradient[index] += error * value
        intercept -= TABULAR_LEARNING_RATE * intercept_gradient / normalizer
        for index in range(width):
            weights[index] -= TABULAR_LEARNING_RATE * (
                gradient[index] / normalizer + TABULAR_L2 * weights[index]
            )
    summary = {
        "feature_names": list(FEATURE_NAMES),
        "negative_sampling_ratio": TABULAR_NEGATIVE_RATIO,
        "training_rows": count,
        "positive_training_rows": positive_count,
        "negative_training_rows": negative_count,
        "positive_class_weight": positive_weight,
        "epochs": TABULAR_EPOCHS,
        "learning_rate": TABULAR_LEARNING_RATE,
        "l2": TABULAR_L2,
        "means": list(means),
        "scales": list(scales),
        "weights": list(weights),
        "intercept": intercept,
    }
    if any(
        not math.isfinite(value)
        for value in (*means, *scales, *weights, intercept, positive_weight)
    ):
        raise ValueError("tabular logistic fit produced a non-finite parameter")
    return _LogisticModel(means, scales, tuple(weights), intercept, summary)


def _parameter_hash(
    providers: Mapping[str, Sequence[float]],
    drugs: Mapping[DrugId, Sequence[float]],
    specialties: Mapping[str, Sequence[float]],
) -> str:
    digest = hashlib.sha256()
    for kind, values in (("provider", providers), ("drug", drugs), ("specialty", specialties)):
        for key in sorted(values, key=lambda value: (value,) if isinstance(value, str) else _drug_sort_key(value)):
            digest.update(kind.encode("utf-8"))
            digest.update(b"\0")
            digest.update(_drug_token(key).encode("utf-8"))
            digest.update(b"\0")
            for value in values[key]:
                digest.update(struct.pack(">d", float(value)))
    return digest.hexdigest()


def _fit_graph_bpr(history: _History, target_year: int) -> _GraphBprModel:
    providers = tuple(sorted(history.provider_drugs))
    drugs = tuple(sorted(history.drug_providers, key=_drug_sort_key))
    specialties = tuple(
        sorted(
            specialty
            for specialty in {
                history.latest_specialty(npi) for npi in providers
            }
            if specialty is not None
        )
    )
    if not providers or not drugs:
        raise ValueError(f"graph BPR training graph is empty for year {target_year}")
    provider_embeddings = {
        npi: np.asarray(_stable_vector("provider", npi, GRAPH_DIMENSION), dtype=np.float64)
        for npi in providers
    }
    drug_embeddings = {
        drug: np.asarray(_stable_vector("drug", _drug_token(drug), GRAPH_DIMENSION), dtype=np.float64)
        for drug in drugs
    }
    specialty_embeddings = {
        specialty: np.asarray(_stable_vector("specialty", specialty, GRAPH_DIMENSION), dtype=np.float64)
        for specialty in specialties
    }
    negatives_by_provider = {
        npi: tuple(sorted(_candidate_drugs(history, npi), key=_drug_sort_key))
        for npi in providers
    }
    update_count = 0
    for epoch in range(GRAPH_BPR_EPOCHS):
        for npi in providers:
            positives = tuple(sorted(history.provider_drugs[npi], key=_drug_sort_key))
            negative_pool = negatives_by_provider[npi]
            if not negative_pool:
                continue
            specialty = history.latest_specialty(npi)
            for positive in positives:
                for sample in range(GRAPH_BPR_NEGATIVE_SAMPLES):
                    negative = negative_pool[
                        _stable_integer(
                            "graph-bpr-negative",
                            target_year,
                            epoch,
                            npi,
                            _drug_token(positive),
                            sample,
                        )
                        % len(negative_pool)
                    ]
                    provider_before = provider_embeddings[npi].copy()
                    positive_before = drug_embeddings[positive].copy()
                    negative_before = drug_embeddings[negative].copy()
                    specialty_before = (
                        specialty_embeddings[specialty].copy()
                        if specialty is not None
                        else None
                    )
                    positive_score = float(np.dot(provider_before, positive_before))
                    negative_score = float(np.dot(provider_before, negative_before))
                    if specialty_before is not None:
                        positive_score += GRAPH_SPECIALTY_WEIGHT * float(
                            np.dot(specialty_before, positive_before)
                        )
                        negative_score += GRAPH_SPECIALTY_WEIGHT * float(
                            np.dot(specialty_before, negative_before)
                        )
                    coefficient = _sigmoid(-(positive_score - negative_score))
                    direction = positive_before - negative_before
                    shared = provider_before + (
                        GRAPH_SPECIALTY_WEIGHT * specialty_before
                        if specialty_before is not None
                        else 0.0
                    )
                    provider_embeddings[npi] += GRAPH_BPR_LEARNING_RATE * (
                        coefficient * direction
                        - GRAPH_BPR_REGULARIZATION * provider_before
                    )
                    drug_embeddings[positive] += GRAPH_BPR_LEARNING_RATE * (
                        coefficient * shared
                        - GRAPH_BPR_REGULARIZATION * positive_before
                    )
                    drug_embeddings[negative] += GRAPH_BPR_LEARNING_RATE * (
                        -coefficient * shared
                        - GRAPH_BPR_REGULARIZATION * negative_before
                    )
                    if specialty_before is not None:
                        specialty_embeddings[specialty] += GRAPH_BPR_LEARNING_RATE * (
                            coefficient * GRAPH_SPECIALTY_WEIGHT * direction
                            - GRAPH_BPR_REGULARIZATION * specialty_before
                        )
                    update_count += 1
    parameter_hash = _parameter_hash(
        provider_embeddings, drug_embeddings, specialty_embeddings
    )
    summary = {
        "graph": "provider-drug bipartite graph with provider-specialty relation",
        "objective": "Bayesian personalized ranking",
        "dimension": GRAPH_DIMENSION,
        "epochs": GRAPH_BPR_EPOCHS,
        "negative_samples_per_positive": GRAPH_BPR_NEGATIVE_SAMPLES,
        "learning_rate": GRAPH_BPR_LEARNING_RATE,
        "regularization": GRAPH_BPR_REGULARIZATION,
        "specialty_weight": GRAPH_SPECIALTY_WEIGHT,
        "provider_nodes": len(providers),
        "drug_nodes": len(drugs),
        "specialty_nodes": len(specialties),
        "observed_provider_drug_edges": sum(len(values) for values in history.provider_drugs.values()),
        "parameter_updates": update_count,
        "parameter_sha256": parameter_hash,
        "message_passing": False,
    }
    if any(
        not math.isfinite(float(value))
        for values in (*provider_embeddings.values(), *drug_embeddings.values(), *specialty_embeddings.values())
        for value in values
    ):
        raise ValueError("graph BPR fit produced a non-finite parameter")
    return _GraphBprModel(
        provider_embeddings,
        drug_embeddings,
        specialty_embeddings,
        GRAPH_SPECIALTY_WEIGHT,
        summary,
    )


def _global_support(history: _History, drug: DrugId) -> int:
    return len(history.drug_providers.get(drug, set()))


def _specialty_scores(
    history: _History,
    npi: str,
    candidates: set[DrugId],
    latest_specialties: Mapping[str, str | None],
    specialty_support: Mapping[str, Mapping[DrugId, int]],
) -> tuple[dict[DrugId, float], bool]:
    specialty = latest_specialties.get(npi)
    if specialty is None:
        return {drug: float(_global_support(history, drug)) for drug in candidates}, True
    support = specialty_support.get(specialty, {})
    return {drug: float(support.get(drug, 0)) for drug in candidates}, False


def _overlap_scores(
    history: _History, npi: str, candidates: set[DrugId]
) -> dict[DrugId, float]:
    own_drugs = history.provider_drugs.get(npi, set())
    scores = {drug: 0.0 for drug in candidates}
    peers: set[str] = set()
    for own_drug in own_drugs:
        peers.update(history.drug_providers.get(own_drug, set()))
    peers.discard(npi)
    for peer in sorted(peers):
        peer_drugs = history.provider_drugs[peer]
        intersection = len(own_drugs.intersection(peer_drugs))
        union = len(own_drugs) + len(peer_drugs) - intersection
        similarity = intersection / union if union else 0.0
        for drug in peer_drugs.intersection(candidates):
            scores[drug] += similarity
    return scores


def _positive_ranks(
    candidates: set[DrugId],
    positives: set[DrugId],
    scores: Mapping[DrugId, float],
    history: _History,
) -> dict[DrugId, int]:
    ranks: dict[DrugId, int] = {}
    for positive in positives:
        positive_score = scores[positive]
        positive_support = _global_support(history, positive)
        better = 0
        for candidate in candidates:
            candidate_score = scores[candidate]
            if candidate_score > positive_score or (
                candidate_score == positive_score
                and (
                    _global_support(history, candidate) > positive_support
                    or (
                        _global_support(history, candidate) == positive_support
                        and _drug_sort_key(candidate) < _drug_sort_key(positive)
                    )
                )
            ):
                better += 1
        ranks[positive] = better + 1
    return ranks


def _top_recommendations(
    candidates: set[DrugId],
    scores: Mapping[DrugId, float],
    history: _History,
) -> list[tuple[DrugId, float]]:
    top = heapq.nsmallest(
        TOP_KS[-1],
        candidates,
        key=lambda drug: (
            -scores[drug],
            -_global_support(history, drug),
            _drug_sort_key(drug),
        ),
    )
    return [(drug, scores[drug]) for drug in top]


@dataclass(slots=True)
class _MetricAccumulator:
    positive_count: int = 0
    contributing_provider_years: int = 0
    contributing_providers: set[str] = field(default_factory=set)
    hits: dict[int, int] = field(default_factory=lambda: {k: 0 for k in TOP_KS})
    macro_recall: dict[int, float] = field(
        default_factory=lambda: {k: 0.0 for k in TOP_KS}
    )
    reciprocal_rank_sum: float = 0.0

    def add(self, npi: str, ranks: Iterable[int]) -> None:
        values = list(ranks)
        if not values:
            return
        count = len(values)
        self.positive_count += count
        self.contributing_provider_years += 1
        self.contributing_providers.add(npi)
        for cutoff in TOP_KS:
            hits = sum(rank <= cutoff for rank in values)
            self.hits[cutoff] += hits
            self.macro_recall[cutoff] += hits / count
        self.reciprocal_rank_sum += 1.0 / min(values)

    def as_dict(self) -> dict[str, object]:
        if not self.positive_count:
            return {
                "positive_count": 0,
                "contributing_provider_count": 0,
                "contributing_provider_year_count": 0,
                "hits_at_5": 0,
                "hits_at_10": 0,
                "hits_at_20": 0,
                "micro_recall_at_5": None,
                "micro_recall_at_10": None,
                "micro_recall_at_20": None,
                "provider_macro_recall_at_5": None,
                "provider_macro_recall_at_10": None,
                "provider_macro_recall_at_20": None,
                "mrr": None,
            }
        return {
            "positive_count": self.positive_count,
            "contributing_provider_count": len(self.contributing_providers),
            "contributing_provider_year_count": self.contributing_provider_years,
            "hits_at_5": self.hits[5],
            "hits_at_10": self.hits[10],
            "hits_at_20": self.hits[20],
            "micro_recall_at_5": self.hits[5] / self.positive_count,
            "micro_recall_at_10": self.hits[10] / self.positive_count,
            "micro_recall_at_20": self.hits[20] / self.positive_count,
            "provider_macro_recall_at_5": self.macro_recall[5]
            / self.contributing_provider_years,
            "provider_macro_recall_at_10": self.macro_recall[10]
            / self.contributing_provider_years,
            "provider_macro_recall_at_20": self.macro_recall[20]
            / self.contributing_provider_years,
            "mrr": self.reciprocal_rank_sum / self.contributing_provider_years,
        }


@dataclass(slots=True)
class _EvaluationAccumulator:
    positive_metrics: _MetricAccumulator = field(default_factory=_MetricAccumulator)
    target_cohort_provider_years: int = 0
    eligible_provider_years: int = 0
    ineligible_provider_years: int = 0
    candidate_empty_provider_years: int = 0
    positive_empty_provider_years: int = 0
    recommendation_slots: dict[int, int] = field(
        default_factory=lambda: {k: 0 for k in TOP_KS}
    )
    recommendation_hits: dict[int, int] = field(
        default_factory=lambda: {k: 0 for k in TOP_KS}
    )
    zero_positive_recommended: dict[int, int] = field(
        default_factory=lambda: {k: 0 for k in TOP_KS}
    )
    zero_positive_high_confidence: dict[int, int] = field(
        default_factory=lambda: {k: 0 for k in TOP_KS}
    )

    def add(
        self,
        npi: str,
        *,
        eligible: bool,
        candidate_count: int,
        positives: set[DrugId],
        positive_ranks: Iterable[int],
        recommendations: Sequence[DrugId],
        recommendation_scores: Sequence[float],
        high_confidence_threshold: float | None,
    ) -> None:
        self.target_cohort_provider_years += 1
        if not eligible:
            self.ineligible_provider_years += 1
            return
        self.eligible_provider_years += 1
        if candidate_count == 0:
            self.candidate_empty_provider_years += 1
        if not positives:
            self.positive_empty_provider_years += 1
        else:
            self.positive_metrics.add(npi, positive_ranks)
        for cutoff in TOP_KS:
            selected = recommendations[:cutoff]
            selected_scores = recommendation_scores[:cutoff]
            self.recommendation_slots[cutoff] += len(selected)
            self.recommendation_hits[cutoff] += sum(drug in positives for drug in selected)
            if not positives and selected:
                self.zero_positive_recommended[cutoff] += 1
                if high_confidence_threshold is not None and any(
                    score >= high_confidence_threshold for score in selected_scores
                ):
                    self.zero_positive_high_confidence[cutoff] += 1

    def as_dict(self) -> dict[str, object]:
        all_provider_years: dict[str, object] = {}
        for cutoff in TOP_KS:
            slots = self.recommendation_slots[cutoff]
            all_provider_years[f"precision_at_{cutoff}"] = (
                self.recommendation_hits[cutoff] / slots if slots else None
            )
            all_provider_years[f"hits_at_{cutoff}"] = self.recommendation_hits[cutoff]
            all_provider_years[f"recommendation_slots_at_{cutoff}"] = slots
            all_provider_years[
                f"recommendation_burden_per_target_provider_year_at_{cutoff}"
            ] = (
                slots / self.target_cohort_provider_years
                if self.target_cohort_provider_years
                else None
            )
            all_provider_years[
                f"recommendation_burden_per_eligible_provider_year_at_{cutoff}"
            ] = slots / self.eligible_provider_years if self.eligible_provider_years else None
            all_provider_years[
                f"zero_positive_provider_years_recommended_at_{cutoff}"
            ] = self.zero_positive_recommended[cutoff]
            all_provider_years[
                f"fraction_zero_positive_provider_years_recommended_at_{cutoff}"
            ] = (
                self.zero_positive_recommended[cutoff] / self.positive_empty_provider_years
                if self.positive_empty_provider_years
                else None
            )
            all_provider_years[
                f"zero_positive_provider_years_high_confidence_recommended_at_{cutoff}"
            ] = self.zero_positive_high_confidence[cutoff]
            all_provider_years[
                f"fraction_zero_positive_provider_years_high_confidence_recommended_at_{cutoff}"
            ] = (
                self.zero_positive_high_confidence[cutoff]
                / self.positive_empty_provider_years
                if self.positive_empty_provider_years
                else None
            )
        all_provider_years.update(
            {
                "target_cohort_provider_year_count": self.target_cohort_provider_years,
                "eligible_provider_year_count": self.eligible_provider_years,
                "ineligible_provider_year_count": self.ineligible_provider_years,
                "candidate_empty_provider_year_count": self.candidate_empty_provider_years,
                "positive_empty_provider_year_count": self.positive_empty_provider_years,
                "positive_empty_fraction_of_eligible": (
                    self.positive_empty_provider_years / self.eligible_provider_years
                    if self.eligible_provider_years
                    else None
                ),
                "precision_denominator": "actual top-K recommendation slots, min(K, candidate_count) per eligible provider-year",
                "top_k_is_ranking_threshold_not_calibrated_confidence": True,
            }
        )
        return {
            "positive_containing_provider_years": self.positive_metrics.as_dict(),
            "all_provider_years": all_provider_years,
        }


@dataclass(slots=True)
class _PairedAccumulator:
    differences: list[float] = field(default_factory=list)

    def add(self, candidate_ranks: Sequence[int], baseline_ranks: Sequence[int]) -> None:
        if not candidate_ranks:
            return
        candidate_recall = sum(rank <= 10 for rank in candidate_ranks) / len(candidate_ranks)
        baseline_recall = sum(rank <= 10 for rank in baseline_ranks) / len(baseline_ranks)
        self.differences.append(candidate_recall - baseline_recall)

    def as_dict(self) -> dict[str, object]:
        return {
            "mean_provider_year_recall_at_10_difference": (
                sum(self.differences) / len(self.differences) if self.differences else None
            ),
            "provider_year_count": len(self.differences),
        }


def _score_target(
    *,
    year: int,
    cohort: set[str],
    prior_years: Sequence[int],
    rows_by_year: Mapping[int, Sequence[_ProjectedRow]],
) -> tuple[
    dict[str, _EvaluationAccumulator],
    dict[str, _PairedAccumulator],
    list[dict[str, object]],
    dict[str, object],
]:
    history = _build_history(rows_by_year, prior_years, cohort)
    context = _feature_context(history, year)
    tabular = _fit_logistic(context)
    graph = _fit_graph_bpr(history, year)
    threshold_values: dict[str, list[float]] = {
        method: [] for method in METHOD_NAMES
    }
    for train_npi in sorted(history.provider_drugs):
        train_candidates = _candidate_drugs(history, train_npi)
        train_specialty_scores, _ = _specialty_scores(
            history,
            train_npi,
            train_candidates,
            context.latest_specialties,
            context.specialty_support,
        )
        train_overlap_scores = _overlap_scores(history, train_npi, train_candidates)
        train_specialty = context.latest_specialties.get(train_npi)
        train_score_maps: dict[str, dict[DrugId, float]] = {
            "specialty_popularity": train_specialty_scores,
            "history_overlap": train_overlap_scores,
            "tabular_logistic": {
                drug: tabular.score(context.features(train_npi, drug))
                for drug in train_candidates
            },
            "graph_bpr": {
                drug: graph.score(train_npi, drug, train_specialty)
                for drug in train_candidates
            },
        }
        for method in METHOD_NAMES:
            threshold_values[method].extend(train_score_maps[method].values())
    high_confidence_thresholds: dict[str, float | None] = {}
    for method, values in threshold_values.items():
        if not values:
            high_confidence_thresholds[method] = None
        else:
            values.sort()
            index = min(
                len(values) - 1,
                math.ceil(HIGH_SCORE_QUANTILE * (len(values) - 1)),
            )
            high_confidence_thresholds[method] = values[index]
    global_drugs = set(history.drug_providers)
    metrics = {method: _EvaluationAccumulator() for method in METHOD_NAMES}
    paired = {
        f"{method}_vs_{baseline}": _PairedAccumulator()
        for method in ("tabular_logistic", "graph_bpr")
        for baseline in ("specialty_popularity", "history_overlap")
    }
    current_by_provider: dict[str, set[DrugId]] = defaultdict(set)
    for row in rows_by_year[year]:
        if row.npi in cohort:
            current_by_provider[row.npi].add(row.drug)
    latest_specialties = context.latest_specialties
    rankings: list[dict[str, object]] = []
    fallback_provider_years = 0
    positive_edges = 0
    for npi in sorted(cohort):
        own_drugs = history.provider_drugs.get(npi, set())
        eligible = bool(own_drugs)
        candidates = global_drugs.difference(own_drugs) if eligible else set()
        current = current_by_provider.get(npi, set())
        positives = {
            drug for drug in current if drug not in own_drugs and drug in global_drugs
        }
        positive_edges += len(positives)
        specialty_scores, specialty_fallback = _specialty_scores(
            history,
            npi,
            candidates,
            latest_specialties,
            context.specialty_support,
        )
        if eligible and specialty_fallback:
            fallback_provider_years += 1
        overlap_scores = _overlap_scores(history, npi, candidates)
        target_specialty = latest_specialties.get(npi)
        score_maps: dict[str, dict[DrugId, float]] = {
            "specialty_popularity": specialty_scores,
            "history_overlap": overlap_scores,
            "tabular_logistic": {
                drug: tabular.score(context.features(npi, drug)) for drug in candidates
            },
            "graph_bpr": {
                drug: graph.score(npi, drug, target_specialty) for drug in candidates
            },
        }
        ranks_by_method: dict[str, dict[DrugId, int]] = {}
        recommendations_by_method: dict[str, list[tuple[DrugId, float]]] = {}
        for method in METHOD_NAMES:
            ranks = _positive_ranks(candidates, positives, score_maps[method], history)
            ranks_by_method[method] = ranks
            recommendations_by_method[method] = _top_recommendations(
                candidates, score_maps[method], history
            )
            positive_ranks = [ranks[drug] for drug in sorted(positives, key=_drug_sort_key)]
            recommendation_ids = [drug for drug, _ in recommendations_by_method[method]]
            metrics[method].add(
                npi,
                eligible=eligible,
                candidate_count=len(candidates),
                positives=positives,
                positive_ranks=positive_ranks,
                recommendations=recommendation_ids,
                recommendation_scores=[
                    score for _, score in recommendations_by_method[method]
                ],
                high_confidence_threshold=high_confidence_thresholds[method],
            )
        for method in ("tabular_logistic", "graph_bpr"):
            model_ranks = [
                ranks_by_method[method][drug] for drug in sorted(positives, key=_drug_sort_key)
            ]
            for baseline in ("specialty_popularity", "history_overlap"):
                baseline_ranks = [
                    ranks_by_method[baseline][drug]
                    for drug in sorted(positives, key=_drug_sort_key)
                ]
                paired[f"{method}_vs_{baseline}"].add(model_ranks, baseline_ranks)
        rankings.append(
            {
                "representation": None,
                "year": year,
                "npi": npi,
                "eligible": eligible,
                "candidate_count": len(candidates),
                "positive_count": len(positives),
                "positives": [
                    {
                        "drug": _drug_payload(drug),
                        "ranks": {
                            method: ranks_by_method[method][drug] for method in METHOD_NAMES
                        },
                    }
                    for drug in sorted(positives, key=_drug_sort_key)
                ],
                "recommendations": {
                    method: [
                        {
                            "drug": _drug_payload(drug),
                            "rank": rank,
                            "score": score,
                        }
                        for rank, (drug, score) in enumerate(
                            recommendations_by_method[method], start=1
                        )
                    ]
                    for method in METHOD_NAMES
                },
            }
        )
    training_summary = {
        "history_years": list(prior_years),
        "target_cohort_provider_count": len(cohort),
        "history_provider_count": len(history.provider_drugs),
        "history_drug_count": len(history.drug_providers),
        "history_provider_drug_edge_count": sum(
            len(drugs) for drugs in history.provider_drugs.values()
        ),
        "positive_edges_in_target": positive_edges,
        "specialty_fallback_provider_years": fallback_provider_years,
        "high_score_threshold_quantile": HIGH_SCORE_QUANTILE,
        "high_score_thresholds": high_confidence_thresholds,
        "tabular_logistic": tabular.summary,
        "graph_bpr": graph.summary,
    }
    return metrics, paired, rankings, training_summary


def _metric_report(
    accumulators: Mapping[str, _EvaluationAccumulator],
    paired: Mapping[str, _PairedAccumulator],
) -> dict[str, object]:
    return {
        "by_method": {
            method: accumulators[method].as_dict() for method in METHOD_NAMES
        },
        "paired_recall_at_10": {
            name: accumulator.as_dict() for name, accumulator in sorted(paired.items())
        },
    }


def _identity_sensitivity(
    metrics_by_representation: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    generic = metrics_by_representation["generic"]
    variant = metrics_by_representation["variant"]
    differences: dict[str, object] = {}
    for scope in ("by_year", "pooled_provider_year"):
        if scope == "by_year":
            scope_values = {}
            for year in ("2023", "2024"):
                scope_values[year] = {}
                generic_year = generic[scope][year]["by_method"]
                variant_year = variant[scope][year]["by_method"]
                for method in METHOD_NAMES:
                    scope_values[year][method] = _metric_difference(
                        generic_year[method], variant_year[method]
                    )
            differences[scope] = scope_values
        else:
            generic_values = generic[scope]["by_method"]
            variant_values = variant[scope]["by_method"]
            differences[scope] = {
                method: _metric_difference(generic_values[method], variant_values[method])
                for method in METHOD_NAMES
            }
    return {
        "comparison": "variant_minus_generic",
        "differences": differences,
        "interpretation": (
            "Generic is the primary node representation. Variant retains exact source-native "
            "brand+generic keys. Differences are identity-sensitivity diagnostics, not clinical "
            "equivalence evidence or a post-hoc model-selection rule."
        ),
    }


def _metric_difference(generic: Mapping[str, object], variant: Mapping[str, object]) -> dict[str, object]:
    generic_positive = generic["positive_containing_provider_years"]
    variant_positive = variant["positive_containing_provider_years"]
    generic_all = generic["all_provider_years"]
    variant_all = variant["all_provider_years"]
    result: dict[str, object] = {}
    for key in (
        "micro_recall_at_5",
        "micro_recall_at_10",
        "micro_recall_at_20",
        "mrr",
    ):
        left = generic_positive[key]
        right = variant_positive[key]
        result[f"positive_{key}_variant_minus_generic"] = (
            right - left if left is not None and right is not None else None
        )
    for key in ("precision_at_5", "precision_at_10", "precision_at_20"):
        left = generic_all[key]
        right = variant_all[key]
        result[f"all_provider_{key}_variant_minus_generic"] = (
            right - left if left is not None and right is not None else None
        )
    return result


def _source_provenance(repo_root: Path) -> dict[str, object]:
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return {
            "commit": None,
            "dirty": None,
            "status_porcelain": None,
            "reason": f"Git metadata unavailable: {exc}",
        }
    status = status_result.stdout
    return {
        "commit": commit_result.stdout.strip() or None,
        "dirty": bool(status),
        "status_porcelain": status,
        "reason": None,
    }


def run_model_gate(
    feasibility_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    """Run the frozen 2023-validation/2024-test Part D model gate."""
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing model-gate output: {output_dir}")
    if not isinstance(feasibility_dir, Path):
        feasibility_dir = Path(feasibility_dir)
    if not isinstance(output_dir, Path):
        output_dir = Path(output_dir)
    feasibility_report, input_rows, cohorts, input_provenance = _load_input(feasibility_dir)
    years = [2019, 2020, 2021, 2022, 2023, 2024]
    prior_years_by_target = {2023: [2019, 2020, 2021, 2022], 2024: [2019, 2020, 2021, 2022, 2023]}
    projections: dict[str, dict[int, list[_ProjectedRow]]] = {}
    projection_summaries: dict[str, dict[str, object]] = {}
    all_rankings: list[dict[str, object]] = []
    metrics_by_representation: dict[str, dict[str, object]] = {}
    training_by_representation: dict[str, dict[str, object]] = {}
    target_audits: dict[str, dict[str, object]] = {}
    for representation in REPRESENTATIONS:
        projected, projection_summary = _project_rows(input_rows, representation)
        projections[representation] = projected
        projection_summaries[representation] = projection_summary
        yearly_accumulators: dict[str, dict[str, _EvaluationAccumulator]] = {}
        yearly_paired: dict[str, dict[str, _PairedAccumulator]] = {}
        pooled_accumulators = {
            method: _EvaluationAccumulator() for method in METHOD_NAMES
        }
        pooled_paired = {
            f"{method}_vs_{baseline}": _PairedAccumulator()
            for method in ("tabular_logistic", "graph_bpr")
            for baseline in ("specialty_popularity", "history_overlap")
        }
        training_by_representation[representation] = {}
        target_audits[representation] = {}
        for year in (2023, 2024):
            metrics, paired, rankings, training_summary = _score_target(
                year=year,
                cohort=cohorts[year],
                prior_years=prior_years_by_target[year],
                rows_by_year=projected,
            )
            for row in rankings:
                row["representation"] = representation
            all_rankings.extend(rankings)
            yearly_accumulators[str(year)] = metrics
            yearly_paired[str(year)] = paired
            training_by_representation[representation][str(year)] = training_summary
            for method in METHOD_NAMES:
                source = metrics[method]
                target = pooled_accumulators[method]
                target.target_cohort_provider_years += source.target_cohort_provider_years
                target.eligible_provider_years += source.eligible_provider_years
                target.ineligible_provider_years += source.ineligible_provider_years
                target.candidate_empty_provider_years += source.candidate_empty_provider_years
                target.positive_empty_provider_years += source.positive_empty_provider_years
                target.positive_metrics.positive_count += source.positive_metrics.positive_count
                target.positive_metrics.contributing_provider_years += source.positive_metrics.contributing_provider_years
                target.positive_metrics.contributing_providers.update(source.positive_metrics.contributing_providers)
                for cutoff in TOP_KS:
                    target.positive_metrics.hits[cutoff] += source.positive_metrics.hits[cutoff]
                    target.positive_metrics.macro_recall[cutoff] += source.positive_metrics.macro_recall[cutoff]
                    target.recommendation_slots[cutoff] += source.recommendation_slots[cutoff]
                    target.recommendation_hits[cutoff] += source.recommendation_hits[cutoff]
                    target.zero_positive_recommended[cutoff] += source.zero_positive_recommended[cutoff]
                    target.zero_positive_high_confidence[cutoff] += source.zero_positive_high_confidence[cutoff]
                target.positive_metrics.reciprocal_rank_sum += source.positive_metrics.reciprocal_rank_sum
            for name, source in paired.items():
                pooled_paired[name].differences.extend(source.differences)
            target_audits[representation][str(year)] = {
                "target_cohort_provider_years": len(cohorts[year]),
                "projected_rows_excluded_blank_generic": projection_summary[
                    "rows_excluded_blank_generic"
                ],
                "positive_edges": training_summary["positive_edges_in_target"],
                "history_years": list(prior_years_by_target[year]),
                "history_provider_count": training_summary["history_provider_count"],
                "history_drug_count": training_summary["history_drug_count"],
                "history_provider_drug_edge_count": training_summary[
                    "history_provider_drug_edge_count"
                ],
                "specialty_fallback_provider_years": training_summary[
                    "specialty_fallback_provider_years"
                ],
            }
        metrics_by_representation[representation] = {
            "by_year": {
                year: _metric_report(yearly_accumulators[year], yearly_paired[year])
                for year in ("2023", "2024")
            },
            "pooled_provider_year": _metric_report(pooled_accumulators, pooled_paired),
        }
    all_positive = all(
        int(target_audits[representation][str(year)]["positive_edges"]) > 0
        for representation in REPRESENTATIONS
        for year in (2023, 2024)
    )
    configuration: dict[str, object] = {
        "analysis_version": MODEL_GATE_VERSION,
        "input_record_kind": "partd_feasibility",
        "years": years,
        "training_history": {
            "validation": "2019-2022 history; score 2023 first-observed published relationships",
            "test": "2019-2023 history; score 2024 first-observed published relationships",
            "refit_before_each_target": True,
            "target_rows_never_used_before_scoring": True,
        },
        "evaluation_roles": {
            "2022": "train_target",
            "2023": "validation",
            "2024": "held_out_test",
        },
        "primary_representation": "generic",
        "representations": {
            "generic": {
                "drug_node": "generic_name",
                "identity": "exact trimmed source generic_name",
                "blank_generic_policy": "exclude",
            },
            "variant": {
                "drug_node": "(brand_name, generic_name)",
                "identity": "exact trimmed source brand_name plus generic_name",
                "blank_generic_policy": "retain when brand_name is nonblank",
            },
        },
        "candidate_rule": (
            "all drugs observed globally in the target cohort's strictly prior history "
            "minus the target provider's entire strictly prior history; evaluate every candidate"
        ),
        "methods": list(METHOD_NAMES),
        "tabular_features": list(FEATURE_NAMES),
        "model_hyperparameters": {
            "tabular_logistic": {
                "negative_sampling_ratio": TABULAR_NEGATIVE_RATIO,
                "epochs": TABULAR_EPOCHS,
                "learning_rate": TABULAR_LEARNING_RATE,
                "l2": TABULAR_L2,
                "negative_sampling_role": "training only; evaluation ranks all candidates",
            },
            "graph_bpr": {
                "graph": "provider-PRESCRIBED-drug plus provider-HAS_SPECIALTY-specialty",
                "dimension": GRAPH_DIMENSION,
                "epochs": GRAPH_BPR_EPOCHS,
                "negative_samples_per_positive": GRAPH_BPR_NEGATIVE_SAMPLES,
                "learning_rate": GRAPH_BPR_LEARNING_RATE,
                "regularization": GRAPH_BPR_REGULARIZATION,
                "specialty_weight": GRAPH_SPECIALTY_WEIGHT,
                "message_passing": False,
            },
        },
        "metric_cutoffs": list(TOP_KS),
        "high_score_threshold_quantile": HIGH_SCORE_QUANTILE,
        "all_provider_year_metric_rule": (
            "precision uses actual top-K recommendation slots, min(K, candidate_count) per "
            "eligible provider-year; zero-positive provider-years remain in burden denominators"
        ),
        "tie_rule": "descending score, descending prior global provider support, ascending source-native drug key",
    }
    configuration_sha256 = hashlib.sha256(_canonical_json(configuration).encode("utf-8")).hexdigest()
    repo_root = Path(__file__).resolve().parents[2]
    registry_path = repo_root / "configs" / "task_candidates_v0_2_model_gate.json"
    registry_sha256 = sha256_file(registry_path) if registry_path.is_file() else None
    source_provenance = _source_provenance(repo_root)
    rankings_path = output_dir / "rankings.jsonl"
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()
    all_rankings.sort(key=lambda row: (str(row["representation"]), int(row["year"]), str(row["npi"])))
    with rankings_path.open("w", encoding="utf-8", newline="") as handle:
        for row in all_rankings:
            handle.write(_canonical_json(row) + "\n")
    report: dict[str, object] = {
        "record_kind": MODEL_GATE_RECORD_KIND,
        "status": "exploratory",
        "decision": "MODEL_GATE_REVIEW_REQUIRED" if all_positive else "INSUFFICIENT_OBSERVED_SUPPORT",
        "decision_basis": (
            "MODEL_GATE_REVIEW_REQUIRED requires at least one projected positive in both "
            "2023 validation and 2024 held-out test for both identity representations; no "
            "automatic superiority or admission threshold is applied."
        ),
        "admission_status": "model_gate_pending",
        "temporal_mode": "retrospective_service_year",
        "historical_availability_verified": False,
        "executed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_commit": source_provenance["commit"],
        "dirty_state": source_provenance,
        "configuration": configuration,
        "configuration_sha256": configuration_sha256,
        "configuration_source": {
            "path": str(registry_path),
            "sha256": registry_sha256,
            "reason": None if registry_sha256 is not None else f"candidate registry unavailable: {registry_path}",
        },
        "input": input_provenance,
        "feasibility_decision": feasibility_report.get("decision"),
        "projections": projection_summaries,
        "evaluation": target_audits,
        "training": training_by_representation,
        "metrics": {
            "primary_representation": "generic",
            "methods": list(METHOD_NAMES),
            "representations": metrics_by_representation,
            "identity_sensitivity": _identity_sensitivity(metrics_by_representation),
        },
        "interpretation_limits": [
            "The target remains a first observed published provider-drug relationship, not a first prescription or prescribing start.",
            "CMS suppresses provider-drug combinations with 10 or fewer Part D claims; absence is non-observation subject to suppression and left censoring.",
            "Generic-only is the primary source-text representation; exact brand+generic is a sensitivity representation, not a verified molecule identity.",
            "No RxNorm, molecule-level, or clinical-equivalence mapping is asserted.",
            "All-provider-year precision and burden include zero-positive provider-years; top-K is a ranking threshold, and the fixed 95th-percentile high-score flag is not calibrated confidence.",
            "Training negative sampling is used only to fit the tabular and BPR models; evaluation ranks every eligible candidate.",
            "Provider cohorts remain bounded and target-specific; full national scalability is not established.",
            "Historical publication-time availability is not verified, so this is not deployment-valid next-calendar-year forecasting.",
            "Part D remains exploratory and is not admitted to the frozen benchmark by this model gate.",
        ],
        "leakage_controls": [
            "2023 models use only target-cohort observations through 2022; 2024 models use only target-cohort observations through 2023.",
            "Each target cohort is inherited from providers first observed strictly before that target year.",
            "Current target rows are used only to form positives after model fitting and ranking inputs are frozen.",
            "Tabular normalization statistics and fitted parameters use only the corresponding strictly prior history.",
            "Graph BPR embeddings are fit independently at each target cutoff with deterministic negative samples.",
            "Evaluation uses all candidates under the temporal rule; no sampled evaluation negatives are used.",
        ],
        "artifact_hashes": {
            "rankings.jsonl": sha256_file(rankings_path),
            "feasibility_edges.csv": input_provenance["feasibility_edges_sha256"],
            "feasibility_report.json": input_provenance["feasibility_report_sha256"],
        },
    }
    report_path = output_dir / "report.json"
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return report
