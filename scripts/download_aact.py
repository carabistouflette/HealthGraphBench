"""Download and integrity-pin the historical AACT flat-file snapshots."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import tempfile
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from healthgraphbench.data import sha256_file


SNAPSHOT_SPECS: tuple[dict[str, str], ...] = (
    {"snapshot_date": "2019-01-01", "path": "aact_2019-01-01_export_ctgov.zip"},
    {"snapshot_date": "2020-01-01", "path": "aact_2020-01-01_export_ctgov.zip"},
    {"snapshot_date": "2021-01-01", "path": "aact_2021-01-01_export_ctgov.zip"},
    {"snapshot_date": "2022-02-01", "path": "aact_2022-02-01_export_ctgov.zip"},
    {"snapshot_date": "2023-02-01", "path": "aact_2023-02-01_export_ctgov.zip"},
    {"snapshot_date": "2024-02-01", "path": "aact_2024-02-01_export_ctgov.zip"},
    {"snapshot_date": "2025-02-01", "path": "aact_2025-02-01_export_ctgov.zip"},
)

LANDING_URL = "https://aact.ctti-clinicaltrials.org/"
DOWNLOAD_URL_TEMPLATE = (
    "https://aact.ctti-clinicaltrials.org/static/exported_files/pipe_files/"
    "{yyyymmdd}_export_ctgov.zip"
)
REQUIRED_TABLES: tuple[str, ...] = (
    "studies.txt",
    "conditions.txt",
    "interventions.txt",
    "sponsors.txt",
    "facilities.txt",
    "designs.txt",
)
MANIFEST_VERSION = "0.2-candidate-clinical-trials"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_path(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"manifest path must be a non-empty string: {relative!r}")
    path = (root / relative).resolve()
    root_resolved = root.resolve()
    if path != root_resolved and root_resolved not in path.parents:
        raise ValueError(f"manifest path escapes source root: {relative!r}")
    return path


def _headers(path: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = [name for name in REQUIRED_TABLES if name not in names]
        if missing:
            raise ValueError(f"AACT archive is missing required tables: {path}: {missing}")
        for name in REQUIRED_TABLES:
            with archive.open(name) as raw:
                line = raw.readline().decode("utf-8-sig").rstrip("\r\n")
            if not line:
                raise ValueError(f"AACT table has an empty header: {path}!{name}")
            result[name] = line.split("|")
    return result


def _download_range(url: str, start: int, end: int) -> bytes:
    for attempt in range(6):
        separator = "&" if "?" in url else "?"
        ranged_url = f"{url}{separator}hgb_range={start}-{end}-{attempt}"
        request = urllib.request.Request(
            ranged_url,
            headers={
                "Accept-Encoding": "identity",
                "Range": f"bytes={start}-{end}",
                "User-Agent": "HealthGraphBench/0.2 candidate feasibility",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                if response.status != 206:
                    continue
                content_range = response.headers.get("Content-Range", "")
                expected_range = f"bytes {start}-{end}/"
                if not content_range.startswith(expected_range):
                    continue
                payload = response.read()
        except (OSError, ValueError, http.client.IncompleteRead):
            continue
        if len(payload) == end - start + 1:
            return payload
    raise OSError(f"unable to fetch byte range {start}-{end} from {url}")


def _download_segmented(path: Path, url: str, expected_bytes: int | None) -> dict[str, Any]:
    head_request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "HealthGraphBench/0.2 candidate feasibility"},
    )
    with urllib.request.urlopen(head_request, timeout=180) as response:
        content_length = response.headers.get("Content-Length")
        range_url = response.geturl()
    remote_bytes = int(content_length) if content_length else expected_bytes
    if remote_bytes is None or remote_bytes <= 0:
        raise ValueError(f"AACT archive has no usable Content-Length: {url}")
    if expected_bytes is not None and remote_bytes != expected_bytes:
        raise ValueError(
            f"AACT archive size differs from frozen manifest: {url}; "
            f"got {remote_bytes}, expected {expected_bytes}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        partial = Path(handle.name)
        handle.truncate(remote_bytes)
    chunk_size = 8 * 1024 * 1024
    ranges = [
        (start, min(start + chunk_size, remote_bytes) - 1)
        for start in range(0, remote_bytes, chunk_size)
    ]
    fd = os.open(partial, os.O_WRONLY)
    published = False
    try:
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = {
                executor.submit(_download_range, range_url, start, end): (start, end)
                for start, end in ranges
            }
            for future in as_completed(futures):
                start, _ = futures.pop(future)
                payload = future.result()
                os.pwrite(fd, payload, start)
                del payload
        os.fsync(fd)
        actual = {"bytes": partial.stat().st_size, "sha256": sha256_file(partial)}
        partial.replace(path)
        published = True
        return actual
    finally:
        os.close(fd)
        if not published:
            partial.unlink(missing_ok=True)


def _download(
    path: Path,
    url: str,
    expected: dict[str, Any] | None = None,
    *,
    allow_existing: bool = False,
) -> dict[str, Any]:
    if path.exists():
        if expected is None and not allow_existing:
            raise FileExistsError(f"refusing to reuse existing AACT archive: {path}")
        actual = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        if expected is not None:
            wanted = {"bytes": int(expected["bytes"]), "sha256": str(expected["sha256"])}
            if actual != wanted:
                raise ValueError(f"existing AACT archive differs from manifest: {path}; got {actual}, expected {wanted}")
    else:
        expected_bytes = None if expected is None else int(expected["bytes"])
        actual = _download_segmented(path, url, expected_bytes)
        if expected is not None:
            wanted = {"bytes": int(expected["bytes"]), "sha256": str(expected["sha256"])}
            if actual != wanted:
                raise ValueError(
                    f"downloaded AACT archive differs from manifest: {url}; got {actual}, expected {wanted}"
                )
    return {"bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _specifications() -> list[dict[str, str]]:
    specifications: list[dict[str, str]] = []
    for specification in SNAPSHOT_SPECS:
        snapshot_date = specification["snapshot_date"]
        yyyymmdd = snapshot_date.replace("-", "")
        specifications.append(
            {
                **specification,
                "url": DOWNLOAD_URL_TEMPLATE.format(yyyymmdd=yyyymmdd),
            }
        )
    return specifications


def _validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError(f"unsupported AACT manifest version: {manifest.get('version')!r}")
    if manifest.get("dataset") != "clinical_trials_reporting":
        raise ValueError(f"unexpected AACT dataset: {manifest.get('dataset')!r}")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != len(SNAPSHOT_SPECS):
        raise ValueError("AACT manifest must contain exactly the frozen snapshot list")
    expected_by_date = {item["snapshot_date"]: item for item in _specifications()}
    checked: list[dict[str, Any]] = []
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("AACT manifest file entries must be objects")
        date = item.get("snapshot_date")
        expected = expected_by_date.get(date)
        if expected is None:
            raise ValueError(f"unexpected AACT snapshot date: {date!r}")
        if item.get("path") != expected["path"] or item.get("url") != expected["url"]:
            raise ValueError(f"AACT manifest entry does not match frozen URL/path for {date}")
        if not isinstance(item.get("bytes"), int) or item["bytes"] <= 0:
            raise ValueError(f"invalid AACT byte count for {date}")
        sha256 = item.get("sha256")
        if not isinstance(sha256, str) or len(sha256) != 64:
            raise ValueError(f"invalid AACT SHA-256 for {date}")
        headers = item.get("headers")
        if not isinstance(headers, dict) or any(name not in headers for name in REQUIRED_TABLES):
            raise ValueError(f"AACT manifest headers are incomplete for {date}")
        checked.append(item)
    if {item["snapshot_date"] for item in checked} != set(expected_by_date):
        raise ValueError("AACT manifest snapshot dates are incomplete or duplicated")
    return sorted(checked, key=lambda item: item["snapshot_date"])


def acquire(output: Path, manifest_path: Path, *, allow_existing: bool = False) -> dict[str, Any]:
    """Download the frozen snapshots or replay an existing pinned manifest."""
    specifications = _specifications()
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = _validate_manifest(manifest)
        for entry in entries:
            path = _safe_path(output, entry["path"])
            _download(path, str(entry["url"]), entry)
            actual_headers = _headers(path)
            if actual_headers != entry["headers"]:
                raise ValueError(f"AACT table header drift in {path}")
        return manifest

    existing = [specification["path"] for specification in specifications if (output / specification["path"]).exists()]
    if existing and not allow_existing:
        raise FileExistsError(
            "AACT destination contains frozen archive names but no manifest; "
            f"use a new destination or --allow-existing: {existing}"
        )

    entries: list[dict[str, Any]] = []
    for specification in specifications:
        path = _safe_path(output, specification["path"])
        integrity = _download(path, specification["url"], allow_existing=allow_existing)
        entries.append(
            {
                "snapshot_date": specification["snapshot_date"],
                "path": specification["path"],
                "url": specification["url"],
                **integrity,
                "headers": _headers(path),
                "retrieved_at": _utc_now(),
                "historical_published_at": None,
            }
        )
        print(f"verified {path.name}")

    manifest = {
        "dataset": "clinical_trials_reporting",
        "version": MANIFEST_VERSION,
        "landing_url": LANDING_URL,
        "format": "aact_pipe_delimited_flat_file_zip",
        "snapshot_policy": "first-of-month historical AACT archive; source publication timestamp is not asserted",
        "required_tables": list(REQUIRED_TABLES),
        "files": entries,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="external directory for AACT ZIP snapshots")
    parser.add_argument("--manifest", type=Path, required=True, help="new or existing pinned manifest path")
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="reuse already complete archive names when recovering an interrupted manifest-free acquisition",
    )
    args = parser.parse_args()
    manifest = acquire(args.output, args.manifest, allow_existing=args.allow_existing)
    print(f"verified {len(manifest['files'])} AACT snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
