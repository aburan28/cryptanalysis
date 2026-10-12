#!/usr/bin/env python3
"""Charge sequential phase attempts to one frozen ordinary N83 target."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from phase_schedule import INDICES

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(kind: str, phase: int) -> dict | None:
    path = HERE / "runs" / kind / f"phase{phase}" / "receipt.json"
    return json.loads(path.read_text()) if path.exists() else None


def run(kind: str, phase: int) -> dict:
    previous = receipt(kind, phase)
    if previous is not None:
        return previous
    print("START", kind, phase, flush=True)
    subprocess.run([sys.executable, str(HERE / "run.py"), kind, str(phase)], check=True)
    current = receipt(kind, phase)
    assert current is not None
    return current


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["proposal_id"] == "Q1472"
    assert tuple(protocol["solver"]["phase_indices"]) == INDICES
    assert receipt("control", 0)["status"] == "SAT_REPLAYED_XCNF"
    assert receipt("ordinary", 0) is not None
    for phase in INDICES[1:]:
        control = run("control", phase)
        print("CONTROL", phase, control["status"], flush=True)
        ordinary = run("ordinary", phase)
        print("ORDINARY", phase, ordinary["status"], flush=True)
        if ordinary["status"] == "VERIFIED_RELATION":
            break
    ordinary_rows = []
    for phase in INDICES:
        row = receipt("ordinary", phase)
        if row is None:
            break
        ordinary_rows.append({"phase": phase, "status": row["status"],
                              "receipt_sha256": sha(HERE / "runs" / "ordinary" /
                                                    f"phase{phase}" / "receipt.json"),
                              "branch_lower_bound": row["branch_lower_bound"],
                              "user_cpu_seconds": row["user_cpu_seconds"],
                              "run_wall_seconds_exploratory": row[
                                  "run_wall_seconds_exploratory"]})
        if row["status"] == "VERIFIED_RELATION":
            break
    target = json.loads((HERE / "target.json").read_text())
    output = {"proposal_id": "Q1472", "candidate_id": None,
              "workload_id": target["workload_id"], "target_count": 1,
              "attempts": ordinary_rows,
              "stop_status": ("VERIFIED_RELATION" if ordinary_rows[-1]["status"] ==
                              "VERIFIED_RELATION" else "PHASE_SCHEDULE_EXHAUSTED"),
              "total_user_cpu_seconds_exploratory": sum(
                  row["user_cpu_seconds"] for row in ordinary_rows),
              "total_target_dependent_wall_seconds_exploratory": (
                  target["target_preimage_seconds_exploratory"] +
                  target["formula_build_seconds_exploratory"] +
                  sum(row["run_wall_seconds_exploratory"] for row in ordinary_rows)),
              "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(HERE / "protocol.json"),
              "target_sha256": sha(HERE / "target.json")}
    path = HERE / "drive_receipt.json"
    assert not path.exists()
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("STOP", output["stop_status"], len(ordinary_rows), flush=True)


if __name__ == "__main__":
    main()
