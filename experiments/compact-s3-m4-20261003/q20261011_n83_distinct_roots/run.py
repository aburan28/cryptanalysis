#!/usr/bin/env python3
"""Run the Q1478 matched prefix with distinct pair-1 logging."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1478 = HERE.parent / "q20261011_n83_leaf_exposure"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    prior = json.loads((Q1478 / "freeze.json").read_text())
    build = json.loads((HERE / "build_receipt.json").read_text())
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert build["freeze_sha256"] == sha(HERE / "freeze.json")
    assert sha(Q1478 / "run.py") == frozen["q1478_run_source_sha256"]
    spec = importlib.util.spec_from_file_location("q1478_run_for_q1479",
                                                  Q1478 / "run.py")
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.HERE = HERE
    impl_protocol = dict(protocol,
                         cpu_soft_seconds_per_cell=protocol["cpu_soft_seconds_per_point"],
                         cpu_hard_seconds_per_cell=protocol["cpu_hard_seconds_per_point"],
                         wall_seconds_per_cell=protocol["wall_seconds_per_point"])
    rows = []
    for name in ("selected", "holdout"):
        implementation = runner.run_one(name, protocol["branch_order"],
                                        impl_protocol, prior, build)
        folder = HERE / "runs" / f"{name}_{protocol['branch_order']}"
        (folder / "receipt.json").rename(folder / "implementation_receipt.json")
        row = {"proposal_id": "Q1479", "candidate_id": None, "run_id": None,
               "curve_id": protocol["curve_id"],
               "workload_id": frozen["inputs"][name]["workload_id"],
               "input": name, "branch_order": protocol["branch_order"],
               "status": implementation["status"],
               "branch_lower_bound": implementation["branch_lower_bound"],
               "ready_checkpoints": implementation["ready_checkpoints"],
               "work_checkpoints": implementation["work_checkpoints"],
               "solver_wall_seconds_exploratory": implementation[
                   "solver_wall_seconds_exploratory"],
               "solver_user_cpu_seconds_exploratory": implementation[
                   "solver_user_cpu_seconds_exploratory"],
               "implementation_receipt_sha256": sha(
                   folder / "implementation_receipt.json"),
               "stdout_sha256": implementation["stdout_sha256"],
               "stderr_sha256": implementation["stderr_sha256"],
               "binary_sha256": build["binary_sha256"],
               "freeze_sha256": sha(HERE / "freeze.json"),
               "complete_n83_decomposition_work_log2": None,
               "complete_n131_solve_work_log2": None}
        (folder / "receipt.json").write_text(json.dumps(row, indent=2,
                                                       sort_keys=True) + "\n")
        rows.append(row)
        if row["status"] != "CHECKPOINT_TERMINATED":
            break
    drive = {"proposal_id": "Q1479", "candidate_id": None, "run_id": None,
             "rows": [{"input": row["input"], "status": row["status"],
                       "receipt_sha256": sha(HERE / "runs" /
                                             f"{row['input']}_{protocol['branch_order']}" /
                                             "receipt.json")} for row in rows],
             "new_ordinary_attempts": len(rows),
             "solver_wall_phase_sum_seconds_exploratory": sum(
                 row["solver_wall_seconds_exploratory"] for row in rows),
             "solver_user_cpu_sum_seconds_exploratory": sum(
                 row["solver_user_cpu_seconds_exploratory"] for row in rows),
             "freeze_sha256": sha(HERE / "freeze.json"),
             "complete_n83_decomposition_work_log2": None,
             "complete_n131_solve_work_log2": None,
             "degree131_challenge_gap_bits": None}
    (HERE / "drive_receipt.json").write_text(json.dumps(drive, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
