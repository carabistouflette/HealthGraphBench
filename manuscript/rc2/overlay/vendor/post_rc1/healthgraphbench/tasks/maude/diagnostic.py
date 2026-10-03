"""Run the bounded, exploratory GraphSAGE duration diagnostic on prepared MAUDE snapshots."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import multiprocessing
import os
import platform
import resource
import sys
import time
import traceback
import zlib
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .data import QUARTERS
from .evaluate import MetricAccumulator, _ranked_candidates, eligible_edges, support_band
from .models import (
    GRAPHSAGE_DIMENSION,
    GRAPHSAGE_LEARNING_RATE,
    GRAPHSAGE_NEIGHBOR_SAMPLE,
    GRAPHSAGE_REGULARIZATION,
    FeatureContext,
    GraphSageRanker,
    History,
    fit_graphsage,
)

VALIDATION_EPOCHS = (0, 3, 10, 30)
SELECTION_EPOCHS = (3, 10, 30)
VALIDATION_QUARTERS = ("2023Q1", "2023Q2", "2023Q3", "2023Q4")
VALIDATION_POPULATION = {
    "products_with_positives": 3483,
    "positive_edges": 7705,
    "candidate_pairs": 1_618_588,
}
MAX_TIMEOUT_SECONDS = 900.0
MAX_RSS_BYTES = 512 * 1024 * 1024
MAX_OUTPUT_BYTES = 512 * 1024 * 1024
_INTERNAL_OUTPUT_RESERVE = 64 * 1024
_POLL_SECONDS = 0.05
_THREAD_ENV_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)


def _limit_library_threads() -> None:
    for name in _THREAD_ENV_VARIABLES:
        os.environ[name] = "1"


@dataclass(frozen=True, slots=True)
class PreparedSnapshot:
    quarter: str
    product_reports: Mapping[str, int]
    edges: frozenset[tuple[str, str]]


class OutputLimitExceeded(RuntimeError):
    """Raised before a worker writes beyond its reserved phase-output budget."""


class PhaseExecutionError(RuntimeError):
    """A supervised phase failed or was terminated by an enforced resource limit."""

    def __init__(self, message: str, supervisor: Mapping[str, object]) -> None:
        super().__init__(message)
        self.supervisor = dict(supervisor)


class _BudgetFile:
    def __init__(self, path: Path, budget: _OutputBudget) -> None:
        self._file = path.open("wb")
        self._budget = budget

    def write(self, value: bytes) -> int:
        if self._budget.used_bytes + len(value) > self._budget.worker_limit_bytes:
            raise OutputLimitExceeded(
                f"phase output would exceed {self._budget.phase_limit_bytes} bytes"
            )
        written = self._file.write(value)
        self._budget.used_bytes += written
        return written

    def flush(self) -> None:
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> _BudgetFile:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class _OutputBudget:
    def __init__(self, root: Path, phase_limit_bytes: int) -> None:
        self.root = root
        self.phase_limit_bytes = phase_limit_bytes
        self.worker_limit_bytes = max(0, phase_limit_bytes - _INTERNAL_OUTPUT_RESERVE)
        self.used_bytes = 0

    def open(self, relative_path: str) -> _BudgetFile:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        return _BudgetFile(path, self)

    def write_json(self, relative_path: str, value: object) -> None:
        encoded = json.dumps(
            value, ensure_ascii=False, indent=2, allow_nan=False
        ).encode("utf-8") + b"\n"
        with self.open(relative_path) as output:
            output.write(encoded)


class _GzipJsonl:
    def __init__(self, budget: _OutputBudget, relative_path: str) -> None:
        self._raw = budget.open(relative_path)
        self._gzip = gzip.GzipFile(fileobj=self._raw, mode="wb", filename="")

    def write(self, value: object) -> None:
        line = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8") + b"\n"
        self._gzip.write(line)

    def flush(self) -> None:
        self._gzip.flush(zlib.Z_SYNC_FLUSH)
        self._raw.flush()

    def close(self) -> None:
        try:
            self._gzip.close()
        finally:
            self._raw.close()

    def __enter__(self) -> _GzipJsonl:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def _write_gzip_json(budget: _OutputBudget, relative_path: str, value: object) -> None:
    raw = budget.open(relative_path)
    compressed = gzip.GzipFile(fileobj=raw, mode="wb", filename="")
    try:
        encoder = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        for chunk in encoder.iterencode(value):
            compressed.write(chunk.encode("utf-8"))
        compressed.write(b"\n")
    finally:
        try:
            compressed.close()
        finally:
            raw.close()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_prepared_snapshots(path: Path) -> tuple[dict[str, object], tuple[PreparedSnapshot, ...]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        prepared = json.load(source)
    if not isinstance(prepared, dict):
        raise ValueError("prepared input root must be a JSON object")
    if not isinstance(prepared.get("provenance"), dict):
        raise ValueError("prepared input must include provenance")
    if "schema" not in prepared:
        raise ValueError("prepared input must include schema")
    rows = prepared.get("snapshots")
    if not isinstance(rows, list):
        raise ValueError("prepared input snapshots must be a list")
    snapshots: list[PreparedSnapshot] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"quarter", "product_reports", "edges"}:
            raise ValueError("each prepared snapshot must contain only quarter, product_reports, and edges")
        quarter = row["quarter"]
        reports = row["product_reports"]
        edges = row["edges"]
        if not isinstance(quarter, str) or not isinstance(reports, dict) or not isinstance(edges, list):
            raise ValueError("prepared snapshot fields have invalid types")
        normalized_reports: dict[str, int] = {}
        for product, count in reports.items():
            if not isinstance(product, str) or not product or isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"invalid product report count in {quarter}")
            normalized_reports[product] = count
        normalized_edges: set[tuple[str, str]] = set()
        for edge in edges:
            if not isinstance(edge, (list, tuple)) or len(edge) != 2:
                raise ValueError(f"invalid edge in {quarter}")
            product, problem = edge
            if not isinstance(product, str) or not product or not isinstance(problem, str) or not problem:
                raise ValueError(f"invalid edge identifiers in {quarter}")
            normalized_edges.add((product, problem))
        snapshots.append(
            PreparedSnapshot(quarter, normalized_reports, frozenset(normalized_edges))
        )
    expected_quarters = QUARTERS
    if tuple(snapshot.quarter for snapshot in snapshots) != expected_quarters:
        raise ValueError("prepared input must contain the ordered 2019Q1–2025Q4 snapshots")
    return prepared, tuple(snapshots)


def _first_edges(snapshots: Sequence[PreparedSnapshot]) -> dict[str, frozenset[tuple[str, str]]]:
    seen: set[tuple[str, str]] = set()
    result: dict[str, frozenset[tuple[str, str]]] = {}
    for snapshot in snapshots:
        current = set(snapshot.edges)
        result[snapshot.quarter] = frozenset(current.difference(seen))
        seen.update(current)
    return result


def _add_snapshot_to_history(history: History, snapshot: PreparedSnapshot) -> None:
    """Add only values physically available in the prepared snapshot."""
    history.product_reports.update(snapshot.product_reports)
    for product, problem in snapshot.edges:
        history.product_problems[product].add(problem)
        history.problem_products[problem].add(product)


def _history_through(
    snapshots: Sequence[PreparedSnapshot], before_quarter: str
) -> History:
    history = History.empty()
    for snapshot in snapshots:
        if snapshot.quarter >= before_quarter:
            break
        _add_snapshot_to_history(history, snapshot)
    return history


def _copy_history(source: History) -> History:
    copied = History.empty()
    copied.product_reports.update(source.product_reports)
    for product, problems in source.product_problems.items():
        copied.product_problems[product].update(problems)
    for problem, products in source.problem_products.items():
        copied.problem_products[problem].update(products)
    return copied


def _metric_accumulators() -> tuple[dict[int, MetricAccumulator], dict[str, MetricAccumulator]]:
    return (
        {threshold: MetricAccumulator() for threshold in (1, 10, 50)},
        {band: MetricAccumulator() for band in ("1-9", "10-49", "50-199", "200+")},
    )


def _accumulator_payload(accumulator: MetricAccumulator) -> dict[str, object]:
    return {
        "positive_edges": accumulator.positive_edges,
        "products": accumulator.products,
        "hits_at_5": accumulator.hits_at_5,
        "hits_at_10": accumulator.hits_at_10,
        "hits_at_20": accumulator.hits_at_20,
        "product_recall_sum_at_5": accumulator.product_recall_sum_at_5,
        "product_recall_sum_at_10": accumulator.product_recall_sum_at_10,
        "product_recall_sum_at_20": accumulator.product_recall_sum_at_20,
        "reciprocal_rank_sum": accumulator.reciprocal_rank_sum,
    }


def _metric_report(
    thresholds: Mapping[int, MetricAccumulator],
    bands: Mapping[str, MetricAccumulator],
) -> dict[str, object]:
    return {
        "thresholds": {str(key): value.as_dict() for key, value in thresholds.items()},
        "support_bands": {key: value.as_dict() for key, value in bands.items()},
        "accumulators": {
            "thresholds": {str(key): _accumulator_payload(value) for key, value in thresholds.items()},
            "support_bands": {key: _accumulator_payload(value) for key, value in bands.items()},
        },
    }


def _merge_accumulator_payloads(
    left: Mapping[str, object], right: Mapping[str, object]
) -> dict[str, object]:
    merged: dict[str, object] = {}
    for key in (
        "positive_edges",
        "products",
        "hits_at_5",
        "hits_at_10",
        "hits_at_20",
        "product_recall_sum_at_5",
        "product_recall_sum_at_10",
        "product_recall_sum_at_20",
        "reciprocal_rank_sum",
    ):
        merged[key] = left[key] + right[key]  # type: ignore[operator]
    return merged


def _accumulator_from_payload(payload: Mapping[str, object]) -> MetricAccumulator:
    return MetricAccumulator(
        positive_edges=int(payload["positive_edges"]),
        products=int(payload["products"]),
        hits_at_5=int(payload["hits_at_5"]),
        hits_at_10=int(payload["hits_at_10"]),
        hits_at_20=int(payload["hits_at_20"]),
        product_recall_sum_at_5=float(payload["product_recall_sum_at_5"]),
        product_recall_sum_at_10=float(payload["product_recall_sum_at_10"]),
        product_recall_sum_at_20=float(payload["product_recall_sum_at_20"]),
        reciprocal_rank_sum=float(payload["reciprocal_rank_sum"]),
    )


def _write_epoch_callback(budget: _OutputBudget, fit_dir: str) -> tuple[Callable[[dict[str, object]], None], Callable[[], None]]:
    writer = _GzipJsonl(budget, f"{fit_dir}/epochs.jsonl.gz")

    def on_epoch(record: dict[str, object]) -> None:
        writer.write(record)
        writer.flush()

    return on_epoch, writer.close


def _fit_one(
    history: History,
    epochs: int,
    budget: _OutputBudget,
    fit_dir: str,
    trace: _GzipJsonl,
    aggregation: str = "mean",
) -> tuple[GraphSageRanker, dict[str, object]]:
    fit_path = budget.root / fit_dir
    fit_path.mkdir(parents=True, exist_ok=True)
    on_epoch, close_epochs = _write_epoch_callback(budget, fit_dir)
    checkpoint_calls = 0

    def on_checkpoint(state: dict[str, object]) -> None:
        nonlocal checkpoint_calls
        checkpoint_calls += 1
        if checkpoint_calls != 1:
            raise RuntimeError("fit_graphsage emitted more than one final checkpoint")
        _write_gzip_json(budget, f"{fit_dir}/checkpoint.json.gz", state)

    start_wall = time.monotonic()
    start_cpu = time.process_time()
    trace.write({"event": "fit_started", "epochs": epochs, "fit_dir": fit_dir})
    trace.flush()
    try:
        ranker = fit_graphsage(
            history,
            dimension=GRAPHSAGE_DIMENSION,
            epochs=epochs,
            neighbor_sample=GRAPHSAGE_NEIGHBOR_SAMPLE,
            learning_rate=GRAPHSAGE_LEARNING_RATE,
            regularization=GRAPHSAGE_REGULARIZATION,
            aggregation=aggregation,
            on_epoch=on_epoch,
            on_checkpoint=on_checkpoint,
        )
    finally:
        close_epochs()
    fit_wall = time.monotonic() - start_wall
    fit_cpu = time.process_time() - start_cpu
    if checkpoint_calls != 1:
        raise RuntimeError("fit_graphsage did not emit its final checkpoint")
    epoch_records = _read_gzip_jsonl(budget.root / fit_dir / "epochs.jsonl.gz")
    training_configuration: dict[str, object] = {
        "dimension": GRAPHSAGE_DIMENSION,
        "neighbor_sample": GRAPHSAGE_NEIGHBOR_SAMPLE if aggregation == "mean" else 0,
        "learning_rate": GRAPHSAGE_LEARNING_RATE,
        "regularization": GRAPHSAGE_REGULARIZATION,
        "objective": "bpr",
        "activation": "tanh",
    }
    if aggregation != "mean":
        training_configuration["aggregation"] = aggregation
    fit_record: dict[str, object] = {
        "epochs_requested": epochs,
        "epochs_completed": len(epoch_records),
        "wall_seconds": fit_wall,
        "cpu_seconds": fit_cpu,
        "steps": sum(int(row["steps"]) for row in epoch_records),
        "positive_edges_skipped": sum(int(row["positive_edges_skipped"]) for row in epoch_records),
        "triplets_visited": sum(int(row["triplets_visited"]) for row in epoch_records),
        "training_configuration": training_configuration,
        "loss_semantics": "epoch mean softplus(-margin) before updates; regularization is separate and is not included in this data-loss value",
        "epoch_log": f"{fit_dir}/epochs.jsonl.gz",
        "checkpoint": f"{fit_dir}/checkpoint.json.gz",
    }
    trace.write({"event": "fit_completed", "epochs": epochs, **fit_record})
    trace.flush()
    return ranker, fit_record


def _read_gzip_jsonl(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def _evaluate_quarter(
    *,
    snapshot: PreparedSnapshot,
    first: frozenset[tuple[str, str]],
    history: History,
    ranker: GraphSageRanker,
    budget: _OutputBudget,
    artifact_prefix: str,
    trace: _GzipJsonl,
) -> tuple[dict[str, object], dict[int, MetricAccumulator], dict[str, MetricAccumulator]]:
    eligible = eligible_edges(first, history)
    positives_by_product: dict[str, set[str]] = defaultdict(set)
    for product, problem in eligible:
        positives_by_product[product].add(problem)
    threshold_totals, band_totals = _metric_accumulators()
    candidate_pairs = 0
    candidate_sets = _GzipJsonl(budget, f"{artifact_prefix}/candidate_sets.jsonl.gz")
    predictions = _GzipJsonl(budget, f"{artifact_prefix}/candidate_predictions.jsonl.gz")
    context = FeatureContext(history, snapshot.quarter, {})
    try:
        for product in sorted(positives_by_product):
            positive_problems = positives_by_product[product]
            original_candidates = context.history.candidate_problems(product)
            candidate_hash = _json_sha256(original_candidates)
            candidate_scores: dict[str, float] = {}

            def score(candidate_product: str, problem: str) -> float:
                value = float(ranker.score(candidate_product, problem))
                if not math.isfinite(value):
                    raise ValueError(f"non-finite GraphSAGE score for {candidate_product}/{problem}")
                candidate_scores[problem] = value
                return value

            ranking = _ranked_candidates(context, product, score)
            if len(candidate_scores) != len(original_candidates) or set(candidate_scores) != set(original_candidates):
                raise RuntimeError("ranked candidates did not score each historical candidate exactly once")
            ranks = {problem: index + 1 for index, problem in enumerate(ranking)}
            if not positive_problems.issubset(ranks):
                raise RuntimeError("eligible positive missing from its historical candidate list")
            candidate_sets.write(
                {
                    "quarter": snapshot.quarter,
                    "product": product,
                    "candidate_ids": original_candidates,
                    "candidate_set_sha256": candidate_hash,
                    "positive_problem_ids": sorted(positive_problems),
                    "history_product_reports": int(history.product_reports.get(product, 0)),
                }
            )
            candidate_pairs += len(original_candidates)
            for problem in ranking:
                predictions.write(
                    {
                        "quarter": snapshot.quarter,
                        "product": product,
                        "problem": problem,
                        "score": candidate_scores[problem],
                        "rank": ranks[problem],
                        "label": int(problem in positive_problems),
                        "candidate_set_sha256": candidate_hash,
                    }
                )
            candidate_sets.flush()
            predictions.flush()

            positive_ranks = {problem: ranks[problem] for problem in positive_problems}
            supports = {
                problem: int(history.product_reports.get(product, 0))
                for problem in positive_problems
            }
            for threshold, accumulator in threshold_totals.items():
                selected_ranks = [
                    positive_ranks[problem]
                    for problem, support in supports.items()
                    if support >= threshold
                ]
                if selected_ranks:
                    accumulator.add_product(selected_ranks, len(selected_ranks))
            by_band: dict[str, list[int]] = defaultdict(list)
            for problem, rank in positive_ranks.items():
                by_band[support_band(supports[problem])].append(rank)
            for band, selected_ranks in by_band.items():
                band_totals[band].add_product(selected_ranks, len(selected_ranks))
    finally:
        candidate_sets.close()
        predictions.close()
    report = _metric_report(threshold_totals, band_totals)
    quarter_record: dict[str, object] = {
        "quarter": snapshot.quarter,
        "products_with_positives": len(positives_by_product),
        "positive_edges": len(eligible),
        "candidate_pairs": candidate_pairs,
        "metrics": report,
        "artifacts": {
            "candidate_sets": f"{artifact_prefix}/candidate_sets.jsonl.gz",
            "candidate_predictions": f"{artifact_prefix}/candidate_predictions.jsonl.gz",
        },
    }
    budget.write_json(f"{artifact_prefix}/quarter_result.json", quarter_record)
    trace.write(
        {
            "event": "quarter_completed",
            "quarter": snapshot.quarter,
            "products_with_positives": len(positives_by_product),
            "positive_edges": len(eligible),
            "candidate_pairs": candidate_pairs,
        }
    )
    trace.flush()
    return quarter_record, threshold_totals, band_totals


def _merge_metric_sets(
    destination: tuple[dict[int, MetricAccumulator], dict[str, MetricAccumulator]],
    source: tuple[Mapping[int, MetricAccumulator], Mapping[str, MetricAccumulator]],
) -> None:
    for key, accumulator in source[0].items():
        destination[0][key].merge(accumulator)
    for key, accumulator in source[1].items():
        destination[1][key].merge(accumulator)


def _validation_worker(
    input_path: str,
    phase_path: str,
    phase_limit_bytes: int,
    validation_epochs: tuple[int, ...] = VALIDATION_EPOCHS,
    aggregation: str = "mean",
) -> None:
    root = Path(phase_path)
    budget = _OutputBudget(root, phase_limit_bytes)
    trace = _GzipJsonl(budget, "trace.jsonl.gz")
    try:
        _prepared, snapshots = _load_prepared_snapshots(Path(input_path))
        snapshot_by_quarter = {snapshot.quarter: snapshot for snapshot in snapshots}
        first_by_quarter = _first_edges(snapshots)
        initial_history = _history_through(snapshots, "2023Q1")
        all_fit_results: dict[str, object] = {}
        for epochs in validation_epochs:
            fit_dir = f"fit_epochs_{epochs:02d}"
            ranker, fit_record = _fit_one(
                initial_history, epochs, budget, fit_dir, trace, aggregation
            )
            history = _copy_history(initial_history)
            quarter_records: dict[str, object] = {}
            annual_totals = _metric_accumulators()
            total_products = total_positives = total_candidates = 0
            for quarter in VALIDATION_QUARTERS:
                snapshot = snapshot_by_quarter[quarter]
                quarter_record, threshold_totals, band_totals = _evaluate_quarter(
                    snapshot=snapshot,
                    first=first_by_quarter[quarter],
                    history=history,
                    ranker=ranker,
                    budget=budget,
                    artifact_prefix=f"{fit_dir}/{quarter}",
                    trace=trace,
                )
                quarter_records[quarter] = quarter_record
                _merge_metric_sets(annual_totals, (threshold_totals, band_totals))
                total_products += int(quarter_record["products_with_positives"])
                total_positives += int(quarter_record["positive_edges"])
                total_candidates += int(quarter_record["candidate_pairs"])
                _add_snapshot_to_history(history, snapshot)
            population = {
                "products_with_positives": total_products,
                "positive_edges": total_positives,
                "candidate_pairs": total_candidates,
            }
            if population != VALIDATION_POPULATION:
                raise ValueError(
                    f"validation population differs from fixed protocol: {population}"
                )
            validation_result: dict[str, object] = {
                "status": "complete",
                "duration_epochs": epochs,
                "fit": fit_record,
                "quarters": quarter_records,
                "validation": _metric_report(*annual_totals),
                "population": population,
            }
            budget.write_json(f"{fit_dir}/fit_result.json", validation_result)
            all_fit_results[str(epochs)] = validation_result
        if validation_epochs == VALIDATION_EPOCHS:
            phase_result = {
                "status": "complete",
                "phase": "validation_2023",
                "grid_epochs": list(VALIDATION_EPOCHS),
                "selection_epochs": list(SELECTION_EPOCHS),
                "fits": all_fit_results,
                "population": VALIDATION_POPULATION,
            }
        else:
            phase_result = {
                "status": "complete",
                "phase": "validation_2023",
                "validation_epochs": list(validation_epochs),
                "fits": all_fit_results,
                "population": VALIDATION_POPULATION,
            }
        budget.write_json("validation_summary.json", phase_result)
        trace.write({"event": "phase_completed", "phase": "validation_2023"})
        trace.flush()
    finally:
        trace.close()


def _test_worker(
    input_path: str,
    phase_path: str,
    phase_limit_bytes: int,
    year: int,
    selected_epochs: int,
    aggregation: str = "mean",
) -> None:
    root = Path(phase_path)
    budget = _OutputBudget(root, phase_limit_bytes)
    trace = _GzipJsonl(budget, "trace.jsonl.gz")
    try:
        _prepared, snapshots = _load_prepared_snapshots(Path(input_path))
        snapshot_by_quarter = {snapshot.quarter: snapshot for snapshot in snapshots}
        first_by_quarter = _first_edges(snapshots)
        refit_quarter = f"{year}Q1"
        history = _history_through(snapshots, refit_quarter)
        fit_dir = f"fit_epochs_{selected_epochs:02d}"
        ranker, fit_record = _fit_one(
            history, selected_epochs, budget, fit_dir, trace, aggregation
        )
        annual_totals = _metric_accumulators()
        quarter_records: dict[str, object] = {}
        total_products = total_positives = total_candidates = 0
        for quarter in (f"{year}Q{index}" for index in range(1, 5)):
            snapshot = snapshot_by_quarter[quarter]
            quarter_record, threshold_totals, band_totals = _evaluate_quarter(
                snapshot=snapshot,
                first=first_by_quarter[quarter],
                history=history,
                ranker=ranker,
                budget=budget,
                artifact_prefix=f"{quarter}",
                trace=trace,
            )
            quarter_records[quarter] = quarter_record
            _merge_metric_sets(annual_totals, (threshold_totals, band_totals))
            total_products += int(quarter_record["products_with_positives"])
            total_positives += int(quarter_record["positive_edges"])
            total_candidates += int(quarter_record["candidate_pairs"])
            _add_snapshot_to_history(history, snapshot)
            budget.write_json(
                "completed_quarters.json",
                {"status": "incomplete_until_year_complete", "quarters": list(quarter_records)},
            )
        annual = _metric_report(*annual_totals)
        phase_result: dict[str, object] = {
            "status": "complete",
            "year": year,
            "refit_quarter": refit_quarter,
            "duration_epochs": selected_epochs,
            "fit": fit_record,
            "quarters": quarter_records,
            "annual": annual,
            "population": {
                "products_with_positives": total_products,
                "positive_edges": total_positives,
                "candidate_pairs": total_candidates,
            },
        }
        budget.write_json("phase_summary.json", phase_result)
        budget.write_json(
            "completed_quarters.json",
            {"status": "complete", "quarters": list(quarter_records)},
        )
        trace.write({"event": "phase_completed", "phase": f"test_{year}"})
        trace.flush()
    finally:
        trace.close()


def _worker_entry(
    worker_kind: str,
    input_path: str,
    phase_path: str,
    phase_limit_bytes: int,
    year: int | None = None,
    selected_epochs: int | None = None,
    aggregation: str = "mean",
    validation_epochs: tuple[int, ...] = VALIDATION_EPOCHS,
) -> None:
    phase_root = Path(phase_path)
    started = time.monotonic()
    started_cpu = time.process_time()
    _write_json(
        phase_root / "worker_status.json",
        {"status": "running", "worker_kind": worker_kind, "pid": os.getpid()},
    )
    try:
        if worker_kind == "validation":
            _validation_worker(
                input_path, phase_path, phase_limit_bytes, validation_epochs, aggregation
            )
        elif worker_kind == "test" and year is not None and selected_epochs is not None:
            _test_worker(
                input_path, phase_path, phase_limit_bytes, year, selected_epochs, aggregation
            )
        else:
            raise ValueError("invalid phase worker configuration")
    except BaseException as exc:
        _write_json(
            phase_root / "worker_error.json",
            {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
        )
        _write_json(
            phase_root / "worker_status.json",
            {
                "status": "incomplete",
                "worker_kind": worker_kind,
                "pid": os.getpid(),
                "wall_seconds": time.monotonic() - started,
                "cpu_seconds": time.process_time() - started_cpu,
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        raise
    _write_json(
        phase_root / "worker_status.json",
        {
            "status": "complete",
            "worker_kind": worker_kind,
            "pid": os.getpid(),
            "wall_seconds": time.monotonic() - started,
            "cpu_seconds": time.process_time() - started_cpu,
            "peak_rss_bytes": _process_peak_rss_bytes(os.getpid()),
        },
    )


def _process_memory_bytes(pid: int) -> tuple[int, int]:
    rss = high_water = 0
    try:
        with Path(f"/proc/{pid}/status").open(encoding="utf-8") as source:
            for line in source:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) * 1024
                elif line.startswith("VmHWM:"):
                    high_water = int(line.split()[1]) * 1024
    except (FileNotFoundError, ProcessLookupError):
        pass
    return rss, high_water


def _process_cpu_seconds(pid: int) -> float:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        fields = stat[stat.rfind(")") + 2 :].split()
        ticks = int(fields[11]) + int(fields[12])
        return ticks / os.sysconf("SC_CLK_TCK")
    except (FileNotFoundError, ProcessLookupError):
        return 0.0


def _process_peak_rss_bytes(pid: int) -> int:
    _rss, high_water = _process_memory_bytes(pid)
    if high_water:
        return high_water
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(usage if sys.platform == "darwin" else usage * 1024)


def _directory_bytes(path: Path) -> int:
    total = 0
    for root, _directories, files in os.walk(path):
        for filename in files:
            try:
                total += (Path(root) / filename).stat().st_size
            except FileNotFoundError:
                continue
    return total

def _terminate_process(process: multiprocessing.Process) -> None:
    process.terminate()
    process.join(timeout=2.0)
    if process.is_alive():
        process.kill()
        process.join()


def _supervise_worker(
    target: Callable[..., None],
    args: tuple[object, ...],
    phase_dir: Path,
    *,
    timeout_seconds: float,
    max_rss_bytes: int,
    max_output_bytes: int,
) -> dict[str, object]:
    if not sys.platform.startswith("linux") or not Path("/proc/self/status").exists():
        raise RuntimeError("effective aggregate RSS enforcement requires Linux /proc")
    phase_dir.mkdir(parents=True, exist_ok=True)
    _limit_library_threads()
    process = multiprocessing.get_context("fork").Process(target=target, args=args)
    controller_rss, _controller_hwm = _process_memory_bytes(os.getpid())
    started = time.monotonic()
    process.start()
    worker_pid = process.pid
    peak_aggregate_rss = controller_rss
    sampled_worker_cpu = 0.0
    stop_reason: str | None = None
    output_bytes = 0
    try:
        while process.is_alive():
            worker_rss, worker_hwm = _process_memory_bytes(int(worker_pid))
            controller_now, _ = _process_memory_bytes(os.getpid())
            peak_aggregate_rss = max(
                peak_aggregate_rss,
                worker_hwm + controller_now,
                worker_rss + controller_now,
            )
            sampled_worker_cpu = max(
                sampled_worker_cpu, _process_cpu_seconds(int(worker_pid))
            )
            output_bytes = _directory_bytes(phase_dir)
            if peak_aggregate_rss > max_rss_bytes:
                stop_reason = "rss_limit"
            elif output_bytes > max_output_bytes:
                stop_reason = "output_limit"
            elif time.monotonic() - started >= timeout_seconds:
                stop_reason = "timeout"
            if stop_reason is not None:
                _terminate_process(process)
                break
            process.join(timeout=_POLL_SECONDS)
        process.join()
    except BaseException:
        if process.is_alive():
            _terminate_process(process)
        raise
    wall_seconds = time.monotonic() - started
    if process.exitcode == 0:
        worker_cpu = sampled_worker_cpu
        status_path = phase_dir / "worker_status.json"
        if status_path.exists():
            try:
                status_value = json.loads(status_path.read_text(encoding="utf-8"))
                worker_cpu = max(worker_cpu, float(status_value.get("cpu_seconds", 0.0)))
                peak_aggregate_rss = max(
                    peak_aggregate_rss,
                    int(status_value.get("peak_rss_bytes", 0)) + controller_rss,
                )
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
    else:
        worker_cpu = sampled_worker_cpu
    output_bytes = _directory_bytes(phase_dir)
    if stop_reason is None:
        if peak_aggregate_rss > max_rss_bytes:
            stop_reason = "rss_limit"
        elif output_bytes > max_output_bytes:
            stop_reason = "output_limit"
        elif wall_seconds >= timeout_seconds:
            stop_reason = "timeout"
    state = "complete" if process.exitcode == 0 and stop_reason is None else "incomplete"
    supervisor: dict[str, object] = {
        "status": state,
        "reason": stop_reason or (None if process.exitcode == 0 else "worker_error"),
        "pid": worker_pid,
        "exit_code": process.exitcode,
        "wall_seconds": wall_seconds,
        "worker_cpu_seconds": worker_cpu,
        "peak_aggregate_rss_bytes": peak_aggregate_rss,
        "phase_output_bytes": output_bytes,
        "limits": {
            "timeout_seconds": timeout_seconds,
            "aggregate_rss_bytes": max_rss_bytes,
            "output_bytes": max_output_bytes,
        },
    }
    _write_json(phase_dir / "supervisor_status.json", supervisor)
    if state != "complete":
        reason = stop_reason or f"worker exited with status {process.exitcode}"
        raise PhaseExecutionError(reason, supervisor)
    return supervisor


def _select_validation_duration(fits: Mapping[str | int, object]) -> dict[str, object]:
    normalized: dict[int, Mapping[str, object]] = {}
    for key, value in fits.items():
        try:
            epochs = int(key)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid validation grid key {key!r}") from exc
        if epochs in normalized or not isinstance(value, Mapping):
            raise ValueError("validation grid contains duplicate or malformed fit results")
        normalized[epochs] = value
    if set(normalized) != set(VALIDATION_EPOCHS):
        raise ValueError("duration selection requires the complete 0/3/10/30 validation grid")
    metrics: dict[int, float] = {}
    for epochs in VALIDATION_EPOCHS:
        result = normalized[epochs]
        if result.get("status") != "complete":
            raise ValueError(f"validation fit {epochs} is incomplete")
        validation = result.get("validation")
        if not isinstance(validation, Mapping):
            raise ValueError(f"validation fit {epochs} has no complete validation metrics")
        thresholds = validation.get("thresholds")
        if not isinstance(thresholds, Mapping) or not isinstance(thresholds.get("1"), Mapping):
            raise ValueError(f"validation fit {epochs} has no support-1 metrics")
        recall = thresholds["1"].get("recall_at_10")
        if isinstance(recall, bool) or not isinstance(recall, (int, float)) or not math.isfinite(float(recall)) or not 0.0 <= float(recall) <= 1.0:
            raise ValueError(f"validation fit {epochs} has an invalid micro recall@10")
        metrics[epochs] = float(recall)
    selected = min(SELECTION_EPOCHS, key=lambda epochs: (-metrics[epochs], epochs))
    return {
        "status": "locked",
        "selected_epochs": selected,
        "validation_micro_recall_at_10": metrics[selected],
        "selection_rule": "maximum validation micro recall@10 among 3/10/30; exact tie selects fewer epochs",
        "eligible_validation_scores": {str(epochs): metrics[epochs] for epochs in SELECTION_EPOCHS},
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_scores_consulted": False,
    }


def _assert_new_output(output_dir: Path, repo_root: Path) -> None:
    destination = output_dir.resolve()
    required_parent = (repo_root / "results" / "generated" / "consolidation-post-RC1").resolve()
    if destination.parent != required_parent:
        raise ValueError(f"output-dir must be a new run directly under {required_parent}")
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing result directory: {destination}")
    frozen = (repo_root / "results" / "generated" / "manuscript-rc1").resolve()
    if destination == frozen or frozen in destination.parents:
        raise ValueError(f"refusing to write within frozen RC1 results: {destination}")


def _source_hashes(repo_root: Path) -> dict[str, str]:
    paths = {
        "runner": Path(__file__).resolve(),
        "cli": repo_root / "scripts" / "run_maude_duration_diagnostic.py",
        "evaluation": repo_root / "healthgraphbench" / "tasks" / "maude" / "evaluate.py",
        "models": repo_root / "healthgraphbench" / "tasks" / "maude" / "models.py",
        "data": repo_root / "healthgraphbench" / "tasks" / "maude" / "data.py",
    }
    return {name: _sha256_file(path) for name, path in paths.items()}


def _environment() -> dict[str, object]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "thread_environment": {
            name: os.environ.get(name)
            for name in _THREAD_ENV_VARIABLES
        },
        "supervisor": "one controller process plus one serial worker process per phase",
    }


def _add_phase_costs(costs: dict[str, float | int], supervisor: Mapping[str, object]) -> None:
    costs["phase_wall_seconds"] = float(costs["phase_wall_seconds"]) + float(
        supervisor.get("wall_seconds", 0.0)
    )
    costs["worker_cpu_seconds"] = float(costs["worker_cpu_seconds"]) + float(
        supervisor.get("worker_cpu_seconds", 0.0)
    )
    costs["peak_aggregate_rss_bytes"] = max(
        int(costs["peak_aggregate_rss_bytes"]),
        int(supervisor.get("peak_aggregate_rss_bytes", 0)),
    )


def _combined_test_metrics(test_summaries: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    years = sorted(test_summaries)
    if not years:
        raise ValueError("no completed test-year summaries to aggregate")
    first_annual = test_summaries[years[0]]["annual"]
    if not isinstance(first_annual, Mapping) or not isinstance(first_annual.get("accumulators"), Mapping):
        raise ValueError("annual test metrics lack mergeable denominators")
    merged_accumulators: dict[str, dict[str, dict[str, object]]] = {
        "thresholds": {},
        "support_bands": {},
    }
    for section in ("thresholds", "support_bands"):
        keys = first_annual["accumulators"][section]
        if not isinstance(keys, Mapping):
            raise ValueError("malformed annual test accumulator section")
        for key in keys:
            current: Mapping[str, object] | None = None
            for year in years:
                annual = test_summaries[year]["annual"]
                if not isinstance(annual, Mapping) or not isinstance(annual.get("accumulators"), Mapping):
                    raise ValueError(f"malformed annual metrics for {year}")
                values = annual["accumulators"][section]
                if not isinstance(values, Mapping) or not isinstance(values.get(key), Mapping):
                    raise ValueError(f"missing annual accumulator for {year}/{section}/{key}")
                current = dict(values[key]) if current is None else _merge_accumulator_payloads(current, values[key])
            if current is None:
                raise ValueError("no annual metric rows to aggregate")
            merged_accumulators[section][str(key)] = dict(current)
    thresholds = {
        key: _accumulator_from_payload(payload).as_dict()
        for key, payload in merged_accumulators["thresholds"].items()
    }
    bands = {
        key: _accumulator_from_payload(payload).as_dict()
        for key, payload in merged_accumulators["support_bands"].items()
    }
    totals = {
        "products_with_positives": 0,
        "positive_edges": 0,
        "candidate_pairs": 0,
    }
    for year in years:
        population = test_summaries[year].get("population")
        if isinstance(population, Mapping):
            for key in totals:
                totals[key] += int(population[key])
    return {
        "years": years,
        "thresholds": thresholds,
        "support_bands": bands,
        "population": totals,
        "aggregation": "sum numerators and denominators across 2024Q1–2025Q4; no mean of annual recalls",
        "accumulators": merged_accumulators,
    }


def run_diagnostic(
    *,
    prepared_input: Path,
    output_dir: Path,
    protocol: Path,
    protocol_sha256: str,
    validation_timeout_seconds: float = MAX_TIMEOUT_SECONDS,
    test_timeout_seconds: float = MAX_TIMEOUT_SECONDS,
    max_rss_mib: int = 512,
    max_output_mib: int = 512,
) -> dict[str, object]:
    repo_root = Path(__file__).resolve().parents[3]
    prepared_input = prepared_input.resolve(strict=True)
    protocol = protocol.resolve(strict=True)
    if not prepared_input.is_file() or not protocol.is_file():
        raise ValueError("prepared-input and protocol must be files")
    expected_protocol_hash = protocol_sha256.lower()
    actual_protocol_hash = _sha256_file(protocol)
    if actual_protocol_hash != expected_protocol_hash:
        raise ValueError(
            f"protocol SHA-256 mismatch: expected {expected_protocol_hash}, found {actual_protocol_hash}"
        )
    if not 0 < validation_timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"validation timeout must be in (0, {MAX_TIMEOUT_SECONDS}] seconds")
    if not 0 < test_timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"test timeout must be in (0, {MAX_TIMEOUT_SECONDS}] seconds")
    if not 0 < max_rss_mib <= MAX_RSS_BYTES // (1024 * 1024):
        raise ValueError("max RSS must be in (0, 512] MiB")
    if not 0 < max_output_mib <= MAX_OUTPUT_BYTES // (1024 * 1024):
        raise ValueError("max output must be in (0, 512] MiB")
    _assert_new_output(output_dir, repo_root)
    output_dir.mkdir(parents=True, exist_ok=False)
    _limit_library_threads()
    run_started_monotonic = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    max_rss_bytes = max_rss_mib * 1024 * 1024
    max_output_bytes = max_output_mib * 1024 * 1024
    code_hashes = _source_hashes(repo_root)
    run_manifest: dict[str, object] = {
        "status": "running",
        "started_at_utc": started_at,
        "prepared_input": {"path": str(prepared_input), "sha256": _sha256_file(prepared_input)},
        "protocol": {
            "path": str(protocol),
            "expected_sha256": expected_protocol_hash,
            "sha256": actual_protocol_hash,
        },
        "code_sha256": code_hashes,
        "limits": {
            "validation_timeout_seconds": validation_timeout_seconds,
            "test_timeout_seconds_per_phase": test_timeout_seconds,
            "aggregate_rss_bytes_per_phase": max_rss_bytes,
            "new_output_bytes_per_phase": max_output_bytes,
            "automatic_retries": 0,
            "thread_count_per_library": 1,
        },
        "enforcement": {
            "platform": "Linux /proc",
            "poll_interval_seconds": _POLL_SECONDS,
            "aggregate_rss": "controller current RSS plus worker VmHWM/current RSS; worker terminated on limit",
            "worker_termination": "SIGTERM, then SIGKILL after 2 seconds if still alive",
            "phase_output": "worker byte budget reserves 64 KiB for status; controller also polls phase-directory bytes",
        },
        "formats": {
            "manifests_and_metrics": "UTF-8 JSON",
            "epoch_logs_and_candidate_tables": "gzip-compressed UTF-8 JSON Lines",
            "checkpoints": "gzip-compressed JSON",
            "trace": "gzip-compressed UTF-8 JSON Lines",
        },
        "environment": _environment(),
        "phases": {"validation_2023": {"status": "pending"}, "test_2024": {"status": "pending"}, "test_2025": {"status": "pending"}},
        "interpretation": "exploratory re-analysis of previously consulted historical tests; not independent confirmation",
    }
    costs: dict[str, float | int] = {
        "wall_seconds": 0.0,
        "phase_wall_seconds": 0.0,
        "worker_cpu_seconds": 0.0,
        "peak_aggregate_rss_bytes": 0,
    }
    _write_json(output_dir / "run_manifest.json", run_manifest)
    try:
        validation_dir = output_dir / "validation_2023"
        validation_dir.mkdir()
        run_manifest["phases"]["validation_2023"] = {"status": "running"}  # type: ignore[index]
        _write_json(output_dir / "run_manifest.json", run_manifest)
        try:
            validation_supervisor = _supervise_worker(
                _worker_entry,
                ("validation", str(prepared_input), str(validation_dir), max_output_bytes),
                validation_dir,
                timeout_seconds=validation_timeout_seconds,
                max_rss_bytes=max_rss_bytes,
                max_output_bytes=max_output_bytes,
            )
        except PhaseExecutionError as exc:
            _add_phase_costs(costs, exc.supervisor)
            run_manifest["phases"]["validation_2023"] = exc.supervisor  # type: ignore[index]
            raise
        _add_phase_costs(costs, validation_supervisor)
        run_manifest["phases"]["validation_2023"] = validation_supervisor  # type: ignore[index]
        _write_json(output_dir / "run_manifest.json", run_manifest)
        validation_summary = json.loads(
            (validation_dir / "validation_summary.json").read_text(encoding="utf-8")
        )
        if validation_summary.get("status") != "complete":
            raise ValueError("validation worker did not finish the complete duration grid")
        fits = validation_summary.get("fits")
        if not isinstance(fits, dict):
            raise ValueError("validation worker result omitted the duration grid")
        selection = _select_validation_duration(fits)
        _write_json(output_dir / "selection.json", selection)
        run_manifest["selection"] = {
            "artifact": "selection.json",
            "locked_at_utc": selection["locked_at_utc"],
            "selected_epochs": selection["selected_epochs"],
        }
        _write_json(output_dir / "run_manifest.json", run_manifest)
        test_summaries: dict[str, Mapping[str, object]] = {}
        selected_epochs = int(selection["selected_epochs"])
        for year in (2024, 2025):
            phase_name = f"test_{year}"
            phase_dir = output_dir / phase_name
            phase_dir.mkdir()
            run_manifest["phases"][phase_name] = {"status": "running"}  # type: ignore[index]
            _write_json(output_dir / "run_manifest.json", run_manifest)
            try:
                supervisor = _supervise_worker(
                    _worker_entry,
                    ("test", str(prepared_input), str(phase_dir), max_output_bytes, year, selected_epochs),
                    phase_dir,
                    timeout_seconds=test_timeout_seconds,
                    max_rss_bytes=max_rss_bytes,
                    max_output_bytes=max_output_bytes,
                )
            except PhaseExecutionError as exc:
                _add_phase_costs(costs, exc.supervisor)
                run_manifest["phases"][phase_name] = exc.supervisor  # type: ignore[index]
                raise
            _add_phase_costs(costs, supervisor)
            run_manifest["phases"][phase_name] = supervisor  # type: ignore[index]
            _write_json(output_dir / "run_manifest.json", run_manifest)
            summary = json.loads((phase_dir / "phase_summary.json").read_text(encoding="utf-8"))
            if summary.get("status") != "complete" or summary.get("year") != year:
                raise ValueError(f"test worker did not finish the complete {year} cohort")
            test_summaries[str(year)] = summary
        aggregate = _combined_test_metrics(test_summaries)
        _write_json(output_dir / "test_aggregate_2024_2025.json", aggregate)
        costs["wall_seconds"] = time.monotonic() - run_started_monotonic
        report: dict[str, object] = {
            "status": "complete",
            "started_at_utc": started_at,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "selection": selection,
            "validation": {
                "status": "complete",
                "summary": "validation_2023/validation_summary.json",
                "micro_recall_at_10_by_epochs": {
                    str(epochs): fits[str(epochs)]["validation"]["thresholds"]["1"]["recall_at_10"]
                    for epochs in VALIDATION_EPOCHS
                },
            },
            "tests": {
                str(year): {
                    "status": "complete",
                    "summary": f"test_{year}/phase_summary.json",
                    "annual_metrics": test_summaries[str(year)]["annual"],
                    "population": test_summaries[str(year)]["population"],
                }
                for year in (2024, 2025)
            },
            "combined_test_2024_2025": "test_aggregate_2024_2025.json",
            "costs": costs,
            "limitations": [
                "prepared snapshots expose only quarter, product report support, and unique product-problem edges",
                "no manufacturer labels, edge multiplicities, or missing DataBundle fields were reconstructed",
                "dates use prepared MAUDE DATE_RECEIVED; this does not establish public historical availability",
                "2023–2025 periods were previously consulted; this is exploratory, not independent confirmation",
                "controller CPU and storage I/O are not attributed to worker CPU time",
            ],
        }
        _write_json(output_dir / "report.json", report)
        run_manifest["status"] = "complete"
        run_manifest["finished_at_utc"] = report["finished_at_utc"]
        run_manifest["costs"] = costs
        _write_json(output_dir / "run_manifest.json", run_manifest)
        return report
    except BaseException as exc:
        costs["wall_seconds"] = time.monotonic() - run_started_monotonic
        run_manifest["status"] = "incomplete"
        run_manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        run_manifest["error"] = f"{type(exc).__name__}: {exc}"
        run_manifest["costs"] = costs
        for phase in run_manifest["phases"].values():
            if phase.get("status") == "running":
                phase.update(status="incomplete", reason=run_manifest["error"])
        _write_json(output_dir / "run_manifest.json", run_manifest)
        _write_json(
            output_dir / "report.json",
            {
                "status": "incomplete",
                "started_at_utc": started_at,
                "finished_at_utc": run_manifest["finished_at_utc"],
                "error": run_manifest["error"],
                "phases": run_manifest["phases"],
                "selection": run_manifest.get("selection"),
                "costs": costs,
                "interpretation": "no metrics from a truncated phase and no selection from an incomplete validation grid",
            },
        )
        raise


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--validation-timeout-seconds", type=float, default=MAX_TIMEOUT_SECONDS)
    parser.add_argument("--test-timeout-seconds", type=float, default=MAX_TIMEOUT_SECONDS)
    parser.add_argument("--max-rss-mib", type=int, default=512)
    parser.add_argument("--max-output-mib", type=int, default=512)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = run_diagnostic(
            prepared_input=args.prepared_input,
            output_dir=args.output_dir,
            protocol=args.protocol,
            protocol_sha256=args.protocol_sha256,
            validation_timeout_seconds=args.validation_timeout_seconds,
            test_timeout_seconds=args.test_timeout_seconds,
            max_rss_mib=args.max_rss_mib,
            max_output_mib=args.max_output_mib,
        )
    except Exception as exc:
        print(f"MAUDE duration diagnostic failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {args.output_dir / 'report.json'}")
    print(f"selected GraphSAGE duration: {report['selection']['selected_epochs']} epochs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
