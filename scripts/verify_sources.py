"""Verify user-managed raw source files against the v0.1 manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from healthgraphbench.data import load_manifest, verify_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    for task_name in ("maude", "cms"):
        entries = manifest[task_name]["files"]
        root = args.data_root / task_name
        verify_files(root, entries)
        print(f"verified {task_name}: {len(entries)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
