"""Rebuild both v0.1 tasks and regenerate the exploratory result table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from healthgraphbench import load_task
from healthgraphbench.data import load_manifest, verify_files
from healthgraphbench.models import (
    BprNeighborAverage,
    BoostedStumps,
    FacilityHistory,
    GlobalPopularity,
    LogisticTabular,
    NeighborFrequency,
    OwnershipAggregates,
    Prevalence,
    SpectralFactorization,
)


TASK_MODELS = {
    "maude": (
        GlobalPopularity,
        NeighborFrequency,
        LogisticTabular,
        BoostedStumps,
        SpectralFactorization,
        BprNeighborAverage,
    ),
    "cms_nursing": (Prevalence, FacilityHistory, OwnershipAggregates),
}


def _run_task(task_name: str, data_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    manifest_name = "cms" if task_name == "cms_nursing" else task_name
    verify_files(data_root / manifest_name, manifest[manifest_name]["files"])
    task = load_task(task_name, data_root)
    train, validation, test = task.train(), task.validation(), task.test()
    methods = []
    for model_type in TASK_MODELS[task_name]:
        model = model_type()
        predictions = model.fit_predict(train, validation, test)
        methods.append({"method": model.name, "test": task.evaluate(predictions)})
    return {"task": task_name, "contract": task.manifest(), "methods": methods}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--task", choices=("maude", "cms_nursing", "all"), default="all")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    selected = ("maude", "cms_nursing") if args.task == "all" else (args.task,)
    result = {
        "benchmark_version": manifest["benchmark_version"],
        "result_status": "exploratory_benchmark_development",
        "tasks": [_run_task(name, args.data_root, manifest) for name in selected],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
