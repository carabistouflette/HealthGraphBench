"""Run or evaluate the sealed prospective Part D Q2 forecast."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from healthgraphbench.q2.common import DEFAULT_LIMITS
from healthgraphbench.q2.prospective_partd import evaluate_forecast, run_forecast


def _add_forecast_limits(parser: argparse.ArgumentParser) -> None:
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    forecast = commands.add_parser("forecast", help="capture history and seal a prospective forecast")
    forecast.add_argument("--source-root", type=Path, required=True)
    forecast.add_argument("--comparison-dir", type=Path, required=True)
    forecast.add_argument("--protocol", type=Path, required=True)
    forecast.add_argument("--protocol-sha256", required=True)
    forecast.add_argument("--output-dir", type=Path, required=True)
    _add_forecast_limits(forecast)

    evaluate = commands.add_parser("evaluate", help="evaluate a sealed forecast against official 2025 source")
    evaluate.add_argument("--origin-dir", type=Path, required=True)
    evaluate.add_argument("--target-source", type=Path, required=True)
    evaluate.add_argument("--target-manifest", type=Path, required=True)
    evaluate.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "forecast":
        limits = {
            "timeout_seconds": args.timeout_seconds,
            "max_rss_bytes": args.max_rss_bytes,
            "max_output_bytes": args.max_output_bytes,
            "family_validation_wall_seconds": args.family_validation_wall_seconds,
            "run_wall_seconds": args.run_wall_seconds,
            "total_output_bytes": args.total_output_bytes,
        }
        result = run_forecast(
            args.source_root,
            args.comparison_dir,
            args.output_dir,
            args.protocol,
            args.protocol_sha256,
            limits=limits,
        )
    else:
        result = evaluate_forecast(
            args.origin_dir,
            args.target_source,
            args.target_manifest,
            args.output_dir,
        )
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
