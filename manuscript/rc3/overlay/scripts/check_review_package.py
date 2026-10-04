#!/usr/bin/env python3
"""Check RC3 artifact integrity, rendered numbers, languages and explicit gates.

No training, scoring, bootstrap, acquisition or historical audit is executed.
This is manuscript QA, not independent evaluation, author approval or submission.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def language_signature(path):
    text = path.read_text()
    # Comments are documentary, not translated scientific content.
    text = re.sub(r'(?m)^\s*%.*$', '', text)
    text = text.replace(r'\,', '').replace('{,}', '.').replace(r'\%', '%')
    text = re.sub(r'\b(?:trente|thirty)\b', '30', text)
    # Commas in explicit index sets or binary tuples are not decimal marks.
    text = re.sub(r'\\\{(\d+(?:,\d+)+)\\\}', lambda match: r'\{' + match[1].replace(',', ';') + r'\}', text)
    text = text.replace('(0,1)', '(0;1)').replace('(1,0)', '(1;0)')
    if path.name.endswith('_fr.tex'):
        text = re.sub(r'(?<=\d),(?=\d)', '.', text)
    else:
        # English grouping separators are permitted by the translation policy.
        text = re.sub(r'(?<![\d.])\d{1,3}(?:,\d{3})+(?:\.\d+)?',
                      lambda match: match[0].replace(',', ''), text)
    def normalize(value):
        # Four active translated-header derivatives retain historical originals.
        for stem in ('cms_ap_bounds_R4', 'cms_ap_exact_R4', 'cms_ap_identity_R4', 'cms_decile_exact_R4'):
            value = value.replace(stem + '_translated_en', stem + '_en')
        return re.sub(r'_(?:fr|en)(?=\.|\}|$)', '_LANG', value)
    structures = [match.group(1) for match in re.finditer(r'\\(section\*?|subsection\*?|paragraph\*?)\{', text)]
    controls = {}
    for command in ('label', 'ref', 'cite', 'input'):
        controls[command] = Counter(normalize(match) for match in re.findall(r'\\' + command + r'\{([^}]+)\}', text))
    # Exact digits remain useful for rates, dates, counts, hashes and dimensions;
    # narrative word order may legitimately differ between languages.
    numbers = Counter(re.findall(r'\d+(?:\.\d+)?', text))
    return structures, controls, numbers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-manifest', action='store_true')
    parser.add_argument('--allow-unsealed', action='store_true', help='Assembly QA before visual review and sealing')
    args = parser.parse_args()
    checks = []

    def check(name, passed, detail=None):
        checks.append({'check': name, 'passed': bool(passed), 'detail': detail})

    release = json.loads((ROOT / 'release.json').read_text())
    provenance = json.loads((ROOT / 'provenance.json').read_text())
    status = json.loads((ROOT / release['current_scientific_status']).read_text())
    check('RC3_identity', release['release_candidate'] == provenance['revision'] == status['revision'] == 'RC3'
          and release['package_id'] == provenance['package_id'] == status['package_id'] == (ROOT / 'VERSION').read_text().strip() == 'manuscript-rc3')
    check('parent_identity', release['parent_archive'] == provenance['parent_archive']
          and release['parent_archive']['sha256'] == 'a1731aa9eb02d8f31179adfea62d1d70a168594910aa2002780aa66e8f83c4f9'
          and release['parent_archive']['modified'] is False)
    check('benchmark_DOI_not_manuscript', release['benchmark']['declared_DOI'] == '10.5281/zenodo.22796551'
          and release['benchmark']['version'] == '0.2.0' and release['benchmark']['modified'] is False
          and release['manuscript_package_DOI'] is None and not release['tag_created'])
    check('no_author_or_submission_claim', all(release['readiness'][key] is False for key in
          ('author_validation_complete', 'ready_for_submission', 'editorial_acceptance_claimed')))
    check('operation_records_consistent', status['current_operations'] == provenance['current_operations'])
    operations = provenance['current_operations']
    check('no_scientific_rerun', all(operations[key] is False for key in
          ('health_model_training_executed_during_RC3_preparation', 'raw_sources_acquired_during_RC3_preparation',
           'new_scores_or_target2025_metrics_computed', 'new_tuning_bootstrap_or_intervals', 'historical_successful_audits_rerun')))
    gates = status['scientific_gates']
    check('missing_external_evidence_not_passed', gates['independent_evaluation_passed'] is False
          and gates['target2025_source_acquired'] is False and gates['target2025_metrics_computed'] is False
          and gates['human_nonconsultation_attestations'] == 'unknown'
          and gates['external_human_study'] == 'not_performed' and not gates['author_validation_complete'])
    retained = json.loads((ROOT / release['retention_manifest']).read_text())
    for row in retained['files']:
        path = ROOT / row['retained_path']
        check('parent_retained:' + row['original_path'], path.is_file() and digest(path) == row['sha256'])
    evidence = json.loads((ROOT / 'data/q2/bundled_evidence_index.json').read_text())
    for row in evidence:
        path = ROOT / row['target']
        check('Q2_received_bytes:' + row['target'], path.is_file() and digest(path) == row['sha256'])
    snapshots = json.loads((ROOT / 'data/q2/source_snapshots/index.json').read_text())
    for row in snapshots:
        path = ROOT / row['package_path']
        check('consumed_source_archive:' + row['commit'], digest(path) == row['sha256'])
    protocol = ROOT / provenance['q2_protocol']['path']
    check('locked_protocol_identity', digest(protocol) == provenance['q2_protocol']['sha256']
          == '22b3b308e1ddd55f9ebfc388edc1a08ba3dc8a4a83205b230406643155536db7')
    prospective = json.loads((ROOT / 'data/q2/q2_partd_prospective_20261003.json').read_text())
    publication = json.loads((ROOT / 'data/q2/q2_partd_prospective_publication_20261003.json').read_text())
    check('sealed_not_evaluated', prospective['status'] == 'sealed_awaiting_official_target_publication'
          and not prospective['independent_evaluation']['passed']
          and not prospective['independent_evaluation']['target_metrics_computed']
          and not publication['target_metrics_computed'] and not publication['independent_evaluation_passed'])
    rendered = json.loads((ROOT / 'data/q2/rendered_evidence.json').read_text())
    spec = importlib.util.spec_from_file_location('rc3_assets', ROOT / 'scripts/render_q2_assets.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = {key: json.loads((ROOT / 'data/q2' / name).read_text()) for key, name in module.SOURCES.items()}
    tables, probes = module.derive(data)
    check('rendered_numeric_rows_match_received_JSON', rendered['tables'] == tables and rendered['learning_probes'] == probes)
    check('probes_are_history_only_learning_not_generalization', len(probes) == 12
          and all(row['passed'] and row['state_changed'] and row['relative_drop'] >= .01 for row in probes))
    check('seed_spans_not_CIs', rendered['seed_ranges_are_confidence_intervals'] is False and rendered['new_fit_score_bootstrap'] is False)
    for name, rows in tables.items():
        for lang in ('fr', 'en'):
            path = ROOT / 'tables' / f'{name}_{lang}.tex'
            text = path.read_text()
            actual = [[float(cell.replace('{,}', '.')) for cell in re.findall(r'\$([0-9]+(?:\{,\}|\.)[0-9]+)\$', line)]
                      for line in text.splitlines() if re.search(r'\$[0-9]', line)]
            digits = 3 if name == 'q2_resources' else 6
            expected = [[float(f'{value:.{digits}f}') for value in row['values'] if value is not None] for row in rows]
            check('printed_table_numbers:' + path.name, actual == expected)
    pairs = []
    for path in sorted(ROOT.rglob('*_fr.tex')):
        relative = path.relative_to(ROOT)
        if relative.parts[0] not in ('sections', 'tables') and len(relative.parts) != 1:
            continue
        other = path.with_name(path.name[:-7] + '_en.tex')
        if not other.exists():
            continue
        left, right = language_signature(path), language_signature(other)
        item = {'french': str(relative), 'english': str(other.relative_to(ROOT)),
                'same_structure': left[0] == right[0], 'same_controls': left[1] == right[1],
                'same_numeric_tokens': left[2] == right[2]}
        pairs.append(item)
        check('bilingual_structure:' + str(relative), item['same_structure'] and item['same_controls'])
        check('bilingual_numbers:' + str(relative), item['same_numeric_tokens'],
              None if item['same_numeric_tokens'] else {'French_only': dict(left[2] - right[2]), 'English_only': dict(right[2] - left[2])})
    for document in release['documents']:
        pdf = ROOT / document['pdf']
        valid_pdf = pdf.is_file()
        if valid_pdf:
            with pdf.open('rb') as source:
                valid_pdf = source.read(5) == b'%PDF-'
        check('PDF_exists:' + document['pdf'], valid_pdf)
    if not args.allow_unsealed:
        review = json.loads((ROOT / 'verification/rc3/surface_review.json').read_text())
        for name in ('main_fr.pdf', 'main_en.pdf', 'supplement_fr.pdf', 'supplement_en.pdf'):
            row = review['documents'][name]
            check('actual_PDF_surface_review:' + name, row['sha256'] == digest(ROOT / name)
                  and row['reviewed_pages'] and row['visual_review_completed']
                  and row['blank_pages'] == [] and row['unresolved_references'] == [])
        check('sealed_readiness_without_submission', release['readiness']['technical_verification_complete'] is True
              and release['readiness']['ready_for_review'] is True and operations['surfaces_visually_inspected'] is True)
    if not args.skip_manifest:
        lines = (ROOT / 'SHA256SUMS').read_text().splitlines()
        for line in lines:
            expected_hash, name = line.split('  ', 1)
            path = ROOT / name
            check('manifest:' + name, path.is_file() and digest(path) == expected_hash)
        listed = {line.split('  ', 1)[1] for line in lines}
        actual_files = {str(path.relative_to(ROOT)) for path in ROOT.rglob('*') if path.is_file() and path != ROOT / 'SHA256SUMS'}
        check('manifest_complete_without_self_reference', listed == actual_files)
    report = {'schema': 'healthgraphbench.rc3-package-QA.v1', 'passed': all(row['passed'] for row in checks),
              'checks': checks, 'bilingual_pairs': pairs,
              'scope': 'RC3 manuscript integrity/numerical/structural QA; no historical audit rerun, statistical calculation or clinical/independent/human validation',
              'missing_scientific_and_author_gates': gates}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
