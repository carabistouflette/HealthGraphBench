"""Run the bounded leakage-safe MAUDE temporal-model gate."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NotRequired, TypedDict

from .data import (
    QUARTERS,
    DataBundle,
    Edge,
    load_problem_parent_map,
    load_snapshots,
    sha256_file,
)
from .models import (
    FEATURE_NAMES,
    SUPPORT_BANDS,
    GRAPHSAGE_DIMENSION,
    GRAPHSAGE_EPOCHS,
    GRAPHSAGE_LEARNING_RATE,
    GRAPHSAGE_NEIGHBOR_SAMPLE,
    GRAPHSAGE_REGULARIZATION,
    BoostedStumpRanker,
    FeatureContext,
    GraphRanker,
    GraphSageRanker,
    History,
    LogisticRanker,
    SpectralRanker,
    TrainingRow,
    fit_boosted_stumps,
    fit_graph,
    fit_graphsage,
    fit_logistic,
    fit_spectral,
    sample_training_rows,
)

EVALUATION_QUARTERS: tuple[str, ...] = tuple(quarter for quarter in QUARTERS if quarter >= "2023Q1")
MODEL_REFIT_QUARTERS: tuple[str, ...] = ("2023Q1", "2024Q1", "2025Q1")
SUPPORT_THRESHOLDS: tuple[int, ...] = (1, 10, 50)
TOP_KS: tuple[int, ...] = (5, 10, 20)
NEGATIVE_RATIO = 1

PREDICTION_EXPORT_METHODS = frozenset(
    {"graph_message_passing_bpr", "graphsage_link_prediction"}
)


class MetricRow(TypedDict):
    positive_edges: int
    products: int
    hits_at_5: int
    hits_at_10: int
    hits_at_20: int
    recall_at_5: float
    recall_at_10: float
    recall_at_20: float
    macro_recall_at_5: float
    macro_recall_at_10: float
    macro_recall_at_20: float
    mrr: float


class AggregateResult(TypedDict):
    thresholds: dict[str, MetricRow]
    support_bands: dict[str, MetricRow]


class QuarterResult(TypedDict):
    thresholds: dict[str, MetricRow]
    support_bands: dict[str, MetricRow]


class MethodResult(TypedDict):
    quarters: dict[str, QuarterResult]
    validation: NotRequired[AggregateResult]
    test: NotRequired[AggregateResult]


FittedRanker = (
    LogisticRanker | BoostedStumpRanker | SpectralRanker | GraphRanker | GraphSageRanker
)


@dataclass(frozen=True, slots=True)
class MethodEvaluator:
    name: str
    scorer: Callable[[str, str], float]


@dataclass(slots=True)
class MetricAccumulator:
    positive_edges: int = 0
    products: int = 0
    hits_at_5: int = 0
    hits_at_10: int = 0
    hits_at_20: int = 0
    product_recall_sum_at_5: float = 0.0
    product_recall_sum_at_10: float = 0.0
    product_recall_sum_at_20: float = 0.0
    reciprocal_rank_sum: float = 0.0

    def add_product(self, ranks: Sequence[int], positive_count: int) -> None:
        self.positive_edges += positive_count
        self.products += 1
        for limit, field in ((5, "hits_at_5"), (10, "hits_at_10"), (20, "hits_at_20")):
            hits = sum(rank <= limit for rank in ranks)
            setattr(self, field, getattr(self, field) + hits)
            setattr(
                self,
                f"product_recall_sum_at_{limit}",
                getattr(self, f"product_recall_sum_at_{limit}") + hits / positive_count,
            )
        self.reciprocal_rank_sum += 1.0 / min(ranks) if ranks else 0.0

    def as_dict(self) -> MetricRow:
        if not self.positive_edges or not self.products:
            return {
                "positive_edges": self.positive_edges,
                "products": self.products,
                "hits_at_5": self.hits_at_5,
                "hits_at_10": self.hits_at_10,
                "hits_at_20": self.hits_at_20,
                "recall_at_5": 0.0,
                "recall_at_10": 0.0,
                "recall_at_20": 0.0,
                "macro_recall_at_5": 0.0,
                "macro_recall_at_10": 0.0,
                "macro_recall_at_20": 0.0,
                "mrr": 0.0,
            }
        return {
            "positive_edges": self.positive_edges,
            "products": self.products,
            "hits_at_5": self.hits_at_5,
            "hits_at_10": self.hits_at_10,
            "hits_at_20": self.hits_at_20,
            "recall_at_5": self.hits_at_5 / self.positive_edges,
            "recall_at_10": self.hits_at_10 / self.positive_edges,
            "recall_at_20": self.hits_at_20 / self.positive_edges,
            "macro_recall_at_5": self.product_recall_sum_at_5 / self.products,
            "macro_recall_at_10": self.product_recall_sum_at_10 / self.products,
            "macro_recall_at_20": self.product_recall_sum_at_20 / self.products,
            "mrr": self.reciprocal_rank_sum / self.products,
        }

    def merge(self, other: MetricAccumulator) -> None:
        self.positive_edges += other.positive_edges
        self.products += other.products
        self.hits_at_5 += other.hits_at_5
        self.hits_at_10 += other.hits_at_10
        self.hits_at_20 += other.hits_at_20
        self.product_recall_sum_at_5 += other.product_recall_sum_at_5
        self.product_recall_sum_at_10 += other.product_recall_sum_at_10
        self.product_recall_sum_at_20 += other.product_recall_sum_at_20
        self.reciprocal_rank_sum += other.reciprocal_rank_sum


def first_edges(bundle: DataBundle) -> dict[str, frozenset[Edge]]:
    seen: set[Edge] = set()
    result: dict[str, frozenset[Edge]] = {}
    for snapshot in bundle.snapshots:
        current = set(snapshot.edges)
        result[snapshot.quarter] = frozenset(current.difference(seen))
        seen.update(current)
    return result


def eligible_edges(
    first: frozenset[Edge],
    history: History,
) -> frozenset[Edge]:
    return frozenset(
        (product, problem)
        for product, problem in first
        if history.product_reports.get(product, 0) >= 1 and problem in history.problem_products
    )


def support_band(value: int) -> str:
    if value < 10:
        return "1-9"
    if value < 50:
        return "10-49"
    if value < 200:
        return "50-199"
    return "200+"


def _ranked_candidates(
    context: FeatureContext,
    product: str,
    scorer: Callable[[str, str], float],
) -> list[str]:
    candidates = context.history.candidate_problems(product)
    popularity = context.history.problem_products
    return sorted(
        candidates,
        key=lambda problem: (-scorer(product, problem), -len(popularity[problem]), problem),
    )


def evaluate_method(
    context: FeatureContext,
    eligible: frozenset[Edge],
    scorer: Callable[[str, str], float],
) -> tuple[dict[str, MetricRow], dict[str, MetricRow]]:
    positives_by_product: dict[str, set[str]] = defaultdict(set)
    for product, problem in eligible:
        positives_by_product[product].add(problem)
    rankings: dict[str, list[str]] = {}
    for product in sorted(positives_by_product):
        rankings[product] = _ranked_candidates(context, product, scorer)

    threshold_totals = {threshold: MetricAccumulator() for threshold in SUPPORT_THRESHOLDS}
    bands = {band: MetricAccumulator() for band in SUPPORT_BANDS}
    for product, positives in positives_by_product.items():
        ranking = rankings[product]
        ranks_by_problem = {problem: index + 1 for index, problem in enumerate(ranking)}
        supports = {
            problem: context.history.product_reports.get(product, 0) for problem in positives
        }
        for threshold, accumulator in threshold_totals.items():
            selected = [
                ranks_by_problem[problem]
                for problem, support in supports.items()
                if support >= threshold
            ]
            if selected:
                accumulator.add_product(selected, len(selected))
        by_band: dict[str, list[int]] = defaultdict(list)
        for problem, support in supports.items():
            by_band[support_band(support)].append(ranks_by_problem[problem])
        for band, ranks in by_band.items():
            bands[band].add_product(ranks, len(ranks))

    return (
        {
            str(threshold): accumulator.as_dict()
            for threshold, accumulator in threshold_totals.items()
        },
        {band: accumulator.as_dict() for band, accumulator in bands.items()},
    )


def prediction_rows(
    context: FeatureContext,
    eligible: frozenset[Edge],
    scorer: Callable[[str, str], float],
) -> list[dict[str, object]]:
    """Return deterministic positive/negative rows for clustered analysis."""

    positive_problems: dict[str, set[str]] = defaultdict(set)
    for product, problem in eligible:
        positive_problems[product].add(problem)
    positives_by_product = {
        product: tuple(sorted(problems))
        for product, problems in sorted(positive_problems.items())
    }
    rows: list[dict[str, object]] = []
    for product, positives in positives_by_product.items():
        candidates = context.history.candidate_problems(product)
        positive_set = set(positives)
        negative_candidates = [
            problem for problem in candidates if problem not in positive_set
        ]
        support = context.history.product_reports.get(product, 0)
        for problem in positives:
            rows.append(
                {
                    "cluster": product,
                    "quarter": context.quarter,
                    "product": product,
                    "problem": problem,
                    "label": 1,
                    "score": scorer(product, problem),
                    "history_support": support,
                    "candidate_count": len(candidates),
                }
            )
        if negative_candidates:
            for index in range(len(positives)):
                problem = negative_candidates[index % len(negative_candidates)]
                rows.append(
                    {
                        "cluster": product,
                        "quarter": context.quarter,
                        "product": product,
                        "problem": problem,
                        "label": 0,
                        "score": scorer(product, problem),
                        "history_support": support,
                        "candidate_count": len(candidates),
                    }
                )
    return rows


def _score_popularity(context: FeatureContext, _product: str, problem: str) -> float:
    return float(len(context.history.problem_products[problem]))


def _score_neighbor(context: FeatureContext, product: str, problem: str) -> float:
    return float(context.neighbor_scores(product).get(problem, 0))


def _score_feature_model(
    context: FeatureContext,
    product: str,
    problem: str,
    model: LogisticRanker | BoostedStumpRanker,
) -> float:
    return model.score(context.features_for(product, problem))


def _score_spectral(
    _context: FeatureContext,
    product: str,
    problem: str,
    model: SpectralRanker,
) -> float:
    return model.score(product, problem)


def _score_graph(
    _context: FeatureContext,
    product: str,
    problem: str,
    model: GraphRanker | GraphSageRanker,
) -> float:
    return model.score(product, problem)


def _bind_popularity_scorer(context: FeatureContext) -> Callable[[str, str], float]:
    def scorer(product: str, problem: str) -> float:
        return _score_popularity(context, product, problem)

    return scorer


def _bind_neighbor_scorer(context: FeatureContext) -> Callable[[str, str], float]:
    def scorer(product: str, problem: str) -> float:
        return _score_neighbor(context, product, problem)

    return scorer


def _bind_feature_scorer(
    context: FeatureContext,
    model: LogisticRanker | BoostedStumpRanker,
) -> Callable[[str, str], float]:
    def scorer(product: str, problem: str) -> float:
        return _score_feature_model(context, product, problem, model)

    return scorer


def _bind_spectral_scorer(
    context: FeatureContext,
    model: SpectralRanker,
) -> Callable[[str, str], float]:
    def scorer(product: str, problem: str) -> float:
        return _score_spectral(context, product, problem, model)

    return scorer


def _bind_graph_scorer(
    _context: FeatureContext,
    model: GraphRanker | GraphSageRanker,
) -> Callable[[str, str], float]:
    def scorer(product: str, problem: str) -> float:
        return _score_graph(_context, product, problem, model)

    return scorer


def _aggregate_method_period(
    quarters: Mapping[str, QuarterResult],
    selected: Sequence[str],
) -> AggregateResult:
    threshold_aggregate: dict[str, MetricRow] = {}
    band_aggregate: dict[str, MetricRow] = {}
    for threshold in SUPPORT_THRESHOLDS:
        rows = {quarter: quarters[quarter]["thresholds"][str(threshold)] for quarter in selected}
        threshold_aggregate[str(threshold)] = _aggregate_metric_rows(rows)
    for band in SUPPORT_BANDS:
        rows = {
            quarter: quarters[quarter]["support_bands"][band]
            for quarter in selected
            if band in quarters[quarter]["support_bands"]
        }
        band_aggregate[band] = (
            _aggregate_metric_rows(rows) if rows else MetricAccumulator().as_dict()
        )
    return {"thresholds": threshold_aggregate, "support_bands": band_aggregate}


def _aggregate_metric_rows(
    quarter_rows: Mapping[str, MetricRow],
) -> MetricRow:
    accumulator = MetricAccumulator()
    for row in quarter_rows.values():
        accumulator.positive_edges += int(row["positive_edges"])
        accumulator.products += int(row["products"])
        accumulator.hits_at_5 += int(row["hits_at_5"])
        accumulator.hits_at_10 += int(row["hits_at_10"])
        accumulator.hits_at_20 += int(row["hits_at_20"])
        accumulator.product_recall_sum_at_5 += float(row["macro_recall_at_5"]) * int(
            row["products"]
        )
        accumulator.product_recall_sum_at_10 += float(row["macro_recall_at_10"]) * int(
            row["products"]
        )
        accumulator.product_recall_sum_at_20 += float(row["macro_recall_at_20"]) * int(
            row["products"]
        )
        accumulator.reciprocal_rank_sum += float(row["mrr"]) * int(row["products"])
    return accumulator.as_dict()


def _source_metadata(paths: Sequence[Path]) -> list[dict[str, str | int]]:
    return [
        {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in paths
    ]


def _audit_dict(bundle: DataBundle) -> dict[str, object]:
    audit = bundle.audit
    return {
        "device_files": {year: stats.as_dict() for year, stats in audit.device_stats.items()},
        "problem_file": audit.problem_stats.as_dict(),
        "merge": {
            "unique_device_mdr_keys": audit.unique_device_mdr_keys,
            "matched_device_problem_mdr_keys": audit.matched_device_problem_mdr_keys,
            "problem_only_mdr_keys": audit.problem_only_mdr_keys,
            "unique_product_problem_edges": audit.unique_product_problem_edges,
            "unique_product_codes": audit.unique_product_codes,
            "unique_problem_codes": audit.unique_problem_codes,
        },
        "device_multiplicity": {
            "valid_device_rows": audit.valid_device_rows,
            "keys_multiple_valid_device_rows": audit.keys_multiple_valid_device_rows,
            "duplicate_valid_rows_beyond_unique_product_per_key": audit.duplicate_valid_rows_beyond_unique_product_per_key,
            "keys_multiple_product_codes": audit.keys_multiple_product_codes,
            "max_valid_rows_per_key": audit.max_valid_rows_per_key,
            "max_unique_products_per_key": audit.max_unique_products_per_key,
        },
        "problem_multiplicity": {
            "keys_with_multiple_distinct_problem_codes": audit.problem_keys_with_multiple_codes,
            "max_distinct_problem_codes_per_key": audit.max_distinct_problem_codes_per_key,
        },
    }


def _gate_decision(result_by_method: Mapping[str, MethodResult]) -> dict[str, object]:
    baseline_names = {"global_popularity", "neighbor_frequency"}
    learned_names = sorted(set(result_by_method).difference(baseline_names))
    test_quarters = tuple(
        quarter for quarter in EVALUATION_QUARTERS if quarter.startswith(("2024", "2025"))
    )
    comparisons: dict[str, object] = {}
    qualified: list[str] = []
    for name in learned_names:
        method = result_by_method[name]
        quarters = method["quarters"]
        global_wins = 0
        neighbor_wins = 0
        for quarter in test_quarters:
            learned = quarters[quarter]["thresholds"]["1"]["recall_at_10"]
            popularity = result_by_method["global_popularity"]["quarters"][quarter]["thresholds"][
                "1"
            ]["recall_at_10"]
            neighbor = result_by_method["neighbor_frequency"]["quarters"][quarter]["thresholds"][
                "1"
            ]["recall_at_10"]
            global_wins += learned > popularity
            neighbor_wins += learned > neighbor
        low_support = method["test"]["support_bands"]["1-9"]["recall_at_10"]
        baseline_low_support = max(
            result_by_method["global_popularity"]["test"]["support_bands"]["1-9"]["recall_at_10"],
            result_by_method["neighbor_frequency"]["test"]["support_bands"]["1-9"]["recall_at_10"],
        )
        qualifies = (
            global_wins >= math.ceil(len(test_quarters) / 2)
            and neighbor_wins >= math.ceil(len(test_quarters) / 2)
            and low_support >= baseline_low_support
        )
        comparisons[name] = {
            "test_quarter_wins_over_global": global_wins,
            "test_quarter_wins_over_neighbor": neighbor_wins,
            "test_quarters": len(test_quarters),
            "low_support_recall_at_10": low_support,
            "best_baseline_low_support_recall_at_10": baseline_low_support,
            "qualifies_under_frozen_criterion": qualifies,
        }
        if qualifies:
            qualified.append(name)
    decision = "GO_TO_NEXT_GRAPH_MODEL_GATE" if qualified else "STOP_BEFORE_PLATFORM"
    return {
        "frozen_criterion": "A learned method must beat both baselines in at least half of held-out test quarters at support >=1 and must not have lower aggregate 1-9-report Recall@10 than either baseline.",
        "learned_methods_qualifying": qualified,
        "decision": decision,
        "comparisons": comparisons,
        "scope_boundary": "This gate does not activate Neo4j, GraphRAG, an interface, specification revision, or clinical/safety claims.",
    }


def run_gate(
    device_dir: Path,
    problem_zip: Path,
    problem_code_map: Path,
    output: Path,
    *,
    bundle: DataBundle | None = None,
) -> dict[str, object]:
    if bundle is None:
        bundle = load_snapshots(device_dir, problem_zip)
    observed_codes = {problem for snapshot in bundle.snapshots for _, problem in snapshot.edges}
    parent_map, code_to_imdrf = load_problem_parent_map(problem_code_map, observed_codes)
    first = first_edges(bundle)
    history = History.empty()
    training_rows: list[TrainingRow] = []
    fitted: dict[str, FittedRanker] = {}
    result_by_method: dict[str, MethodResult] = {}
    training_row_counts: dict[str, int] = {}

    def fit_models() -> None:
        nonlocal fitted
        fitted = {
            "logistic_tabular": fit_logistic(training_rows),
            "boosted_stumps_tabular": fit_boosted_stumps(training_rows),
            "matrix_factorization_spectral": fit_spectral(history),
            "graph_message_passing_bpr": fit_graph(history),
            "graphsage_link_prediction": fit_graphsage(history),
        }

    for snapshot in bundle.snapshots:
        quarter = snapshot.quarter
        current_first = first[quarter]
        current_eligible = eligible_edges(current_first, history)
        if quarter in MODEL_REFIT_QUARTERS:
            if not training_rows:
                raise RuntimeError(f"No temporal training rows available before {quarter}")
            fit_models()
            training_row_counts[quarter] = len(training_rows)
        if quarter in EVALUATION_QUARTERS:
            context = FeatureContext(history, quarter, parent_map)
            logistic_model = fitted["logistic_tabular"]
            boosted_model = fitted["boosted_stumps_tabular"]
            spectral_model = fitted["matrix_factorization_spectral"]
            graph_model = fitted["graph_message_passing_bpr"]
            graphsage_model = fitted["graphsage_link_prediction"]
            if not isinstance(logistic_model, LogisticRanker):
                raise TypeError("Internal logistic model shape error")
            if not isinstance(boosted_model, BoostedStumpRanker):
                raise TypeError("Internal boosted model shape error")
            if not isinstance(spectral_model, SpectralRanker):
                raise TypeError("Internal spectral model shape error")
            if not isinstance(graph_model, GraphRanker):
                raise TypeError("Internal graph model shape error")
            if not isinstance(graphsage_model, GraphSageRanker):
                raise TypeError("Internal GraphSAGE model shape error")
            methods = (
                MethodEvaluator("global_popularity", _bind_popularity_scorer(context)),
                MethodEvaluator("neighbor_frequency", _bind_neighbor_scorer(context)),
                MethodEvaluator("logistic_tabular", _bind_feature_scorer(context, logistic_model)),
                MethodEvaluator(
                    "boosted_stumps_tabular", _bind_feature_scorer(context, boosted_model)
                ),
                MethodEvaluator(
                    "matrix_factorization_spectral",
                    _bind_spectral_scorer(context, spectral_model),
                ),
                MethodEvaluator(
                    "graph_message_passing_bpr", _bind_graph_scorer(context, graph_model)
                ),
                MethodEvaluator(
                    "graphsage_link_prediction",
                    _bind_graph_scorer(context, graphsage_model),
                ),
            )
            for method in methods:
                threshold_rows, band_rows = evaluate_method(
                    context, current_eligible, method.scorer
                )
                method_result = result_by_method.setdefault(method.name, {"quarters": {}})
                method_result["quarters"][quarter] = {
                    "thresholds": threshold_rows,
                    "support_bands": band_rows,
                }
                if method.name in PREDICTION_EXPORT_METHODS:
                    method_result.setdefault("prediction_rows", []).extend(
                        prediction_rows(context, current_eligible, method.scorer)
                    )

        if quarter < "2025Q1":
            training_rows.extend(
                sample_training_rows(
                    quarter,
                    current_eligible,
                    FeatureContext(history, quarter, parent_map),
                    NEGATIVE_RATIO,
                )
            )
        history.add(snapshot, parent_map)

    for method_result in result_by_method.values():
        quarters = method_result["quarters"]
        method_result["validation"] = _aggregate_method_period(
            quarters, tuple(q for q in EVALUATION_QUARTERS if q.startswith("2023"))
        )
        method_result["test"] = _aggregate_method_period(
            quarters, tuple(q for q in EVALUATION_QUARTERS if q.startswith(("2024", "2025")))
        )

    first_rows = [
        [
            quarter,
            len(first[quarter]),
            len(eligible_edges(first[quarter], _history_before(bundle, quarter, parent_map))),
        ]
        for quarter in QUARTERS
    ]
    output_record: dict[str, object] = {
        "record_kind": "P3_MAUDE_TEMPORAL_MODEL_GATE",
        "status": "COMPLETE",
        "task_definition": {
            "target": "Future observed MAUDE product-code/device-problem-code edge.",
            "positive_label": "First observed report-level relationship in quarter q.",
            "negative_label": "A known problem code not linked to the product before q and not observed for that product in q; this is a temporal non-observation label, not proof of no underlying failure.",
            "candidate_rule": "Problem code existed historically before q AND the product/problem edge never appeared before q.",
            "date_field": "DATE_RECEIVED",
            "no_random_edge_split": True,
            "training_quarters": "2019Q1-2022Q4",
            "validation_quarters": "2023Q1-2023Q4",
            "test_quarters": "2024Q1-2025Q4",
        },
        "configuration": {
            "negative_sampling_ratio": NEGATIVE_RATIO,
            "support_thresholds": list(SUPPORT_THRESHOLDS),
            "top_k": list(TOP_KS),
            "support_bands": list(SUPPORT_BANDS),
            "model_refit_quarters": list(MODEL_REFIT_QUARTERS),
            "feature_names": list(FEATURE_NAMES),
            "recent_window_quarters": 4,
            "spectral_rank": 8,
            "spectral_iterations": 18,
            "graph_embedding_dimension": 8,
            "graph_bpr_epochs": 4,
            "graph_propagation": "0.5 learned node embedding + 0.5 mean one-hop neighbor embedding",
            "graphsage": {
                "dimension": GRAPHSAGE_DIMENSION,
                "epochs": GRAPHSAGE_EPOCHS,
                "neighbor_sample": GRAPHSAGE_NEIGHBOR_SAMPLE,
                "learning_rate": GRAPHSAGE_LEARNING_RATE,
                "regularization": GRAPHSAGE_REGULARIZATION,
                "objective": "bpr",
                "activation": "tanh",
            },
            "tree_rounds": 12,
        },
        "sources": {
            "device_dir": str(device_dir),
            "problem_zip": str(problem_zip),
            "problem_code_map": str(problem_code_map),
            "files": _source_metadata((*bundle.source_paths, problem_code_map)),
            "official_urls": {
                "data_files": "https://www.fda.gov/medical-devices/medical-device-reporting-mdr-how-report-medical-device-problems/mdr-data-files",
                "adverse_event_codes": "https://www.fda.gov/medical-devices/mandatory-reporting-requirements-manufacturers-importers-and-device-user-facilities/mdr-adverse-event-codes",
                "device_problem_map": "https://www.accessdata.fda.gov/MAUDE/ftparea/deviceproblemcodes2025.zip",
            },
        },
        "dataset_audit": _audit_dict(bundle),
        "problem_hierarchy": {
            "observed_problem_codes": len(observed_codes),
            "codes_with_imdrf_mapping": len(set(observed_codes).intersection(code_to_imdrf)),
            "codes_with_derived_parent": len(parent_map),
            "parent_derivation": "Nearest shorter IMDRF_CODE prefix present in the official FDA mapping; numeric FDA-code adjacency is never treated as hierarchy.",
        },
        "quarterly_first_edges": {
            "columns": ["quarter", "first_observed_edges", "eligible_edges"],
            "rows": first_rows,
        },
        "methods": [
            {"method": name, **values} for name, values in sorted(result_by_method.items())
        ],
        "leakage_controls": [
            "History state is updated only after each quarter is scored and training rows are created.",
            "Candidate problems are restricted to prior globally observed codes not previously linked to the target product.",
            "Tabular features use only prior reports, prior product/problem edges, prior manufacturers, prior parent mappings, and prior four-quarter activity.",
            "Matrix-factorization and graph embeddings are fit only on the history available at each configured refit quarter.",
            "Current-quarter labels are never used as features or candidate-generation inputs.",
        ],
        "interpretation_limits": [
            "MAUDE is passive surveillance with under-reporting, reporting bias, incomplete/unverified records, and no device-use denominator.",
            "Observed edges represent reporting/coding patterns, not incidence, causation, or clinical safety risk.",
            "Product codes are coarse classification proxies and are reused across manufacturers.",
            "A temporal negative means no observed standardized relationship in the evaluated window; it is not a clinical negative.",
        ],
        "training_row_counts_at_refit": training_row_counts,
    }
    output_record["decision"] = _gate_decision(result_by_method)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_record, indent=2) + "\n", encoding="utf-8")
    return output_record


def _history_before(
    bundle: DataBundle,
    quarter: str,
    problem_parent_map: Mapping[str, str],
) -> History:
    history = History.empty()
    for snapshot in bundle.snapshots:
        if snapshot.quarter >= quarter:
            break
        history.add(snapshot, problem_parent_map)
    return history


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-dir", type=Path, required=True)
    parser.add_argument("--problem-zip", type=Path, required=True)
    parser.add_argument("--problem-code-map", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    run_gate(args.device_dir, args.problem_zip, args.problem_code_map, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
