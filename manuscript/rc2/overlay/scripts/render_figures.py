#!/usr/bin/env python3
"""Render C/D1 figures from completed outputs; never train or recompute scores."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--duration-only', action='store_true',
                        help='Render only the two C duration figures; do not read D1 inputs.')
    args = parser.parse_args()
    root = args.root
    metrics = json.loads((root / 'data/post_rc1/post_rc1_metrics.json').read_text())
    if not args.duration_only:
        with (root / 'data/post_rc1/D1_epochs.csv').open() as stream:
            epochs = list(csv.DictReader(stream))
    output = root / 'figures'
    output.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    for language in ('fr', 'en'):
        french = language == 'fr'
        fits = metrics['C']['validation']['fits']
        durations = (0, 3, 10, 30)
        recalls = [fits[str(n)]['metrics']['1']['recall_at_10'] for n in durations]
        fig, ax = plt.subplots(figsize=(6.6, 3.7), layout='constrained')
        ax.plot(durations, recalls, 'o-', color='#27648e')
        for n, recall in zip(durations, recalls):
            ax.annotate(f'{recall:.6f}', (n, recall), xytext=(0, 9), textcoords='offset points', ha='center')
        ax.set(xticks=durations, ylim=(0, .24), xlabel='Époques' if french else 'Epochs',
               ylabel='Rappel micro à 10' if french else 'Micro recall@10',
               title='C — entraînements séparés, validation 2023' if french else 'C — separate training runs, 2023 validation')
        ax.grid(axis='y', alpha=.2)
        fig.savefig(output / f'maude_duration_RC2_{language}.png', dpi=180)
        plt.close(fig)
        if args.duration_only:
            continue
        fig, axes = plt.subplots(2, 1, figsize=(6.6, 6.4), layout='constrained')
        rows = metrics['D1']['primary_results']
        x = np.arange(len(rows))
        axes[0].bar(x - .18, [r['mean_r10'] for r in rows], .36, label='mean30 (C)', color='#27648e')
        axes[0].bar(x + .18, [r['none_r10'] for r in rows], .36, label='none30 (D1)', color='#d57536')
        axes[0].set(xticks=x, xticklabels=['Val. 2023', '2024', '2025', '2024–25'], ylim=(0, .25),
                    ylabel='Rappel micro à 10' if french else 'Micro recall@10',
                    title='D1 — mêmes cohortes, pas de nouvel IC' if french else 'D1 — same cohorts, no new CI')
        axes[0].legend(fontsize=8)
        axes[0].grid(axis='y', alpha=.2)
        colors = {'validation_2023': '#27648e', 'test_2024': '#557c36', 'test_2025': '#964d85'}
        labels = {'validation_2023': 'Val. 2023', 'test_2024': '2024', 'test_2025': '2025'}
        for model, style in (('mean30', '-'), ('none30', '--')):
            for split in colors:
                points = [r for r in epochs if r['record_type'] == 'training_epoch'
                          and r['model'] == model and r['split'] == split]
                points.sort(key=lambda r: int(r['epoch']))
                axes[1].plot([int(r['epoch']) for r in points], [float(r['mean_bpr_data_loss']) for r in points],
                             linestyle=style, color=colors[split], label=model + ' ' + labels[split])
        axes[1].axhline(np.log(2), color='grey', linewidth=.7, linestyle=':', label='ln(2)')
        axes[1].set(xlabel='Époque' if french else 'Epoch', ylabel='Perte BPR observée' if french else 'Observed BPR loss',
                    title='mean conservé; none nouveau' if french else 'Retained mean; new none')
        axes[1].legend(fontsize=8.5, ncol=3, loc='center', bbox_to_anchor=(.5, .55))
        axes[1].grid(alpha=.2)
        fig.savefig(output / f'maude_aggregation_RC2_{language}.png', dpi=180)
        plt.close(fig)
    if args.duration_only:
        print('Rendered two bilingual C duration figures from completed metrics; no fit or score recomputation.')
    else:
        print('Rendered four bilingual figures from completed C/D1 CSVs and metrics; no fit or score recomputation.')


if __name__ == '__main__':
    main()
