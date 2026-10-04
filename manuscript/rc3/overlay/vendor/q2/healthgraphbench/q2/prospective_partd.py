"""Prospective Part D forecast sealing and delayed, target-only evaluation."""

from __future__ import annotations

import csv
import hashlib
import heapq
import json
import math
import re
import time
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import numpy as np

from ..candidates.partd import (
    REQUIRED_COLUMNS,
    _first_seen_years,
    _iter_selected_rows,
    _safe_source_path,
    _validate_manifest,
    _write_edges,
)
from ..candidates.partd_model import (
    TOP_KS,
    _EvaluationAccumulator,
    _InputEdge,
    _ProjectedRow,
    _build_history,
    _candidate_drugs,
    _global_support,
    _overlap_scores,
    _project_rows,
    _specialty_scores,
    _positive_ranks,
    _specialty_support,
    _top_recommendations,
)
from ..data import sha256_file
from ..tasks.partd.task import PartDHistoryView, _history_view
from . import common
from .partd import (
    Q2_SEEDS,
    _fit_boosted,
    _fit_bpr,
    _fit_logistic,
    _training_row_count,
    _validate_protocol,
    _write_json,
)

TARGET_YEAR = 2025
PRIOR_YEARS = tuple(range(2019, TARGET_YEAR))
DEVELOPMENT_INVENTORY_SCHEMA = "healthgraphbench.q2-partd-development-population.v1"
ORIGIN_RECORD_KIND = "partd_q2_prospective_origin"
FORECAST_RECORD_KIND = "partd_q2_prospective_forecast"
EVALUATION_RECORD_KIND = "partd_q2_prospective_evaluation"
_CATALOG_YEAR_RE = re.compile(r"(?<!\d)2025(?!\d)")
_CHUNK_SIZE = 1024 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load {description} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object: {path}")
    return value


def _phase_result(phase_dir: Path) -> dict[str, Any]:
    result = _json_object(Path(phase_dir) / "result.json", "supervised Q2 phase result")
    return result


def _npi(value: object, *, context: str) -> str:
    result = "" if value is None else str(value)
    if len(result) != 10 or not result.isascii() or not result.isdigit():
        raise ValueError(f"invalid NPI {result!r} in {context}")
    return result


def _validate_https_cms_url(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty HTTPS CMS URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"data.cms.gov", "www.data.cms.gov"}:
        raise ValueError(f"{label} is not an HTTPS data.cms.gov URL: {value!r}")
    return value


def _capture_source(
    source_root: Path,
    entry: dict[str, Any],
    phase_dir: Path,
) -> dict[str, Any]:
    """Stream one public GET against the already-retained local bytes, without storing a copy."""
    phase_dir = Path(phase_dir)
    source_path = _safe_source_path(Path(source_root), entry["path"])
    url = _validate_https_cms_url(entry["url"], label=f"source URL {entry['path']}")
    started_at = _utc_now()
    digest = hashlib.sha256()
    sha1 = hashlib.sha1()
    received = 0
    response_metadata: dict[str, Any] = {}
    try:
        request = Request(url, headers={"User-Agent": "HealthGraphBench-Q2-prospective/1.0"})
        with source_path.open("rb") as local, urlopen(request, timeout=120) as response:
            response_metadata = {
                "status": int(getattr(response, "status", 200)),
                "final_url": response.geturl(),
                "headers": {str(key): str(value) for key, value in response.headers.items()},
            }
            if response_metadata["status"] != 200:
                raise ValueError(f"public source GET returned HTTP {response_metadata['status']}")
            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                local_chunk = local.read(len(chunk))
                digest.update(chunk)
                sha1.update(chunk)
                received += len(chunk)
                if local_chunk != chunk:
                    raise ValueError(
                        f"public bytes differ from retained local source at byte offset {received - len(chunk)}"
                    )
            if local.read(1):
                raise ValueError("retained local source has trailing bytes beyond the public GET")
        actual_sha256 = digest.hexdigest()
        expected_bytes = int(entry["bytes"])
        expected_sha256 = str(entry["sha256"]).lower()
        if received != expected_bytes:
            raise ValueError(f"public byte count mismatch: expected {expected_bytes}, received {received}")
        if actual_sha256 != expected_sha256:
            raise ValueError(f"public SHA-256 mismatch: expected {expected_sha256}, received {actual_sha256}")
        if source_path.stat().st_size != received:
            raise ValueError("retained local source size changed during public capture")
        result = {
            "year": int(entry["year"]),
            "manifest_path": str(entry["path"]),
            "url": url,
            "request_authentication": "none",
            "capture_started_at_utc": started_at,
            "capture_completed_at_utc": _utc_now(),
            "received_bytes": received,
            "sha256": actual_sha256,
            "sha1": sha1.hexdigest(),
            "manifest_sha256": expected_sha256,
            "retained_local_path": str(source_path),
            "retained_local_bytes": source_path.stat().st_size,
            "retained_local_sha256": actual_sha256,
            "byte_for_byte_equal_to_retained_local": True,
            **response_metadata,
        }
        _write_json(phase_dir / "capture_attempt.json", result)
        return result
    except BaseException as exc:
        try:
            _write_json(
                phase_dir / "capture_attempt.json",
                {
                    "year": int(entry["year"]),
                    "manifest_path": str(entry["path"]),
                    "url": url,
                    "request_authentication": "none",
                    "capture_started_at_utc": started_at,
                    "capture_failed_at_utc": _utc_now(),
                    "received_bytes_before_failure": received,
                    "partial_sha256": digest.hexdigest(),
                    "byte_for_byte_equal_to_retained_local": False,
                    "response": response_metadata,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
        except OSError:
            pass
        raise


def _catalog_2025_nodes(document: object) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        raise ValueError("CMS dataset catalogue response root is not an object")
    nodes = document.get("data")
    if not isinstance(nodes, list):
        raise ValueError("CMS dataset catalogue response has no data array")
    matching: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        attributes = node.get("attributes")
        if not isinstance(attributes, dict):
            continue
        version = attributes.get("field_dataset_version")
        version_text = str(version).strip()
        if version_text == "2025" or _CATALOG_YEAR_RE.search(version_text):
            matching.append(
                {
                    "dataset_id": node.get("id"),
                    "dataset_version": version,
                    "re_release_version": attributes.get("field_re_release_version"),
                    "last_updated_date": attributes.get("field_last_updated_date"),
                    "re_release_select": attributes.get("field_re_release_select"),
                }
            )
    return matching


def _capture_catalog(catalog_url: str, phase_dir: Path) -> dict[str, Any]:
    phase_dir = Path(phase_dir)
    url = _validate_https_cms_url(catalog_url, label="CMS dataset catalogue URL")
    started_at = _utc_now()
    try:
        request = Request(url, headers={"User-Agent": "HealthGraphBench-Q2-prospective/1.0"})
        with urlopen(request, timeout=120) as response:
            status = int(getattr(response, "status", 200))
            if status != 200:
                raise ValueError(f"CMS catalogue GET returned HTTP {status}")
            digest = hashlib.sha256()
            body = bytearray()
            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                body.extend(chunk)
            response_metadata = {
                "status": status,
                "final_url": response.geturl(),
                "headers": {str(key): str(value) for key, value in response.headers.items()},
            }
        document = json.loads(body)
        matching = _catalog_2025_nodes(document)
        response_path = phase_dir / "catalog_response.json"
        response_path.write_bytes(body)
        return {
            "url": url,
            "request_authentication": "none",
            "captured_at_utc": _utc_now(),
            "request_started_at_utc": started_at,
            "response_bytes": len(body),
            "response_sha256": digest.hexdigest(),
            "response_file": response_path.name,
            "response_file_sha256": sha256_file(response_path),
            "metadata_only": True,
            "service_2025_officially_listed": bool(matching),
            "matching_dataset_nodes": matching,
            **response_metadata,
        }
    except BaseException as exc:
        try:
            _write_json(
                phase_dir / "catalog_capture_error.json",
                {
                    "url": url,
                    "request_started_at_utc": started_at,
                    "failed_at_utc": _utc_now(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
        except OSError:
            pass
        raise


def _read_development_population(path: Path) -> tuple[set[str], dict[str, Any]]:
    record = _json_object(path, "Part D development NPI inventory")
    if record.get("schema") != DEVELOPMENT_INVENTORY_SCHEMA:
        raise ValueError("Part D development NPI inventory has an unsupported schema")
    values = record.get("npis")
    if not isinstance(values, list):
        raise ValueError("Part D development NPI inventory is missing its NPI list")
    npis = {_npi(value, context="development NPI inventory") for value in values}
    if len(npis) != len(values) or record.get("npi_count") != len(npis) or len(npis) != 2518:
        raise ValueError("Part D development NPI inventory must contain exactly 2518 distinct NPIs")
    return npis, {
        "path": str(path),
        "sha256": sha256_file(path),
        "npi_count": len(npis),
        "schema": record["schema"],
        "identity_only_scan_is_not_drug_label_consultation": record.get(
            "identity_only_scan_is_not_drug_label_consultation"
        ),
    }


def _read_comparison_population(
    prepared_dir: Path,
    expected_manifest_sha256: str,
) -> tuple[set[str], dict[str, Any]]:
    prepared_dir = Path(prepared_dir)
    report_path = prepared_dir / "report.json"
    edges_path = prepared_dir / "edges.csv"
    report = _json_object(report_path, "new Part D comparison preparation report")
    if report.get("record_kind") != "partd_execution_preparation" or report.get("status") != "prepared":
        raise ValueError("comparison preparation must be a completed raw Part D execution preparation")
    sources = report.get("sources")
    if not isinstance(sources, dict) or sources.get("manifest_sha256") != expected_manifest_sha256:
        raise ValueError("comparison preparation does not use the locked six-source manifest")
    configuration = report.get("configuration")
    if not isinstance(configuration, dict) or configuration.get("years") != list(PRIOR_YEARS):
        raise ValueError("comparison preparation is not based on exactly service years 2019-2024")
    artifact_hashes = report.get("artifact_hashes")
    expected_edges_hash = artifact_hashes.get("edges.csv") if isinstance(artifact_hashes, dict) else None
    actual_edges_hash = sha256_file(edges_path)
    if not isinstance(expected_edges_hash, str) or actual_edges_hash != expected_edges_hash:
        raise ValueError("comparison preparation edges.csv hash differs from its report")
    cohort_value = report.get("cohort")
    by_year = cohort_value.get("by_target_year") if isinstance(cohort_value, dict) else None
    if not isinstance(by_year, dict):
        raise ValueError("comparison preparation report is missing target cohort identities")
    npis: set[str] = set()
    for year, values in by_year.items():
        if not isinstance(year, str) or not isinstance(values, list):
            raise ValueError("comparison preparation cohort must map year strings to NPI lists")
        for value in values:
            npis.add(_npi(value, context=f"comparison preparation report cohort {year}"))
    if not npis:
        raise ValueError("comparison preparation report has no provider identities")
    try:
        with edges_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames is None or "npi" not in reader.fieldnames:
                raise ValueError("comparison preparation edges.csv has no npi column")
            for row_number, row in enumerate(reader, start=1):
                if None in row:
                    raise ValueError(f"malformed comparison edge at row {row_number}")
                npis.add(_npi(row.get("npi"), context=f"comparison preparation edge row {row_number}"))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"unable to scan comparison preparation NPI identities: {exc}") from exc
    return npis, {
        "prepared_dir": str(prepared_dir),
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path),
        "edges_path": str(edges_path),
        "edges_sha256": actual_edges_hash,
        "npi_count": len(npis),
        "identity_fields_read": ["report.cohort.by_target_year", "edges.csv.npi"],
        "drug_claim_and_target_label_fields_consulted": False,
    }


def _salted_cohort_hash(npi: str, salt: str) -> str:
    return hashlib.sha256((salt + "\0" + npi).encode("ascii")).hexdigest()


class TrainingOrigin:
    """Real six-year Part D training history and fixed 2025 candidate cohort."""

    def __init__(self, rows_by_year: dict[int, list[_ProjectedRow]], cohort: set[str]):
        self.rows_by_year = rows_by_year
        self.cohort = cohort

    def _target_history(self, year: int) -> tuple[Any, tuple[int, ...], set[str]]:
        if year != TARGET_YEAR:
            raise ValueError(f"prospective Part D TrainingOrigin only supports target year {TARGET_YEAR}")
        history = _build_history(self.rows_by_year, PRIOR_YEARS, self.cohort)
        return history, PRIOR_YEARS, self.cohort


def _save_history_rows(path: Path, rows_by_year: dict[int, list[_ProjectedRow]]) -> int:
    count = 0
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        for year in PRIOR_YEARS:
            for row in rows_by_year[year]:
                handle.write(
                    _canonical_json(
                        {
                            "year": row.year,
                            "npi": row.npi,
                            "generic_name": row.drug,
                            "claims": row.claims,
                            "specialties": list(row.specialties),
                        }
                    )
                    + "\n"
                )
                count += 1
    return count


def _write_candidate_layout(path: Path, origin: TrainingOrigin) -> dict[str, Any]:
    history, _, cohort = origin._target_history(TARGET_YEAR)
    providers = tuple(sorted(cohort))
    drugs = tuple(sorted(history.drug_providers))
    offsets = np.zeros(len(providers) + 1, dtype=np.int64)
    for index, npi in enumerate(providers):
        own_drugs = history.provider_drugs.get(npi, set())
        offsets[index + 1] = offsets[index] + len(drugs) - len(own_drugs)
    candidate_indices = np.empty(int(offsets[-1]), dtype=np.int64)
    for index, npi in enumerate(providers):
        own_drugs = history.provider_drugs.get(npi, set())
        position = int(offsets[index])
        for drug_index, drug in enumerate(drugs):
            if drug not in own_drugs:
                candidate_indices[position] = drug_index
                position += 1
        if position != int(offsets[index + 1]):
            raise ValueError(f"candidate count changed while sealing provider {npi}")
    np.savez_compressed(
        path,
        provider_ids=np.asarray(providers, dtype=np.str_),
        drug_ids=np.asarray(drugs, dtype=np.str_),
        drug_global_support=np.asarray([_global_support(history, drug) for drug in drugs], dtype=np.int64),
        provider_candidate_offsets=offsets,
        candidate_drug_indices=candidate_indices,
    )
    return {
        "path": path.name,
        "sha256": sha256_file(path),
        "provider_count": len(providers),
        "global_prior_drug_count": len(drugs),
        "candidate_score_count": len(candidate_indices),
        "candidate_set_encoding": "provider offsets and candidate indices address drug_ids; exact generic-name IDs",
        "tie_support_vector": "drug_global_support aligned with drug_ids",
    }


def _prepare_origin_worker(
    source_root: Path,
    manifest_path: Path,
    development_population_path: Path,
    comparison_prepared_dir: Path,
    destination: Path,
    source_captures: list[dict[str, Any]],
    catalog_capture: dict[str, Any],
    selection_sha256: str,
    protocol_sha256: str,
    selection_bytes: bytes,
    selected_configurations: dict[str, Any],
    salt: str,
    cohort_size: int,
    run_output_dir: Path,
    origin_sealed_at_utc: str,
    phase_dir: Path,
) -> dict[str, Any]:
    source_root = Path(source_root)
    manifest_path = Path(manifest_path)
    destination = Path(destination)
    manifest, entries = _validate_manifest(manifest_path, source_root)
    years = [int(entry["year"]) for entry in entries]
    if years != list(PRIOR_YEARS):
        raise ValueError(f"prospective Part D origin requires 2019-2024 sources, got {years!r}")
    if len(source_captures) != 6 or {int(item["year"]) for item in source_captures} != set(PRIOR_YEARS):
        raise ValueError("origin cannot be prepared without six successful exact public source captures")
    if any(item.get("byte_for_byte_equal_to_retained_local") is not True for item in source_captures):
        raise ValueError("origin source capture does not match retained local bytes")
    if catalog_capture.get("service_2025_officially_listed") is not False:
        raise ValueError("origin cannot be sealed while service year 2025 is officially listed")
    if isinstance(cohort_size, bool) or cohort_size != 2000:
        raise ValueError("prospective Part D cohort size is locked at 2000")
    if salt != "q2-prospective-20261003":
        raise ValueError("prospective Part D cohort salt differs from the published Q2 salt")

    development_npis, development_record = _read_development_population(Path(development_population_path))
    comparison_npis, comparison_record = _read_comparison_population(
        Path(comparison_prepared_dir), sha256_file(manifest_path)
    )
    excluded_npis = development_npis | comparison_npis
    first_seen = _first_seen_years(source_root, entries)
    eligible = sorted(npi for npi, year in first_seen.items() if year in PRIOR_YEARS and npi not in excluded_npis)
    if len(eligible) < cohort_size:
        raise ValueError(
            f"only {len(eligible)} eligible first-seen NPIs remain after exclusions; exactly {cohort_size} required"
        )
    ranked = sorted((_salted_cohort_hash(npi, salt), npi) for npi in eligible)
    cohort = {npi for _, npi in ranked[:cohort_size]}
    if len(cohort) != cohort_size or cohort & excluded_npis:
        raise ValueError("deterministic prospective cohort selection failed its size or exclusion invariant")

    raw_rows_by_year: dict[int, list[Any]] = {}
    for entry in entries:
        path = _safe_source_path(source_root, entry["path"])
        raw_rows_by_year[int(entry["year"])] = _iter_selected_rows(path, entry, cohort)
    destination.mkdir(parents=True, exist_ok=False)
    edges_path = destination / "edges.csv"
    _write_edges(edges_path, raw_rows_by_year)
    input_rows_by_year = {
        year: [
            _InputEdge(year, row.npi, row.brand_name, row.generic_name, row.claims, row.specialty)
            for row in rows
        ]
        for year, rows in raw_rows_by_year.items()
    }
    projected_rows_by_year, projection = _project_rows(input_rows_by_year, "generic")
    origin = TrainingOrigin(projected_rows_by_year, cohort)
    history_rows_path = destination / "history_rows.jsonl"
    projected_count = _save_history_rows(history_rows_path, projected_rows_by_year)
    candidate_layout = _write_candidate_layout(destination / "candidate_layout.npz", origin)
    training_rows = _training_row_count(origin, TARGET_YEAR)
    selection_path = destination / "selection.json"
    selection_path.write_bytes(selection_bytes)
    cohort_path = destination / "cohort.json"
    cohort_record = {
        "target_year": TARGET_YEAR,
        "cohort_size": cohort_size,
        "selection": "ascending SHA-256 hex of ASCII(salt + NUL + NPI), then ascending NPI; selected first 2000 eligible NPIs",
        "salt": salt,
        "eligible_first_seen_population_count_after_exclusions": len(eligible),
        "development_exclusion_count": len(development_npis),
        "comparison_preparation_exclusion_count": len(comparison_npis),
        "combined_exclusion_count": len(excluded_npis),
        "overlap_between_exclusion_sets": len(development_npis & comparison_npis),
        "selected_npis": sorted(cohort),
        "selected_hashes": [
            {"npi": npi, "sha256_salted_npi": _salted_cohort_hash(npi, salt)}
            for npi in sorted(cohort)
        ],
    }
    _write_json(cohort_path, cohort_record)
    capture_completed_at = max(
        [str(item["capture_completed_at_utc"]) for item in source_captures]
        + [str(catalog_capture["captured_at_utc"])]
    )
    sealed_at = origin_sealed_at_utc
    report = {
        "record_kind": ORIGIN_RECORD_KIND,
        "status": "sealed_awaiting_official_target_publication",
        "protocol_sha256": protocol_sha256,
        "task": "partd_prescriber_drug",
        "target_year": TARGET_YEAR,
        "prior_years": list(PRIOR_YEARS),
        "origin_sealed_at_utc": sealed_at,
        "source_capture_completed_at_utc": capture_completed_at,
        "availability_claim": "verified_public_recapture_before_prediction; not_first_publication_or_first_prescription",
        "human_nonconsultation_gate": "unknown; requires external human attestation; no assistant claim",
        "source_root": str(source_root),
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": sha256_file(manifest_path),
        "source_files": source_captures,
        "catalog_capture": catalog_capture,
        "official_target_publication_found_at_origin": False,
        "comparison_selection": {
            "path": str(selection_path),
            "sha256": selection_sha256,
            "selected_configurations": selected_configurations,
            "configurations_read_from_selection_only": True,
        },
        "development_population": development_record,
        "comparison_preparation": comparison_record,
        "cohort": {
            "path": cohort_path.name,
            "sha256": sha256_file(cohort_path),
            "selected_provider_count": len(cohort),
            "eligible_first_seen_provider_count_after_exclusions": len(eligible),
            "salt": salt,
            "selection_hash": cohort_record["selection"],
            "first_seen_years": [int(year) for year in PRIOR_YEARS],
        },
        "preparation": {
            "edges_path": edges_path.name,
            "edges_sha256": sha256_file(edges_path),
            "history_rows_path": history_rows_path.name,
            "history_rows_sha256": sha256_file(history_rows_path),
            "projected_history_rows": projected_count,
            "generic_projection": projection,
            "candidate_layout": candidate_layout,
            "training_rows_for_seed_policy": training_rows,
        },
        "run_output_dir": str(Path(run_output_dir).resolve()),
        "source_manifest_metadata": {
            "landing_url": manifest["landing_url"],
            "dataset": manifest["dataset"],
            "years": years,
        },
        "sealed_at_utc_precedes_preparation_completion": True,
    }
    _write_json(destination / "origin.json", report)
    return {
        "origin_dir": str(destination),
        "origin_sha256": sha256_file(destination / "origin.json"),
        "status": report["status"],
        "cohort_size": len(cohort),
        "eligible_npis_after_exclusions": len(eligible),
        "retained_edges": sum(len(rows) for rows in raw_rows_by_year.values()),
        "projected_history_rows": projected_count,
        "candidate_score_count": candidate_layout["candidate_score_count"],
        "training_rows": training_rows,
        "phase_dir": str(phase_dir),
    }


def _read_history_origin(origin_dir: Path) -> tuple[dict[str, Any], TrainingOrigin, dict[str, Any]]:
    origin_dir = Path(origin_dir).resolve(strict=True)
    report = _json_object(origin_dir / "origin.json", "prospective Part D origin")
    if report.get("record_kind") != ORIGIN_RECORD_KIND or report.get("status") != "sealed_awaiting_official_target_publication":
        raise ValueError("origin is not a sealed prospective Part D forecast origin")
    if report.get("target_year") != TARGET_YEAR or report.get("prior_years") != list(PRIOR_YEARS):
        raise ValueError("prospective origin has altered target or history years")
    cohort_data = _json_object(origin_dir / "cohort.json", "prospective Part D cohort")
    salt = cohort_data.get("salt")
    selected_npis = cohort_data.get("selected_npis")
    selected_hashes = cohort_data.get("selected_hashes")
    if salt != "q2-prospective-20261003":
        raise ValueError("sealed cohort uses an unexpected deterministic salt")
    if not isinstance(selected_npis, list) or selected_npis != sorted(selected_npis):
        raise ValueError("sealed cohort identities must be a sorted NPI list")
    if not isinstance(selected_hashes, list) or len(selected_hashes) != len(selected_npis):
        raise ValueError("sealed cohort hash list is malformed")
    selected_npis = [_npi(value, context="sealed prospective cohort") for value in selected_npis]
    expected_hashes = [
        {"npi": npi, "sha256_salted_npi": _salted_cohort_hash(npi, salt)}
        for npi in selected_npis
    ]
    if selected_hashes != expected_hashes:
        raise ValueError("sealed cohort salted NPI hashes do not reproduce")
    cohort = set(selected_npis)
    if len(cohort) != 2000 or cohort_data.get("cohort_size") != 2000:
        raise ValueError("sealed prospective cohort must contain exactly 2000 NPIs")

    run_output_dir = Path(report.get("run_output_dir", "")).resolve(strict=True)
    if origin_dir != (run_output_dir / "sealed_origin").resolve():
        raise ValueError("sealed origin is outside its recorded Q2 run output")
    prep = report.get("preparation")
    if not isinstance(prep, dict):
        raise ValueError("sealed origin is missing preparation artifact hashes")
    file_hashes = {
        "edges.csv": prep.get("edges_sha256"),
        "history_rows.jsonl": prep.get("history_rows_sha256"),
        "candidate_layout.npz": (prep.get("candidate_layout") or {}).get("sha256"),
    }
    for name, expected_hash in file_hashes.items():
        path = origin_dir / name
        if not isinstance(expected_hash, str) or sha256_file(path) != expected_hash:
            raise ValueError(f"sealed origin artifact hash mismatch: {name}")
    cohort_ref = report.get("cohort")
    if not isinstance(cohort_ref, dict) or sha256_file(origin_dir / "cohort.json") != cohort_ref.get("sha256"):
        raise ValueError("sealed origin cohort hash mismatch")
    selection_record = report.get("comparison_selection")
    if (
        not isinstance(selection_record, dict)
        or selection_record.get("configurations_read_from_selection_only") is not True
        or sha256_file(origin_dir / "selection.json") != selection_record.get("sha256")
    ):
        raise ValueError("sealed origin comparison selection provenance is invalid")
    source_files = report.get("source_files")
    if (
        not isinstance(source_files, list)
        or len(source_files) != len(PRIOR_YEARS)
        or any(not isinstance(item, dict) for item in source_files)
        or {item.get("year") for item in source_files} != set(PRIOR_YEARS)
    ):
        raise ValueError("sealed origin must contain exactly six historical public captures")
    if not isinstance(report.get("source_manifest_sha256"), str):
        raise ValueError("sealed origin source manifest provenance is missing")
    for capture in source_files:
        if (
            capture.get("byte_for_byte_equal_to_retained_local") is not True
            or capture.get("sha256") != capture.get("manifest_sha256")
        ):
            raise ValueError("sealed origin includes an unverified public source capture")

    rows_by_year: dict[int, list[_ProjectedRow]] = {year: [] for year in PRIOR_YEARS}
    path = origin_dir / "history_rows.jsonl"
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid sealed history row {line_number}: {exc}") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"sealed history row {line_number} is not an object")
                year = value.get("year")
                npi = _npi(value.get("npi"), context=f"sealed history row {line_number}")
                drug = value.get("generic_name")
                claims = value.get("claims")
                specialties = value.get("specialties")
                if year not in rows_by_year or npi not in cohort:
                    raise ValueError(f"sealed history row {line_number} escapes its year/cohort")
                if not isinstance(drug, str) or not drug or isinstance(claims, bool) or not isinstance(claims, int):
                    raise ValueError(f"invalid generic history fields in sealed row {line_number}")
                if not isinstance(specialties, list) or any(not isinstance(value, str) for value in specialties):
                    raise ValueError(f"invalid specialty list in sealed row {line_number}")
                rows_by_year[year].append(_ProjectedRow(year, npi, drug, claims, tuple(specialties)))
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"unable to read sealed prospective history: {exc}") from exc
    if sum(map(len, rows_by_year.values())) != prep.get("projected_history_rows"):
        raise ValueError("sealed prospective history row count differs from its origin report")
    return report, TrainingOrigin(rows_by_year, cohort), cohort_data


def _read_candidate_layout(origin_dir: Path, origin: TrainingOrigin) -> dict[str, Any]:
    layout_path = Path(origin_dir) / "candidate_layout.npz"
    history, _, cohort = origin._target_history(TARGET_YEAR)
    try:
        with np.load(layout_path, allow_pickle=False) as loaded:
            if set(loaded.files) != {
                "provider_ids",
                "drug_ids",
                "drug_global_support",
                "provider_candidate_offsets",
                "candidate_drug_indices",
            }:
                raise ValueError("candidate layout has unexpected array fields")
            providers = loaded["provider_ids"]
            drugs = loaded["drug_ids"]
            support = loaded["drug_global_support"]
            offsets = loaded["provider_candidate_offsets"]
            indices = loaded["candidate_drug_indices"]
    except (OSError, ValueError) as exc:
        raise ValueError(f"unable to load sealed candidate layout: {exc}") from exc
    expected_providers = np.asarray(sorted(cohort), dtype=np.str_)
    expected_drugs = np.asarray(sorted(history.drug_providers), dtype=np.str_)
    expected_support = np.asarray([_global_support(history, str(drug)) for drug in expected_drugs], dtype=np.int64)
    if not np.array_equal(providers, expected_providers) or not np.array_equal(drugs, expected_drugs):
        raise ValueError("sealed candidate layout provider/drug identities differ from exact history")
    if not np.array_equal(support, expected_support):
        raise ValueError("sealed candidate tie-support vector differs from exact history")
    if offsets.shape != (len(providers) + 1,) or int(offsets[0]) != 0 or int(offsets[-1]) != len(indices):
        raise ValueError("sealed candidate layout offsets are malformed")
    if len(indices) and (int(indices.min()) < 0 or int(indices.max()) >= len(drugs)):
        raise ValueError("sealed candidate layout contains an out-of-range drug index")
    drug_index = {str(drug): index for index, drug in enumerate(drugs)}
    for provider_index, npi in enumerate(providers):
        start = int(offsets[provider_index])
        end = int(offsets[provider_index + 1])
        actual = indices[start:end]
        expected = np.asarray(
            [drug_index[drug] for drug in sorted(_candidate_drugs(history, str(npi)))],
            dtype=np.int64,
        )
        if not np.array_equal(actual, expected):
            raise ValueError(f"sealed candidates differ from exact prior history for NPI {npi}")
    return {
        "provider_ids": providers,
        "drug_ids": drugs,
        "drug_global_support": support,
        "provider_candidate_offsets": offsets,
        "candidate_drug_indices": indices,
    }


def _score_forecast_worker(
    origin_dir: Path,
    family: str,
    configuration: dict[str, Any] | None,
    configuration_index: int | None,
    seed: int | None,
    fixed: dict[str, Any],
    phase_dir: Path,
) -> dict[str, Any]:
    origin_dir = Path(origin_dir)
    phase_dir = Path(phase_dir)
    origin_report, origin, _ = _read_history_origin(origin_dir)
    layout = _read_candidate_layout(origin_dir, origin)
    history, prior_years, cohort = origin._target_history(TARGET_YEAR)
    view = _history_view(history, TARGET_YEAR, prior_years)
    if family == "specialty_popularity":
        latest = {npi: history.latest_specialty(npi) for npi in history.provider_drugs}
        specialty_support = _specialty_support(history)

        def scorer(history_view: PartDHistoryView, npi: str, candidates: tuple[str, ...]) -> Mapping[str, float]:
            if history_view.target_year != TARGET_YEAR:
                raise ValueError("specialty popularity used with a different cutoff")
            scores, _ = _specialty_scores(history, npi, set(candidates), latest, specialty_support)
            return scores

        fit_summary: dict[str, Any] = {"fit": "none; deterministic history-only baseline"}
    elif family == "history_overlap":
        def scorer(history_view: PartDHistoryView, npi: str, candidates: tuple[str, ...]) -> Mapping[str, float]:
            if history_view.target_year != TARGET_YEAR:
                raise ValueError("history overlap used with a different cutoff")
            return _overlap_scores(history, npi, set(candidates))

        fit_summary = {"fit": "none; deterministic history-only baseline"}
    elif family == "logistic":
        if configuration is None:
            raise ValueError("selected logistic configuration is missing")
        scorer, fit_summary = _fit_logistic(origin, TARGET_YEAR, configuration, fixed["logistic"], seed, phase_dir / "model")
    elif family == "boosted":
        if configuration is None:
            raise ValueError("selected boosted-tree configuration is missing")
        scorer, fit_summary = _fit_boosted(origin, TARGET_YEAR, configuration, fixed["boosted"], seed, phase_dir / "model")
    elif family == "bpr":
        if configuration is None:
            raise ValueError("selected BPR configuration is missing")
        scorer, fit_summary = _fit_bpr(origin, TARGET_YEAR, configuration, fixed["bpr"], seed, phase_dir / "model")
    else:
        raise ValueError(f"unknown prospective Part D family {family!r}")

    provider_ids = layout["provider_ids"]
    drug_ids = layout["drug_ids"]
    offsets = layout["provider_candidate_offsets"]
    candidate_indices = layout["candidate_drug_indices"]
    supports = layout["drug_global_support"]
    drug_support = {str(drug): int(supports[index]) for index, drug in enumerate(drug_ids)}
    all_scores = np.empty(len(candidate_indices), dtype=np.float64)
    predictions_path = phase_dir / "predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8", newline="") as output:
        for provider_index, raw_npi in enumerate(provider_ids):
            npi = str(raw_npi)
            start = int(offsets[provider_index])
            end = int(offsets[provider_index + 1])
            candidate_ids = tuple(str(drug_ids[index]) for index in candidate_indices[start:end])
            raw_scores = scorer(view, npi, candidate_ids)
            candidate_set = set(candidate_ids)
            if not isinstance(raw_scores, Mapping) or set(raw_scores) != candidate_set:
                raise ValueError(f"ranker must score every prospective candidate exactly once for NPI {npi}")
            row_scores: dict[str, float] = {}
            for offset, drug in enumerate(candidate_ids, start=start):
                value = raw_scores[drug]
                if isinstance(value, bool):
                    raise ValueError(f"ranker returned a boolean score for {drug!r}")
                score = float(value)
                if not math.isfinite(score):
                    raise ValueError(f"ranker returned a non-finite score for {drug!r}")
                all_scores[offset] = score
                row_scores[drug] = score
            recommendations = heapq.nsmallest(
                TOP_KS[-1],
                candidate_ids,
                key=lambda drug: (-row_scores[drug], -drug_support[drug], drug),
            )
            record = {
                "target_year": TARGET_YEAR,
                "npi": npi,
                "eligible": bool(history.provider_drugs.get(npi)),
                "candidate_count": len(candidate_ids),
                "recommendations": [
                    {"drug": drug, "rank": rank, "score": row_scores[drug]}
                    for rank, drug in enumerate(recommendations, start=1)
                ],
            }
            output.write(_canonical_json(record) + "\n")
    score_path = phase_dir / "candidate_scores.npz"
    np.savez_compressed(score_path, candidate_scores=all_scores)
    return {
        "family": family,
        "configuration_index": configuration_index,
        "configuration": configuration,
        "seed": seed,
        "fit": fit_summary,
        "candidate_layout_sha256": sha256_file(origin_dir / "candidate_layout.npz"),
        "candidate_score_count": int(len(all_scores)),
        "candidate_scores_file": score_path.name,
        "candidate_scores_sha256": sha256_file(score_path),
        "prediction_file": predictions_path.name,
        "prediction_file_sha256": sha256_file(predictions_path),
        "target_provider_count": len(cohort),
        "scoring_policy": "all candidates scored; no target labels or metrics used",
    }


def _load_selection(selection_bytes: bytes, partd_protocol: dict[str, Any]) -> dict[str, Any]:
    try:
        selection = json.loads(selection_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid comparison selection.json: {exc}") from exc
    if not isinstance(selection, dict) or not isinstance(selection.get("families"), dict):
        raise ValueError("comparison selection.json is missing its families object")
    if selection.get("validation_year") != 2023 or selection.get("test_year") != 2024:
        raise ValueError("comparison selection must be the Part D 2023 validation selection")
    if selection.get("seeds_are_not_selected") is not True:
        raise ValueError("comparison selection must keep the protocol seeds fixed")
    selected: dict[str, Any] = {}
    for family in ("logistic", "boosted", "bpr"):
        value = selection["families"].get(family)
        if not isinstance(value, dict):
            raise ValueError(f"comparison selection.json is missing selected family {family}")
        index = value.get("configuration_index")
        configuration = value.get("configuration")
        grid = partd_protocol["grids"][family]
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(grid):
            raise ValueError(f"comparison selection has invalid {family} configuration_index")
        if configuration != grid[index]:
            raise ValueError(f"comparison selection {family} configuration differs from locked Q2 grid")
        selected[family] = {"configuration_index": index, "configuration": dict(configuration)}
    return selected


def _read_locked_protocol_config(protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    partd = _validate_protocol(protocol)
    prospective = partd.get("prospective")
    if not isinstance(prospective, dict):
        raise ValueError("Q2 Part D protocol is missing tasks.partd.prospective")
    expected = {
        "target_year": TARGET_YEAR,
        "source_manifest": partd.get("source_manifest"),
        "catalog_url": prospective.get("catalog_url"),
        "cohort_size": 2000,
        "cohort_salt": "q2-prospective-20261003",
        "cohort_hash": "sha256((salt + NUL + NPI).ascii), ascending (lowercase_hex_digest, NPI)",
        "development_population": "results/q2_partd_development_population_20261003.json",
        "comparison_prepared_relative": "phases/prepare_raw/prepared",
        "availability_claim": "verified_public_recapture_before_prediction; not_first_publication_or_first_prescription",
    }
    for key, value in expected.items():
        if prospective.get(key) != value:
            raise ValueError(f"Q2 Part D prospective protocol key {key!r} must equal {value!r}")
    _validate_https_cms_url(prospective["catalog_url"], label="CMS dataset catalogue URL")
    return partd, prospective


def _load_limits(protocol: dict[str, Any], limits: Mapping[str, int] | None) -> dict[str, int]:
    values = protocol.get("limits")
    if not isinstance(values, dict) or set(values) != set(common.DEFAULT_LIMITS):
        raise ValueError("Q2 prospective execution requires the complete locked protocol limits")
    resolved = {key: int(value) for key, value in values.items()}
    if limits is not None:
        unknown = set(limits) - set(resolved)
        if unknown:
            raise ValueError(f"unrecognized Q2 limits: {sorted(unknown)}")
        resolved.update({key: int(value) for key, value in limits.items()})
    return resolved


def _read_capture_phase_result(phase_dir: Path) -> dict[str, Any]:
    return _phase_result(phase_dir)


def _catalog_gate(
    budget: common.RunBudget, url: str, phase_dir: Path, run_root: Path
) -> dict[str, Any]:
    phase_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        budget.execute(_capture_catalog, (url,), phase_dir)
        capture = _phase_result(phase_dir)
        capture["response_path"] = str(
            (phase_dir / capture["response_file"]).relative_to(run_root)
        )
        if capture.get("service_2025_officially_listed") is not False:
            raise ValueError("service year 2025 appeared before forecast sealing")
        return capture
    except BaseException as exc:
        _write_json(
            run_root / "forecast.json",
            {
                "record_kind": FORECAST_RECORD_KIND,
                "status": "catalog_sealing_gate_failed",
                "target_year": TARGET_YEAR,
                "prospective_claim_permitted": False,
                "gate_phase": str(phase_dir),
                "error_type": type(exc).__name__,
                "gate_reason": str(exc),
                "resources": {"phases": budget.phases},
            },
        )
        raise


def run_forecast(
    source_root: Path,
    comparison_dir: Path,
    output_dir: Path,
    protocol: Path,
    sha256: str,
    limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Capture public history, seal a 2025 forecast, and never inspect 2025 outcomes."""
    source_root = Path(source_root).resolve(strict=True)
    comparison_dir = Path(comparison_dir).resolve(strict=True)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to reuse Q2 prospective output directory: {output_dir}")
    protocol_data = common.load_protocol(Path(protocol), sha256, output_dir)
    partd_protocol, prospective = _read_locked_protocol_config(protocol_data)
    required_locked_sources = {
        "healthgraphbench/q2/prospective_partd.py",
        "scripts/run_q2_prospective_partd.py",
        "healthgraphbench/q2/partd.py",
        "healthgraphbench/q2/common.py",
        "healthgraphbench/candidates/partd.py",
        "healthgraphbench/candidates/partd_model.py",
        "healthgraphbench/tasks/partd/task.py",
        prospective["source_manifest"],
        prospective["development_population"],
    }
    missing_locked_sources = required_locked_sources.difference(protocol_data["locked_sources"])
    if missing_locked_sources:
        raise ValueError(
            f"Q2 prospective execution source lock is missing {sorted(missing_locked_sources)}"
        )
    manifest_path = Path(prospective["source_manifest"])
    if not manifest_path.is_absolute():
        manifest_path = common.REPO_ROOT / manifest_path
    manifest_path = manifest_path.resolve(strict=True)
    if prospective["source_manifest"] not in protocol_data["locked_sources"]:
        raise ValueError("prospective source manifest must be a locked scientific source")
    manifest, entries = _validate_manifest(manifest_path, source_root)
    if [int(entry["year"]) for entry in entries] != list(PRIOR_YEARS):
        raise ValueError("prospective forecast requires exactly the six locked 2019-2024 source URLs")

    comparison_prepared = comparison_dir / prospective["comparison_prepared_relative"]
    development_population = common.REPO_ROOT / prospective["development_population"]
    resolved_limits = _load_limits(protocol_data, limits)
    budget = common.RunBudget(output_dir, resolved_limits)


    catalog_result: dict[str, Any] | None = None
    capture_errors: list[dict[str, Any]] = []
    catalog_phase = output_dir / "phases" / "capture_catalog"
    catalog_phase.parent.mkdir(parents=True, exist_ok=True)
    try:
        budget.execute(_capture_catalog, (prospective["catalog_url"],), catalog_phase)
        catalog_result = _read_capture_phase_result(catalog_phase)
        catalog_result["response_path"] = str(
            (catalog_phase / catalog_result["response_file"]).relative_to(output_dir)
        )
    except Exception as exc:
        capture_errors.append(
            {
                "phase": "catalog",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "phase_directory": str(catalog_phase),
                "worker_error_path": str(catalog_phase / "worker_error.json"),
            }
        )

    if catalog_result is None:
        result = {
            "record_kind": FORECAST_RECORD_KIND,
            "status": "capture_failed",
            "task": "partd_prescriber_drug",
            "target_year": TARGET_YEAR,
            "prospective_claim_permitted": False,
            "gate_reason": "official catalogue capture failed; no source capture or forecast was attempted",
            "catalog_capture": None,
            "successful_source_captures": [],
            "capture_errors": capture_errors,
            "limits": budget.limits,
            "resources": {"phases": budget.phases},
        }
        _write_json(output_dir / "forecast.json", result)
        return result
    if catalog_result.get("service_2025_officially_listed") is True:
        result = {
            "record_kind": FORECAST_RECORD_KIND,
            "status": "gate_service_2025_already_officially_listed",
            "task": "partd_prescriber_drug",
            "target_year": TARGET_YEAR,
            "prospective_claim_permitted": False,
            "gate_reason": "service year 2025 was already listed by the official CMS dataset catalogue at capture time",
            "catalog_capture": catalog_result,
            "successful_source_captures": [],
            "limits": budget.limits,
            "resources": {"phases": budget.phases},
        }
        _write_json(output_dir / "gate.json", result)
        _write_json(output_dir / "forecast.json", result)
        return result
    source_results: list[dict[str, Any]] = []
    for entry in entries:
        phase_dir = output_dir / "phases" / "capture_sources" / f"service-year-{int(entry['year'])}"
        phase_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            budget.execute(_capture_source, (source_root, entry), phase_dir)
            capture_record = _read_capture_phase_result(phase_dir)
            capture_record["capture_metadata_path"] = str(
                (phase_dir / "capture_attempt.json").relative_to(output_dir)
            )
            capture_record["capture_metadata_sha256"] = sha256_file(
                phase_dir / "capture_attempt.json"
            )
            source_results.append(capture_record)
        except Exception as exc:
            capture_errors.append(
                {
                    "phase": "source_capture",
                    "year": int(entry["year"]),
                    "path": entry["path"],
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "phase_directory": str(phase_dir),
                    "worker_error_path": str(phase_dir / "worker_error.json"),
                    "capture_attempt_path": str(phase_dir / "capture_attempt.json"),
                }
            )
    if capture_errors:
        result = {
            "record_kind": FORECAST_RECORD_KIND,
            "status": "capture_failed",
            "task": "partd_prescriber_drug",
            "target_year": TARGET_YEAR,
            "prospective_claim_permitted": False,
            "gate_reason": "one or more exact public source captures failed; no forecast was prepared",
            "catalog_capture": catalog_result,
            "successful_source_captures": source_results,
            "capture_errors": capture_errors,
            "limits": budget.limits,
            "resources": {"phases": budget.phases},
        }
        _write_json(output_dir / "forecast.json", result)
        return result
    catalog_result = _catalog_gate(
        budget, prospective["catalog_url"],
        output_dir / "phases" / "catalog_after_source_captures", output_dir,
    )
    origin_sealed_at_utc = _utc_now()
    selection_path = comparison_dir / "selection.json"
    try:
        selection_bytes = selection_path.read_bytes()
        selection_sha256 = hashlib.sha256(selection_bytes).hexdigest()
        selected = _load_selection(selection_bytes, partd_protocol)
    except (OSError, ValueError) as exc:
        result = {
            "record_kind": FORECAST_RECORD_KIND,
            "status": "preparation_gate_failed",
            "target_year": TARGET_YEAR,
            "gate_reason": str(exc),
            "catalog_capture": catalog_result,
            "successful_source_captures": source_results,
            "limits": budget.limits,
            "resources": {"phases": budget.phases},
        }
        _write_json(output_dir / "forecast.json", result)
        raise
    selection_copy = output_dir / "selection.json"
    selection_copy.write_bytes(selection_bytes)
    sealed_origin_dir = output_dir / "sealed_origin"
    prepare_phase = output_dir / "phases" / "prepare_origin"
    prepare_phase.parent.mkdir(parents=True, exist_ok=True)
    budget.execute(
        _prepare_origin_worker,
        (
            source_root,
            manifest_path,
            development_population,
            comparison_prepared,
            sealed_origin_dir,
            source_results,
            catalog_result,
            selection_sha256,
            sha256,
            selection_bytes,
            selected,
            prospective["cohort_salt"],
            int(prospective["cohort_size"]),
            output_dir,
            origin_sealed_at_utc,
        ),
        prepare_phase,
    )
    preparation = _phase_result(prepare_phase)
    origin_dir = Path(preparation["origin_dir"])
    origin_report_sha256 = sha256_file(origin_dir / "origin.json")
    if origin_report_sha256 != preparation.get("origin_sha256"):
        raise ValueError("sealed origin report hash changed after preparation")
    training_rows = int(preparation["training_rows"])
    boosted_seeds = list(Q2_SEEDS) if training_rows > 200_000 else [None]
    fits: dict[str, list[dict[str, Any]]] = {}
    schedules = (
        ("specialty_popularity", None, None, [None]),
        ("history_overlap", None, None, [None]),
        ("logistic", selected["logistic"]["configuration"], selected["logistic"]["configuration_index"], [None]),
        ("boosted", selected["boosted"]["configuration"], selected["boosted"]["configuration_index"], boosted_seeds),
        ("bpr", selected["bpr"]["configuration"], selected["bpr"]["configuration_index"], list(Q2_SEEDS)),
    )
    for family, configuration, configuration_index, seeds in schedules:
        family_runs: list[dict[str, Any]] = []
        for seed in seeds:
            seed_label = f"seed-{seed}" if seed is not None else "deterministic"
            phase_dir = output_dir / "phases" / "forecast_fits" / family / seed_label
            phase_dir.parent.mkdir(parents=True, exist_ok=True)
            supervisor = budget.execute(
                _score_forecast_worker,
                (origin_dir, family, configuration, configuration_index, seed, partd_protocol["fixed"]),
                phase_dir,
            )
            fit_result = _phase_result(phase_dir)
            fit_summary = fit_result.get("fit")
            if isinstance(fit_summary, dict) and isinstance(fit_summary.get("checkpoint"), str):
                checkpoint_path = Path(fit_summary["checkpoint"])
                if not checkpoint_path.is_absolute():
                    checkpoint_path = Path.cwd() / checkpoint_path
                checkpoint_path = checkpoint_path.resolve(strict=True)
                fit_summary["checkpoint"] = checkpoint_path.relative_to(
                    output_dir.resolve(strict=True)
                ).as_posix()
            fit_result["candidate_scores_path"] = str(
                (phase_dir / fit_result["candidate_scores_file"]).relative_to(output_dir)
            )
            fit_result["prediction_path"] = str(
                (phase_dir / fit_result["prediction_file"]).relative_to(output_dir)
            )
            fit_result["supervision"] = supervisor
            family_runs.append(fit_result)
        fits[family] = family_runs
    seal_catalog = _catalog_gate(
        budget, prospective["catalog_url"],
        output_dir / "phases" / "catalog_before_forecast_seal", output_dir,
    )
    result = {
        "record_kind": FORECAST_RECORD_KIND,
        "status": "sealed_awaiting_official_target_publication",
        "task": "partd_prescriber_drug",
        "target_year": TARGET_YEAR,
        "origin_dir": str(origin_dir.resolve()),
        "origin_sha256": origin_report_sha256,
        "origin_sealed_at_utc": _json_object(origin_dir / "origin.json", "prospective Part D origin")["origin_sealed_at_utc"],
        "forecast_sealed_at_utc": _utc_now(),
        "seal_catalog_capture": seal_catalog,
        "availability_claim": prospective["availability_claim"],
        "human_nonconsultation_gate": "unknown; external human attestation required",
        "official_target_publication_found_at_origin": False,
        "independent_evaluation": {
            "status": "awaiting_official_target_publication",
            "passed": False,
            "target_metrics_computed": False,
        },
        "protocol_path": str(Path(protocol).resolve()),
        "protocol_sha256": sha256,
        "selection_path": str(selection_copy),
        "selection_sha256": selection_sha256,
        "selected_configurations": selected,
        "fixed_settings": partd_protocol["fixed"],
        "training_rows_for_boosted_seed_policy": training_rows,
        "boosted_seeds": [seed for seed in boosted_seeds if seed is not None],
        "fits": fits,
        "limits": budget.limits,
        "resources": {
            "run_wall_seconds": time.monotonic() - budget.started,
            "phases": budget.phases,
        },
    }
    output_bytes = common.diagnostic._directory_bytes(output_dir)
    result["resources"]["output_bytes_before_final_report"] = output_bytes
    if output_bytes > int(budget.limits["total_output_bytes"]):
        result["status"] = "resource_budget_exceeded"
        result["independent_evaluation"]["status"] = "not_sealed_due_to_output_budget"
    _write_json(output_dir / "forecast.json", result)
    return result


def _read_target_manifest(
    target_source: Path, target_manifest: Path
) -> tuple[dict[str, Any], dict[str, Any], Path, Path, str]:
    target_source = Path(target_source).resolve(strict=True)
    target_manifest = Path(target_manifest).resolve(strict=True)
    manifest = _json_object(target_manifest, "official 2025 Part D target manifest")
    if manifest.get("version") != "0.2-candidate" or manifest.get("dataset") != "partd_prescriber_drug":
        raise ValueError("official target manifest is not a supported Part D source manifest")
    _validate_https_cms_url(manifest.get("landing_url"), label="official Part D target landing URL")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("official target manifest has no files")
    matching = [
        item
        for item in files
        if isinstance(item, dict)
        and not isinstance(item.get("year"), bool)
        and item.get("year") == TARGET_YEAR
    ]
    if len(matching) != 1:
        raise ValueError("official target manifest must identify exactly one service-year 2025 file")
    entry = dict(matching[0])
    required = (
        "year",
        "path",
        "url",
        "dataset_id",
        "bytes",
        "sha256",
        "header",
        "retrieved_at",
        "historical_published_at",
    )
    for key in required:
        if key not in entry:
            raise ValueError(f"official target manifest entry is missing {key!r}")
    if entry["year"] != TARGET_YEAR:
        raise ValueError("official target entry is not service year 2025")
    if not isinstance(entry["path"], str) or not entry["path"]:
        raise ValueError("official target manifest file path is invalid")
    _validate_https_cms_url(entry["url"], label="official 2025 target source URL")
    if not isinstance(entry["dataset_id"], str) or not entry["dataset_id"]:
        raise ValueError("official target manifest dataset identifier is invalid")
    if entry["historical_published_at"] is not None:
        raise ValueError("target manifest historical publication date is not verified; keep it null")
    header = entry["header"]
    if (
        not isinstance(header, list)
        or any(not isinstance(column, str) for column in header)
        or len(set(header)) != len(header)
        or any(column not in header for column in REQUIRED_COLUMNS)
    ):
        raise ValueError("official 2025 target manifest header is invalid or missing required Part D fields")
    byte_count = entry["bytes"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count <= 0:
        raise ValueError("official 2025 target manifest byte count is invalid")
    expected_sha256 = entry["sha256"]
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("official 2025 target manifest SHA-256 is invalid")
    if not isinstance(entry["retrieved_at"], str) or not entry["retrieved_at"]:
        raise ValueError("official target manifest retrieval timestamp is missing")
    target_path = _safe_source_path(target_source, entry["path"]).resolve(strict=True)
    target_path.relative_to(target_source)
    actual_size = target_path.stat().st_size
    actual_sha256 = sha256_file(target_path)
    if actual_size != byte_count or actual_sha256.lower() != expected_sha256.lower():
        raise ValueError(
            f"official 2025 target source hash/size mismatch: expected {byte_count}/{expected_sha256}, got {actual_size}/{actual_sha256}"
        )
    return manifest, entry, target_source, target_path, sha256_file(target_manifest)


def _safe_run_artifact(run_root: Path, relative_path: object) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("forecast artifact path is missing")
    path = (Path(run_root) / relative_path).resolve(strict=True)
    try:
        path.relative_to(Path(run_root).resolve(strict=True))
    except ValueError as exc:
        raise ValueError(f"forecast artifact escapes run output directory: {relative_path!r}") from exc
    return path


def _prediction_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid forecast prediction row {line_number}: {exc}") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"forecast prediction row {line_number} is not an object")
                records.append(value)
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"unable to read sealed predictions: {exc}") from exc
    return records


def _sealed_runs(
    run_root: Path,
    forecast: dict[str, Any],
    origin: TrainingOrigin,
    origin_dir: Path,
    layout: dict[str, Any],
) -> list[dict[str, Any]]:
    fits = forecast.get("fits")
    if not isinstance(fits, dict):
        raise ValueError("forecast is missing saved model score tables")
    expected_families = {"specialty_popularity", "history_overlap", "logistic", "boosted", "bpr"}
    if set(fits) != expected_families:
        raise ValueError("forecast family set differs from the locked five-family comparison")
    selected = forecast.get("selected_configurations")
    training_rows = forecast.get("training_rows_for_boosted_seed_policy")
    if (
        not isinstance(selected, dict)
        or set(selected) != {"logistic", "boosted", "bpr"}
        or isinstance(training_rows, bool)
        or not isinstance(training_rows, int)
        or training_rows < 0
    ):
        raise ValueError("forecast is missing locked selected configurations or HGB seed-policy count")
    for family in ("logistic", "boosted", "bpr"):
        if not isinstance(selected[family], dict):
            raise ValueError(f"forecast selected {family} configuration is malformed")
    boosted_seeds: list[int | None] = list(Q2_SEEDS) if training_rows > 200_000 else [None]
    if forecast.get("boosted_seeds") != [seed for seed in boosted_seeds if seed is not None]:
        raise ValueError("forecast HGB repetitions differ from the locked training-row seed rule")
    expected_runs = {
        "specialty_popularity": ([None], None, None),
        "history_overlap": ([None], None, None),
        "logistic": (
            [None],
            selected["logistic"]["configuration"],
            selected["logistic"]["configuration_index"],
        ),
        "boosted": (
            boosted_seeds,
            selected["boosted"]["configuration"],
            selected["boosted"]["configuration_index"],
        ),
        "bpr": (
            list(Q2_SEEDS),
            selected["bpr"]["configuration"],
            selected["bpr"]["configuration_index"],
        ),
    }
    history, _, cohort = origin._target_history(TARGET_YEAR)
    drug_ids = layout["drug_ids"]
    providers = layout["provider_ids"]
    offsets = layout["provider_candidate_offsets"]
    candidate_indices = layout["candidate_drug_indices"]
    candidate_layout_sha256 = sha256_file(Path(origin_dir) / "candidate_layout.npz")
    runs: list[dict[str, Any]] = []
    for family in sorted(fits):
        family_runs = fits[family]
        expected_seeds, expected_configuration, expected_index = expected_runs[family]
        if not isinstance(family_runs, list) or len(family_runs) != len(expected_seeds):
            raise ValueError(f"forecast run count differs from locked seed policy for {family}")
        for expected_seed, item in zip(expected_seeds, family_runs, strict=True):
            if not isinstance(item, dict):
                raise ValueError(f"forecast run record for {family} is malformed")
            if (
                item.get("family") != family
                or item.get("seed") != expected_seed
                or item.get("configuration") != expected_configuration
                or item.get("configuration_index") != expected_index
            ):
                raise ValueError(f"forecast run configuration or seed differs from locked policy for {family}")
            if item.get("candidate_score_count") != len(candidate_indices):
                raise ValueError(f"forecast score count does not cover all candidates for {family}")
            if item.get("candidate_layout_sha256") != candidate_layout_sha256:
                raise ValueError(f"forecast candidate layout reference mismatch for {family}")
            if family in {"logistic", "boosted", "bpr"}:
                fit_summary = item.get("fit")
                if not isinstance(fit_summary, dict) or not isinstance(fit_summary.get("checkpoint"), str):
                    raise ValueError(f"forecast {family} run is missing its fitted weight checkpoint")
                checkpoint_path = _safe_run_artifact(run_root, fit_summary["checkpoint"])
                if sha256_file(checkpoint_path) != fit_summary.get("checkpoint_sha256"):
                    raise ValueError(f"forecast {family} fitted checkpoint hash mismatch")

            score_path = _safe_run_artifact(run_root, item.get("candidate_scores_path"))
            prediction_path = _safe_run_artifact(run_root, item.get("prediction_path"))
            if sha256_file(score_path) != item.get("candidate_scores_sha256"):
                raise ValueError(f"forecast candidate score hash mismatch for {family}")
            if sha256_file(prediction_path) != item.get("prediction_file_sha256"):
                raise ValueError(f"forecast prediction file hash mismatch for {family}")
            try:
                with np.load(score_path, allow_pickle=False) as loaded:
                    if set(loaded.files) != {"candidate_scores"}:
                        raise ValueError("score table has unexpected arrays")
                    scores = loaded["candidate_scores"]
            except (OSError, ValueError) as exc:
                raise ValueError(f"unable to load sealed candidate scores for {family}: {exc}") from exc
            if scores.shape != (len(candidate_indices),) or not np.all(np.isfinite(scores)):
                raise ValueError(f"sealed candidate score vector is malformed for {family}")
            predictions = _prediction_records(prediction_path)
            if len(predictions) != len(cohort):
                raise ValueError(f"sealed forecast has incomplete provider predictions for {family}")
            for provider_index, (npi_value, record) in enumerate(zip(providers, predictions, strict=True)):
                npi = str(npi_value)
                if record.get("npi") != npi or record.get("target_year") != TARGET_YEAR:
                    raise ValueError(f"sealed prediction identity/year mismatch for {family}, provider {npi}")
                if record.get("eligible") is not bool(history.provider_drugs.get(npi)):
                    raise ValueError(f"sealed prediction eligibility differs for {family}, provider {npi}")
                start = int(offsets[provider_index])
                end = int(offsets[provider_index + 1])
                candidate_ids = [str(drug_ids[index]) for index in candidate_indices[start:end]]
                if record.get("candidate_count") != len(candidate_ids):
                    raise ValueError(f"sealed candidate count differs for {family}, provider {npi}")
                row_scores = {
                    drug: float(scores[index])
                    for drug, index in zip(candidate_ids, range(start, end), strict=True)
                }
                recommended = heapq.nsmallest(
                    TOP_KS[-1],
                    candidate_ids,
                    key=lambda drug: (-row_scores[drug], -_global_support(history, drug), drug),
                )
                expected_recommendations = [
                    {"drug": drug, "rank": rank, "score": row_scores[drug]}
                    for rank, drug in enumerate(recommended, start=1)
                ]
                if record.get("recommendations") != expected_recommendations:
                    raise ValueError(
                        f"sealed recommendations do not reproduce from scores for {family}, provider {npi}"
                    )
            runs.append({"family": family, "record": item, "path": str(score_path)})
    return runs


def _verify_run_lock(
    run_root: Path, forecast: dict[str, Any], origin_report: dict[str, Any]
) -> dict[str, Any]:
    protocol_path = Path(run_root) / "protocol_executed.json"
    provenance_path = Path(run_root) / "source_provenance.json"
    protocol_bytes = protocol_path.read_bytes()
    protocol_sha256 = hashlib.sha256(protocol_bytes).hexdigest()
    source_provenance = _json_object(provenance_path, "forecast source provenance")
    try:
        protocol = json.loads(protocol_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid executed forecast protocol: {exc}") from exc
    if (
        forecast.get("protocol_sha256") != protocol_sha256
        or origin_report.get("protocol_sha256") != protocol_sha256
        or source_provenance.get("protocol_sha256") != protocol_sha256
    ):
        raise ValueError("forecast, origin, and executed protocol hashes do not agree")
    if not isinstance(protocol, dict) or not isinstance(protocol.get("locked_sources"), list):
        raise ValueError("executed forecast protocol has no locked source list")
    tasks = protocol.get("tasks")
    partd = tasks.get("partd") if isinstance(tasks, dict) else None
    if not isinstance(partd, dict) or forecast.get("fixed_settings") != partd.get("fixed"):
        raise ValueError("forecast fixed model settings differ from the executed protocol")
    source_hashes = source_provenance.get("source_sha256")
    if not isinstance(source_hashes, dict):
        raise ValueError("forecast source provenance is missing locked source hashes")
    manifest_relative = Path(origin_report["source_manifest"]).resolve(strict=True).relative_to(
        common.REPO_ROOT
    ).as_posix()
    development = origin_report.get("development_population")
    if not isinstance(development, dict):
        raise ValueError("forecast development exclusion provenance is missing")
    development_relative = Path(development["path"]).resolve(strict=True).relative_to(
        common.REPO_ROOT
    ).as_posix()
    required = {
        "healthgraphbench/q2/prospective_partd.py",
        "scripts/run_q2_prospective_partd.py",
        "healthgraphbench/q2/partd.py",
        "healthgraphbench/q2/common.py",
        "healthgraphbench/candidates/partd.py",
        "healthgraphbench/candidates/partd_model.py",
        "healthgraphbench/tasks/partd/task.py",
        manifest_relative,
        development_relative,
    }
    if not required.issubset(protocol["locked_sources"]):
        raise ValueError("executed Q2 protocol did not lock every prospective implementation source")
    for name in required:
        expected_hash = source_hashes.get(name)
        current_path = common.REPO_ROOT / name
        if not isinstance(expected_hash, str) or sha256_file(current_path) != expected_hash:
            raise ValueError(f"prospective evaluation code/source differs from forecast-locked source {name}")
    if (
        source_hashes.get(manifest_relative) != origin_report.get("source_manifest_sha256")
        or source_hashes.get(development_relative) != development.get("sha256")
    ):
        raise ValueError("origin source manifests differ from protocol-locked source hashes")
    source_files = origin_report.get("source_files")
    if not isinstance(source_files, list):
        raise ValueError("forecast origin has no captured source metadata")
    for capture in source_files:
        if not isinstance(capture, dict):
            raise ValueError("forecast source capture record is malformed")
        metadata_path = _safe_run_artifact(run_root, capture.get("capture_metadata_path"))
        if sha256_file(metadata_path) != capture.get("capture_metadata_sha256"):
            raise ValueError("forecast source capture metadata hash mismatch")
        metadata = _json_object(metadata_path, "verified public source capture metadata")
        for key in (
            "year",
            "url",
            "request_authentication",
            "capture_started_at_utc",
            "capture_completed_at_utc",
            "received_bytes",
            "sha256",
            "manifest_sha256",
            "byte_for_byte_equal_to_retained_local",
        ):
            if metadata.get(key) != capture.get(key):
                raise ValueError(f"forecast source capture metadata differs for field {key}")
        if capture.get("request_authentication") != "none":
            raise ValueError("forecast source capture was not unauthenticated")
        _validate_https_cms_url(capture.get("url"), label="captured historical Part D source URL")
    catalog_capture = origin_report.get("catalog_capture")
    if not isinstance(catalog_capture, dict) or catalog_capture.get("service_2025_officially_listed") is not False:
        raise ValueError("forecast origin lacks a negative official service-year 2025 catalogue check")
    if catalog_capture.get("request_authentication") != "none":
        raise ValueError("official CMS catalogue capture was not unauthenticated")
    prospective = partd.get("prospective")
    if not isinstance(prospective, dict) or catalog_capture.get("url") != prospective.get("catalog_url"):
        raise ValueError("official CMS catalogue capture URL differs from the executed protocol")
    _validate_https_cms_url(catalog_capture.get("url"), label="captured CMS dataset catalogue URL")
    catalog_path = _safe_run_artifact(run_root, catalog_capture.get("response_path"))
    catalog_sha256 = sha256_file(catalog_path)
    if (
        catalog_sha256 != catalog_capture.get("response_file_sha256")
        or catalog_sha256 != catalog_capture.get("response_sha256")
        or catalog_path.stat().st_size != catalog_capture.get("response_bytes")
    ):
        raise ValueError("forecast official catalogue capture hash or size mismatch")
    seal_catalog = forecast.get("seal_catalog_capture")
    if not isinstance(seal_catalog, dict):
        raise ValueError("forecast lacks its post-fit catalogue capture")
    for capture in (catalog_capture, seal_catalog):
        if (
            capture.get("url") != prospective.get("catalog_url")
            or capture.get("request_authentication") != "none"
            or capture.get("service_2025_officially_listed") is not False
        ):
            raise ValueError("forecast catalogue sealing gate is not negative and authenticated-free")
        response_path = _safe_run_artifact(run_root, capture.get("response_path"))
        digest = sha256_file(response_path)
        if (
            digest != capture.get("response_sha256")
            or digest != capture.get("response_file_sha256")
            or response_path.stat().st_size != capture.get("response_bytes")
            or _catalog_2025_nodes(_json_object(response_path, "sealed CMS catalogue"))
        ):
            raise ValueError("forecast sealing catalogue bytes or target-year gate differ")
    origin_time = datetime.fromisoformat(origin_report["origin_sealed_at_utc"].replace("Z", "+00:00"))
    catalogue_time = datetime.fromisoformat(catalog_capture["captured_at_utc"].replace("Z", "+00:00"))
    final_start = datetime.fromisoformat(seal_catalog["request_started_at_utc"].replace("Z", "+00:00"))
    final_time = datetime.fromisoformat(seal_catalog["captured_at_utc"].replace("Z", "+00:00"))
    seal_time = datetime.fromisoformat(forecast["forecast_sealed_at_utc"].replace("Z", "+00:00"))
    if not catalogue_time <= origin_time <= final_start <= final_time <= seal_time:
        raise ValueError("forecast sealing catalogue chronology is inconsistent")
    for capture in source_files:
        completed = datetime.fromisoformat(capture["capture_completed_at_utc"].replace("Z", "+00:00"))
        if completed > catalogue_time:
            raise ValueError("historical source capture completed after the origin catalogue gate")
    return {
        "protocol_sha256": protocol_sha256,
        "code_commit": source_provenance.get("code_commit"),
        "locked_source_sha256": source_hashes,
    }




def _evaluate_target_worker(
    origin_dir: Path,
    target_source: Path,
    target_manifest: Path,
    run_root: Path,
    phase_dir: Path,
) -> dict[str, Any]:
    origin_dir = Path(origin_dir).resolve(strict=True)
    run_root = Path(run_root).resolve(strict=True)
    origin_report, origin, _ = _read_history_origin(origin_dir)
    forecast_path = run_root / "forecast.json"
    forecast = _json_object(forecast_path, "sealed prospective forecast")
    if forecast.get("record_kind") != FORECAST_RECORD_KIND or forecast.get("status") != "sealed_awaiting_official_target_publication":
        raise ValueError("target evaluation requires an intact sealed forecast, not a gate or failed run")
    if forecast.get("origin_dir") != str(origin_dir) or forecast.get("origin_sha256") != sha256_file(origin_dir / "origin.json"):
        raise ValueError("forecast does not reference this exact sealed origin")
    if (
        forecast.get("target_year") != TARGET_YEAR
        or forecast.get("official_target_publication_found_at_origin") is not False
        or origin_report.get("official_target_publication_found_at_origin") is not False
    ):
        raise ValueError("forecast origin is not eligible for a 2025 delayed evaluation")
    availability_claim = "verified_public_recapture_before_prediction; not_first_publication_or_first_prescription"
    if forecast.get("availability_claim") != availability_claim or origin_report.get("availability_claim") != availability_claim:
        raise ValueError("forecast does not preserve the conservative public-recapture availability claim")
    if (
        forecast.get("human_nonconsultation_gate") != "unknown; external human attestation required"
        or origin_report.get("human_nonconsultation_gate")
        != "unknown; requires external human attestation; no assistant claim"
    ):
        raise ValueError("forecast incorrectly resolves the external human non-consultation gate")
    run_provenance = _verify_run_lock(run_root, forecast, origin_report)
    preparation = origin_report.get("preparation")
    if (
        not isinstance(preparation, dict)
        or forecast.get("training_rows_for_boosted_seed_policy")
        != preparation.get("training_rows_for_seed_policy")
    ):
        raise ValueError("forecast HGB seed-policy count differs from sealed origin preparation")
    selection_record = origin_report.get("comparison_selection")
    if (
        not isinstance(selection_record, dict)
        or forecast.get("selection_sha256") != selection_record.get("sha256")
        or sha256_file(origin_dir / "selection.json") != selection_record.get("sha256")
    ):
        raise ValueError("forecast does not reference the exact sealed selection.json")
    selection = _json_object(origin_dir / "selection.json", "sealed Part D comparison selection")
    forecast_selected = forecast.get("selected_configurations")
    if not isinstance(forecast_selected, dict) or not isinstance(selection.get("families"), dict):
        raise ValueError("forecast selected configurations are malformed")
    if (
        selection.get("validation_year") != 2023
        or selection.get("test_year") != 2024
        or selection.get("seeds_are_not_selected") is not True
    ):
        raise ValueError("sealed selection is not the locked Part D 2023 validation selection")
    if selection_record.get("selected_configurations") != forecast_selected:
        raise ValueError("origin and forecast selected-configuration records differ")
    for family in ("logistic", "boosted", "bpr"):
        selected_row = selection["families"].get(family)
        forecast_row = forecast_selected.get(family)
        if not isinstance(selected_row, dict) or not isinstance(forecast_row, dict):
            raise ValueError(f"forecast/selection is missing chosen {family} configuration")
        if (
            selected_row.get("configuration_index") != forecast_row.get("configuration_index")
            or selected_row.get("configuration") != forecast_row.get("configuration")
        ):
            raise ValueError(f"forecast {family} configuration differs from sealed selection.json")
    layout = _read_candidate_layout(origin_dir, origin)
    sealed_runs = _sealed_runs(run_root, forecast, origin, origin_dir, layout)
    _, target_entry, target_root, target_path, target_manifest_sha256 = _read_target_manifest(
        Path(target_source), Path(target_manifest)
    )
    target_catalog_dir = phase_dir / "target_catalog"
    target_catalog_dir.mkdir()
    executed = _json_object(run_root / "protocol_executed.json", "forecast protocol")
    target_catalog = _capture_catalog(
        executed["tasks"]["partd"]["prospective"]["catalog_url"], target_catalog_dir
    )
    document = _json_object(target_catalog_dir / "catalog_response.json", "target CMS catalogue")
    matching = {node["dataset_id"] for node in _catalog_2025_nodes(document)}
    if target_entry["dataset_id"] not in matching:
        raise ValueError("target dataset_id is not an official service-year 2025 catalogue node")
    node = next(item for item in document["data"] if item.get("id") == target_entry["dataset_id"])
    media_id = node["relationships"]["field_ref_primary_data_file"]["data"]["id"]
    media = next(item for item in document["included"] if item.get("id") == media_id)
    csv_metadata = json.loads(media["attributes"]["field_csv_metadata"])
    target_capture_dir = phase_dir / "target_source_capture"
    target_capture_dir.mkdir()
    target_capture = _capture_source(target_root, target_entry, target_capture_dir)
    if (
        target_capture["sha1"] != csv_metadata.get("csvFileSHA1")
        or target_capture["received_bytes"] != csv_metadata.get("csvFileSize")
    ):
        raise ValueError("target CSV bytes do not match official 2025 primary-file metadata")
    target_rows = _iter_selected_rows(target_path, target_entry, origin.cohort)
    input_rows = {
        TARGET_YEAR: [
            _InputEdge(TARGET_YEAR, row.npi, row.brand_name, row.generic_name, row.claims, row.specialty)
            for row in target_rows
        ]
    }
    projected_target, projection = _project_rows(input_rows, "generic")
    targets_by_provider: dict[str, set[str]] = defaultdict(set)
    for row in projected_target[TARGET_YEAR]:
        targets_by_provider[row.npi].add(row.drug)
    history, _, cohort = origin._target_history(TARGET_YEAR)
    metrics_by_run: list[dict[str, Any]] = []
    providers = layout["provider_ids"]
    drug_ids = layout["drug_ids"]
    offsets = layout["provider_candidate_offsets"]
    indices = layout["candidate_drug_indices"]
    for sealed_run in sealed_runs:
        item = sealed_run["record"]
        family = sealed_run["family"]
        with np.load(sealed_run["path"], allow_pickle=False) as loaded:
            scores = loaded["candidate_scores"]
        accumulator = _EvaluationAccumulator()
        for provider_index, raw_npi in enumerate(providers):
            npi = str(raw_npi)
            start = int(offsets[provider_index])
            end = int(offsets[provider_index + 1])
            candidate_ids = [str(drug_ids[index]) for index in indices[start:end]]
            candidate_set = set(candidate_ids)
            own_history = history.provider_drugs.get(npi, set())
            positives = {
                drug
                for drug in targets_by_provider.get(npi, set())
                if drug not in own_history and drug in history.drug_providers
            }
            row_scores = {drug: float(scores[index]) for drug, index in zip(candidate_ids, range(start, end), strict=True)}
            ranks = _positive_ranks(candidate_set, positives, row_scores, history)
            recommendations = _top_recommendations(candidate_set, row_scores, history)
            accumulator.add(
                npi,
                eligible=bool(own_history),
                candidate_count=len(candidate_ids),
                positives=positives,
                positive_ranks=ranks.values(),
                recommendations=[drug for drug, _ in recommendations],
                recommendation_scores=[score for _, score in recommendations],
                high_confidence_threshold=None,
            )
        metric_result = accumulator.as_dict()
        for name in tuple(metric_result["all_provider_years"]):
            if "high_confidence" in name:
                del metric_result["all_provider_years"][name]
        metrics_by_run.append(
            {
                "family": family,
                "configuration_index": item.get("configuration_index"),
                "configuration": item.get("configuration"),
                "seed": item.get("seed"),
                "metrics": metric_result,
                "target_provider_years": len(cohort),
                "candidate_denominator": "all exact prior-history generic candidates for each eligible provider-year; no sampling",
                "positive_denominator": "all target-year new-to-provider generic relationships present in the strictly prior global drug vocabulary",
                "scores_reused_without_refit_or_tuning": True,
            }
        )
    target_source_record = {
        "target_source_root": str(target_root),
        "target_manifest_path": str(Path(target_manifest).resolve()),
        "target_manifest_sha256": target_manifest_sha256,
        "target_file_path": str(target_path),
        "target_file_url": target_entry["url"],
        "target_file_bytes": target_path.stat().st_size,
        "target_file_sha256": sha256_file(target_path),
        "target_year": int(target_entry["year"]),
        "target_dataset_id": target_entry["dataset_id"],
        "target_retrieved_at": target_entry["retrieved_at"],
        "manifest_recorded_at_is_not_claimed_as_first_public_availability": True,
        "target_rows_for_cohort": len(target_rows),
        "generic_projection": projection,
        "captured_at_utc": _utc_now(),
        "public_capture": target_capture,
        "official_catalog_capture": target_catalog,
        "official_primary_file_media_id": media_id,
        "official_csv_metadata_verified": True,
    }
    return {
        "target_source": target_source_record,
        "metrics_by_run": metrics_by_run,
        "run_provenance": run_provenance,
        "evaluation_policy": {
            "refit": False,
            "retuning": False,
            "seed_selection": False,
            "selection_source": "sealed comparison selection.json SHA-256",
            "cohort_and_candidates": "exact identities and candidate layout sealed at origin",
            "history": "exact generic 2019-2024 projected rows sealed at origin",
            "metric_implementation": "PartDTask._metrics conventions via _EvaluationAccumulator; TOP_KS=5,10,20",
        },
    }


def evaluate_forecast(
    origin_dir: Path,
    target_source: Path,
    target_manifest: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Evaluate a sealed forecast only after an official, hash-verified 2025 target exists."""
    origin_dir = Path(origin_dir).resolve(strict=True)
    target_source = Path(target_source).resolve(strict=True)
    target_manifest = Path(target_manifest).resolve(strict=True)
    origin_report = _json_object(origin_dir / "origin.json", "prospective Part D origin")
    run_root = Path(origin_report.get("run_output_dir", "")).resolve(strict=True)
    forecast = _json_object(run_root / "forecast.json", "sealed prospective forecast")
    if forecast.get("record_kind") != FORECAST_RECORD_KIND or forecast.get("status") != "sealed_awaiting_official_target_publication":
        raise ValueError("no sealed, prospectively eligible forecast is available for evaluation")
    if forecast.get("origin_dir") != str(origin_dir) or forecast.get("origin_sha256") != sha256_file(origin_dir / "origin.json"):
        raise ValueError("forecast/origin integrity check failed")
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to reuse Q2 prospective evaluation directory: {output_dir}")
    limits_value = forecast.get("limits")
    if not isinstance(limits_value, dict) or set(limits_value) != set(common.DEFAULT_LIMITS):
        raise ValueError("sealed forecast is missing its complete execution limits")
    budget = common.RunBudget(output_dir, {key: int(value) for key, value in limits_value.items()})
    phase_dir = output_dir / "phases" / "evaluate_target"
    phase_dir.parent.mkdir(parents=True, exist_ok=True)
    supervisor = budget.execute(
        _evaluate_target_worker,
        (origin_dir, target_source, target_manifest, run_root),
        phase_dir,
    )
    phase_result = _phase_result(phase_dir)
    evaluation = {
        "record_kind": EVALUATION_RECORD_KIND,
        "status": "evaluation_completed_human_nonconsultation_gate_unverified",
        "task": "partd_prescriber_drug",
        "target_year": TARGET_YEAR,
        "origin_dir": str(origin_dir),
        "origin_sha256": sha256_file(origin_dir / "origin.json"),
        "forecast_path": str(run_root / "forecast.json"),
        "forecast_sha256": sha256_file(run_root / "forecast.json"),
        "run_provenance": phase_result["run_provenance"],
        "human_nonconsultation_gate": "unknown; external human attestation remains required",
        "independent_evaluation_passed": False,
        "target_source": phase_result["target_source"],
        "evaluation_policy": phase_result["evaluation_policy"],
        "metrics_by_run": phase_result["metrics_by_run"],
        "limits": budget.limits,
        "resources": {"supervision": supervisor, "phases": budget.phases},
    }
    _write_json(output_dir / "source.json", evaluation["target_source"])
    _write_json(output_dir / "evaluation.json", evaluation)
    return evaluation
