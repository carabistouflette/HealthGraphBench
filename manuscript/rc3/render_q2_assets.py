#!/usr/bin/env python3
"""Render RC3 tables/figures from completed JSON evidence; no fit, score or CI.

Requires matplotlib only for figures. French is rendered first, then the same
numeric rows with translated English labels. Input bytes are recorded in the
sidecar; seed spans are descriptive ranges, never confidence intervals.
"""
import argparse
import hashlib
import json
from pathlib import Path

SOURCES = {
    'maude': 'q2_maude_comparison_20261003.json',
    'cms': 'q2_cms_comparison_20261003.json',
    'partd': 'q2_partd_comparison_20261003.json',
    'reuse': 'q2_external_reuse_20261003.json',
    'prospective': 'q2_partd_prospective_20261003.json',
    'maude_completion_resources': 'maude_completion_resource_ledger.json',
}
LABELS = {
    'fr': {'global_popularity': 'Popularité globale', 'neighbor_frequency': 'Fréquence des voisins',
           'logistic': 'Logistique', 'boosted': 'HGB', 'spectral': 'Spectral', 'bpr': 'BPR',
           'graphsage_mean': 'GraphSAGE mean', 'graphsage_none': 'Contrôle none',
           'specialty_popularity': 'Popularité par spécialité', 'history_overlap': 'Recouvrement historique',
           'neighbor_cosine_top50': 'Cosine top50 hors paquet', 'tabular_logistic': 'Logistique SDK (18 époques)'},
    'en': {'global_popularity': 'Global popularity', 'neighbor_frequency': 'Neighbor frequency',
           'logistic': 'Logistic', 'boosted': 'HGB', 'spectral': 'Spectral', 'bpr': 'BPR',
           'graphsage_mean': 'GraphSAGE mean', 'graphsage_none': 'None control',
           'specialty_popularity': 'Specialty popularity', 'history_overlap': 'History overlap',
           'neighbor_cosine_top50': 'Out-of-package cosine top50', 'tabular_logistic': 'SDK logistic (18 epochs)'},
}


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def number(value, lang, digits=6):
    if value is None:
        return r'\textemdash'
    text = f'{value:.{digits}f}'
    return '$' + (text.replace('.', '{,}') if lang == 'fr' else text) + '$'


def tabular(headers, rows, spec):
    return ('% Derived from completed Q2 JSON; no new numerical experiment.\n'
            + r'\begin{tabularx}{\linewidth}{' + spec + '}\n'
            + r'\toprule' + '\n' + ' & '.join(headers) + r' \\' + '\n'
            + r'\midrule' + '\n'
            + ''.join(' & '.join(row) + r' \\' + '\n' for row in rows)
            + r'\bottomrule' + '\n' + r'\end{tabularx}' + '\n')


def derive(data):
    maude, cms, partd, reuse = (data[key] for key in ('maude', 'cms', 'partd', 'reuse'))
    tables = {}
    rows = []
    for family in ('global_popularity', 'neighbor_frequency'):
        rows.append({'id': family, 'values': [None] + [maude['heuristics'][year][family]['micro_recall_at_10'] for year in ('2024', '2025')]})
    for family, model in maude['families'].items():
        rows.append({'id': family, 'configuration': model['selected_configuration'],
                     'values': [model['validation_mean_micro_recall_at_10']] + [model['test_years'][year]['mean_micro_recall_at_10'] for year in ('2024', '2025')]})
    tables['q2_maude'] = rows
    rows = []
    for model, choice in cms['selection'].items():
        result = cms['models'][model]
        rows.append({'id': model, 'values': [choice['mean_validation_roc_auc']] +
                     [result['annual'][year][0]['metrics']['roc_auc'] for year in ('2024', '2025')] +
                     [result['pooled_by_seed']['None']['roc_auc']]})
    tables['q2_cms'] = rows
    tables['q2_partd'] = [{'id': family,
                         'configuration': partd['validation_2023'][family]['selected_configuration'],
                         'values': [partd['validation_2023'][family]['selected_mean_validation_micro_recall_at_10'],
                                    partd['test_2024'][family]['reported_mean_primary_test']]}
                        for family in ('specialty_popularity', 'history_overlap', 'logistic', 'boosted', 'bpr')]
    tables['q2_reuse'] = [{'id': family, 'values': [record[key]['positive_containing_provider_years']['micro_recall_at_10']
                                                 for key in ('validation_metrics', 'test_metrics_recalculated_with_public_task_evaluate')]}
                         for family, record in reuse['metrics'].items()]
    sensitivity = []
    for family in ('spectral', 'bpr', 'graphsage_mean', 'graphsage_none'):
        for year, record in maude['families'][family]['test_years'].items():
            sensitivity.append({'task': 'MAUDE', 'year': year, 'id': family,
                                'values': [record['mean_micro_recall_at_10'], record['min_micro_recall_at_10'], record['max_micro_recall_at_10']],
                                'by_seed': {seed: result['primary_micro_recall_at_10'] for seed, result in record['by_seed'].items()}})
    for family in ('boosted', 'bpr'):
        result = partd['test_2024'][family]
        distribution = result['primary_test_micro_recall_at_10']
        sensitivity.append({'task': 'Part D', 'year': '2024', 'id': family,
                            'values': [distribution['mean'], distribution['min'], distribution['max']],
                            'by_seed': dict(zip(map(str, result['replicate_seeds']), distribution['values'], strict=True))})
    tables['q2_seed_sensitivity'] = sensitivity
    phases = maude['validation_reuse']['previous_resource_ledger']['phases'] + data['maude_completion_resources']['phases']
    resources = [{'id': 'MAUDE', 'wall_kind': 'phase_sum_including_failed_serialization',
                  'values': [sum(row['wall_seconds'] for row in phases), sum(row.get('worker_cpu_seconds') or 0 for row in phases),
                             max(row['peak_aggregate_rss_bytes'] for row in phases) / 1024**2], 'fits': '84 + 28'}]
    for task, result, wall_key, fits in [('CMS', cms['resources'], 'wall_seconds_sum', '24 + 8'),
                                         ('Part D', partd['resources'], 'run_wall_seconds_recorded', '42 + 7')]:
        resources.append({'id': task, 'wall_kind': wall_key,
                          'values': [result[wall_key], result['worker_cpu_seconds_sum'], result['peak_aggregate_rss_bytes_max'] / 1024**2], 'fits': fits})
    result = reuse['resources']['raw_fits_evaluation']
    resources.append({'id': 'reuse', 'wall_kind': 'supervised_raw_fits_evaluation_phase',
                      'values': [result['wall_seconds'], result['worker_cpu_seconds'], result['peak_aggregate_rss_bytes'] / 1024**2], 'fits': None})
    result = data['prospective']['resources']
    resources.append({'id': 'prospective', 'wall_kind': 'run_wall_seconds',
                      'values': [result['run_wall_seconds'], None, result['maximum_observed_phase_rss_bytes'] / 1024**2], 'fits': '7'})
    tables['q2_resources'] = resources
    probes = []
    for variant in ('graphsage_mean', 'graphsage_none'):
        for year, result in maude['families'][variant]['test_years'].items():
            for seed, replicate in result['by_seed'].items():
                diagnosis = replicate['diagnostics']
                probes.append({'variant': variant, 'year': year, 'seed': seed,
                               'before': diagnosis['probe_loss_before'], 'after': diagnosis['probe_loss_after'],
                               'relative_drop': diagnosis['probe_relative_loss_drop'],
                               'state_changed': diagnosis['state_changed'], 'passed': diagnosis['learning_gate_passed']})
    return tables, probes


def render_tables(root, tables, lang):
    labels = LABELS[lang]
    numeric = lambda values, digits=6: [number(value, lang, digits) for value in values]
    contents = {}
    contents['q2_maude'] = tabular(['Méthode' if lang == 'fr' else 'Method', 'Val. 2023', 'Test 2024', 'Test 2025'],
                                  [[labels[row['id']]] + numeric(row['values']) for row in tables['q2_maude']], '@{}Xrrr@{}')
    feature = ('Historique local', '+ propriétaires') if lang == 'fr' else ('Facility history', '+ ownership')
    cms_label = lambda name: (feature[1] if 'ownership' in name else feature[0]) + ' / ' + labels[name.rsplit('__', 1)[1]]
    contents['q2_cms'] = tabular(['Variables / modèle' if lang == 'fr' else 'Features / model', 'Val. 2023', '2024', '2025', '2024--25'],
                                [[cms_label(row['id'])] + numeric(row['values']) for row in tables['q2_cms']], '@{}Xrrrr@{}')
    for name in ('q2_partd', 'q2_reuse'):
        contents[name] = tabular(['Méthode' if lang == 'fr' else 'Method', 'Val. 2023', 'Test 2024'],
                                 [[labels[row['id']]] + numeric(row['values']) for row in tables[name]], '@{}Xrr@{}')
    contents['q2_seed_sensitivity'] = tabular(['Tâche' if lang == 'fr' else 'Task', 'Année' if lang == 'fr' else 'Year',
                                              'Modèle' if lang == 'fr' else 'Model', 'Moyenne' if lang == 'fr' else 'Mean', 'Min.', 'Max.'],
                                             [[row['task'], row['year'], labels[row['id']]] + numeric(row['values']) for row in tables['q2_seed_sensitivity']], '@{}llXrrr@{}')
    resource_label = {'reuse': 'Réutilisation' if lang == 'fr' else 'Reuse', 'prospective': 'Forecast scellé' if lang == 'fr' else 'Sealed forecast'}
    contents['q2_resources'] = tabular(['Parcours' if lang == 'fr' else 'Run', 'Wall (s)', 'CPU (s)', 'RSS (Mio)' if lang == 'fr' else 'RSS (MiB)',
                                      'Ajustements' if lang == 'fr' else 'Fits'],
                                     [[resource_label.get(row['id'], row['id'])] + numeric(row['values'], 3) + [row['fits'] or r'\textemdash'] for row in tables['q2_resources']], '@{}Xrrrl@{}')
    directory = root / 'tables'
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in contents.items():
        (directory / f'{name}_{lang}.tex').write_text(content)


def render_figures(root, tables, probes, lang):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    plt.rcParams.update({'font.size': 9, 'pdf.fonttype': 42, 'savefig.bbox': 'tight'})
    formatter = FuncFormatter(lambda value, pos: f'{value:.2f}'.replace('.', ',') if lang == 'fr' else f'{value:.2f}')
    directory = root / 'figures'
    directory.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.2), sharey=True)
    for axis, year in zip(axes, ('2024', '2025'), strict=True):
        for variant, color, offset in [('graphsage_mean', '#17608d', 0), ('graphsage_none', '#b14529', 4)]:
            points = [row for row in probes if row['variant'] == variant and row['year'] == year]
            for index, row in enumerate(points):
                x = index + offset
                axis.plot([x, x], [row['before'], row['after']], color=color, linewidth=1.2)
                axis.scatter(x, row['before'], facecolors='white', edgecolors=color, zorder=3)
                axis.scatter(x, row['after'], color=color, zorder=3)
        axis.set_title(year)
        axis.set_xticks([0, 1, 2, 4, 5, 6], ['103', '211', '307', '103', '211', '307'])
        axis.set_xlabel('mean (d=8)           none (d=16)\nseed')
        axis.yaxis.set_major_formatter(formatter)
        axis.grid(axis='y', alpha=.2)
    axes[0].set_ylabel('Perte BPR du probe fixe' if lang == 'fr' else 'Fixed-probe BPR loss')
    fig.suptitle('Initiale (cercle ouvert) → finale (plein), 30 époques' if lang == 'fr' else 'Initial (open circle) → final (filled), 30 epochs')
    fig.tight_layout()
    fig.savefig(directory / f'q2_maude_learning_{lang}.pdf')
    fig.savefig(directory / f'q2_maude_learning_{lang}.png', dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.25))
    for axis, (task, year) in zip(axes, [('MAUDE', '2024'), ('MAUDE', '2025'), ('Part D', '2024')], strict=True):
        rows = [row for row in tables['q2_seed_sensitivity'] if row['task'] == task and row['year'] == year]
        for position, row in enumerate(rows):
            mean, low, high = row['values']
            axis.hlines(position, low, high, color='#17608d', linewidth=1.4)
            axis.scatter(list(row['by_seed'].values()), [position] * len(row['by_seed']), color='#17608d', s=16)
            axis.scatter(mean, position, color='#b14529', marker='D', s=23, zorder=4)
        axis.set_yticks(range(len(rows)), [LABELS[lang][row['id']] for row in rows])
        axis.invert_yaxis()
        axis.set_title(f'{task}, {year}')
        axis.set_xlabel('Rappel micro@10' if lang == 'fr' else 'Micro recall@10')
        axis.xaxis.set_major_formatter(formatter)
        axis.grid(axis='x', alpha=.2)
    fig.suptitle('Trois seeds ; segments min–max, losanges = moyennes (pas des IC)' if lang == 'fr' else 'Three seeds; min–max spans, diamonds = means (not CIs)')
    fig.tight_layout()
    fig.savefig(directory / f'q2_seed_sensitivity_{lang}.pdf')
    fig.savefig(directory / f'q2_seed_sensitivity_{lang}.png', dpi=170)
    plt.close(fig)
    return matplotlib.__version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    data = {key: json.loads((args.evidence_dir / name).read_text()) for key, name in SOURCES.items()}
    tables, probes = derive(data)
    versions = []
    for lang in ('fr', 'en'):
        render_tables(args.output_root, tables, lang)
        versions.append(render_figures(args.output_root, tables, probes, lang))
    sidecar = {'schema': 'healthgraphbench.rc3-rendered-evidence.v1', 'new_fit_score_bootstrap': False,
               'source_sha256': {name: digest(args.evidence_dir / name) for name in SOURCES.values()},
               'tables': tables, 'learning_probes': probes, 'matplotlib': versions[0],
               'seed_ranges_are_confidence_intervals': False, 'french_then_faithful_english': True}
    destination = args.output_root / 'data/q2/rendered_evidence.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'table_pairs': len(tables), 'figure_pairs': 2, 'learning_probe_count': len(probes), 'sidecar': str(destination)}))


if __name__ == '__main__':
    main()
