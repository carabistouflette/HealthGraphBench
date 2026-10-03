"""Run the protocol-locked raw-data MAUDE Q2 comparison."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from healthgraphbench.q2.maude import main


if __name__ == "__main__":
    raise SystemExit(main())
