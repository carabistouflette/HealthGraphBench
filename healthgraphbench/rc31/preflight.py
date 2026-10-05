"""Exercise the new synthetic surfaces without health scoring or historic audits."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path

from . import analysis, cms, maude, partd


def run(protocol_path: Path, output_path: Path) -> dict:
    if output_path.exists():
        raise FileExistsError('Preflight evidence must be new')
    protocol = json.loads(protocol_path.read_text())
    report = {
        'schema': 'healthgraphbench.rc31-preflight.v1',
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'protocol_sha256': hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        'partd': partd.preflight(), 'maude': maude.preflight(),
        'cms': cms.preflight(), 'analysis': analysis.preflight(),
        'packages': {name: importlib.metadata.version(name) for name in ('numpy', 'scipy', 'scikit-learn', 'numba', 'llvmlite')},
        'source_sha256': {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in protocol['locked_sources']},
        'health_fit_or_score_performed': False,
        'historical_audits_reexecuted': False,
        'scope': 'New neighbor/adapter/reassignment/checkpoint/denominator paths exercised on synthetic inputs; old exact-gradient proofs are reused, not re-audited.',
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.protocol, args.output)
    print(json.dumps({'protocol_sha256': report['protocol_sha256'],
                      'health_fit_or_score_performed': False, 'new_surface_preflight_passed': True}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
