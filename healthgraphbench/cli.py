"""Small command-line entrypoint for inspecting a loaded task."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import load_task


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=("maude", "cms_nursing"))
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    task = load_task(args.task, args.data_root)
    print(json.dumps(task.manifest(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
