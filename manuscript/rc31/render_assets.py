#!/usr/bin/env python3
"""Render only completed RC3.1 JSON; never fit, score or bootstrap."""
import argparse
import hashlib
import json
import math
from pathlib import Path

INPUTS = ('partd_experiments.json', 'maude_experiments.json', 'cms_experiments.json',
          'analysis.json', 'cycle.json', 'protocol_executed.json', 'source_provenance.json', 'resource_ledger.json')
LIMITS = {'independent_temporal_evaluation_completed': False, 'external_human_reproduction_completed': False,
          'author_approval': 'unknown', 'venue_compliance': 'unknown', 'submission_performed': False}
DOI = '10.5281/zenodo.22796551'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    def reject(value):
        raise ValueError('Non-finite JSON: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=reject)


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def tex(value):
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
                    '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(replacements.get(char, char) for char in str(value))


def table_label(value):
    return tex(value).replace(r'\_', r'\_\allowbreak{}').replace('/', r'/\allowbreak{}')


def number(value, lang, digits=6):
    if value is None:
        return r'\textemdash'
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError('Not a finite metric: ' + repr(value))
    value = f'{value:.{digits}f}'
    return '$' + (value.replace('.', '{,}') if lang == 'fr' else value) + '$'


def mean(values):
    if any(value is None for value in values):
        return None
    return sum(values) / len(values) if values else None


def span(values):
    if not values or any(value is None for value in values):
        return None
    return [min(values), max(values)]


def consume(root):
    root = Path(root)
    data = {name: load(root / name) for name in INPUTS}
    cycle, protocol, provenance = (data[name] for name in ('cycle.json', 'protocol_executed.json', 'source_provenance.json'))
    if cycle['status'] != 'completed_exploratory' or cycle['schema'] != 'healthgraphbench.rc31-targeted-cycle.v1':
        raise ValueError('Actual completed RC3.1 cycle required')
    if protocol['cycle'] != 'rc31-relational-information' or protocol['evidence_level'] != 'exploratory_on_previously_consulted_2023_2025':
        raise ValueError('Wrong targeted protocol/evidence level')
    if digest(root / 'protocol_executed.json') != cycle['protocol_sha256'] or cycle['protocol_sha256'] != provenance['protocol_sha256']:
        raise ValueError('Protocol consumption hashes disagree')
    if set(provenance['source_sha256']) != set(protocol['locked_sources']) or not provenance['code_commit']:
        raise ValueError('Incomplete consumed scientific-source records')
    for gate in ('independent_temporal_evaluation_completed', 'external_human_reproduction_completed'):
        if cycle[gate] is not False:
            raise ValueError('This exploratory package cannot close independent/human gates')
    for domain in ('partd', 'maude', 'cms'):
        experiments = data[domain + '_experiments.json']
        if experiments != cycle['experiments'][domain] or not experiments['phases']:
            raise ValueError('Cycle/experiment discrepancy: ' + domain)
    return data


def derive(data):
    analysis = data['analysis.json']
    if analysis['evidence_level'] != data['protocol_executed.json']['evidence_level']:
        raise ValueError('Analysis evidence level mismatch')
    result = {'methods': [], 'contrasts': [], 'workload': [], 'strata': [], 'resources': [], 'selection': []}
    for family, selected in sorted(data['partd_experiments.json']['selection'].items()):
        if selected['seed_selection'] is not False:
            raise ValueError('Training-seed selection is forbidden')
        result['selection'].append({'family': family, **selected})
    for domain in ('partd', 'maude', 'cms'):
        years = ('2024',) if domain == 'partd' else ('2023', '2024', '2025')
        for year in years:
            annual = analysis[domain][year]
            if domain != 'cms':
                expected_methods = ({'cosine', 'bpr_reuse', 'global_popularity', 'specialty_popularity', 'graphsage', 'jaccard', 'common_count'}
                                    if domain == 'partd' else {'graph_real_k4', 'graph_real_k8', 'graph_real_k16', 'graph_reassigned_k8', 'bpr_raw', 'bpr_smoothed'})
                if set(annual['methods']) != expected_methods:
                    raise ValueError('Missing required targeted methods: ' + domain + '/' + year)
                for method, record in sorted(annual['methods'].items()):
                    summaries = record['seed_summaries']
                    if len(summaries) != len(record['seeds']) or not summaries:
                        raise ValueError('Missing seed summaries')
                    stochastic = domain == 'maude' or method in ('graphsage', 'bpr_reuse')
                    expected_seeds = data['protocol_executed.json']['seeds'] if stochastic else [None]
                    if record['seeds'] != expected_seeds or len(record['phases']) != len(expected_seeds):
                        raise ValueError('Missing or selected training seeds')
                    for phase in record['phases']:
                        if phase not in data[domain + '_experiments.json']['phases']:
                            raise ValueError('Analysis references an unconsumed phase')
                    values = [row['workload']['10']['micro_recall'] for row in summaries]
                    population = {key: summaries[0][key] for key in ('entity_periods', 'unique_entities', 'positive_total',
                                                                    'zero_positive_entity_periods', 'zero_positive_fraction')}
                    if any(any(summary[key] != value for key, value in population.items()) for summary in summaries):
                        raise ValueError('Training seeds changed the workload population')
                    result['methods'].append(dict(domain=domain, year=year, method=method, metric='micro_recall_at_10',
                                                  seeds=record['seeds'], values=values, mean=mean(values), seed_range=span(values), population=population))
                    for k in ('1', '5', '10', '20', '50', '100'):
                        for metric in ('micro_recall', 'observed_precision', 'actual_proposal_slots', 'retrieved_observed_links', 'entity_period_hit_coverage'):
                            values = [row['workload'][k][metric] for row in summaries]
                            result['workload'].append(dict(domain=domain, year=year, method=method, k=int(k), metric=metric,
                                                           values=values, mean=mean(values), seed_range=span(values)))
                containers = [('', annual['contrasts'])]
            else:
                containers = []
                for family in ('logistic', 'boosted'):
                    record = annual[family]
                    if record['task_is_conditional_on_inspection'] is not True:
                        raise ValueError('CMS must remain conditional on inspection')
                    if {phase['feature_set'] for phase in record['phases']} != set(data['protocol_executed.json']['tasks']['cms']['feature_sets']):
                        raise ValueError('Missing fixed CMS feature comparison')
                    if any(phase not in data['cms_experiments.json']['phases'] for phase in record['phases']):
                        raise ValueError('CMS analysis references an unconsumed phase')
                    for phase in record['phases']:
                        value = phase['primary_metric']
                        result['methods'].append(dict(domain=domain, year=year, method=family + '/' + phase['feature_set'],
                                                      metric='roc_auc', seeds=[phase['seed']], values=[value], mean=value, seed_range=None))
                    containers.append((family + '/', record['contrasts']))
            for prefix, contrasts in containers:
                for name, record in sorted(contrasts.items()):
                    for group, values in [('overall', record['overall']), *sorted(record['strata'].items())]:
                        metric = 'delta_roc_auc' if domain == 'cms' else 'delta_micro_recall_at_10'
                        interval_key = 'conditional_paired_facility_interval_95' if domain == 'cms' else 'conditional_paired_cluster_interval_95'
                        if values['configuration_selection_covered'] is not False or values['period_or_network_independence_claimed'] is not False or values['margin_is_clinical_utility_threshold'] is not False:
                            raise ValueError('Unsupported uncertainty claim')
                        if values['requested_draws'] != data['protocol_executed.json']['uncertainty']['conditional_entity_cluster_bootstrap_draws']:
                            raise ValueError('Bootstrap draw contract mismatch')
                        if values['bootstrap_seed'] != data['protocol_executed.json']['uncertainty']['seed'] or not 0 <= values['valid_draws'] <= values['requested_draws']:
                            raise ValueError('Bootstrap provenance mismatch')
                        if domain != 'cms' and (values['training_seed_resampling'] is not False or values['cluster_unit'] != ('provider' if domain == 'partd' else 'product')):
                            raise ValueError('Intervals must cluster entities, not training seeds')
                        if values['evidence_level'] != 'exploratory_conditional_on_fits' or values['practical_margin_absolute'] != .01:
                            raise ValueError('Conditional exploratory interval/margin contract changed')
                        interval = values[interval_key]
                        if interval is not None and (len(interval) != 2 or interval[0] > interval[1]):
                            raise ValueError('Invalid conditional interval')
                        row = dict(domain=domain, year=year, method=prefix + name, group=group, metric=metric,
                                   delta=values[metric], conditional_interval_95=interval,
                                   left_seed_range=span(values.get('left_seed_metrics', [])),
                                   right_seed_range=span(values.get('right_seed_metrics', [])),
                                   cluster_unit='facility' if domain == 'cms' else values['cluster_unit'],
                                   clusters=values.get('facilities', values.get('clusters')),
                                   bootstrap_seed=values['bootstrap_seed'], practical_margin_absolute=values['practical_margin_absolute'],
                                   requested_draws=values['requested_draws'], valid_draws=values['valid_draws'])
                        result['contrasts' if group == 'overall' else 'strata'].append(row)
    for domain in ('partd', 'maude', 'cms'):
        for phase in data[domain + '_experiments.json']['phases']:
            result['resources'].append({key: phase.get(key) for key in ('phase', 'family', 'year', 'seed', 'configuration',
                                      'parameter_count', 'trainable_parameter_count', 'stored_state', 'fit_seconds', 'score_seconds',
                                      'learning_gate_passed', 'learning', 'feature_dimension', 'training_rows', 'target_rows')})
    return result


def table(headers, rows):
    return ('% Actual RC3.1 consumed JSON; descriptive seed ranges are not intervals.\n'
            + r'\begin{longtable}{@{}>{\raggedright\arraybackslash}p{.42\linewidth}rrr@{}}' + '\n' + r'\toprule' + '\n'
            + ' & '.join(headers) + r' \\' + '\n' + r'\midrule\endhead' + '\n'
            + ''.join(' & '.join(row) + r' \\' + '\n' for row in rows)
            + r'\bottomrule\end{longtable}' + '\n')


def tables(records, lang):
    fr = lang == 'fr'
    outputs = {}
    for domain in ('partd', 'maude', 'cms'):
        rows = []
        for row in records['methods']:
            if row['domain'] == domain:
                interval = row['seed_range']
                rows.append([table_label(row['year'] + ' / ' + row['method']), number(row['mean'], lang),
                             number(interval[0] if interval else None, lang), number(interval[1] if interval else None, lang)])
        outputs[domain + '_' + lang + '.tex'] = table(['Méthode / année' if fr else 'Method / year',
            'AUC' if domain == 'cms' else 'Recall@10', 'Min. graine' if fr else 'Seed min.', 'Max. graine' if fr else 'Seed max.'], rows)
    for kind in ('contrasts', 'strata'):
        rows = []
        for row in records[kind]:
            interval = row['conditional_interval_95']
            rows.append([table_label(row['domain'] + ' ' + row['year'] + ' / ' + row['method'] + ' / ' + row['group']),
                         number(row['delta'], lang), number(interval[0] if interval else None, lang), number(interval[1] if interval else None, lang)])
        outputs[kind + '_' + lang + '.tex'] = table(['Contraste' if fr else 'Contrast', r'$\Delta$',
                                                   'IC cond. bas' if fr else 'Cond. CI low', 'IC cond. haut' if fr else 'Cond. CI high'], rows)
    workload = []
    for row in records['workload']:
        if row['metric'] in ('actual_proposal_slots', 'retrieved_observed_links', 'entity_period_hit_coverage'):
            interval = row['seed_range']
            digits = 2 if row['metric'] in ('actual_proposal_slots', 'retrieved_observed_links') else 6
            workload.append([table_label(f"{row['domain']} {row['year']} / {row['method']} / K={row['k']} / {row['metric']}"),
                             number(row['mean'], lang, digits), number(interval[0] if interval else None, lang, digits), number(interval[1] if interval else None, lang, digits)])
    outputs['workload_' + lang + '.tex'] = table(['Charge observée' if fr else 'Observed workload',
                                               'Moyenne' if fr else 'Mean', 'Min. graine' if fr else 'Seed min.', 'Max. graine' if fr else 'Seed max.'], workload)
    population_rows = []
    for row in records['methods']:
        if row['domain'] != 'cms':
            population = row['population']
            population_rows.append([table_label(row['domain'] + ' ' + row['year'] + ' / ' + row['method']),
                                    number(population['entity_periods'], lang, 0),
                                    number(population['zero_positive_entity_periods'], lang, 0),
                                    number(population['positive_total'], lang, 0)])
    outputs['population_' + lang + '.tex'] = table(['Population', 'Unités' if fr else 'Units',
                                                    'Sans positif' if fr else 'Zero positive', 'Liens' if fr else 'Links'], population_rows)
    resource_rows = []
    for row in records['resources']:
        gate = row['learning_gate_passed'] if row['learning_gate_passed'] is not None else row['learning'].get('learning_gate_passed') if row['learning'] else None
        resource_rows.append([table_label(row['phase'] + ' / learning gate=' + str(gate)), number(row['fit_seconds'], lang, 3),
                              number(row['score_seconds'], lang, 3), number(row['trainable_parameter_count'], lang, 0)])
    outputs['resources_' + lang + '.tex'] = table(['Phase', 'Fit (s)', 'Score (s)',
                                                  'Paramètres' if fr else 'Parameters'], resource_rows)
    selected_rows = []
    for row in records['selection']:
        label = row['family'] + ' / ' + json.dumps(row['configuration'], ensure_ascii=False, sort_keys=True)
        selected_rows.append([table_label(label), number(row['mean_validation_micro_recall_at_10'], lang),
                              number(row['configuration_index'], lang, 0), 'non' if fr else 'no'])
    outputs['selection_' + lang + '.tex'] = table(['Configuration', 'Val. R@10', 'Index', 'Choix graine' if fr else 'Seed selection'], selected_rows)
    return outputs


def plot_specs(records):
    specs = []
    for domain in ('partd', 'maude'):
        years = sorted({row['year'] for row in records['workload'] if row['domain'] == domain})
        for year in years:
            for metric in ('micro_recall', 'observed_precision'):
                selected = [row for row in records['workload'] if row['domain'] == domain and row['year'] == year and row['metric'] == metric]
                specs.append(dict(name=f'workload_{domain}_{year}_{metric}', kind='workload', domain=domain, year=year,
                                  metric=metric, points=selected))
    for domain in ('partd', 'maude', 'cms'):
        for year in sorted({row['year'] for row in records['strata'] if row['domain'] == domain}):
            selected = [row for row in records['strata'] if row['domain'] == domain and row['year'] == year]
            methods = sorted({row['method'] for row in selected})
            for index, method in enumerate(methods):
                specs.append(dict(name=f'strata_{domain}_{year}_{index:02}', kind='strata', domain=domain, year=year,
                                  method=method, metric='delta_roc_auc' if domain == 'cms' else 'delta_micro_recall_at_10',
                                  points=[row for row in selected if row['method'] == method]))
    return specs


def plots(specs, destination, lang):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for spec in specs:
        if spec['kind'] == 'workload':
            fig, ax = plt.subplots(figsize=(7, 4.5), layout='constrained')
            for method in sorted({row['method'] for row in spec['points']}):
                rows = sorted((row for row in spec['points'] if row['method'] == method), key=lambda row: row['k'])
                valid = [row for row in rows if row['mean'] is not None]
                ax.plot([row['k'] for row in valid], [row['mean'] for row in valid], marker='o', label=method)
                if valid:
                    ax.fill_between([row['k'] for row in valid], [row['seed_range'][0] for row in valid],
                                    [row['seed_range'][1] for row in valid], alpha=.12)
            ax.set_xlabel('K : propositions à examiner' if lang == 'fr' else 'K: proposals to review')
            ax.set_ylabel(spec['metric'])
            ax.legend(fontsize=7)
            subtitle = 'Plage descriptive des graines (pas un IC)' if lang == 'fr' else 'Descriptive seed range (not a CI)'
        else:
            rows = spec['points']
            fig, ax = plt.subplots(figsize=(8, max(3, len(rows) * .36)), layout='constrained')
            for index, row in enumerate(rows):
                if row['delta'] is not None:
                    ax.plot(row['delta'], index, 'o', color='navy')
                    if row['conditional_interval_95'] is not None:
                        ax.plot(row['conditional_interval_95'], [index, index], color='navy')
            ax.set_yticks(range(len(rows)), [row['group'] for row in rows], fontsize=8)
            ax.axvline(0, color='grey', linewidth=.7)
            ax.axvline(.01, color='grey', linestyle=':', linewidth=.7)
            ax.axvline(-.01, color='grey', linestyle=':', linewidth=.7)
            ax.set_xlabel(spec['metric'])
            subtitle = 'IC conditionnel apparié ; ajustements fixés' if lang == 'fr' else 'Paired conditional CI; fixed fits'
        method_title = ('\n' + spec['method'].replace('_minus_', ' − ').replace('_', ' ')) if spec['kind'] == 'strata' else ''
        ax.set_title(spec['domain'].upper() + ' ' + spec['year'] + method_title + '\n' + subtitle, fontsize=9)
        fig.savefig(destination / (spec['name'] + '_' + lang + '.pdf'), metadata={'CreationDate': None, 'ModDate': None})
        plt.close(fig)


def render(run_root, output):
    run_root, output = Path(run_root).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError('Assets directory must be new')
    input_hashes = {name: digest(run_root / name) for name in INPUTS}
    renderer_sha256 = digest(Path(__file__))
    data = consume(run_root)
    records = derive(data)
    specs = plot_specs(records)
    output.mkdir(parents=True)
    (output / 'tables').mkdir()
    (output / 'figures').mkdir()
    for lang in ('fr', 'en'):
        for name, content in tables(records, lang).items():
            (output / 'tables' / name).write_text(content, encoding='utf-8')
        plots(specs, output / 'figures', lang)
    dump(output / 'numeric_records.json', records)
    dump(output / 'plot_records.json', specs)
    if input_hashes != {name: digest(run_root / name) for name in INPUTS} or renderer_sha256 != digest(Path(__file__)):
        raise ValueError('Consumed inputs or renderer changed during rendering')
    generated = sorted(path for path in output.rglob('*') if path.is_file())
    report = {'schema': 'healthgraphbench.rc31-assets.v1', 'revision': 'RC3.1', 'run_root': str(run_root),
              'inputs': input_hashes,
              'renderer_sha256': renderer_sha256, 'scientific_sources': data['source_provenance.json']['source_sha256'],
              'outputs': {path.relative_to(output).as_posix(): digest(path) for path in generated},
              'limits': LIMITS, 'benchmark_doi': DOI, 'doi_scope': 'benchmark v0.2.0 only',
              'training_seed_ranges_are_confidence_intervals': False,
              'conditional_intervals_cover_selection_or_period_independence': False}
    dump(output / 'asset_manifest.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output-assets', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(render(args.run_root, args.output_assets), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
