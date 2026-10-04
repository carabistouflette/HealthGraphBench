"""RC3.1 binary-history Part D comparisons; only the requested target is ranked.

Neighbor votes use a single pre-target top-k list per provider. GraphSAGE maps
providers/drugs directly onto the faithful Q2 bipartite numeric backend, without
changing its objective, sampling, gradients or inference. Selected Q2 BPR state
is consumed, never fitted here. All workload rows, including zeros, are retained.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..data import sha256_file
from ..q2.partd import _primary_metric, _save_all_candidate_scores
from ..q2.maude_backend import (
    fit_graphsage, load_graphsage_checkpoint,
    save_graphsage_checkpoint,
)
from ..tasks.maude.models import History
from ..tasks.partd.task import PartDHistoryView, PartDTask

NEIGHBOR_KS = (8, 16, 32, 50, 100, 200)
NEIGHBOR_FAMILIES = ("common_count", "jaccard", "cosine")
GRAPH_SAGE_GRID = tuple(
    {"dimension": dimension, "regularization": regularization}
    for dimension in (16, 32) for regularization in (0.0005, 0.000005, 0.0)
)
BPR_CONFIGURATION = {
    "dimension": 32, "learning_rate": 0.03,
    "regularization": 0.001, "negative_samples": 5,
}
SEEDS = (103, 211, 307)
TOP_RECOMMENDATIONS = 100


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _view(task: PartDTask, year: int) -> PartDHistoryView:
    if year not in (2023, 2024):
        raise ValueError("Part D supports only target years 2023 and 2024")
    return task.history_view("validation" if year == 2023 else "test")


def binary_history(view: PartDHistoryView) -> tuple[tuple[str, ...], tuple[str, ...], Any]:
    """CSR incidence has one integer per distinct provider-drug link, not claims."""
    from scipy.sparse import csr_matrix
    providers, drugs = view.providers, view.drugs
    drug_index = {drug: index for index, drug in enumerate(drugs)}
    indices: list[int] = []
    offsets = [0]
    for provider in providers:
        indices.extend(sorted(drug_index[drug] for drug in view.provider_history(provider)))
        offsets.append(len(indices))
    matrix = csr_matrix((np.ones(len(indices), dtype=np.int32), np.asarray(indices, dtype=np.int32),
                         np.asarray(offsets, dtype=np.int32)), shape=(len(providers), len(drugs)))
    return providers, drugs, matrix


class HistoricalNeighbors:
    """Fixed positive-similarity, self-free neighbor lists with lexical NPI ties."""

    def __init__(self, view: PartDHistoryView) -> None:
        self.view = view
        self.providers, self.drugs, self.incidence = binary_history(view)
        self.provider_index = {provider: index for index, provider in enumerate(self.providers)}
        self.drug_index = {drug: index for index, drug in enumerate(self.drugs)}
        self.degrees = np.diff(self.incidence.indptr)
        self.common = (self.incidence @ self.incidence.T).tocsr()
        self._tables: dict[tuple[str, int], dict[str, tuple[tuple[str, float], ...]]] = {}

    def table(self, family: str, k: int) -> dict[str, tuple[tuple[str, float], ...]]:
        if family not in NEIGHBOR_FAMILIES or k < 1:
            raise ValueError("unknown neighbor similarity or nonpositive k")
        key = (family, k)
        if key in self._tables:
            return self._tables[key]
        result = {}
        for index, provider in enumerate(self.providers):
            start, end = self.common.indptr[index:index + 2]
            peers = []
            for other, common in zip(self.common.indices[start:end], self.common.data[start:end], strict=True):
                if other == index or common <= 0:
                    continue
                if family == "common_count":
                    similarity = float(common)
                elif family == "jaccard":
                    similarity = float(common) / (int(self.degrees[index]) + int(self.degrees[other]) - int(common))
                else:
                    similarity = float(common) / math.sqrt(int(self.degrees[index]) * int(self.degrees[other]))
                peers.append((self.providers[other], similarity))
            peers.sort(key=lambda pair: (-pair[1], pair[0]))
            result[provider] = tuple(peers[:k])
        self._tables[key] = result
        return result

    def scorer(self, family: str, k: int):
        table = self.table(family, k)
        def score(view: PartDHistoryView, npi: str, candidates: tuple[str, ...]) -> Mapping[str, float]:
            if view.target_year != self.view.target_year:
                raise ValueError("neighbor state used at a different temporal cutoff")
            votes: dict[str, float] = {}
            for peer, weight in table.get(npi, ()):
                for drug in sorted(self.view.provider_history(peer)):
                    votes[drug] = votes.get(drug, 0.0) + weight
            return {drug: votes.get(drug, 0.0) for drug in candidates}
        return score

    def fixed_support(self, npi: str) -> Counter[str]:
        return Counter(drug for peer, _ in self.table("cosine", 50).get(npi, ())
                       for drug in self.view.provider_history(peer))

    def save(self, path: Path, family: str, k: int) -> None:
        table = self.table(family, k)
        indices = np.full((len(self.providers), k), -1, dtype=np.int32)
        weights = np.zeros((len(self.providers), k), dtype=np.float64)
        for row, provider in enumerate(self.providers):
            for column, (peer, weight) in enumerate(table[provider]):
                indices[row, column] = self.provider_index[peer]
                weights[row, column] = weight
        np.savez_compressed(path, providers=np.asarray(self.providers), drugs=np.asarray(self.drugs),
                            incidence_indices=self.incidence.indices, incidence_offsets=self.incidence.indptr,
                            neighbor_indices=indices, neighbor_weights=weights,
                            family=np.asarray(family), k=np.asarray(k), year=np.asarray(self.view.target_year))


def _graph_history(view: PartDHistoryView) -> History:
    """Only the binary provider-drug graph is exposed to the MAUDE backend."""
    history = History.empty()
    history.product_problems = {provider: set(drugs) for provider, drugs in view.provider_drugs.items() if drugs}
    history.problem_products = {drug: set(providers) for drug, providers in view.drug_providers.items()}
    return history


def _baseline(view: PartDHistoryView, family: str):
    specialties: dict[str, Counter[str]] = {}
    for provider in view.providers:
        specialty = view.prior_specialty(provider)
        if specialty is not None:
            specialties.setdefault(specialty, Counter()).update(view.provider_history(provider))
    def score(current: PartDHistoryView, npi: str, candidates: tuple[str, ...]) -> Mapping[str, float]:
        if current.target_year != view.target_year:
            raise ValueError("baseline state used at a different temporal cutoff")
        specialty = view.prior_specialty(npi)
        if family == "global_popularity" or specialty is None:
            return {drug: float(view.global_support(drug)) for drug in candidates}
        return {drug: float(specialties.get(specialty, {}).get(drug, 0)) for drug in candidates}
    state = {"target_year": view.target_year, "prior_years": view.prior_years,
             "global_support": {drug: view.global_support(drug) for drug in view.drugs},
             "latest_specialties": dict(view.latest_specialties), "specialty_support": specialties}
    return score, state


def _validate_request(family: str, configuration: dict, seed: int | None, fixed: dict) -> None:
    if family in NEIGHBOR_FAMILIES:
        if configuration not in [{"k": k} for k in NEIGHBOR_KS] or seed is not None:
            raise ValueError("neighbors require a published k and seed=None")
    elif family in ("global_popularity", "specialty_popularity"):
        if configuration or seed is not None:
            raise ValueError("fixed baselines require empty configuration and seed=None")
    elif family == "graphsage":
        if configuration not in GRAPH_SAGE_GRID or seed not in SEEDS:
            raise ValueError("GraphSAGE requires the published six-grid and seed")
        expected = {"epochs": 30, "learning_rate": 0.02, "fanout": 8, "aggregation": "mean"}
        if any(fixed.get(key, value) != value for key, value in expected.items()):
            raise ValueError("GraphSAGE fixed settings differ from the approved protocol")
    elif family == "bpr_reuse":
        if configuration != BPR_CONFIGURATION or seed not in SEEDS or not fixed.get("reuse_phase_path"):
            raise ValueError("BPR reuse requires selected configuration, seed and explicit reuse_phase_path")
    else:
        raise ValueError(f"unknown Part D RC3.1 family {family!r}")


def consume_reused_bpr(task: PartDTask, year: int, phase_path: Path, seed: int,
                       prepared_path: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any], Path]:
    """Validate the existing cohort/history/targets/candidate mapping, then reuse scores.

    This is artifact compatibility checking, not a rerun of the old scientific audit.
    The source phase is explicit; no search for a favorable seed/configuration occurs.
    """
    phase_path = Path(phase_path)
    source_result = json.loads((phase_path / "result.json").read_text(encoding="utf-8"))
    if (source_result.get("family") != "bpr" or source_result.get("target_year") != year
            or source_result.get("configuration") != BPR_CONFIGURATION or source_result.get("seed") != seed):
        raise ValueError("reused BPR phase configuration/year/seed mismatch")
    fit = source_result["fit"]
    if any(fit.get(key) != value for key, value in {"epochs": 30, "specialty_weight": 0.35}.items()):
        raise ValueError("reused BPR fixed settings mismatch")
    prepared_path = Path(prepared_path) if prepared_path is not None else phase_path.parents[4] / "phases/prepare_raw/prepared"
    source_task = PartDTask.from_prepared_input(prepared_path)
    view, source_view = _view(task, year), _view(source_task, year)
    if task.cohorts[year] != source_task.cohorts[year] or view != source_view:
        raise ValueError("reused BPR cohort or pre-target history mismatch")
    checkpoint = phase_path / "model/checkpoint.npz"
    if sha256_file(checkpoint) != fit["checkpoint_sha256"]:
        raise ValueError("reused BPR checkpoint hash mismatch")
    with np.load(checkpoint, allow_pickle=False) as raw:
        if tuple(raw["providers"].tolist()) != view.providers or tuple(raw["drugs"].tolist()) != view.drugs:
            raise ValueError("reused BPR checkpoint provider/drug mapping mismatch")
        parameter_count = sum(int(raw[key].size) for key in
                              ("provider_embeddings", "drug_embeddings", "specialty_embeddings"))
    score_path = phase_path / "all_candidate_scores.npz"
    if sha256_file(score_path) != source_result["candidate_score_table"]["sha256"]:
        raise ValueError("reused BPR candidate score hash mismatch")
    with np.load(score_path, allow_pickle=False) as raw:
        providers = tuple(raw["provider_ids"].tolist())
        drugs = tuple(raw["drug_ids"].tolist())
        offsets = raw["provider_candidate_offsets"]
        indices = raw["candidate_drug_indices"]
        scores = raw["candidate_scores"]
        if (providers != tuple(sorted(task.cohorts[year])) or drugs != view.drugs
                or not np.array_equal(raw["drug_global_support"], [view.global_support(drug) for drug in drugs])):
            raise ValueError("reused BPR candidate/cohort mapping mismatch")
        if (offsets.shape != (len(providers) + 1,) or offsets[0] != 0 or offsets[-1] != len(indices)
                or np.any(np.diff(offsets) < 0) or len(scores) != len(indices)
                or np.any(indices < 0) or np.any(indices >= len(drugs)) or not np.all(np.isfinite(scores))):
            raise ValueError("invalid reused BPR candidate score encoding")
        provider_index = {provider: index for index, provider in enumerate(providers)}
        def scorer(current, npi, candidates):
            index = provider_index[npi]
            start, end = offsets[index:index + 2]
            names = tuple(drugs[int(value)] for value in indices[start:end])
            if names != candidates:
                raise ValueError("reused BPR exact candidate mapping mismatch")
            return dict(zip(names, (float(value) for value in scores[start:end]), strict=True))
        rows = task._rank_target(year, scorer, retain_candidate_scores=True)
    prediction_path = phase_path / "predictions.jsonl"
    if sha256_file(prediction_path) != source_result["prediction_file_sha256"]:
        raise ValueError("reused BPR prediction hash mismatch")
    old_rows = [json.loads(line) for line in prediction_path.read_text(encoding="utf-8").splitlines() if line]
    if len(old_rows) != len(rows):
        raise ValueError("reused BPR target row count mismatch")
    for old, current in zip(old_rows, rows, strict=True):
        for key in ("npi", "year", "eligible", "candidate_count", "positive_count", "positives", "positive_ranks", "recommendations"):
            if old.get(key) != current[key]:
                raise ValueError(f"reused BPR target/ranking mismatch: {key}")
    before, after = fit["loss_before"]["sampled_objective"], fit["loss_after"]["sampled_objective"]
    drop = (before - after) / before if before > 0 else 0.0
    diagnostics = {**fit, "reused": True, "source_phase": str(phase_path),
                   "source_result_sha256": sha256_file(phase_path / "result.json"),
                   "source_prepared": str(prepared_path), "parameter_count": parameter_count,
                   "probe_relative_loss_drop": drop, "learning_gate_passed": drop >= 0.01,
                   "fit_performed": False}
    return rows, diagnostics, checkpoint


def _portable_rows(rows: list[dict[str, Any]], view: PartDHistoryView,
                   neighbors: HistoricalNeighbors) -> tuple[str, str]:
    candidates_fingerprint = hashlib.sha256()
    targets_fingerprint = hashlib.sha256()
    for row in rows:
        npi = row["npi"]
        scores = row["candidate_scores"]
        ordered = sorted(scores, key=lambda drug: (-scores[drug], *view.tie_key(drug)))
        ranks = {drug: rank for rank, drug in enumerate(ordered, start=1)}
        support = neighbors.fixed_support(npi)
        def item(drug: str) -> dict[str, Any]:
            return {"item_id": drug, "rank": ranks[drug], "prior_support": view.global_support(drug),
                    "neighbor_support": support[drug]}
        row.update(entity_id=npi, period=str(row["year"]), history_support=len(view.provider_history(npi)),
                   neighbor_support_definition="distinct supporting providers in fixed pre-target cosine top50",
                   positive_items=[item(drug) for drug in row["positives"]])
        row["recommendations"] = [{**item(drug), "drug": drug, "score": scores[drug]}
                                  for drug in ordered[:TOP_RECOMMENDATIONS]]
        candidates_fingerprint.update(bytes.fromhex(_digest([npi, row["year"], sorted(scores)])))
        targets_fingerprint.update(bytes.fromhex(_digest([npi, row["year"], row["positives"]])))
    return candidates_fingerprint.hexdigest(), targets_fingerprint.hexdigest()


def run_phase(input_path: str, year: int, family: str, configuration: dict,
              seed: int | None, fixed: dict, phase_dir: Path) -> dict:
    """Worker contract; parent owns supervision, selection and publication gates."""
    phase_dir = Path(phase_dir)
    started = time.perf_counter()
    try:
        _validate_request(family, configuration, seed, fixed)
        task = PartDTask.from_prepared_input(Path(input_path))
        view = _view(task, year)
        neighbors = HistoricalNeighbors(view)
        model_dir = phase_dir / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = model_dir / "checkpoint.npz"
        rows = None
        state_started = time.perf_counter()
        if family in NEIGHBOR_FAMILIES:
            scorer = neighbors.scorer(family, configuration["k"])
            neighbors.save(checkpoint, family, configuration["k"])
            diagnostics = {"fit_performed": False, "parameter_count": 0, "learning_gate_passed": None,
                           "similarity": family, "k": configuration["k"], "weighted_vote": True,
                           "binary_incidence": True, "candidate_specific_neighbor_reselection": False}
            diagnostics["stored_state"] = {
                "binary_incidence_entries": int(neighbors.incidence.nnz),
                "neighbor_entries": sum(len(peers) for peers in neighbors.table(family, configuration["k"]).values()),
                "definition": "nonparametric stored historical links and similarity weights; not trainable parameters",
            }
        elif family in ("global_popularity", "specialty_popularity"):
            scorer, state = _baseline(view, family)
            checkpoint = model_dir / "state.json"
            _json(checkpoint, state)
            diagnostics = {"fit_performed": False, "parameter_count": 0, "learning_gate_passed": None}
            diagnostics["stored_state"] = {
                "global_support_entries": len(state["global_support"]),
                "specialty_support_entries": sum(len(values) for values in state["specialty_support"].values()),
                "provider_specialty_entries": len(state["latest_specialties"]),
                "definition": "nonparametric pre-target support counts and assignments; not trainable parameters",
            }
        elif family == "graphsage":
            ranker, diagnostics = fit_graphsage(_graph_history(view), dimension=configuration["dimension"],
                                                regularization=configuration["regularization"], seed=seed,
                                                epochs=30, learning_rate=0.02, fanout=8, aggregation="mean")
            raw = diagnostics.pop("raw_checkpoint")
            save_graphsage_checkpoint(checkpoint, raw)
            _json(model_dir / "diagnostics.json", diagnostics)
            _json(model_dir / "probe.json", {"triplets": diagnostics["probe"],
                                           "definition": "fixed pre-target positive/complement pairs"})
            diagnostics["parameter_count"] = sum(int(raw[key].size) for key in
                                                 ("product_inputs", "problem_inputs", "self_weights", "neighbor_weights"))
            diagnostics["fit_performed"] = True
            diagnostics["node_types"] = {"products": "PartD providers", "problems": "PartD original generic drugs"}
            if not diagnostics["learning_gate_passed"]:
                raise ValueError("Part D GraphSAGE failed fixed-probe learning gate; checkpoint and diagnostics retained")
            def scorer(current, npi, candidates):
                if current.target_year != year:
                    raise ValueError("GraphSAGE used at a different temporal cutoff")
                return {drug: ranker.score(npi, drug) for drug in candidates}
        else:
            rows, diagnostics, source_checkpoint = consume_reused_bpr(
                task, year, Path(fixed["reuse_phase_path"]), seed,
                Path(fixed["reuse_prepared_path"]) if fixed.get("reuse_prepared_path") else None)
            # Preserve the exact learned bytes; copying does not refit or alter state.
            import shutil
            shutil.copyfile(source_checkpoint, checkpoint)
            if not diagnostics["learning_gate_passed"]:
                raise ValueError("reused BPR failed fixed historical learning gate")
        state_seconds = time.perf_counter() - state_started
        fit_seconds = state_seconds if diagnostics["fit_performed"] else 0.0
        # Reuse compatibility checking includes the single target score consumption.
        score_seconds = state_seconds if family == "bpr_reuse" else 0.0
        if rows is None:
            score_started = time.perf_counter()
            rows = task._rank_target(year, scorer, retain_candidate_scores=True)
            score_seconds = time.perf_counter() - score_started
        metrics = task._metrics(rows)
        candidate_hash, target_hash = _portable_rows(rows, view, neighbors)
        score_table = _save_all_candidate_scores(task, year, rows, phase_dir / "all_candidate_scores.npz")
        prediction_path = phase_dir / "predictions.jsonl.gz"
        # mtime=0 makes portable prediction hashes independent of execution time.
        with prediction_path.open("wb") as stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as output:
                for row in rows:
                    row.pop("candidate_scores")
                    output.write((json.dumps({**row, "family": family, "configuration": configuration, "seed": seed},
                                             sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode())
        diagnostics["checkpoint"] = str(checkpoint)
        diagnostics["checkpoint_sha256"] = sha256_file(checkpoint)
        result = {"family": family, "configuration": configuration, "seed": seed,
                  "year": year, "target_year": year, "primary_metric": _primary_metric(metrics),
                  "metrics": metrics, "fit": diagnostics, "learning_diagnostics": diagnostics,
                  "parameter_count": diagnostics["parameter_count"],
                  "trainable_parameter_count": diagnostics["parameter_count"],
                  "stored_state": diagnostics.get("stored_state"),
                  "fit_seconds": fit_seconds, "score_seconds": score_seconds,
                  "state_preparation_seconds": state_seconds if not diagnostics["fit_performed"] and family != "bpr_reuse" else 0.0,
                  "learning_gate_passed": diagnostics["learning_gate_passed"],
                  "target_provider_years": len(rows), "eligible_provider_years": sum(row["eligible"] for row in rows),
                  "positive_total": sum(row["positive_count"] for row in rows),
                  "evaluated_candidate_total": sum(row["candidate_count"] for row in rows),
                  "candidate_fingerprint": candidate_hash, "target_fingerprint": target_hash,
                  "candidate_score_table": score_table, "prediction_file": str(prediction_path),
                  "prediction_file_sha256": sha256_file(prediction_path),
                  "checkpoint": str(checkpoint), "checkpoint_sha256": sha256_file(checkpoint),
                  "data_provenance": {"prepared_dir": input_path, "prior_years": view.prior_years,
                                      "edges_sha256": sha256_file(Path(input_path) / "edges.csv"),
                                      "report_sha256": sha256_file(Path(input_path) / "report.json"),
                                      "history_fingerprint": _digest({p: sorted(view.provider_history(p)) for p in view.providers}),
                                      "sources": task.report.get("sources", {})},
                  "wall_seconds": time.perf_counter() - started}
        _json(phase_dir / "result.json", result)
        return result
    except BaseException as error:
        _json(phase_dir / "error.json", {"error": repr(error), "traceback": traceback.format_exc()})
        raise


def preflight() -> dict[str, Any]:
    """Numerical synthetic checks only; never opens or scores health data."""
    import tempfile
    providers = {"a": frozenset({"x"}), "b": frozenset({"x", "y"}),
                 "c": frozenset({"y", "z"}), "d": frozenset({"z"})}
    drugs = {drug: frozenset(p for p, values in providers.items() if drug in values) for drug in ("x", "y", "z")}
    view = PartDHistoryView(2023, (2019, 2020, 2021, 2022), providers, drugs, {})
    neighbors = HistoricalNeighbors(view)
    if neighbors.table("common_count", 8)["a"] != (("b", 1.0),):
        raise AssertionError("binary common-count synthetic check failed")
    ranker, diagnostics = fit_graphsage(_graph_history(view), dimension=16, regularization=0.000005,
                                        seed=103, epochs=30, learning_rate=0.02, fanout=8)
    if not diagnostics["learning_gate_passed"]:
        raise AssertionError("synthetic GraphSAGE learning gate failed")
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / "checkpoint.npz"
        save_graphsage_checkpoint(checkpoint, diagnostics.pop("raw_checkpoint"))
        restored = load_graphsage_checkpoint(checkpoint)
        error = max(abs(ranker.score(p, drug) - restored.score(p, drug)) for p in providers for drug in drugs)
        if error > 1e-12:
            raise AssertionError("GraphSAGE checkpoint round-trip changed scores")
    return {"binary_neighbors": True,
            "checkpoint_max_score_error": error, "probe_relative_loss_drop": diagnostics["probe_relative_loss_drop"],
            "learning_gate_passed": True, "health_data_executed": False}
