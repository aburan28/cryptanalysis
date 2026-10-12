#!/usr/bin/env python3
"""Freeze Q1471's exact XG inputs, selected orders, executable and caps."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from priorities import priorities

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1469 = PARENT / "q20261011_wdsat_prefix_search"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_path = Q1469 / "freeze.json"
    parent = json.loads(parent_path.read_text())
    build_path = Q1469 / "build_receipt.json"
    build = json.loads(build_path.read_text())
    screen_path = Q1469 / "analysis.json"
    screen = json.loads(screen_path.read_text())
    verification = json.loads((Q1469 / "verification.json").read_text())
    assert protocol["proposal_id"] == "Q1471"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["limits"]["left_branch_attempts_per_run"] == 1 << 20
    assert verification["status"] == "PASS" and len(verification["runs"]) == 12
    assert sha(HERE / "priorities.py") == sha(Q1469 / "priorities.py")
    winners = {str(row["degree"]): row["mode"] for row in screen[
        "single_query_exploratory_winners"]}
    assert protocol["selected_mode_by_degree"] == winners
    assert protocol["solver"]["command_flag"] == "-x"
    cells = parent["cells"]
    baselines = {}
    for degree in (53, 83):
        name = f"n{degree}"
        mode = winners[str(degree)]
        binary = Path(build["per_degree"][name]["binary_path"])
        assert sha(binary) == build["per_degree"][name]["binary_sha256"]
        baseline_path = Q1469 / "runs" / f"{name}_ordinary" / mode / "receipt.json"
        baseline = json.loads(baseline_path.read_text())
        assert baseline["status"] == "BRANCH_CAP_REACHED"
        assert baseline["left_branch_attempt_limit"] == 1 << 20
        assert baseline["cpu_soft_limit_seconds"] == protocol["limits"]["cpu_seconds_soft"]
        assert baseline["wall_limit_seconds"] == protocol["limits"]["wall_seconds_per_run"]
        assert priorities(degree)[mode] == parent["priority_arrays"][name][mode]
        baselines[name] = {"mode": mode, "receipt_sha256": sha(baseline_path),
                           "binary_sha256": sha(binary)}
    output = {"proposal_id": "Q1471", "candidate_id": None,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "freeze_source_sha256": sha(Path(__file__)),
              "runner_source_sha256": sha(HERE / "run.py"),
              "priority_source_sha256": sha(HERE / "priorities.py"),
              "q1469_priority_source_sha256": sha(Q1469 / "priorities.py"),
              "q1469_freeze_sha256": sha(parent_path),
              "q1469_build_receipt_sha256": sha(build_path),
              "q1469_analysis_sha256": sha(screen_path),
              "q1469_verification_sha256": sha(Q1469 / "verification.json"),
              "upstream_commit": protocol["solver"]["upstream_commit"],
              "priority_arrays": parent["priority_arrays"],
              "baseline": baselines, "cells": cells}
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1471 frozen", len(baselines), "degrees")


if __name__ == "__main__":
    main()
