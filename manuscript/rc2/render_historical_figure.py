#!/usr/bin/env python3
"""Rebuild the historical GraphSAGE differences plot with its original intervals."""
import argparse
from pathlib import Path
import csv
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True,
                        help='Root of an unpacked manuscript package containing the retained numeric inputs.')
    root = parser.parse_args().root
    with (root / 'data/maude_cutoff_differences_R2.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    complementary = json.loads((root / 'data/maude_neighbors_vs_global_R2.json').read_text())['results']['metrics']['micro_recall_at_10']
    methods = ['global_popularity', 'matrix_factorization_spectral', 'graphsage_link_prediction']
    labels = {
        'fr': ['Popularité globale (IC complémentaire)', 'Factorisation spectrale', 'GraphSAGE historique, 3 époques (IC historique)'],
        'en': ['Global popularity (additional CI)', 'Spectral factorization', 'Historical GraphSAGE, 3 epochs (historical CI)'],
    }
    for language in ('fr', 'en'):
        fig, ax = plt.subplots(figsize=(6.2, 3.8))
        for method, label, marker in zip(methods, labels[language], ('o', 's', '^')):
            selected = [row for row in rows if row['method'] == method]
            x = [int(row['k']) for row in selected]
            y = [float(row['delta']) for row in selected]
            if method == 'graphsage_link_prediction':
                errors = np.array([[np.nan, y[1] + 0.023578, np.nan],
                                   [np.nan, -0.014845 - y[1], np.nan]])
                ax.errorbar(x, y, yerr=errors, fmt=marker + '-', capsize=4, label=label)
            elif method == 'global_popularity':
                low, high = -complementary['ci95'][1], -complementary['ci95'][0]
                if abs(y[1] + complementary['delta_a_minus_b']) > 1e-12:
                    raise ValueError('Global-neighbor point contrast has wrong sign')
                errors = np.array([[np.nan, y[1]-low, np.nan],
                                   [np.nan, high-y[1], np.nan]])
                ax.errorbar(x, y, yerr=errors, fmt=marker + '-', capsize=4, label=label)
            else:
                ax.plot(x, y, marker=marker, label=label)
        ax.axhline(0, linestyle=':', linewidth=1)
        ax.set_xticks([5, 10, 20])
        ax.set_xlabel('Nombre de propositions K' if language == 'fr' else 'Number of suggestions K')
        ax.set_ylabel('Différence de rappel micro\npar rapport aux voisins' if language == 'fr'
                      else 'Micro-recall difference\nrelative to neighbors')
        if language == 'fr':
            ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:.3f}'.replace('.', ',')))
        ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.02), ncol=2, fontsize=8, frameon=False)
        ax.grid(axis='y', alpha=0.25)
        fig.tight_layout()
        fig.savefig(root / f'figures/maude_cutoffs_historical3_{language}.pdf', bbox_inches='tight')
        fig.savefig(root / f'figures/maude_cutoffs_historical3_{language}.png', dpi=200, bbox_inches='tight')
        plt.close(fig)


if __name__ == '__main__':
    main()
