"""Common-interface adapter for the frozen MAUDE temporal benchmark."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...core import PredictionSet, Split
from .data import QUARTERS, load_problem_parent_map, load_snapshots
from .evaluate import run_gate


_ALLOWED_METHODS = {
    "global_popularity",
    "neighbor_frequency",
    "logistic_tabular",
    "boosted_stumps_tabular",
    "matrix_factorization_spectral",
    "graph_message_passing_bpr",
    "graphsage_link_prediction",
}


@dataclass
class MaudeTask:
    """A fully loaded MAUDE task with frozen temporal boundaries.

    ``source_root`` contains a ``maude/`` directory with the seven annual
    device ZIPs and the two problem-code ZIPs. Raw files remain user-managed;
    this object stores only parsed snapshots in memory.
    """

    bundle: Any
    problem_parent_map: dict[str, str]
    code_to_imdrf: dict[str, str]
    source_root: Path
    device_dir: Path
    problem_zip: Path
    problem_code_map: Path
    _cached_record: dict[str, Any] | None = None

    name = "maude"

    @classmethod
    def from_source_root(cls, source_root: Path, **_: Any) -> "MaudeTask":
        root = source_root / "maude" if (source_root / "maude").is_dir() else source_root
        device_dir = root / "device"
        if not device_dir.is_dir():
            device_dir = root
        problem_zip = root / "foidevproblem_thru2025.zip"
        problem_code_map = root / "deviceproblemcodes2025.zip"
        missing = [str(path) for path in (problem_zip, problem_code_map) if not path.is_file()]
        if not device_dir.is_dir() or len(tuple(device_dir.glob("device20*.zip"))) < 7:
            missing.append(f"{device_dir}/device2019.zip ... device2025.zip")
        if missing:
            raise FileNotFoundError(
                "MAUDE source files are missing; run scripts/download_maude.py. Missing: "
                + ", ".join(missing)
            )
        bundle = load_snapshots(device_dir, problem_zip)
        observed_codes = {problem for snapshot in bundle.snapshots for _, problem in snapshot.edges}
        parent_map, code_to_imdrf = load_problem_parent_map(problem_code_map, observed_codes)
        return cls(
            bundle,
            parent_map,
            code_to_imdrf,
            root,
            device_dir,
            problem_zip,
            problem_code_map,
        )

    def get_split(self, name: str) -> Split:
        """Return a frozen MAUDE temporal split by name."""

        normalized = name.strip().lower()
        if normalized == "train":
            return Split(
                self,
                "train",
                {"quarters": [q for q in QUARTERS if q <= "2022Q4"], "cutoff": "2022Q4"},
            )
        if normalized == "validation":
            return Split(
                self,
                "validation",
                {"quarters": [q for q in QUARTERS if q.startswith("2023")], "cutoff": "2023Q4"},
            )
        if normalized == "test":
            return Split(
                self,
                "test",
                {
                    "quarters": [q for q in QUARTERS if q.startswith(("2024", "2025"))],
                    "cutoff": "2025Q4",
                },
            )
        raise ValueError(f"Unknown MAUDE split {name!r}; expected train, validation, or test")

    def fit_predict(
        self, method: str, train: Split, validation: Split, test: Split
    ) -> PredictionSet:
        if method not in _ALLOWED_METHODS:
            raise ValueError(f"Unknown MAUDE method {method!r}")
        if {train.name, validation.name, test.name} != {"train", "validation", "test"}:
            raise ValueError("MAUDE requires train, validation, and test splits")
        if train.task is not self or validation.task is not self or test.task is not self:
            raise ValueError("all splits must belong to this MAUDE task")
        if self._cached_record is None:
            with tempfile.TemporaryDirectory(prefix="healthgraphbench-maude-") as tmp:
                self._cached_record = run_gate(
                    self.device_dir,
                    self.problem_zip,
                    self.problem_code_map,
                    Path(tmp) / "maude_gate.json",
                    bundle=self.bundle,
                )
        method_record = next(
            item for item in self._cached_record["methods"] if item["method"] == method
        )
        return PredictionSet(self.name, method, "test", method_record)

    def evaluate(self, predictions: PredictionSet) -> dict[str, Any]:
        if predictions.task_name != self.name:
            raise ValueError("predictions belong to a different task")
        if predictions.split != "test":
            raise ValueError("MAUDE evaluation requires test predictions")
        return dict(predictions.payload["test"])

    def manifest(self) -> dict[str, Any]:
        """Return the task contract and parsed cardinalities."""

        return {
            "benchmark_version": "0.1",
            "task": self.name,
            "target": "first observed product/problem edge in the retained quarter window",
            "candidate_rule": "problem code observed globally before q and edge absent before q",
            "training_quarters": "2019Q1-2022Q4",
            "validation_quarters": "2023Q1-2023Q4",
            "test_quarters": "2024Q1-2025Q4",
            "negative_semantics": "temporal non-observation, not a clinical negative",
            "metrics": ["Recall@5", "Recall@10", "Recall@20", "macro Recall", "MRR"],
            "clusters": "product code",
            "unique_edges": len({edge for snapshot in self.bundle.snapshots for edge in snapshot.edges}),
            "snapshots": len(self.bundle.snapshots),
        }
