"""RC3.1 targeted MAUDE diagnostics; no model/fanout selection is performed here.

run_phase consumes the immutable Q2 prepared directory. BPR reuses a selected
raw checkpoint (fixed['checkpoint_path'], or a checkpoint input_path together
with fixed['prepared_path']); it never fits. Real and reassigned GraphSAGE use
Q2's exact sequential gradient kernels, initialization, probe and negative
universe. Reassignment changes aggregation adjacency only, is a bounded double
edge-switch diagnostic, not a uniform graph null or a medical causal intervention.
All four GraphSAGE levels and all three seeds must be reported by the controller.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import random
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

from ..q2 import maude as q2
from ..q2 import maude_backend as backend
from ..tasks.maude.data import DataBundle, QuarterSnapshot, sha256_file
from ..tasks.maude.evaluate import (
    MetricAccumulator, SUPPORT_BANDS, SUPPORT_THRESHOLDS, eligible_edges,
    first_edges, support_band,
)
from ..tasks.maude.models import FeatureContext, History

SEEDS = (103, 211, 307)
TOP_KS = (1, 5, 10, 20, 50, 100)
GRAPH_CONFIGURATIONS = tuple(
    {"dimension": 16, "regularization": 0.000005, "fanout": fanout, "adjacency": "real"}
    for fanout in (4, 8, 16)
) + ({"dimension": 16, "regularization": 0.000005, "fanout": 8, "adjacency": "reassigned"},)
PREPARED_PATH = Path("results/generated/q2-cycle-20261003/maude-comparison-001/prepared")
PUBLISHED_BPR_ROOT = Path("results/generated/q2-cycle-20261003/maude-comparison-002/test/bpr")


def _digest(rows: Any) -> str:
    digest = hashlib.sha256()
    for row in rows:
        encoded = json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _edges(history: History) -> list[tuple[str, str]]:
    return [(p, d) for p in sorted(history.product_problems) for d in sorted(history.product_problems[p])]


def reassign_adjacency(history: History, *, seed: int = 303, attempts_per_edge: int = 10) -> tuple[History, dict[str, Any]]:
    """Switch (p,d),(q,e) -> (p,e),(q,d), preserving both typed degree vectors.

    The input is strictly pre-origin history. Labels, reports and evaluation
    candidates are never replaced with this aggregation-only graph.
    """
    if attempts_per_edge < 0:
        raise ValueError("negative edge-switch attempt count")
    original = _edges(history)
    edges = original.copy()
    present = set(edges)
    rng = random.Random(seed)
    attempted = accepted = rejected_same_endpoint = rejected_duplicate = 0
    if len(edges) >= 2:
        for _ in range(attempts_per_edge * len(edges)):
            attempted += 1
            i = rng.randrange(len(edges))
            j = rng.randrange(len(edges) - 1)
            if j >= i:
                j += 1
            p, d = edges[i]
            q, e = edges[j]
            if p == q or d == e:
                rejected_same_endpoint += 1
                continue
            left, right = (p, e), (q, d)
            if left in present or right in present:
                rejected_duplicate += 1
                continue
            present.remove(edges[i])
            present.remove(edges[j])
            present.update((left, right))
            edges[i], edges[j] = left, right
            accepted += 1
    adjacency = History.empty()
    for p, d in sorted(present):
        adjacency.product_problems[p].add(d)
        adjacency.problem_products[d].add(p)
    if {p: len(ds) for p, ds in history.product_problems.items()} != {p: len(ds) for p, ds in adjacency.product_problems.items()}:
        raise RuntimeError("product degrees changed in aggregation reassignment")
    if {d: len(ps) for d, ps in history.problem_products.items()} != {d: len(ps) for d, ps in adjacency.problem_products.items()}:
        raise RuntimeError("problem degrees changed in aggregation reassignment")
    changed = len(set(original) - present)
    return adjacency, {
        "randomization_seed": seed, "attempts_per_edge": attempts_per_edge,
        "edge_count": len(original), "attempted_swaps": attempted,
        "accepted_swaps": accepted, "rejected_same_endpoint": rejected_same_endpoint,
        "rejected_duplicate": rejected_duplicate, "changed_edges": changed,
        "changed_fraction": changed / len(original) if original else 0.0,
        "every_node_degree_preserved": True, "typed_bipartite_edges_only": True,
        "original_adjacency_sha256": _digest(original),
        "reassigned_adjacency_sha256": _digest(sorted(present)),
        "interpretation": "aggregation-only bounded edge-switch diagnostic; not a uniform null or medical causal effect",
    }


def _fit_reassigned(history: History, seed: int, probe_limit: int, minimum_drop: float) -> tuple[Any, dict[str, Any]]:
    """Q2 orchestration with only aggregation arrays replaced; no monkeypatch."""
    np, _ = backend._numeric_libraries()
    train, probe, _ = backend._kernels()
    layout = backend._graph_layout(history, 8, np)
    products, problems, pi, di, _, _, pp, pd, flat, offsets = layout
    adjacency, swaps = reassign_adjacency(history)
    alternate = backend._graph_layout(adjacency, 8, np)
    if alternate[0] != products or alternate[1] != problems:
        raise RuntimeError("aggregation reassignment changed node universe")
    pn, dn = alternate[4:6]
    x, y = backend._initial_pair(len(products), len(problems), 16, seed, np)
    ws = np.eye(16, dtype=np.float64)
    wn = ws * 0.25
    probe_p, probe_d, probe_n, named_probe = backend._probe_indices(history, pi, di, probe_limit)
    before = float(probe(x, y, ws, wn, pn, dn, probe_p, probe_d, probe_n, True))
    initial = tuple(value.copy() for value in (x, y, ws, wn))
    initial_hash = hashlib.sha256()
    for value in initial:
        initial_hash.update(memoryview(value).cast("B"))
    trace = train(x, y, ws, wn, pn, dn, pp, pd, flat, offsets, 30, 0.02, 0.000005, seed, True)
    after = float(probe(x, y, ws, wn, pn, dn, probe_p, probe_d, probe_n, True))
    hidden_p, hidden_d = backend._graph_embeddings(x, y, ws, wn, pn, dn, True, np)
    changed = any(bool(np.any(a != b)) for a, b in zip(initial, (x, y, ws, wn), strict=True))
    drop = (before - after) / before if before > 0 else 0.0
    config = {"aggregation": "mean", "adjacency": "reassigned", "dimension": 16,
              "epochs": 30, "learning_rate": 0.02, "regularization": 0.000005,
              "fanout": 8, "seed": seed, "initialization": "normal(0,0.05)",
              "objective": "online sequential BPR, exact per-triplet gradients with repeated-neighbor accumulation",
              "active_transform_parameters": 512, "node_input_scalars": (len(products) + len(problems)) * 16}
    raw = {"products": products, "problems": problems, "product_inputs": x,
           "problem_inputs": y, "self_weights": ws, "neighbor_weights": wn,
           "product_neighbors": pn, "problem_neighbors": dn,
           "product_embeddings": hidden_p, "problem_embeddings": hidden_d, "configuration": config}
    raw["aggregation_edges"] = _edges(adjacency)
    ranker = backend.GraphSageRanker(backend._ranker_vectors(hidden_p, products), backend._ranker_vectors(hidden_d, problems), config)
    diagnostics = {"configuration": config, "trace": [
        {"epoch": int(row[0]), "steps": int(row[1]), "positive_edges_skipped": int(row[2]),
         "mean_bpr_data_loss": None if math.isnan(row[3]) else float(row[3])} for row in trace],
        "probe": [list(row) for row in named_probe], "probe_triplets": len(named_probe),
        "probe_loss_before": before, "probe_loss_after": after,
        "probe_relative_loss_drop": drop, "state_changed": changed,
        "initialization_sha256": initial_hash.hexdigest(),
        "minimum_probe_loss_reduction": minimum_drop,
        "learning_gate_passed": changed and drop >= minimum_drop,
        "training_edge_sha256": _digest(_edges(history)),
        "negative_problem_universe_sha256": _digest(problems),
        "probe_sha256": _digest(named_probe),
        "reassignment": swaps, "raw_checkpoint": raw}
    return ranker, diagnostics


def _check_bpr_history(path: Path, history: History, seed: int) -> tuple[Any, dict[str, Any]]:
    """Verify exact node/label universe before using either inference transform."""
    smoothed = backend.load_bpr_checkpoint(path)  # Also verifies stored smoothing against raw state.
    np = q2._numpy()
    with np.load(path, allow_pickle=False) as archive:
        products = tuple(str(p) for p in archive["products"].tolist())
        problems = tuple(str(d) for d in archive["problems"].tolist())
        if products != tuple(sorted(history.product_problems)) or problems != tuple(sorted(history.problem_products)):
            raise ValueError("reused BPR node universe does not match pre-target history")
        di = {d: i for i, d in enumerate(problems)}
        expected = [di[d] for p in products for d in sorted(history.product_problems[p])]
        offsets = [0]
        for p in products:
            offsets.append(offsets[-1] + len(history.product_problems[p]))
        if not np.array_equal(archive["product_positive_values"], expected) or not np.array_equal(archive["product_positive_offsets"], offsets):
            raise ValueError("reused BPR training edges do not match pre-target history")
        reverse, reverse_offsets = backend._reverse_csr(len(problems), archive["product_positive_values"], archive["product_positive_offsets"], np)
        if not np.array_equal(reverse, archive["problem_positive_values"]) or not np.array_equal(reverse_offsets, archive["problem_positive_offsets"]):
            raise ValueError("reused BPR reverse adjacency does not match training edges")
        if int(smoothed.configuration["seed"]) != seed:
            raise ValueError("reused BPR seed differs from phase seed")
        raw_ranker = backend.LatentRanker(products, problems,
            backend._ranker_vectors(archive["product_inputs"], products),
            backend._ranker_vectors(archive["problem_inputs"], problems), dict(smoothed.configuration))
    return (raw_ranker, smoothed), {
        "configuration": dict(smoothed.configuration), "retrained": False,
        "identical_learned_state": True, "source_checkpoint_sha256": sha256_file(path),
        "training_edge_sha256": _digest(_edges(history)),
        "interpretation": "inference smoothing only; not removal of all relational learning",
    }


def _workload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = sum(row["positive_count"] for row in rows)
    out = {}
    for k in TOP_KS:
        hits = sum(sum(rank <= k for rank in row["positive_ranks"]) for row in rows)
        slots = sum(min(k, row["candidate_count"]) for row in rows)
        covered = sum(any(rank <= k for rank in row["positive_ranks"]) for row in rows)
        out[str(k)] = {"retrieved_links": hits, "proposal_slots": slots,
            "observed_positive_links": positives, "recall": hits / positives if positives else 0.0,
            "precision": hits / slots if slots else 0.0, "entity_hit_count": covered,
            "entity_hit_coverage": covered / len(rows) if rows else 0.0}
    zeros = sum(row["positive_count"] == 0 for row in rows)
    return {"product_quarters": len(rows), "zero_positive_product_quarters": zeros,
            "zero_positive_fraction": zeros / len(rows) if rows else 0.0, "top_k": out}


def _quarter_rows(history: History, quarter: str, first: Any, parent_map: Mapping[str, str], family: str, model: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    positives: dict[str, set[str]] = defaultdict(set)
    for product, problem in eligible_edges(first, history):
        positives[product].add(problem)
    rows, score_rows = [], []
    thresholds = {n: MetricAccumulator() for n in SUPPORT_THRESHOLDS}
    bands = {b: MetricAccumulator() for b in SUPPORT_BANDS}
    context = FeatureContext(history, quarter, parent_map)
    for product in sorted(history.product_reports):
        support = history.product_reports[product]
        if support < 1:
            continue
        candidates = history.candidate_problems(product)
        if not candidates:
            continue
        target = positives.get(product, set())
        if not target.issubset(candidates):
            raise RuntimeError("eligible MAUDE positives are outside candidate universe")
        ranking = q2._rank_candidates(history, quarter, product, candidates, family, model, parent_map)
        ranks = {problem: i for i, (problem, _) in enumerate(ranking, 1)}
        neighbors = context.neighbor_scores(product)
        def item(problem: str, rank: int, score: float) -> dict[str, Any]:
            return {"item_id": problem, "problem": problem, "rank": rank, "score": score,
                    "prior_support": len(history.problem_products[problem]),
                    "neighbor_support": int(neighbors.get(problem, 0))}
        positive_items = [item(d, ranks[d], ranking[ranks[d] - 1][1]) for d in sorted(target)]
        row = {"record_kind": "product_ranking", "entity_id": product, "product": product,
            "period": quarter, "quarter": quarter, "year": int(quarter[:4]), "method": family,
            "history_support": support, "history_support_band": support_band(support),
            "candidate_count": len(candidates), "positive_count": len(target), "positive_edges": len(target),
            "candidate_universe_sha256_length_prefixed_utf8": q2._candidate_fingerprint(candidates),
            "target_sha256": _digest(sorted(target)), "positive_ranks": [ranks[d] for d in sorted(target)],
            "positive_items": positive_items,
            "recommendations": [item(d, i, score) for i, (d, score) in enumerate(ranking[:100], 1)]}
        row["workload_top_k"] = {
            str(k): {"proposal_slots": min(k, len(candidates)),
                     "retrieved_links": sum(rank <= k for rank in row["positive_ranks"])}
            for k in TOP_KS
        }
        rows.append(row)
        score_rows.append({"entity_id": product, "period": quarter,
            "item_ids": [d for d, _ in ranking],
            "ranks": list(range(1, len(ranking) + 1)),
            "scores": [score for _, score in ranking],
            "prior_support": [len(history.problem_products[d]) for d, _ in ranking]})
        if target:
            for n, accumulator in thresholds.items():
                if support >= n:
                    accumulator.add_product(row["positive_ranks"], len(target))
            bands[support_band(support)].add_product(row["positive_ranks"], len(target))
    return rows, score_rows, {"thresholds": {str(n): a.as_dict() for n, a in thresholds.items()},
        "support_bands": {b: a.as_dict() for b, a in bands.items()}, "workload": _workload(rows)}


def _write_jsonl(output: Any, rows: Any) -> None:
    for row in rows:
        output.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def run_phase(input_path: str, year: int, family: str, configuration: dict, seed: int | None, fixed: dict, phase_dir: Path) -> dict:
    """Fit GraphSAGE, or reuse BPR, then rank only the requested year's quarters.

    fixed optionally carries Q2 learning_gate; GraphSAGE settings are locked.
    BPR checkpoint paths may be supplied in fixed/configuration. A checkpoint
    input_path uses fixed['prepared_path'] (default published prepared bundle).
    Actual checkpoints, losses/gate, predictions and *all* candidate ranks/scores
    are retained. Failure of the historical learning gate stops before ranking.
    """
    if year not in (2023, 2024, 2025) or seed not in SEEDS:
        raise ValueError("RC3.1 MAUDE requires year2023/24/25 and seed103/211/307")
    if family not in ("graphsage_mean", "graphsage_reassigned", "bpr_raw", "bpr_smoothed"):
        raise ValueError("unknown RC3.1 MAUDE family")
    input_file = Path(input_path)
    checkpoint_source = fixed.get("checkpoint_path", configuration.get("checkpoint_path"))
    if input_file.is_file():
        if family.startswith("bpr_"):
            checkpoint_source = str(input_file)
            prepared = Path(fixed.get("prepared_path", PREPARED_PATH))
        else:
            raise ValueError("GraphSAGE input_path must be a prepared directory")
    else:
        prepared = input_file
    cached = q2._load_prepared(prepared / "maude_raw_bundle.pkl.gz")
    bundle, parent_map = cached["bundle"], cached["problem_parent_map"]
    origin = f"{year}Q1"
    history = q2._history_before(bundle, origin, parent_map)
    training_edges = _edges(history)
    config = dict(configuration)
    checkpoint = phase_dir / "checkpoint.bin"
    if family.startswith("graphsage"):
        for key, value in (("dimension", 16), ("regularization", 0.000005), ("epochs", 30), ("learning_rate", 0.02)):
            if key in config and config[key] != value:
                raise ValueError(f"RC3.1 MAUDE locks {key}={value}")
            config[key] = value
        adjacency = config.get("adjacency", "reassigned" if family == "graphsage_reassigned" else "real")
        fanout = int(config.get("fanout", 8))
        if adjacency not in ("real", "reassigned") or fanout not in (4, 8, 16) or config.get("fanout", 8) != fanout or (adjacency == "reassigned" and fanout != 8):
            raise ValueError("invalid fixed MAUDE fanout/adjacency level")
        config.update(fanout=fanout, adjacency=adjacency)
        gate = fixed.get("learning_gate", {})
        probe_limit = int(gate.get("fixed_historical_probe_max_triplets", 20000))
        minimum_drop = float(gate.get("minimum_relative_bpr_data_loss_reduction", 0.01))
        if probe_limit < 1 or not math.isfinite(minimum_drop) or not 0 <= minimum_drop <= 1:
            raise ValueError("invalid training-only learning gate")
        if adjacency == "real":
            model, diagnostics = backend.fit_graphsage(history, dimension=16, regularization=0.000005,
                seed=seed, epochs=30, learning_rate=0.02, fanout=fanout, aggregation="mean",
                probe_limit=probe_limit, minimum_probe_loss_reduction=minimum_drop)
        else:
            model, diagnostics = _fit_reassigned(history, seed, probe_limit, minimum_drop)
        backend.save_graphsage_checkpoint(checkpoint, diagnostics["raw_checkpoint"])
        if adjacency == "reassigned":
            adjacency_path = phase_dir / "aggregation_adjacency.jsonl.gz"
            with gzip.open(adjacency_path, "wt", encoding="utf-8", newline="\n") as output:
                _write_jsonl(output, diagnostics["raw_checkpoint"]["aggregation_edges"])
            diagnostics["reassignment"]["adjacency_file"] = adjacency_path.name
            diagnostics["reassignment"]["adjacency_file_sha256"] = sha256_file(adjacency_path)
        q2._json_write(phase_dir / "learning_diagnostics.json", q2._public_diagnostics(diagnostics))
        if not diagnostics["learning_gate_passed"]:
            q2._json_write(phase_dir / "failed_learning_gate.json", q2._public_diagnostics(diagnostics))
            raise RuntimeError("RC3.1 MAUDE historical learning gate failed; raw state retained")
        parameter_count = int(diagnostics["configuration"]["node_input_scalars"]) + 512
    else:
        if checkpoint_source is None:
            if year == 2023:
                raise ValueError("validation2023 BPR needs selected published checkpoint_path mapping")
            checkpoint_source = PUBLISHED_BPR_ROOT / f"year{year}" / f"seed{seed}" / "checkpoint.bin"
        checkpoint_source = Path(checkpoint_source)
        models, diagnostics = _check_bpr_history(checkpoint_source, history, seed)
        model = models[0 if family == "bpr_raw" else 1]
        sibling = checkpoint_source.parent / "result.json"
        if sibling.exists():
            prior = q2._json_read(sibling)
            if prior.get("fit_cutoff") != f"{year - 1}Q4" or prior.get("seed") != seed:
                raise ValueError("BPR published phase cutoff/seed mismatches requested origin")
            diagnostics["published_learning_diagnostics"] = prior.get("diagnostics", {})
            diagnostics["published_result_sha256"] = sha256_file(sibling)
        diagnostics["source_checkpoint_path"] = str(checkpoint_source)
        diagnostics["inference_transform"] = "x/y raw" if family == "bpr_raw" else "0.5self+0.5historical_neighbor_mean"
        shutil.copyfile(checkpoint_source, checkpoint)
        config.update(model.configuration)
        config["inference_transform"] = diagnostics["inference_transform"]
        parameter_count = int(model.configuration["node_input_scalars"])
        q2._json_write(phase_dir / "learning_diagnostics.json", diagnostics)
    quarters = tuple(f"{year}Q{i}" for i in range(1, 5))
    snapshots = {snapshot.quarter: snapshot for snapshot in bundle.snapshots}
    if any(q not in snapshots for q in quarters):
        raise ValueError("prepared bundle lacks requested target quarters")
    first = first_edges(bundle)
    all_rows, quarterly = [], {}
    predictions = phase_dir / "predictions.jsonl.gz"
    scores = phase_dir / "all_candidate_scores.jsonl.gz"
    with gzip.open(predictions, "wt", encoding="utf-8", newline="\n") as pred, gzip.open(scores, "wt", encoding="utf-8", newline="\n") as score_output:
        for quarter in quarters:
            rows, score_rows, quarterly[quarter] = _quarter_rows(history, quarter, first[quarter], parent_map, family, model)
            _write_jsonl(pred, rows)
            _write_jsonl(score_output, score_rows)
            all_rows.extend({key: row[key] for key in (
                "period", "entity_id", "candidate_count", "positive_count", "positive_ranks",
                "candidate_universe_sha256_length_prefixed_utf8", "target_sha256"
            )} for row in rows)
            history.add(snapshots[quarter], parent_map)  # Only after current-quarter scoring.
    workload = _workload(all_rows)
    candidate_fingerprint = _digest([(r["period"], r["entity_id"], r["candidate_universe_sha256_length_prefixed_utf8"]) for r in all_rows])
    target_fingerprint = _digest([(r["period"], r["entity_id"], r["target_sha256"]) for r in all_rows])
    record = {"task": "maude", "family": family, "year": year, "seed": seed,
        "configuration": config, "fit_cutoff": f"{year - 1}Q4", "forecast_origin": origin,
        "primary_metric": workload["top_k"]["10"]["recall"],
        "primary_micro_recall_at_10": workload["top_k"]["10"]["recall"],
        "quarters": quarterly, "annual_metrics": q2._aggregate_metrics(quarterly), "workload": workload,
        "parameter_count": parameter_count, "training_edge_count": len(training_edges),
        "training_edge_sha256": _digest(training_edges), "diagnostics": q2._public_diagnostics(diagnostics),
        "data_provenance": {"prepared_path": str(prepared), "prepared_bundle_sha256": sha256_file(prepared / "maude_raw_bundle.pkl.gz"),
            "raw_sources": cached.get("raw_sources", []), "task_manifest": cached.get("task_manifest", {})},
        "candidate_fingerprint": candidate_fingerprint, "target_fingerprint": target_fingerprint,
        "checkpoint": checkpoint.name, "checkpoint_sha256": sha256_file(checkpoint),
        "prediction_file": predictions.name, "prediction_sha256": sha256_file(predictions),
        "candidate_scores_file": scores.name, "candidate_scores_sha256": sha256_file(scores),
        "candidate_score_format": "gzip JSONL; parallel item_ids/ranks/scores/prior_support arrays for every product-quarter candidate",
        "all_factor_levels_reported_not_selected": True,
        "interpretation": "observed novel published links; absent links are not clinical errors"}
    q2._json_write(phase_dir / "result.json", record)
    return record


def _synthetic_history() -> History:
    history = History.empty()
    edges = frozenset((("A", "10"), ("B", "10"), ("C", "20"), ("D", "20")))
    history.add(QuarterSnapshot("2022Q4", 4, {p: 1 for p in "ABCD"}, {}, edges, {e: 1 for e in edges}), {})
    return history


def preflight() -> dict[str, Any]:
    """Synthetic-only preflight; parent runs this after integration, never on health data."""
    history = _synthetic_history()
    original = _edges(history)
    adjacency, stats = reassign_adjacency(history)
    assert original == _edges(history)
    assert stats["accepted_swaps"] > 0
    assert len(_edges(adjacency)) == len(original)
    learning = []
    for seed in SEEDS:
        for fanout in (4, 8, 16):
            _, diagnostics = backend.fit_graphsage(history, dimension=16, regularization=0.000005,
                seed=seed, epochs=30, learning_rate=0.02, fanout=fanout)
            assert diagnostics["learning_gate_passed"]
            learning.append({"seed": seed, "fanout": fanout, "gate": True})
        _, alternate = _fit_reassigned(history, seed, 20000, 0.01)
        assert alternate["learning_gate_passed"]
        expected_probe = backend._probe_indices(history, {p: i for i, p in enumerate(sorted(history.product_problems))},
            {d: i for i, d in enumerate(sorted(history.problem_products))})[3]
        assert alternate["probe"] == [list(row) for row in expected_probe]
        learning.append({"seed": seed, "fanout": 8, "adjacency": "reassigned", "gate": True})
    return {"synthetic_only": True, "reassignment": stats, "learning": learning}
