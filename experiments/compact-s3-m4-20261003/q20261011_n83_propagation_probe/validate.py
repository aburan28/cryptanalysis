#!/usr/bin/env python3
"""Independently check Q1474 identities, work traces, and status accounting."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1473 = HERE.parent / "q20261011_selector_polarity"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    drive = json.loads((HERE / "drive_receipt.json").read_text())
    assert protocol["proposal_id"] == frozen["proposal_id"] == drive["proposal_id"] == "Q1474"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert sha(HERE / "freeze.json") == drive["freeze_sha256"]
    for name, digest in frozen["files_sha256"].items():
        assert sha(HERE / name) == digest
    for label, name in (("freeze", "freeze.json"), ("build", "build_receipt.json"),
                        ("smoke", "smoke_receipt.json"), ("target", "target.json")):
        assert sha(Q1473 / name) == frozen[f"q1473_{label}_sha256"]
    smoke = json.loads((Q1473 / "smoke_receipt.json").read_text())
    assert smoke["status"] == "PASS" and len(smoke["rows"]) == 4
    assert all(row["status"] == "SAT_REPLAYED_XCNF" for row in smoke["rows"])
    assert sha(Path(frozen["binary_path"])) == frozen["binary_sha256"] == smoke["binary_sha256"]
    cell = frozen["ordinary_cell"]
    for key in ("derived", "source"):
        path = Path(cell[f"{key}_archive_path"])
        assert sha(path) == cell[f"{key}_archive_sha256"]
        assert hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() == cell[
            f"{key}_raw_sha256"]
    rows = []
    for phase in protocol["phase_order"]:
        folder = HERE / "runs" / f"phase{phase}"
        if not folder.exists():
            break
        row = json.loads((folder / "receipt.json").read_text())
        assert row["phase"] == phase
        assert row["curve_id"] == protocol["curve_id"] == cell["curve_id"]
        assert row["workload_id"] == protocol["workload_id"] == cell["workload_id"]
        assert row["factor_base_actual_B"] == protocol["factor_base_actual_B"] == cell[
            "factor_base_actual_B"]
        assert row["factor_base_folded_columns_K"] == protocol[
            "factor_base_folded_columns_K"] == cell["factor_base_folded_columns_K"]
        assert row["isogeny"] == "none" and row["binary_sha256"] == frozen["binary_sha256"]
        assert row["freeze_sha256"] == sha(HERE / "freeze.json")
        assert row["source_sha256"] == sha(HERE / "run.py")
        assert row["flip_ids"] == frozen["phase_schedule"][str(phase)]["flip_ids"]
        stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        assert sha(stdout) == row["stdout_sha256"] and sha(stderr) == row["stderr_sha256"]
        log = stderr.read_text(errors="replace")
        checkpoints = [int(x) for x in re.findall(r"^Q1464_BRANCH (\d+)$", log, re.M)]
        work = [list(map(int, x)) for x in re.findall(
            r"^Q1473_WORK (\d+) (\d+) (\d+)$", log, re.M)]
        assert [item[0] for item in work] == checkpoints
        assert checkpoints == [1 << index for index in range(len(checkpoints))]
        assert row["branch_checkpoints"] == checkpoints and row["work_checkpoints"] == work
        assert row["branch_lower_bound"] == (checkpoints[-1] if checkpoints else 0)
        assert row["search_started"] == ("Q1458_SEARCH_START" in log)
        marker_ok = (log.splitlines().count("Q1469_ORDER selector_pair_mids 168") == 1 and
                     log.splitlines().count("Q1472_PHASE 0 0") == 1 and
                     log.splitlines().count(f"Q1473_SELECTOR_PHASE {phase} 2140 2141") == 1)
        assert row["marker_ok"] == marker_ok
        at_cap = next((item for item in work if item[0] == protocol[
            "checkpoint_left_branches"]), None)
        assert row["cnf_set_true_calls_at_checkpoint"] == (at_cap[1] if at_cap else None)
        assert row["xor_set_true_calls_at_checkpoint"] == (at_cap[2] if at_cap else None)
        if row["status"] == "CHECKPOINT_TERMINATED":
            assert at_cap and marker_ok and row["search_started"]
            assert row["verified_natural_relations"] == 0
        elif row["status"] == "VERIFIED_RELATION":
            assert row["verified_natural_relations"] == 1
            assert row["group_replay"]["status"] == "verified_four_point_relation"
        else:
            assert row["status"] in ("CENSORED_BEFORE_SEARCH", "WALL_CAP_SEARCH_STARTED",
                                     "CPU_CAP_BEFORE_SEARCH", "CPU_CAP_SEARCH_STARTED",
                                     "PRODUCER_FAILURE", "MODEL_REPLAY_FAILED")
        assert row["complete_n83_decomposition_work_log2"] is None
        assert row["complete_n131_solve_work_log2"] is None
        rows.append(row)
    assert rows and drive["new_ordinary_attempts"] == len(rows)
    assert drive["phase_statuses"] == [row["status"] for row in rows]
    assert drive["new_verified_relations"] == sum(row["verified_natural_relations"] for row in rows)
    assert abs(drive["new_ordinary_wall_seconds_exploratory"] - sum(
        row["solver_wall_seconds_exploratory"] for row in rows)) < 1e-8
    assert abs(drive["new_ordinary_user_cpu_seconds"] - sum(
        row["user_cpu_seconds"] for row in rows)) < 1e-8
    assert drive["complete_n83_decomposition_work_log2"] is None
    assert drive["complete_n131_solve_work_log2"] is None
    assert drive["degree131_challenge_gap_bits"] is None
    print("PASS Q1474", len(rows), "ordinary phases", [row["status"] for row in rows])


if __name__ == "__main__":
    main()
