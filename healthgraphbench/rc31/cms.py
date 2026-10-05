"""RC3.1 inspection-conditional CMS representation sensitivity experiment.

The documentation proxy is NOT verified ownership quality. A retained existing
combined PAC link must have an actual CHOW owner association and an enrollment
mapped to that CCN by an actual dated buyer/seller CHOW event. Both dates must be
strictly earlier than the inspection. The enrollment must map to only that CCN
among strictly earlier events. Future events cannot grant or revoke eligibility.
No ownership end dates, historical publication dates, or verified truth exist in
this snapshot; persistent associations are a representation assumption. Current
name-based links are excluded from the proxy, not declared incorrect. This probes
representation sensitivity, not a causal ownership-quality mechanism or selection
of facilities for inspection. The August 2026 snapshot is retrospective.

Preparation is a separately supervised worker. It verifies raw files, calls the
existing preparation, checks every base row against Q2, preserves all episode,
label and local-history fields, and recomputes BOTH relational representations
with strict date cutoffs (the old peer helper allowed same-day associations).
Workers never tune or select configurations; the controller must publish the
protocol before fits and supervise workers with q2.common.RunBudget.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.metadata
import json
import pickle
import warnings
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..data import load_manifest, sha256_file, verify_files
from ..tasks.cms_nursing.models import BASE_FEATURE_NAMES, GRAPH_FEATURE_NAMES, model_metrics, row_numeric
from ..tasks.cms_nursing.prepare import (
    CHOW_ROLES, CmsPrepared, OwnerRecord, _episode_histories, _parse_date,
    _read_json_records, history_stats,
)
from ..tasks.cms_nursing.task import CmsNursingTask

FEATURE_SETS = (
    "facility_history", "facility_plus_combined_ownership",
    "facility_plus_documented_ownership",
)
RELATION_FIELDS = (
    "owner_count", "peer_count", "peer_prior_facilities", "peer_prior_inspections",
    "peer_prior_serious", "peer_recent365_inspections", "peer_recent365_serious",
    "peer_recent730_serious", "peer_any_serious365", "peer_any_serious730",
)
LOGISTIC_CONFIGURATION = {"C": .01}
BOOSTED_CONFIGURATION = {
    "learning_rate": .05, "max_iter": 100, "max_leaf_nodes": 15,
    "l2_regularization": 1,
}
LOGISTIC_FIXED = {"solver": "lbfgs", "class_weight": None, "max_iter": 1000, "tol": 1e-8}
BOOSTED_FIXED = {
    "early_stopping": False, "max_features": 1, "max_bins": 255,
    "min_samples_leaf": 20, "seed_repetition_condition": "training_rows_gt_200000",
}
SOURCE_FILES = (
    "health_citations.csv", "ownership.csv", "provider_info.csv", "survey_dates.csv",
    "penalties.csv", "chow.json", "chow_owners_full.json",
)
OPERATIONAL_CRITERION = (
    "Existing combined PAC association; raw owner role in CHOW_ROLES; nonempty raw "
    "ASSOCIATE ID - OWNER; ASSOCIATION DATE - OWNER < inspection; actual CHOW "
    "EFFECTIVE DATE < inspection joining ENROLLMENT ID to buyer/seller CCN; "
    "enrollment has one distinct CCN among events strictly before inspection. "
    "Both focal and peer links must satisfy the rule. No current-name fallback."
)
# ccn -> PAC owner -> ((max(owner-association, CHOW-effective), ambiguity-date), ...)
Evidence = dict[str, dict[str, tuple[tuple[date, date | None], ...]]]


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _load_rows(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def _fingerprint(rows: Iterable[Mapping[str, Any]], fields: tuple[str, ...] | None = None) -> str:
    digest = hashlib.sha256()
    for row in rows:
        value = dict(row) if fields is None else {key: row[key] for key in fields}
        digest.update((json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode())
    return digest.hexdigest()


def _base(row: Mapping[str, Any]) -> dict[str, Any]:
    output = {key: value for key, value in row.items() if key not in RELATION_FIELDS}
    if isinstance(output["date"], date):
        output["date"] = output["date"].isoformat()
    return output


def _documented_evidence(
    chow_rows: Iterable[Mapping[str, str]], owner_rows: Iterable[Mapping[str, str]],
    prepared: CmsPrepared,
) -> tuple[Evidence, dict[str, int]]:
    """Build temporal evidence, retaining dated ambiguity rather than future filters."""
    events: dict[str, dict[str, date]] = defaultdict(dict)
    counts: Counter[str] = Counter()
    for row in chow_rows:
        counts["chow_rows"] += 1
        effective = _parse_date(row.get("EFFECTIVE DATE", ""))
        if effective is None:
            counts["chow_rows_without_valid_effective_date"] += 1
            continue
        for side in ("BUYER", "SELLER"):
            enrollment = row.get(f"ENROLLMENT ID - {side}", "").strip()
            ccn = row.get(f"CCN - {side}", "").strip()
            if enrollment and ccn:
                prior = events[enrollment].get(ccn)
                if prior is None or effective < prior:
                    events[enrollment][ccn] = effective
                counts["dated_enrollment_ccn_event_sides"] += 1
    pairs: dict[str, dict[str, set[tuple[date, date | None]]]] = defaultdict(lambda: defaultdict(set))
    for row in owner_rows:
        counts["chow_owner_rows"] += 1
        enrollment = row.get("ENROLLMENT ID", "").strip()
        associate = row.get("ASSOCIATE ID - OWNER", "").strip()
        association = _parse_date(row.get("ASSOCIATION DATE - OWNER", ""))
        role = row.get("ROLE TEXT - OWNER", "").strip()
        if not associate or association is None or role not in CHOW_ROLES:
            counts["owner_rows_excluded_missing_id_date_or_role"] += 1
            continue
        if enrollment not in events:
            counts["owner_rows_without_dated_enrollment_ccn_event"] += 1
            continue
        owner = f"PAC:{associate}"  # Exact existing preparation namespace, actual raw ID.
        for ccn, effective in events[enrollment].items():
            if owner not in prepared.combined_first or ccn not in prepared.combined_first[owner]:
                counts["evidence_pairs_outside_existing_combined_links"] += 1
                continue
            conflicting = [when for other, when in events[enrollment].items() if other != ccn]
            ambiguity = min(conflicting) if conflicting else None
            pairs[ccn][owner].add((max(association, effective), ambiguity))
            counts["documented_candidate_owner_record_event_pairs"] += 1
    evidence = {
        ccn: {owner: tuple(sorted(values, key=lambda pair: (pair[0], pair[1] or date.max)))
              for owner, values in owners.items()}
        for ccn, owners in pairs.items()
    }
    counts["unique_candidate_documented_facility_owner_pairs"] = sum(map(len, evidence.values()))
    counts["combined_facility_owner_pairs_all_dates"] = sum(map(len, prepared.combined_first.values()))
    counts["current_name_pairs_excluded_from_documentation_proxy"] = sum(
        len(peers) for owner, peers in prepared.combined_first.items() if not owner.startswith("PAC:")
    )
    counts["enrollments_with_multiple_ccns_across_snapshot"] = sum(len(ccns) > 1 for ccns in events.values())
    return evidence, dict(counts)


def _documented(evidence: Evidence, ccn: str, owner: str, target: date) -> bool:
    return any(
        documented < target and (ambiguous is None or target <= ambiguous)
        for documented, ambiguous in evidence.get(ccn, {}).get(owner, ())
    )


def _peer_stats(
    ccn: str, target: date, records: Mapping[str, Iterable[OwnerRecord]],
    first: Mapping[str, Mapping[str, date]], histories: Mapping[str, Any],
    cache: dict[tuple[str, date], dict[str, Any]], evidence: Evidence | None = None,
) -> dict[str, int]:
    """Exact existing aggregate definitions, but strict association-date cutoff."""
    active = {
        owner for owner, association, _role, _kind in records.get(ccn, ())
        if association < target and (evidence is None or _documented(evidence, ccn, owner, target))
    }
    peers = {
        peer for owner in active for peer, association in first.get(owner, {}).items()
        if peer != ccn and association < target
        and (evidence is None or _documented(evidence, peer, owner, target))
    }
    result = dict.fromkeys(RELATION_FIELDS, 0)
    result.update(owner_count=len(active), peer_count=len(peers))
    for peer in sorted(peers):
        if peer not in histories:
            continue
        key = peer, target
        stats = cache.get(key)
        if stats is None:
            stats = history_stats(histories, peer, target)
            cache[key] = stats
        if not stats["prior_inspections"]:
            continue
        result["peer_prior_facilities"] += 1
        for field in ("prior_inspections", "prior_serious", "recent365_inspections", "recent365_serious", "recent730_serious"):
            result[f"peer_{field}"] += stats[field]
        result["peer_any_serious365"] += int(stats["recent365_serious"] > 0)
        result["peer_any_serious730"] += int(stats["recent730_serious"] > 0)
    return result


def _quality_bin(combined: int, documented: int) -> str:
    if not 0 <= documented <= combined:
        raise ValueError("documented owners must be a subset of combined owners")
    if combined == 0:
        return "no_combined_links"
    if documented == 0:
        return "none_retained"
    return "all_retained" if documented == combined else "some_retained"


def _history_bin(count: int) -> str:
    return "1" if count == 1 else "2-3" if count <= 3 else ">3"


def prepare_phase(
    source_root: str | Path, manifest_path: str | Path,
    baseline_rows_path: str | Path, phase_dir: Path,
) -> dict[str, Any]:
    """Supervised raw preparation only; does not fit or score a health model."""
    root = Path(source_root)
    root = root / "cms" if (root / "cms").is_dir() else root
    manifest_path, baseline_rows_path = Path(manifest_path), Path(baseline_rows_path)
    manifest = load_manifest(manifest_path)
    entries = manifest["cms"]["files"]
    if not set(SOURCE_FILES).issubset({entry["path"] for entry in entries}):
        raise ValueError("source manifest does not cover all seven actual CMS dependencies")
    verified = verify_files(root, entries)
    prepared = CmsNursingTask.from_source_root(root).prepared
    baseline = _load_rows(baseline_rows_path)
    fresh_base = [_base(row) for row in prepared.rows]
    baseline_base = [_base(row) for row in baseline]
    if fresh_base != baseline_base:
        raise ValueError("raw preparation does not reproduce EVERY ordered Q2 episode/base-history/label row")
    if len({(row["ccn"], row["date"]) for row in baseline}) != len(baseline):
        raise ValueError("duplicate inspection keys in Q2 preparation")
    evidence, source_counts = _documented_evidence(
        _read_json_records(prepared.sources.chow), _read_json_records(prepared.sources.chow_owners), prepared,
    )
    histories = _episode_histories(prepared.standard_episodes, set(prepared.serious_episodes))
    cache: dict[tuple[str, date], dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    strata: dict[str, Counter[str]] = defaultdict(Counter)
    rows_path = phase_dir / "rows.jsonl.gz"
    fingerprint_fields = ("ccn", "date", "year", "label", "state")
    with gzip.open(rows_path, "wt", encoding="utf-8") as stream:
        for base, old in zip(baseline_base, baseline, strict=True):
            target = date.fromisoformat(base["date"])
            combined = _peer_stats(base["ccn"], target, prepared.combined_records, prepared.combined_first, histories, cache)
            documented = _peer_stats(base["ccn"], target, prepared.combined_records, prepared.combined_first, histories, cache, evidence)
            row = {**base, **combined, **{f"documented_{key}": value for key, value in documented.items()}}
            row["history_bin"] = _history_bin(base["prior_inspections"])
            row["quality_bin"] = _quality_bin(combined["owner_count"], documented["owner_count"])
            row["combined_owner_count"] = combined["owner_count"]
            row["documented_owner_count"] = documented["owner_count"]
            row["combined_peer_count"] = combined["peer_count"]
            row["documented_peer_count"] = documented["peer_count"]
            strata[str(base["year"])][row["quality_bin"]] += 1
            for prefix, values in (("combined", combined), ("documented", documented)):
                for key in ("owner_count", "peer_count", "peer_prior_inspections"):
                    counts[f"{prefix}_{key}_summed_over_inspection_rows"] += values[key]
            counts["rows_with_documented_owners"] += int(documented["owner_count"] > 0)
            counts["rows_with_documented_peers"] += int(documented["peer_count"] > 0)
            counts["rows_changed_by_strict_combined_cutoff"] += int(any(old[key] != combined[key] for key in RELATION_FIELDS))
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    common_fingerprint = _fingerprint(baseline_base, fingerprint_fields)
    result = {
        "rows": len(baseline), "rows_path": "rows.jsonl.gz", "rows_sha256": sha256_file(rows_path),
        "prepared_path": str(rows_path.resolve()),
        "primary_metric": "roc_auc", "primary_metric_name": "ROC_AUC",
        "feature_sets": list(FEATURE_SETS),
        "source_files": verified, "manifest_path": str(manifest_path), "manifest_sha256": sha256_file(manifest_path),
        "baseline_rows_path": str(baseline_rows_path), "baseline_rows_sha256": sha256_file(baseline_rows_path),
        "base_rows_sha256": _fingerprint(baseline_base), "every_base_row_equal_to_q2": True,
        "ordered_inspection_fingerprint": common_fingerprint,
        "row_layout_fingerprint": common_fingerprint,
        "stratum_fields": {"quality": "quality_bin", "history": "history_bin"},
        "feature_set_row_fingerprints": {name: common_fingerprint for name in FEATURE_SETS},
        "operational_criterion": OPERATIONAL_CRITERION,
        "source_restriction_counts": source_counts, "inspection_restriction_counts": dict(counts),
        "quality_bins_by_year": {year: dict(values) for year, values in strata.items()},
        "quality_bin_definition": "pre-inspection documented owner-count fraction: no combined links / zero / some / all retained",
        "history_bin_definition": "pre-inspection local inspection count 1 / 2-3 / >3",
        "relation_cutoff": "association and documenting CHOW event strictly before each inspection; peer history strictly before inspection",
        "relation_cutoff_change_from_q2": "New RC3.1 associations < inspection replaces Q2 <= inspection; old Q2 metrics and outputs are unchanged",
        "estimand": "serious deficiency conditional on a Health Standard inspection, not inspection selection",
        "availability": "retrospective_snapshot_not_origin_verified",
        "interpretation": "documentation-restriction representation sensitivity; no verified ownership truth or causal quality mechanism",
        "baseline_relational_features_reused": False,
        "raw_dependencies": list(SOURCE_FILES),
    }
    _json(phase_dir / "result.json", result)
    return result


def _matrices(rows: list[dict[str, Any]], year: int, feature_set: str) -> tuple[Any, ...]:
    if year not in (2023, 2024, 2025) or feature_set not in FEATURE_SETS:
        raise ValueError("only declared years and feature sets are supported")
    training = [row for row in rows if 2019 <= row["year"] < year]
    target = [row for row in rows if row["year"] == year]
    if not training or not target:
        raise ValueError("nonempty strictly-prior training and target inspections are required")
    states = tuple(sorted({str(row["state"]) for row in training}))
    labels = np.asarray([row["label"] for row in training], dtype=np.int64)
    if np.unique(labels).size != 2:
        raise ValueError("strictly-prior training must contain both classes")
    def numeric(row: dict[str, Any]) -> list[float]:
        if feature_set == "facility_plus_documented_ownership":
            row = {**row, **{key: row[f"documented_{key}"] for key in RELATION_FIELDS}}
        return row_numeric(row, feature_set != "facility_history", states)
    return (np.asarray([numeric(row) for row in training], dtype=np.float64), labels,
            np.asarray([numeric(row) for row in target], dtype=np.float64), training, target, states)


def expected_seeds(family: str, training_rows: int) -> list[int | None]:
    if family not in ("logistic", "boosted"):
        raise ValueError("unknown CMS family")
    return [103, 211, 307] if family == "boosted" and training_rows > 200000 else [None]


def _parameters(family: str, configuration: dict[str, Any], fixed: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    supplied = dict(configuration)
    feature_set = supplied.pop("feature_set", None)
    if feature_set not in FEATURE_SETS:
        raise ValueError("configuration.feature_set must name a declared representation")
    if family == "logistic":
        declared, fixed_declared = LOGISTIC_CONFIGURATION, LOGISTIC_FIXED
    elif family == "boosted":
        declared, fixed_declared = BOOSTED_CONFIGURATION, BOOSTED_FIXED
    else:
        raise ValueError("unknown CMS family")
    if supplied != declared or fixed != fixed_declared:
        raise ValueError("CMS requires exact shared fixed configurations; feature-set tuning is forbidden")
    return feature_set, {**fixed_declared, **declared}


def run_phase(
    input_path: str, year: int, family: str, configuration: dict,
    seed: int | None, fixed: dict, phase_dir: Path,
) -> dict[str, Any]:
    """Fit prior years, then score ONLY the named target year; supervised externally."""
    feature_set, parameters = _parameters(family, configuration, fixed)
    rows = _load_rows(Path(input_path))
    xs, labels, target_xs, training, target, states = _matrices(rows, year, feature_set)
    if seed not in expected_seeds(family, len(training)):
        raise ValueError("seed must follow the shared declared deterministic/binning condition")
    if family == "logistic":
        model = make_pipeline(StandardScaler(), LogisticRegression(**parameters))
    else:
        parameters.pop("seed_repetition_condition")
        parameters["max_features"] = float(parameters["max_features"])
        model = HistGradientBoostingClassifier(random_state=0 if seed is None else seed, **parameters)
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        model.fit(xs, labels)
    # Scoring occurs only after the fit; no later-year inspection enters training.
    scores = model.predict_proba(target_xs)[:, 1]
    training_scores = model.predict_proba(xs)[:, 1]
    if not np.all(np.isfinite(scores)) or not np.all(np.isfinite(training_scores)):
        raise ValueError("nonfinite model predictions")
    warning_rows = [{"category": item.category.__name__, "message": str(item.message)} for item in observed]
    _json(phase_dir / "warnings.json", warning_rows)
    names = list(BASE_FEATURE_NAMES)
    if feature_set != "facility_history":
        names.extend(("documented_" if feature_set.endswith("documented_ownership") else "") + name for name in GRAPH_FEATURE_NAMES)
    names.extend(f"state:{state}" for state in states)
    checkpoint = phase_dir / "checkpoint.pkl"
    with checkpoint.open("xb") as stream:
        pickle.dump({"model": model, "state_values": states, "feature_names": names,
                     "feature_set": feature_set, "year": year, "configuration": configuration,
                     "fixed": fixed, "seed": seed}, stream, protocol=5)
    fitted = model[-1] if family == "logistic" else model
    state: dict[str, Any] = {"state_values": list(states), "feature_names": names,
                             "parameters": model.get_params(deep=False) if family == "boosted" else parameters}
    if family == "logistic":
        state.update(scaler_mean=model[0].mean_.tolist(), scaler_scale=model[0].scale_.tolist(),
                     coefficients=fitted.coef_.tolist(), intercept=fitted.intercept_.tolist(), classes=fitted.classes_.tolist())
    _json(phase_dir / "model_state.json", state)
    predictions_path = phase_dir / "predictions.jsonl.gz"
    with gzip.open(predictions_path, "wt", encoding="utf-8") as stream:
        for row, score in zip(target, scores.tolist(), strict=True):
            prediction = {key: row[key] for key in (
                "ccn", "date", "year", "label", "state", "history_bin", "quality_bin",
                "prior_inspections", "combined_owner_count", "documented_owner_count",
                "combined_peer_count", "documented_peer_count",
            )}
            prediction["score"] = score
            stream.write(json.dumps(prediction, sort_keys=True, allow_nan=False) + "\n")
    fields = ("ccn", "date", "year", "label", "state")
    result = {
        "family": family, "feature_set": feature_set, "year": year, "seed": seed,
        "configuration": configuration, "fixed": fixed,
        "primary_metric": "roc_auc", "primary_metric_name": "ROC_AUC",
        "stratum_fields": {"quality": "quality_bin", "history": "history_bin"},
        "training_rows": len(training), "training_positives": int(labels.sum()), "target_rows": len(target),
        "training_years": sorted({row["year"] for row in training}),
        "training_facilities": len({row["ccn"] for row in training}), "target_facilities": len({row["ccn"] for row in target}),
        "training_row_fingerprint": _fingerprint(training, fields), "target_row_fingerprint": _fingerprint(target, fields),
        "row_layout_fingerprint": _fingerprint(target, fields),
        "training_facility_fingerprint": _fingerprint([{"ccn": ccn} for ccn in sorted({row["ccn"] for row in training})]),
        "target_facility_fingerprint": _fingerprint([{"ccn": ccn} for ccn in sorted({row["ccn"] for row in target})]),
        "input_sha256": sha256_file(Path(input_path)),
        "feature_dimension": int(xs.shape[1]), "feature_names": names,
        "feature_counts": {"local": len(BASE_FEATURE_NAMES), "relational": 0 if feature_set == "facility_history" else len(GRAPH_FEATURE_NAMES), "states": len(states)},
        "state_values": list(states), "state_vocabulary_source": "strictly_prior_training_only",
        "scaler_source": "strictly_prior_training_only" if family == "logistic" else "not_used",
        "iterations": int(np.max(fitted.n_iter_)),
        "losses": {"definition": "unweighted strictly-prior training binary cross-entropy data loss (not penalized optimizer objective)",
                   "initial_zero_logit": float(log_loss(labels, np.full(labels.shape, .5), labels=[0, 1])),
                   "trained": float(log_loss(labels, training_scores, labels=[0, 1])),
                   "full_iteration_trace_available": False},
        "warnings": warning_rows,
        "checkpoint": {"path": "checkpoint.pkl", "sha256": sha256_file(checkpoint), "trusted_internal_pickle_only": True,
                       "sklearn_version": importlib.metadata.version("scikit-learn")},
        "model_state_sha256": sha256_file(phase_dir / "model_state.json"),
        "prediction_sha256": sha256_file(predictions_path),
        "metrics": model_metrics([row["label"] for row in target], scores.tolist()),
        "quality_bins": dict(Counter(row["quality_bin"] for row in target)),
        "history_bins": dict(Counter(row["history_bin"] for row in target)),
        "operational_criterion": OPERATIONAL_CRITERION,
        "relation_cutoff_change_from_q2": "New RC3.1 associations < inspection replaces Q2 <= inspection; old Q2 metrics and outputs are unchanged",
        "estimand": "serious deficiency conditional on a Health Standard inspection, not inspection selection",
        "interpretation": "representation sensitivity, not verified ownership quality or a causal mechanism",
        "availability": "retrospective_snapshot_not_origin_verified",
    }
    _json(phase_dir / "result.json", result)
    return result


def preflight(
    source_root: str | Path | None = None, manifest_path: str | Path | None = None,
    baseline_rows_path: str | Path | None = None,
) -> dict[str, Any]:
    """Dependency/schema feasibility only; NEVER fit, predict, or run an experiment."""
    import inspect
    if "max_features" not in inspect.signature(HistGradientBoostingClassifier).parameters:
        raise RuntimeError("RC3.1 CMS requires a sklearn HGB backend supporting max_features")
    result: dict[str, Any] = {
        "versions": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-learn", "threadpoolctl")},
        "health_fit_executed": False, "raw_dependencies": list(SOURCE_FILES),
        "source_import_closure": [
            "healthgraphbench/__init__.py", "healthgraphbench/core.py", "healthgraphbench/data.py",
            "healthgraphbench/tasks/__init__.py", "healthgraphbench/tasks/cms_nursing/__init__.py",
            "healthgraphbench/tasks/cms_nursing/prepare.py", "healthgraphbench/tasks/cms_nursing/models.py",
            "healthgraphbench/tasks/cms_nursing/task.py", "healthgraphbench/rc31/__init__.py",
            "healthgraphbench/rc31/cms.py",
        ],
        "feature_sets": list(FEATURE_SETS), "operational_criterion": OPERATIONAL_CRITERION,
        "fixed_configurations": {"logistic": LOGISTIC_CONFIGURATION, "boosted": BOOSTED_CONFIGURATION},
        "fixed_parameters": {"logistic": LOGISTIC_FIXED, "boosted": BOOSTED_FIXED},
        "cost": {"preparation": "one verified full raw preparation plus strict combined/documented peer aggregation on every Q2 inspection; no row sampling",
                 "fits": "9 logistic + 9 HGB if all training windows <=200000; 3 HGB seeds in each window above 200000 (maximum 36 fits total)",
                 "logistic": "11 local + 0/12 relational + training-state-count columns; at most 1000 lbfgs iterations per fit",
                 "boosted": "100 iterations, 15 leaves, same rows/features; no early stopping or tuning",
                 "memory": "full raw CHOW owners + existing prepared histories/owner maps and inspection peer-history cache; numeric arrays for every training/target row"},
    }
    if source_root is not None:
        root = Path(source_root)
        root = root / "cms" if (root / "cms").is_dir() else root
        missing = [name for name in SOURCE_FILES if not (root / name).is_file()]
        if missing:
            raise FileNotFoundError(f"missing actual CMS raw dependencies: {missing}")
        result["raw_bytes"] = sum((root / name).stat().st_size for name in SOURCE_FILES)
        if manifest_path is not None:
            result["source_files"] = verify_files(root, load_manifest(Path(manifest_path))["cms"]["files"])
    if baseline_rows_path is not None and not Path(baseline_rows_path).is_file():
        raise FileNotFoundError(baseline_rows_path)
    return result
