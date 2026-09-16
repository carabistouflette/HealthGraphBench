"""Run the bounded CMS Medicare Part D learned-model gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from healthgraphbench.candidates.partd_model import run_model_gate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feasibility-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        run_model_gate(args.feasibility_dir, args.output_dir)
    except Exception as exc:
        print(f"Part D model gate failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {args.output_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
