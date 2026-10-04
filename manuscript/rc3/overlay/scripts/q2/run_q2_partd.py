"""Run the supervised Part D Q2 comparison from raw CMS snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from healthgraphbench.q2.common import DEFAULT_LIMITS
from healthgraphbench.q2.partd import run_comparison


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prepared-input", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_LIMITS["timeout_seconds"])
    parser.add_argument("--max-rss-bytes", type=int, default=DEFAULT_LIMITS["max_rss_bytes"])
    parser.add_argument("--max-output-bytes", type=int, default=DEFAULT_LIMITS["max_output_bytes"])
    parser.add_argument(
        "--family-validation-wall-seconds",
        type=int,
        default=DEFAULT_LIMITS["family_validation_wall_seconds"],
    )
    parser.add_argument("--run-wall-seconds", type=int, default=DEFAULT_LIMITS["run_wall_seconds"])
    parser.add_argument("--total-output-bytes", type=int, default=DEFAULT_LIMITS["total_output_bytes"])
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    limits = {
        "timeout_seconds": args.timeout_seconds,
        "max_rss_bytes": args.max_rss_bytes,
        "max_output_bytes": args.max_output_bytes,
        "family_validation_wall_seconds": args.family_validation_wall_seconds,
        "run_wall_seconds": args.run_wall_seconds,
        "total_output_bytes": args.total_output_bytes,
    }
    result = run_comparison(
        args.source_root,
        args.output_dir,
        args.protocol,
        args.protocol_sha256,
        limits=limits,
        prepared_input=args.prepared_input,
    )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
