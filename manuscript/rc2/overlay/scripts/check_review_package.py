#!/usr/bin/env python3
"""Verify the RC2 delivery, retained scientific bytes and completed C/D1 numbers.

No training, bootstrap, raw acquisition or successful scientific audit is rerun.
A pass is not author approval, independent confirmation or submission readiness.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import math
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-manifest', action='store_true', help='Use only after rebuilding in a copy')
    args = parser.parse_args()
    checks = []

    def check(name, passed, detail=None):
        checks.append({'check': name, 'passed': bool(passed), 'detail': detail})

    release = json.loads((ROOT / 'release.json').read_text())
    provenance = json.loads((ROOT / 'provenance.json').read_text())
    status = json.loads((ROOT / release['current_scientific_status']).read_text())
    check('package_identity', release['package_id'] == 'manuscript-rc2'
          and release['release_candidate'] == provenance['revision'] == status['revision'] == 'RC2'
          and (ROOT / 'VERSION').read_text().strip() == release['package_id'])
    check('parent_preserved', release['parent_archive'] == provenance['parent_archive']
          and provenance['parent_archive']['modified'] is False)
    check('no_approval_invented', all(release['readiness'][key] is False for key in
          ('author_validation_complete', 'ready_for_submission', 'editorial_acceptance_claimed')))
    check('no_manuscript_doi_or_tag', release['manuscript_package_DOI'] is None and not release['tag_created'])
    check('benchmark_identity', release['benchmark']['declared_DOI'] == '10.5281/zenodo.22796551'
          and release['benchmark']['version'] == '0.2.0' and not release['benchmark']['modified'])
    check('operations_consistent', status['current_operations'] == provenance['current_operations'])
    protected = json.loads((ROOT / 'release/protected_payload.json').read_text())
    check('retention_parent', protected['parent_archive_sha256'] == release['parent_archive']['sha256'])
    for name, expected in protected['files'].items():
        path = ROOT / name
        check('retained:' + name, path.is_file() and digest(path) == expected)
    metrics = json.loads((ROOT / 'data/post_rc1/post_rc1_metrics.json').read_text())
    for key in ('C', 'D1'):
        source = provenance['post_rc1_code_and_evidence'][key]
        check('source_manifest:' + key, digest(ROOT / source['manifest']) == source['manifest_sha256']
              == metrics[key]['source_manifest_sha256'])
    rows = metrics['D1']['primary_results']
    for row in rows:
        den = row['positive_edges']
        for variant in ('mean', 'none'):
            check('hits_ratio:' + row['period'] + ':' + variant,
                  den > 0 and 0 <= row[variant + '_hits10'] <= den
                  and math.isclose(row[variant + '_r10'], row[variant + '_hits10'] / den,
                                   rel_tol=0, abs_tol=1e-12))
        check('signed_contrast:' + row['period'], math.isclose(
              row['mean_minus_none'], row['mean_r10'] - row['none_r10'], rel_tol=0, abs_tol=1e-12))
    annual = [row for row in rows if row['period'] in ('2024', '2025')]
    pooled = next(row for row in rows if row['period'] == 'pooled2024_2025')
    for field in ('positive_edges', 'products', 'mean_hits10', 'none_hits10'):
        check('pooled_counts:' + field, pooled[field] == sum(row[field] for row in annual))
    for key in ('C', 'D1'):
        audit = json.loads((ROOT / f'verification/post_rc1/{key}_numeric_audit.json').read_text())
        check('retained_audit_zero_discrepancy:' + key, audit['discrepancies']['count'] == 0, 'Received completed audit; not rerun')
    reserve = provenance['rss_audit_reserve']
    check('audit_rss_reserve', reserve['ru_maxrss_bytes'] > 512 * 1024 ** 2
          and not reserve['global_audit_RSS_below_512MiB_certified']
          and not reserve['certain_peak_cause_claimed'])
    index = json.loads((ROOT / 'data/post_rc1/checkpoint_index.json').read_text())
    for row in index['checkpoints']:
        path = ROOT / row['path']
        check('checkpoint_bytes:' + row['path'], digest(path) == row['sha256'])
        checkpoint = json.loads(gzip.decompress(path.read_bytes()))
        check('checkpoint_inference_only:' + row['path'], checkpoint['resume_supported'] is False)
    pdfs = []
    for document in release['documents']:
        path = ROOT / document['pdf']
        try:
            text = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True,
                                  capture_output=True, text=True).stdout
            info = subprocess.run(['pdfinfo', str(path)], check=True, capture_output=True, text=True).stdout
            pages = int(next(line.split(':', 1)[1] for line in info.splitlines() if line.startswith('Pages:')))
            check('pdf_resolved:' + path.name, '??' not in text and '\ufffd' not in text)
            pdfs.append({'file': path.name, 'pages': pages, 'sha256': digest(path)})
        except (OSError, subprocess.SubprocessError, ValueError, StopIteration) as exc:
            check('pdf_readable:' + path.name, False, str(exc))
    if not args.skip_manifest:
        listed = set()
        for line in (ROOT / 'SHA256SUMS').read_text().splitlines():
            expected, name = line.split(None, 1)
            name = name.lstrip('*')
            listed.add(name)
            path = ROOT / name
            check('manifest:' + name, path.is_file() and digest(path) == expected)
        actual = {str(path.relative_to(ROOT)) for path in ROOT.rglob('*') if path.is_file()
                  and '__pycache__' not in path.parts and path != ROOT / 'SHA256SUMS'}
        check('manifest_complete', actual == listed,
              {'unlisted': sorted(actual - listed), 'missing': sorted(listed - actual)})
    report = {'revision': 'RC2', 'passed': all(row['passed'] for row in checks),
              'ready_for_submission': False, 'manifest_skipped': args.skip_manifest,
              'scope': 'Delivery integrity and arithmetic on retained results; no fits or scientific audits rerun',
              'checks': checks, 'pdfs': pdfs}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
