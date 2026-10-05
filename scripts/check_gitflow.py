"""Check branch names and pull-request directions for the repository Gitflow."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


_BRANCH = re.compile(r"(feature|fix|chore|release|hotfix)/[a-z0-9]+(?:[.-][a-z0-9]+)*")


def _branch_kind(branch: str) -> str | None:
    match = _BRANCH.fullmatch(branch)
    return match.group(1) if match else None


def _policy_error(base: str, head: str) -> str | None:
    if base == head:
        return "source and target must differ"
    if base == "develop" and head == "main":
        return None

    head_kind = _branch_kind(head)
    if head_kind is None:
        return "use feature/, fix/, chore/, release/ or hotfix/ with a lowercase name"

    if base == "main":
        if head_kind not in {"release", "hotfix"}:
            return "main only accepts release/ or hotfix/ branches"
    elif base == "develop":
        return None
    elif _branch_kind(base) == "release":
        if head_kind not in {"fix", "chore", "hotfix"}:
            return "a release only accepts stabilization fixes, chores and hotfix backports"
    elif _branch_kind(base) == "hotfix":
        if head_kind not in {"fix", "chore"}:
            return "a hotfix only accepts fixes and chores"
    else:
        return "target main, develop, release/<id> or hotfix/<id>"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="target branch")
    parser.add_argument("--head", help="source branch")
    parser.add_argument("--event", type=Path, help="GitHub pull_request event JSON")
    args = parser.parse_args()

    if args.event is not None:
        if args.base is not None or args.head is not None:
            parser.error("--event cannot be combined with --base or --head")
        try:
            with args.event.open(encoding="utf-8") as handle:
                pull_request = json.load(handle)["pull_request"]
            base = pull_request["base"]["ref"]
            head = pull_request["head"]["ref"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.error(f"cannot read pull-request event: {error}")
        if not isinstance(base, str) or not isinstance(head, str):
            parser.error("pull-request base and head refs must be strings")
    else:
        if args.base is None or args.head is None:
            parser.error("provide --base and --head, or --event")
        base, head = args.base, args.head

    error = _policy_error(base, head)
    if error is not None:
        print(f"Gitflow: {head} -> {base}: refused ({error})", file=sys.stderr)
        return 1
    print(f"Gitflow: {head} -> {base}: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
