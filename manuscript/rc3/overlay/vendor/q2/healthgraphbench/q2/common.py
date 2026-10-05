"""Committed-protocol provenance and enforced Linux budgets for the Q2 cycle."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from threadpoolctl import threadpool_limits

from ..tasks.maude import diagnostic

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LIMITS = {
    "timeout_seconds": 1800,
    "max_rss_bytes": 4 * 1024**3,
    "max_output_bytes": 1024**3,
    "family_validation_wall_seconds": 21600,
    "run_wall_seconds": 86400,
    "total_output_bytes": 16 * 1024**3,
}


def load_protocol(path: Path, expected_sha256: str, output_dir: Path) -> dict[str, Any]:
    """Verify the exact committed protocol and its source set before any fit.

    Unrelated dirty user documents are not a scientific-source mismatch. Every
    source listed in the protocol must nevertheless equal its committed blob.
    The executed protocol is copied verbatim, not reserialized.
    """
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"Q2 protocol hash mismatch: expected {expected_sha256}, got {actual}")
    protocol = json.loads(raw)
    if protocol.get("schema") != "healthgraphbench.q2-protocol.v1":
        raise ValueError("unsupported Q2 protocol schema")
    relative = path.relative_to(REPO_ROOT).as_posix()
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    committed = subprocess.check_output(
        ["git", "show", f"{commit}:{relative}"], cwd=REPO_ROOT
    )
    if committed != raw:
        raise ValueError("Q2 protocol must be committed verbatim before execution")
    sources = protocol.get("locked_sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Q2 protocol must enumerate its locked scientific sources")
    source_hashes: dict[str, str] = {}
    for name in sources:
        source_path = (REPO_ROOT / name).resolve(strict=True)
        source_path.relative_to(REPO_ROOT)
        current = source_path.read_bytes()
        blob = subprocess.check_output(
            ["git", "show", f"{commit}:{name}"], cwd=REPO_ROOT
        )
        if current != blob:
            raise ValueError(f"uncommitted Q2 scientific-source change: {name}")
        source_hashes[name] = hashlib.sha256(current).hexdigest()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    executed = output_dir / "protocol_executed.json"
    with executed.open("xb") as output:
        output.write(raw)
    versions = {}
    for distribution in ("healthgraphbench", "numpy", "scikit-learn", "scipy", "numba", "llvmlite"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    diagnostic._write_json(
        output_dir / "source_provenance.json",
        {
            "code_commit": commit,
            "base_commit": protocol["base_commit"],
            "protocol_path": relative,
            "protocol_sha256": actual,
            "source_sha256": source_hashes,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "argv": sys.argv,
            "python": sys.version,
            "packages": versions,
            "thread_environment": {name: os.environ.get(name) for name in diagnostic._THREAD_ENV_VARIABLES},
            "evidence_level": protocol["evidence_level"],
        },
    )
    return protocol


def _guarded_worker(target: Callable[..., Any], args: tuple[Any, ...], phase_dir: Path) -> None:
    started = time.monotonic()
    started_cpu = time.process_time()
    diagnostic._write_json(phase_dir / "worker_status.json", {"status": "running", "pid": os.getpid()})
    try:
        with threadpool_limits(limits=1):
            result = target(*args, phase_dir)
        if result is not None and not (phase_dir / "result.json").exists():
            diagnostic._write_json(phase_dir / "result.json", result)
    except BaseException as exc:
        diagnostic._write_json(
            phase_dir / "worker_error.json",
            {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()},
        )
        diagnostic._write_json(
            phase_dir / "worker_status.json",
            {"status": "incomplete", "pid": os.getpid(), "cpu_seconds": time.process_time() - started_cpu},
        )
        raise
    diagnostic._write_json(
        phase_dir / "worker_status.json",
        {
            "status": "complete",
            "pid": os.getpid(),
            "wall_seconds": time.monotonic() - started,
            "cpu_seconds": time.process_time() - started_cpu,
            "peak_rss_bytes": diagnostic._process_peak_rss_bytes(os.getpid()),
        },
    )


def execute_phase(
    target: Callable[..., Any],
    args: tuple[Any, ...],
    phase_dir: Path,
    limits: Mapping[str, int | float] | None = None,
) -> dict[str, Any]:
    """Run target(*args, phase_dir), retaining errors and measured supervision.

    Return ``status=complete`` and the existing diagnostic supervisor cost
    fields. Result data, when present, lives in phase_dir/result.json. Phase
    directories may not be reused; the supervisor creates the new directory.
    """
    phase_dir = Path(phase_dir)
    if phase_dir.exists():
        raise FileExistsError(f"refusing to reuse Q2 phase: {phase_dir}")
    effective = dict(DEFAULT_LIMITS)
    if limits is not None:
        effective.update(limits)
    for key in ("timeout_seconds", "max_rss_bytes", "max_output_bytes"):
        if not math.isfinite(float(effective[key])) or float(effective[key]) <= 0:
            raise ValueError(f"Q2 {key} must be finite and positive")
        if float(effective[key]) > DEFAULT_LIMITS[key]:
            raise ValueError(f"Q2 {key} exceeds the published maximum")
    os.environ["NUMBA_NUM_THREADS"] = "1"
    return diagnostic._supervise_worker(
        _guarded_worker,
        (target, args, phase_dir),
        phase_dir,
        timeout_seconds=float(effective["timeout_seconds"]),
        max_rss_bytes=int(effective["max_rss_bytes"]),
        max_output_bytes=int(effective["max_output_bytes"]),
    )


class RunBudget:
    """Apply cumulative run/family limits in addition to each supervised phase."""

    def __init__(self, output_dir: Path, limits: Mapping[str, int | float]) -> None:
        self.output_dir = Path(output_dir)
        self.limits = dict(DEFAULT_LIMITS)
        self.limits.update(limits)
        for name, maximum in DEFAULT_LIMITS.items():
            value = float(self.limits[name])
            if not math.isfinite(value) or value <= 0 or value > maximum:
                raise ValueError(f"invalid or unpublished cumulative Q2 limit: {name}")
        self.started = time.monotonic()
        self.family_seconds: dict[str, float] = {}
        self.phases: list[dict[str, Any]] = []

    def execute(
        self,
        target: Callable[..., Any],
        args: tuple[Any, ...],
        phase_dir: Path,
        *,
        family: str | None = None,
    ) -> dict[str, Any]:
        remaining = float(self.limits["run_wall_seconds"]) - (time.monotonic() - self.started)
        if family is not None:
            remaining = min(
                remaining,
                float(self.limits["family_validation_wall_seconds"]) - self.family_seconds.get(family, 0.0),
            )
        available_bytes = int(self.limits["total_output_bytes"]) - diagnostic._directory_bytes(self.output_dir)
        if remaining <= 0 or available_bytes <= 0:
            raise RuntimeError("cumulative Q2 budget exhausted; no incomplete-grid selection is permitted")
        limits = dict(self.limits)
        limits["timeout_seconds"] = min(float(limits["timeout_seconds"]), remaining)
        limits["max_output_bytes"] = min(int(limits["max_output_bytes"]), available_bytes)
        error: diagnostic.PhaseExecutionError | None = None
        try:
            supervisor = execute_phase(target, args, phase_dir, limits)
        except diagnostic.PhaseExecutionError as exc:
            supervisor = dict(exc.supervisor)
            error = exc
        if family is not None:
            self.family_seconds[family] = self.family_seconds.get(family, 0.0) + float(supervisor["wall_seconds"])
        self.phases.append({"phase": str(Path(phase_dir).relative_to(self.output_dir)), "family": family, **supervisor})
        diagnostic._write_json(
            self.output_dir / "resource_ledger.json",
            {"limits": self.limits, "family_validation_seconds": self.family_seconds, "phases": self.phases},
        )
        if error is not None:
            raise error
        if diagnostic._directory_bytes(self.output_dir) > int(self.limits["total_output_bytes"]):
            raise RuntimeError("cumulative Q2 output limit exceeded; no test scoring is permitted")
        return supervisor
