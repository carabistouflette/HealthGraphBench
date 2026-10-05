"""Run the wheel-isolated external Part D reuse demonstration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from healthgraphbench.q2.reuse import run_demonstration


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reuse-python", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--max-rss-bytes", type=int)
    parser.add_argument("--max-output-bytes", type=int)
    parser.add_argument("--family-validation-wall-seconds", type=int)
    parser.add_argument("--run-wall-seconds", type=int)
    parser.add_argument("--total-output-bytes", type=int)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    names = {
        "timeout_seconds": args.timeout_seconds,
        "max_rss_bytes": args.max_rss_bytes,
        "max_output_bytes": args.max_output_bytes,
        "family_validation_wall_seconds": args.family_validation_wall_seconds,
        "run_wall_seconds": args.run_wall_seconds,
        "total_output_bytes": args.total_output_bytes,
    }
    limits: dict[str, Any] = {name: value for name, value in names.items() if value is not None}
    result = run_demonstration(
        args.source_root,
        args.output_dir,
        args.protocol,
        args.protocol_sha256,
        args.reuse_python,
        limits=limits or None,
    )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
