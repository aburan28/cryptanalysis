#!/usr/bin/env python3
"""Charge the four selector masks sequentially to one existing N83 target."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from phase_schedule import INDICES

HERE = Path(__file__).resolve().parent
Q1472 = HERE.parent / "q20261011_wdsat_phase_restart"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row(kind: str, phase: int) -> dict | None:
    path = HERE / "runs" / kind / f"phase{phase}" / "receipt.json"
    return json.loads(path.read_text()) if path.exists() else None


def run(kind: str, phase: int) -> dict:
    previous = row(kind, phase)
    if previous is not None:
        return previous
    print("START", kind, phase, flush=True)
    subprocess.run([sys.executable, str(HERE / "run.py"), kind, str(phase)],
                   check=True)
    current = row(kind, phase)
    assert current is not None
    return current


def main() -> None:
    path = HERE / "drive_receipt.json"
    assert not path.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    freeze = json.loads((HERE / "freeze.json").read_text())
    target = json.loads((HERE / "target.json").read_text())
    parent_path = Q1472 / "drive_receipt.json"
    parent = json.loads(parent_path.read_text())
    assert protocol["proposal_id"] == "Q1473"
    assert freeze["drive_source_sha256"] == sha(Path(__file__))
    assert tuple(protocol["solver"]["phase_indices"]) == INDICES
    assert parent["workload_id"] == target["workload_id"]
    assert parent["stop_status"] == "INFRASTRUCTURE_TERMINATED_AFTER_PHASE6"
    stop = "SCREEN_COMPLETED_WITHOUT_RELATION"
    for phase in INDICES:
        control = run("control", phase)
        print("CONTROL", phase, control["status"], flush=True)
        if control["status"] != "SAT_REPLAYED_XCNF":
            stop = "CONTROL_GATE_FAILED"
            break
        ordinary = run("ordinary", phase)
        print("ORDINARY", phase, ordinary["status"], flush=True)
        if ordinary["status"] == "VERIFIED_RELATION":
            stop = "VERIFIED_RELATION"
            break
        if ordinary["status"] != "BRANCH_CAP_REACHED":
            stop = "ORDINARY_CENSORED_OR_FAILED"
            break
    controls, ordinary_rows = [], []
    for phase in INDICES:
        control = row("control", phase)
        ordinary = row("ordinary", phase)
        if control is not None:
            controls.append({"phase": phase, "status": control["status"],
                             "receipt_sha256": sha(HERE / "runs" / "control" /
                                                   f"phase{phase}" / "receipt.json")})
        if ordinary is not None:
            ordinary_rows.append({
                "phase": phase, "status": ordinary["status"],
                "receipt_sha256": sha(HERE / "runs" / "ordinary" /
                                      f"phase{phase}" / "receipt.json"),
                "branch_lower_bound": ordinary["branch_lower_bound"],
                "cnf_set_true_calls_lower_bound": ordinary[
                    "cnf_set_true_calls_lower_bound"],
                "xor_set_true_calls_lower_bound": ordinary[
                    "xor_set_true_calls_lower_bound"],
                "user_cpu_seconds": ordinary["user_cpu_seconds"],
                "run_wall_seconds_exploratory": ordinary[
                    "run_wall_seconds_exploratory"],
            })
    charged_wall = sum(x["run_wall_seconds_exploratory"] for x in ordinary_rows)
    output = {
        "proposal_id": "Q1473", "candidate_id": None,
        "workload_id": target["workload_id"], "target_count": 1,
        "planned_phase_indices": list(INDICES),
        "controls": controls, "ordinary_attempts": ordinary_rows,
        "unattempted_ordinary_phase_indices": [i for i in INDICES
                                                if row("ordinary", i) is None],
        "stop_status": stop,
        "new_ordinary_branch_lower_bound": sum(x["branch_lower_bound"]
                                               for x in ordinary_rows),
        "new_ordinary_solver_child_user_cpu_seconds_exploratory": sum(
            x["user_cpu_seconds"] for x in ordinary_rows),
        "new_ordinary_wall_seconds_exploratory": charged_wall,
        "prior_q1472_charged_wall_seconds_exploratory": parent[
            "total_target_dependent_wall_seconds_exploratory"],
        "cumulative_same_target_wall_seconds_exploratory": (
            parent["total_target_dependent_wall_seconds_exploratory"] +
            charged_wall),
        "prior_q1472_branch_lower_bound": sum(x["branch_lower_bound"]
                                               for x in parent["attempts"]),
        "prior_q1472_drive_sha256": sha(parent_path),
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "target_sha256": sha(HERE / "target.json"),
    }
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("STOP", stop, len(ordinary_rows), flush=True)


if __name__ == "__main__":
    main()
