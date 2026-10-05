"""Fresh metadata-only availability check; never opens target outcomes or forecasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..q2.common import RunBudget
from ..q2.prospective_partd import _capture_catalog


def run_check(protocol_path: Path, output_dir: Path) -> dict:
    protocol = json.loads(Path(protocol_path).read_text())
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError('Availability evidence directory must be new')
    output_dir.mkdir(parents=True)
    budget = RunBudget(output_dir, protocol['limits'])
    phase = output_dir / 'catalog'
    url = protocol['independent_evaluation']['official_catalog_metadata_url']
    budget.execute(_capture_catalog, (url,), phase)
    capture = json.loads((phase / 'result.json').read_text())
    response = json.loads((phase / capture['response_file']).read_text())
    versions = [node.get('attributes', {}).get('field_dataset_version') for node in response.get('data', [])]
    report = {
        'schema': 'healthgraphbench.rc31-availability.v1', 'catalog_capture': capture,
        'observed_dataset_versions': versions,
        'official_target_2025_listed_in_captured_response': capture['service_2025_officially_listed'],
        'target_outcomes_downloaded_or_opened': False, 'target_metrics_calculated': False,
        'old_forecast_protocol_origin_scores_modified': False,
        'human_nonconsultation_attestations': 'unknown', 'external_human_reproduction': 'not_performed',
        'independent_evaluation_completed': False,
        'blocking_prerequisites': ['official real target source and verified file provenance',
                                   'actual human nonconsultation/usage attestations',
                                   'actual independent intervention and record'],
        'interpretation': 'Absence applies to this filtered official response at its captured instant, not all public/private sources. A service year is not an origin-availability proof.',
        'resource_ledger': str(output_dir / 'resource_ledger.json'),
    }
    (output_dir / 'availability.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_check(args.protocol, args.output_dir), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
