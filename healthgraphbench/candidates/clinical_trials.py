"""Historical AACT feasibility gate for timely ClinicalTrials.gov results posting."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import subprocess
import zipfile
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterator, Mapping

from healthgraphbench.data import sha256_file, verify_files


ANALYSIS_VERSION = "clinical_trials_feasibility_v1"
MANIFEST_VERSION = "0.2-candidate-clinical-trials"
HORIZON_DAYS = 365
MAX_COMPLETION_LAG_DAYS = 90
COHORT_SIZE = 2000
LEARNING_RATE = 0.08
EPOCHS = 24
L2 = 0.01
TOP_DECILE = 0.10

SNAPSHOT_DATES: tuple[str, ...] = (
    "2019-01-01",
    "2020-01-01",
    "2021-01-01",
    "2022-02-01",
    "2023-02-01",
    "2024-02-01",
    "2025-02-01",
)
SNAPSHOT_ROLES: dict[str, str] = {
    "2019-01-01": "train_origin",
    "2020-01-01": "train_origin",
    "2021-01-01": "train_origin",
    "2022-02-01": "train_origin",
    "2023-02-01": "validation_origin",
    "2024-02-01": "held_out_test_origin",
    "2025-02-01": "future_observation_only",
}
TRAIN_ORIGINS = frozenset(date.fromisoformat(value) for value, role in SNAPSHOT_ROLES.items() if role == "train_origin")
VALIDATION_ORIGIN = date.fromisoformat("2023-02-01")
TEST_ORIGIN = date.fromisoformat("2024-02-01")

REQUIRED_TABLES: tuple[str, ...] = (
    "studies.txt",
    "conditions.txt",
    "interventions.txt",
    "sponsors.txt",
    "facilities.txt",
    "designs.txt",
)
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "studies.txt": (
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
    ),
    "conditions.txt": ("nct_id", "name"),
    "interventions.txt": ("nct_id", "name"),
    "sponsors.txt": ("nct_id", "lead_or_collaborator", "name"),
    "facilities.txt": ("nct_id", "name"),
    "designs.txt": (
        "nct_id",
        "allocation",
        "intervention_model",
        "primary_purpose",
        "time_perspective",
        "masking",
    ),
}

ENTITY_TYPES: tuple[str, ...] = (
    "sponsor",
    "condition",
    "intervention",
    "facility",
    "collaborator",
)
RELATION_TABLES: dict[str, str] = {
    "conditions.txt": "condition",
    "interventions.txt": "intervention",
    "facilities.txt": "facility",
}
LOCAL_CATEGORICAL: tuple[str, ...] = (
    "phase",
    "allocation",
    "intervention_model",
    "masking",
    "primary_purpose",
    "time_perspective",
)
LOCAL_NUMERIC: tuple[str, ...] = (
    "enrollment",
    "number_of_arms",
    "number_of_groups",
    "start_to_completion_days",
    "completion_lag_days",
    "is_fda_regulated_drug",
    "is_fda_regulated_device",
)
SPONSOR_NUMERIC: tuple[str, ...] = (
    "prior_trial_count",
    "timely_fraction",
    "median_delay_days",
    "entity_count",
    "history_entity_count",
)
CONTEXT_NUMERIC: tuple[str, ...] = (
    "prior_trial_count",
    "timely_fraction",
    "median_delay_days",
    "entity_count",
    "history_entity_count",
)
STABILITY_ENTITY_GROUPS: dict[str, tuple[str, ...]] = {
    "local_plus_sponsor_logistic": ("sponsor",),
    "local_plus_sponsor_condition_logistic": ("sponsor", "condition"),
    "local_plus_sponsor_facility_logistic": ("sponsor", "facility"),
    "local_plus_sponsor_intervention_logistic": ("sponsor", "intervention"),
    "local_plus_sponsor_collaborator_logistic": ("sponsor", "collaborator"),
    "heterogeneous_context_by_entity_logistic": (
        "sponsor",
        "condition",
        "facility",
        "intervention",
        "collaborator",
    ),
}

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_NCT_RE = re.compile(r"^NCT[0-9]{8}$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _Study:
    nct_id: str
    phase: str | None
    enrollment: float | None
    number_of_arms: float | None
    number_of_groups: float | None
    start_date: date | None
    completion_date: date
    results_date: date | None
    fda_drug: float | None
    fda_device: float | None
    study_type: str
    completion_lag_days: int


@dataclass(frozen=True, slots=True)
class _KnownOutcome:
    timely: bool
    results_date: date | None
    delay_days: int | None


@dataclass(slots=True)
class _HistoryStats:
    trial_count: int = 0
    timely_count: int = 0
    posting_delays: list[int] = field(default_factory=list)


@dataclass(slots=True)
class _Example:
    nct_id: str
    origin_date: date
    role: str
    study: _Study
    local: dict[str, str | float | None]
    sponsor: dict[str, float | None]
    context: dict[str, float | None]
    relation_counts: dict[str, int]
    history_relation_counts: dict[str, int]
    context_by_type: dict[str, dict[str, float | None]] = field(default_factory=dict)
    label: int | None = None
    result_date: date | None = None


@dataclass(slots=True)
class _OriginResult:
    examples: list[_Example]
    audit: dict[str, Any]
    coverage: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _FeatureEncoder:
    group: str
    categorical_maps: dict[str, dict[str, int]]
    numeric_stats: dict[str, tuple[float, float]]
    feature_names: tuple[str, ...]

    @classmethod
    def build(cls, group: str, examples: list[_Example]) -> "_FeatureEncoder":
        categorical = list(LOCAL_CATEGORICAL)
        numeric = list(LOCAL_NUMERIC)
        stability_entities = STABILITY_ENTITY_GROUPS.get(group)
        if stability_entities is not None:
            if "sponsor" in stability_entities:
                numeric.extend(f"sponsor_{name}" for name in SPONSOR_NUMERIC)
            for entity_type in stability_entities:
                if entity_type != "sponsor":
                    numeric.extend(f"context_entity_{entity_type}_{name}" for name in CONTEXT_NUMERIC)
        elif group in {"sponsor_history_logistic", "heterogeneous_context_logistic"}:
            numeric.extend(f"sponsor_{name}" for name in SPONSOR_NUMERIC)
            if group == "heterogeneous_context_logistic":
                numeric.extend(f"context_{name}" for name in CONTEXT_NUMERIC)
        categorical_maps: dict[str, dict[str, int]] = {}
        feature_names: list[str] = []
        for name in categorical:
            values = {
                _category_value(example.local.get(name))
                for example in examples
            }
            values.add("__UNK__")
            ordered = sorted(values)
            mapping = {value: index for index, value in enumerate(ordered)}
            categorical_maps[name] = mapping
            feature_names.extend(f"{name}={value}" for value in ordered)
        numeric_stats: dict[str, tuple[float, float]] = {}
        for name in numeric:
            values = [value for value in _numeric_fields(examples, name) if value is not None]
            mean = sum(values) / len(values) if values else 0.0
            variance = sum((value - mean) ** 2 for value in values) / len(values) if values else 0.0
            std = math.sqrt(variance)
            if not math.isfinite(std) or std < 1e-12:
                std = 1.0
            numeric_stats[name] = (mean, std)
            feature_names.append(name)
            feature_names.append(f"{name}__missing")
        return cls(group, categorical_maps, numeric_stats, tuple(feature_names))

    def encode(self, example: _Example) -> list[float]:
        values: list[float] = []
        for name, mapping in self.categorical_maps.items():
            selected = mapping.get(_category_value(example.local.get(name)), mapping["__UNK__"])
            values.extend(1.0 if index == selected else 0.0 for index in range(len(mapping)))
        for name, (mean, std) in self.numeric_stats.items():
            raw = _numeric_field(example, name)
            values.append(0.0 if raw is None else (raw - mean) / std)
            values.append(1.0 if raw is None else 0.0)
        return values


def _table_rows(
    archive: zipfile.ZipFile, name: str, expected_header: list[str]
) -> Iterator[dict[str, str]]:
    try:
        raw = archive.open(name)
    except KeyError as exc:
        raise ValueError(f"AACT archive is missing required table {name}") from exc
    with raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
        reader = csv.DictReader(text, delimiter="|")
        if reader.fieldnames != expected_header:
            raise ValueError(
                f"AACT table header drift in {name}: got {reader.fieldnames!r}, expected {expected_header!r}"
            )
        yield from reader


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_source_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"manifest path must be a non-empty string: {relative!r}")
    root_resolved = root.resolve()
    path = (root / relative).resolve()
    if path != root_resolved and root_resolved not in path.parents:
        raise ValueError(f"manifest path escapes source root: {relative!r}")
    return path


def _archive_url(snapshot_date: str) -> str:
    return (
        "https://aact.ctti-clinicaltrials.org/static/exported_files/pipe_files/"
        f"{snapshot_date.replace('-', '')}_export_ctgov.zip"
    )


def _validate_manifest(manifest_path: Path, source_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load AACT manifest {manifest_path}: {exc}") from exc
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError(f"unsupported AACT manifest version: {manifest.get('version')!r}")
    if manifest.get("dataset") != "clinical_trials_reporting":
        raise ValueError(f"unexpected AACT dataset: {manifest.get('dataset')!r}")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != len(SNAPSHOT_DATES):
        raise ValueError("AACT manifest must contain exactly seven frozen snapshots")
    by_date: dict[str, dict[str, Any]] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("AACT manifest entries must be objects")
        snapshot_date = entry.get("snapshot_date")
        if snapshot_date not in SNAPSHOT_DATES or snapshot_date in by_date:
            raise ValueError(f"invalid or duplicate AACT snapshot date: {snapshot_date!r}")
        expected_path = f"aact_{snapshot_date}_export_ctgov.zip"
        if entry.get("path") != expected_path or entry.get("url") != _archive_url(snapshot_date):
            raise ValueError(f"AACT manifest URL/path drift for {snapshot_date}")
        if not isinstance(entry.get("bytes"), int) or entry["bytes"] <= 0:
            raise ValueError(f"invalid AACT byte count for {snapshot_date}")
        if not isinstance(entry.get("sha256"), str) or not _SHA256_RE.fullmatch(entry["sha256"]):
            raise ValueError(f"invalid AACT SHA-256 for {snapshot_date}")
        headers = entry.get("headers")
        if not isinstance(headers, dict) or any(name not in headers for name in REQUIRED_TABLES):
            raise ValueError(f"incomplete AACT table headers for {snapshot_date}")
        for name in REQUIRED_TABLES:
            header = headers[name]
            if not isinstance(header, list) or not all(isinstance(field, str) for field in header):
                raise ValueError(f"invalid AACT header for {snapshot_date}!{name}")
            missing = [field for field in REQUIRED_FIELDS[name] if field not in header]
            if missing:
                raise ValueError(f"AACT header missing {missing} for {snapshot_date}!{name}")
        _safe_source_path(source_root, entry["path"])
        by_date[snapshot_date] = entry
    if set(by_date) != set(SNAPSHOT_DATES):
        raise ValueError("AACT manifest snapshot dates are incomplete")
    ordered = [by_date[snapshot_date] for snapshot_date in SNAPSHOT_DATES]
    verify_files(source_root, ordered)
    return manifest, ordered


def _category_value(value: object) -> str:
    if value is None:
        return "__MISSING__"
    text = str(value).strip()
    return text if text else "__MISSING__"


def _normalize_entity(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _parse_date(value: object, *, field: str, nct_id: str, snapshot_date: date) -> date | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        parsed = date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"invalid {field} {text!r} for {nct_id} in snapshot {snapshot_date}") from exc
    return parsed


def _parse_number(value: object, *, field: str, nct_id: str, snapshot_date: date) -> float | None:
    text = "" if value is None else str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError as exc:
        raise ValueError(f"invalid {field} {text!r} for {nct_id} in snapshot {snapshot_date}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite {field} for {nct_id} in snapshot {snapshot_date}")
    return parsed


def _parse_bool(value: object, *, field: str, nct_id: str, snapshot_date: date) -> float | None:
    text = "" if value is None else str(value).strip().casefold()
    if not text:
        return None
    if text in {"t", "true", "yes", "y", "1"}:
        return 1.0
    if text in {"f", "false", "no", "n", "0"}:
        return 0.0
    raise ValueError(f"invalid {field} {text!r} for {nct_id} in snapshot {snapshot_date}")


def _parse_study(row: Mapping[str, str], snapshot_date: date) -> _Study | None:
    nct_id = str(row.get("nct_id", "")).strip()
    if not nct_id:
        raise ValueError(f"blank nct_id in studies.txt at snapshot {snapshot_date}")
    if not _NCT_RE.fullmatch(nct_id):
        raise ValueError(f"invalid nct_id {nct_id!r} in snapshot {snapshot_date}")
    study_type = str(row.get("study_type", "")).strip()
    if study_type.casefold() != "interventional":
        return None
    if str(row.get("primary_completion_date_type", "")).strip().casefold() != "actual":
        return None
    completion = _parse_date(
        row.get("primary_completion_date"),
        field="primary_completion_date",
        nct_id=nct_id,
        snapshot_date=snapshot_date,
    )
    if completion is None:
        raise ValueError(f"actual primary completion has no date for {nct_id} in snapshot {snapshot_date}")
    if completion > snapshot_date:
        return None
    results_date = _parse_date(
        row.get("results_first_posted_date"),
        field="results_first_posted_date",
        nct_id=nct_id,
        snapshot_date=snapshot_date,
    )
    start_date = _parse_date(row.get("start_date"), field="start_date", nct_id=nct_id, snapshot_date=snapshot_date)
    return _Study(
        nct_id=nct_id,
        phase=_category_value(row.get("phase")) if str(row.get("phase", "")).strip() else None,
        enrollment=_parse_number(row.get("enrollment"), field="enrollment", nct_id=nct_id, snapshot_date=snapshot_date),
        number_of_arms=_parse_number(
            row.get("number_of_arms"), field="number_of_arms", nct_id=nct_id, snapshot_date=snapshot_date
        ),
        number_of_groups=_parse_number(
            row.get("number_of_groups"), field="number_of_groups", nct_id=nct_id, snapshot_date=snapshot_date
        ),
        start_date=start_date,
        completion_date=completion,
        results_date=results_date,
        fda_drug=_parse_bool(
            row.get("is_fda_regulated_drug"), field="is_fda_regulated_drug", nct_id=nct_id, snapshot_date=snapshot_date
        ),
        fda_device=_parse_bool(
            row.get("is_fda_regulated_device"),
            field="is_fda_regulated_device",
            nct_id=nct_id,
            snapshot_date=snapshot_date,
        ),
        study_type=study_type,
        completion_lag_days=(snapshot_date - completion).days,
    )


def _history_outcome(study: _Study, origin: date) -> _KnownOutcome:
    horizon_end = study.completion_date + timedelta(days=HORIZON_DAYS)
    timely = study.results_date is not None and study.results_date <= horizon_end
    delay = None if study.results_date is None else (study.results_date - study.completion_date).days
    return _KnownOutcome(timely=timely, results_date=study.results_date, delay_days=delay)


def _add_relation(
    relations: dict[str, dict[str, set[str]]], entity_type: str, nct_id: str, name: object
) -> None:
    normalized = _normalize_entity(name)
    if normalized:
        relations[entity_type].setdefault(nct_id, set()).add(normalized)


def _aggregate_history(
    names: set[str], history: dict[str, _HistoryStats]
) -> tuple[dict[str, float | None], int]:
    selected = [history[name] for name in names if name in history]
    prior_count = sum(item.trial_count for item in selected)
    timely_count = sum(item.timely_count for item in selected)
    delays = [delay for item in selected for delay in item.posting_delays]
    values: dict[str, float | None] = {
        "prior_trial_count": float(prior_count),
        "timely_fraction": (timely_count / prior_count) if prior_count else None,
        "median_delay_days": float(median(delays)) if delays else None,
        "entity_count": float(len(names)),
        "history_entity_count": float(len(selected)),
    }
    return values, len(selected)


def _local_features(study: _Study, designs: dict[str, dict[str, str]], origin: date) -> dict[str, str | float | None]:
    design = designs.get(study.nct_id, {})
    start_to_completion = None
    if study.start_date is not None:
        start_to_completion = float((study.completion_date - study.start_date).days)
    return {
        "phase": study.phase,
        "allocation": design.get("allocation"),
        "intervention_model": design.get("intervention_model"),
        "masking": design.get("masking"),
        "primary_purpose": design.get("primary_purpose"),
        "time_perspective": design.get("time_perspective"),
        "enrollment": study.enrollment,
        "number_of_arms": study.number_of_arms,
        "number_of_groups": study.number_of_groups,
        "start_to_completion_days": start_to_completion,
        "completion_lag_days": float((origin - study.completion_date).days),
        "is_fda_regulated_drug": study.fda_drug,
        "is_fda_regulated_device": study.fda_device,
    }


def _parse_origin_snapshot(path: Path, manifest_entry: dict[str, Any], cohort_size: int) -> _OriginResult:
    snapshot_date = date.fromisoformat(str(manifest_entry["snapshot_date"]))
    headers = manifest_entry["headers"]
    role = SNAPSHOT_ROLES[snapshot_date.isoformat()]
    study_rows = 0
    interventional_rows = 0
    known: dict[str, tuple[_Study, _KnownOutcome]] = {}
    eligible: dict[str, _Study] = {}
    seen_studies: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        for row in _table_rows(archive, "studies.txt", headers["studies.txt"]):
            study_rows += 1
            nct_id = str(row.get("nct_id", "")).strip()
            if nct_id in seen_studies:
                raise ValueError(f"duplicate studies.txt nct_id {nct_id} in snapshot {snapshot_date}")
            seen_studies.add(nct_id)
            study = _parse_study(row, snapshot_date)
            if study is None:
                continue
            interventional_rows += 1
            age = (snapshot_date - study.completion_date).days
            if age >= HORIZON_DAYS:
                known[study.nct_id] = (study, _history_outcome(study, snapshot_date))
            if 0 <= age <= MAX_COMPLETION_LAG_DAYS and study.results_date is None:
                eligible[study.nct_id] = study
        selected_ids = sorted(
            eligible,
            key=lambda nct_id: (hashlib.sha256(nct_id.encode("ascii")).hexdigest(), nct_id),
        )[:cohort_size]
        selected = set(selected_ids)
        retained = set(known) | selected
        relations: dict[str, dict[str, set[str]]] = {entity_type: {} for entity_type in ENTITY_TYPES}
        relation_rows: dict[str, int] = defaultdict(int)
        for table_name, entity_type in RELATION_TABLES.items():
            for row in _table_rows(archive, table_name, headers[table_name]):
                relation_rows[table_name] += 1
                nct_id = str(row.get("nct_id", "")).strip()
                if nct_id in retained:
                    _add_relation(relations, entity_type, nct_id, row.get("name"))
        for row in _table_rows(archive, "sponsors.txt", headers["sponsors.txt"]):
            relation_rows["sponsors.txt"] += 1
            nct_id = str(row.get("nct_id", "")).strip()
            if nct_id not in retained:
                continue
            role_text = str(row.get("lead_or_collaborator", "")).strip().casefold()
            if "lead" in role_text:
                entity_type = "sponsor"
            elif "collabor" in role_text:
                entity_type = "collaborator"
            else:
                raise ValueError(
                    f"unknown sponsor relation {role_text!r} for {nct_id} in snapshot {snapshot_date}"
                )
            _add_relation(relations, entity_type, nct_id, row.get("name"))
        designs: dict[str, dict[str, str]] = {}
        design_rows = 0
        for row in _table_rows(archive, "designs.txt", headers["designs.txt"]):
            design_rows += 1
            nct_id = str(row.get("nct_id", "")).strip()
            if nct_id not in selected:
                continue
            current = {
                field: str(row.get(field, "")).strip()
                for field in (
                    "allocation",
                    "intervention_model",
                    "primary_purpose",
                    "time_perspective",
                    "masking",
                )
            }
            previous = designs.setdefault(nct_id, {})
            for field, value in current.items():
                if not value:
                    continue
                if field in previous and previous[field] != value:
                    raise ValueError(f"conflicting design {field} for {nct_id} in snapshot {snapshot_date}")
                previous[field] = value
        history_by_type: dict[str, dict[str, _HistoryStats]] = {
            entity_type: {} for entity_type in ENTITY_TYPES
        }
        for nct_id, (_, outcome) in known.items():
            for entity_type in ENTITY_TYPES:
                for name in relations[entity_type].get(nct_id, set()):
                    stats = history_by_type[entity_type].setdefault(name, _HistoryStats())
                    stats.trial_count += 1
                    if outcome.timely:
                        stats.timely_count += 1
                    if outcome.delay_days is not None:
                        stats.posting_delays.append(outcome.delay_days)
        examples: list[_Example] = []
        coverage_counts: dict[str, dict[str, int]] = {
            entity_type: {"relation_present": 0, "history_present": 0}
            for entity_type in ENTITY_TYPES
        }
        for nct_id in selected_ids:
            study = eligible[nct_id]
            relation_counts: dict[str, int] = {}
            history_relation_counts: dict[str, int] = {}
            for entity_type in ENTITY_TYPES:
                names = relations[entity_type].get(nct_id, set())
                relation_counts[entity_type] = len(names)
                _, history_count = _aggregate_history(names, history_by_type[entity_type])
                history_relation_counts[entity_type] = history_count
                if names:
                    coverage_counts[entity_type]["relation_present"] += 1
                if history_count:
                    coverage_counts[entity_type]["history_present"] += 1
            sponsor, _ = _aggregate_history(
                relations["sponsor"].get(nct_id, set()), history_by_type["sponsor"]
            )
            context_names = {
                entity_type: relations[entity_type].get(nct_id, set())
                for entity_type in ("facility", "condition", "intervention", "collaborator")
            }
            context_values: list[dict[str, float | None]] = []
            context_by_type: dict[str, dict[str, float | None]] = {}
            context_history_count = 0
            context_entity_count = 0
            for entity_type, names in context_names.items():
                aggregate, history_count = _aggregate_history(names, history_by_type[entity_type])
                context_by_type[entity_type] = aggregate
                context_values.append(aggregate)
                context_history_count += history_count
                context_entity_count += len(names)
            context_prior = sum(float(value["prior_trial_count"] or 0.0) for value in context_values)
            context_timely_numerator = sum(
                float(value["timely_fraction"] or 0.0) * float(value["prior_trial_count"] or 0.0)
                for value in context_values
            )
            context_delays = [
                float(value["median_delay_days"])
                for value in context_values
                if value["median_delay_days"] is not None
            ]
            context = {
                "prior_trial_count": context_prior,
                "timely_fraction": (context_timely_numerator / context_prior) if context_prior else None,
                "median_delay_days": (sum(context_delays) / len(context_delays)) if context_delays else None,
                "entity_count": float(context_entity_count),
                "history_entity_count": float(context_history_count),
            }
            examples.append(
                _Example(
                    nct_id=nct_id,
                    origin_date=snapshot_date,
                    role=role,
                    study=study,
                    local=_local_features(study, designs, snapshot_date),
                    sponsor=sponsor,
                    context=context,
                    context_by_type=context_by_type,
                    relation_counts=relation_counts,
                    history_relation_counts=history_relation_counts,
                )
            )
    total_context_isolated = sum(
        1
        for example in examples
        if not any(example.history_relation_counts[entity_type] for entity_type in ENTITY_TYPES)
    )
    coverage: dict[str, Any] = {}
    for entity_type, counts in coverage_counts.items():
        coverage[entity_type] = {
            **counts,
            "target_count": len(examples),
            "relation_fraction": (counts["relation_present"] / len(examples)) if examples else None,
            "history_fraction": (counts["history_present"] / len(examples)) if examples else None,
        }
    coverage["isolated_target_trials"] = total_context_isolated
    coverage["nonisolated_target_trials"] = len(examples) - total_context_isolated
    audit = {
        "snapshot_date": snapshot_date.isoformat(),
        "role": role,
        "archive_sha256": manifest_entry["sha256"],
        "study_rows": study_rows,
        "interventional_rows_with_actual_completion": interventional_rows,
        "known_prior_trials_with_observed_365_day_outcome": len(known),
        "eligible_origin_pool": len(eligible),
        "selected_target_trials": len(examples),
        "cohort_size_limit": cohort_size,
        "relation_rows_scanned": dict(sorted(relation_rows.items())),
        "design_rows_scanned": design_rows,
    }
    return _OriginResult(examples=examples, audit=audit, coverage=coverage)


def _attach_future_labels(
    examples: list[_Example], future_path: Path, future_manifest_entry: dict[str, Any]
) -> dict[str, Any]:
    future_snapshot_date = str(future_manifest_entry["snapshot_date"])
    if not examples:
        return {
            "future_snapshot_date": future_snapshot_date,
            "missing_trials": 0,
            "missing_trial_ids": [],
            "origin_inconsistent_trials": 0,
            "origin_inconsistent_trial_ids": [],
            "selected_trials": 0,
            "future_rows_seen": 0,
            "observed_trials": 0,
        }
    origin = examples[0].origin_date
    future_date = date.fromisoformat(future_snapshot_date)
    horizon_end = origin + timedelta(days=HORIZON_DAYS)
    if future_date < horizon_end:
        raise ValueError(
            f"future AACT snapshot {future_date} does not cover the 365-day horizon from {origin}"
        )
    wanted = {example.nct_id: example for example in examples}
    seen: set[str] = set()
    origin_inconsistent: set[str] = set()
    headers = future_manifest_entry["headers"]
    with zipfile.ZipFile(future_path) as archive:
        for row in _table_rows(archive, "studies.txt", headers["studies.txt"]):
            nct_id = str(row.get("nct_id", "")).strip()
            if nct_id not in wanted:
                continue
            if nct_id in seen:
                raise ValueError(f"duplicate future studies.txt nct_id {nct_id} in snapshot {future_date}")
            seen.add(nct_id)
            result_date = _parse_date(
                row.get("results_first_posted_date"),
                field="results_first_posted_date",
                nct_id=nct_id,
                snapshot_date=future_date,
            )
            if result_date is not None and result_date > future_date:
                raise ValueError(
                    f"future AACT row exposes a result date after its snapshot: {nct_id}, {result_date}, {future_date}"
                )
            if result_date is not None and result_date <= origin:
                origin_inconsistent.add(nct_id)
                continue
            example = wanted[nct_id]
            example.result_date = result_date
            example.label = int(result_date is not None and result_date <= horizon_end)
    missing = sorted(set(wanted) - seen)
    missing_set = set(missing)
    excluded = missing_set | origin_inconsistent
    if excluded:
        examples[:] = [example for example in examples if example.nct_id not in excluded]
    origin_inconsistent_ids = sorted(origin_inconsistent)
    return {
        "future_snapshot_date": future_snapshot_date,
        "horizon_end": horizon_end.isoformat(),
        "missing_trials": len(missing),
        "missing_trial_ids": missing[:20],
        "origin_inconsistent_trials": len(origin_inconsistent),
        "origin_inconsistent_trial_ids": origin_inconsistent_ids[:20],
        "selected_trials": len(wanted),
        "future_rows_seen": len(seen),
        "observed_trials": len(examples),
        "excluded_trials": len(excluded),
        "positive_trials": sum(example.label or 0 for example in examples),
        "negative_trials": sum(1 for example in examples if example.label == 0),
    }


def _numeric_fields(examples: list[_Example], name: str) -> Iterator[float | None]:
    for example in examples:
        yield _numeric_field(example, name)


def _numeric_field(example: _Example, name: str) -> float | None:
    if name in LOCAL_NUMERIC:
        value = example.local.get(name)
    elif name.startswith("sponsor_"):
        value = example.sponsor.get(name.removeprefix("sponsor_"))
    elif name.startswith("context_entity_"):
        remainder = name.removeprefix("context_entity_")
        entity_type, separator, metric = remainder.partition("_")
        if separator and entity_type in ENTITY_TYPES:
            value = example.context_by_type.get(entity_type, {}).get(metric)
        else:
            value = example.context.get(name.removeprefix("context_"))
    elif name.startswith("context_"):
        value = example.context.get(name.removeprefix("context_"))
    else:
        raise KeyError(name)
    if value is None:
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _sigmoid(value: float) -> float:
    if value >= 0:
        exponent = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(max(value, -700.0))
    return exponent / (1.0 + exponent)


def _fit_logistic(group: str, examples: list[_Example]) -> tuple[_FeatureEncoder, list[float]]:
    if not examples:
        raise ValueError(f"cannot fit {group} without training examples")
    if any(example.label not in (0, 1) for example in examples):
        raise ValueError(f"{group} received unlabeled training example")
    encoder = _FeatureEncoder.build(group, examples)
    encoded = [(encoder.encode(example), int(example.label)) for example in sorted(examples, key=lambda item: item.nct_id)]
    weights = [0.0] * (len(encoder.feature_names) + 1)
    for _ in range(EPOCHS):
        for features, label in encoded:
            score = weights[0] + sum(weight * value for weight, value in zip(weights[1:], features))
            probability = _sigmoid(score)
            error = probability - label
            weights[0] -= LEARNING_RATE * error
            for index, value in enumerate(features, start=1):
                weights[index] -= LEARNING_RATE * (error * value + L2 * weights[index])
    return encoder, weights


def _predict(encoder: _FeatureEncoder, weights: list[float], examples: list[_Example]) -> dict[str, float]:
    predictions: dict[str, float] = {}
    for example in examples:
        features = encoder.encode(example)
        score = weights[0] + sum(weight * value for weight, value in zip(weights[1:], features))
        predictions[example.nct_id] = _sigmoid(score)
    return predictions


def _auc(labels: list[int], scores: list[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    ordered = sorted(zip(scores, labels), key=lambda pair: pair[0])
    rank_sum = 0.0
    position = 1
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = (position + position + (end - index) - 1) / 2.0
        rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        position += end - index
        index = end
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def _average_precision(labels: list[int], scores: list[float], ids: list[str]) -> float | None:
    positives = sum(labels)
    if positives == 0:
        return None
    ordered = sorted(zip(scores, labels, ids), key=lambda row: (-row[0], row[2]))
    found = 0
    total = 0.0
    for position, (_, label, _) in enumerate(ordered, start=1):
        if label:
            found += 1
            total += found / position
    return total / positives


def _metrics(examples: list[_Example], predictions: Mapping[str, float]) -> dict[str, Any]:
    labels = [int(example.label) for example in examples if example.label in (0, 1)]
    scores = [float(predictions[example.nct_id]) for example in examples if example.label in (0, 1)]
    ids = [example.nct_id for example in examples if example.label in (0, 1)]
    positives = sum(labels)
    count = len(labels)
    top_count = max(1, math.ceil(count * TOP_DECILE)) if count else 0
    ranked = sorted(
        ((predictions[example.nct_id], int(example.label), example.nct_id) for example in examples if example.label in (0, 1)),
        key=lambda row: (-row[0], row[2]),
    )
    top_positives = sum(label for _, label, _ in ranked[:top_count])
    brier = sum((score - label) ** 2 for score, label in zip(scores, labels)) / count if count else None
    log_loss = None
    if count:
        log_loss = -sum(
            label * math.log(min(max(score, 1e-12), 1.0 - 1e-12))
            + (1 - label) * math.log(min(max(1.0 - score, 1e-12), 1.0 - 1e-12))
            for score, label in zip(scores, labels)
        ) / count
    return {
        "trial_count": count,
        "positive_count": positives,
        "positive_prevalence": (positives / count) if count else None,
        "roc_auc": _auc(labels, scores),
        "average_precision": _average_precision(labels, scores, ids),
        "brier_score": brier,
        "log_loss": log_loss,
        "top_decile_count": top_count,
        "top_decile_precision": (top_positives / top_count) if top_count else None,
        "top_decile_recall": (top_positives / positives) if positives else None,
    }


def _configuration(cohort_size: int) -> dict[str, Any]:
    return {
        "analysis_version": ANALYSIS_VERSION,
        "snapshot_dates": list(SNAPSHOT_DATES),
        "snapshot_roles": dict(SNAPSHOT_ROLES),
        "origin_rule": {
            "study_type": "Interventional",
            "primary_completion_date_type": "Actual",
            "completion_lag_days": [0, MAX_COMPLETION_LAG_DAYS],
            "results_first_posted_date": "blank at origin",
        },
        "horizon_days": HORIZON_DAYS,
        "cohort_size_per_origin": cohort_size,
        "future_observation_rule": "Trials absent from the paired future snapshot or showing a future result date at or before the blank origin are excluded from labeled evaluation rather than treated as untimely.",
        "cohort_selection": "smallest SHA-256(NCT ID) then NCT ID among eligible origin rows",
        "prior_history_rule": "Only actual-completion trials at least 365 days before origin contribute known outcomes; blank result by that horizon is untimely.",
        "relation_identity": "exact trimmed source names, case-folded and whitespace-normalized; no entity resolution",
        "entities": list(ENTITY_TYPES),
        "models": [
            "trial_local_logistic",
            "sponsor_history_logistic",
            "heterogeneous_context_logistic",
        ],
        "logistic": {"epochs": EPOCHS, "learning_rate": LEARNING_RATE, "l2": L2},
        "evaluation": {
            "metrics": [
                "roc_auc",
                "average_precision",
                "brier_score",
                "log_loss",
                "top_decile_precision",
                "top_decile_recall",
            ],
            "top_decile_fraction": TOP_DECILE,
            "training": "rolling origins only; validation and held-out test are scored after fitting on strictly earlier origins",
        },
        "escalation_rule": "No graph neural model in this gate; require a positive reproducible held-out increment over trial-local and sponsor-history baselines before separate reviewer approval.",
    }


def _source_provenance(repo_root: Path) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root, check=True, capture_output=True, text=True
        ).stdout
        return {"commit": commit, "dirty": bool(status), "status_porcelain": status}
    except (OSError, subprocess.CalledProcessError) as exc:
        return {"commit": None, "dirty": None, "status_porcelain": None, "unavailable_reason": str(exc)}


def _write_jsonl(path: Path, rows: Iterator[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write(_canonical_json(row) + "\n")


def _score_groups(
    train_examples: list[_Example], evaluation_examples: list[_Example]
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, Any]]]:
    groups = ("trial_local_logistic", "sponsor_history_logistic", "heterogeneous_context_logistic")
    predictions: dict[str, dict[str, float]] = {}
    metrics: dict[str, dict[str, Any]] = {}
    for group in groups:
        encoder, weights = _fit_logistic(group, train_examples)
        predictions[group] = _predict(encoder, weights, evaluation_examples)
        metrics[group] = _metrics(evaluation_examples, predictions[group])
    return predictions, metrics


def _role_metrics(
    all_examples: list[_Example], prediction_rows: dict[str, dict[str, float]], role: str
) -> dict[str, Any]:
    selected = [example for example in all_examples if example.role == role]
    return {
        group: _metrics(selected, predictions)
        for group, predictions in prediction_rows.items()
    }


def run_gate(source_root: Path, manifest_path: Path, output_dir: Path, *, cohort_size: int = COHORT_SIZE) -> dict[str, Any]:
    """Run the historical AACT results-posting feasibility gate."""
    if cohort_size <= 0:
        raise ValueError("cohort_size must be positive")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output directory: {output_dir}")
    source_root = Path(source_root)
    manifest_path = Path(manifest_path)
    manifest, entries = _validate_manifest(manifest_path, source_root)
    entry_by_date = {str(entry["snapshot_date"]): entry for entry in entries}
    origins: dict[date, _OriginResult] = {}
    future_audits: dict[str, dict[str, Any]] = {}
    for snapshot_date in SNAPSHOT_DATES[:-1]:
        origin_entry = entry_by_date[snapshot_date]
        origin_path = _safe_source_path(source_root, origin_entry["path"])
        origin_result = _parse_origin_snapshot(origin_path, origin_entry, cohort_size)
        future_date = SNAPSHOT_DATES[SNAPSHOT_DATES.index(snapshot_date) + 1]
        future_entry = entry_by_date[future_date]
        future_path = _safe_source_path(source_root, future_entry["path"])
        future_audit = _attach_future_labels(origin_result.examples, future_path, future_entry)
        origin_result.audit["future_observed_target_trials"] = future_audit["observed_trials"]
        origin_result.audit["future_missing_target_trials"] = future_audit["missing_trials"]
        origin_result.audit["future_origin_inconsistent_trials"] = future_audit["origin_inconsistent_trials"]
        future_audits[snapshot_date] = future_audit
        origins[date.fromisoformat(snapshot_date)] = origin_result
    training_examples = [
        example
        for origin_date, origin_result in origins.items()
        if origin_date in TRAIN_ORIGINS
        for example in origin_result.examples
    ]
    validation_examples = origins[VALIDATION_ORIGIN].examples
    test_examples = origins[TEST_ORIGIN].examples
    if any(example.label not in (0, 1) for example in training_examples + validation_examples + test_examples):
        raise ValueError("AACT gate contains unlabeled examples after future snapshot attachment")

    validation_predictions, validation_metrics = _score_groups(training_examples, validation_examples)
    test_train_examples = training_examples + validation_examples
    test_predictions, test_metrics = _score_groups(test_train_examples, test_examples)
    prediction_rows: list[dict[str, Any]] = []
    for example in validation_examples:
        prediction_rows.append(
            {
                "nct_id": example.nct_id,
                "origin_date": example.origin_date.isoformat(),
                "role": example.role,
                "primary_completion_date": example.study.completion_date.isoformat(),
                "completion_lag_days": example.study.completion_lag_days,
                "label": example.label,
                "results_first_posted_date": example.result_date.isoformat() if example.result_date else None,
                "relation_counts": dict(example.relation_counts),
                "history_relation_counts": dict(example.history_relation_counts),
                "scores": {group: validation_predictions[group][example.nct_id] for group in validation_predictions},
            }
        )
    for example in test_examples:
        prediction_rows.append(
            {
                "nct_id": example.nct_id,
                "origin_date": example.origin_date.isoformat(),
                "role": example.role,
                "primary_completion_date": example.study.completion_date.isoformat(),
                "completion_lag_days": example.study.completion_lag_days,
                "label": example.label,
                "results_first_posted_date": example.result_date.isoformat() if example.result_date else None,
                "relation_counts": dict(example.relation_counts),
                "history_relation_counts": dict(example.history_relation_counts),
                "scores": {group: test_predictions[group][example.nct_id] for group in test_predictions},
            }
        )

    pooled_examples = validation_examples + test_examples
    pooled_predictions: dict[str, dict[str, float]] = {}
    for group in validation_predictions:
        pooled_predictions[group] = {
            **validation_predictions[group],
            **test_predictions[group],
        }
    pooled_metrics = {
        group: _metrics(pooled_examples, predictions)
        for group, predictions in pooled_predictions.items()
    }
    metric_deltas: dict[str, dict[str, float | None]] = {}
    for role, role_metric in (
        ("validation_origin", validation_metrics),
        ("held_out_test_origin", test_metrics),
        ("pooled", pooled_metrics),
    ):
        local_ap = role_metric["trial_local_logistic"]["average_precision"]
        metric_deltas[role] = {
            "sponsor_history_minus_trial_local_average_precision": (
                None
                if local_ap is None or role_metric["sponsor_history_logistic"]["average_precision"] is None
                else role_metric["sponsor_history_logistic"]["average_precision"] - local_ap
            ),
            "heterogeneous_context_minus_trial_local_average_precision": (
                None
                if local_ap is None or role_metric["heterogeneous_context_logistic"]["average_precision"] is None
                else role_metric["heterogeneous_context_logistic"]["average_precision"] - local_ap
            ),
            "heterogeneous_context_minus_sponsor_history_average_precision": (
                None
                if role_metric["heterogeneous_context_logistic"]["average_precision"] is None
                or role_metric["sponsor_history_logistic"]["average_precision"] is None
                else role_metric["heterogeneous_context_logistic"]["average_precision"]
                - role_metric["sponsor_history_logistic"]["average_precision"]
            ),
        }

    configuration = _configuration(cohort_size)
    repo_root = Path(__file__).resolve().parents[2]
    output_dir.mkdir(parents=True)
    predictions_path = output_dir / "predictions.jsonl"
    _write_jsonl(predictions_path, iter(prediction_rows))
    configuration_sha256 = hashlib.sha256(_canonical_json(configuration).encode("utf-8")).hexdigest()
    source_manifest_sha256 = sha256_file(manifest_path)
    support_ok = all(
        metric["positive_count"] > 0 and metric["positive_count"] < metric["trial_count"]
        for metric in (validation_metrics["trial_local_logistic"], test_metrics["trial_local_logistic"])
    )
    report: dict[str, Any] = {
        "record_kind": "clinical_trials_feasibility",
        "analysis_version": ANALYSIS_VERSION,
        "status": "exploratory",
        "decision": "REVIEW_REQUIRED" if support_ok else "INSUFFICIENT_OBSERVED_SUPPORT",
        "admission_status": "deferred",
        "graph_model_status": "no_go_for_escalation",
        "historical_availability_verified": True,
        "executed_at_utc": _utc_now(),
        "source_provenance": _source_provenance(repo_root),
        "input": {
            "manifest_path": str(manifest_path),
            "manifest_sha256": source_manifest_sha256,
            "format": manifest.get("format"),
            "required_tables": list(REQUIRED_TABLES),
            "verified_snapshots": [
                {
                    "snapshot_date": entry["snapshot_date"],
                    "role": SNAPSHOT_ROLES[str(entry["snapshot_date"])],
                    "path": entry["path"],
                    "sha256": entry["sha256"],
                    "bytes": entry["bytes"],
                }
                for entry in entries
            ],
        },
        "configuration": configuration,
        "configuration_sha256": configuration_sha256,
        "snapshot_audits": [origins[date.fromisoformat(snapshot_date)].audit for snapshot_date in SNAPSHOT_DATES[:-1]],
        "future_label_audits": future_audits,
        "coverage": {
            snapshot_date: origins[date.fromisoformat(snapshot_date)].coverage
            for snapshot_date in SNAPSHOT_DATES[:-1]
        },
        "training": {
            "origins": sorted(origin.isoformat() for origin in TRAIN_ORIGINS),
            "trial_count": len(training_examples),
            "positive_count": sum(example.label or 0 for example in training_examples),
            "negative_count": sum(1 for example in training_examples if example.label == 0),
            "validation_fit_excludes_validation_and_test": True,
            "test_fit_includes_validation_origin": True,
        },
        "metrics": {
            "validation_origin": validation_metrics,
            "held_out_test_origin": test_metrics,
            "pooled": pooled_metrics,
        },
        "metric_deltas": metric_deltas,
        "escalation": {
            "recommendation": "do_not_build_graph_neural_model_in_this_gate",
            "reason": "Review whether sponsor history and broader heterogeneous context add reproducible held-out average-precision signal over trial-local features before any separate graph-model request.",
            "message_passing": False,
        },
        "interpretation_limits": [
            "Results-first-posted-date is a registry publication outcome, not legal compliance or proof of reporting obligation.",
            "The target is timely posting within 365 days after actual primary completion, not whether a sponsor was legally required to report.",
            "Predictors are read only from the historical AACT snapshot at origin; later record revisions are excluded from origin features.",
            "Targets missing from the paired future snapshot or showing a future result date at or before the blank origin are excluded because their 365-day observation is unavailable; they are not labeled untimely.",
            "Exact source names are normalized only for within-snapshot relation matching; no sponsor, facility, condition, or intervention entity resolution is asserted.",
            "The bounded cohort and selected snapshots do not establish national representativeness or deployment validity.",
        ],
        "artifact_hashes": {
            "predictions.jsonl": sha256_file(predictions_path),
        },
    }
    report_path = output_dir / "report.json"
    report_path.write_text(_canonical_json(report) + "\n", encoding="utf-8")
    return report
