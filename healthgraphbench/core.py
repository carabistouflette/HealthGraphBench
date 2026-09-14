"""Model-independent benchmark protocol."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Split:
    """A named temporal split owned by a benchmark task."""

    task: "BenchmarkTask"
    name: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PredictionSet:
    """Predictions returned by a model through the common benchmark interface."""

    task_name: str
    method: str
    split: str
    payload: Any


class BenchmarkModel(Protocol):
    """Protocol implemented by all benchmark models."""

    name: str

    def fit_predict(
        self, train: Split, validation: Split, test: Split
    ) -> PredictionSet:
        ...


class BenchmarkTask(Protocol):
    """Protocol shared by the MAUDE and CMS benchmark tasks."""

    name: str

    def get_split(self, name: str) -> Split:
        """Return one frozen temporal split by name."""
        ...

    def fit_predict(
        self, method: str, train: Split, validation: Split, test: Split
    ) -> PredictionSet:
        ...

    def evaluate(self, predictions: PredictionSet) -> dict[str, Any]:
        ...


def load_task(
    name: str,
    source_root: str | Path | None = None,
    **kwargs: Any,
) -> BenchmarkTask:
    """Load a task from official-source snapshots under ``source_root``.

    When omitted, ``source_root`` defaults to ``$HEALTHGRAPHBENCH_DATA_ROOT``
    or ``./data``. Raw snapshots remain external to the repository.
    """

    import os

    root = Path(source_root or os.environ.get("HEALTHGRAPHBENCH_DATA_ROOT", "data"))
    normalized = name.strip().lower().replace("-", "_")
    if normalized == "maude":
        from .tasks.maude.task import MaudeTask

        return MaudeTask.from_source_root(root, **kwargs)
    if normalized in {"cms", "cms_nursing", "nursing_home"}:
        from .tasks.cms_nursing.task import CmsNursingTask

        return CmsNursingTask.from_source_root(root, **kwargs)
    raise ValueError(f"Unknown task {name!r}; expected 'maude' or 'cms_nursing'")
