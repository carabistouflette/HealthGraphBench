"""Evaluation utilities for dependence-aware uncertainty estimates."""

from .bootstrap import cluster_bootstrap_indices, paired_cluster_bootstrap
from .metrics import ranking_auc, average_precision
from .numpy_metrics import (
    average_precision_numpy,
    finite_float_array,
    mean_reciprocal_rank,
    numpy_to_python,
    ranking_auc_numpy,
    recall_at_k,
)

__all__ = [
    "average_precision",
    "average_precision_numpy",
    "cluster_bootstrap_indices",
    "finite_float_array",
    "mean_reciprocal_rank",
    "numpy_to_python",
    "paired_cluster_bootstrap",
    "ranking_auc",
    "ranking_auc_numpy",
    "recall_at_k",
]
