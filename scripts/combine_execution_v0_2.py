"""Combine immutable v0.1 references with the admitted Part D result."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any



def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _artifact(path: Path, *, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maude", type=Path, default=Path("results/maude_execution_v0_1_20260915.json"))
    parser.add_argument("--cms", type=Path, default=Path("results/cms_execution_v0_1_20260915.json"))
    parser.add_argument("--partd", type=Path, default=Path("results/partd_execution_v0_2_20260916.json"))
    parser.add_argument("--controls", type=Path, default=Path("results/synthetic_controls_execution_v0_1_20260915.json"))
    parser.add_argument("--summary", type=Path, default=Path("results/benchmark_summary_v0_2.json"))
    parser.add_argument("--analysis", type=Path, default=Path("results/relational_value_v0_2.json"))
    parser.add_argument("--contract", type=Path, default=Path("configs/task_contract_v0_2.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite an existing execution index: {args.output}")
    paths = {
        "maude": args.maude,
        "cms_nursing": args.cms,
        "partd_prescriber_drug": args.partd,
        "controls": args.controls,
        "summary": args.summary,
        "analysis": args.analysis,
        "contract": args.contract,
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing v0.2 input(s): " + ", ".join(missing))
    maude = _read_object(args.maude)
    cms = _read_object(args.cms)
    partd = _read_object(args.partd)
    if maude.get("benchmark_version") != "0.1" or cms.get("benchmark_version") != "0.1":
        raise ValueError("MAUDE and CMS inputs must remain v0.1 task artifacts")
    if partd.get("benchmark_version") != "0.2" or partd.get("task") != "partd_prescriber_drug":
        raise ValueError("Part D input must be the admitted v0.2 task artifact")
    result = {
        "benchmark_version": "0.2",
        "result_status": "admitted_replication_extension",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "immutability_statement": "v0.1 MAUDE, CMS, controls, and result payloads are referenced without modification.",
        "task_artifacts": {
            "maude": _artifact(args.maude, kind="frozen_v0_1_task_result"),
            "cms_nursing": _artifact(args.cms, kind="frozen_v0_1_task_result"),
            "partd_prescriber_drug": _artifact(args.partd, kind="v0_2_admitted_task_result"),
        },
        "controls": _artifact(args.controls, kind="frozen_v0_1_controls"),
        "summary": _artifact(args.summary, kind="v0_2_unified_cross_task_table"),
        "analysis": _artifact(args.analysis, kind="v0_2_cross_task_relational_value"),
        "contract": _artifact(args.contract, kind="v0_2_admission_contract"),
        "method_suite": {
            "maude": [item["method"] for item in maude["tasks"][0]["methods"]],
            "cms_nursing": [item["method"] for item in cms["tasks"][0]["methods"]],
            "partd_prescriber_drug": [item["method"] for item in partd["methods"]],
            "architecture_sweep": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
