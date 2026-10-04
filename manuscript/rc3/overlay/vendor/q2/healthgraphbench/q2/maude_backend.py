"""Faithful, seeded numeric backends for the Q2 MAUDE latent models.

Numba is deliberately required when these fitters run; there is no slower
fallback whose behavior could silently differ from the published protocol.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..tasks.maude.models import History, _sample_graph_neighbors


@dataclass(frozen=True, slots=True)
class LatentRanker:
    products: tuple[str, ...]
    problems: tuple[str, ...]
    product_vectors: Mapping[str, tuple[float, ...]]
    problem_vectors: Mapping[str, tuple[float, ...]]
    configuration: Mapping[str, int | float | str]

    def score(self, product: str, problem: str) -> float:
        left = self.product_vectors.get(product)
        right = self.problem_vectors.get(problem)
        if left is None or right is None:
            return 0.0
        return math.fsum(a * b for a, b in zip(left, right, strict=True))


def _numeric_libraries() -> tuple[Any, Any]:
    try:
        import numpy as np
        from numba import njit
    except ImportError as error:
        raise RuntimeError(
            "The MAUDE Q2 latent backend requires the optional q2 dependencies "
            "NumPy and Numba; install the `q2` extra."
        ) from error
    return np, njit


def _kernels() -> tuple[Any, Any, Any]:
    """Return lazily compiled kernels; importing the package never compiles code."""
    global _COMPILED_KERNELS
    cached = globals().get("_COMPILED_KERNELS")
    if cached is not None:
        return cached
    np, njit = _numeric_libraries()
    from numba.extending import register_jitable

    for helper in (_triplet_start, _contains_sorted, _add_touched, _softplus_negative):
        register_jitable(helper)
    train = njit(cache=False, fastmath=False)(_train_graphsage_kernel)
    probe = njit(cache=False, fastmath=False)(_graphsage_probe_kernel)
    bpr = njit(cache=False, fastmath=False)(_train_bpr_kernel)
    _COMPILED_KERNELS = (train, probe, bpr)
    return _COMPILED_KERNELS


def _triplet_start(seed: int, epoch: int, product: int, positive: int, size: int) -> int:
    # Small bounded integer mixing is deterministic and has no per-triplet allocation.
    value = (
        (seed + 1) * 1_103_515_245
        + (epoch + 1) * 12_345
        + (product + 1) * 2_654_435_761
        + (positive + 1) * 2_246_822_519
    ) % 2_147_483_647
    return value % size


def _contains_sorted(values: Any, start: int, end: int, item: int) -> bool:
    low = start
    high = end
    while low < high:
        middle = (low + high) // 2
        current = values[middle]
        if current < item:
            low = middle + 1
        else:
            high = middle
    return low < end and values[low] == item


def _add_touched(
    ids: Any,
    gradients: Any,
    count: int,
    node: int,
    values: Any,
    dimension: int,
) -> int:
    position = -1
    for index in range(count):
        if ids[index] == node:
            position = index
            break
    if position < 0:
        position = count
        ids[position] = node
        for component in range(dimension):
            gradients[position, component] = 0.0
        count += 1
    for component in range(dimension):
        gradients[position, component] += values[component]
    return count


def _softplus_negative(margin: float) -> float:
    if margin >= 0.0:
        return math.log1p(math.exp(-margin))
    return -margin + math.log1p(math.exp(margin))


def _train_graphsage_kernel(
    product_inputs: Any,
    problem_inputs: Any,
    self_weights: Any,
    neighbor_weights: Any,
    product_neighbors: Any,
    problem_neighbors: Any,
    positive_product: Any,
    positive_problem: Any,
    product_positive_values: Any,
    product_positive_offsets: Any,
    epochs: int,
    learning_rate: float,
    regularization: float,
    seed: int,
    use_neighbors: bool,
) -> Any:
    _, dimension = product_inputs.shape
    problem_count = problem_inputs.shape[0]
    fanout = product_neighbors.shape[1]
    triplet_count = positive_product.shape[0]
    epoch_trace = []

    hidden = np.empty((3, dimension), dtype=np.float64)
    means = np.empty((3, dimension), dtype=np.float64)
    pre_gradient = np.empty((3, dimension), dtype=np.float64)
    own_gradient = np.empty((3, dimension), dtype=np.float64)
    neighbor_gradient = np.empty((3, dimension), dtype=np.float64)
    self_gradient = np.empty((dimension, dimension), dtype=np.float64)
    neighbor_weight_gradient = np.empty((dimension, dimension), dtype=np.float64)
    product_touched = np.empty((1 + 2 * fanout,), dtype=np.int64)
    problem_touched = np.empty((2 + fanout,), dtype=np.int64)
    product_gradients = np.empty((1 + 2 * fanout, dimension), dtype=np.float64)
    problem_gradients = np.empty((2 + fanout, dimension), dtype=np.float64)

    for epoch in range(epochs):
        loss_sum = 0.0
        steps = 0
        skipped = 0
        for triplet in range(triplet_count):
            product = positive_product[triplet]
            positive = positive_problem[triplet]
            start = _triplet_start(seed, epoch, product, positive, problem_count)
            negative = -1
            for offset in range(problem_count):
                candidate = (start + offset) % problem_count
                if not _contains_sorted(
                    product_positive_values,
                    product_positive_offsets[product],
                    product_positive_offsets[product + 1],
                    candidate,
                ):
                    negative = candidate
                    break
            if negative < 0:
                skipped += 1
                continue

            for role in range(3):
                node = product if role == 0 else positive if role == 1 else negative
                product_side = role == 0
                if product_side:
                    own = product_inputs[node]
                    adjacency = product_neighbors[node]
                    neighbor_inputs = problem_inputs
                else:
                    own = problem_inputs[node]
                    adjacency = problem_neighbors[node]
                    neighbor_inputs = product_inputs
                for component in range(dimension):
                    means[role][component] = 0.0
                neighbor_count = 0
                if use_neighbors:
                    for slot in range(fanout):
                        neighbor = adjacency[slot]
                        if neighbor < 0:
                            break
                        neighbor_count += 1
                        for component in range(dimension):
                            means[role][component] += neighbor_inputs[neighbor, component]
                    if neighbor_count:
                        for component in range(dimension):
                            means[role][component] /= neighbor_count
                for row in range(dimension):
                    value = 0.0
                    for column in range(dimension):
                        value += self_weights[row, column] * own[column]
                        if use_neighbors:
                            value += neighbor_weights[row, column] * means[role][column]
                    hidden[role][row] = math.tanh(value)

            margin = 0.0
            for component in range(dimension):
                margin += hidden[0][component] * (
                    hidden[1][component] - hidden[2][component]
                )
            loss_sum += _softplus_negative(margin)
            if margin >= 0.0:
                coefficient = math.exp(-margin) / (1.0 + math.exp(-margin))
            else:
                coefficient = 1.0 / (1.0 + math.exp(margin))
            for component in range(dimension):
                pre_gradient[0][component] = (
                    coefficient
                    * (hidden[1][component] - hidden[2][component])
                    * (1.0 - hidden[0][component] * hidden[0][component])
                )
                pre_gradient[1][component] = (
                    coefficient
                    * hidden[0][component]
                    * (1.0 - hidden[1][component] * hidden[1][component])
                )
                pre_gradient[2][component] = (
                    -coefficient
                    * hidden[0][component]
                    * (1.0 - hidden[2][component] * hidden[2][component])
                )

            product_touched_count = 0
            problem_touched_count = 0
            for row in range(dimension):
                for column in range(dimension):
                    self_gradient[row][column] = 0.0
                    neighbor_weight_gradient[row][column] = 0.0
            for role in range(3):
                node = product if role == 0 else positive if role == 1 else negative
                product_side = role == 0
                if product_side:
                    own = product_inputs[node]
                    adjacency = product_neighbors[node]
                    neighbor_inputs = problem_inputs
                    own_table_ids = product_touched
                    own_table_grads = product_gradients
                    neighbor_table_ids = problem_touched
                    neighbor_table_grads = problem_gradients
                else:
                    own = problem_inputs[node]
                    adjacency = problem_neighbors[node]
                    neighbor_inputs = product_inputs
                    own_table_ids = problem_touched
                    own_table_grads = problem_gradients
                    neighbor_table_ids = product_touched
                    neighbor_table_grads = product_gradients
                neighbor_count = 0
                if use_neighbors:
                    for slot in range(fanout):
                        if adjacency[slot] < 0:
                            break
                        neighbor_count += 1
                for column in range(dimension):
                    value = 0.0
                    for row in range(dimension):
                        value += self_weights[row, column] * pre_gradient[role][row]
                    own_gradient[role][column] = value
                if product_side:
                    product_touched_count = _add_touched(
                        own_table_ids,
                        own_table_grads,
                        product_touched_count,
                        node,
                        own_gradient[role],
                        dimension,
                    )
                else:
                    problem_touched_count = _add_touched(
                        own_table_ids,
                        own_table_grads,
                        problem_touched_count,
                        node,
                        own_gradient[role],
                        dimension,
                    )
                for row in range(dimension):
                    for column in range(dimension):
                        self_gradient[row][column] += pre_gradient[role][row] * own[column]
                        if use_neighbors:
                            neighbor_weight_gradient[row][column] += (
                                pre_gradient[role][row] * means[role][column]
                            )
                if use_neighbors:
                    for column in range(dimension):
                        value = 0.0
                        for row in range(dimension):
                            value += neighbor_weights[row, column] * pre_gradient[role][row]
                        neighbor_gradient[role][column] = value / max(1, neighbor_count)
                    for slot in range(fanout):
                        neighbor = adjacency[slot]
                        if neighbor < 0:
                            break
                        if product_side:
                            problem_touched_count = _add_touched(
                                neighbor_table_ids,
                                neighbor_table_grads,
                                problem_touched_count,
                                neighbor,
                                neighbor_gradient[role],
                                dimension,
                            )
                        else:
                            product_touched_count = _add_touched(
                                neighbor_table_ids,
                                neighbor_table_grads,
                                product_touched_count,
                                neighbor,
                                neighbor_gradient[role],
                                dimension,
                            )

            for row in range(dimension):
                for column in range(dimension):
                    self_weights[row, column] += learning_rate * (
                        self_gradient[row][column]
                        - regularization * self_weights[row, column]
                    )
                    if use_neighbors:
                        neighbor_weights[row, column] += learning_rate * (
                            neighbor_weight_gradient[row][column]
                            - regularization * neighbor_weights[row, column]
                        )
            for touched in range(product_touched_count):
                node = product_touched[touched]
                for component in range(dimension):
                    product_inputs[node, component] += learning_rate * (
                        product_gradients[touched][component]
                        - regularization * product_inputs[node, component]
                    )
            for touched in range(problem_touched_count):
                node = problem_touched[touched]
                for component in range(dimension):
                    problem_inputs[node, component] += learning_rate * (
                        problem_gradients[touched][component]
                        - regularization * problem_inputs[node, component]
                    )
            steps += 1
        epoch_trace.append((epoch + 1, steps, skipped, loss_sum / steps if steps else math.nan))
    return epoch_trace


def _graphsage_probe_kernel(
    product_inputs: Any,
    problem_inputs: Any,
    self_weights: Any,
    neighbor_weights: Any,
    product_neighbors: Any,
    problem_neighbors: Any,
    probe_product: Any,
    probe_positive: Any,
    probe_negative: Any,
    use_neighbors: bool,
) -> float:
    dimension = product_inputs.shape[1]
    fanout = product_neighbors.shape[1]
    hidden = np.empty((3, dimension), dtype=np.float64)
    means = np.empty((3, dimension), dtype=np.float64)
    total = 0.0
    count = probe_product.shape[0]
    for index in range(count):
        product = probe_product[index]
        positive = probe_positive[index]
        negative = probe_negative[index]
        for role in range(3):
            node = product if role == 0 else positive if role == 1 else negative
            product_side = role == 0
            if product_side:
                own = product_inputs[node]
                adjacency = product_neighbors[node]
                neighbor_inputs = problem_inputs
            else:
                own = problem_inputs[node]
                adjacency = problem_neighbors[node]
                neighbor_inputs = product_inputs
            for component in range(dimension):
                means[role][component] = 0.0
            neighbor_count = 0
            if use_neighbors:
                for slot in range(fanout):
                    neighbor = adjacency[slot]
                    if neighbor < 0:
                        break
                    neighbor_count += 1
                    for component in range(dimension):
                        means[role][component] += neighbor_inputs[neighbor, component]
                if neighbor_count:
                    for component in range(dimension):
                        means[role][component] /= neighbor_count
            for row in range(dimension):
                value = 0.0
                for column in range(dimension):
                    value += self_weights[row, column] * own[column]
                    if use_neighbors:
                        value += neighbor_weights[row, column] * means[role][column]
                hidden[role][row] = math.tanh(value)
        margin = 0.0
        for component in range(dimension):
            margin += hidden[0][component] * (hidden[1][component] - hidden[2][component])
        total += _softplus_negative(margin)
    return total / count if count else math.nan

def _train_bpr_kernel(
    product_vectors: Any,
    problem_vectors: Any,
    positive_product: Any,
    positive_problem: Any,
    product_positive_values: Any,
    product_positive_offsets: Any,
    epochs: int,
    learning_rate: float,
    regularization: float,
    seed: int,
) -> Any:
    dimension = product_vectors.shape[1]
    problem_count = problem_vectors.shape[0]
    product_before = np.empty(dimension, dtype=np.float64)
    positive_before = np.empty(dimension, dtype=np.float64)
    negative_before = np.empty(dimension, dtype=np.float64)
    traces = []
    for epoch in range(epochs):
        loss_sum = 0.0
        steps = 0
        skipped = 0
        for index in range(positive_product.shape[0]):
            product = positive_product[index]
            positive = positive_problem[index]
            start = _triplet_start(seed, epoch, product, positive, problem_count)
            negative = -1
            for offset in range(problem_count):
                candidate = (start + offset) % problem_count
                if not _contains_sorted(
                    product_positive_values,
                    product_positive_offsets[product],
                    product_positive_offsets[product + 1],
                    candidate,
                ):
                    negative = candidate
                    break
            if negative < 0:
                skipped += 1
                continue
            margin = 0.0
            for component in range(dimension):
                margin += product_vectors[product, component] * (
                    problem_vectors[positive, component] - problem_vectors[negative, component]
                )
                product_before[component] = product_vectors[product, component]
                positive_before[component] = problem_vectors[positive, component]
                negative_before[component] = problem_vectors[negative, component]
            loss_sum += _softplus_negative(margin)
            if margin >= 0.0:
                coefficient = math.exp(-margin) / (1.0 + math.exp(-margin))
            else:
                coefficient = 1.0 / (1.0 + math.exp(margin))
            for component in range(dimension):
                product_vectors[product, component] += learning_rate * (
                    coefficient * (positive_before[component] - negative_before[component])
                    - regularization * product_before[component]
                )
                problem_vectors[positive, component] += learning_rate * (
                    coefficient * product_before[component]
                    - regularization * positive_before[component]
                )
                problem_vectors[negative, component] += learning_rate * (
                    -coefficient * product_before[component]
                    - regularization * negative_before[component]
                )
            steps += 1
        traces.append((epoch + 1, steps, skipped, loss_sum / steps if steps else math.nan))
    return traces


def _graph_layout(history: History, fanout: int, np: Any) -> tuple[Any, ...]:
    products = tuple(sorted(history.product_problems))
    problems = tuple(sorted(history.problem_products))
    product_index = {value: index for index, value in enumerate(products)}
    problem_index = {value: index for index, value in enumerate(problems)}
    p_neighbors = np.full((len(products), fanout), -1, dtype=np.int64)
    d_neighbors = np.full((len(problems), fanout), -1, dtype=np.int64)
    for product, index in product_index.items():
        values = _sample_graph_neighbors(
            history.product_problems[product], f"p:{product}", fanout
        )
        if values:
            p_neighbors[index, : len(values)] = [problem_index[value] for value in values]
    for problem, index in problem_index.items():
        values = _sample_graph_neighbors(
            history.problem_products[problem], f"d:{problem}", fanout
        )
        if values:
            d_neighbors[index, : len(values)] = [product_index[value] for value in values]
    flat: list[int] = []
    offsets = [0]
    positive_pairs: list[tuple[int, int]] = []
    for product, index in product_index.items():
        values = sorted(problem_index[value] for value in history.product_problems[product])
        flat.extend(values)
        offsets.append(len(flat))
        positive_pairs.extend((index, value) for value in values)
    return (
        products,
        problems,
        product_index,
        problem_index,
        p_neighbors,
        d_neighbors,
        np.asarray([pair[0] for pair in positive_pairs], dtype=np.int64),
        np.asarray([pair[1] for pair in positive_pairs], dtype=np.int64),
        np.asarray(flat, dtype=np.int64),
        np.asarray(offsets, dtype=np.int64),
    )

def _reverse_csr(
    problem_count: int,
    positive_values: Any,
    positive_offsets: Any,
    np: Any,
) -> tuple[Any, Any]:
    rows: list[list[int]] = [[] for _ in range(problem_count)]
    for product in range(len(positive_offsets) - 1):
        for problem in positive_values[positive_offsets[product] : positive_offsets[product + 1]]:
            rows[int(problem)].append(product)
    flattened: list[int] = []
    offsets = [0]
    for row in rows:
        flattened.extend(row)
        offsets.append(len(flattened))
    return np.asarray(flattened, dtype=np.int64), np.asarray(offsets, dtype=np.int64)


def _probe_indices(
    history: History,
    product_index: Mapping[str, int],
    problem_index: Mapping[str, int],
    max_triplets: int = 20_000,
) -> tuple[Any, Any, Any, tuple[tuple[str, str, str], ...]]:
    np, _ = _numeric_libraries()
    problems = tuple(problem_index)
    problem_count = len(problems)
    probe: list[tuple[str, str, str]] = []
    if problem_count:
        for product in sorted(history.product_problems):
            positives = history.product_problems[product]
            for positive in sorted(positives):
                start = int.from_bytes(
                    hashlib.sha256(f"q2-fixed-probe|{product}|{positive}".encode()).digest()[:8],
                    "big",
                ) % problem_count
                negative = None
                for offset in range(problem_count):
                    candidate = problems[(start + offset) % problem_count]
                    if candidate not in positives:
                        negative = candidate
                        break
                if negative is not None:
                    probe.append((product, positive, negative))
    if len(probe) > max_triplets:
        count = max_triplets
        probe = [probe[(index * len(probe)) // count] for index in range(count)]
    return (
        np.asarray([product_index[p] for p, _, _ in probe], dtype=np.int64),
        np.asarray([problem_index[d] for _, d, _ in probe], dtype=np.int64),
        np.asarray([problem_index[n] for _, _, n in probe], dtype=np.int64),
        tuple(probe),
    )


def _initial_pair(
    product_count: int,
    problem_count: int,
    dimension: int,
    seed: int,
    np: Any,
) -> tuple[Any, Any]:
    generator = np.random.default_rng(seed)
    values = generator.normal(0.0, 0.05, size=(product_count + problem_count, dimension))
    values = np.ascontiguousarray(values, dtype=np.float64)
    return values[:product_count], values[product_count:]


def _ranker_vectors(values: Any, names: Sequence[str]) -> dict[str, tuple[float, ...]]:
    return {name: tuple(float(value) for value in values[index]) for index, name in enumerate(names)}


def _graph_embeddings(
    product_inputs: Any,
    problem_inputs: Any,
    self_weights: Any,
    neighbor_weights: Any,
    product_neighbors: Any,
    problem_neighbors: Any,
    use_neighbors: bool,
    np: Any,
) -> tuple[Any, Any]:
    product_hidden = np.empty_like(product_inputs)
    problem_hidden = np.empty_like(problem_inputs)
    dimension = product_inputs.shape[1]
    for node in range(product_inputs.shape[0]):
        mean = np.zeros(dimension, dtype=np.float64)
        count = 0
        if use_neighbors:
            for neighbor in product_neighbors[node]:
                if neighbor < 0:
                    break
                for component in range(dimension):
                    mean[component] += problem_inputs[neighbor, component]
                count += 1
            if count:
                mean /= count
        for row in range(dimension):
            value = 0.0
            for column in range(dimension):
                value += self_weights[row, column] * product_inputs[node, column]
                if use_neighbors:
                    value += neighbor_weights[row, column] * mean[column]
            product_hidden[node, row] = math.tanh(value)
    for node in range(problem_inputs.shape[0]):
        mean = np.zeros(dimension, dtype=np.float64)
        count = 0
        if use_neighbors:
            for neighbor in problem_neighbors[node]:
                if neighbor < 0:
                    break
                for component in range(dimension):
                    mean[component] += product_inputs[neighbor, component]
                count += 1
            if count:
                mean /= count
        for row in range(dimension):
            value = 0.0
            for column in range(dimension):
                value += self_weights[row, column] * problem_inputs[node, column]
                if use_neighbors:
                    value += neighbor_weights[row, column] * mean[column]
            problem_hidden[node, row] = math.tanh(value)
    return product_hidden, problem_hidden


@dataclass(frozen=True, slots=True)
class GraphSageRanker:
    """Inference ranker reconstructed from raw identity vectors and transforms."""

    product_vectors: Mapping[str, tuple[float, ...]]
    problem_vectors: Mapping[str, tuple[float, ...]]
    configuration: Mapping[str, int | float | str]

    def score(self, product: str, problem: str) -> float:
        left = self.product_vectors.get(product)
        right = self.problem_vectors.get(problem)
        if left is None or right is None:
            return 0.0
        return math.fsum(a * b for a, b in zip(left, right, strict=True))


def fit_graphsage(
    history: History,
    *,
    dimension: int,
    regularization: float,
    seed: int,
    epochs: int = 30,
    learning_rate: float = 0.02,
    fanout: int = 8,
    aggregation: str = "mean",
    probe_limit: int = 20_000,
    minimum_probe_loss_reduction: float = 0.01,
    on_epoch: Any = None,
) -> tuple[GraphSageRanker, dict[str, Any]]:
    if aggregation not in {"mean", "none"}:
        raise ValueError("aggregation must be 'mean' or 'none'")
    if dimension < 1 or epochs < 1 or fanout < 0 or probe_limit < 1:
        raise ValueError("invalid Q2 GraphSAGE configuration")
    if (
        not math.isfinite(minimum_probe_loss_reduction)
        or not 0.0 <= minimum_probe_loss_reduction <= 1.0
    ):
        raise ValueError("invalid Q2 GraphSAGE probe loss threshold")
    np, _ = _numeric_libraries()
    train_kernel, probe_kernel, _ = _kernels()
    (
        products,
        problems,
        product_index,
        problem_index,
        product_neighbors,
        problem_neighbors,
        positive_product,
        positive_problem,
        flat_positive,
        positive_offsets,
    ) = _graph_layout(history, fanout if aggregation == "mean" else 0, np)
    if aggregation == "none":
        product_neighbors = np.empty((len(products), 0), dtype=np.int64)
        problem_neighbors = np.empty((len(problems), 0), dtype=np.int64)
    product_inputs, problem_inputs = _initial_pair(
        len(products), len(problems), dimension, seed, np
    )
    identity = np.eye(dimension, dtype=np.float64)
    self_weights = identity.copy()
    neighbor_weights = identity * 0.25
    use_neighbors = aggregation == "mean"
    probe_product, probe_positive, probe_negative, named_probe = _probe_indices(
        history, product_index, problem_index, probe_limit
    )
    before_loss = float(
        probe_kernel(
            product_inputs,
            problem_inputs,
            self_weights,
            neighbor_weights,
            product_neighbors,
            problem_neighbors,
            probe_product,
            probe_positive,
            probe_negative,
            use_neighbors,
        )
    )
    raw_before = (
        product_inputs.copy(),
        problem_inputs.copy(),
        self_weights.copy(),
        neighbor_weights.copy(),
    )
    initial_digest = hashlib.sha256()
    for initial_state in (product_inputs, problem_inputs, self_weights, neighbor_weights):
        initial_digest.update(memoryview(initial_state).cast("B"))
    trace = train_kernel(
        product_inputs,
        problem_inputs,
        self_weights,
        neighbor_weights,
        product_neighbors,
        problem_neighbors,
        positive_product,
        positive_problem,
        flat_positive,
        positive_offsets,
        epochs,
        learning_rate,
        regularization,
        seed,
        use_neighbors,
    )
    after_loss = float(
        probe_kernel(
            product_inputs,
            problem_inputs,
            self_weights,
            neighbor_weights,
            product_neighbors,
            problem_neighbors,
            probe_product,
            probe_positive,
            probe_negative,
            use_neighbors,
        )
    )
    product_hidden, problem_hidden = _graph_embeddings(
        product_inputs,
        problem_inputs,
        self_weights,
        neighbor_weights,
        product_neighbors,
        problem_neighbors,
        use_neighbors,
        np,
    )
    configuration: dict[str, int | float | str] = {
        "aggregation": aggregation,
        "dimension": dimension,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "regularization": regularization,
        "fanout": fanout if use_neighbors else 0,
        "seed": seed,
        "initialization": "normal(0,0.05)",
        "objective": "online sequential BPR, exact per-triplet gradients with repeated-neighbor accumulation",
        "active_transform_parameters": (2 if use_neighbors else 1) * dimension * dimension,
        "node_input_scalars": (len(products) + len(problems)) * dimension,
    }
    ranker = GraphSageRanker(
        _ranker_vectors(product_hidden, products),
        _ranker_vectors(problem_hidden, problems),
        configuration,
    )
    changed = any(
        bool(np.any(before != after))
        for before, after in zip(
            raw_before,
            (product_inputs, problem_inputs, self_weights, neighbor_weights),
            strict=True,
        )
    )
    relative_drop = (before_loss - after_loss) / before_loss if before_loss > 0 else 0.0
    diagnostics = {
        "trace": [
            {
                "epoch": int(row[0]),
                "steps": int(row[1]),
                "positive_edges_skipped": int(row[2]),
                "mean_bpr_data_loss": None if math.isnan(row[3]) else float(row[3]),
            }
            for row in trace
        ],
        "probe": [list(row) for row in named_probe],
        "probe_triplets": len(named_probe),
        "probe_loss_before": before_loss,
        "probe_loss_after": after_loss,
        "probe_relative_loss_drop": relative_drop,
        "state_changed": changed,
        "initialization_sha256": initial_digest.hexdigest(),
        "learning_gate_passed": changed and relative_drop >= minimum_probe_loss_reduction,
        "minimum_probe_loss_reduction": minimum_probe_loss_reduction,
        "configuration": configuration,
    }
    if on_epoch is not None:
        for epoch_record in diagnostics["trace"]:
            on_epoch(epoch_record)
    raw = {
        "products": products,
        "problems": problems,
        "product_inputs": product_inputs,
        "problem_inputs": problem_inputs,
        "self_weights": self_weights,
        "neighbor_weights": neighbor_weights,
        "product_neighbors": product_neighbors,
        "problem_neighbors": problem_neighbors,
        "product_embeddings": product_hidden,
        "problem_embeddings": problem_hidden,
        "configuration": configuration,
    }
    return ranker, {**diagnostics, "raw_checkpoint": raw}


def _checkpoint_ranker(raw: Mapping[str, Any], np: Any) -> GraphSageRanker:
    products = tuple(str(value) for value in raw["products"])
    problems = tuple(str(value) for value in raw["problems"])
    configuration = dict(raw["configuration"])
    aggregation = configuration.get("aggregation", "mean")
    if aggregation not in {"mean", "none"}:
        raise ValueError("invalid Q2 GraphSAGE checkpoint aggregation")
    product_embeddings, problem_embeddings = _graph_embeddings(
        np.asarray(raw["product_inputs"], dtype=np.float64),
        np.asarray(raw["problem_inputs"], dtype=np.float64),
        np.asarray(raw["self_weights"], dtype=np.float64),
        np.asarray(raw["neighbor_weights"], dtype=np.float64),
        np.asarray(raw["product_neighbors"], dtype=np.int64),
        np.asarray(raw["problem_neighbors"], dtype=np.int64),
        aggregation == "mean",
        np,
    )
    stored_product = np.asarray(raw["product_embeddings"], dtype=np.float64)
    stored_problem = np.asarray(raw["problem_embeddings"], dtype=np.float64)
    if not np.allclose(product_embeddings, stored_product, rtol=0.0, atol=1e-12):
        raise ValueError("Q2 GraphSAGE product inference checkpoint does not match raw state")
    if not np.allclose(problem_embeddings, stored_problem, rtol=0.0, atol=1e-12):
        raise ValueError("Q2 GraphSAGE problem inference checkpoint does not match raw state")
    return GraphSageRanker(
        _ranker_vectors(product_embeddings, products),
        _ranker_vectors(problem_embeddings, problems),
        configuration,
    )


def save_graphsage_checkpoint(path: Path, raw: Mapping[str, Any]) -> None:
    np, _ = _numeric_libraries()
    path.parent.mkdir(parents=True, exist_ok=True)
    configuration = json.dumps(raw["configuration"], sort_keys=True, separators=(",", ":"))
    with path.open("wb") as output:
        np.savez_compressed(
            output,
            schema=np.asarray("healthgraphbench.q2.graphsage-checkpoint.v1"),
            products=np.asarray(raw["products"], dtype=np.str_),
            problems=np.asarray(raw["problems"], dtype=np.str_),
            product_inputs=raw["product_inputs"],
            problem_inputs=raw["problem_inputs"],
            self_weights=raw["self_weights"],
            neighbor_weights=raw["neighbor_weights"],
            product_neighbors=raw["product_neighbors"],
            problem_neighbors=raw["problem_neighbors"],
            product_embeddings=raw["product_embeddings"],
            problem_embeddings=raw["problem_embeddings"],
            configuration=np.asarray(configuration),
        )


def load_graphsage_checkpoint(path: Path) -> GraphSageRanker:
    np, _ = _numeric_libraries()
    with np.load(path, allow_pickle=False) as archive:
        if str(archive["schema"].item()) != "healthgraphbench.q2.graphsage-checkpoint.v1":
            raise ValueError("Unsupported Q2 GraphSAGE checkpoint schema")
        configuration = json.loads(str(archive["configuration"].item()))
        raw = {
            "products": tuple(str(value) for value in archive["products"].tolist()),
            "problems": tuple(str(value) for value in archive["problems"].tolist()),
            "product_inputs": archive["product_inputs"],
            "problem_inputs": archive["problem_inputs"],
            "self_weights": archive["self_weights"],
            "neighbor_weights": archive["neighbor_weights"],
            "product_neighbors": archive["product_neighbors"],
            "problem_neighbors": archive["problem_neighbors"],
            "product_embeddings": archive["product_embeddings"],
            "problem_embeddings": archive["problem_embeddings"],
            "configuration": configuration,
        }
    return _checkpoint_ranker(raw, np)


def fit_spectral(
    history: History,
    *,
    rank: int,
    power_iterations: int,
    seed: int,
) -> tuple[LatentRanker, dict[str, Any]]:
    if rank < 1 or power_iterations < 1:
        raise ValueError("invalid Q2 spectral configuration")
    np, _ = _numeric_libraries()
    products = tuple(sorted(history.product_problems))
    problems = tuple(sorted(history.problem_products))
    problem_index = {problem: index for index, problem in enumerate(problems)}
    rows = tuple(
        tuple(problem_index[problem] for problem in sorted(history.product_problems[product]))
        for product in products
    )
    edge_values = np.asarray([problem for row in rows for problem in row], dtype=np.int64)
    edge_offsets = np.zeros(len(rows) + 1, dtype=np.int64)
    for index, row in enumerate(rows):
        edge_offsets[index + 1] = edge_offsets[index] + len(row)
    weights = np.asarray(
        [1.0 / math.sqrt(max(1, len(history.problem_products[problem]))) for problem in problems],
        dtype=np.float64,
    )
    generator = np.random.default_rng(seed)
    vectors: list[Any] = []
    trace: list[dict[str, int | float]] = []
    for component in range(min(rank, len(problems))):
        vector = generator.normal(0.0, 1.0, size=len(problems)).astype(np.float64, copy=False)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            break
        vector /= norm
        for iteration in range(power_iterations):
            candidate = np.zeros(len(problems), dtype=np.float64)
            for row in rows:
                projection = math.fsum(float(weights[index] * vector[index]) for index in row)
                for index in row:
                    candidate[index] += weights[index] * projection
            for previous in vectors:
                candidate -= float(np.dot(candidate, previous)) * previous
            norm = float(np.linalg.norm(candidate))
            trace.append(
                {
                    "component": component + 1,
                    "iteration": iteration + 1,
                    "norm_before_normalization": norm,
                }
            )
            if norm <= 1e-12:
                break
            vector = candidate / norm
        if norm <= 1e-12:
            break
        vectors.append(vector.copy())
    basis = np.vstack(vectors) if vectors else np.empty((0, len(problems)), dtype=np.float64)
    projections = np.zeros((len(products), len(vectors)), dtype=np.float64)
    for product_index, row in enumerate(rows):
        for component, vector in enumerate(vectors):
            projections[product_index, component] = math.fsum(
                float(weights[index] * vector[index]) for index in row
            )
    configuration: dict[str, int | float | str] = {
        "rank": rank,
        "power_iterations": power_iterations,
        "seed": seed,
        "seeded_initialization": "normal(0,1), then L2-normalized",
        "operator": "weighted product-problem incidence Gram matrix",
    }
    product_vectors = _ranker_vectors(projections, products)
    problem_vectors = {
        problem: tuple(float(basis[component, index]) for component in range(len(vectors)))
        for index, problem in enumerate(problems)
    }
    ranker = LatentRanker(products, problems, product_vectors, problem_vectors, configuration)
    raw = {
        "products": products,
        "problems": problems,
        "basis": basis,
        "problem_weights": weights,
        "product_projections": projections,
        "edge_values": edge_values,
        "edge_offsets": edge_offsets,
        "configuration": configuration,
    }
    return ranker, {"trace": trace, "configuration": configuration, "raw_checkpoint": raw}


def save_spectral_checkpoint(path: Path, raw: Mapping[str, Any]) -> None:
    np, _ = _numeric_libraries()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        np.savez_compressed(
            output,
            schema=np.asarray("healthgraphbench.q2.spectral-checkpoint.v1"),
            products=np.asarray(raw["products"], dtype=np.str_),
            problems=np.asarray(raw["problems"], dtype=np.str_),
            basis=raw["basis"],
            problem_weights=raw["problem_weights"],
            edge_values=raw["edge_values"],
            edge_offsets=raw["edge_offsets"],
            product_projections=raw["product_projections"],
            configuration=np.asarray(json.dumps(raw["configuration"], sort_keys=True)),
        )


def load_spectral_checkpoint(path: Path) -> LatentRanker:
    np, _ = _numeric_libraries()
    with np.load(path, allow_pickle=False) as archive:
        if str(archive["schema"].item()) != "healthgraphbench.q2.spectral-checkpoint.v1":
            raise ValueError("Unsupported Q2 spectral checkpoint schema")
        products = tuple(str(value) for value in archive["products"].tolist())
        problems = tuple(str(value) for value in archive["problems"].tolist())
        basis = archive["basis"]
        weights = archive["problem_weights"]
        edge_values = archive["edge_values"]
        edge_offsets = archive["edge_offsets"]
        stored_projections = archive["product_projections"]
        configuration = json.loads(str(archive["configuration"].item()))
        projections = np.zeros_like(stored_projections)
        for product in range(len(products)):
            start = int(edge_offsets[product])
            end = int(edge_offsets[product + 1])
            for component in range(basis.shape[0]):
                projections[product, component] = math.fsum(
                    float(weights[index] * basis[component, index])
                    for index in edge_values[start:end]
                )
        if not np.allclose(projections, stored_projections, rtol=0.0, atol=1e-12):
            raise ValueError("Q2 spectral inference checkpoint does not match raw state")
        product_vectors = _ranker_vectors(projections, products)
        problem_vectors = {
            problem: tuple(float(basis[component, index]) for component in range(basis.shape[0]))
            for index, problem in enumerate(problems)
        }

    return LatentRanker(products, problems, product_vectors, problem_vectors, configuration)



def fit_bpr(
    history: History,
    *,
    dimension: int,
    regularization: float,
    seed: int,
    epochs: int = 30,
    learning_rate: float = 0.03,
) -> tuple[LatentRanker, dict[str, Any]]:
    if dimension < 1 or epochs < 1:
        raise ValueError("invalid Q2 BPR configuration")
    np, _ = _numeric_libraries()
    _, _, train_kernel = _kernels()
    (
        products,
        problems,
        _,
        _,
        _,
        _,
        positive_product,
        positive_problem,
        flat_positive,
        positive_offsets,
    ) = _graph_layout(history, 0, np)
    problem_positive_values, problem_positive_offsets = _reverse_csr(
        len(problems), flat_positive, positive_offsets, np
    )
    product_vectors, problem_vectors = _initial_pair(
        len(products), len(problems), dimension, seed, np
    )
    trace = train_kernel(
        product_vectors,
        problem_vectors,
        positive_product,
        positive_problem,
        flat_positive,
        positive_offsets,
        epochs,
        learning_rate,
        regularization,
        seed,
    )
    propagated_products = np.empty_like(product_vectors)
    propagated_problems = np.empty_like(problem_vectors)
    for product in range(len(products)):
        start = int(positive_offsets[product])
        end = int(positive_offsets[product + 1])
        mean = np.zeros(dimension, dtype=np.float64)
        for edge in range(start, end):
            mean += problem_vectors[flat_positive[edge]]
        if end > start:
            mean /= end - start
        propagated_products[product] = 0.5 * product_vectors[product] + 0.5 * mean
    for problem in range(len(problems)):
        start = int(problem_positive_offsets[problem])
        end = int(problem_positive_offsets[problem + 1])
        mean = np.zeros(dimension, dtype=np.float64)
        for edge in range(start, end):
            mean += product_vectors[problem_positive_values[edge]]
        if end > start:
            mean /= end - start
        propagated_problems[problem] = 0.5 * problem_vectors[problem] + 0.5 * mean
    configuration: dict[str, int | float | str] = {
        "dimension": dimension,
        "epochs": epochs,
        "learning_rate": learning_rate,
        "regularization": regularization,
        "seed": seed,
        "initialization": "normal(0,0.05)",
        "objective": "online sequential BPR",
        "neighbor_rule": "all historical bipartite neighbors; fixed across configurations",
        "node_input_scalars": (len(products) + len(problems)) * dimension,
    }
    ranker = LatentRanker(
        products,
        problems,
        _ranker_vectors(propagated_products, products),
        _ranker_vectors(propagated_problems, problems),
        configuration,
    )
    diagnostics = {
        "trace": [
            {
                "epoch": int(row[0]),
                "steps": int(row[1]),
                "positive_edges_skipped": int(row[2]),
                "mean_bpr_data_loss": None if math.isnan(row[3]) else float(row[3]),
            }
            for row in trace
        ],
        "configuration": configuration,
        "raw_checkpoint": {
            "products": products,
            "problems": problems,
            "product_inputs": product_vectors,
            "problem_inputs": problem_vectors,
            "product_positive_values": flat_positive,
            "product_positive_offsets": positive_offsets,
            "problem_positive_values": problem_positive_values,
            "problem_positive_offsets": problem_positive_offsets,
            "product_embeddings": propagated_products,
            "problem_embeddings": propagated_problems,
            "configuration": configuration,
        },
    }
    return ranker, diagnostics


def save_bpr_checkpoint(path: Path, raw: Mapping[str, Any]) -> None:
    np, _ = _numeric_libraries()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        np.savez_compressed(
            output,
            schema=np.asarray("healthgraphbench.q2.bpr-checkpoint.v1"),
            products=np.asarray(raw["products"], dtype=np.str_),
            problems=np.asarray(raw["problems"], dtype=np.str_),
            product_inputs=raw["product_inputs"],
            problem_inputs=raw["problem_inputs"],
            product_positive_values=raw["product_positive_values"],
            product_positive_offsets=raw["product_positive_offsets"],
            problem_positive_values=raw["problem_positive_values"],
            problem_positive_offsets=raw["problem_positive_offsets"],
            product_embeddings=raw["product_embeddings"],
            problem_embeddings=raw["problem_embeddings"],
            configuration=np.asarray(json.dumps(raw["configuration"], sort_keys=True)),
        )


def load_bpr_checkpoint(path: Path) -> LatentRanker:
    np, _ = _numeric_libraries()
    with np.load(path, allow_pickle=False) as archive:
        if str(archive["schema"].item()) != "healthgraphbench.q2.bpr-checkpoint.v1":
            raise ValueError("Unsupported Q2 BPR checkpoint schema")
        products = tuple(str(value) for value in archive["products"].tolist())
        problems = tuple(str(value) for value in archive["problems"].tolist())
        config = json.loads(str(archive["configuration"].item()))
        product_inputs = archive["product_inputs"]
        problem_inputs = archive["problem_inputs"]
        product_values = archive["product_positive_values"]
        product_offsets = archive["product_positive_offsets"]
        problem_values = archive["problem_positive_values"]
        problem_offsets = archive["problem_positive_offsets"]
        stored_product = archive["product_embeddings"]
        stored_problem = archive["problem_embeddings"]
        dimension = product_inputs.shape[1]
        propagated_products = np.empty_like(product_inputs)
        propagated_problems = np.empty_like(problem_inputs)
        for product in range(len(products)):
            start = int(product_offsets[product])
            end = int(product_offsets[product + 1])
            mean = np.zeros(dimension, dtype=np.float64)
            for edge in range(start, end):
                mean += problem_inputs[product_values[edge]]
            if end > start:
                mean /= end - start
            propagated_products[product] = 0.5 * product_inputs[product] + 0.5 * mean
        for problem in range(len(problems)):
            start = int(problem_offsets[problem])
            end = int(problem_offsets[problem + 1])
            mean = np.zeros(dimension, dtype=np.float64)
            for edge in range(start, end):
                mean += product_inputs[problem_values[edge]]
            if end > start:
                mean /= end - start
            propagated_problems[problem] = 0.5 * problem_inputs[problem] + 0.5 * mean
        if not np.allclose(propagated_products, stored_product, rtol=0.0, atol=1e-12):
            raise ValueError("Q2 BPR product inference checkpoint does not match raw state")
        if not np.allclose(propagated_problems, stored_problem, rtol=0.0, atol=1e-12):
            raise ValueError("Q2 BPR problem inference checkpoint does not match raw state")
        product_vectors = _ranker_vectors(propagated_products, products)
        problem_vectors = _ranker_vectors(propagated_problems, problems)
    return LatentRanker(products, problems, product_vectors, problem_vectors, config)


def _python_graphsage_loss(
    product_inputs: Any,
    problem_inputs: Any,
    self_weights: Any,
    neighbor_weights: Any,
    product_neighbors: Any,
    problem_neighbors: Any,
    product: int,
    positive: int,
    negative: int,
    use_neighbors: bool,
) -> float:
    np, _ = _numeric_libraries()
    dimension = product_inputs.shape[1]
    hidden: list[Any] = []
    for role, node in enumerate((product, positive, negative)):
        own = product_inputs[node] if role == 0 else problem_inputs[node]
        adjacency = product_neighbors[node] if role == 0 else problem_neighbors[node]
        neighbor_inputs = problem_inputs if role == 0 else product_inputs
        mean = np.zeros(dimension, dtype=np.float64)
        count = 0
        if use_neighbors:
            for neighbor in adjacency:
                if neighbor < 0:
                    break
                mean += neighbor_inputs[neighbor]
                count += 1
            if count:
                mean /= count
        value = self_weights @ own
        if use_neighbors:
            value = value + neighbor_weights @ mean
        hidden.append(np.tanh(value))
    margin = float(np.dot(hidden[0], hidden[1] - hidden[2]))
    return _softplus_negative(margin)


def graphsage_gradient_preflight() -> dict[str, Any]:
    """Finite-difference-check a single exact BPR gradient for mean and none."""
    np, _ = _numeric_libraries()
    train_kernel, _, _ = _kernels()
    products = np.asarray([[0.12, -0.08], [-0.03, 0.09]], dtype=np.float64)
    problems = np.asarray([[0.07, 0.02], [-0.11, 0.05], [0.03, -0.06]], dtype=np.float64)
    self_weights = np.asarray([[0.9, 0.04], [-0.02, 1.1]], dtype=np.float64)
    neighbor_weights = np.asarray([[0.22, 0.01], [-0.03, 0.19]], dtype=np.float64)
    product_neighbors = np.asarray([[0], [1]], dtype=np.int64)
    problem_neighbors = np.asarray([[0], [1], [1]], dtype=np.int64)
    positives_product = np.asarray([0, 1], dtype=np.int64)
    positives_problem = np.asarray([0, 1], dtype=np.int64)
    flat_positive = np.asarray([0, 1], dtype=np.int64)
    offsets = np.asarray([0, 1, 2], dtype=np.int64)
    reports: dict[str, Any] = {}
    for aggregation in ("mean", "none"):
        use_neighbors = aggregation == "mean"
        p_neighbors = product_neighbors if use_neighbors else np.empty((2, 0), dtype=np.int64)
        d_neighbors = problem_neighbors if use_neighbors else np.empty((3, 0), dtype=np.int64)
        p = products.copy()
        d = problems.copy()
        w_self = self_weights.copy()
        w_neighbor = neighbor_weights.copy()
        seed = 103
        negative = _triplet_start(seed, 0, 0, 0, 3)
        for offset in range(3):
            candidate = (negative + offset) % 3
            if candidate not in {0}:
                negative = candidate
                break
        rate = 1e-6
        train_kernel(
            p,
            d,
            w_self,
            w_neighbor,
            p_neighbors,
            d_neighbors,
            positives_product[:1],
            positives_problem[:1],
            flat_positive,
            offsets,
            1,
            rate,
            0.0,
            seed,
            use_neighbors,
        )
        numerical_epsilon = 1e-6
        plus = products.copy()
        minus = products.copy()
        plus[0, 0] += numerical_epsilon
        minus[0, 0] -= numerical_epsilon
        plus_loss = _python_graphsage_loss(
            plus, problems, self_weights, neighbor_weights, p_neighbors, d_neighbors,
            0, 0, negative, use_neighbors
        )
        minus_loss = _python_graphsage_loss(
            minus, problems, self_weights, neighbor_weights, p_neighbors, d_neighbors,
            0, 0, negative, use_neighbors
        )
        finite_difference = (plus_loss - minus_loss) / (2 * numerical_epsilon)
        analytical_gradient = (products[0, 0] - p[0, 0]) / rate
        reports[aggregation] = {
            "analytical_gradient": float(analytical_gradient),
            "finite_difference_gradient": float(finite_difference),
            "absolute_error": float(abs(analytical_gradient - finite_difference)),
        }
    return reports
