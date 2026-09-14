"""Run the real-topology positive and zero-signal CMS controls."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from healthgraphbench import load_task
from healthgraphbench.data import load_manifest, sha256_file
from healthgraphbench.controls import run_topology_controls


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


def _assert_new_output(output: Path) -> None:
    frozen = _repo_root() / "results" / "synthetic_controls_v0_1.json"
    if output.resolve() == frozen.resolve():
        raise ValueError(f"frozen exploratory result path is immutable: {output}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--cutoff", type=date.fromisoformat, default=date(2024, 1, 1))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _assert_new_output(args.output)
    started_at_utc = datetime.now(timezone.utc).isoformat()
    manifest_path = _repo_root() / "data" / "manifests" / "v0.1.json"
    manifest = load_manifest(manifest_path)
    task = load_task("cms_nursing", args.data_root)
    rows = run_topology_controls(task.prepared.current_records, cutoff=args.cutoff)
    result = {
        "benchmark_version": "0.1",
        "task": "cms_nursing",
        "control_type": "synthetic node labels on real pre-cutoff ownership topology",
        "interpretation": "implementation check only; not evidence that relational features should improve real CMS prediction",
        "execution": {
            "source_commit": _source_commit(),
            "started_at_utc": started_at_utc,
            "model_config": {
                "cutoff": args.cutoff.isoformat(),
                "seeds": [301, 302, 303],
                "betas": [0.0, 2.5],
            },
            "source_snapshot": manifest["cms"]["snapshot"],
        },
        "rows": rows,
    }
    result["execution"]["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
