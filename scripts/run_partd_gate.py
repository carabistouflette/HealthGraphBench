"""Run the CMS Medicare Part D feasibility gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from healthgraphbench.candidates.partd import run_gate


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cohort-size", type=_positive_int, default=2000)
    args = parser.parse_args()
    try:
        run_gate(
            args.source_root,
            args.manifest,
            args.output_dir,
            cohort_size=args.cohort_size,
        )
    except Exception as exc:
        print(f"Part D gate failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {args.output_dir / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
