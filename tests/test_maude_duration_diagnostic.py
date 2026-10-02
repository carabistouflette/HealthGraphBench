"""Behavioral boundaries for the bounded MAUDE duration runner."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from healthgraphbench.tasks.maude.diagnostic import (
    MAX_OUTPUT_BYTES,
    MAX_RSS_BYTES,
    PhaseExecutionError,
    PreparedSnapshot,
    _add_snapshot_to_history,
    _assert_new_output,
    _first_edges,
    _select_validation_duration,
    _supervise_worker,
)
from healthgraphbench.tasks.maude.evaluate import _ranked_candidates, eligible_edges
from healthgraphbench.tasks.maude.models import FeatureContext, GraphSageRanker, History


def _sleep_until_killed(marker_path: str) -> None:
    marker = Path(marker_path)
    marker.write_text(str(os.getpid()), encoding="ascii")
    while True:
        time.sleep(0.05)


def _expand_sparse_output_until_killed(output_path: str) -> None:
    with Path(output_path).open("wb") as output:
        output.truncate(4 * 1024 * 1024)
        output.flush()
        while True:
            time.sleep(0.05)


class MaudeDurationDiagnosticTests(unittest.TestCase):
    def test_unrepresented_candidates_remain_and_exact_ties_use_popularity_then_code(self) -> None:
        history = History.empty()
        history.product_reports["P"] = 1
        history.problem_products["A"].update({"X", "Y"})
        history.problem_products["B"].update({"X", "Y"})
        history.problem_products["C"].add("Z")
        ranker = GraphSageRanker({}, {}, {})
        context = FeatureContext(history, "2023Q1", {})

        ranked = _ranked_candidates(context, "P", ranker.score)

        self.assertEqual(ranked, ["A", "B", "C"])
        self.assertEqual([ranker.score("P", problem) for problem in ranked], [0.0, 0.0, 0.0])

    def test_temporal_eligibility_uses_only_prior_history_then_updates_after_quarter(self) -> None:
        earlier = PreparedSnapshot(
            "2019Q1",
            {"P": 2, "Q": 1},
            frozenset({("P", "A"), ("Q", "B")}),
        )
        current = PreparedSnapshot(
            "2019Q2",
            {"P": 1, "R": 1},
            frozenset({("P", "A"), ("P", "B"), ("P", "C"), ("R", "C"), ("Q", "B")}),
        )
        first = _first_edges((earlier, current))
        history = History.empty()
        _add_snapshot_to_history(history, earlier)

        eligible = eligible_edges(first[current.quarter], history)

        self.assertEqual(eligible, frozenset({("P", "B")}))
        self.assertNotIn("C", history.problem_products)
        _add_snapshot_to_history(history, current)
        self.assertIn("C", history.problem_products)
        self.assertIn("B", history.product_problems["P"])

    @staticmethod
    def _fit_result(recall: float, status: str = "complete") -> dict[str, object]:
        return {
            "status": status,
            "validation": {"thresholds": {"1": {"recall_at_10": recall}}},
        }

    def test_selection_requires_complete_grid_excludes_zero_and_breaks_exact_tie_shorter(self) -> None:
        fits = {
            0: self._fit_result(1.0),
            3: self._fit_result(0.25),
            10: self._fit_result(0.25),
            30: self._fit_result(0.125),
        }

        selection = _select_validation_duration(fits)

        self.assertEqual(selection["selected_epochs"], 3)
        self.assertEqual(selection["validation_micro_recall_at_10"], 0.25)
        with self.assertRaises(ValueError):
            _select_validation_duration({key: value for key, value in fits.items() if key != 30})
        fits[10] = self._fit_result(0.25, status="incomplete")
        with self.assertRaises(ValueError):
            _select_validation_duration(fits)

    def test_existing_output_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_parent = root / "results" / "generated" / "consolidation-post-RC1"
            existing = output_parent / "already-used"
            existing.mkdir(parents=True)

            with self.assertRaises(FileExistsError):
                _assert_new_output(existing, root)

    def test_unavailable_rss_monitor_refuses_to_launch_worker(self) -> None:
        original_open = Path.open

        def unreadable_proc(path: Path, *args: object, **kwargs: object):
            if str(path).startswith("/proc/"):
                raise PermissionError("required RSS telemetry is unavailable")
            return original_open(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temporary:
            phase_dir = Path(temporary) / "phase"
            marker = phase_dir / "worker.pid"
            with patch.object(Path, "open", unreadable_proc):
                with self.assertRaises(PermissionError):
                    _supervise_worker(
                        _sleep_until_killed,
                        (str(marker),),
                        phase_dir,
                        timeout_seconds=1.0,
                        max_rss_bytes=MAX_RSS_BYTES,
                        max_output_bytes=MAX_OUTPUT_BYTES,
                    )
            self.assertFalse(marker.exists())

    def test_supervisor_terminates_timed_out_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            phase_dir = Path(temporary) / "phase"
            phase_dir.mkdir()
            marker = phase_dir / "worker.pid"
            with self.assertRaises(PhaseExecutionError) as caught:
                _supervise_worker(
                    _sleep_until_killed,
                    (str(marker),),
                    phase_dir,
                    timeout_seconds=1.0,
                    max_rss_bytes=MAX_RSS_BYTES,
                    max_output_bytes=MAX_OUTPUT_BYTES,
                )

            supervisor = caught.exception.supervisor
            self.assertEqual(supervisor["reason"], "timeout")
            self.assertTrue(marker.exists())
            self.assertFalse(Path(f"/proc/{supervisor['pid']}").exists())

    def test_supervisor_terminates_worker_at_rss_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            phase_dir = Path(temporary) / "phase"
            phase_dir.mkdir()
            with self.assertRaises(PhaseExecutionError) as caught:
                _supervise_worker(
                    _sleep_until_killed,
                    (str(phase_dir / "worker.pid"),),
                    phase_dir,
                    timeout_seconds=5.0,
                    max_rss_bytes=1,
                    max_output_bytes=MAX_OUTPUT_BYTES,
                )

            supervisor = caught.exception.supervisor
            self.assertEqual(supervisor["reason"], "rss_limit")
            self.assertFalse(Path(f"/proc/{supervisor['pid']}").exists())

    def test_supervisor_terminates_worker_at_output_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            phase_dir = Path(temporary) / "phase"
            phase_dir.mkdir()
            output_path = phase_dir / "oversized.bin"
            with self.assertRaises(PhaseExecutionError) as caught:
                _supervise_worker(
                    _expand_sparse_output_until_killed,
                    (str(output_path),),
                    phase_dir,
                    timeout_seconds=5.0,
                    max_rss_bytes=MAX_RSS_BYTES,
                    max_output_bytes=1024,
                )

            supervisor = caught.exception.supervisor
            self.assertEqual(supervisor["reason"], "output_limit")
            self.assertTrue(output_path.exists())
            self.assertGreater(supervisor["phase_output_bytes"], 1024)
            self.assertFalse(Path(f"/proc/{supervisor['pid']}").exists())


if __name__ == "__main__":
    unittest.main()
