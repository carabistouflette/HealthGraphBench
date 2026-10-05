#!/usr/bin/env python3
"""Deterministic RC3.1 numeric/source/integrity QA, not a historic scientific audit."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from render_assets import INPUTS, LIMITS, DOI, consume, derive, digest, load, plot_specs, tables

DOCUMENTS = ('main_fr', 'main_en', 'supplement_fr', 'supplement_en')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative(name):
    path = PurePosixPath(name)
    require(bool(path.parts) and not path.is_absolute() and '..' not in path.parts and '\\' not in name, 'Unsafe package path: ' + name)
    return Path(*path.parts)


def check_assets(assets, run_root):
    assets, run_root = Path(assets), Path(run_root)
    data = consume(run_root)
    manifest = load(assets / 'asset_manifest.json')
    require(manifest['revision'] == 'RC3.1' and manifest['limits'] == LIMITS, 'Asset readiness/limits changed')
    require(manifest['benchmark_doi'] == DOI and manifest['doi_scope'] == 'benchmark v0.2.0 only', 'DOI scope changed')
    require(manifest['training_seed_ranges_are_confidence_intervals'] is False and
            manifest['conditional_intervals_cover_selection_or_period_independence'] is False, 'Uncertainty limits changed')
    require(manifest['inputs'] == {name: digest(run_root / name) for name in INPUTS}, 'Actual input hashes changed')
    require(manifest['scientific_sources'] == data['source_provenance.json']['source_sha256'], 'Source consumption record changed')
    require(manifest['renderer_sha256'] == digest(Path(__file__).with_name('render_assets.py')), 'Renderer differs from recorded source')
    records = derive(data)
    require(load(assets / 'numeric_records.json') == records, 'Numeric records not derived from actual JSON')
    require(load(assets / 'plot_records.json') == plot_specs(records), 'Plot points not derived from actual JSON')
    for lang in ('fr', 'en'):
        for name, text in tables(records, lang).items():
            require((assets / 'tables' / name).read_text(encoding='utf-8') == text, 'Actual numeric table mismatch: ' + name)
    expected_plots = {f"figures/{spec['name']}_{lang}.pdf" for spec in plot_specs(records) for lang in ('fr', 'en')}
    require(expected_plots <= set(manifest['outputs']), 'Missing actual-data plots')
    actual_outputs = {path.relative_to(assets).as_posix() for path in assets.rglob('*') if path.is_file() and path.name != 'asset_manifest.json'}
    require(actual_outputs == set(manifest['outputs']), 'Assets inventory changed')
    for name, sha in manifest['outputs'].items():
        require(digest(assets / relative(name)) == sha, 'Numeric asset hash mismatch: ' + name)
    return data


def check(root, sealed=False):
    root = Path(root)
    require(root.name == 'HealthGraphBench_RC3_1', 'Wrong RC3.1 root')
    data = check_assets(root / 'assets/rc31', root / 'data/rc31')
    release = load(root / 'release.json')
    require(release['revision'] == 'RC3.1' and release['scientific_gates'] == LIMITS, 'Readiness/gates mismatch')
    require(release['benchmark_doi'] == DOI and release['doi_scope'] == 'benchmark v0.2.0 only', 'Package DOI scope changed')
    require(release['evidence_scope'] == 'compact evidence and pinned external full-output/input paths; not self-contained raw data', 'False raw-data completeness claim')
    require(release['canonical_language'] == 'fr' and release['english_role'] == 'faithful_translation', 'Canonical language changed')
    provenance = data['source_provenance.json']
    source_manifest = load(root / 'release/source_snapshots.json')
    require(set(source_manifest) == set(provenance['source_sha256']), 'Missing consumed source snapshots')
    for name, sha in provenance['source_sha256'].items():
        require(source_manifest[name] == sha and digest(root / 'data/rc31/sources' / relative(name)) == sha, 'Consumed source bytes changed: ' + name)
    retention = load(root / 'release/parent_payload_RC3.json')
    require(retention['parent_archive_sha256'] == '6cc3005a46ac2c906daf42a7c27781dfae8953b5eaa78c874e41b622014dd402', 'Wrong consumed parent')
    for row in retention['files']:
        path = root / relative(row['retained_path'])
        require(path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], 'Retained RC3 bytes changed: ' + row['original_path'])
    narrative = load(root / 'data/rc31/narrative.json')
    require(digest(root / 'data/rc31/narrative.json') == release['narrative_sha256'], 'Canonical narrative changed')
    require(narrative['canonical_language'] == 'fr' and narrative['english_role'] == 'faithful_translation', 'Narrative language contract changed')
    require(narrative['analysis_sha256'] == digest(root / 'data/rc31/analysis.json'), 'Narrative is not bound to actual analysis')
    canonical = hashlib.sha256(json.dumps(narrative['fr'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(narrative['translation_of_fr_sha256'] == canonical, 'English canonical source binding changed')
    phase_records = load(root / 'release/phase_records.json')
    for name, sha in phase_records.items():
        require(digest(root / relative(name)) == sha, 'Actual compact phase record changed: ' + name)
    registry = load(root / 'release/evidence_registry.json')
    require(registry['scope'] == 'external_full_outputs_and_inputs' and registry['full_outputs'] and registry['inputs'], 'Missing full output/input registry')
    for row in registry['full_outputs'] + registry['inputs']:
        require(isinstance(row['sha256'], str) and len(row['sha256']) == 64 and row['bytes'] > 0 and row['path'], 'Incomplete external evidence pin')
    run_archives = [row for row in registry['full_outputs'] if row['role'] == 'rc31_run']
    require(len(run_archives) == 1, 'Missing consumed full scientific run TAR')
    prefix = relative(run_archives[0]['run_prefix']).as_posix() if run_archives[0]['run_prefix'] else ''
    expected_members = {(prefix + '/' if prefix else '') + name: digest(root / 'data/rc31' / name) for name in INPUTS}
    require(registry['consumed_run_members_sha256'] == expected_members, 'Full TAR consumed-input binding changed')
    ledger = data['resource_ledger.json']
    require(ledger['limits'] == data['protocol_executed.json']['limits'], 'Executed resource limits changed')
    require(ledger['phases'] and all(row['status'] == 'complete' for row in ledger['phases']), 'Incomplete actual supervised phase')
    require(all(value <= ledger['limits']['family_validation_wall_seconds'] for value in ledger['family_validation_seconds'].values()), 'Family limit exceeded')
    require(sum(row['wall_seconds'] for row in ledger['phases']) <= ledger['limits']['run_wall_seconds'], 'Recorded cumulative phase wall exceeds run limit')
    for row in ledger['phases']:
        require(row['peak_aggregate_rss_bytes'] <= row['limits']['aggregate_rss_bytes'] <= ledger['limits']['max_rss_bytes'], 'Observed phase RSS limit exceeded')
        require(row['phase_output_bytes'] <= row['limits']['output_bytes'] <= ledger['limits']['max_output_bytes'], 'Observed phase output limit exceeded')
        require(row['wall_seconds'] < row['limits']['timeout_seconds'] <= ledger['limits']['timeout_seconds'], 'Observed phase timeout limit exceeded')
        for filename in ('result.json', 'worker_status.json', 'supervisor_status.json'):
            name = 'data/rc31/phases/' + relative(row['phase']).as_posix() + '/' + filename
            require(name in phase_records, 'Missing actual supervised phase record')
        supervisor = load(root / 'data/rc31/phases' / relative(row['phase']) / 'supervisor_status.json')
        require(all(row[key] == value for key, value in supervisor.items()), 'Ledger and actual supervisor record differ')
    require(sum(row['phase_output_bytes'] for row in ledger['phases']) <= ledger['limits']['total_output_bytes'], 'Recorded output budget exceeded')
    if sealed:
        require(release['readiness']['technical_verification_complete'] is True and release['readiness']['ready_for_review'] is True, 'Technical review not complete')
        assembly = load(root / 'verification/rc31/assembly.json')
        require(assembly['sealed'] is True, 'Unsealed package')
        review = load(root / 'verification/rc31/surface_review.json')
        compilation = load(root / 'verification/rc31/compilation.json')
        for name in DOCUMENTS:
            row = review['documents'][name + '.pdf']
            require(row['sha256'] == digest(root / (name + '.pdf')) and row['visual_review_completed'] is True, 'Stale visual review')
            require(row['reviewed_pages'] == list(range(1, row['page_count'] + 1)) and row['page_count'] > 0, 'Not every actual page reviewed')
            require(not row['blank_pages'] and not row['unresolved_references'] and not row['overfull_boxes'], 'Unresolved visual defects')
            diagnostic = compilation['documents'][name]
            require(diagnostic['pdf_sha256'] == row['sha256'] and diagnostic['log_sha256'] == digest(root / (name + '.log')), 'Compilation evidence stale')
            require(not diagnostic['overfull'] and not diagnostic['undefined'], 'Unresolved LaTeX defects')
        for name, sha in compilation['source_hashes'].items():
            require(digest(root / relative(name)) == sha, 'Source changed after compilation: ' + name)
        manifest = {}
        for line in (root / 'SHA256SUMS').read_text().splitlines():
            sha, name = line.split('  ', 1)
            require(name not in manifest, 'Duplicate integrity entry')
            manifest[name] = sha
        actual = {path.relative_to(root).as_posix(): digest(path) for path in root.rglob('*') if path.is_file() and path != root / 'SHA256SUMS'}
        require(manifest == actual, 'Manifest inventory/hash mismatch')
    return {'schema': 'healthgraphbench.rc31-package-qa.v1', 'passed': True, 'sealed': sealed,
            'checks': ['actual_numeric_derivation', 'bilingual_tables', 'actual_plot_points_and_assets', 'consumed_source_records',
                       'exploratory_limits_and_gates', 'compact_external_evidence_scope', 'parent_byte_retention',
                       'resource_completion_and_limits'] + (['four_actual_pdf_visual_reviews', 'latex_diagnostics', 'manifest_integrity'] if sealed else [])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--sealed', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.root, args.sealed), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'passed': False, 'error': str(exc)}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
