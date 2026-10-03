"""Run the protocol-locked raw-data MAUDE Q2 comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import traceback
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from healthgraphbench.q2 import common, maude


def verify_completed_validation(parent: Path, protocol: dict, sha256: str) -> tuple:
    """Accept only a complete locked grid from the pre-serialization-fix code."""
    parent = parent.resolve(strict=True)
    provenance = maude._json_read(parent / "source_provenance.json")
    if provenance["protocol_sha256"] != sha256:
        raise ValueError("validation protocol differs from completion protocol")
    if hashlib.sha256((parent / "protocol_executed.json").read_bytes()).hexdigest() != sha256:
        raise ValueError("validation protocol bytes differ")
    for name, expected in provenance["source_sha256"].items():
        original = subprocess.check_output(
            ["git", "show", f"{provenance['code_commit']}:{name}"], cwd=_REPO_ROOT,
        )
        if hashlib.sha256(original).hexdigest() != expected:
            raise ValueError(f"validation source provenance mismatch: {name}")
        current = (_REPO_ROOT / name).read_bytes()
        if name in {"scripts/run_q2_maude.py", "healthgraphbench/q2/cms.py"}:
            # Published controller extension and unrelated, unconsumed CMS adapter.
            continue
        if name == "healthgraphbench/q2/maude.py":
            original = original.replace(br'newline="\\n"', br'newline="\n"')
            original = original.replace(br'+ "\\n"', br'+ "\n"')
        if current != original:
            raise ValueError(f"validation-consuming implementation changed: {name}")
    selection = maude._json_read(parent / "selection.json")
    if (selection["status"] != "LOCKED"
            or selection["protocol_sha256"] != sha256
            or not selection["selection_locked_before_test_scoring"]):
        raise ValueError("validation selection was not locked")
    task = maude._protocol_config(protocol)
    training_rows = selection["boosted_seed_policy"]["validation_training_rows"]
    if set(selection["families"]) != set(maude.FAMILY_METHODS):
        raise ValueError("validation family set is incomplete")
    for family, result in selection["families"].items():
        grid = maude._grid_for(task, family)
        rows = result["configurations"]
        if len(rows) != 6 or [row["configuration"] for row in rows] != grid:
            raise ValueError(f"incomplete or changed validation grid: {family}")
        eligible = []
        for index, row in enumerate(rows):
            seeds = maude._family_seeds(task, family, training_rows)
            if set(row["by_seed"]) != {str(seed) for seed in seeds}:
                raise ValueError(f"incomplete validation seeds: {family}")
            for seed in seeds:
                phase = maude._phase_config_dir(parent / "validation", family, index) / f"seed{seed:03d}"
                status = maude._json_read(phase / "supervisor_status.json")
                if status["status"] != "complete" or not (phase / "checkpoint.bin").is_file():
                    raise ValueError(f"incomplete validation phase: {phase}")
                if maude._phase_result(phase) != row["by_seed"][str(seed)]:
                    raise ValueError(f"validation result differs from locked selection: {phase}")
            values = [seed["validation_micro_recall_at_10"] for seed in row["by_seed"].values()]
            if sum(values) / len(values) != row["mean_validation_micro_recall_at_10"]:
                raise ValueError(f"validation average differs: {family}")
            if family not in {"graphsage_mean", "graphsage_none"} or all(
                seed["diagnostics"]["learning_gate_passed"]
                for seed in row["by_seed"].values()
            ):
                eligible.append(row)
        if not eligible:
            raise ValueError(f"no learning-qualified validation configuration: {family}")
        best = max(eligible, key=lambda row: row["mean_validation_micro_recall_at_10"])
        if (result["selected_config_id"] != best["config_id"]
                or result["selected_configuration"] != best["configuration"]
                or result["selected_validation_score"] != best["mean_validation_micro_recall_at_10"]):
            raise ValueError(f"selection differs from complete validation grid: {family}")
    ledger = maude._json_read(parent / "resource_ledger.json")
    prepared = maude._json_read(parent / "prepared" / "prepared.json")
    return selection, prepared, ledger


def complete_validation(args: argparse.Namespace, parent: Path) -> dict:
    output = args.output_dir
    if output.exists():
        raise FileExistsError(f"refusing to reuse Q2 MAUDE output directory {output}")
    output.mkdir(parents=True)
    try:
        protocol = common.load_protocol(args.protocol, args.protocol_sha256, output)
        selection, prepared, old_ledger = verify_completed_validation(
            parent, protocol, args.protocol_sha256,
        )
        if Path(selection["source_root"]).resolve() != args.source_root.resolve():
            raise ValueError("completion raw source root differs from validation")
        limits = maude._parse_limits(args)
        old_wall = sum(row["wall_seconds"] for row in old_ledger["phases"])
        old_bytes = common.diagnostic._directory_bytes(parent)
        limits["run_wall_seconds"] -= old_wall
        limits["total_output_bytes"] -= old_bytes
        budget = common.RunBudget(output, limits)
        prepared_dir = parent.resolve() / "prepared"
        reuse = {
            "validation_run": str(parent.resolve()),
            "validation_commit": maude._json_read(parent / "source_provenance.json")["code_commit"],
            "selection_sha256": hashlib.sha256((parent / "selection.json").read_bytes()).hexdigest(),
            "prepared_artifacts": maude._source_manifest([
                str(prepared_dir / name) for name in
                ("prepared.json", "training_rows.npz", "maude_raw_bundle.pkl.gz")
            ]),
            "previous_resource_ledger": old_ledger,
            "previous_wall_seconds_charged": old_wall,
            "previous_output_bytes_charged": old_bytes,
            "validation_refitted": False,
            "reason": "JSONL newline serialization fix only; unchanged validation numerics",
        }
        maude._json_write(output / "validation_reuse.json", reuse)
        records = []
        tests = {"heuristics": {}}
        task = maude._protocol_config(protocol)
        for year in (2024, 2025):
            phase = output / "test" / "heuristics" / f"year{year}" / "seed000"
            supervisor = maude._run_phase(
                budget, maude._heuristics_worker, (str(prepared_dir), False, year), phase,
            )
            tests["heuristics"][str(year)] = maude._phase_result(phase)["methods"]
            records.append({"phase": "test", "family": "heuristics", "year": year, "supervisor": supervisor})
            maude._save_execution_records(output, records)
            training_rows = selection["boosted_seed_policy"]["test_refits"][str(year)]["training_rows"]
            for family, selected in selection["families"].items():
                by_seed = {}
                for seed in maude._family_seeds(task, family, training_rows):
                    phase = output / "test" / family / f"year{year}" / f"seed{seed:03d}"
                    supervisor = maude._run_phase(
                        budget, maude._test_worker,
                        (str(prepared_dir), task, family, selected["selected_configuration"], seed, year),
                        phase,
                    )
                    by_seed[str(seed)] = maude._phase_result(phase)
                    records.append({"phase": "test", "family": family, "year": year,
                                    "seed": seed, "supervisor": supervisor})
                    maude._save_execution_records(output, records)
                tests.setdefault(family, {})[str(year)] = by_seed
        result = {
            "record_kind": "Q2_MAUDE_COMPARISON", "status": "COMPLETE",
            "protocol_sha256": args.protocol_sha256, "protocol_metadata": protocol,
            "source_manifest": prepared["raw_sources"], "task_manifest": prepared["task_manifest"],
            "selection": selection, "test_results": tests,
            "resource_limits": maude._parse_limits(args), "continuation_limits": limits,
            "execution_phases": records, "validation_reuse": reuse,
        }
        maude._json_write(output / "result.json", result)
        return result
    except BaseException as error:
        maude._json_write(output / "run_error.json", {
            "status": "incomplete", "type": type(error).__name__,
            "message": str(error), "traceback": traceback.format_exc(),
        })
        raise


def entrypoint() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--complete-validation", type=Path)
    continuation, remaining = parser.parse_known_args()
    if continuation.complete_validation is None:
        return maude.main(remaining)
    args = maude._parse_args(remaining)
    result = complete_validation(args, continuation.complete_validation)
    print(json.dumps({"status": result["status"], "output_dir": str(args.output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(entrypoint())
