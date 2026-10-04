"""Synthetic node-label controls on a supplied ownership topology."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import date
from typing import Iterable, Mapping, Sequence

from ..evaluation.metrics import ranking_auc


def ownership_neighbors(
    records_by_ccn: Mapping[str, Iterable[tuple[str, date, str, str]]],
    cutoff: date,
) -> dict[str, frozenset[str]]:
    """Project active owner associations into an undirected CCN graph."""

    owner_to_ccns: dict[str, set[str]] = defaultdict(set)
    for ccn, records in records_by_ccn.items():
        for owner, association, _role, _owner_type in records:
            if association < cutoff:
                token = owner
                for prefix in ("INDIVIDUAL", "ORGANIZATION"):
                    if token.startswith(prefix):
                        token = token[len(prefix) :]
                        break
                owner_to_ccns[token].add(ccn)
    neighbors: dict[str, set[str]] = defaultdict(set)
    for ccns in owner_to_ccns.values():
        ordered = sorted(ccns)
        for index, left in enumerate(ordered):
            neighbors[left].update(ordered[:index])
            neighbors[left].update(ordered[index + 1 :])
    return {node: frozenset(values) for node, values in neighbors.items() if values}


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)


def run_control(
    neighbors: Mapping[str, Sequence[str]],
    *,
    beta: float,
    seed: int,
    train_fraction: float = 0.7,
) -> dict[str, float | int]:
    """Generate labels with local and relational signal and score held-out nodes."""

    nodes = tuple(sorted(node for node, values in neighbors.items() if values))
    if len(nodes) < 4:
        raise ValueError("topology control requires at least four non-isolated nodes")
    generator = random.Random(seed)
    local = {node: generator.gauss(0.0, 1.0) for node in nodes}
    raw_neighbor = {
        node: sum(local[peer] for peer in neighbors[node] if peer in local) / len(neighbors[node])
        for node in nodes
    }
    order = list(nodes)
    generator.shuffle(order)
    train_size = max(1, min(len(nodes) - 1, int(train_fraction * len(nodes))))
    train_nodes = set(order[:train_size])
    test_nodes = order[train_size:]
    train_values = [raw_neighbor[node] for node in train_nodes]
    mean = sum(train_values) / len(train_values)
    variance = sum((value - mean) ** 2 for value in train_values) / len(train_values)
    scale = math.sqrt(variance) if variance > 1e-12 else 1.0
    relational = {node: (raw_neighbor[node] - mean) / scale for node in nodes}
    labels = {
        node: int(generator.random() < _sigmoid(-1.0 + 0.5 * local[node] + beta * relational[node]))
        for node in nodes
    }
    test_labels = [labels[node] for node in test_nodes]
    local_auc = ranking_auc(test_labels, [local[node] for node in test_nodes])
    relational_auc = ranking_auc(test_labels, [relational[node] for node in test_nodes])
    return {
        "seed": seed,
        "beta": beta,
        "nodes": len(nodes),
        "undirected_links": sum(len(values) for values in neighbors.values()) // 2,
        "train_nodes": len(train_nodes),
        "test_nodes": len(test_nodes),
        "local_auc": local_auc,
        "relational_auc": relational_auc,
    }


def run_topology_controls(
    records_by_ccn: Mapping[str, Iterable[tuple[str, date, str, str]]],
    *,
    cutoff: date = date(2024, 1, 1),
    seeds: Sequence[int] = (301, 302, 303),
    betas: Sequence[float] = (0.0, 2.5),
) -> list[dict[str, float | int]]:
    neighbors = ownership_neighbors(records_by_ccn, cutoff)
    return [run_control(neighbors, beta=beta, seed=seed) for beta in betas for seed in seeds]
