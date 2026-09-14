"""Download and verify the frozen MAUDE v0.1 source snapshot."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path

from healthgraphbench.data import load_manifest, sha256_file


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
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as output:
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
    parser.add_argument("--output", type=Path, required=True, help="directory for MAUDE ZIP files")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    spec = manifest["maude"]
    urls = spec["official_urls"]
    for entry in spec["files"]:
        name = str(entry["path"])
        if name.startswith("device20"):
            year = name[len("device") : -len(".zip")]
            url = str(urls["file_template"]).format(year=year)
        elif name == "foidevproblem_thru2025.zip":
            url = str(urls["problem_file"])
        elif name == "deviceproblemcodes2025.zip":
            url = str(urls["device_problem_map"])
        else:
            raise ValueError(f"unmapped MAUDE manifest file {name}")
        _download_verified(url, args.output / name, entry)
        print(f"verified {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
