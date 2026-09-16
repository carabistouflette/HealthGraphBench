"""Acquire and integrity-pin the CMS Medicare Part D candidate snapshot."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from healthgraphbench.data import sha256_file

REQUIRED_COLUMNS: tuple[str, ...] = (
    "Prscrbr_NPI",
    "Brnd_Name",
    "Gnrc_Name",
    "Prscrbr_Type",
    "Prscrbr_State_Abrvtn",
    "Tot_Clms",
    "Tot_Drug_Cst",
)
OFFICIAL_HEADER: tuple[str, ...] = (
    "Prscrbr_NPI",
    "Prscrbr_Last_Org_Name",
    "Prscrbr_First_Name",
    "Prscrbr_City",
    "Prscrbr_State_Abrvtn",
    "Prscrbr_State_FIPS",
    "Prscrbr_Type",
    "Prscrbr_Type_Src",
    "Brnd_Name",
    "Gnrc_Name",
    "Tot_Clms",
    "Tot_30day_Fills",
    "Tot_Day_Suply",
    "Tot_Drug_Cst",
    "Tot_Benes",
    "GE65_Sprsn_Flag",
    "GE65_Tot_Clms",
    "GE65_Tot_30day_Fills",
    "GE65_Tot_Drug_Cst",
    "GE65_Tot_Day_Suply",
    "GE65_Bene_Sprsn_Flag",
    "GE65_Tot_Benes",
)

LANDING_URL = (
    "https://data.cms.gov/provider-summary-by-type-of-service/"
    "medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug"
)
DICTIONARY_URL = (
    "https://data.cms.gov/sites/default/files/2022-07/"
    "MUP_DPR_RY22_20220715_DD_PRV_Drug.pdf"
)
METHODOLOGY_URL = (
    "https://data.cms.gov/sites/default/files/2026-05/"
    "MUP_DPR_RY26_20260421_Methodology_508.pdf"
)

OFFICIAL_FILES: tuple[dict[str, object], ...] = (
    {
        "year": 2019,
        "path": "partd_2019.csv",
        "bytes": 3657232553,
        "url": (
            "https://data.cms.gov/sites/default/files/2024-05/"
            "129e7c21-d492-425b-be03-d2e59d933ab6/"
            "MUP_DPR_RY24_P04_V10_DY19_NPIBN.csv"
        ),
        "dataset_id": "2a6705e6-7a1e-460c-ba22-35249a531918",
    },
    {
        "year": 2020,
        "path": "partd_2020.csv",
        "bytes": 3636794301,
        "url": (
            "https://data.cms.gov/sites/default/files/2024-05/"
            "75fecc51-c9e8-4904-b570-9da9dc101721/"
            "MUP_DPR_RY24_P04_V10_DY20_NPIBN.csv"
        ),
        "dataset_id": "7795fe20-e80e-435a-a9ed-d2d65e05feeb",
    },
    {
        "year": 2021,
        "path": "partd_2021.csv",
        "bytes": 3641939924,
        "url": (
            "https://data.cms.gov/sites/default/files/2024-05/"
            "43359391-e7fa-40b9-9bd4-5dc295e18712/"
            "MUP_DPR_RY24_P04_V10_DY21_NPIBN.csv"
        ),
        "dataset_id": "f68114ed-f854-4ffc-9c6e-ed78b5e2f8d0",
    },
    {
        "year": 2022,
        "path": "partd_2022.csv",
        "bytes": 3738326206,
        "url": (
            "https://data.cms.gov/sites/default/files/2024-05/"
            "18f82097-61a6-4889-9941-9a0b6ad7523c/"
            "MUP_DPR_RY24_P04_V10_DY22_NPIBN.csv"
        ),
        "dataset_id": "b101b457-ffa4-49bb-8fd9-27c1266086e2",
    },
    {
        "year": 2023,
        "path": "partd_2023.csv",
        "bytes": 3877447342,
        "url": (
            "https://data.cms.gov/sites/default/files/2025-04/"
            "0d5915ce-002c-4d87-bde8-24ffb08bb6cc/"
            "MUP_DPR_RY25_P04_V10_DY23_NPIBN.csv"
        ),
        "dataset_id": "e54db557-cd82-4e91-a0fe-61aad5865d69",
    },
    {
        "year": 2024,
        "path": "partd_2024.csv",
        "bytes": 4057615134,
        "url": (
            "https://data.cms.gov/sites/default/files/2026-05/"
            "0ae165f4-eb44-495d-8cac-67f4571b6b83/"
            "MUP_DPR_RY26_P04_V10_DY24_NPIBN.csv"
        ),
        "dataset_id": "9552739e-3d05-4c1b-8eff-ecabf391e2e5",
    },
)
DEFAULT_YEARS: tuple[int, ...] = (2022, 2023, 2024)
_OFFICIAL_BY_YEAR = {int(specification["year"]): specification for specification in OFFICIAL_FILES}


def _official_specifications(years: list[int] | None) -> list[dict[str, object]]:
    selected_years = list(DEFAULT_YEARS if years is None else years)
    if not selected_years:
        raise ValueError("at least one official service year is required")
    if len(set(selected_years)) != len(selected_years):
        raise ValueError(f"official service years must be distinct: {selected_years!r}")
    ordered_years = sorted(selected_years)
    if ordered_years != list(range(ordered_years[0], ordered_years[0] + len(ordered_years))):
        raise ValueError(f"official service years must be contiguous: {selected_years!r}")
    unknown_years = [year for year in ordered_years if year not in _OFFICIAL_BY_YEAR]
    if unknown_years:
        raise ValueError(f"no pinned CMS metadata for service years: {unknown_years!r}")
    return [_OFFICIAL_BY_YEAR[year] for year in ordered_years]


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_destination(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"manifest path must be a non-empty string: {relative!r}")
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError(f"manifest path must be relative: {relative!r}")
    root_resolved = root.resolve()
    destination = (root / candidate).resolve(strict=False)
    try:
        destination.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"manifest path escapes source root: {relative!r}") from exc
    return destination


def _read_header(path: Path, *, source_url: str | None = None) -> list[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle), None)
    except (OSError, UnicodeError, csv.Error) as exc:
        location = source_url or str(path)
        raise ValueError(f"unable to read CSV header from {location}: {exc}") from exc
    if not header:
        location = source_url or str(path)
        raise ValueError(f"CSV has no header: {location}")
    if len(set(header)) != len(header):
        location = source_url or str(path)
        raise ValueError(f"CSV header contains duplicate columns: {location}")
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        location = source_url or str(path)
        raise ValueError(f"CSV header missing required columns {missing}: {location}")
    return header


def _download_verified(
    url: str,
    destination: Path,
    *,
    expected_bytes: int,
    expected_sha256: str | None = None,
    expected_header: list[str] | None = None,
) -> tuple[str, list[str]]:
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing destination: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        partial = Path(handle.name)
    try:
        try:
            with urllib.request.urlopen(url, timeout=180) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output)
        except Exception as exc:
            raise RuntimeError(f"failed downloading {url}: {exc}") from exc
        actual_bytes = partial.stat().st_size
        if actual_bytes != expected_bytes:
            raise ValueError(
                f"downloaded source differs from frozen CMS metadata: {url}; "
                f"got {actual_bytes} bytes, expected {expected_bytes}"
            )
        actual_sha256 = sha256_file(partial)
        if expected_sha256 is not None and actual_sha256 != expected_sha256:
            raise ValueError(
                f"downloaded source differs from frozen manifest: {url}; "
                f"got SHA-256 {actual_sha256}, expected {expected_sha256}"
            )
        header = _read_header(partial, source_url=url)
        if expected_header is not None and header != expected_header:
            raise ValueError(
                f"downloaded source header differs from frozen manifest: {url}; "
                f"got {header!r}, expected {expected_header!r}"
            )
        partial.replace(destination)
        return actual_sha256, header
    finally:
        partial.unlink(missing_ok=True)


def _validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("version") != "0.2-candidate":
        raise ValueError(f"unsupported Part D manifest version: {manifest.get('version')!r}")
    if manifest.get("dataset") != "partd_prescriber_drug":
        raise ValueError(f"unsupported Part D manifest dataset: {manifest.get('dataset')!r}")
    for field in ("landing_url", "dictionary_url", "methodology_url"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise ValueError(f"manifest field {field!r} must be a non-empty string")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) < 3:
        raise ValueError("Part D manifest must contain at least three file entries")
    checked: list[dict[str, Any]] = []
    years: list[int] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Part D manifest file entries must be objects")
        try:
            year = int(entry["year"])
            path = entry["path"]
            url = entry["url"]
            dataset_id = entry["dataset_id"]
            size = int(entry["bytes"])
            sha256 = str(entry["sha256"])
            header = entry["header"]
            retrieved_at = entry["retrieved_at"]
            historical_published_at = entry["historical_published_at"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid Part D manifest file entry: {entry!r}") from exc
        if not isinstance(path, str) or not path:
            raise ValueError(f"invalid manifest path: {path!r}")
        if not isinstance(url, str) or not url:
            raise ValueError(f"invalid manifest URL for {path!r}")
        if not isinstance(dataset_id, str) or not dataset_id:
            raise ValueError(f"invalid dataset identifier for {path!r}")
        if size < 0 or not _SHA256_RE.fullmatch(sha256):
            raise ValueError(f"invalid byte count or SHA-256 for {path!r}")
        if (
            not isinstance(header, list)
            or not header
            or any(not isinstance(column, str) for column in header)
            or len(set(header)) != len(header)
        ):
            raise ValueError(f"invalid pinned header for {path!r}")
        if any(column not in header for column in REQUIRED_COLUMNS):
            raise ValueError(f"pinned header missing required columns for {path!r}")
        if not isinstance(retrieved_at, str) or not retrieved_at:
            raise ValueError(f"invalid retrieved_at for {path!r}")
        if historical_published_at is not None:
            raise ValueError(f"historical_published_at must be null for {path!r}")
        years.append(year)
        checked.append(
            {
                "year": year,
                "path": path,
                "url": url,
                "dataset_id": dataset_id,
                "bytes": size,
                "sha256": sha256,
                "header": header,
                "retrieved_at": retrieved_at,
                "historical_published_at": None,
            }
        )
    ordered_years = sorted(years)
    if len(set(years)) != len(years) or ordered_years != list(
        range(ordered_years[0], ordered_years[0] + len(ordered_years))
    ):
        raise ValueError(f"Part D service years must be distinct and contiguous: {years!r}")
    if len({entry["path"] for entry in checked}) != len(checked):
        raise ValueError("Part D manifest file paths must be distinct")
    return sorted(checked, key=lambda entry: int(entry["year"]))


def _initial_state(output: Path, manifest_path: Path) -> None:
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite existing manifest: {manifest_path}")
    if output.exists():
        if not output.is_dir():
            raise FileExistsError(f"output destination is not a directory: {output}")
        retained = sorted(path.name for path in output.iterdir())
        if retained:
            raise FileExistsError(
                "initial acquisition requires a fresh output destination; "
                f"retained files: {retained}"
            )


def _acquire_initial(
    output: Path,
    manifest_path: Path,
    years: list[int] | None,
) -> dict[str, Any]:
    specifications = _official_specifications(years)
    _initial_state(output, manifest_path)
    output.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    try:
        for specification in specifications:
            path = str(specification["path"])
            destination = _safe_destination(output, path)
            sha256, header = _download_verified(
                str(specification["url"]),
                destination,
                expected_bytes=int(specification["bytes"]),
                expected_header=list(OFFICIAL_HEADER),
            )
            entry = {
                "path": path,
                "year": int(specification["year"]),
                "url": str(specification["url"]),
                "dataset_id": str(specification["dataset_id"]),
                "bytes": int(specification["bytes"]),
                "sha256": sha256,
                "header": header,
                "retrieved_at": _utc_now(),
                "historical_published_at": None,
            }
            entries.append(entry)
            print(f"verified {path} ({entry['bytes']} bytes, {sha256})")
    except Exception:
        retained = sorted(path.name for path in output.iterdir()) if output.is_dir() else []
        if retained:
            print(f"retained files after failed acquisition: {retained}", file=sys.stderr)
        raise
    manifest = {
        "version": "0.2-candidate",
        "dataset": "partd_prescriber_drug",
        "landing_url": LANDING_URL,
        "dictionary_url": DICTIONARY_URL,
        "methodology_url": METHODOLOGY_URL,
        "files": entries,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite existing manifest: {manifest_path}")
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=manifest_path.parent, delete=False
    ) as handle:
        partial_manifest = Path(handle.name)
        handle.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    try:
        partial_manifest.replace(manifest_path)
    finally:
        partial_manifest.unlink(missing_ok=True)
    print(f"published manifest {manifest_path}")
    return manifest


def _acquire_replay(output: Path, manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to load Part D manifest {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Part D manifest root must be an object")
    entries = _validate_manifest(manifest)
    output.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        destination = _safe_destination(output, entry["path"])
        if destination.exists():
            if not destination.is_file():
                raise ValueError(f"source destination is not a file: {destination}")
            actual = (destination.stat().st_size, sha256_file(destination))
            expected = (int(entry["bytes"]), str(entry["sha256"]))
            if actual != expected:
                raise ValueError(
                    f"existing file does not match frozen manifest: {destination}; "
                    f"got {actual}, expected {expected}"
                )
            header = _read_header(destination, source_url=str(entry["url"]))
            if header != entry["header"]:
                raise ValueError(
                    f"existing source header differs from frozen manifest: {destination}"
                )
            print(f"verified {entry['path']}")
            continue
        _download_verified(
            str(entry["url"]),
            destination,
            expected_bytes=int(entry["bytes"]),
            expected_sha256=str(entry["sha256"]),
            expected_header=list(entry["header"]),
        )
        print(f"downloaded and verified {entry['path']}")
    return manifest


def acquire(
    output: Path,
    manifest_path: Path,
    *,
    years: list[int] | None = None,
) -> dict[str, Any]:
    """Acquire the official files or replay an existing pinned manifest."""
    if manifest_path.exists():
        return _acquire_replay(output, manifest_path)
    return _acquire_initial(output, manifest_path, years)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="external raw source directory")
    parser.add_argument("--manifest", type=Path, required=True, help="new or existing manifest path")
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=None,
        help="contiguous official service years; defaults to the frozen 2022-2024 profile",
    )
    args = parser.parse_args()
    try:
        acquire(args.output, args.manifest, years=args.years)
    except Exception as exc:
        print(f"Part D acquisition failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
