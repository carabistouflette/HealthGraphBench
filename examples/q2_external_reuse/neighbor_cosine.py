"""Out-of-package Part D cosine-neighbor example and wheel-isolated driver.

The ranker is fitted only from the immutable public ``PartDHistoryView``. Its
binary incidence representation is unsupervised: no target-year labels or loss
function are used.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import resource
import signal
import shutil
import sys
import sysconfig
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


MODEL_NAME = "neighbor_cosine_top50"
NEIGHBOR_COUNT = 50
CHECKPOINT_SCHEMA = "healthgraphbench.external-neighbor-cosine.v1"
_REQUIRED_PACKAGE_SOURCES = {
    "healthgraphbench/core.py",
    "healthgraphbench/candidates/partd.py",
    "healthgraphbench/candidates/partd_model.py",
    "healthgraphbench/data.py",
    "healthgraphbench/q2/common.py",
    "healthgraphbench/q2/reuse.py",
    "healthgraphbench/q2/partd.py",
    "healthgraphbench/tasks/partd/task.py",
}

_RUNTIME_LOADED = False
np: Any
csr_matrix: Any
PredictionSet: Any
PartDHistoryView: Any


def _load_runtime() -> None:
    global _RUNTIME_LOADED, np, csr_matrix, PredictionSet, PartDHistoryView
    if _RUNTIME_LOADED:
        return
    import numpy
    from scipy.sparse import csr_matrix as scipy_csr_matrix

    from healthgraphbench.core import PredictionSet as package_prediction_set
    from healthgraphbench.tasks.partd.task import PartDHistoryView as package_history_view

    np = numpy
    csr_matrix = scipy_csr_matrix
    PredictionSet = package_prediction_set
    PartDHistoryView = package_history_view
    _RUNTIME_LOADED = True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hash_field(digest: Any, value: str) -> None:
    encoded = value.encode("utf-8")
    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)


def _view_sha256(view: PartDHistoryView) -> str:
    digest = hashlib.sha256()
    providers = view.providers
    drugs = view.drugs
    _hash_field(digest, str(view.target_year))
    for year in view.prior_years:
        _hash_field(digest, str(year))
    for provider in providers:
        _hash_field(digest, provider)
    _hash_field(digest, "drugs")
    for drug in drugs:
        _hash_field(digest, drug)
    _hash_field(digest, "provider_drugs")
    for provider in providers:
        _hash_field(digest, provider)
        provider_drugs = sorted(view.provider_drugs.get(provider, ()))
        _hash_field(digest, str(len(provider_drugs)))
        for drug in provider_drugs:
            _hash_field(digest, drug)
    return digest.hexdigest()


def _locked_package_sources(lock_path: Path) -> dict[str, str]:
    try:
        lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read locked package sources: {lock_path}") from exc
    if not isinstance(lock, dict):
        raise ValueError("source lock must be a JSON object")
    sources = lock.get("source_sha256")
    if not isinstance(sources, dict):
        raise ValueError("source lock must contain source_sha256")
    package_sources: dict[str, str] = {}
    for name, digest in sources.items():
        if isinstance(name, str) and name.startswith("healthgraphbench/"):
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError(f"invalid locked source SHA-256 for {name!r}")
            package_sources[name] = digest
    missing = _REQUIRED_PACKAGE_SOURCES.difference(package_sources)
    if missing:
        raise ValueError(
            "scientific protocol does not lock required wheel sources: "
            + ", ".join(sorted(missing))
        )
    return package_sources


def verify_installed_sources(lock_path: Path) -> dict[str, Any]:
    """Prove imports and locked package bytes resolve from this installed wheel."""
    import healthgraphbench
    import healthgraphbench.candidates.partd as partd_candidates
    import healthgraphbench.candidates.partd_model as partd_model
    import healthgraphbench.q2.common as q2_common
    import healthgraphbench.q2.partd as q2_partd
    import healthgraphbench.tasks.partd.task as partd_task

    package_root = Path(healthgraphbench.__file__).resolve().parent
    site_roots = {
        Path(value).resolve()
        for value in (
            sysconfig.get_paths().get("purelib", ""),
            sysconfig.get_paths().get("platlib", ""),
        )
        if value
    }
    package_parent = package_root.parent
    if not site_roots or package_parent not in site_roots:
        raise RuntimeError(
            f"healthgraphbench was not imported from this environment's site-packages: {package_root}"
        )
    distribution = importlib.metadata.distribution("healthgraphbench")
    distribution_root = Path(distribution.locate_file("")).resolve()
    if distribution_root != package_parent:
        raise RuntimeError(
            "installed distribution metadata and imported package resolve to different roots"
        )

    expected = _locked_package_sources(lock_path)
    verified: dict[str, str] = {}
    for relative, expected_sha256 in sorted(expected.items()):
        source = (package_parent / relative).resolve(strict=True)
        try:
            source.relative_to(package_parent)
        except ValueError as exc:
            raise RuntimeError(f"locked wheel source escapes site-packages: {relative}") from exc
        actual_sha256 = _sha256_file(source)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"installed wheel source differs from scientific lock: {relative}"
            )
        verified[relative] = actual_sha256

    imported_modules = {
        "healthgraphbench": Path(healthgraphbench.__file__).resolve(),
        "healthgraphbench.candidates.partd": Path(partd_candidates.__file__).resolve(),
        "healthgraphbench.candidates.partd_model": Path(partd_model.__file__).resolve(),
        "healthgraphbench.q2.common": Path(q2_common.__file__).resolve(),
        "healthgraphbench.q2.partd": Path(q2_partd.__file__).resolve(),
        "healthgraphbench.tasks.partd.task": Path(partd_task.__file__).resolve(),
    }
    for module_path in imported_modules.values():
        try:
            module_path.relative_to(package_root)
        except ValueError as exc:
            raise RuntimeError(f"a benchmark module imported outside the wheel: {module_path}") from exc
    return {
        "package_name": "healthgraphbench",
        "package_version": distribution.version,
        "package_path": str(package_root),
        "site_packages_path": str(package_parent),
        "imported_modules": {name: str(path) for name, path in imported_modules.items()},
        "locked_package_source_sha256": verified,
        "python": {"executable": sys.executable, "version": sys.version},
        "distribution_versions": {
            name: importlib.metadata.version(name)
            for name in ("healthgraphbench", "numpy", "scipy", "scikit-learn", "numba", "threadpoolctl")
        },
    }


@dataclass(slots=True)
class NeighborCosineTop50:
    """Top-50 provider-neighbor cosine ranker fitted to binary incidence."""

    provider_ids: tuple[str, ...]
    drug_ids: tuple[str, ...]
    incidence: csr_matrix
    neighbor_indices: np.ndarray
    neighbor_weights: np.ndarray
    target_year: int
    prior_years: tuple[int, ...]
    scope_sha256: str
    provider_to_index: dict[str, int] = field(init=False, repr=False)
    drug_id_set: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.provider_to_index = {
            provider: index for index, provider in enumerate(self.provider_ids)
        }
        self.drug_id_set = frozenset(self.drug_ids)

    @classmethod
    def fit(cls, view: PartDHistoryView) -> "NeighborCosineTop50":
        _load_runtime()
        if not isinstance(view, PartDHistoryView):
            raise TypeError("cosine ranker fit requires a PartDHistoryView")
        providers = view.providers
        drugs = view.drugs
        if not providers or not drugs:
            raise ValueError("cosine ranker requires a non-empty provider-drug history")
        drug_index = {drug: index for index, drug in enumerate(drugs)}
        indptr = np.zeros(len(providers) + 1, dtype=np.int64)
        columns: list[int] = []
        for row, provider in enumerate(providers):
            row_drugs = sorted(view.provider_drugs.get(provider, ()))
            try:
                columns.extend(drug_index[drug] for drug in row_drugs)
            except KeyError as exc:
                raise ValueError("history view provider-drug incidence is inconsistent") from exc
            indptr[row + 1] = len(columns)
        indices = np.asarray(columns, dtype=np.int32)
        incidence = csr_matrix(
            (np.ones(indices.size, dtype=np.float64), indices, indptr),
            shape=(len(providers), len(drugs)),
            dtype=np.float64,
        )
        incidence.sort_indices()

        row_norms = np.sqrt(np.asarray(incidence.multiply(incidence).sum(axis=1)).ravel())
        inverse_norms = np.zeros_like(row_norms)
        nonzero_norms = row_norms > 0.0
        inverse_norms[nonzero_norms] = 1.0 / row_norms[nonzero_norms]
        cosine = (incidence @ incidence.T).tocsr()
        cosine.sort_indices()
        for row in range(len(providers)):
            start, stop = int(cosine.indptr[row]), int(cosine.indptr[row + 1])
            if inverse_norms[row] == 0.0:
                cosine.data[start:stop] = 0.0
            else:
                columns_for_row = cosine.indices[start:stop]
                cosine.data[start:stop] *= (
                    inverse_norms[row] * inverse_norms[columns_for_row]
                )
                np.clip(cosine.data[start:stop], 0.0, 1.0, out=cosine.data[start:stop])

        neighbor_count = min(NEIGHBOR_COUNT, max(0, len(providers) - 1))
        neighbor_indices = np.empty((len(providers), neighbor_count), dtype=np.int32)
        neighbor_weights = np.empty((len(providers), neighbor_count), dtype=np.float64)
        provider_names = np.asarray(providers, dtype=np.str_)
        all_indices = np.arange(len(providers), dtype=np.int32)
        for row in range(len(providers)):
            row_similarity = np.zeros(len(providers), dtype=np.float64)
            start, stop = int(cosine.indptr[row]), int(cosine.indptr[row + 1])
            row_similarity[cosine.indices[start:stop]] = cosine.data[start:stop]
            other_indices = all_indices[all_indices != row]
            order = np.lexsort(
                (provider_names[other_indices], -row_similarity[other_indices])
            )
            selected = other_indices[order[:neighbor_count]]
            neighbor_indices[row] = selected
            neighbor_weights[row] = row_similarity[selected]

        model = cls(
            provider_ids=providers,
            drug_ids=drugs,
            incidence=incidence,
            neighbor_indices=neighbor_indices,
            neighbor_weights=neighbor_weights,
            target_year=int(view.target_year),
            prior_years=tuple(int(year) for year in view.prior_years),
            scope_sha256=_view_sha256(view),
        )
        return model

    def assert_compatible(self, view: PartDHistoryView) -> None:
        if (
            int(view.target_year) != self.target_year
            or tuple(int(year) for year in view.prior_years) != self.prior_years
            or view.providers != self.provider_ids
            or view.drugs != self.drug_ids
            or _view_sha256(view) != self.scope_sha256
        ):
            raise ValueError("cosine checkpoint does not match the supplied history view")

    def _score_candidates(
        self, npi: str, candidate_ids: tuple[str, ...]
    ) -> dict[str, float]:
        _load_runtime()
        if not self.drug_id_set.issuperset(candidate_ids):
            raise ValueError("ranker candidate is absent from its fitted history view")
        row = self.provider_to_index.get(npi)
        if row is None or not candidate_ids:
            return {drug: 0.0 for drug in candidate_ids}
        neighbors = self.neighbor_indices[row]
        weights = self.neighbor_weights[row]
        if not neighbors.size or not np.any(weights):
            return {drug: 0.0 for drug in candidate_ids}
        neighbor_matrix = self.incidence[neighbors]
        weight_row = csr_matrix(weights.reshape(1, -1))
        weight_row.eliminate_zeros()
        aggregate = (weight_row @ neighbor_matrix).tocsr()
        drug_scores = {
            self.drug_ids[int(index)]: float(value)
            for index, value in zip(aggregate.indices, aggregate.data, strict=True)
        }
        return {drug: drug_scores.get(drug, 0.0) for drug in candidate_ids}

    def score_candidates(
        self,
        view: PartDHistoryView,
        npi: str,
        candidate_ids: tuple[str, ...],
    ) -> dict[str, float]:
        """Score every supplied candidate after checking exact checkpoint scope."""
        self.assert_compatible(view)
        return self._score_candidates(npi, candidate_ids)

    def save(self, path: Path) -> dict[str, Any]:
        _load_runtime()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"refusing to overwrite cosine checkpoint: {path}")
        with path.open("xb") as checkpoint:
            np.savez_compressed(
                checkpoint,
                schema=np.asarray(CHECKPOINT_SCHEMA),
                provider_ids=np.asarray(self.provider_ids, dtype=np.str_),
                drug_ids=np.asarray(self.drug_ids, dtype=np.str_),
                incidence_data=self.incidence.data,
                incidence_indices=self.incidence.indices,
                incidence_indptr=self.incidence.indptr,
                incidence_shape=np.asarray(self.incidence.shape, dtype=np.int64),
                neighbor_indices=self.neighbor_indices,
                neighbor_weights=self.neighbor_weights,
                target_year=np.asarray(self.target_year, dtype=np.int64),
                prior_years=np.asarray(self.prior_years, dtype=np.int64),
                scope_sha256=np.asarray(self.scope_sha256),
                neighbor_limit=np.asarray(NEIGHBOR_COUNT, dtype=np.int64),
            )
        return {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }

    @classmethod
    def load(cls, path: Path) -> "NeighborCosineTop50":
        _load_runtime()
        with np.load(Path(path), allow_pickle=False) as checkpoint:
            schema = str(checkpoint["schema"].item())
            if schema != CHECKPOINT_SCHEMA:
                raise ValueError(f"unsupported cosine checkpoint schema: {schema!r}")
            if int(checkpoint["neighbor_limit"].item()) != NEIGHBOR_COUNT:
                raise ValueError("cosine checkpoint has a different neighbor limit")
            provider_ids = tuple(str(value) for value in checkpoint["provider_ids"].tolist())
            drug_ids = tuple(str(value) for value in checkpoint["drug_ids"].tolist())
            shape = tuple(int(value) for value in checkpoint["incidence_shape"].tolist())
            if shape != (len(provider_ids), len(drug_ids)):
                raise ValueError("cosine checkpoint incidence shape is inconsistent")
            incidence = csr_matrix(
                (
                    checkpoint["incidence_data"].copy(),
                    checkpoint["incidence_indices"].copy(),
                    checkpoint["incidence_indptr"].copy(),
                ),
                shape=shape,
            )
            neighbor_indices = checkpoint["neighbor_indices"].copy()
            neighbor_weights = checkpoint["neighbor_weights"].copy()
            target_year = int(checkpoint["target_year"].item())
            prior_years = tuple(int(value) for value in checkpoint["prior_years"].tolist())
            scope_sha256 = str(checkpoint["scope_sha256"].item())
        if (
            neighbor_indices.ndim != 2
            or neighbor_weights.shape != neighbor_indices.shape
            or neighbor_indices.shape[0] != len(provider_ids)
            or neighbor_indices.shape[1] > NEIGHBOR_COUNT
            or (neighbor_indices.size and (
                int(neighbor_indices.min()) < 0
                or int(neighbor_indices.max()) >= len(provider_ids)
                or np.any(
                    neighbor_indices
                    == np.arange(len(provider_ids), dtype=neighbor_indices.dtype)[:, None]
                )
            ))
            or not np.isfinite(neighbor_weights).all()
            or np.any(neighbor_weights < 0.0)
            or np.any(neighbor_weights > 1.0)
            or len(set(provider_ids)) != len(provider_ids)
            or len(set(drug_ids)) != len(drug_ids)
            or tuple(sorted(provider_ids)) != provider_ids
            or tuple(sorted(drug_ids)) != drug_ids
            or incidence.nnz != incidence.data.size
            or not incidence.has_canonical_format
            or not np.isfinite(incidence.data).all()
            or np.any(incidence.data != 1.0)
            or len(scope_sha256) != 64
            or tuple(sorted(prior_years)) != prior_years
        ):
            raise ValueError("cosine checkpoint matrices or identifiers are invalid")
        return cls(
            provider_ids,
            drug_ids,
            incidence,
            neighbor_indices,
            neighbor_weights,
            target_year,
            prior_years,
            scope_sha256,
        )


def fit_predict(
    train: Any,
    validation: Any,
    test: Any,
    *,
    checkpoint_dir: Path | None = None,
) -> PredictionSet:
    """Fit through public Part D history views and ``task.predict_ranker``."""
    _load_runtime()
    task = getattr(train, "task", None)
    predict_ranker = getattr(task, "predict_ranker", None)
    if not callable(predict_ranker):
        raise TypeError("train must be a Part D split with the public predict_ranker API")
    checkpoint_root = Path(checkpoint_dir).resolve() if checkpoint_dir is not None else None
    fitted: dict[int, NeighborCosineTop50] = {}
    checked_views: dict[int, int] = {}
    fit_records: dict[int, dict[str, Any]] = {}

    def score(
        view: PartDHistoryView,
        npi: str,
        candidates: tuple[str, ...],
    ) -> Mapping[str, float]:
        year = int(view.target_year)
        model = fitted.get(year)
        if model is None:
            original = NeighborCosineTop50.fit(view)
            checkpoint_record: dict[str, Any] | None = None
            reload_verified = False
            reload_probe_candidates = 0
            if checkpoint_root is not None:
                checkpoint = checkpoint_root / f"target_year_{year}" / "checkpoint.npz"
                checkpoint_record = original.save(checkpoint)
                model = NeighborCosineTop50.load(checkpoint)
                model.assert_compatible(view)
                if view.providers:
                    probe_npi = view.providers[0]
                    probe_candidates: tuple[str, ...] = ()
                    for provider in view.providers:
                        provider_candidates = tuple(view.candidate_ids(provider))
                        if provider_candidates:
                            probe_npi = provider
                            probe_candidates = provider_candidates
                            break
                    if not probe_candidates:
                        raise ValueError(
                            "cosine checkpoint reload verification requires candidate drugs"
                        )
                    original_scores = original.score_candidates(
                        view, probe_npi, probe_candidates
                    )
                    reloaded_scores = model.score_candidates(
                        view, probe_npi, probe_candidates
                    )
                    if original_scores != reloaded_scores:
                        raise RuntimeError("cosine checkpoint reload changed model scores")
                    reload_verified = True
                    reload_probe_candidates = len(probe_candidates)
            else:
                model = original
            fitted[year] = model
            fit_records[year] = {
                "model_name": MODEL_NAME,
                "fit_algorithm": "cosine similarity over binary provider-by-generic-drug incidence",
                "fit_scope": {
                    "target_year": year,
                    "prior_years": list(view.prior_years),
                    "provider_count": len(view.providers),
                    "generic_drug_count": len(view.drugs),
                    "incidence_nonzero": int(model.incidence.nnz),
                    "scope_sha256": model.scope_sha256,
                },
                "neighbors": {
                    "maximum": NEIGHBOR_COUNT,
                    "actual_per_provider": int(model.neighbor_indices.shape[1]),
                    "sort_order": "cosine descending, NPI ascending; self excluded",
                },
                "supervision": {
                    "objective": "unsupervised binary-incidence fit",
                    "target_year_labels_used": False,
                    "loss": None,
                    "random_seed": None,
                    "tuning": "none",
                },
                "checkpoint": checkpoint_record,
                "reload_score_identity_verified": reload_verified,
                "reload_score_probe_candidate_count": reload_probe_candidates,
            }
        if checked_views.get(year) != id(view):
            model.assert_compatible(view)
            checked_views[year] = id(view)
        return model._score_candidates(npi, candidates)

    predictions = predict_ranker(
        MODEL_NAME,
        train,
        validation,
        test,
        score,
    )
    if not isinstance(predictions.payload, dict):
        raise TypeError("Part D predict_ranker returned a non-mapping payload")
    payload = dict(predictions.payload)
    payload["external_model_fit"] = {
        "model_name": MODEL_NAME,
        "fit_records_by_target_year": {
            str(year): fit_records[year] for year in sorted(fit_records)
        },
    }
    return PredictionSet(
        task_name=predictions.task_name,
        method=predictions.method,
        split=predictions.split,
        payload=payload,
    )


def _write_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")

def _replace_json(path: Path, value: Any) -> None:
    with Path(path).open("w", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _descendant_pids() -> list[int]:
    pending = [os.getpid()]
    descendants: list[int] = []
    while pending:
        pid = pending.pop()
        try:
            child_text = Path(f"/proc/{pid}/task/{pid}/children").read_text(
                encoding="ascii"
            )
        except (OSError, UnicodeError):
            continue
        children = [int(value) for value in child_text.split()]
        descendants.extend(children)
        pending.extend(children)
    return descendants


def _terminate_descendants(signum: int, _frame: Any) -> None:
    for pid in reversed(_descendant_pids()):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    raise SystemExit(128 + signum)


def _run_supervised_phase(
    phase_dir: Path,
    operation: Any,
) -> dict[str, Any]:
    phase_dir = Path(phase_dir).resolve(strict=True)
    signal.signal(signal.SIGTERM, _terminate_descendants)
    signal.signal(signal.SIGINT, _terminate_descendants)
    started_wall = time.monotonic()
    started_cpu = time.process_time()
    _replace_json(
        phase_dir / "worker_status.json",
        {"status": "running", "pid": os.getpid()},
    )
    try:
        result = operation()
        _write_json(phase_dir / "result.json", result)
        _replace_json(
            phase_dir / "worker_status.json",
            {
                "status": "complete",
                "pid": os.getpid(),
                "wall_seconds": time.monotonic() - started_wall,
                "cpu_seconds": time.process_time() - started_cpu,
                "peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024,
            },
        )
        return result
    except BaseException as exc:
        _write_json(
            phase_dir / "worker_error.json",
            {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        _replace_json(
            phase_dir / "worker_status.json",
            {
                "status": "incomplete",
                "pid": os.getpid(),
                "cpu_seconds": time.process_time() - started_cpu,
                "peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024,
            },
        )
        raise


def _protocol_model_spec(protocol_path: Path) -> dict[str, Any]:
    try:
        protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read external-reuse protocol: {protocol_path}") from exc
    external_reuse = protocol.get("external_reuse") if isinstance(protocol, dict) else None
    spec = external_reuse.get(MODEL_NAME) if isinstance(external_reuse, dict) else None
    if not isinstance(spec, dict):
        raise ValueError(f"protocol is missing external_reuse.{MODEL_NAME}")
    expected = {
        "model_name": MODEL_NAME,
        "neighbor_count": NEIGHBOR_COUNT,
        "fit_representation": "binary_provider_by_generic_drug_incidence",
        "tuning": "none",
        "fit_scope": {
            "validation_target_year": 2023,
            "validation_prior_years": [2019, 2020, 2021, 2022],
            "test_target_year": 2024,
            "test_prior_years": [2019, 2020, 2021, 2022, 2023],
        },
        "loss": "none_unsupervised",
    }
    if spec != expected:
        raise ValueError(
            f"protocol external_reuse.{MODEL_NAME} does not match the fixed model contract"
        )
    return spec


def _run_preflight(lock_path: Path, output_path: Path) -> dict[str, Any]:
    package = verify_installed_sources(lock_path)
    proof = {
        "status": "complete",
        "package": package,
        "preflight_before_any_fit": True,
    }
    _write_json(output_path, proof)
    return proof


def _run_demonstration(
    source_root: Path,
    manifest_path: Path,
    contract_path: Path,
    output_dir: Path,
    protocol_path: Path,
    source_lock_path: Path,
    cohort_size: int,
) -> dict[str, Any]:
    from healthgraphbench.tasks.partd.task import PartDTask

    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to reuse external-reuse output: {output_dir}")
    output_dir.mkdir(parents=True)
    source_root = Path(source_root).resolve(strict=True)
    manifest_path = Path(manifest_path).resolve(strict=True)
    contract_path = Path(contract_path).resolve(strict=True)
    protocol_path = Path(protocol_path).resolve(strict=True)
    source_lock_path = Path(source_lock_path).resolve(strict=True)
    spec = _protocol_model_spec(protocol_path)
    package_provenance = verify_installed_sources(source_lock_path)
    driver_path = Path(__file__).resolve()
    driver_sha256 = _sha256_file(driver_path)
    source_lock = json.loads(source_lock_path.read_text(encoding="utf-8"))
    locked_driver_sha256 = source_lock["source_sha256"].get(
        "examples/q2_external_reuse/neighbor_cosine.py"
    )
    if driver_sha256 != locked_driver_sha256:
        raise RuntimeError("out-of-tree driver bytes differ from the scientific source lock")

    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir()
    shutil.copyfile(manifest_path, inputs_dir / "partd_manifest.json")
    shutil.copyfile(contract_path, inputs_dir / "task_contract.json")

    preparation_dir = output_dir / "preparation"
    task = PartDTask.from_source_root(
        source_root,
        manifest_path=manifest_path,
        preparation_dir=preparation_dir,
        contract_path=contract_path,
        cohort_size=cohort_size,
    )
    splits = tuple(task.get_split(name) for name in ("train", "validation", "test"))
    checkpoint_dir = output_dir / "checkpoints"
    neural_predictions = fit_predict(
        *splits,
        checkpoint_dir=checkpoint_dir,
    )
    builtin_predictions = task.fit_predict("tabular_logistic", *splits)
    neural_test_metrics = task.evaluate(neural_predictions)
    builtin_test_metrics = task.evaluate(builtin_predictions)
    neural_payload = neural_predictions.payload
    builtin_payload = builtin_predictions.payload
    if not isinstance(neural_payload, dict) or not isinstance(builtin_payload, dict):
        raise TypeError("prediction payloads must be JSON-compatible mappings")
    if neural_test_metrics != neural_payload.get("test"):
        raise RuntimeError("public Part D evaluation did not reproduce cosine test metrics")
    if builtin_test_metrics != builtin_payload.get("test"):
        raise RuntimeError("public Part D evaluation did not reproduce logistic test metrics")

    source_files = task.source_manifest()
    source_file = output_dir / "source_files.json"
    _write_json(source_file, source_files)
    predictions_path = output_dir / "prediction_payloads.json"
    _write_json(
        predictions_path,
        {
            "neighbor_cosine_top50": neural_payload,
            "tabular_logistic": builtin_payload,
        },
    )
    metrics_path = output_dir / "metrics_recalculated.json"
    _write_json(
        metrics_path,
        {
            "neighbor_cosine_top50": {
                "validation_metrics": neural_payload["validation"],
                "test_metrics_recalculated_with_public_task_evaluate": neural_test_metrics,
                "matches_ranker_test_metrics": True,
            },
            "tabular_logistic": {
                "validation_metrics": builtin_payload["validation"],
                "test_metrics_recalculated_with_public_task_evaluate": builtin_test_metrics,
                "matches_ranker_test_metrics": True,
            },
        },
    )
    preparation_report = json.loads((preparation_dir / "report.json").read_text(encoding="utf-8"))
    checkpoint_records = neural_payload["external_model_fit"]["fit_records_by_target_year"]
    if set(checkpoint_records) != {"2023", "2024"}:
        raise RuntimeError("cosine ranker did not create both temporal history fits")
    if any(
        not record.get("checkpoint") or not record.get("reload_score_identity_verified")
        for record in checkpoint_records.values()
    ):
        raise RuntimeError("cosine ranker checkpoints were not saved and score-verified after reload")

    artifact_paths = [
        inputs_dir / "partd_manifest.json",
        inputs_dir / "task_contract.json",
        preparation_dir / "report.json",
        preparation_dir / "edges.csv",
        source_file,
        predictions_path,
        metrics_path,
    ]
    for record in checkpoint_records.values():
        artifact_paths.append(Path(record["checkpoint"]["path"]))
    artifacts = {
        str(path.relative_to(output_dir)): {
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in sorted(artifact_paths)
    }
    result = {
        "status": "complete",
        "model_name": MODEL_NAME,
        "built_in_comparator": "tabular_logistic",
        "protocol_model_spec": spec,
        "package": package_provenance,
        "driver": {
            "path": str(driver_path),
            "sha256": driver_sha256,
            "locked_source_sha256": locked_driver_sha256,
            "module_path_is_out_of_package": True,
        },
        "preparation": {
            "raw_source_root": str(source_root),
            "manifest_path": str(manifest_path),
            "manifest_sha256": _sha256_file(manifest_path),
            "contract_path": str(contract_path),
            "contract_sha256": _sha256_file(contract_path),
            "preparation_report_sha256": _sha256_file(preparation_dir / "report.json"),
            "source_file_count": len(source_files),
            "raw_sources": source_files,
            "cohort_size_requested": int(cohort_size),
            "cohort_size_by_target_year": {
                str(year): len(providers)
                for year, providers in preparation_report.get("cohort", {}).get(
                    "by_target_year", {}
                ).items()
            },
        },
        "fits": {
            "neighbor_cosine_top50": checkpoint_records,
            "tabular_logistic": {
                "method": "public PartDTask.fit_predict('tabular_logistic', ...)",
                "evaluation": "public PartDTask.evaluate recalculated test metrics",
            },
        },
        "predictions_path": str(predictions_path.resolve()),
        "metrics_path": str(metrics_path.resolve()),
        "source_files_path": str(source_file.resolve()),
        "artifacts": artifacts,
        "evidence": {
            "historically_consulted_2019_2024_periods_are_exploratory": True,
            "independent_public_availability_at_origin_established": False,
            "external_human_participant_validation": "pending",
            "technical_assistant_run_is_not_external_human_validation": True,
            "performance_comparison_is_not_independent_validation": True,
            "target_year_labels_used_by_cosine_fit": False,
            "cosine_loss_invented": False,
        },
    }
    _write_json(output_dir / "result.json", result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--preflight-output", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--cohort-size", type=int, default=2000)
    parser.add_argument("--phase-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.preflight:
        if args.preflight_output is None:
            raise ValueError("preflight requires --preflight-output")
        if not args.source_lock.is_absolute() or not args.preflight_output.is_absolute():
            raise ValueError("preflight source-lock and output paths must be absolute")

        def preflight() -> dict[str, Any]:
            return {
                "status": "complete",
                "preflight": _run_preflight(args.source_lock, args.preflight_output),
            }

        phase_result = (
            _run_supervised_phase(args.phase_dir, preflight)
            if args.phase_dir is not None
            else preflight()
        )
    else:
        required = (
            args.source_root,
            args.manifest,
            args.contract,
            args.output_dir,
            args.protocol,
        )
        if any(value is None for value in required):
            raise ValueError(
                "demonstration requires --source-root, --manifest, --contract, --output-dir, and --protocol"
            )
        input_paths = (
            args.source_lock,
            args.source_root,
            args.manifest,
            args.contract,
            args.output_dir,
            args.protocol,
        )
        if any(not path.is_absolute() for path in input_paths):
            raise ValueError("source-lock and all demonstration paths must be absolute")

        def demonstration() -> dict[str, Any]:
            driver_result = _run_demonstration(
                args.source_root,
                args.manifest,
                args.contract,
                args.output_dir,
                args.protocol,
                args.source_lock,
                args.cohort_size,
            )
            result_path = args.output_dir.resolve() / "result.json"
            return {
                "status": "complete",
                "driver_result_path": str(result_path),
                "driver_result_sha256": _sha256_file(result_path),
                "driver_result": driver_result,
            }

        phase_result = (
            _run_supervised_phase(args.phase_dir, demonstration)
            if args.phase_dir is not None
            else demonstration()
        )
    print(json.dumps(phase_result, ensure_ascii=False, allow_nan=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
