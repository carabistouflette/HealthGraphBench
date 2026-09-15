"""Rebuild both v0.1 tasks and regenerate the exploratory result table."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from healthgraphbench import load_task
from healthgraphbench.data import load_manifest, sha256_file, verify_files
from healthgraphbench.models import (
    BprNeighborAverage,
    BoostedStumps,
    FacilityHistory,
    GlobalPopularity,
    GraphSageLinkPrediction,
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
        GraphSageLinkPrediction,
    ),
    "cms_nursing": (Prevalence, FacilityHistory, OwnershipAggregates),
}


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_specs(selected: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {
            "task": task_name,
            "method": model_type().name,
            "wrapper": model_type.__name__,
            "seed": None,
            "deterministic": True,
        }
        for task_name in selected
        for model_type in TASK_MODELS[task_name]
    ]


def _run_task(task_name: str, data_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    manifest_name = "cms" if task_name == "cms_nursing" else task_name
    verified_files = verify_files(data_root / manifest_name, manifest[manifest_name]["files"])
    task = load_task(task_name, data_root)
    train, validation, test = (
        task.get_split("train"),
        task.get_split("validation"),
        task.get_split("test"),
    )
    methods = []
    for model_type in TASK_MODELS[task_name]:
        model = model_type()
        predictions = model.fit_predict(train, validation, test)
        method_result: dict[str, Any] = {
            "method": model.name,
            "test": task.evaluate(predictions),
        }
        if task_name == "maude" and predictions.payload.get("quarters") is not None:
            method_result["quarters"] = predictions.payload["quarters"]
        if task_name == "maude" and predictions.payload.get("entity_metrics") is not None:
            method_result["entity_metrics"] = predictions.payload["entity_metrics"]
        if task_name == "cms_nursing" or model.name in {
            "neighbor_frequency",
            "graph_message_passing_bpr",
            "graphsage_link_prediction",
        }:
            prediction_rows = predictions.payload.get("predictions")
            if prediction_rows is None:
                prediction_rows = predictions.payload.get("prediction_rows")
            if prediction_rows is not None:
                method_result["prediction_rows"] = prediction_rows
        methods.append(method_result)
    return {
        "task": task_name,
        "contract": task.manifest(),
        "source_files": verified_files,
        "methods": methods,
    }


def _assert_new_output(output: Path) -> None:
    frozen = {
        _repo_root() / "results" / "exploratory_v0_1.json",
        _repo_root() / "results" / "maude_exploratory_v0_1.json",
        _repo_root() / "results" / "cms_exploratory_v0_1.json",
    }
    resolved = output.resolve()
    if resolved in {path.resolve() for path in frozen}:
        raise ValueError(f"frozen exploratory result path is immutable: {output}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--task", choices=("maude", "cms_nursing", "all"), default="all")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    _assert_new_output(args.output)
    manifest_path = args.manifest or _repo_root() / "data" / "manifests" / "v0.1.json"
    manifest = load_manifest(manifest_path)
    selected = ("maude", "cms_nursing") if args.task == "all" else (args.task,)
    started_at = _utc_now()
    result = {
        "benchmark_version": manifest["benchmark_version"],
        "result_status": "exploratory_benchmark_development",
        "execution": {
            "source_commit": _source_commit(),
            "manifest_sha256": sha256_file(manifest_path),
            "started_at_utc": started_at,
            "models": _model_specs(selected),
        },
        "tasks": [_run_task(name, args.data_root, manifest) for name in selected],
    }
    result["execution"]["finished_at_utc"] = _utc_now()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


