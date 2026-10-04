"""Build a Part D execution record from verified raw CMS snapshots."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Type

from healthgraphbench import load_task
from healthgraphbench.core import BenchmarkModel
from healthgraphbench.models import (
    HistoryOverlap,
    PartDGraphBpr,
    PartDTabularLogistic,
    SpecialtyPopularity,
)

MODEL_TYPES: tuple[Type[BenchmarkModel], ...] = (
    SpecialtyPopularity,
    HistoryOverlap,
    PartDTabularLogistic,
    PartDGraphBpr,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_new_output(output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {output}")


def _method_record(
    task: Any,
    model_type: Type[BenchmarkModel],
    splits: tuple[Any, ...],
) -> dict[str, Any]:
    prediction = model_type().fit_predict(*splits)
    return {
        "method": prediction.method,
        "representation": prediction.payload["representation"],
        "validation": prediction.payload["validation"],
        "test": task.evaluate(prediction),
        "pooled_provider_year": prediction.payload["pooled_provider_year"],
        "prediction_rows": len(prediction.payload["predictions"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--preparation-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract", type=Path)
    args = parser.parse_args()
    _assert_new_output(args.output)
    preparation_output = args.preparation_output or args.output.with_name(
        f"{args.output.name}.prepared"
    )
    _assert_new_output(preparation_output)
    task = load_task(
        "partd_prescriber_drug",
        args.source_root,
        manifest_path=args.manifest,
        preparation_dir=preparation_output,
        contract_path=args.contract,
    )
    splits = (task.get_split("train"), task.get_split("validation"), task.get_split("test"))
    result = {
        "benchmark_version": "0.2",
        "result_status": "raw_partd_execution",
        "execution": {
            "started_at_utc": _utc_now(),
            "model_interface": "healthgraphbench.core.BenchmarkTask",
            "model_wrappers": [model_type.__name__ for model_type in MODEL_TYPES],
            "deterministic": True,
        },
        "task": task.name,
        "contract": task.manifest(),
        "source_files": task.source_manifest(),
        "preparation": {
            "directory": str(preparation_output),
            "record_kind": task.report["record_kind"],
        },
        "methods": [_method_record(task, model_type, splits) for model_type in MODEL_TYPES],
    }
    result["execution"]["finished_at_utc"] = _utc_now()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
