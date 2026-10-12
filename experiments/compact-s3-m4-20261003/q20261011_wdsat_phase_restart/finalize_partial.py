#!/usr/bin/env python3
"""Record the infrastructure stop after the frozen phase-6 wall cap."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(kind: str, phase: int) -> dict:
    return json.loads((HERE / "runs" / kind / f"phase{phase}" /
                       "receipt.json").read_text())


def main() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    assert not (HERE / "termination.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    target = json.loads((HERE / "target.json").read_text())
    assert protocol["proposal_id"] == "Q1472"
    assert protocol["solver"]["phase_indices"] == list(range(9))
    controls = [receipt("control", phase) for phase in range(7)]
    ordinary = [receipt("ordinary", phase) for phase in range(7)]
    assert all(row["status"] == "SAT_REPLAYED_XCNF" for row in controls)
    assert all(row["status"] == "BRANCH_CAP_REACHED" for row in ordinary[:6])
    assert ordinary[6]["status"] == "WALL_CAP_SEARCH_STARTED"
    assert ordinary[6]["branch_lower_bound"] == 1 << 18
    for phase in (7, 8):
        assert not (HERE / "runs" / "ordinary" / f"phase{phase}" /
                    "receipt.json").exists()
        assert not (HERE / "runs" / "control" / f"phase{phase}" /
                    "receipt.json").exists()
    phase7_control = HERE / "runs/control/phase7"
    assert phase7_control.is_dir() and not any(phase7_control.iterdir())
    termination = {
        "proposal_id": "Q1472", "candidate_id": None,
        "workload_id": target["workload_id"],
        "status": "INFRASTRUCTURE_TERMINATED_AFTER_PHASE6",
        "reason": "phase 6 reached the 900-second wall cap after only 48.83 solver user CPU seconds under severe host contention; remaining phases were stopped before their ordinary attempts",
        "frozen_schedule_departure": "planned phases 0..8; ordinary phases 0..6 completed; control phase 7 was interrupted without a receipt; phases 7 and 8 ordinary unattempted",
        "last_completed_ordinary_phase": 6,
        "last_completed_ordinary_receipt_sha256": sha(HERE /
            "runs/ordinary/phase6/receipt.json"),
        "interrupted_control_phase": 7,
        "interrupted_control_cost": None,
        "phase6_user_cpu_seconds": ordinary[6]["user_cpu_seconds"],
        "phase6_solver_wall_seconds": ordinary[6]["solver_wall_seconds_exploratory"],
        "phase6_branch_lower_bound": ordinary[6]["branch_lower_bound"],
        "unattempted_ordinary_phases": [7, 8],
        "source_sha256": sha(Path(__file__)),
    }
    (HERE / "termination.json").write_text(json.dumps(
        termination, indent=2, sort_keys=True) + "\n")
    attempts = []
    for phase, row in enumerate(ordinary):
        attempts.append({
            "phase": phase, "status": row["status"],
            "receipt_sha256": sha(HERE / "runs" / "ordinary" /
                                  f"phase{phase}" / "receipt.json"),
            "branch_lower_bound": row["branch_lower_bound"],
            "user_cpu_seconds": row["user_cpu_seconds"],
            "run_wall_seconds_exploratory": row[
                "run_wall_seconds_exploratory"],
        })
    drive = {
        "proposal_id": "Q1472", "candidate_id": None,
        "workload_id": target["workload_id"], "target_count": 1,
        "attempts": attempts,
        "planned_phase_indices": list(range(9)),
        "completed_ordinary_phase_indices": list(range(7)),
        "unattempted_ordinary_phase_indices": [7, 8],
        "stop_status": termination["status"],
        "termination_sha256": sha(HERE / "termination.json"),
        "total_user_cpu_seconds_exploratory": sum(
            row["user_cpu_seconds"] for row in ordinary),
        "total_target_dependent_wall_seconds_exploratory": (
            target["target_preimage_seconds_exploratory"] +
            target["formula_build_seconds_exploratory"] +
            sum(row["run_wall_seconds_exploratory"] for row in ordinary)),
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "target_sha256": sha(HERE / "target.json"),
    }
    (HERE / "drive_receipt.json").write_text(json.dumps(
        drive, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": termination["status"],
                      "attempts": len(attempts),
                      "branch_lower_bound": sum(row["branch_lower_bound"]
                                                for row in attempts)}, sort_keys=True))


if __name__ == "__main__":
    main()
