"""Estimate a paired, entity-clustered difference from prediction rows.

Input JSON is a list of objects containing ``cluster``, ``label``, ``score_a``,
and ``score_b``. The command intentionally does not infer clinical negatives.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from healthgraphbench.evaluation.bootstrap import paired_cluster_bootstrap
from healthgraphbench.evaluation.metrics import average_precision, ranking_auc


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--metric", choices=("auc", "ap", "brier"), required=True)
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(interval.as_dict(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
