"""Conditional paired entity-cluster uncertainty and observable review workload.

Intervals condition on fixed selected fits; they do not cover selection, training,
period variation, residual network dependence or clinical utility.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

KS = (1, 5, 10, 20, 50, 100)


def read_rows(path: str | Path, *, keep_recommendations: bool = False) -> list[dict[str, Any]]:
    """Load analysis inputs without retaining the large top100 lists by default."""
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    rows = []
    with opener(path, 'rt', encoding='utf-8') as source:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            if not keep_recommendations:
                row.pop('recommendations', None)
                row.pop('top100', None)
            rows.append(row)
    return rows


def _key(row: Mapping[str, Any]) -> tuple[str, str]:
    entity = row.get('entity_id', row.get('npi', row.get('product', row.get('ccn'))))
    period = row.get('period', row.get('quarter', row.get('date', row.get('year'))))
    if entity is None or period is None:
        raise ValueError('prediction requires an entity and an observation period')
    return str(entity), str(period)


def _positive_count(row: Mapping[str, Any]) -> int:
    return int(row.get('positive_count', row.get('positive_edges', len(row['positive_ranks']))))


def _ranks(row: Mapping[str, Any]) -> list[int]:
    return [int(value['rank'] if isinstance(value, dict) else value)
            for value in row['positive_ranks']]


def history_band(value: int, domain: str) -> str:
    if domain == 'maude':
        return '1-9' if value < 10 else '10-49' if value < 50 else '50-199' if value < 200 else '200+'
    return '<=10' if value <= 10 else '11-50' if value <= 50 else '>50'


def support_band(value: int) -> str:
    return '<=5' if value <= 5 else '6-50' if value <= 50 else '>50'


def neighbor_band(value: int) -> str:
    return '0' if value == 0 else '1-2' if value <= 2 else '3+'


def ranking_vectors(rows: Sequence[Mapping[str, Any]], k: int,
                    group: tuple[str, str] | None = None,
                    domain: str = 'partd') -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if k <= 0:
        raise ValueError('ranking cutoff must be positive')
    hits = np.zeros(len(rows), dtype=np.float64)
    positives = np.zeros(len(rows), dtype=np.float64)
    slots = np.zeros(len(rows), dtype=np.float64)
    selected = np.ones(len(rows), dtype=np.float64)
    for index, row in enumerate(rows):
        count = int(row['candidate_count'])
        if count < 0:
            raise ValueError('negative candidate count')
        positive_count = _positive_count(row)
        ranks = _ranks(row)
        if positive_count != len(ranks) or any(rank < 1 or rank > count for rank in ranks):
            raise ValueError('inconsistent positive ranks or denominator')
        if group is not None and group[0] == 'history':
            selected[index] = float(history_band(int(row['history_support']), domain) == group[1])
        if group is not None and group[0] in {'candidate_support', 'neighbor_support'}:
            items = row.get('positive_items')
            if items is None or len(items) != positive_count:
                raise ValueError('item strata require one historically annotated item per positive')
            field, classify = ('prior_support', support_band) if group[0] == 'candidate_support' else ('neighbor_support', neighbor_band)
            chosen = [item for item in items if classify(int(item[field])) == group[1]]
            hits[index] = sum(int(item['rank']) <= k for item in chosen)
            positives[index] = len(chosen)
            recommendations = row.get('recommendations', row.get('top100', row.get('top20', [])))
            slots[index] = sum(int(item['rank']) <= k and classify(int(item[field])) == group[1]
                               for item in recommendations)
        else:
            hits[index] = sum(rank <= k for rank in ranks)
            positives[index] = positive_count
            slots[index] = min(k, count)
    return hits * selected, positives * selected, slots * selected, selected


def _ratio(numerator: np.ndarray, denominator: np.ndarray, weights: np.ndarray | None = None) -> float | None:
    total = float(denominator.sum() if weights is None else denominator @ weights)
    if total <= 0:
        return None
    value = float(numerator.sum() if weights is None else numerator @ weights)
    return value / total


def ranking_summary(rows: Sequence[Mapping[str, Any]], domain: str = 'partd') -> dict[str, Any]:
    keys = [_key(row) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate entity-period prediction')
    total_positives = sum(_positive_count(row) for row in rows)
    summary: dict[str, Any] = {
        'entity_periods': len(rows), 'unique_entities': len({key[0] for key in keys}),
        'positive_total': total_positives,
        'zero_positive_entity_periods': sum(_positive_count(row) == 0 for row in rows),
        'zero_positive_fraction': sum(_positive_count(row) == 0 for row in rows) / len(rows) if rows else None,
        'workload': {}, 'strata': {},
        'interpretation': 'Observed published links, not clinical correctness; K is review workload, not a confidence threshold.',
    }
    for k in KS:
        hits, positives, slots, selected = ranking_vectors(rows, k, domain=domain)
        summary['workload'][str(k)] = {
            'retrieved_observed_links': int(hits.sum()), 'actual_proposal_slots': int(slots.sum()),
            'micro_recall': _ratio(hits, positives), 'observed_precision': _ratio(hits, slots),
            'entity_period_hit_coverage': float(np.mean(hits > 0)) if len(rows) else None,
            'entity_periods_with_proposals': int(np.sum(slots > 0)),
        }
    groups = [('history', name) for name in (('1-9', '10-49', '50-199', '200+') if domain == 'maude' else ('<=10', '11-50', '>50'))]
    groups += [('candidate_support', name) for name in ('<=5', '6-50', '>50')]
    groups += [('neighbor_support', name) for name in ('0', '1-2', '3+')]
    for group in groups:
        hits, positives, slots, selected = ranking_vectors(rows, 10, group, domain)
        summary['strata']['/'.join(group)] = {
            'positive_total': int(positives.sum()), 'hits_at_10': int(hits.sum()),
            'micro_recall_at_10': _ratio(hits, positives),
            'entity_period_count': int(selected.sum()) if group[0] == 'history' else len(rows),
            'definition_before_target': True,
        }
    return summary


def _aligned_streams(streams: Sequence[Sequence[Mapping[str, Any]]], keys: list[tuple[str, str]]) -> list[list[Mapping[str, Any]]]:
    if not streams:
        raise ValueError('missing prediction streams')
    aligned = []
    for stream in streams:
        lookup = {_key(row): row for row in stream}
        if len(lookup) != len(stream) or set(lookup) != set(keys):
            raise ValueError('paired streams must contain the same unique entity-periods')
        aligned.append([lookup[key] for key in keys])
    return aligned


def ranking_contrast(left: Sequence[Sequence[Mapping[str, Any]]],
                     right: Sequence[Sequence[Mapping[str, Any]]], *,
                     k: int = 10, group: tuple[str, str] | None = None,
                     domain: str = 'partd', draws: int = 2000, seed: int = 313,
                     practical_margin: float = .01) -> dict[str, Any]:
    if draws <= 0:
        raise ValueError('bootstrap draws must be positive')
    keys = sorted(_key(row) for row in left[0])
    a = _aligned_streams(left, keys)
    b = _aligned_streams(right, keys)
    positive_counts = np.asarray([_positive_count(row) for row in a[0]])
    candidates = np.asarray([int(row['candidate_count']) for row in a[0]])
    for stream in a + b:
        if not np.array_equal(positive_counts, [_positive_count(row) for row in stream]) or not np.array_equal(candidates, [int(row['candidate_count']) for row in stream]):
            raise ValueError('paired comparison changed targets or candidate counts')
    av = [ranking_vectors(stream, k, group, domain) for stream in a]
    bv = [ranking_vectors(stream, k, group, domain) for stream in b]
    denominator = av[0][1]
    if any(not np.array_equal(denominator, values[1]) for values in av + bv):
        raise ValueError('paired comparison changed pre-target stratum membership')
    ah = np.mean([values[0] for values in av], axis=0)
    bh = np.mean([values[0] for values in bv], axis=0)
    entities = sorted({key[0] for key in keys})
    mapping = {entity: index for index, entity in enumerate(entities)}
    cluster_index = np.asarray([mapping[key[0]] for key in keys], dtype=np.int64)
    delta = _ratio(ah - bh, denominator)
    generator = np.random.default_rng(seed)
    samples = []
    for _ in range(draws if delta is not None else 0):
        counts = np.bincount(generator.integers(0, len(entities), len(entities)), minlength=len(entities))
        value = _ratio(ah - bh, denominator, counts[cluster_index])
        if value is not None:
            samples.append(value)
    interval = np.quantile(samples, [.025, .975]).tolist() if samples else None
    return {
        'delta_micro_recall_at_' + str(k): delta, 'conditional_paired_cluster_interval_95': interval,
        'requested_draws': draws, 'valid_draws': len(samples), 'bootstrap_seed': seed,
        'cluster_unit': 'provider' if domain == 'partd' else 'product', 'clusters': len(entities),
        'left_seed_metrics': [_ratio(values[0], denominator) for values in av],
        'right_seed_metrics': [_ratio(values[0], denominator) for values in bv],
        'training_seed_resampling': False, 'configuration_selection_covered': False,
        'period_or_network_independence_claimed': False, 'evidence_level': 'exploratory_conditional_on_fits',
        'practical_margin_absolute': practical_margin,
        'positive_gain_at_least_margin_excluded_conditionally': bool(interval is not None and interval[1] < practical_margin),
        'interval_inside_plus_minus_margin_conditionally': bool(interval is not None and interval[0] > -practical_margin and interval[1] < practical_margin),
        'margin_is_clinical_utility_threshold': False,
    }


def _auc_layout(labels: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(scores, kind='stable')
    starts = np.r_[0, np.flatnonzero(np.diff(scores[order])) + 1]
    return order, starts, labels[order]


def _auc(labels: np.ndarray, scores: np.ndarray, weights: np.ndarray | None = None, *,
         layout: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None) -> float | None:
    weights = np.ones(labels.size) if weights is None else weights
    order, starts, ordered_labels = _auc_layout(labels, scores) if layout is None else layout
    ordered_weights = weights[order]
    positive = ordered_weights * ordered_labels
    negative = ordered_weights * (1 - ordered_labels)
    p, n = float(positive.sum()), float(negative.sum())
    if p <= 0 or n <= 0:
        return None
    grouped_positive = np.add.reduceat(positive, starts)
    grouped_negative = np.add.reduceat(negative, starts)
    below = np.cumsum(grouped_negative) - grouped_negative
    return float(grouped_positive @ (below + .5 * grouped_negative) / (p * n))


def cms_contrast(left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]], *,
                 draws: int = 2000, seed: int = 313, practical_margin: float = .01) -> dict[str, Any]:
    keys = sorted(_key(row) for row in left)
    a, b = _aligned_streams([left, right], keys)
    labels = np.asarray([int(row['label']) for row in a], dtype=np.int64)
    if not np.array_equal(labels, [int(row['label']) for row in b]):
        raise ValueError('paired inspection comparison changed labels')
    scores_a = np.asarray([float(row['score']) for row in a])
    scores_b = np.asarray([float(row['score']) for row in b])
    entities = sorted({key[0] for key in keys})
    mapping = {entity: index for index, entity in enumerate(entities)}
    cluster_index = np.asarray([mapping[key[0]] for key in keys], dtype=np.int64)
    layout_a, layout_b = _auc_layout(labels, scores_a), _auc_layout(labels, scores_b)
    point_a, point_b = _auc(labels, scores_a, layout=layout_a), _auc(labels, scores_b, layout=layout_b)
    generator = np.random.default_rng(seed)
    samples = []
    for _ in range(draws if point_a is not None and point_b is not None else 0):
        weights = np.bincount(generator.integers(0, len(entities), len(entities)), minlength=len(entities))[cluster_index]
        va, vb = _auc(labels, scores_a, weights, layout=layout_a), _auc(labels, scores_b, weights, layout=layout_b)
        if va is not None and vb is not None:
            samples.append(va - vb)
    interval = np.quantile(samples, [.025, .975]).tolist() if samples else None
    return {'delta_roc_auc': None if point_a is None or point_b is None else point_a - point_b,
            'left_roc_auc': point_a, 'right_roc_auc': point_b,
            'conditional_paired_facility_interval_95': interval,
            'requested_draws': draws, 'valid_draws': len(samples), 'bootstrap_seed': seed,
            'facilities': len(entities), 'inspection_rows': len(a),
            'configuration_selection_covered': False, 'period_or_network_independence_claimed': False,
            'evidence_level': 'exploratory_conditional_on_fits',
            'practical_margin_absolute': practical_margin,
            'positive_gain_at_least_margin_excluded_conditionally': bool(interval is not None and interval[1] < practical_margin),
            'interval_inside_plus_minus_margin_conditionally': bool(interval is not None and interval[0] > -practical_margin and interval[1] < practical_margin),
            'margin_is_clinical_utility_threshold': False}


def preflight() -> dict[str, Any]:
    a = [dict(entity_id='a', period=2024, candidate_count=3, positive_count=1,
              positive_ranks=[1], history_support=2,
              positive_items=[dict(item_id='x', rank=1, prior_support=1, neighbor_support=0)]),
         dict(entity_id='b', period=2024, candidate_count=2, positive_count=0,
              positive_ranks=[], history_support=2, positive_items=[])]
    b = [{**row, 'positive_ranks': [3], 'positive_items': [dict(item_id='x', rank=3, prior_support=1, neighbor_support=0)]} if row['positive_count'] else row for row in a]
    vectors = ranking_vectors(a, 1)
    assert _ratio(vectors[0], vectors[2]) == .5
    assert ranking_contrast([a], [b], k=1, draws=64)['delta_micro_recall_at_1'] == 1.0
    assert _auc(np.asarray([0, 1]), np.asarray([.5, .5])) == .5
    assert _auc(np.asarray([0, 1]), np.asarray([0., 1.])) == 1.0
    return {'zero_positive_workload_precision': .5, 'paired_delta': 1.0, 'tied_auc': .5,
            'bootstrap_cluster_unit_not_training_seed': True}
