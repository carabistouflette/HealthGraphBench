"""Download and verify the frozen CMS v0.1 source snapshot."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from healthgraphbench.data import load_manifest, sha256_file


def _download_owners_full(url: str, destination: Path) -> None:
    """Restore the frozen complete JSON, not the API's capped first page."""

    parts = urllib.parse.urlsplit(url)
    parameters = dict(urllib.parse.parse_qsl(parts.query))
    parameters["size"] = "5000"
    records: list[dict[str, object]] = []
    offset = 0
    while True:
        parameters["offset"] = str(offset)
        page_url = urllib.parse.urlunsplit(
            parts._replace(query=urllib.parse.urlencode(parameters))
        )
        with urllib.request.urlopen(page_url, timeout=180) as response:
            page = json.load(response)
        if not isinstance(page, list):
            raise ValueError("CMS owners API did not return a JSON record list")
        if not page:
            break
        records.extend(page)
        offset += len(page)
        print(f"owners records collected: {offset}", flush=True)

    # Frozen owners use compact UTF-8, API field order, and no trailing newline.
    # The caller checks the full byte count and digest before installing it.
    with destination.open("w", encoding="utf-8", newline="") as output:
        json.dump(records, output, ensure_ascii=False, separators=(",", ":"))

def _download_verified(url: str, destination: Path, expected: dict[str, object]) -> None:
    if destination.exists():
        actual = (destination.stat().st_size, sha256_file(destination))
        expected_pair = (int(expected["bytes"]), str(expected["sha256"]))
        if actual != expected_pair:
            raise ValueError(
                f"existing file does not match frozen manifest: {destination}; "
                f"got {actual}, expected {expected_pair}"
            )
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        partial = Path(handle.name)
    try:
        if destination.name == "chow_owners_full.json":
            _download_owners_full(url, partial)
        else:
            with urllib.request.urlopen(url, timeout=180) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output)
        actual = (partial.stat().st_size, sha256_file(partial))
        expected_pair = (int(expected["bytes"]), str(expected["sha256"]))
        if actual != expected_pair:
            raise ValueError(
                f"downloaded source differs from frozen manifest: {url}; "
                f"got {actual}, expected {expected_pair}"
            )
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="directory for CMS source files")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    spec = manifest["cms"]
    urls = spec["official_urls"]
    for entry in spec["files"]:
        name = str(entry["path"])
        source_key = "chow_owners" if name == "chow_owners_full.json" else Path(name).stem
        url = str(urls[source_key])
        _download_verified(url, args.output / name, entry)
        print(f"verified {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
