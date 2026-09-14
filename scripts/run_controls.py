"""Run the real-topology positive and zero-signal CMS controls."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from healthgraphbench import load_task
from healthgraphbench.controls import run_topology_controls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--cutoff", type=date.fromisoformat, default=date(2024, 1, 1))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    task = load_task("cms_nursing", args.data_root)
    rows = run_topology_controls(task.prepared.current_records, cutoff=args.cutoff)
    result = {
        "benchmark_version": "0.1",
        "task": "cms_nursing",
        "control_type": "synthetic node labels on real pre-cutoff ownership topology",
        "interpretation": "implementation check only; not evidence that relational features should improve real CMS prediction",
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
