"""Pair retained MAUDE C30 ranks with historical neighbor contributions.

No model is fitted or scored. Historical full candidate IDs were not exported:
their rule is reconstructed from pinned prepared history, and counts/positive
IDs are crosschecked against the original historical prediction export.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import resource
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np
import healthgraphbench.evaluation.bootstrap as bootstrap


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _interval(rows, *, resamples, seed):
    """Resample products, keeping every quarter and a shared denominator."""
    totals = defaultdict(lambda: [0, 0])
    for row in rows:
        positives = int(row['positive_edges'])
        a, b = int(row['hits_C30_at_10']), int(row['hits_neighbors_at_10'])
        _require(positives > 0 and 0 <= a <= positives and 0 <= b <= positives,
                 'invalid positive/hit count')
        group = totals[str(row['product'])]
        group[0] += a - b
        group[1] += positives
    products = sorted(totals)
    counts = np.asarray([totals[p] for p in products], dtype=np.int64)
    indices = bootstrap.cluster_bootstrap_indices(products, resamples=resamples, seed=seed)
    numerators = counts[:, 0][indices].sum(axis=1)
    denominators = counts[:, 1][indices].sum(axis=1)
    _require(bool(np.all(denominators > 0)), 'undefined bootstrap draw')
    draws = numerators / denominators
    bounds = np.quantile(draws, [0.025, 0.975], method='linear')
    return {'estimate': float(counts[:, 0].sum() / counts[:, 1].sum()),
            'ci95': bounds.tolist(), 'resamples': resamples, 'seed': seed,
            'clusters': len(products), 'valid_resamples': len(draws),
            'undefined_resamples': 0}, draws


def _pair_quarter(quarter, sets, predictions, historical, history_predictions,
                  product_problems, known_problems, reports):
    """Reject label/candidate/cohort mismatches rather than using an intersection."""
    _require(set(sets) == set(historical), f'{quarter}: product key mismatch')
    _require(set(predictions) == set(sets), f'{quarter}: C prediction key mismatch')
    _require(set(history_predictions) == set(sets), f'{quarter}: historical prediction key mismatch')
    paired = []
    for product in sorted(sets):
        row, old, observed = sets[product], historical[product], history_predictions[product]
        ids = row['candidate_ids']
        positives = set(row['positive_problem_ids'])
        _require(len(positives) == len(row['positive_problem_ids']) and bool(positives),
                 f'{quarter}/{product}: duplicate/empty positive IDs')
        expected_ids = sorted(known_problems - product_problems.get(product, set()))
        _require(ids == expected_ids, f'{quarter}/{product}: candidate IDs differ from fixed history')
        _require(row['candidate_set_sha256'] == json_digest(ids), f'{quarter}/{product}: candidate hash mismatch')
        _require(positives == observed['positive_ids'], f'{quarter}/{product}: historical positive labels mismatch')
        _require(observed['candidate_counts'] == {len(ids)}, f'{quarter}/{product}: historical candidate count mismatch')
        _require(observed['support'] == {int(row['history_product_reports'])}, f'{quarter}/{product}: historical prediction support mismatch')
        _require(int(old['history_support']) == int(row['history_product_reports']) == reports.get(product, 0),
                 f'{quarter}/{product}: historical support mismatch')
        _require(int(old['positive_edges']) == len(positives), f'{quarter}/{product}: positive denominator mismatch')
        c = predictions[product]
        _require(c['ids'] == set(ids) and c['positive_ids'] == positives,
                 f'{quarter}/{product}: C labels/candidates mismatch')
        _require(c['ranks'] == set(range(1, len(ids) + 1)), f'{quarter}/{product}: C rank permutation mismatch')
        a, b = c['hits'], int(old['hits_at_10'])
        _require(0 <= a <= len(positives) and 0 <= b <= len(positives), f'{quarter}/{product}: invalid hits')
        paired.append({'product': product, 'quarter': quarter,
                       'history_support': reports[product], 'positive_edges': len(positives),
                       'candidate_count': len(ids), 'candidate_set_sha256': row['candidate_set_sha256'],
                       'positive_ids_sha256': json_digest(sorted(positives)),
                       'hits_C30_at_10': a, 'hits_neighbors_at_10': b})
    return paired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--input-root', type=Path, default=REPO)
    parser.add_argument('--replay-contributions', type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('Output must be new; retained analyses are immutable.')
    started = time.monotonic()
    protocol = json.loads(args.protocol.read_text())
    limits = protocol['limits']
    def guard():
        _require(time.monotonic() - started < limits['wall_seconds'], 'wall-time limit exceeded')
        _require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 < limits['rss_bytes'], 'RSS limit exceeded')
    inputs = []
    if args.replay_contributions:
        with args.replay_contributions.open(newline='') as source:
            rows = list(csv.DictReader(source))
        inputs.append({'role': 'paired_contributions', 'sha256': digest(args.replay_contributions)})
        pairing_scope = 'Compact replay only; original candidate/label inputs not rechecked.'
    else:
        by_role = defaultdict(dict)
        for row in protocol['inputs']:
            path = args.input_root / row['path']
            _require(digest(path) == row['sha256'], 'changed input: ' + row['path'])
            by_role[row['role']][row.get('quarter', '')] = path
            inputs.append(row)
            guard()
        historical = json.loads(by_role['historical_execution'][''].read_text())
        task = next(t for t in historical['tasks'] if t['task'] == 'maude')
        method = next(m for m in task['methods'] if m['method'] == 'neighbor_frequency')
        quarters = protocol['population']['quarters']
        old_rows = defaultdict(dict)
        for row in method['entity_metrics']:
            q, p = row['quarter'], row['product']
            if q in quarters:
                _require(p not in old_rows[q], f'{q}/{p}: duplicate historical contribution')
                old_rows[q][p] = row
        old_predictions = defaultdict(lambda: defaultdict(lambda: {'positive_ids': set(), 'candidate_counts': set(), 'support': set(), 'seen_ids': set()}))
        for row in method['prediction_rows']:
            q, p = row['quarter'], row['product']
            if q in quarters:
                item = old_predictions[q][p]
                _require(row['problem'] not in item['seen_ids'], f'{q}/{p}: duplicate historical prediction')
                item['seen_ids'].add(row['problem'])
                if int(row['label']) == 1:
                    item['positive_ids'].add(row['problem'])
                item['candidate_counts'].add(int(row['candidate_count']))
                item['support'].add(int(row['history_support']))
        del historical, task, method
        with gzip.open(by_role['prepared_snapshots'][''], 'rt') as source:
            prepared = json.load(source)
        # Prepared format is the same frozen list consumed by the C diagnostic.
        snapshots = prepared['snapshots'] if isinstance(prepared, dict) else prepared
        product_problems, known_problems, reports = defaultdict(set), set(), defaultdict(int)
        rows = []
        for snapshot in snapshots:
            quarter = snapshot['quarter']
            if quarter in quarters:
                sets = {}
                with gzip.open(by_role['C_sets'][quarter], 'rt') as source:
                    for line in source:
                        row = json.loads(line)
                        p = row['product']
                        _require(row['quarter'] == quarter and p not in sets, 'duplicate/misdated C candidate list')
                        sets[p] = row
                predictions = defaultdict(lambda: {'ids': set(), 'positive_ids': set(), 'ranks': set(), 'hits': 0})
                with gzip.open(by_role['C_predictions'][quarter], 'rt') as source:
                    for index, line in enumerate(source):
                        row = json.loads(line)
                        p = row['product']
                        _require(p in sets and row['quarter'] == quarter, 'unexpected C prediction product/quarter')
                        item = predictions[p]
                        _require(row['problem'] not in item['ids'], 'duplicate C candidate prediction')
                        _require(row['candidate_set_sha256'] == sets[p]['candidate_set_sha256'], 'C prediction candidate hash mismatch')
                        _require(row['label'] in (0, 1) and isinstance(row['rank'], int), 'invalid C label/rank')
                        item['ids'].add(row['problem']); item['ranks'].add(row['rank'])
                        if row['label'] == 1:
                            item['positive_ids'].add(row['problem'])
                            item['hits'] += row['rank'] <= 10
                        if index % 25000 == 0:
                            guard()
                rows.extend(_pair_quarter(quarter, sets, predictions, old_rows[quarter], old_predictions[quarter],
                                          product_problems, known_problems, reports))
                guard()
            for p, count in snapshot['product_reports'].items():
                reports[p] += int(count)
            for p, problem in snapshot['edges']:
                product_problems[p].add(problem); known_problems.add(problem)
        pairing_scope = protocol['pairing']['candidate_check']
        del prepared, snapshots, sets, predictions, old_rows, old_predictions
    rows.sort(key=lambda row: (row['product'], row['quarter']))
    expected = protocol['population']
    _require(len({(r['product'], r['quarter']) for r in rows}) == len(rows), 'duplicate paired key')
    _require(len(rows) == expected['expected_observations'], 'paired observation count mismatch')
    positives = sum(int(r['positive_edges']) for r in rows)
    _require(positives == expected['expected_positive_edges'], 'paired positive count mismatch')
    candidates = sum(int(r['candidate_count']) for r in rows)
    _require(candidates == expected['expected_candidate_pairs'], 'paired candidate count mismatch')
    _require(set(r['quarter'] for r in rows) == set(expected['quarters']), 'paired quarter set mismatch')
    cfg = protocol['bootstrap']
    interval, draws = _interval(rows, resamples=cfg['resamples'], seed=cfg['seed'])
    _require(interval['clusters'] == expected['expected_products'], 'paired cluster count mismatch')
    guard()
    args.output_dir.mkdir(parents=True)
    with (args.output_dir / 'paired_contributions.csv').open('w', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (args.output_dir / 'bootstrap_draws.json').write_text(json.dumps(draws.tolist()) + '\n')
    a, b = sum(int(r['hits_C30_at_10']) for r in rows), sum(int(r['hits_neighbors_at_10']) for r in rows)
    result = {'analysis': protocol['analysis'], 'status': 'completed',
              'protocol_sha256': digest(args.protocol), 'code_sha256': digest(Path(__file__)),
              'bootstrap_helper_sha256': digest(Path(bootstrap.__file__)),
              'executed_at_utc': datetime.now(timezone.utc).isoformat(), 'inputs': inputs,
              'pairing': {'scope': pairing_scope, 'observations': len(rows), 'positive_edges': positives,
                          'candidate_pairs': candidates, 'products': interval['clusters'], 'mismatches': 0},
              'point': {'C30_hits': a, 'neighbors_hits': b, 'positive_edges': positives,
                        'C30_r10': a / positives, 'neighbors_r10': b / positives},
              'interval': interval, 'scope': protocol['scope'],
              'cost': {'wall_seconds': time.monotonic() - started,
                       'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024},
              'environment': {'python': sys.version, 'numpy': np.__version__},
              'contributions_sha256': digest(args.output_dir / 'paired_contributions.csv'),
              'draws_sha256': digest(args.output_dir / 'bootstrap_draws.json')}
    (args.output_dir / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    _require(sum(p.stat().st_size for p in args.output_dir.iterdir()) < limits['output_bytes'], 'output limit exceeded')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
