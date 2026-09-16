"""Prepare hashes and a payload manifest for the v0.2 release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_ASSETS = (
    ("CITATION.cff", "v0.2 citation metadata"),
    ("docs/benchmark_report_v0_2.md", "v0.2 research report"),
    ("configs/task_contract_v0_2.json", "v0.2 Part D admission contract"),
    ("configs/task_candidates_v0_2.json", "v0.2 task registry"),
    ("results/partd_execution_v0_2_20260916.json", "Part D execution record"),
    ("results/execution_v0_2_20260916.json", "v0.2 execution index"),
    ("results/benchmark_summary_v0_2.csv", "unified result table CSV"),
    ("results/benchmark_summary_v0_2.json", "unified result table JSON"),
    ("results/benchmark_summary_v0_2.svg", "unified result plot"),
    ("results/relational_value_v0_2.json", "cross-task relational-value analysis"),
    (
        "results/generated/partd-v0_2-model-gate-run-003/report.json",
        "Part D model-gate report",
    ),
    (
        "results/generated/partd-v0_2-model-gate-run-003/rankings.jsonl",
        "Part D primary generic rankings",
    ),
)

RELEASE_DOI = "10.5281/zenodo.22796551"
ZENODO_RECORD_URL = "https://zenodo.org/records/22765003"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_commit(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _source_tree_dirty(root: Path, *, ignored_paths: tuple[str, ...] = ()) -> bool:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return True
    return any(
        line[3:].strip() not in ignored_paths
        for line in completed.stdout.splitlines()
        if line.strip()
    )


def _asset(name: str, path: Path, role: str, *, source_path: str) -> dict[str, Any]:
    return {
        "name": name,
        "source_path": source_path,
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--dist-dir", type=Path)
    parser.add_argument(
        "--release-status",
        choices=(
            "local_payload_prepared_not_tagged",
            "tag_ready",
            "github_release_published",
        ),
        help="override the automatically inferred payload status",
    )
    parser.add_argument(
        "--output-manifest", type=Path, default=Path("results/release_assets_v0_2.json")
    )
    parser.add_argument(
        "--output-checksums", type=Path, default=Path("results/SHA256SUMS_v0_2")
    )
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = args.output_manifest
    checksums_path = args.output_checksums
    if manifest_path.exists() or checksums_path.exists():
        raise FileExistsError("refusing to overwrite an existing v0.2 release manifest or checksums")

    assets: list[dict[str, Any]] = []
    missing: list[str] = []
    for relative, role in REPOSITORY_ASSETS:
        path = root / relative
        if not path.is_file():
            missing.append(str(path))
            continue
        assets.append(
            _asset(
                Path(relative).name,
                path,
                role,
                source_path=relative,
            )
        )
    if missing:
        raise FileNotFoundError("missing release payload file(s): " + ", ".join(missing))

    distributions: list[dict[str, Any]] = []
    if args.dist_dir is not None:
        dist_dir = args.dist_dir.resolve()
        if not dist_dir.is_dir():
            raise FileNotFoundError(f"distribution directory is missing: {dist_dir}")
        for path in sorted(dist_dir.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                distributions.append(
                    _asset(
                        path.name,
                        path,
                        "Python distribution",
                        source_path=str(path),
                    )
                )

    source_commit = _source_commit(root)
    ignored_release_paths = tuple(
        os.path.relpath(path.resolve(), root)
        for path in (manifest_path, checksums_path)
    )
    dirty = _source_tree_dirty(root, ignored_paths=ignored_release_paths)
    release_status = args.release_status or (
        "local_payload_prepared_not_tagged" if dirty else "tag_ready"
    )
    manifest = {
        "schema_version": 1,
        "release": "v0.2.0",
        "source_commit": source_commit,
        "source_tree_dirty": dirty,
        "release_status": release_status,
        "packaged_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_status": "development-stage admitted replication extension",
        "report_status": "v0.2 report and unified cross-task analysis are frozen for packaging",
        "raw_data_included": False,
        "frozen_v0_1_reference": {
            "release": "v0.1.2",
            "manifest": "results/release_assets_v0_1_2.json",
            "status": "unchanged dependency; not duplicated or rewritten",
        },
        "assets": assets,
        "distributions": distributions,
        "verification": "SHA256SUMS_v0_2 covers every repository payload asset and this manifest; distribution hashes are recorded separately; raw datasets remain external.",
        "doi": RELEASE_DOI,
        "zenodo_record_url": ZENODO_RECORD_URL,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    checksums_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_absolute = manifest_path.resolve()
    checksums_path.write_text("", encoding="utf-8")
    manifest_absolute.write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    checksum_lines = [
        f"{_sha256_file(root / asset['source_path'])}  {asset['source_path']}"
        for asset in assets
    ]
    checksum_lines.append(
        f"{_sha256_file(manifest_absolute)}  {os.path.relpath(manifest_absolute, root)}"
    )
    checksums_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path} and {checksums_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
