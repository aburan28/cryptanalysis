#!/usr/bin/env python3
"""Freeze the four N83 selector masks and all executed source/input identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from phase_schedule import INDICES, phases

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1472 = PARENT / "q20261011_wdsat_phase_restart"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = HERE / "freeze.json"
    assert not path.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    target_path = Q1472 / "target.json"
    target = json.loads(target_path.read_text())
    parent_freeze_path = Q1472 / "freeze.json"
    parent = json.loads(parent_freeze_path.read_text())
    runtime_path = HERE / "sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    assert protocol["proposal_id"] == "Q1473"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["workload_id"] == target["workload_id"]
    assert protocol["curve_id"] == target["curve_id"]
    assert protocol["factor_base_actual_B"] == target["factor_base_actual_B"]
    assert protocol["factor_base_folded_columns_K"] == target[
        "factor_base_folded_columns_K"]
    assert protocol["isogeny"] == target["isogeny"] == "none"
    assert tuple(protocol["solver"]["phase_indices"]) == INDICES
    assert parent["target_sha256"] == sha(target_path)
    for cell in parent["cells"].values():
        assert sha(Path(cell["source_archive_path"])) == cell[
            "source_archive_sha256"]
        assert sha(Path(cell["derived_archive_path"])) == cell[
            "derived_archive_sha256"]
    schedule = phases()
    assert [schedule[i]["flip_ids"] for i in INDICES] == [
        [], [2140], [2141], [2140, 2141]]
    output = {
        "proposal_id": "Q1473", "candidate_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runtime_info_sha256": sha(runtime_path),
        "target_sha256": sha(target_path),
        "q1472_freeze_sha256": sha(parent_freeze_path),
        "q1472_build_source_sha256": sha(Q1472 / "build.py"),
        "q1472_build_receipt_sha256": sha(Q1472 / "build_receipt.json"),
        "q1472_run_source_sha256": sha(Q1472 / "run.py"),
        "q1472_analysis_sha256": sha(Q1472 / "analysis.json"),
        "phase_source_sha256": sha(HERE / "phase_schedule.py"),
        "build_source_sha256": sha(HERE / "build.py"),
        "runner_source_sha256": sha(HERE / "run.py"),
        "drive_source_sha256": sha(HERE / "drive.py"),
        "freeze_source_sha256": sha(Path(__file__)),
        "phase_schedule": {str(i): schedule[i] for i in INDICES},
        "cells": parent["cells"],
    }
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1473 frozen", target["workload_id"], len(schedule), "selector masks")


if __name__ == "__main__":
    main()
