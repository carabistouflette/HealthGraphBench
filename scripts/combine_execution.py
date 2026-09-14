"""Combine versioned task, control, and analysis artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _source_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object result: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maude", type=Path, required=True)
    parser.add_argument("--cms", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=_repo_root() / "data" / "manifests" / "v0.1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {args.output}")
    started_at_utc = datetime.now(timezone.utc).isoformat()
    maude = _read(args.maude)
    cms = _read(args.cms)
    controls = _read(args.controls)
    analysis = _read(args.analysis)
    result = {
        "benchmark_version": "0.1",
        "result_status": "post_baseline_execution",
        "execution": {
            "source_commit": _source_commit(),
            "manifest_sha256": _sha256_file(args.manifest),
            "started_at_utc": started_at_utc,
            "inputs": {
                name: {
                    "path": str(path),
                    "sha256": _sha256_file(path),
                    "source_commit": value.get("execution", {}).get("source_commit"),
                }
                for name, path, value in (
                    ("maude", args.maude, maude),
                    ("cms", args.cms, cms),
                    ("controls", args.controls, controls),
                    ("analysis", args.analysis, analysis),
                )
            },
        },
        "tasks": maude.get("tasks", []) + cms.get("tasks", []),
        "controls": controls,
        "analysis": analysis,
    }
    result["execution"]["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
