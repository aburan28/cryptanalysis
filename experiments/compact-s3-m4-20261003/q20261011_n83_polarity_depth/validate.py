#!/usr/bin/env python3
"""Check Q1475's deep-prefix receipts against frozen Q1474 implementation."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1473 = PARENT / "q20261011_selector_polarity"
Q1474 = PARENT / "q20261011_n83_propagation_probe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    assert protocol["proposal_id"] == frozen["proposal_id"] == drive["proposal_id"] == "Q1475"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    assert sha(Q1474 / "freeze.json") == frozen["q1474_freeze_sha256"]
    assert sha(Q1474 / "analysis.json") == frozen["q1474_analysis_sha256"]
    assert sha(Q1474 / "run.py") == frozen["q1474_runner_sha256"]
    assert sha(Q1473 / "smoke_receipt.json") == frozen["q1473_smoke_sha256"]
    assert sha(Q1473 / "target.json") == frozen["q1473_target_sha256"]
    assert sha(Path(frozen["binary_path"])) == frozen["binary_sha256"]
    cell = frozen["ordinary_cell"]
    for kind in ("derived", "source"):
        path = Path(cell[f"{kind}_archive_path"])
        assert sha(path) == cell[f"{kind}_archive_sha256"]
        assert hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() == cell[
            f"{kind}_raw_sha256"]
    rows = []
    for phase in protocol["phase_order"]:
        folder = HERE / "runs" / f"phase{phase}"
        if not folder.exists():
            break
        outer = json.loads((folder / "receipt.json").read_text())
        child_path = folder / "implementation_receipt.json"
        child = json.loads(child_path.read_text())
        assert outer["proposal_id"] == "Q1475" and child["proposal_id"] == "Q1474"
        assert outer["implementation_receipt_sha256"] == sha(child_path)
        assert outer["phase"] == child["phase"] == phase
        assert outer["flip_ids"] == child["flip_ids"] == frozen[
            "phase_schedule"][str(phase)]["flip_ids"]
        for key in ("status", "branch_lower_bound", "cnf_set_true_calls_at_checkpoint",
                    "xor_set_true_calls_at_checkpoint", "user_cpu_seconds",
                    "solver_wall_seconds_exploratory", "verified_natural_relations"):
            assert outer[key] == child[key]
        assert outer["curve_id"] == child["curve_id"] == protocol["curve_id"]
        assert outer["workload_id"] == child["workload_id"] == protocol["workload_id"]
        assert outer["isogeny"] == child["isogeny"] == "none"
        assert outer["factor_base_actual_B"] == child["factor_base_actual_B"] == protocol[
            "factor_base_actual_B"]
        assert outer["factor_base_folded_columns_K"] == child[
            "factor_base_folded_columns_K"] == protocol["factor_base_folded_columns_K"]
        assert child["binary_sha256"] == frozen["binary_sha256"]
        assert child["freeze_sha256"] == outer["freeze_sha256"] == sha(HERE / "freeze.json")
        assert child["source_sha256"] == frozen["q1474_runner_sha256"]
        assert outer["wrapper_source_sha256"] == sha(HERE / "run.py")
        stdout_path, stderr_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        assert sha(stdout_path) == child["stdout_sha256"]
        assert sha(stderr_path) == child["stderr_sha256"]
        text = stderr_path.read_text(errors="replace")
        checkpoints = [int(x) for x in re.findall(r"^Q1464_BRANCH (\d+)$", text, re.M)]
        work = [list(map(int, x)) for x in re.findall(
            r"^Q1473_WORK (\d+) (\d+) (\d+)$", text, re.M)]
        assert [item[0] for item in work] == checkpoints
        assert checkpoints == [1 << index for index in range(len(checkpoints))]
        assert child["branch_checkpoints"] == checkpoints and child["work_checkpoints"] == work
        at_cap = next((item for item in work if item[0] == protocol[
            "checkpoint_left_branches"]), None)
        assert child["cnf_set_true_calls_at_checkpoint"] == (at_cap[1] if at_cap else None)
        assert child["xor_set_true_calls_at_checkpoint"] == (at_cap[2] if at_cap else None)
        assert child["search_started"] == ("Q1458_SEARCH_START" in text)
        if outer["status"] == "CHECKPOINT_TERMINATED":
            assert at_cap and child["search_started"] and child["marker_ok"]
            assert outer["branch_lower_bound"] == protocol["checkpoint_left_branches"]
        else:
            assert outer["status"] in ("VERIFIED_RELATION", "CENSORED_BEFORE_SEARCH",
                                       "WALL_CAP_SEARCH_STARTED", "CPU_CAP_BEFORE_SEARCH",
                                       "CPU_CAP_SEARCH_STARTED", "PRODUCER_FAILURE",
                                       "MODEL_REPLAY_FAILED")
        rows.append(outer)
    assert rows and len(rows) == drive["new_ordinary_attempts"]
    assert drive["phase_statuses"] == [row["status"] for row in rows]
    assert drive["new_verified_relations"] == sum(row["verified_natural_relations"] for row in rows)
    assert abs(drive["new_ordinary_wall_seconds_exploratory"] - sum(
        row["solver_wall_seconds_exploratory"] for row in rows)) < 1e-8
    assert abs(drive["new_ordinary_user_cpu_seconds"] - sum(
        row["user_cpu_seconds"] for row in rows)) < 1e-8
    assert drive["complete_n83_decomposition_work_log2"] is None
    assert drive["complete_n131_solve_work_log2"] is None
    print("PASS Q1475", len(rows), [row["status"] for row in rows])


if __name__ == "__main__":
    main()
