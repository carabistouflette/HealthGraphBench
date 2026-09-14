"""Leakage-safe baselines and learned rankers for the MAUDE edge gate."""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from .data import QUARTER_INDEX, Edge, QuarterSnapshot

FEATURE_NAMES: tuple[str, ...] = (
    "product_log_prior_reports",
    "problem_log_prior_reports",
    "problem_log_product_prevalence",
    "neighbor_log_product_count",
    "recent_problem_log_product_count",
    "recent_problem_prevalence_fraction",
    "product_log_manufacturer_count",
    "manufacturer_log_product_activity",
    "product_age_quarters",
    "problem_age_quarters",
    "parent_log_product_prevalence",
    "product_recent_report_fraction",
)
SUPPORT_BANDS: tuple[str, ...] = ("1-9", "10-49", "50-199", "200+")


@dataclass(slots=True)
class History:
    """Mutable graph state containing only quarters before the current cutoff."""

    product_reports: Counter[str]
    problem_reports: Counter[str]
    product_problems: dict[str, set[str]]
    problem_products: dict[str, set[str]]
    product_manufacturers: dict[str, set[str]]
    manufacturer_products: dict[str, set[str]]
    parent_products: dict[str, set[str]]
    quarter_product_reports: dict[str, Counter[str]]
    quarter_problem_products: dict[str, dict[str, set[str]]]
    first_product_index: dict[str, int]
    first_problem_index: dict[str, int]

    @classmethod
    def empty(cls) -> History:
        return cls(
            product_reports=Counter(),
            problem_reports=Counter(),
            product_problems=defaultdict(set),
            problem_products=defaultdict(set),
            product_manufacturers=defaultdict(set),
            manufacturer_products=defaultdict(set),
            parent_products=defaultdict(set),
            quarter_product_reports={},
            quarter_problem_products={},
            first_product_index={},
            first_problem_index={},
        )

    def add(
        self,
        snapshot: QuarterSnapshot,
        problem_parent_map: Mapping[str, str],
    ) -> None:
        quarter_index = QUARTER_INDEX[snapshot.quarter]
        self.quarter_product_reports[snapshot.quarter] = Counter(snapshot.product_reports)
        quarter_problem_products: dict[str, set[str]] = defaultdict(set)
        for product, report_count in snapshot.product_reports.items():
            self.product_reports[product] += report_count
            self.first_product_index.setdefault(product, quarter_index)
        for product, manufacturers in snapshot.product_manufacturers.items():
            self.product_manufacturers[product].update(manufacturers)
            for manufacturer in manufacturers:
                self.manufacturer_products[manufacturer].add(product)
        for product, problem in snapshot.edges:
            self.product_problems[product].add(problem)
            self.problem_products[problem].add(product)
            self.problem_reports[problem] += snapshot.edge_report_counts[(product, problem)]
            self.first_problem_index.setdefault(problem, quarter_index)
            quarter_problem_products[problem].add(product)
            parent = problem_parent_map.get(problem)
            if parent is not None:
                self.parent_products[parent].add(product)
        self.quarter_problem_products[snapshot.quarter] = dict(quarter_problem_products)

    def candidate_problems(self, product: str) -> list[str]:
        observed = self.product_problems.get(product, set())
        return sorted(set(self.problem_products).difference(observed))


@dataclass(frozen=True, slots=True)
class FeatureContext:
    history: History
    quarter: str
    problem_parent_map: Mapping[str, str]
    recent_window: int = 4
    _neighbor_cache: dict[str, Counter[str]] = field(default_factory=dict, compare=False)
    _recent_problem_cache: dict[str, int] = field(default_factory=dict, compare=False)
    _recent_product_cache: dict[str, int] = field(default_factory=dict, compare=False)
    _manufacturer_cache: dict[str, int] = field(default_factory=dict, compare=False)
    _feature_cache: dict[tuple[str, str], tuple[float, ...]] = field(
        default_factory=dict, compare=False
    )

    def neighbor_scores(self, product: str) -> Counter[str]:
        cached = self._neighbor_cache.get(product)
        if cached is not None:
            return cached
        own_problems = self.history.product_problems.get(product, set())
        neighbors: set[str] = set()
        for problem in own_problems:
            neighbors.update(self.history.problem_products.get(problem, set()))
        neighbors.discard(product)
        scores = Counter(
            {
                problem: len(neighbors.intersection(products))
                for problem, products in self.history.problem_products.items()
                if problem not in own_problems and neighbors.intersection(products)
            }
        )
        self._neighbor_cache[product] = scores
        return scores

    def _recent_problem_products(self, problem: str) -> int:
        cached = self._recent_problem_cache.get(problem)
        if cached is not None:
            return cached
        current = QUARTER_INDEX[self.quarter]
        products: set[str] = set()
        for quarter, values in self.history.quarter_problem_products.items():
            if current - QUARTER_INDEX[quarter] <= self.recent_window:
                products.update(values.get(problem, set()))
        result = len(products)
        self._recent_problem_cache[problem] = result
        return result

    def _recent_product_reports(self, product: str) -> int:
        cached = self._recent_product_cache.get(product)
        if cached is not None:
            return cached
        current = QUARTER_INDEX[self.quarter]
        total = 0
        for quarter, values in self.history.quarter_product_reports.items():
            if current - QUARTER_INDEX[quarter] <= self.recent_window:
                total += values.get(product, 0)
        self._recent_product_cache[product] = total
        return total

    def _manufacturer_activity(self, product: str) -> int:
        cached = self._manufacturer_cache.get(product)
        if cached is not None:
            return cached
        result = sum(
            len(self.history.manufacturer_products[manufacturer])
            for manufacturer in self.history.product_manufacturers.get(product, set())
        )
        self._manufacturer_cache[product] = result
        return result

    def features_for(
        self,
        product: str,
        problem: str,
        neighbor_scores: Counter[str] | None = None,
    ) -> tuple[float, ...]:
        cached = self._feature_cache.get((product, problem))
        if cached is not None:
            return cached
        product_reports = self.history.product_reports.get(product, 0)
        problem_reports = self.history.problem_reports.get(problem, 0)
        problem_prevalence = len(self.history.problem_products.get(problem, set()))
        if neighbor_scores is None:
            neighbor_scores = self.neighbor_scores(product)
        neighbor_count = neighbor_scores.get(problem, 0)
        recent_problem_products = self._recent_problem_products(problem)
        recent_fraction = recent_problem_products / max(1, problem_prevalence)
        product_recent_reports = self._recent_product_reports(product)
        product_recent_fraction = product_recent_reports / max(1, product_reports)
        quarter_index = QUARTER_INDEX[self.quarter]
        product_age = quarter_index - self.history.first_product_index.get(product, quarter_index)
        problem_age = quarter_index - self.history.first_problem_index.get(problem, quarter_index)
        parent = self.problem_parent_map.get(problem)
        parent_prevalence = len(self.history.parent_products.get(parent, set())) if parent else 0
        values = (
            math.log1p(product_reports),
            math.log1p(problem_reports),
            math.log1p(problem_prevalence),
            math.log1p(neighbor_count),
            math.log1p(recent_problem_products),
            recent_fraction,
            math.log1p(len(self.history.product_manufacturers.get(product, set()))),
            math.log1p(self._manufacturer_activity(product)),
            float(product_age),
            float(problem_age),
            math.log1p(parent_prevalence),
            product_recent_fraction,
        )
        self._feature_cache[(product, problem)] = values
        return values

    def row_features(
        self,
        product: str,
        problems: Iterable[str],
    ) -> dict[str, tuple[float, ...]]:
        scores = self.neighbor_scores(product)
        return {problem: self.features_for(product, problem, scores) for problem in problems}


@dataclass(frozen=True, slots=True)
class TrainingRow:
    features: tuple[float, ...]
    label: int


@dataclass(frozen=True, slots=True)
class LogisticRanker:
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    intercept: float

    def score(self, features: Sequence[float]) -> float:
        return self.intercept + sum(
            weight * ((value - mean) / scale)
            for value, mean, scale, weight in zip(
                features, self.means, self.scales, self.weights, strict=True
            )
        )


@dataclass(frozen=True, slots=True)
class Stump:
    feature: int
    threshold: float
    left_value: float
    right_value: float


@dataclass(frozen=True, slots=True)
class BoostedStumpRanker:
    base_score: float
    stumps: tuple[Stump, ...]
    learning_rate: float

    def score(self, features: Sequence[float]) -> float:
        score = self.base_score
        for stump in self.stumps:
            score += self.learning_rate * (
                stump.left_value
                if features[stump.feature] <= stump.threshold
                else stump.right_value
            )
        return score


@dataclass(frozen=True, slots=True)
class SpectralRanker:
    problem_order: tuple[str, ...]
    problem_index: Mapping[str, int]
    vectors: tuple[tuple[float, ...], ...]
    problem_weights: tuple[float, ...]
    product_problem_order: Mapping[str, tuple[str, ...]]
    product_projections: Mapping[str, tuple[float, ...]]

    def score(self, product: str, problem: str) -> float:
        projections = self.product_projections.get(product, ())
        if not projections or not self.vectors:
            return 0.0
        target = self.problem_index.get(problem)
        if target is None:
            return 0.0
        return sum(
            projection * vector[target]
            for projection, vector in zip(projections, self.vectors, strict=True)
        )


@dataclass(frozen=True, slots=True)
class GraphRanker:
    product_embeddings: Mapping[str, tuple[float, ...]]
    problem_embeddings: Mapping[str, tuple[float, ...]]
    propagated_product_embeddings: Mapping[str, tuple[float, ...]]
    propagated_problem_embeddings: Mapping[str, tuple[float, ...]]

    def score(self, product: str, problem: str) -> float:
        left = self.propagated_product_embeddings.get(product)
        right = self.propagated_problem_embeddings.get(problem)
        if left is None or right is None:
            return 0.0
        return sum(a * b for a, b in zip(left, right, strict=True))

GRAPHSAGE_DIMENSION = 8
GRAPHSAGE_EPOCHS = 3
GRAPHSAGE_NEIGHBOR_SAMPLE = 8
GRAPHSAGE_LEARNING_RATE = 0.02
GRAPHSAGE_REGULARIZATION = 0.0005


@dataclass(frozen=True, slots=True)
class GraphSageRanker:
    """One-hop bipartite GraphSAGE link predictor trained with BPR."""

    product_embeddings: Mapping[str, tuple[float, ...]]
    problem_embeddings: Mapping[str, tuple[float, ...]]
    configuration: Mapping[str, int | float | str]

    def score(self, product: str, problem: str) -> float:
        left = self.product_embeddings.get(product)
        right = self.problem_embeddings.get(problem)
        if left is None or right is None:
            return 0.0
        return _dot(left, right)


def _sample_graph_neighbors(
    values: Iterable[str],
    key: str,
    fanout: int,
) -> tuple[str, ...]:
    ordered = tuple(sorted(values))
    if len(ordered) <= fanout:
        return ordered
    start = _stable_integer("graphsage-neighbors", key) % len(ordered)
    return tuple(ordered[(start + offset) % len(ordered)] for offset in range(fanout))


def _graph_message(
    own: Sequence[float],
    neighbors: Sequence[Sequence[float]],
    self_weights: Sequence[Sequence[float]],
    neighbor_weights: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    dimension = len(own)
    if neighbors:
        mean = tuple(
            sum(values[index] for values in neighbors) / len(neighbors)
            for index in range(dimension)
        )
    else:
        mean = (0.0,) * dimension
    hidden = tuple(
        math.tanh(
            sum(self_weights[row][column] * own[column] for column in range(dimension))
            + sum(
                neighbor_weights[row][column] * mean[column]
                for column in range(dimension)
            )
        )
        for row in range(dimension)
    )
    return hidden, mean


def _graph_message_gradients(
    hidden_gradient: Sequence[float],
    hidden: Sequence[float],
    own: Sequence[float],
    mean: Sequence[float],
    self_weights: Sequence[Sequence[float]],
    neighbor_weights: Sequence[Sequence[float]],
    neighbor_count: int,
) -> tuple[list[float], list[float], list[list[float]], list[list[float]]]:
    dimension = len(own)
    pre_gradient = [
        hidden_gradient[index] * (1.0 - hidden[index] * hidden[index])
        for index in range(dimension)
    ]
    own_gradient = [
        sum(self_weights[row][column] * pre_gradient[row] for row in range(dimension))
        for column in range(dimension)
    ]
    neighbor_gradient = [
        sum(neighbor_weights[row][column] * pre_gradient[row] for row in range(dimension))
        / max(1, neighbor_count)
        for column in range(dimension)
    ]
    self_gradient = [
        [pre_gradient[row] * own[column] for column in range(dimension)]
        for row in range(dimension)
    ]
    neighbor_weight_gradient = [
        [pre_gradient[row] * mean[column] for column in range(dimension)]
        for row in range(dimension)
    ]
    return own_gradient, neighbor_gradient, self_gradient, neighbor_weight_gradient


def _add_vector_gradient(
    destination: dict[str, list[float]],
    key: str,
    values: Sequence[float],
) -> None:
    current = destination.setdefault(key, [0.0] * len(values))
    for index, value in enumerate(values):
        current[index] += value


def _apply_vector_gradients(
    values: dict[str, list[float]],
    gradients: Mapping[str, Sequence[float]],
    learning_rate: float,
    regularization: float,
) -> None:
    for key, gradient in gradients.items():
        vector = values[key]
        for index, value in enumerate(gradient):
            vector[index] += learning_rate * (value - regularization * vector[index])


def _apply_matrix_gradient(
    matrix: list[list[float]],
    gradient: Sequence[Sequence[float]],
    learning_rate: float,
    regularization: float,
) -> None:
    for row in range(len(matrix)):
        for column in range(len(matrix[row])):
            matrix[row][column] += learning_rate * (
                gradient[row][column] - regularization * matrix[row][column]
            )


def fit_graphsage(
    history: History,
    dimension: int = GRAPHSAGE_DIMENSION,
    epochs: int = GRAPHSAGE_EPOCHS,
    neighbor_sample: int = GRAPHSAGE_NEIGHBOR_SAMPLE,
    learning_rate: float = GRAPHSAGE_LEARNING_RATE,
    regularization: float = GRAPHSAGE_REGULARIZATION,
) -> GraphSageRanker:
    """Fit a one-layer GraphSAGE link predictor on the observed graph.

    Node inputs are trainable identity embeddings. Each score uses a shared
    self transform and a shared mean-neighbor transform, with deterministic
    fixed-fanout sampling. BPR negatives are sampled only from historically
    known problem nodes that are absent for the target product.
    """

    products = tuple(sorted(history.product_problems))
    problems = tuple(sorted(history.problem_products))
    if not products or not problems:
        return GraphSageRanker({}, {}, {})
    product_neighbors = {
        product: _sample_graph_neighbors(history.product_problems[product], f"p:{product}", neighbor_sample)
        for product in products
    }
    problem_neighbors = {
        problem: _sample_graph_neighbors(history.problem_products[problem], f"d:{problem}", neighbor_sample)
        for problem in problems
    }
    product_inputs = {
        product: _initial_embedding(index, dimension, 11) for index, product in enumerate(products)
    }
    problem_inputs = {
        problem: _initial_embedding(index, dimension, 17) for index, problem in enumerate(problems)
    }
    self_weights = [
        [1.0 if row == column else 0.0 for column in range(dimension)]
        for row in range(dimension)
    ]
    neighbor_weights = [
        [0.25 if row == column else 0.0 for column in range(dimension)]
        for row in range(dimension)
    ]
    positive_by_product = {
        product: tuple(sorted(history.product_problems[product])) for product in products
    }
    problem_count = len(problems)
    for epoch in range(epochs):
        for product in products:
            positives = positive_by_product[product]
            positive_set = set(positives)
            for problem in positives:
                start = _stable_integer("graphsage-negative", str(epoch), product, problem) % problem_count
                negative = None
                for offset in range(problem_count):
                    candidate = problems[(start + offset) % problem_count]
                    if candidate not in positive_set:
                        negative = candidate
                        break
                if negative is None:
                    continue
                product_hidden, product_mean = _graph_message(
                    product_inputs[product],
                    [problem_inputs[item] for item in product_neighbors[product]],
                    self_weights,
                    neighbor_weights,
                )
                positive_hidden, positive_mean = _graph_message(
                    problem_inputs[problem],
                    [product_inputs[item] for item in problem_neighbors[problem]],
                    self_weights,
                    neighbor_weights,
                )
                negative_hidden, negative_mean = _graph_message(
                    problem_inputs[negative],
                    [product_inputs[item] for item in problem_neighbors[negative]],
                    self_weights,
                    neighbor_weights,
                )
                margin = _dot(product_hidden, positive_hidden) - _dot(product_hidden, negative_hidden)
                coefficient = 1.0 / (1.0 + math.exp(min(60.0, max(-60.0, margin))))
                product_gradient, product_neighbor_gradient, product_self_gradient, product_neighbor_weight_gradient = _graph_message_gradients(
                    [coefficient * (positive_hidden[index] - negative_hidden[index]) for index in range(dimension)],
                    product_hidden,
                    product_inputs[product],
                    product_mean,
                    self_weights,
                    neighbor_weights,
                    len(product_neighbors[product]),
                )
                positive_gradient, positive_neighbor_gradient, positive_self_gradient, positive_neighbor_weight_gradient = _graph_message_gradients(
                    [coefficient * product_hidden[index] for index in range(dimension)],
                    positive_hidden,
                    problem_inputs[problem],
                    positive_mean,
                    self_weights,
                    neighbor_weights,
                    len(problem_neighbors[problem]),
                )
                negative_gradient, negative_neighbor_gradient, negative_self_gradient, negative_neighbor_weight_gradient = _graph_message_gradients(
                    [-coefficient * product_hidden[index] for index in range(dimension)],
                    negative_hidden,
                    problem_inputs[negative],
                    negative_mean,
                    self_weights,
                    neighbor_weights,
                    len(problem_neighbors[negative]),
                )
                product_input_gradients: dict[str, list[float]] = {}
                problem_input_gradients: dict[str, list[float]] = {}
                _add_vector_gradient(product_input_gradients, product, product_gradient)
                for item in product_neighbors[product]:
                    _add_vector_gradient(problem_input_gradients, item, product_neighbor_gradient)
                _add_vector_gradient(problem_input_gradients, problem, positive_gradient)
                for item in problem_neighbors[problem]:
                    _add_vector_gradient(product_input_gradients, item, positive_neighbor_gradient)
                _add_vector_gradient(problem_input_gradients, negative, negative_gradient)
                for item in problem_neighbors[negative]:
                    _add_vector_gradient(product_input_gradients, item, negative_neighbor_gradient)
                self_gradient = [
                    [
                        product_self_gradient[row][column]
                        + positive_self_gradient[row][column]
                        + negative_self_gradient[row][column]
                        for column in range(dimension)
                    ]
                    for row in range(dimension)
                ]
                neighbor_gradient = [
                    [
                        product_neighbor_weight_gradient[row][column]
                        + positive_neighbor_weight_gradient[row][column]
                        + negative_neighbor_weight_gradient[row][column]
                        for column in range(dimension)
                    ]
                    for row in range(dimension)
                ]
                _apply_matrix_gradient(
                    self_weights, self_gradient, learning_rate, regularization
                )
                _apply_matrix_gradient(
                    neighbor_weights, neighbor_gradient, learning_rate, regularization
                )
                _apply_vector_gradients(
                    product_inputs, product_input_gradients, learning_rate, regularization
                )
                _apply_vector_gradients(
                    problem_inputs, problem_input_gradients, learning_rate, regularization
                )
    product_hidden = {
        product: _graph_message(
            product_inputs[product],
            [problem_inputs[item] for item in product_neighbors[product]],
            self_weights,
            neighbor_weights,
        )[0]
        for product in products
    }
    problem_hidden = {
        problem: _graph_message(
            problem_inputs[problem],
            [product_inputs[item] for item in problem_neighbors[problem]],
            self_weights,
            neighbor_weights,
        )[0]
        for problem in problems
    }
    return GraphSageRanker(
        product_hidden,
        problem_hidden,
        {
            "dimension": dimension,
            "epochs": epochs,
            "neighbor_sample": neighbor_sample,
            "learning_rate": learning_rate,
            "regularization": regularization,
            "objective": "bpr",
            "activation": "tanh",
        },
    )


def _sigmoid(value: float) -> float:
    if value >= 0:
        exponent = math.exp(-value) if value < 700 else 0.0
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(value) if value > -700 else 0.0
    return exponent / (1.0 + exponent)


def fit_logistic(
    rows: Sequence[TrainingRow],
    epochs: int = 40,
    learning_rate: float = 0.15,
    l2: float = 0.01,
) -> LogisticRanker:
    if not rows:
        raise ValueError("Cannot fit logistic ranker without training rows")
    width = len(rows[0].features)
    means = tuple(sum(row.features[index] for row in rows) / len(rows) for index in range(width))
    scales = tuple(
        max(
            math.sqrt(sum((row.features[index] - means[index]) ** 2 for row in rows) / len(rows)),
            1e-9,
        )
        for index in range(width)
    )
    normalized = [
        tuple((value - means[index]) / scales[index] for index, value in enumerate(row.features))
        for row in rows
    ]
    weights = [0.0] * width
    intercept = 0.0
    size = float(len(rows))
    for _ in range(epochs):
        gradient = [0.0] * width
        intercept_gradient = 0.0
        for row, values in zip(rows, normalized, strict=True):
            error = (
                _sigmoid(
                    intercept
                    + sum(weight * value for weight, value in zip(weights, values, strict=True))
                )
                - row.label
            )
            intercept_gradient += error
            for index, value in enumerate(values):
                gradient[index] += error * value
        intercept -= learning_rate * intercept_gradient / size
        for index in range(width):
            gradient[index] = gradient[index] / size + l2 * weights[index]
            weights[index] -= learning_rate * gradient[index]
    return LogisticRanker(means, scales, tuple(weights), intercept)


def _quantile_thresholds(values: Sequence[float], count: int = 12) -> tuple[float, ...]:
    unique = sorted(set(values))
    if len(unique) <= 1:
        return ()
    if len(unique) <= count + 1:
        return tuple(unique[:-1])
    thresholds: list[float] = []
    for index in range(1, count + 1):
        position = int(index * (len(unique) - 1) / (count + 1))
        threshold = unique[position]
        if threshold not in thresholds:
            thresholds.append(threshold)
    return tuple(thresholds)


def fit_boosted_stumps(
    rows: Sequence[TrainingRow],
    rounds: int = 12,
    learning_rate: float = 0.08,
) -> BoostedStumpRanker:
    if not rows:
        raise ValueError("Cannot fit boosted stumps without training rows")
    width = len(rows[0].features)
    positive_rate = sum(row.label for row in rows) / len(rows)
    base_score = math.log(max(positive_rate, 1e-6) / max(1.0 - positive_rate, 1e-6))
    scores = [base_score] * len(rows)
    feature_orders = [
        sorted(range(len(rows)), key=lambda row_index: rows[row_index].features[feature])
        for feature in range(width)
    ]
    split_count = 8
    stumps: list[Stump] = []
    for _ in range(rounds):
        residuals = [row.label - _sigmoid(score) for row, score in zip(rows, scores, strict=True)]
        total_sum = sum(residuals)
        total_squared = sum(value * value for value in residuals)
        best: tuple[float, Stump] | None = None
        for feature, order in enumerate(feature_orders):
            target_positions = {
                int(split * (len(order) - 1) / (split_count + 1))
                for split in range(1, split_count + 1)
            }
            left_count = 0
            left_sum = 0.0
            left_squared = 0.0
            for position, row_index in enumerate(order):
                residual = residuals[row_index]
                left_count += 1
                left_sum += residual
                left_squared += residual * residual
                if position not in target_positions or position >= len(order) - 1:
                    continue
                value = rows[row_index].features[feature]
                next_value = rows[order[position + 1]].features[feature]
                if value == next_value:
                    continue
                right_count = len(order) - left_count
                right_sum = total_sum - left_sum
                right_squared = total_squared - left_squared
                reduction = (
                    left_squared
                    - left_sum * left_sum / left_count
                    + right_squared
                    - right_sum * right_sum / right_count
                )
                stump = Stump(
                    feature,
                    value,
                    left_sum / left_count,
                    right_sum / right_count,
                )
                if best is None or reduction < best[0]:
                    best = (reduction, stump)
        if best is None:
            break
        stump = best[1]
        stumps.append(stump)
        for index, row in enumerate(rows):
            scores[index] += learning_rate * (
                stump.left_value
                if row.features[stump.feature] <= stump.threshold
                else stump.right_value
            )
    return BoostedStumpRanker(base_score, tuple(stumps), learning_rate)


def _matrix_vector_product(
    vector: Sequence[float],
    products: Sequence[tuple[int, ...]],
    problem_weights: Sequence[float],
) -> list[float]:
    row_projections = [
        sum(problem_weights[index] * vector[index] for index in row) for row in products
    ]
    result = [0.0] * len(vector)
    for row, projection in zip(products, row_projections, strict=True):
        for index in row:
            result[index] += problem_weights[index] * projection
    return result


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 1e-12:
        return [0.0] * len(vector)
    return [value / norm for value in vector]


def fit_spectral(
    history: History,
    rank: int = 8,
    iterations: int = 18,
) -> SpectralRanker:
    problem_order = tuple(sorted(history.problem_products))
    problem_index = {problem: index for index, problem in enumerate(problem_order)}
    product_rows = tuple(
        tuple(problem_index[problem] for problem in sorted(problems))
        for product, problems in sorted(history.product_problems.items())
        if problems
    )
    product_problem_order = {
        product: tuple(sorted(problems))
        for product, problems in history.product_problems.items()
        if problems
    }
    problem_weights = tuple(
        1.0 / math.sqrt(max(1, len(history.problem_products[problem]))) for problem in problem_order
    )
    vectors: list[tuple[float, ...]] = []
    for component in range(min(rank, len(problem_order))):
        vector = [
            math.sin((index + 1) * (component + 1) * 0.731) + 0.1 / (index + component + 1)
            for index in range(len(problem_order))
        ]
        vector = _normalize(vector)
        for _ in range(iterations):
            candidate = _matrix_vector_product(vector, product_rows, problem_weights)
            for previous in vectors:
                projection = sum(
                    left * right for left, right in zip(candidate, previous, strict=True)
                )
                for index in range(len(candidate)):
                    candidate[index] -= projection * previous[index]
            vector = _normalize(candidate)
        if not any(abs(value) > 1e-9 for value in vector):
            break
        vectors.append(tuple(vector))
    product_projections = {
        product: tuple(
            sum(
                problem_weights[problem_index[item]] * vector[problem_index[item]]
                for item in product_problems
            )
            for vector in vectors
        )
        for product, product_problems in product_problem_order.items()
    }
    return SpectralRanker(
        problem_order,
        problem_index,
        tuple(vectors),
        problem_weights,
        product_problem_order,
        product_projections,
    )


def _stable_integer(*parts: str) -> int:
    payload = "|".join(parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _initial_embedding(index: int, dimension: int, salt: int) -> list[float]:
    return [
        0.05 * math.sin((index + 1) * (component + salt + 1) * 0.173)
        for component in range(dimension)
    ]


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def fit_graph(
    history: History,
    dimension: int = 8,
    epochs: int = 4,
    learning_rate: float = 0.03,
    regularization: float = 0.001,
) -> GraphRanker:
    products = tuple(sorted(history.product_problems))
    problems = tuple(sorted(history.problem_products))
    if not products or not problems:
        return GraphRanker({}, {}, {}, {})
    product_embeddings = {
        product: _initial_embedding(index, dimension, 1) for index, product in enumerate(products)
    }
    problem_embeddings = {
        problem: _initial_embedding(index, dimension, 7) for index, problem in enumerate(problems)
    }
    positive_by_product = {
        product: tuple(sorted(history.product_problems[product])) for product in products
    }
    problem_count = len(problems)
    for epoch in range(epochs):
        for product in products:
            positives = positive_by_product[product]
            for problem in positives:
                negative_index = _stable_integer(str(epoch), product, problem) % problem_count
                for _ in range(problem_count):
                    candidate = problems[negative_index]
                    if candidate not in history.product_problems[product]:
                        break
                    negative_index = (negative_index + 1) % problem_count
                else:
                    continue
                left = product_embeddings[product]
                positive = problem_embeddings[problem]
                negative = problem_embeddings[candidate]
                margin = _dot(left, positive) - _dot(left, negative)
                gradient = 1.0 / (1.0 + math.exp(min(60.0, max(-60.0, margin))))
                left_before = tuple(left)
                positive_before = tuple(positive)
                negative_before = tuple(negative)
                for component in range(dimension):
                    left[component] += learning_rate * (
                        gradient * (positive_before[component] - negative_before[component])
                        - regularization * left_before[component]
                    )
                    positive[component] += learning_rate * (
                        gradient * left_before[component]
                        - regularization * positive_before[component]
                    )
                    negative[component] += learning_rate * (
                        -gradient * left_before[component]
                        - regularization * negative_before[component]
                    )

    propagated_products: dict[str, tuple[float, ...]] = {}
    propagated_problems: dict[str, tuple[float, ...]] = {}
    for product in products:
        neighbors = positive_by_product[product]
        mean = [
            sum(problem_embeddings[problem][component] for problem in neighbors) / len(neighbors)
            for component in range(dimension)
        ]
        propagated_products[product] = tuple(
            0.5 * product_embeddings[product][component] + 0.5 * mean[component]
            for component in range(dimension)
        )
    for problem in problems:
        neighbors = tuple(sorted(history.problem_products[problem]))
        mean = [
            sum(product_embeddings[product][component] for product in neighbors) / len(neighbors)
            for component in range(dimension)
        ]
        propagated_problems[problem] = tuple(
            0.5 * problem_embeddings[problem][component] + 0.5 * mean[component]
            for component in range(dimension)
        )
    return GraphRanker(
        {product: tuple(values) for product, values in product_embeddings.items()},
        {problem: tuple(values) for problem, values in problem_embeddings.items()},
        propagated_products,
        propagated_problems,
    )


def sample_training_rows(
    quarter: str,
    eligible_edges: Collection[Edge],
    context: FeatureContext,
    negative_ratio: int = 5,
) -> list[TrainingRow]:
    by_product: dict[str, set[str]] = defaultdict(set)
    for product, problem in eligible_edges:
        by_product[product].add(problem)
    rows: list[TrainingRow] = []
    for product in sorted(by_product):
        positives = sorted(by_product[product])
        candidates = context.history.candidate_problems(product)
        positive_set = set(positives)
        negatives = [candidate for candidate in candidates if candidate not in positive_set]
        negatives.sort(key=lambda problem: _stable_integer(quarter, product, problem))
        negative_limit = min(len(negatives), negative_ratio * len(positives))
        selected = positives + negatives[:negative_limit]
        features = context.row_features(product, selected)
        rows.extend(
            TrainingRow(features[problem], int(problem in positive_set)) for problem in selected
        )
    return rows
