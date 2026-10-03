"""CMS Medicare Part D prescriber-drug feasibility gate."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from healthgraphbench.data import sha256_file, verify_files

REQUIRED_COLUMNS: tuple[str, ...] = (
    "Prscrbr_NPI",
    "Brnd_Name",
    "Gnrc_Name",
    "Prscrbr_Type",
    "Prscrbr_State_Abrvtn",
    "Tot_Clms",
    "Tot_Drug_Cst",
)
EDGE_COLUMNS: tuple[str, ...] = (
    "npi",
    "brand_name",
    "generic_name",
    "year",
    "claims",
    "cost",
    "specialty",
    "state",
    "valid_from",
    "valid_to",
    "observed_at",
    "source_path",
    "source_row",
    "source_sha256",
    "transformation",
)
METHOD_NAMES: tuple[str, ...] = (
    "global_popularity",
    "specialty_popularity",
    "history_overlap",
)
TOP_KS: tuple[int, ...] = (5, 10, 20)
CLAIM_BANDS: tuple[str, ...] = ("11-20", "21-50", "51+")
TRANSFORMATION = "partd_provider_drug_edge_v1"
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

DrugKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class _PartDRow:
    npi: str
    brand_name: str
    generic_name: str
    year: int
    claims: int
    cost: str | None
    specialty: str
    state: str
    source_path: str
    source_row: int
    source_sha256: str
    observed_at: str

    @property
    def drug_key(self) -> DrugKey:
        return (self.brand_name, self.generic_name)


@dataclass(slots=True)
class _History:
    provider_drugs: dict[str, set[DrugKey]] = field(
        default_factory=lambda: defaultdict(set)
    )
    drug_providers: dict[DrugKey, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    provider_year_drugs: dict[tuple[int, str], set[DrugKey]] = field(
        default_factory=lambda: defaultdict(set)
    )
    provider_year_specialties: dict[tuple[int, str], set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    latest_observed_year: dict[str, int] = field(default_factory=dict)

    def add(self, rows: Iterable[_PartDRow], year: int) -> None:
        for row in rows:
            drug = row.drug_key
            self.provider_drugs[row.npi].add(drug)
            self.drug_providers[drug].add(row.npi)
            self.provider_year_drugs[(year, row.npi)].add(drug)
            if row.specialty:
                self.provider_year_specialties[(year, row.npi)].add(row.specialty)
            prior_year = self.latest_observed_year.get(row.npi)
            if prior_year is None or year > prior_year:
                self.latest_observed_year[row.npi] = year

    def latest_specialty(self, npi: str) -> str | None:
        year = self.latest_observed_year.get(npi)
        if year is None:
            return None
        values = self.provider_year_specialties.get((year, npi), set())
        if len(values) != 1:
            return None
        return next(iter(values))


@dataclass(slots=True)
class _MetricAccumulator:
    positive_count: int = 0
    contributing_provider_years: int = 0
    contributing_providers: set[str] = field(default_factory=set)
    hits_at_5: int = 0
    hits_at_10: int = 0
    hits_at_20: int = 0
    macro_recall_sum_at_5: float = 0.0
    macro_recall_sum_at_10: float = 0.0
    macro_recall_sum_at_20: float = 0.0
    reciprocal_rank_sum: float = 0.0

    def add(self, npi: str, ranks: list[int]) -> None:
        if not ranks:
            return
        positive_count = len(ranks)
        self.positive_count += positive_count
        self.contributing_provider_years += 1
        self.contributing_providers.add(npi)
        hits = {
            5: sum(rank <= 5 for rank in ranks),
            10: sum(rank <= 10 for rank in ranks),
            20: sum(rank <= 20 for rank in ranks),
        }
        self.hits_at_5 += hits[5]
        self.hits_at_10 += hits[10]
        self.hits_at_20 += hits[20]
        self.macro_recall_sum_at_5 += hits[5] / positive_count
        self.macro_recall_sum_at_10 += hits[10] / positive_count
        self.macro_recall_sum_at_20 += hits[20] / positive_count
        self.reciprocal_rank_sum += 1.0 / min(ranks)

    def as_dict(self) -> dict[str, object]:
        if not self.positive_count:
            undefined: float | None = None
            return {
                "positive_count": 0,
                "contributing_provider_count": 0,
                "contributing_provider_year_count": 0,
                "hits_at_5": 0,
                "hits_at_10": 0,
                "hits_at_20": 0,
                "micro_recall_at_5": undefined,
                "micro_recall_at_10": undefined,
                "micro_recall_at_20": undefined,
                "provider_macro_recall_at_5": undefined,
                "provider_macro_recall_at_10": undefined,
                "provider_macro_recall_at_20": undefined,
                "mrr": undefined,
            }
        return {
            "positive_count": self.positive_count,
            "contributing_provider_count": len(self.contributing_providers),
            "contributing_provider_year_count": self.contributing_provider_years,
            "hits_at_5": self.hits_at_5,
            "hits_at_10": self.hits_at_10,
            "hits_at_20": self.hits_at_20,
            "micro_recall_at_5": self.hits_at_5 / self.positive_count,
            "micro_recall_at_10": self.hits_at_10 / self.positive_count,
            "micro_recall_at_20": self.hits_at_20 / self.positive_count,
            "provider_macro_recall_at_5": self.macro_recall_sum_at_5
            / self.contributing_provider_years,
            "provider_macro_recall_at_10": self.macro_recall_sum_at_10
            / self.contributing_provider_years,
            "provider_macro_recall_at_20": self.macro_recall_sum_at_20
            / self.contributing_provider_years,
            "mrr": self.reciprocal_rank_sum / self.contributing_provider_years,
        }


@dataclass(slots=True)
class _PairedAccumulator:
    difference_sum: float = 0.0
    provider_years: int = 0

    def add(self, difference: float) -> None:
        self.difference_sum += difference
        self.provider_years += 1

    def as_dict(self) -> dict[str, object]:
        return {
            "mean_provider_year_recall_at_10_difference": (
                self.difference_sum / self.provider_years
                if self.provider_years
                else None
            ),
            "provider_year_count": self.provider_years,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _safe_source_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"manifest path must be a non-empty string: {relative!r}")
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError(f"manifest path must be relative: {relative!r}")
    root_resolved = root.resolve()
    path = (root / candidate).resolve(strict=False)
    try:
        path.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"manifest path escapes source root: {relative!r}") from exc
    return path


def _validate_manifest(manifest_path: Path, source_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load Part D manifest {manifest_path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("Part D manifest root must be an object")
    if loaded.get("version") != "0.2-candidate":
        raise ValueError(f"unsupported Part D manifest version: {loaded.get('version')!r}")
    if loaded.get("dataset") != "partd_prescriber_drug":
        raise ValueError(f"unsupported Part D manifest dataset: {loaded.get('dataset')!r}")
    for field_name in ("landing_url", "dictionary_url", "methodology_url"):
        if not isinstance(loaded.get(field_name), str) or not loaded[field_name]:
            raise ValueError(f"manifest field {field_name!r} must be a non-empty string")
    entries = loaded.get("files")
    if not isinstance(entries, list) or len(entries) < 3:
        raise ValueError("Part D manifest must contain at least three file entries")
    checked: list[dict[str, Any]] = []
    years: list[int] = []
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Part D manifest file entries must be objects")
        try:
            year_value = entry["year"]
            path_value = entry["path"]
            url_value = entry["url"]
            dataset_id_value = entry["dataset_id"]
            bytes_value = entry["bytes"]
            sha256_value = entry["sha256"]
            header_value = entry["header"]
            retrieved_at_value = entry["retrieved_at"]
            published_value = entry["historical_published_at"]
        except KeyError as exc:
            raise ValueError(f"manifest entry missing field {exc.args[0]!r}") from exc
        if isinstance(year_value, bool):
            raise ValueError(f"invalid service year: {year_value!r}")
        try:
            year = int(year_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid service year: {year_value!r}") from exc
        if not isinstance(path_value, str) or not path_value:
            raise ValueError(f"invalid manifest path: {path_value!r}")
        _safe_source_path(source_root, path_value)
        if path_value in paths:
            raise ValueError(f"duplicate manifest path: {path_value!r}")
        paths.add(path_value)
        if not isinstance(url_value, str) or not url_value:
            raise ValueError(f"invalid source URL for {path_value!r}")
        if not isinstance(dataset_id_value, str) or not dataset_id_value:
            raise ValueError(f"invalid dataset identifier for {path_value!r}")
        if isinstance(bytes_value, bool):
            raise ValueError(f"invalid byte count for {path_value!r}")
        try:
            byte_count = int(bytes_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid byte count for {path_value!r}") from exc
        if byte_count < 0:
            raise ValueError(f"invalid byte count for {path_value!r}")
        sha256 = str(sha256_value)
        if not _SHA256_RE.fullmatch(sha256):
            raise ValueError(f"invalid SHA-256 for {path_value!r}")
        if (
            not isinstance(header_value, list)
            or not header_value
            or any(not isinstance(column, str) for column in header_value)
            or len(set(header_value)) != len(header_value)
        ):
            raise ValueError(f"invalid pinned header for {path_value!r}")
        missing = [column for column in REQUIRED_COLUMNS if column not in header_value]
        if missing:
            raise ValueError(
                f"pinned header missing required columns {missing} for {path_value!r}"
            )
        if not isinstance(retrieved_at_value, str) or not retrieved_at_value:
            raise ValueError(f"invalid retrieved_at for {path_value!r}")
        if published_value is not None:
            raise ValueError(f"historical_published_at must be null for {path_value!r}")
        years.append(year)
        checked.append(
            {
                "path": path_value,
                "year": year,
                "url": url_value,
                "dataset_id": dataset_id_value,
                "bytes": byte_count,
                "sha256": sha256,
                "header": list(header_value),
                "retrieved_at": retrieved_at_value,
                "historical_published_at": None,
            }
        )
    ordered_years = sorted(years)
    if len(set(years)) != len(years) or ordered_years != list(
        range(ordered_years[0], ordered_years[0] + len(ordered_years))
    ):
        raise ValueError(f"Part D service years must be distinct and contiguous: {years!r}")
    return loaded, sorted(checked, key=lambda item: int(item["year"]))


def _validate_header(
    fieldnames: list[str] | None,
    expected: list[str],
    path: Path,
    year: int,
) -> None:
    if fieldnames is None:
        raise ValueError(f"CSV has no header: file={path}, year={year}")
    if fieldnames != expected:
        raise ValueError(
            f"CSV header drift: file={path}, year={year}; "
            f"got {fieldnames!r}, expected pinned header {expected!r}"
        )
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(
            f"CSV header missing required columns {missing}: file={path}, year={year}"
        )


def _validate_npi(value: object, *, path: Path, year: int, source_row: int) -> str:
    npi = "" if value is None else str(value)
    if len(npi) != 10 or not npi.isascii() or any(char < "0" or char > "9" for char in npi):
        raise ValueError(
            f"invalid Prscrbr_NPI {npi!r}: file={path}, year={year}, source_row={source_row}"
        )
    return npi


def _parse_claims(value: object, *, path: Path, year: int, source_row: int) -> int:
    text = "" if value is None else str(value).strip()
    if not text or any(char < "0" or char > "9" for char in text):
        raise ValueError(
            f"invalid Tot_Clms {text!r}: file={path}, year={year}, source_row={source_row}"
        )
    claims = int(text)
    if claims < 11:
        raise ValueError(
            f"Tot_Clms must be >= 11: file={path}, year={year}, source_row={source_row}, "
            f"value={claims}"
        )
    return claims


def _parse_cost(value: object, *, path: Path, year: int, source_row: int) -> str | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        decimal = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"invalid Tot_Drug_Cst {text!r}: file={path}, year={year}, source_row={source_row}"
        ) from exc
    if not decimal.is_finite() or decimal < 0:
        raise ValueError(
            f"Tot_Drug_Cst must be finite and nonnegative: file={path}, year={year}, "
            f"source_row={source_row}, value={text!r}"
        )
    return text


def _decode_source_text(value: object) -> str:
    text = "" if value is None else str(value)
    return "".join(
        chr(ord(character) - 0xDC00)
        if 0xDC80 <= ord(character) <= 0xDCFF
        else character
        for character in text
    )


def _iter_npis(path: Path, entry: dict[str, Any]) -> Iterable[str]:
    year = int(entry["year"])
    expected_header = list(entry["header"])
    try:
        with path.open(
            "r", encoding="utf-8-sig", errors="surrogateescape", newline=""
        ) as handle:
            reader = csv.DictReader(handle, strict=True)
            _validate_header(reader.fieldnames, expected_header, path, year)
            for source_row, row in enumerate(reader, start=1):
                if None in row:
                    raise ValueError(
                        f"malformed CSV record: file={path}, year={year}, source_row={source_row}"
                    )
                yield _validate_npi(
                    _decode_source_text(row.get("Prscrbr_NPI")),
                    path=path,
                    year=year,
                    source_row=source_row,
                )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"unable to parse NPI scan: file={path}, year={year}: {exc}") from exc


def _select_hash_cohort(npis: Iterable[str], cohort_size: int) -> set[str]:
    import heapq

    heap: list[tuple[int, int, str]] = []
    selected: set[str] = set()
    for npi in npis:
        if npi in selected:
            continue
        digest_integer = int(hashlib.sha256(npi.encode("ascii")).hexdigest(), 16)
        npi_integer = int(npi)
        candidate = (-digest_integer, -npi_integer, npi)
        if len(heap) < cohort_size:
            heapq.heappush(heap, candidate)
            selected.add(npi)
        elif candidate > heap[0]:
            _, _, removed_npi = heapq.heapreplace(heap, candidate)
            selected.remove(removed_npi)
            selected.add(npi)
    return selected


def _select_cohort(path: Path, entry: dict[str, Any], cohort_size: int) -> set[str]:
    selected = _select_hash_cohort(_iter_npis(path, entry), cohort_size)
    if not selected:
        raise ValueError(f"Part D file has no valid provider rows: {path}")
    return selected


def _first_seen_years(
    source_root: Path,
    entries: list[dict[str, Any]],
    *,
    before_year: int | None = None,
) -> dict[str, int]:
    first_seen: dict[str, int] = {}
    for entry in entries:
        year = int(entry["year"])
        if before_year is not None and year >= before_year:
            continue
        path = _safe_source_path(source_root, entry["path"])
        for npi in _iter_npis(path, entry):
            first_seen.setdefault(npi, year)
    return first_seen


def _dynamic_cohorts(
    first_seen: dict[str, int],
    target_years: Iterable[int],
    cohort_size: int,
) -> dict[int, set[str]]:
    cohorts: dict[int, set[str]] = {}
    for year in target_years:
        cohort = _select_hash_cohort(
            (npi for npi, first_year in first_seen.items() if first_year < year),
            cohort_size,
        )
        if not cohort:
            raise ValueError(f"no providers have prior history before target year {year}")
        cohorts[year] = cohort
    return cohorts


def _iter_selected_rows(
    path: Path,
    entry: dict[str, Any],
    cohort: set[str],
) -> list[_PartDRow]:
    year = int(entry["year"])
    expected_header = list(entry["header"])
    rows: list[_PartDRow] = []
    seen: set[tuple[str, DrugKey]] = set()
    try:
        with path.open(
            "r", encoding="utf-8-sig", errors="surrogateescape", newline=""
        ) as handle:
            reader = csv.DictReader(handle, strict=True)
            _validate_header(reader.fieldnames, expected_header, path, year)
            for source_row, raw in enumerate(reader, start=1):
                if None in raw:
                    raise ValueError(
                        f"malformed CSV record: file={path}, year={year}, source_row={source_row}"
                    )
                npi = _validate_npi(
                    _decode_source_text(raw.get("Prscrbr_NPI")),
                    path=path,
                    year=year,
                    source_row=source_row,
                )
                if npi not in cohort:
                    continue
                brand_name = _decode_source_text(raw.get("Brnd_Name")).strip()
                generic_name = _decode_source_text(raw.get("Gnrc_Name")).strip()
                if not brand_name and not generic_name:
                    raise ValueError(
                        "drug key cannot have two blank names: "
                        f"file={path}, year={year}, source_row={source_row}"
                    )
                drug_key = (brand_name, generic_name)
                pair_key = (npi, drug_key)
                if pair_key in seen:
                    raise ValueError(
                        "duplicate selected provider-drug row: "
                        f"file={path}, year={year}, source_row={source_row}, "
                        f"npi={npi}, drug_key={drug_key!r}"
                    )
                seen.add(pair_key)
                rows.append(
                    _PartDRow(
                        npi=npi,
                        brand_name=brand_name,
                        generic_name=generic_name,
                        year=year,
                        claims=_parse_claims(
                            raw.get("Tot_Clms"),
                            path=path,
                            year=year,
                            source_row=source_row,
                        ),
                        cost=_parse_cost(
                            raw.get("Tot_Drug_Cst"),
                            path=path,
                            year=year,
                            source_row=source_row,
                        ),
                        specialty=_decode_source_text(raw.get("Prscrbr_Type")).strip(),
                        state=_decode_source_text(raw.get("Prscrbr_State_Abrvtn")).strip(),
                        source_path=str(entry["path"]),
                        source_row=source_row,
                        source_sha256=str(entry["sha256"]),
                        observed_at=str(entry["retrieved_at"]),
                    )
                )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"unable to parse selected rows: file={path}, year={year}: {exc}") from exc
    return rows


def _claim_band(claims: int) -> str:
    if claims <= 20:
        return "11-20"
    if claims <= 50:
        return "21-50"
    return "51+"


def _positive_ranks(
    candidates: set[DrugKey],
    positives: Iterable[DrugKey],
    scores: dict[DrugKey, float],
    global_support: dict[DrugKey, int],
) -> dict[DrugKey, int]:
    """Compute exact positive ranks without materializing a negative cross-product."""
    ranks: dict[DrugKey, int] = {}
    for positive in positives:
        positive_score = scores[positive]
        positive_support = global_support[positive]
        better_count = 0
        for candidate in candidates:
            candidate_score = scores[candidate]
            if candidate_score > positive_score or (
                candidate_score == positive_score
                and (
                    global_support[candidate] > positive_support
                    or (
                        global_support[candidate] == positive_support
                        and candidate < positive
                    )
                )
            ):
                better_count += 1
        ranks[positive] = better_count + 1
    return ranks





def _score_provider(
    npi: str,
    candidates: set[DrugKey],
    history: _History,
    global_support: dict[DrugKey, int],
    latest_specialties: dict[str, str | None],
    specialty_support: dict[str, dict[DrugKey, int]],
) -> tuple[dict[str, dict[DrugKey, float]], bool]:
    global_scores = {drug: float(global_support[drug]) for drug in candidates}
    target_specialty = latest_specialties.get(npi)
    specialty_fallback = target_specialty is None
    if specialty_fallback:
        specialty_scores = dict(global_scores)
    else:
        target_support = specialty_support.get(target_specialty, {})
        specialty_scores = {
            drug: float(target_support.get(drug, 0)) for drug in candidates
        }
    own_drugs = history.provider_drugs[npi]
    overlap_scores = {drug: 0.0 for drug in candidates}
    overlap_peers: set[str] = set()
    for own_drug in own_drugs:
        overlap_peers.update(history.drug_providers[own_drug])
    overlap_peers.discard(npi)
    for peer in sorted(overlap_peers):
        peer_drugs = history.provider_drugs[peer]
        intersection_size = len(own_drugs & peer_drugs)
        union_size = len(own_drugs) + len(peer_drugs) - intersection_size
        similarity = intersection_size / union_size if union_size else 0.0
        for peer_drug in peer_drugs:
            if peer_drug in overlap_scores:
                overlap_scores[peer_drug] += similarity
    scores = {
        "global_popularity": global_scores,
        "specialty_popularity": specialty_scores,
        "history_overlap": overlap_scores,
    }
    if any(not math.isfinite(score) for values in scores.values() for score in values.values()):
        raise ValueError(f"non-finite baseline score for provider {npi}")
    return scores, specialty_fallback



def _rows_to_edge_values(rows_by_year: dict[int, list[_PartDRow]]) -> list[list[object]]:
    ordered_rows = sorted(
        (row for rows in rows_by_year.values() for row in rows),
        key=lambda row: (row.year, row.npi, row.brand_name, row.generic_name),
    )
    return [
        [
            row.npi,
            row.brand_name,
            row.generic_name,
            row.year,
            row.claims,
            row.cost,
            row.specialty,
            row.state,
            f"{row.year}-01-01",
            f"{row.year + 1}-01-01",
            row.observed_at,
            row.source_path,
            row.source_row,
            row.source_sha256,
            TRANSFORMATION,
        ]
        for row in ordered_rows
    ]


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


def _metric_sections(
    accumulators: dict[str, _MetricAccumulator],
    band_accumulators: dict[str, dict[str, _MetricAccumulator]],
) -> dict[str, object]:
    return {
        method: {
            "all_eligible_positives": accumulators[method].as_dict(),
            "positive_claim_bands": {
                band: band_accumulators[method][band].as_dict() for band in CLAIM_BANDS
            },
        }
        for method in METHOD_NAMES
    }


def _normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _identity_diagnostics(rows_by_year: dict[int, list[_PartDRow]]) -> dict[str, object]:
    all_rows = [row for rows in rows_by_year.values() for row in rows]
    brands_to_generics: dict[str, set[str]] = defaultdict(set)
    generics_to_brands: dict[str, set[str]] = defaultdict(set)
    generic_raw_variants: dict[str, set[str]] = defaultdict(set)
    brand_raw_variants: dict[str, set[str]] = defaultdict(set)
    generic_signatures: dict[str, set[DrugKey]] = defaultdict(set)
    generic_years: dict[str, set[int]] = defaultdict(set)
    exact_signature_years: dict[DrugKey, set[int]] = defaultdict(set)
    exact_provider_edges: set[tuple[str, DrugKey]] = set()
    generic_provider_edges: set[tuple[str, str]] = set()
    for row in all_rows:
        signature = row.drug_key
        exact_signature_years[signature].add(row.year)
        exact_provider_edges.add((row.npi, signature))
        if row.brand_name:
            brands_to_generics[row.brand_name].add(row.generic_name)
            brand_token = _normalized_name(row.brand_name)
            brand_raw_variants[brand_token].add(row.brand_name)
        if row.generic_name:
            generics_to_brands[row.generic_name].add(row.brand_name)
            generic_token = _normalized_name(row.generic_name)
            generic_raw_variants[generic_token].add(row.generic_name)
            generic_signatures[generic_token].add(signature)
            generic_years[generic_token].add(row.year)
            generic_provider_edges.add((row.npi, row.generic_name))
    unstable_generic_tokens = {
        token: {
            "raw_generic_names": sorted(generic_raw_variants[token]),
            "years": sorted(generic_years[token]),
            "exact_brand_generic_signatures": [
                {"brand_name": brand, "generic_name": generic}
                for brand, generic in sorted(generic_signatures[token])
            ],
        }
        for token in sorted(generic_signatures)
        if len(generic_raw_variants[token]) > 1 or len(generic_signatures[token]) > 1
    }
    unstable_brand_tokens = {
        token: sorted(values)
        for token, values in sorted(brand_raw_variants.items())
        if len(values) > 1
    }
    generic_only_nodes = {row.generic_name for row in all_rows if row.generic_name}
    exact_signatures = {row.drug_key for row in all_rows}
    return {
        "identity_policy": "source_native_exact_brand_generic_signature_v1",
        "brands_with_multiple_generics": {
            brand: sorted(generics)
            for brand, generics in sorted(brands_to_generics.items())
            if len(generics) > 1
        },
        "generics_with_multiple_brands": {
            generic: sorted(brands)
            for generic, brands in sorted(generics_to_brands.items())
            if len(brands) > 1
        },
        "distinct_brands": len(brands_to_generics),
        "distinct_generics": len(generics_to_brands),
        "generic_only_alternative": {
            "policy": "exact_trimmed_generic_name_only",
            "distinct_drug_nodes": len(generic_only_nodes),
            "provider_drug_edges": len(generic_provider_edges),
            "provider_edges_collapsed_from_exact_brand_generic": (
                len(exact_provider_edges) - len(generic_provider_edges)
            ),
            "blank_generic_rows_excluded": sum(not row.generic_name for row in all_rows),
        },
        "temporal_instability": {
            "normalized_generic_tokens": len(generic_raw_variants),
            "normalized_generic_tokens_with_multiple_spellings": sum(
                len(values) > 1 for values in generic_raw_variants.values()
            ),
            "normalized_brand_tokens_with_multiple_spellings": len(unstable_brand_tokens),
            "generic_tokens_with_multiple_exact_brand_generic_signatures": sum(
                len(signatures) > 1 for signatures in generic_signatures.values()
            ),
            "exact_brand_generic_signatures_observed_in_multiple_years": sum(
                len(observed_years) > 1 for observed_years in exact_signature_years.values()
            ),
            "unstable_generic_tokens": unstable_generic_tokens,
            "unstable_brand_tokens": unstable_brand_tokens,
            "interpretation": (
                "These diagnostics group text only by case-folded whitespace-normalized "
                "tokens; they do not alter the source-native identity policy or assert "
                "RxNorm, molecule, or clinical-equivalence mappings."
            ),
        },
        "distinct_exact_brand_generic_signatures": len(exact_signatures),
    }
def _coverage_diagnostics(rows_by_year: dict[int, list[_PartDRow]]) -> dict[str, object]:
    all_rows = [row for rows in rows_by_year.values() for row in rows]
    specialty_values = {row.specialty for row in all_rows if row.specialty}
    state_values = {row.state for row in all_rows if row.state}
    provider_year_specialties: dict[tuple[int, str], set[str]] = defaultdict(set)
    for row in all_rows:
        if row.specialty:
            provider_year_specialties[(row.year, row.npi)].add(row.specialty)
    consistent = sum(len(values) == 1 for values in provider_year_specialties.values())
    conflicting = sum(len(values) > 1 for values in provider_year_specialties.values())
    all_blank = len({(row.year, row.npi) for row in all_rows}) - len(provider_year_specialties)
    return {
        "specialty": {
            "row_count": len(all_rows),
            "nonblank_row_count": sum(bool(row.specialty) for row in all_rows),
            "distinct_nonblank_values": sorted(specialty_values),
            "provider_year_count": len({(row.year, row.npi) for row in all_rows}),
            "provider_years_consistent": consistent,
            "provider_years_conflicting": conflicting,
            "provider_years_all_blank": all_blank,
        },
        "state": {
            "model_role": "descriptive only; not a graph node or model feature",
            "row_count": len(all_rows),
            "nonblank_row_count": sum(bool(row.state) for row in all_rows),
            "distinct_nonblank_values": sorted(state_values),
            "value_counts": {
                state: sum(row.state == state for row in all_rows)
                for state in sorted(state_values)
            },
        },
    }


def _overlap_diagnostics(
    rows_by_year: dict[int, list[_PartDRow]], years: list[int]
) -> list[dict[str, object]]:
    drug_sets = {
        year: {row.drug_key for row in rows_by_year[year]} for year in years
    }
    overlaps: list[dict[str, object]] = []
    for index, left_year in enumerate(years):
        for right_year in years[index + 1 :]:
            left = drug_sets[left_year]
            right = drug_sets[right_year]
            union_size = len(left | right)
            overlaps.append(
                {
                    "year_a": left_year,
                    "year_b": right_year,
                    "intersection_count": len(left & right),
                    "union_count": union_size,
                    "jaccard": len(left & right) / union_size if union_size else None,
                }
            )
    return overlaps


def _write_edges(path: Path, rows_by_year: dict[int, list[_PartDRow]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(EDGE_COLUMNS)
        writer.writerows(_rows_to_edge_values(rows_by_year))



def prepare_execution(
    source_root: Path,
    manifest_path: Path,
    output_dir: Path,
    *,
    cohort_size: int = 2000,
) -> dict[str, object]:
    """Prepare raw Part D inputs for direct model execution without fitting models."""
    source_root = Path(source_root)
    manifest_path = Path(manifest_path)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite Part D preparation: {output_dir}")
    if isinstance(cohort_size, bool) or not isinstance(cohort_size, int) or cohort_size <= 0:
        raise ValueError(f"cohort_size must be a positive integer: {cohort_size!r}")

    manifest, entries = _validate_manifest(manifest_path, source_root)
    years = [int(entry["year"]) for entry in entries]
    if years != [2019, 2020, 2021, 2022, 2023, 2024]:
        raise ValueError(
            "Part D execution requires the frozen 2019-2024 raw source; "
            f"got years={years!r}"
        )
    verified_entries = verify_files(source_root, entries)
    score_years = years[-3:]
    first_seen_year = _first_seen_years(
        source_root,
        entries,
        before_year=max(score_years),
    )
    cohorts_by_year = _dynamic_cohorts(first_seen_year, score_years, cohort_size)
    cohort = set().union(*cohorts_by_year.values())
    if not cohort:
        raise ValueError("Part D execution cohort is empty")

    rows_by_year: dict[int, list[_PartDRow]] = {}
    for entry in entries:
        path = _safe_source_path(source_root, entry["path"])
        rows_by_year[int(entry["year"])] = _iter_selected_rows(path, entry, cohort)

    configuration: dict[str, object] = {
        "years": years,
        "score_years": score_years,
        "evaluation_roles": {
            "2022": "train_target",
            "2023": "validation",
            "2024": "held_out_test",
        },
        "cohort_size": cohort_size,
        "cohort_selection": (
            "for each target year, up to cohort_size providers first observed strictly "
            "before that year, ordered by (SHA-256 NPI, NPI)"
        ),
        "drug_identity": "exact trimmed generic_name; blank generic names excluded",
        "candidate_rule": (
            "all generic drugs observed globally in strictly prior cohort history "
            "minus the provider's entire strictly prior generic history"
        ),
        "target_rule": (
            "first observed generic provider-drug relationship in the target year, "
            "excluding drugs absent from global prior history"
        ),
        "edge_transformation": TRANSFORMATION,
    }
    configuration_sha256 = hashlib.sha256(
        _canonical_json(configuration).encode("utf-8")
    ).hexdigest()
    source_provenance = _source_provenance(Path(__file__).resolve().parents[2])
    report: dict[str, object] = {
        "record_kind": "partd_execution_preparation",
        "status": "prepared",
        "source_commit": source_provenance["commit"],
        "dirty_state": source_provenance,
        "configuration": configuration,
        "configuration_sha256": configuration_sha256,
        "cohort": {
            "size": len(cohort),
            "requested_size_per_target": cohort_size,
            "by_target_year": {
                str(year): sorted(cohorts_by_year[year]) for year in score_years
            },
        },
        "sources": {
            "source_root": str(source_root),
            "manifest_path": str(manifest_path),
            "manifest_sha256": sha256_file(manifest_path),
            "landing_url": manifest["landing_url"],
            "dictionary_url": manifest["dictionary_url"],
            "methodology_url": manifest["methodology_url"],
            "files": verified_entries,
        },
        "audits": {"total_retained_edges": sum(map(len, rows_by_year.values()))},
    }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()
    edges_path = output_dir / "edges.csv"
    _write_edges(edges_path, rows_by_year)
    report["artifact_hashes"] = {"edges.csv": sha256_file(edges_path)}
    with (output_dir / "report.json").open("w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return report

def _write_rankings(path: Path, rankings: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in rankings:
            handle.write(_canonical_json(row) + "\n")


def _score_target_year(
    year: int,
    target_cohort: set[str],
    prior_years: list[int],
    rows_by_year: dict[int, list[_PartDRow]],
    pooled_metrics: dict[str, _MetricAccumulator],
    pooled_band_metrics: dict[str, dict[str, _MetricAccumulator]],
    paired_pooled: dict[str, _PairedAccumulator],
) -> dict[str, object]:
    history = _History()
    for prior_year in prior_years:
        history.add(
            (row for row in rows_by_year[prior_year] if row.npi in target_cohort),
            prior_year,
        )
    prior_global_drugs = set(history.drug_providers)
    current_by_provider: dict[str, dict[DrugKey, _PartDRow]] = defaultdict(dict)
    for row in rows_by_year[year]:
        if row.npi in target_cohort:
            current_by_provider[row.npi][row.drug_key] = row
    metric_by_year = {method: _MetricAccumulator() for method in METHOD_NAMES}
    band_metric_by_year = {
        method: {band: _MetricAccumulator() for band in CLAIM_BANDS}
        for method in METHOD_NAMES
    }
    paired_by_year = {
        method: _PairedAccumulator()
        for method in METHOD_NAMES
        if method != "global_popularity"
    }
    global_support = {
        drug: len(providers) for drug, providers in history.drug_providers.items()
    }
    latest_specialties = {
        peer: history.latest_specialty(peer) for peer in history.provider_drugs
    }
    specialty_support: dict[str, dict[DrugKey, int]] = defaultdict(dict)
    for drug, providers in history.drug_providers.items():
        for peer in providers:
            specialty = latest_specialties.get(peer)
            if specialty is not None:
                counts = specialty_support[specialty]
                counts[drug] = counts.get(drug, 0) + 1
    rankings: list[dict[str, object]] = []
    eligible_positive_rows: list[_PartDRow] = []
    candidate_empty_provider_years = 0
    positive_empty_provider_years = 0
    providers_with_positives: set[str] = set()
    fallback_count = 0
    eligible_provider_years = 0
    for npi in sorted(target_cohort):
        prior_provider_drugs = history.provider_drugs.get(npi, set())
        if not prior_provider_drugs:
            continue
        eligible_provider_years += 1
        candidates = prior_global_drugs.difference(prior_provider_drugs)
        if not candidates:
            candidate_empty_provider_years += 1
        current = current_by_provider.get(npi, {})
        positives = {
            drug: row
            for drug, row in current.items()
            if drug not in prior_provider_drugs and drug in prior_global_drugs
        }
        eligible_positive_rows.extend(positives.values())
        if positives:
            providers_with_positives.add(npi)
        else:
            positive_empty_provider_years += 1
        scores, specialty_fallback = _score_provider(
            npi,
            candidates,
            history,
            global_support,
            latest_specialties,
            specialty_support,
        )
        if specialty_fallback and candidates:
            fallback_count += 1
        rankings_by_method: dict[str, dict[DrugKey, int]] = {}
        for method in METHOD_NAMES:
            rankings_by_method[method] = _positive_ranks(
                candidates, positives, scores[method], global_support
            )
            positive_ranks = [
                rankings_by_method[method][drug] for drug in sorted(positives)
            ]
            metric_by_year[method].add(npi, positive_ranks)
            pooled_metrics[method].add(npi, positive_ranks)
            by_band: dict[str, list[int]] = defaultdict(list)
            for drug, row in positives.items():
                by_band[_claim_band(row.claims)].append(rankings_by_method[method][drug])
            for band, ranks in by_band.items():
                band_metric_by_year[method][band].add(npi, sorted(ranks))
                pooled_band_metrics[method][band].add(npi, sorted(ranks))
            if positives and method != "global_popularity":
                global_ranks = [
                    rankings_by_method["global_popularity"][drug]
                    for drug in sorted(positives)
                ]
                method_recall = sum(
                    rankings_by_method[method][drug] <= 10 for drug in positives
                ) / len(positives)
                global_recall = sum(rank <= 10 for rank in global_ranks) / len(positives)
                difference = method_recall - global_recall
                paired_by_year[method].add(difference)
                paired_pooled[method].add(difference)
        rankings.append(
            {
                "year": year,
                "npi": npi,
                "candidate_count": len(candidates),
                "positives": [
                    {
                        "brand_name": drug[0],
                        "generic_name": drug[1],
                        "ranks": {
                            method: rankings_by_method[method][drug]
                            for method in METHOD_NAMES
                        },
                    }
                    for drug in sorted(positives)
                ],
            }
        )
    eligible_claim_bands = {band: 0 for band in CLAIM_BANDS}
    for row in eligible_positive_rows:
        eligible_claim_bands[_claim_band(row.claims)] += 1
    return {
        "metric": metric_by_year,
        "band_metric": band_metric_by_year,
        "paired": paired_by_year,
        "rankings": rankings,
        "eligible_positive_rows": eligible_positive_rows,
        "eligible_claim_bands": eligible_claim_bands,
        "eligible_provider_years": eligible_provider_years,
        "candidate_empty_provider_years": candidate_empty_provider_years,
        "positive_empty_provider_years": positive_empty_provider_years,
        "eligible_positive_provider_count": len(providers_with_positives),
        "specialty_fallback_provider_years": fallback_count,
    }


def run_gate(
    source_root: Path,
    manifest_path: Path,
    output_dir: Path,
    *,
    cohort_size: int = 2000,
) -> dict[str, object]:
    """Run the retrospective Part D prescriber-drug feasibility gate."""
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output directory: {output_dir}")
    if isinstance(cohort_size, bool) or not isinstance(cohort_size, int) or cohort_size <= 0:
        raise ValueError(f"cohort_size must be a positive integer: {cohort_size!r}")
    manifest, entries = _validate_manifest(manifest_path, source_root)
    manifest_sha256 = sha256_file(manifest_path)
    verified_entries = verify_files(source_root, entries)
    years = [int(entry["year"]) for entry in entries]
    warmup_count = max(1, len(years) - 3)
    warmup_years = years[:warmup_count]
    score_years = years[warmup_count:]
    if not score_years:
        raise ValueError("Part D manifest must contain at least one scored service year")

    dynamic_cohort = len(years) > 3
    if dynamic_cohort:
        first_seen_year = _first_seen_years(
            source_root,
            entries,
            before_year=max(score_years),
        )
        cohorts_by_year = _dynamic_cohorts(first_seen_year, score_years, cohort_size)
    else:
        earliest_entry = entries[0]
        earliest_path = _safe_source_path(source_root, earliest_entry["path"])
        fixed_cohort = _select_cohort(earliest_path, earliest_entry, cohort_size)
        cohorts_by_year = {year: set(fixed_cohort) for year in score_years}
    cohort = set().union(*cohorts_by_year.values())
    if not cohort:
        raise ValueError("Part D cohort is empty")
    rows_by_year: dict[int, list[_PartDRow]] = {}
    for entry in entries:
        path = _safe_source_path(source_root, entry["path"])
        rows_by_year[int(entry["year"])] = _iter_selected_rows(path, entry, cohort)

    rankings: list[dict[str, object]] = []
    metric_by_year: dict[int, dict[str, _MetricAccumulator]] = {}
    band_metric_by_year: dict[int, dict[str, dict[str, _MetricAccumulator]]] = {}
    paired_by_year: dict[int, dict[str, _PairedAccumulator]] = {}
    pooled_metrics = {method: _MetricAccumulator() for method in METHOD_NAMES}
    pooled_band_metrics = {
        method: {band: _MetricAccumulator() for band in CLAIM_BANDS}
        for method in METHOD_NAMES
    }
    paired_pooled = {
        method: _PairedAccumulator()
        for method in METHOD_NAMES
        if method != "global_popularity"
    }
    target_results: dict[int, dict[str, object]] = {}
    for year in score_years:
        result = _score_target_year(
            year,
            cohorts_by_year[year],
            years[: years.index(year)],
            rows_by_year,
            pooled_metrics,
            pooled_band_metrics,
            paired_pooled,
        )
        target_results[year] = result
        metric_by_year[year] = result["metric"]  # type: ignore[assignment]
        band_metric_by_year[year] = result["band_metric"]  # type: ignore[assignment]
        paired_by_year[year] = result["paired"]  # type: ignore[assignment]
        rankings.extend(result["rankings"])  # type: ignore[arg-type]

    annual_audit: dict[str, dict[str, object]] = {}
    claim_bands_by_year: dict[str, dict[str, dict[str, int]]] = {}
    audit_history = _History()
    for index, year in enumerate(years):
        rows = rows_by_year[year]
        observed_providers = {row.npi for row in rows}
        observed_drugs = {row.drug_key for row in rows}
        row_claim_bands = {band: 0 for band in CLAIM_BANDS}
        for row in rows:
            row_claim_bands[_claim_band(row.claims)] += 1
        prior_global_drugs = set(audit_history.drug_providers)
        first_observed_edges = 0
        globally_new_edges = 0
        globally_new_drugs: set[DrugKey] = set()
        recurrent_after_gap = 0
        previous_year = years[index - 1] if index else None
        for row in rows:
            prior_provider_drugs = audit_history.provider_drugs.get(row.npi, set())
            if row.drug_key not in prior_provider_drugs:
                first_observed_edges += 1
                if row.drug_key not in prior_global_drugs:
                    globally_new_edges += 1
                    globally_new_drugs.add(row.drug_key)
            elif previous_year is not None and row.drug_key not in audit_history.provider_year_drugs.get(
                (previous_year, row.npi), set()
            ):
                recurrent_after_gap += 1
        result = target_results.get(year)
        scored = result is not None
        if result is None:
            eligible_positive_rows: list[_PartDRow] = []
            eligible_claim_bands = {band: 0 for band in CLAIM_BANDS}
            eligible_provider_years = 0
            eligible_positive_provider_count = 0
            candidate_empty_provider_years = 0
            positive_empty_provider_years = 0
            fallback_count = 0
            target_cohort_size = 0
        else:
            eligible_positive_rows = result["eligible_positive_rows"]  # type: ignore[assignment]
            eligible_claim_bands = result["eligible_claim_bands"]  # type: ignore[assignment]
            eligible_provider_years = int(result["eligible_provider_years"])
            eligible_positive_provider_count = int(result["eligible_positive_provider_count"])
            candidate_empty_provider_years = int(result["candidate_empty_provider_years"])
            positive_empty_provider_years = int(result["positive_empty_provider_years"])
            fallback_count = int(result["specialty_fallback_provider_years"])
            target_cohort_size = len(cohorts_by_year[year])
        claim_bands_by_year[str(year)] = {
            "all_rows": row_claim_bands,
            "eligible_positives": eligible_claim_bands,
        }
        annual_audit[str(year)] = {
            "service_year": year,
            "scored": scored,
            "retained_npis": len(observed_providers),
            "retained_drugs": len(observed_drugs),
            "retained_edges": len(rows),
            "cohort_size": len(cohort),
            "target_cohort_size": target_cohort_size,
            "observed_cohort_npis": len(observed_providers.intersection(cohort)),
            "disappeared_cohort_npis": len(cohort.difference(observed_providers)),
            "first_observed_edges": first_observed_edges,
            "recurrent_edges_excluded_after_gap": recurrent_after_gap if scored else 0,
            "globally_new_drug_edges": globally_new_edges,
            "globally_new_drugs": len(globally_new_drugs),
            "globally_new_drug_edges_excluded": globally_new_edges if scored else 0,
            "globally_new_drugs_excluded": len(globally_new_drugs) if scored else 0,
            "eligible_positive_edges": len(eligible_positive_rows),
            "eligible_positive_provider_count": eligible_positive_provider_count,
            "eligible_provider_years": eligible_provider_years,
            "candidate_empty_provider_years": candidate_empty_provider_years,
            "positive_empty_provider_years": positive_empty_provider_years,
            "specialty_fallback_provider_years": fallback_count,
        }
        audit_history.add(rows, year)

    metrics_by_year = {
        str(year): _metric_sections(metric_by_year[year], band_metric_by_year[year])
        for year in score_years
    }
    paired_report = {
        "by_year": {
            str(year): {
                method: paired_by_year[year][method].as_dict()
                for method in sorted(paired_by_year[year])
            }
            for year in score_years
        },
        "pooled_provider_year": {
            method: paired_pooled[method].as_dict()
            for method in sorted(paired_pooled)
        },
    }
    evaluation_roles: dict[str, str] = {}
    if len(score_years) == 3:
        evaluation_roles = {
            str(score_years[0]): "train_target",
            str(score_years[1]): "validation",
            str(score_years[2]): "held_out_test",
        }
    else:
        evaluation_roles = {str(year): "scored_target" for year in score_years}
    if dynamic_cohort:
        cohort_selection_mode = "dynamic_pre_target"
        cohort_selection_source_year = None
        cohort_selection_rule = (
            "for each scored target year, select the smallest "
            "(sha256(npi.encode('ascii')).hexdigest(), npi) values among providers "
            "first observed strictly before that target year; use all providers when "
            "fewer than the requested size exist"
        )
        new_provider_generalization = (
            "providers are independently selected from pre-target observations; "
            "providers first observed in the target year are excluded from that target"
        )
    else:
        cohort_selection_mode = "fixed_warmup"
        cohort_selection_source_year = years[0]
        cohort_selection_rule = (
            "smallest (sha256(npi.encode('ascii')).hexdigest(), npi) from the earliest "
            "annual file; use all providers when fewer exist"
        )
        new_provider_generalization = (
            "unmeasured; cohort membership is fixed at the warm-up year"
        )
    configuration: dict[str, object] = {
        "years": years,
        "warmup_years": warmup_years,
        "score_years": score_years,
        "evaluation_roles": evaluation_roles,
        "cohort_size": cohort_size,
        "requested_cohort_size": cohort_size,
        "cohort_selection_mode": cohort_selection_mode,
        "cohort_selection_rule": cohort_selection_rule,
        "cohort_selection_source_year": cohort_selection_source_year,
        "transformation_version": TRANSFORMATION,
        "candidate_rule": (
            "all prior cohort drugs absent from the target NPI's entire prior drug set; "
            "score every candidate, with no sampled negatives"
        ),
        "temporal_rules": {
            "temporal_mode": "retrospective_service_year",
            "warmup_years": warmup_years,
            "score_before_history_update": True,
            "history_cutoff": "all retained rows from years strictly before each target year",
            "positive_rule": (
                "current provider-drug relationship first observed in the retained CMS "
                "Part D public-use snapshots"
            ),
            "global_new_drugs_excluded": True,
            "new_provider_generalization": new_provider_generalization,
        },
        "scorers": list(METHOD_NAMES),
        "tie_rule": "descending score, descending global support, ascending (brand_name, generic_name)",
        "metric_cutoffs": list(TOP_KS),
        "claim_bands": list(CLAIM_BANDS),
    }
    configuration_sha256 = hashlib.sha256(
        _canonical_json(configuration).encode("utf-8")
    ).hexdigest()
    repo_root = Path(__file__).resolve().parents[2]
    registry_name = (
        "task_candidates_v0_2_lookback.json"
        if len(years) > 3
        else "task_candidates_v0_2.json"
    )
    registry_path = repo_root / "configs" / registry_name
    registry_sha256 = sha256_file(registry_path) if registry_path.is_file() else None
    registry_reason = (
        None
        if registry_sha256 is not None
        else f"candidate registry unavailable: {registry_path}"
    )
    all_rows = [row for rows in rows_by_year.values() for row in rows]
    total_edges = len(all_rows)
    total_claim_bands = {band: 0 for band in CLAIM_BANDS}
    total_eligible_claim_bands = {band: 0 for band in CLAIM_BANDS}
    for row in all_rows:
        total_claim_bands[_claim_band(row.claims)] += 1
    for year_stats in claim_bands_by_year.values():
        for band in CLAIM_BANDS:
            total_eligible_claim_bands[band] += year_stats["eligible_positives"][band]
    total_eligible_positive_rows = sum(
        len(result["eligible_positive_rows"]) for result in target_results.values()
    )
    fallback_provider_years_by_year = {
        str(year): int(target_results[year]["specialty_fallback_provider_years"])
        for year in score_years
    }
    scored_provider_years = sum(
        int(result["eligible_provider_years"]) for result in target_results.values()
    )
    candidate_empty_provider_years = sum(
        int(result["candidate_empty_provider_years"])
        for result in target_results.values()
    )
    positive_empty_provider_years = sum(
        int(result["positive_empty_provider_years"])
        for result in target_results.values()
    )
    label_definition = {
        "name": "first_observed_published_provider_drug_relationship",
        "positive_rule": (
            "y[p,d,t] = 1 when provider-drug relationship (p,d) is absent from "
            "every retained earlier CMS Part D public-use snapshot and observable "
            "in the published file for year t"
        ),
        "absence_semantics": (
            "not observable in the retained public-use files; absence is not evidence "
            "of no prescribing"
        ),
        "suppression_limit": (
            "CMS suppresses provider-drug combinations with 10 or fewer Part D claims"
        ),
        "not_a_clinical_start_label": (
            "This is not a first prescription, prescribing start, or verified molecule label."
        ),
    }
    source_provenance = _source_provenance(repo_root)
    execution_time = _utc_now()
    report: dict[str, object] = {
        "record_kind": "partd_feasibility",
        "status": "exploratory",
        "decision": (
            "REVIEW_REQUIRED"
            if all(
                int(annual_audit[str(year)]["eligible_positive_edges"]) > 0
                for year in score_years
            )
            else "INSUFFICIENT_OBSERVED_SUPPORT"
        ),
        "decision_basis": (
            f"REVIEW_REQUIRED requires at least one eligible positive in each of the "
            f"{len(score_years)} scored target years after metadata, header, and "
            "integrity checks pass; no lift threshold is used."
        ),
        "temporal_mode": "retrospective_service_year",
        "historical_availability_verified": False,
        "executed_at_utc": execution_time,
        "source_commit": source_provenance["commit"],
        "dirty_state": source_provenance,
        "configuration": configuration,
        "configuration_sha256": configuration_sha256,
        "label_definition": label_definition,
        "cohort": {
            "npis": sorted(cohort),
            "size": len(cohort),
            "requested_size_per_target": cohort_size,
            "selection_mode": cohort_selection_mode,
            "selection_source_year": cohort_selection_source_year,
            "selection_rule": configuration["cohort_selection_rule"],
            "by_target_year": {
                str(year): sorted(cohorts_by_year[year]) for year in score_years
            },
        },
        "sources": {
            "source_root": str(source_root),
            "manifest_path": str(manifest_path),
            "manifest_sha256": manifest_sha256,
            "landing_url": manifest["landing_url"],
            "dictionary_url": manifest["dictionary_url"],
            "methodology_url": manifest["methodology_url"],
            "text_decoding": (
                "UTF-8 with surrogateescape; undecodable source bytes are preserved "
                "as one-to-one code points for anchored textual diagnostics"
            ),
            "files": verified_entries,
        },
        "configuration_source": {
            "path": str(registry_path),
            "sha256": registry_sha256,
            "reason": registry_reason,
        },
        "audits": {
            "annual": annual_audit,
            "claim_bands": {
                "all_rows": total_claim_bands,
                "eligible_positives": total_eligible_claim_bands,
                "by_year": claim_bands_by_year,
            },
            "retained_scope": (
                "All counts, popularity, drug universes, and identity diagnostics are "
                "cohort-local; they are not national estimates."
            ),
            "key_uniqueness_scope": (
                "duplicate provider-drug keys were audited only within the retained cohort"
            ),
            "provider_retention": {
                "cohort_npis": len(cohort),
                "cohort_size_per_target": cohort_size,
                "selected_by_target_year": {
                    str(year): len(cohorts_by_year[year]) for year in score_years
                },
                "observed_by_year": {
                    year: annual_audit[str(year)]["observed_cohort_npis"] for year in years
                },
                "eligible_provider_years_by_target_year": {
                    str(year): int(target_results[year]["eligible_provider_years"])
                    for year in score_years
                },
                "new_provider_generalization": new_provider_generalization,
            },
            "total_retained_npis_by_year": {
                year: annual_audit[str(year)]["retained_npis"] for year in years
            },
            "total_retained_drugs_by_year": {
                year: annual_audit[str(year)]["retained_drugs"] for year in years
            },
            "total_retained_edges_by_year": {
                year: annual_audit[str(year)]["retained_edges"] for year in years
            },
            "total_retained_edges": total_edges,
            "eligible_positive_edges": total_eligible_positive_rows,
            "specialty_fallback_provider_years": fallback_provider_years_by_year,
            "scored_provider_years": scored_provider_years,
            "candidate_empty_provider_years": candidate_empty_provider_years,
            "positive_empty_provider_years": positive_empty_provider_years,
        },
        "metrics": {
            "methods": list(METHOD_NAMES),
            "by_year": metrics_by_year,
            "pooled_provider_year": _metric_sections(
                pooled_metrics, pooled_band_metrics
            ),
            "paired_recall_at_10_vs_global_popularity": paired_report,
        },
        "identity_diagnostics": {
            "exact_name_drug_set_overlap": _overlap_diagnostics(rows_by_year, years),
            **_identity_diagnostics(rows_by_year),
        },
        "coverage_diagnostics": _coverage_diagnostics(rows_by_year),
        "interpretation_limits": [
            "The label is a first observed published provider-drug relationship, not a first prescription or prescribing start.",
            "CMS suppresses provider-drug combinations with 10 or fewer Part D claims; absence is non-observation subject to suppression and left censoring.",
            "Annual service intervals, retrieval timestamps, and historical publication timing are distinct.",
            "The current methodology documents subsequent-year PDE/NPPES information and retroactive file revisions; historical predictor availability is not verified.",
            "This retrospective gate is not a deployment-valid next-calendar-year forecast.",
            "Drug identity is source-native exact-name (brand, generic) and is not RxNorm or a verified clinical molecule.",
            "Malformed non-UTF-8 source bytes are preserved through surrogateescape decoding; source path, row, and SHA-256 remain authoritative for reconstruction.",
            "Provider disappearance from publication is not evidence of ceased prescribing.",
            "Textual identity stability, population representativeness, and suppression remain unresolved interpretation limits.",
            "Claim bands are descriptive slices, not corrections for suppression or higher-threshold labels.",
        ],
        "leakage_controls": [
            (
                "For each scored target year, the bounded cohort is selected only from "
                "providers first observed strictly before that target year."
                if dynamic_cohort
                else "The cohort is selected only from the earliest annual file using a bounded heap and set."
            ),
            "Every annual file is scanned for NPI validity; selected rows are retained without provider-history truncation.",
            "Each target history contains only retained rows from strictly earlier service years; target rows are not added before scoring.",
            "Positive edges are absent from the target provider's entire retained prior history and use only globally prior drugs.",
            "All candidates are evaluated; no sampled negatives or future provider survival are used.",
            "Specialty popularity uses only agreeing nonblank values from each peer's latest strictly prior observed year.",
            "History overlap uses an inverted drug-to-provider index and accumulates peers in sorted NPI order.",
        ],
        "artifact_hashes": {},
    }
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir()
    edges_path = output_dir / "edges.csv"
    rankings_path = output_dir / "rankings.jsonl"
    report_path = output_dir / "report.json"
    _write_edges(edges_path, rows_by_year)
    rankings.sort(key=lambda row: (int(row["year"]), str(row["npi"])))
    _write_rankings(rankings_path, rankings)
    report["artifact_hashes"] = {
        "edges.csv": sha256_file(edges_path),
        "rankings.jsonl": sha256_file(rankings_path),
        "manifest": manifest_sha256,
    }
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return report
