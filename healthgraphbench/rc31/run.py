"""Run the separately committed RC3.1 protocol with real cumulative supervision."""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from typing import Any

from ..q2.common import RunBudget, load_protocol
from . import analysis, cms, maude, partd


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def _metric(result: dict) -> float:
    value = result['metrics']['roc_auc'] if result.get('primary_metric') == 'roc_auc' else result['primary_metric']
    if value is None:
        raise ValueError('primary metric undefined; no fabricated zero or selection')
    return float(value)


def _slim(result: dict, relative: str) -> dict:
    fields = ('family', 'feature_set', 'year', 'seed', 'configuration', 'parameter_count',
              'trainable_parameter_count', 'stored_state', 'fit_seconds', 'score_seconds',
              'state_preparation_seconds', 'candidate_fingerprint', 'target_fingerprint',
              'row_layout_fingerprint', 'learning_gate_passed', 'checkpoint_sha256',
              'target_provider_years', 'positive_total', 'evaluated_candidate_total',
              'feature_dimension', 'training_rows', 'target_rows', 'quality_bins', 'history_bins')
    row = {key: result[key] for key in fields if key in result}
    row['phase'] = relative
    row['primary_metric'] = _metric(result)
    diagnostic = result.get('diagnostics', result.get('learning_diagnostics', {}))
    row['learning'] = {key: diagnostic[key] for key in
                       ('probe_loss_before', 'probe_loss_after', 'probe_relative_loss_drop',
                        'state_changed', 'initialization_sha256', 'learning_gate_passed',
                        'training_edge_sha256', 'probe_sha256', 'reassignment', 'identical_learned_state')
                       if key in diagnostic}
    return row


def _phase(budget: RunBudget, target, args: tuple, relative: str, *, family: str | None = None) -> dict:
    directory = budget.output_dir / relative
    directory.parent.mkdir(parents=True, exist_ok=True)
    budget.execute(target, args, directory, family=family)
    return json.loads((directory / 'result.json').read_text())


def _check_layout(records: list[dict], domain: str) -> None:
    for year in {record['year'] for record in records}:
        annual = [record for record in records if record['year'] == year]
        fields = ('row_layout_fingerprint',) if domain == 'cms' else ('candidate_fingerprint', 'target_fingerprint')
        for field in fields:
            if len({record[field] for record in annual}) != 1:
                raise ValueError(f'{domain}/{year} changed {field} across paired methods')


def _select(grid: list[list[dict]], expected_seeds: list[int | None]) -> dict:
    scores = []
    for records in grid:
        if [record['seed'] for record in records] != expected_seeds:
            raise ValueError('incomplete configuration or seed grid; selection forbidden')
        scores.append(sum(record['primary_metric'] for record in records) / len(records))
    if not scores:
        raise ValueError('empty grid')
    index = max(range(len(scores)), key=scores.__getitem__)
    return {'configuration_index': index, 'configuration': grid[index][0]['configuration'],
            'mean_validation_micro_recall_at_10': scores[index], 'all_grid_means': scores,
            'exact_tie_break': 'published_grid_order', 'seed_selection': False}


def _run_partd(budget: RunBudget, protocol: dict) -> dict:
    prepared = protocol['inputs']['partd_prepared']
    config = protocol['tasks']['partd']
    records, selections = [], {}
    for family in config['neighbor_measures'] + ['graphsage']:
        grid = ([{'k': k} for k in config['neighbor_k_grid']] if family != 'graphsage' else config['graphsage_grid'])
        seeds = [None] if family != 'graphsage' else protocol['seeds']
        completed = []
        for index, parameters in enumerate(grid):
            replicas = []
            for seed in seeds:
                relative = f'partd/validation/{family}/config-{index:02}/seed-{seed}'
                result = _phase(budget, partd.run_phase,
                                (prepared, 2023, family, parameters, seed, config['graphsage_fixed'] if family == 'graphsage' else {}),
                                relative, family='partd_' + family)
                row = _slim(result, relative)
                replicas.append(row)
                records.append(row)
            completed.append(replicas)
        selections[family] = _select(completed, seeds)
    # The original BPR six-grid selection is frozen, not chosen after cosine/test.
    original = Path(protocol['inputs']['partd_reuse_root'])
    legacy = json.loads((original / 'selection.json').read_text())['families']['bpr']
    if legacy['configuration_index'] != 5 or legacy['configuration'] != config['bpr_selected_configuration']:
        raise ValueError('published BPR validation selection differs from new locked contract')
    selections['bpr_reuse'] = {'configuration_index': 5, 'configuration': legacy['configuration'],
                                'mean_validation_micro_recall_at_10': legacy['mean_primary_validation'],
                                'all_grid_means': legacy['validation_grid_scores'],
                                'selection_reused': True, 'seed_selection': False}
    # Store all family choices before any 2024 scorer is called.
    _json(budget.output_dir / 'partd_selection.json', selections)
    for year in (2023, 2024):
        for family in config['fixed_baselines']:
            relative = f'partd/{year}/{family}/seed-None'
            result = _phase(budget, partd.run_phase, (prepared, year, family, {}, None, {}), relative)
            records.append(_slim(result, relative))
        for seed in protocol['seeds']:
            stage = 'validation' if year == 2023 else 'test'
            old_phase = original / f'phases/{stage}/bpr/config-05/seed-{seed}'
            relative = f'partd/{year}/bpr_reuse/seed-{seed}'
            fixed = {'reuse_phase_path': str(old_phase), 'reuse_prepared_path': prepared}
            result = _phase(budget, partd.run_phase,
                            (prepared, year, 'bpr_reuse', config['bpr_selected_configuration'], seed, fixed), relative)
            records.append(_slim(result, relative))
    for family in config['neighbor_measures'] + ['graphsage']:
        selected = selections[family]['configuration']
        for seed in ([None] if family != 'graphsage' else protocol['seeds']):
            relative = f'partd/test/{family}/seed-{seed}'
            result = _phase(budget, partd.run_phase,
                            (prepared, 2024, family, selected, seed, config['graphsage_fixed'] if family == 'graphsage' else {}), relative)
            records.append(_slim(result, relative))
    _check_layout(records, 'partd')
    result = {'selection': selections, 'phases': records, 'BPR_training_fits_repeated': 0}
    _json(budget.output_dir / 'partd_experiments.json', result)
    return result


def _run_maude(budget: RunBudget, protocol: dict) -> dict:
    prepared = protocol['inputs']['maude_prepared']
    config = protocol['tasks']['maude']
    records = []
    for year in config['years']:
        for level in config['graph_levels']:
            family = 'graphsage_reassigned' if level['adjacency'] == 'reassigned' else 'graphsage_mean'
            parameters = {**config['fixed'], **level}
            name = f"graph_{level['adjacency']}_k{level['fanout']}"
            for seed in protocol['seeds']:
                relative = f'maude/{year}/{name}/seed-{seed}'
                result = _phase(budget, maude.run_phase,
                                (prepared, year, family, parameters, seed, {'learning_gate': protocol['learning_gate']}),
                                relative, family=name if year == 2023 else None)
                row = _slim(result, relative)
                row['comparison_name'] = name
                records.append(row)
        for family in ('bpr_raw', 'bpr_smoothed'):
            for seed in protocol['seeds']:
                root = Path(protocol['inputs']['maude_validation_bpr_root'] if year == 2023 else protocol['inputs']['maude_test_bpr_root'])
                old = root / (f'seed{seed}/checkpoint.bin' if year == 2023 else f'year{year}/seed{seed}/checkpoint.bin')
                relative = f'maude/{year}/{family}/seed-{seed}'
                result = _phase(budget, maude.run_phase,
                                (prepared, year, family, {}, seed, {'checkpoint_path': str(old)}), relative)
                row = _slim(result, relative)
                row['comparison_name'] = family
                records.append(row)
    _check_layout(records, 'maude')
    result = {'phases': records, 'factor_selection': False, 'BPR_training_fits_repeated': 0}
    _json(budget.output_dir / 'maude_experiments.json', result)
    return result


def _run_cms(budget: RunBudget, protocol: dict, source_root: Path) -> dict:
    preparation = _phase(budget, cms.prepare_phase,
                         (str(source_root), protocol['inputs']['cms_manifest'], protocol['inputs']['cms_baseline_rows']),
                         'cms/preparation')
    prepared = preparation['prepared_path']
    config = protocol['tasks']['cms']
    records = []
    for year in config['years']:
        for family in ('logistic', 'boosted'):
            for feature_set in config['feature_sets']:
                parameters = {'feature_set': feature_set, **config[family + '_configuration']}
                relative = f'cms/{year}/{family}/{feature_set}/seed-None'
                result = _phase(budget, cms.run_phase,
                                (prepared, year, family, parameters, None, config[family + '_fixed']), relative,
                                family='cms_' + family if year == 2023 else None)
                records.append(_slim(result, relative))
    _check_layout(records, 'cms')
    result = {'preparation': preparation, 'phases': records, 'same_configuration_across_feature_sets': True}
    _json(budget.output_dir / 'cms_experiments.json', result)
    return result


def _streams(root: Path, records: list[dict]) -> list[list[dict]]:
    return [analysis.read_rows(root / record['phase'] / 'predictions.jsonl.gz') for record in records]


def _analysis_phase(root: str, experiments: dict, protocol: dict, phase_dir: Path) -> dict:
    root_path = Path(root)
    result: dict[str, Any] = {'evidence_level': protocol['evidence_level'], 'partd': {}, 'maude': {}, 'cms': {}}
    for domain in ('partd', 'maude'):
        records = experiments[domain]['phases']
        years = [2024] if domain == 'partd' else [2023, 2024, 2025]
        for year in years:
            selected = [record for record in records if record['year'] == year and
                        (domain != 'partd' or '/validation/' not in record['phase'])]
            names = sorted({record.get('comparison_name', record['family']) for record in selected})
            groups = {name: [record for record in selected if record.get('comparison_name', record['family']) == name] for name in names}
            annual = {'methods': {}, 'contrasts': {}}
            for name, method_records in groups.items():
                streams = _streams(root_path, method_records)
                annual['methods'][name] = {'seed_summaries': [analysis.ranking_summary(rows, domain) for rows in streams],
                                          'seeds': [record['seed'] for record in method_records], 'phases': method_records}
                del streams
            pairs = ([('cosine', 'bpr_reuse'), ('cosine', 'global_popularity'), ('cosine', 'specialty_popularity'),
                      ('graphsage', 'cosine'), ('jaccard', 'cosine'), ('common_count', 'cosine')]
                     if domain == 'partd' else [('graph_real_k16', 'graph_real_k8'), ('graph_real_k8', 'graph_reassigned_k8'),
                                               ('bpr_smoothed', 'bpr_raw'), ('graph_real_k4', 'graph_real_k8')])
            strata = [('history', label) for label in (protocol['strata']['partd_history_distinct_drugs'] if domain == 'partd' else protocol['strata']['maude_history_report_support'])]
            strata += [('candidate_support', label) for label in ('<=5', '6-50', '>50')]
            strata += [('neighbor_support', label) for label in ('0', '1-2', '3+')]
            for left, right in pairs:
                a, b = _streams(root_path, groups[left]), _streams(root_path, groups[right])
                kwargs = {'domain': domain, 'draws': protocol['uncertainty']['conditional_entity_cluster_bootstrap_draws'],
                          'seed': protocol['uncertainty']['seed'], 'practical_margin': .01}
                annual['contrasts'][left + '_minus_' + right] = {
                    'overall': analysis.ranking_contrast(a, b, **kwargs),
                    'strata': {'/'.join(group): analysis.ranking_contrast(a, b, group=group, **kwargs) for group in strata},
                }
                del a, b
                gc.collect()
            result[domain][str(year)] = annual
    for year in (2023, 2024, 2025):
        annual = {}
        for family in ('logistic', 'boosted'):
            records = [record for record in experiments['cms']['phases'] if record['year'] == year and record['family'] == family]
            groups = {record['feature_set']: analysis.read_rows(root_path / record['phase'] / 'predictions.jsonl.gz') for record in records}
            local = groups['facility_history']
            contrasts = {}
            for left, right in [('facility_plus_combined_ownership', 'facility_history'),
                                ('facility_plus_documented_ownership', 'facility_history'),
                                ('facility_plus_documented_ownership', 'facility_plus_combined_ownership')]:
                a, b = groups[left], groups[right]
                kwargs = {'draws': protocol['uncertainty']['conditional_entity_cluster_bootstrap_draws'], 'seed': protocol['uncertainty']['seed']}
                contrast = {'overall': analysis.cms_contrast(a, b, **kwargs), 'strata': {}}
                for field, labels in [('history_bin', protocol['strata']['cms_prior_inspections']),
                                      ('quality_bin', protocol['strata']['cms_documentation_proxy'])]:
                    for label in labels:
                        aa, bb = [row for row in a if row[field] == label], [row for row in b if row[field] == label]
                        contrast['strata'][field + '/' + label] = analysis.cms_contrast(aa, bb, **kwargs)
                contrasts[left + '_minus_' + right] = contrast
            annual[family] = {'phases': records, 'contrasts': contrasts,
                              'task_is_conditional_on_inspection': True}
        result['cms'][str(year)] = annual
    _json(phase_dir / 'result.json', result)
    return result


def run(protocol_path: Path, expected_sha256: str, output_dir: Path, cms_source_root: Path) -> dict:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError('RC3.1 run output must be new')
    protocol = load_protocol(protocol_path, expected_sha256, output_dir)
    if protocol.get('cycle') != 'rc31-relational-information':
        raise ValueError('not the RC3.1 targeted protocol')
    budget = RunBudget(output_dir, protocol['limits'])
    try:
        experiments = {'partd': _run_partd(budget, protocol), 'maude': _run_maude(budget, protocol),
                       'cms': _run_cms(budget, protocol, cms_source_root)}
        analysed = _phase(budget, _analysis_phase, (str(output_dir), experiments, protocol), 'analysis')
        _json(output_dir / 'analysis.json', analysed)
        new_fits = len(experiments['cms']['phases']) + sum(
            record['family'].startswith('graphsage')
            for domain in ('partd', 'maude') for record in experiments[domain]['phases'])
        result = {'schema': 'healthgraphbench.rc31-targeted-cycle.v1', 'status': 'completed_exploratory',
                  'protocol_sha256': expected_sha256, 'source_provenance': str(output_dir / 'source_provenance.json'),
                  'experiments': experiments, 'analysis_path': str(output_dir / 'analysis.json'),
                  'resource_ledger': str(output_dir / 'resource_ledger.json'),
                  'new_medical_training_fits': new_fits, 'historical_BPR_training_fits_repeated': 0,
                  'independent_temporal_evaluation_completed': False, 'external_human_reproduction_completed': False}
        _json(output_dir / 'cycle.json', result)
        return result
    except BaseException as error:
        _json(output_dir / 'controller_error.json', {'error': repr(error), 'completed_phases': len(budget.phases)})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--cms-source-root', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.protocol, args.protocol_sha256, args.output_dir, args.cms_source_root)
    print(json.dumps({key: result[key] for key in ('status', 'new_medical_training_fits', 'historical_BPR_training_fits_repeated', 'analysis_path')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
