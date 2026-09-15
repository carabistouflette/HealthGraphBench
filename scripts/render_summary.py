"""Render final benchmark tables and a dependency-free SVG summary plot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


MAUDE_METRICS = ("recall_at_10", "macro_recall_at_10", "mrr")
CMS_METRICS = ("roc_auc", "average_precision", "brier")


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


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object result: {path}")
    return value


def _task(result: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    return next(item for item in result["tasks"] if item["task"] == name)


def _maude_rows(task: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for method in task["methods"]:
        metrics = method["test"]["thresholds"]["1"]
        rows.append(
            {
                "task": "maude",
                "method": method["method"],
                "recall_at_10": metrics["recall_at_10"],
                "macro_recall_at_10": metrics["macro_recall_at_10"],
                "mrr": metrics["mrr"],
            }
        )
    return rows


def _cms_rows(task: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for method in task["methods"]:
        metrics = method["test"]
        rows.append(
            {
                "task": "cms_nursing",
                "method": method["method"],
                "roc_auc": metrics["roc_auc"],
                "average_precision": metrics["average_precision"],
                "brier": metrics["brier"],
            }
        )
    return rows


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = ("task", "method", "metric", "value")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            for metric in MAUDE_METRICS if row["task"] == "maude" else CMS_METRICS:
                writer.writerow(
                    {
                        "task": row["task"],
                        "method": row["method"],
                        "metric": metric,
                        "value": row[metric],
                    }
                )


def _bar_panel(
    rows: Sequence[Mapping[str, Any]],
    metric: str,
    title: str,
    x: int,
    y: int,
    width: int,
    height: int,
) -> list[str]:
    labels = [str(row["method"]) for row in rows]
    values = [float(row[metric]) for row in rows]
    maximum = max(values) if values else 1.0
    maximum = max(maximum * 1.15, 0.1)
    baseline = y + height
    bar_width = width / max(1, len(rows)) * 0.68
    gap = width / max(1, len(rows))
    lines = [
        f'<text x="{x}" y="{y - 18}" class="title">{html.escape(title)}</text>',
        f'<line x1="{x}" y1="{baseline}" x2="{x + width}" y2="{baseline}" class="axis"/>',
        f'<line x1="{x}" y1="{y}" x2="{x}" y2="{baseline}" class="axis"/>',
        f'<text x="{x - 8}" y="{baseline + 4}" text-anchor="end" class="tick">0</text>',
        f'<text x="{x - 8}" y="{y + 4}" text-anchor="end" class="tick">{maximum:.2f}</text>',
    ]
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        bar_height = value / maximum * height
        bar_x = x + index * gap + (gap - bar_width) / 2
        bar_y = baseline - bar_height
        color = "#b23a48" if "graphsage" in label else "#3973ac"
        lines.append(
            f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}"/>'
        )
        lines.append(
            f'<text x="{bar_x + bar_width / 2:.1f}" y="{bar_y - 5:.1f}" text-anchor="middle" class="value">{value:.3f}</text>'
        )
        lines.append(
            f'<text x="{bar_x + bar_width / 2:.1f}" y="{baseline + 18}" text-anchor="end" transform="rotate(-35 {bar_x + bar_width / 2:.1f} {baseline + 18})" class="label">{html.escape(label)}</text>'
        )
    return lines


def _write_svg(path: Path, maude: Sequence[Mapping[str, Any]], cms: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="760" viewBox="0 0 1400 760">',
        '<style>.title{font:700 18px sans-serif}.axis{stroke:#333}.tick,.label,.value{font:12px sans-serif}.value{font-weight:700}</style>',
        '<rect width="1400" height="760" fill="white"/>',
        '<text x="40" y="34" class="title">HealthGraphBench v0.1 — frozen exploratory temporal evaluation</text>',
    ]
    lines.extend(_bar_panel(maude, "recall_at_10", "MAUDE test Recall@10", 80, 100, 560, 420))
    lines.extend(_bar_panel(cms, "roc_auc", "CMS test ROC AUC", 760, 100, 560, 420))
    lines.extend(
        [
            '<text x="80" y="620" class="tick">MAUDE: threshold=1 aggregate; higher is better.</text>',
            '<text x="760" y="620" class="tick">CMS: pooled 2024–2025 test predictions; higher is better.</text>',
            '<text x="80" y="650" class="tick">GraphSAGE is the sole learned message-passing model; no architecture sweep.</text>',
            '<text x="80" y="680" class="tick">Results are development-stage exploratory temporal evaluations, not confirmatory clinical claims.</text>',
            '</svg>',
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=_repo_root() / "data" / "manifests" / "v0.1.json")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-svg", type=Path, required=True)
    args = parser.parse_args()
    outputs = (args.output_json, args.output_csv, args.output_svg)
    if any(path.exists() for path in outputs):
        raise FileExistsError("refusing to overwrite an existing summary artifact")
    started_at_utc = datetime.now(timezone.utc).isoformat()
    result = _read_object(args.input)
    maude_task = _task(result, "maude")
    cms_task = _task(result, "cms_nursing")
    maude_rows = _maude_rows(maude_task)
    cms_rows = _cms_rows(cms_task)
    summary = {
        "summary_kind": "frozen_benchmark_summary",
        "benchmark_version": "0.1",
        "suite_status": "frozen",
        "interpretation": "development-stage held-out temporal evaluation; test periods were inspected during feasibility work",
        "model_suite": {
            "status": "frozen",
            "architecture_sweep": False,
            "maude": [row["method"] for row in maude_rows],
            "cms_nursing": [row["method"] for row in cms_rows],
            "learned_message_passing_models": ["graphsage_link_prediction"],
        },
        "execution": {
            "source_commit": _source_commit(),
            "manifest_sha256": _sha256_file(args.manifest),
            "input_sha256": _sha256_file(args.input),
            "started_at_utc": started_at_utc,
            "model_config": {
                "maude_metric_scope": "test threshold=1",
                "cms_metric_scope": "pooled 2024-2025 test",
                "graphsage_seed_semantics": "deterministic; seed null",
            },
        },
        "maude": {
            "metric_scope": "test threshold=1",
            "rows": maude_rows,
            "primary_metric_bootstrap": result["analysis"]["maude"]["primary_metric_bootstrap"],
        },
        "cms_nursing": {
            "metric_scope": "pooled 2024-2025 test",
            "rows": cms_rows,
            "primary_metric_bootstrap": result["analysis"]["cms_nursing"]["primary_metric_bootstrap"],
        },
        "controls": result["controls"]["rows"],
    }
    csv_rows = [*maude_rows, *cms_rows]
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_svg.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_csv, csv_rows)
    _write_svg(args.output_svg, maude_rows, cms_rows)
    summary["execution"]["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    args.output_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output_json}, {args.output_csv}, and {args.output_svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
