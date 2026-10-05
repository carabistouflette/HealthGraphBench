"""Wheel-isolated, provenance-locked external Part D reuse demonstration."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import traceback
from pathlib import Path
from typing import Any, Mapping

from . import common

MODEL_NAME = "neighbor_cosine_top50"
_DRIVER_RELATIVE = Path("examples/q2_external_reuse/neighbor_cosine.py")
_REQUIRED_LOCKED_PACKAGE_SOURCES = {
    "healthgraphbench/core.py",
    "healthgraphbench/candidates/partd.py",
    "healthgraphbench/candidates/partd_model.py",
    "healthgraphbench/data.py",
    "healthgraphbench/q2/common.py",
    "healthgraphbench/q2/partd.py",
    "healthgraphbench/q2/reuse.py",
    "healthgraphbench/tasks/partd/task.py",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read Q2 reuse evidence {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Q2 reuse evidence must be a JSON object: {path}")
    return value


def _protocol_layout(protocol: Mapping[str, Any]) -> tuple[Path, Path, int, dict[str, Any]]:
    tasks = protocol.get("tasks")
    partd = tasks.get("partd") if isinstance(tasks, Mapping) else None
    if not isinstance(partd, Mapping):
        raise ValueError("Q2 protocol is missing tasks.partd")
    manifest_value = partd.get("source_manifest")
    if not isinstance(manifest_value, str) or not manifest_value:
        raise ValueError("Q2 protocol tasks.partd.source_manifest is required")
    manifest_relative = Path(manifest_value)
    if manifest_relative.is_absolute():
        raise ValueError("Q2 Part D manifest path must be repository-relative")
    repo_root = common.REPO_ROOT.resolve(strict=True)
    manifest_path = (repo_root / manifest_relative).resolve(strict=True)
    try:
        manifest_path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("Q2 Part D manifest escapes the parent repository") from exc
    contract_path = (repo_root / "configs" / "task_contract_v0_2.json").resolve(strict=True)
    cohort_size = partd.get("cohort_size")
    if isinstance(cohort_size, bool) or not isinstance(cohort_size, int) or cohort_size <= 0:
        raise ValueError("Q2 protocol Part D cohort_size must be a positive integer")
    if partd.get("validation_year") != 2023 or partd.get("test_years") != [2024]:
        raise ValueError("external reuse is locked to validation 2023 and test 2024")
    external = protocol.get("external_reuse")
    if not isinstance(external, Mapping):
        raise ValueError("Q2 protocol external_reuse section is required")
    if external.get("human_participant_required") is not True:
        raise ValueError("external human-participant validation must remain required")
    if external.get("technical_assistant_run_is_not_external_human_validation") is not True:
        raise ValueError("technical execution must not be represented as human validation")
    spec = external.get(MODEL_NAME)
    expected_spec = {
        "model_name": MODEL_NAME,
        "neighbor_count": 50,
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
    if spec != expected_spec:
        raise ValueError(f"protocol external_reuse.{MODEL_NAME} does not match the fixed contract")
    return manifest_path, contract_path, cohort_size, dict(spec)


def _source_lock_from_provenance(output_dir: Path, driver_path: Path) -> tuple[Path, dict[str, str], str]:
    provenance = _read_json(output_dir / "source_provenance.json")
    source_hashes = provenance.get("source_sha256")
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise ValueError("committed protocol provenance contains no locked source hashes")
    normalized: dict[str, str] = {}
    for name, digest in source_hashes.items():
        if not isinstance(name, str) or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("committed protocol provenance contains an invalid source hash")
        normalized[name] = digest
    missing = _REQUIRED_LOCKED_PACKAGE_SOURCES.difference(normalized)
    if missing:
        raise ValueError(
            "Q2 scientific protocol does not lock required installed package sources: "
            + ", ".join(sorted(missing))
        )
    driver_relative = _DRIVER_RELATIVE.as_posix()
    expected_driver_sha256 = normalized.get(driver_relative)
    if expected_driver_sha256 is None:
        raise ValueError(f"Q2 scientific protocol does not lock {driver_relative}")
    actual_driver_sha256 = _sha256_file(driver_path)
    if actual_driver_sha256 != expected_driver_sha256:
        raise ValueError("external driver bytes differ from committed scientific provenance")
    source_lock = output_dir / "wheel_source_lock.json"
    _write_json(source_lock, {"source_sha256": normalized})
    return source_lock, normalized, actual_driver_sha256


def _thread_limited_environment(python: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["GIT_CEILING_DIRECTORIES"] = str(Path(python).parent.parent)
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMBA_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        environment[name] = "1"
    return environment


def _exec_driver(
    python: Path,
    driver_copy: Path,
    command_arguments: list[str],
    phase_dir: Path,
) -> None:
    python = Path(python)
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError(f"reuse_python must identify an executable environment Python: {python}")
    stdout_fd = os.open(
        phase_dir / "driver.stdout.log",
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    stderr_fd = os.open(
        phase_dir / "driver.stderr.log",
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        os.dup2(stdout_fd, 1)
        os.dup2(stderr_fd, 2)
    finally:
        os.close(stdout_fd)
        os.close(stderr_fd)
    os.chdir(Path(phase_dir).resolve(strict=True))
    command = [
        str(python),
        "-I",
        str(Path(driver_copy).resolve(strict=True)),
        *command_arguments,
        "--phase-dir",
        str(Path(phase_dir).resolve(strict=True)),
    ]
    os.execve(str(python), command, _thread_limited_environment(python))


def _copy_driver(driver_path: Path, phase_dir: Path, expected_sha256: str) -> Path:
    destination = phase_dir / "neighbor_cosine.py"
    shutil.copyfile(driver_path, destination)
    if _sha256_file(destination) != expected_sha256:
        raise RuntimeError("out-of-tree driver copy differs from the locked source bytes")
    return destination


def _preflight_worker(
    python: Path,
    driver_path: Path,
    expected_driver_sha256: str,
    source_lock: Path,
    phase_dir: Path,
) -> None:
    driver_copy = _copy_driver(driver_path, phase_dir, expected_driver_sha256)
    proof_path = phase_dir / "preflight.json"
    _exec_driver(
        python,
        driver_copy,
        [
            "--preflight",
            "--source-lock",
            str(source_lock.resolve(strict=True)),
            "--preflight-output",
            str(proof_path.resolve()),
        ],
        phase_dir,
    )


def _demonstration_worker(
    python: Path,
    driver_path: Path,
    expected_driver_sha256: str,
    source_lock: Path,
    source_root: Path,
    manifest_path: Path,
    contract_path: Path,
    executed_protocol_path: Path,
    cohort_size: int,
    phase_dir: Path,
) -> None:
    driver_copy = _copy_driver(driver_path, phase_dir, expected_driver_sha256)
    demonstration_dir = phase_dir / "demonstration_output"
    _exec_driver(
        python,
        driver_copy,
        [
            "--source-root",
            str(source_root.resolve(strict=True)),
            "--manifest",
            str(manifest_path.resolve(strict=True)),
            "--contract",
            str(contract_path.resolve(strict=True)),
            "--output-dir",
            str(demonstration_dir.resolve()),
            "--protocol",
            str(executed_protocol_path.resolve(strict=True)),
            "--source-lock",
            str(source_lock.resolve(strict=True)),
            "--cohort-size",
            str(cohort_size),
        ],
        phase_dir,
    )


def _verify_preflight(proof: Mapping[str, Any], source_hashes: Mapping[str, str]) -> None:
    if proof.get("status") != "complete" or proof.get("preflight_before_any_fit") is not True:
        raise RuntimeError("wheel import/source preflight did not produce complete proof")
    package = proof.get("package")
    if not isinstance(package, Mapping):
        raise RuntimeError("wheel source preflight omitted package provenance")
    package_path = package.get("package_path")
    site_packages = package.get("site_packages_path")
    if not isinstance(package_path, str) or not isinstance(site_packages, str):
        raise RuntimeError("wheel preflight did not identify the imported package path")
    Path(package_path).resolve().relative_to(Path(site_packages).resolve())
    verified = package.get("locked_package_source_sha256")
    if not isinstance(verified, Mapping):
        raise RuntimeError("wheel preflight omitted locked package source hashes")
    expected = {
        name: digest
        for name, digest in source_hashes.items()
        if name.startswith("healthgraphbench/")
    }
    if dict(verified) != expected:
        raise RuntimeError("wheel preflight did not verify every locked package source")


def _validate_phase(phase_dir: Path, supervisor: Mapping[str, Any]) -> dict[str, Any]:
    if supervisor.get("status") != "complete":
        raise RuntimeError(f"Q2 supervised phase is incomplete: {supervisor}")
    worker = _read_json(phase_dir / "worker_status.json")
    if worker.get("status") != "complete":
        raise RuntimeError(f"Q2 phase process did not record completion: {worker}")
    if worker.get("pid") != supervisor.get("pid"):
        raise RuntimeError("exec-replaced driver PID differs from its supervised worker PID")
    if not isinstance(worker.get("cpu_seconds"), (int, float)):
        raise RuntimeError("phase worker omitted CPU accounting")
    if not isinstance(worker.get("peak_rss_bytes"), (int, float)):
        raise RuntimeError("phase worker omitted peak RSS accounting")
    result = _read_json(phase_dir / "result.json")
    if result.get("status") != "complete":
        raise RuntimeError(f"Q2 phase process did not write complete evidence: {result}")
    return result


def _validate_demonstration_artifacts(
    phase_dir: Path,
    driver_result: Mapping[str, Any],
) -> None:
    demonstration_dir = (phase_dir / "demonstration_output").resolve(strict=True)
    artifact_map = driver_result.get("artifacts")
    if not isinstance(artifact_map, dict) or not artifact_map:
        raise RuntimeError("external driver did not export a checksummed artifact manifest")
    for relative, expected in artifact_map.items():
        if not isinstance(relative, str) or not isinstance(expected, dict):
            raise RuntimeError("external artifact manifest is malformed")
        artifact = (demonstration_dir / relative).resolve(strict=True)
        artifact.relative_to(demonstration_dir)
        if (
            artifact.stat().st_size != expected.get("bytes")
            or _sha256_file(artifact) != expected.get("sha256")
        ):
            raise RuntimeError(f"external driver artifact failed integrity verification: {relative}")
    if driver_result.get("model_name") != MODEL_NAME:
        raise RuntimeError("external driver completed a different model")
    if driver_result.get("built_in_comparator") != "tabular_logistic":
        raise RuntimeError("external driver omitted the requested public built-in comparator")
    evidence = driver_result.get("evidence")
    if (
        not isinstance(evidence, dict)
        or evidence.get("external_human_participant_validation") != "pending"
        or evidence.get("independent_public_availability_at_origin_established") is not False
    ):
        raise RuntimeError("external driver misrepresented its independent/human evidence gate")

    prediction_path = Path(str(driver_result.get("predictions_path", ""))).resolve(strict=True)
    metrics_path = Path(str(driver_result.get("metrics_path", ""))).resolve(strict=True)
    prediction_path.relative_to(demonstration_dir)
    metrics_path.relative_to(demonstration_dir)
    prediction_payloads = _read_json(prediction_path)
    recalculated_metrics = _read_json(metrics_path)
    for model_name in (MODEL_NAME, "tabular_logistic"):
        prediction = prediction_payloads.get(model_name)
        metrics = recalculated_metrics.get(model_name)
        if not isinstance(prediction, dict) or not isinstance(metrics, dict):
            raise RuntimeError(f"external driver omitted payload or metrics for {model_name}")
        if not prediction.get("validation_predictions") or not prediction.get("test_predictions"):
            raise RuntimeError(f"external driver exported no scored rows for {model_name}")
        if (
            metrics.get("test_metrics_recalculated_with_public_task_evaluate")
            != prediction.get("test")
            or metrics.get("matches_ranker_test_metrics") is not True
        ):
            raise RuntimeError(f"public evaluation metrics do not match {model_name} payload")
    fit_records = prediction_payloads[MODEL_NAME].get("external_model_fit", {}).get(
        "fit_records_by_target_year"
    )
    if not isinstance(fit_records, dict) or set(fit_records) != {"2023", "2024"}:
        raise RuntimeError("external payload omitted both target-year cosine fits")
    if any(
        record.get("checkpoint") is None
        or record.get("reload_score_identity_verified") is not True
        or not isinstance(record.get("reload_score_probe_candidate_count"), int)
        or record.get("reload_score_probe_candidate_count", 0) <= 0
        for record in fit_records.values()
    ):
        raise RuntimeError("external payload omitted real score-verified checkpoints")



def run_demonstration(
    source_root: Path,
    output_dir: Path,
    protocol: Path,
    protocol_sha256: str,
    reuse_python: Path,
    limits: Mapping[str, int | float] | None = None,
) -> dict[str, Any]:
    """Run the raw-to-evaluation demonstration in a locked installed wheel.

    The parent repository validates the committed protocol before any wheel
    process starts. A site-packages preflight then verifies every locked package
    byte before the out-of-tree driver is allowed to prepare or fit data.
    """
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to reuse Q2 external-reuse output: {output_dir}")
    protocol_path = Path(protocol).resolve(strict=True)
    source_root = Path(source_root).resolve(strict=True)
    python = Path(reuse_python).expanduser()
    if not python.is_absolute():
        python = Path.cwd() / python
    python = Path(os.path.abspath(python))
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError(f"reuse_python must identify an executable environment Python: {python}")
    loaded_protocol = common.load_protocol(protocol_path, protocol_sha256, output_dir)
    effective_limits: dict[str, int | float] = dict(common.DEFAULT_LIMITS)
    protocol_limits = loaded_protocol.get("limits")
    if not isinstance(protocol_limits, Mapping):
        raise ValueError("committed Q2 protocol is missing limits")
    effective_limits.update(protocol_limits)
    if limits is not None:
        effective_limits.update(limits)
    manifest_path, contract_path, cohort_size, spec = _protocol_layout(loaded_protocol)
    repo_root = common.REPO_ROOT.resolve(strict=True)
    provenance = _read_json(output_dir / "source_provenance.json")
    source_hashes = provenance.get("source_sha256")
    if not isinstance(source_hashes, dict):
        raise ValueError("committed Q2 source provenance is missing source_sha256")
    manifest_relative = manifest_path.relative_to(repo_root).as_posix()
    contract_relative = contract_path.relative_to(repo_root).as_posix()
    for relative, path in ((manifest_relative, manifest_path), (contract_relative, contract_path)):
        expected = source_hashes.get(relative)
        if expected is None or expected != _sha256_file(path):
            raise ValueError(f"protocol source lock does not cover current input {relative}")
    driver_path = (repo_root / _DRIVER_RELATIVE).resolve(strict=True)
    source_lock, normalized_hashes, driver_sha256 = _source_lock_from_provenance(
        output_dir, driver_path
    )
    budget = common.RunBudget(output_dir, effective_limits)
    preflight_phase = output_dir / "wheel_preflight"
    demonstration_phase = output_dir / "raw_fits_evaluation"
    try:
        preflight_supervisor = budget.execute(
            _preflight_worker,
            (python, driver_path, driver_sha256, source_lock),
            preflight_phase,
            family="external_reuse",
        )
        _validate_phase(preflight_phase, preflight_supervisor)
        proof = _read_json(preflight_phase / "preflight.json")
        _verify_preflight(proof, normalized_hashes)
        demonstration_supervisor = budget.execute(
            _demonstration_worker,
            (
                python,
                driver_path,
                driver_sha256,
                source_lock,
                source_root,
                manifest_path,
                contract_path,
                output_dir / "protocol_executed.json",
                cohort_size,
            ),
            demonstration_phase,
            family="external_reuse",
        )
        phase_result = _validate_phase(demonstration_phase, demonstration_supervisor)
        driver_result = phase_result.get("driver_result")
        if not isinstance(driver_result, dict) or driver_result.get("status") != "complete":
            raise RuntimeError("external driver result is incomplete")
        _validate_demonstration_artifacts(demonstration_phase, driver_result)
        if phase_result.get("driver_result_sha256") != _sha256_file(
            Path(str(phase_result.get("driver_result_path", "")))
        ):
            raise RuntimeError("phase result does not match the durable external result.json")
        final = {
            "status": "complete",
            "model_name": MODEL_NAME,
            "protocol_sha256": protocol_sha256,
            "protocol_path": str(protocol_path),
            "source_provenance_path": str((output_dir / "source_provenance.json").resolve()),
            "source_sha256": normalized_hashes,
            "external_reuse_model_spec": spec,
            "source_root": str(source_root),
            "manifest_path": str(manifest_path),
            "contract_path": str(contract_path),
            "reuse_python": str(python),
            "wheel_preflight": {
                "supervisor": preflight_supervisor,
                "worker_status": _read_json(preflight_phase / "worker_status.json"),
                "proof": proof,
                "stdout_path": str((preflight_phase / "driver.stdout.log").resolve()),
                "stderr_path": str((preflight_phase / "driver.stderr.log").resolve()),
            },
            "raw_fits_evaluation": {
                "supervisor": demonstration_supervisor,
                "worker_status": _read_json(demonstration_phase / "worker_status.json"),
                "result": driver_result,
                "stdout_path": str((demonstration_phase / "driver.stdout.log").resolve()),
                "stderr_path": str((demonstration_phase / "driver.stderr.log").resolve()),
            },
            "evidence_limits": {
                "historically_consulted_2019_2024_periods_are_exploratory": True,
                "independent_public_availability_at_origin_established": False,
                "external_human_participant_validation": "pending",
                "technical_assistant_run_is_not_external_human_validation": True,
            },
        }
        _write_json(output_dir / "result.json", final)
        _write_json(output_dir / "run_status.json", {"status": "complete"})
        return final
    except BaseException as exc:
        _write_json(
            output_dir / "run_error.json",
            {
                "status": "incomplete",
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        _write_json(output_dir / "run_status.json", {"status": "incomplete"})
        raise
