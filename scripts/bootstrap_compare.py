"""Estimate a paired, entity-clustered difference from prediction rows.

Input JSON is a list of objects containing ``cluster``, ``label``, ``score_a``,
and ``score_b``. The command intentionally does not infer clinical negatives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from healthgraphbench.evaluation.bootstrap import paired_cluster_bootstrap
from healthgraphbench.evaluation.metrics import average_precision, ranking_auc


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

def _metric(rows: list[dict[str, Any]], score_key: str, metric: str) -> float:
    labels = [int(row["label"]) for row in rows]
    scores = [float(row[score_key]) for row in rows]
    if metric == "auc":
        value = ranking_auc(labels, scores)
    elif metric == "ap":
        value = average_precision(labels, scores)
    elif metric == "brier":
        value = sum((score - label) ** 2 for score, label in zip(scores, labels, strict=True)) / len(rows)
    else:
        raise ValueError(f"unsupported metric {metric!r}")
    if value is None:
        raise ValueError(f"{metric} is undefined for the supplied sample")
    return value


def _assert_new_output(output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=_repo_root() / "data" / "manifests" / "v0.1.json")
    parser.add_argument("--metric", choices=("auc", "ap", "brier"), required=True)
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    _assert_new_output(args.output)
    started_at_utc = datetime.now(timezone.utc).isoformat()
    rows = json.loads(args.input.read_text(encoding="utf-8"))

    def difference(sample: list[dict[str, Any]]) -> float:
        return _metric(sample, "score_b", args.metric) - _metric(sample, "score_a", args.metric)

    interval = paired_cluster_bootstrap(
        rows,
        lambda row: str(row["cluster"]),
        difference,
        resamples=args.resamples,
        seed=args.seed,
    )
    result = interval.as_dict()
    result["execution"] = {
        "source_commit": _source_commit(),
        "manifest_sha256": _sha256_file(args.manifest),
        "input_sha256": _sha256_file(args.input),
        "started_at_utc": started_at_utc,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_config": {
            "metric": args.metric,
            "resamples": args.resamples,
            "seed": args.seed,
            "cluster_field": "cluster",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
