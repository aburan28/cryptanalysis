#!/usr/bin/env python3
"""Freeze Q1470 selected prefixes and matched deeper-search baselines."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from priorities import priorities

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1464 = PARENT / "q20261011_wdsat_workprobe"
Q1467 = PARENT / "q20261011_wdsat_order"
Q1468 = PARENT / "q20261011_wdsat_selector_deep"
Q1469 = PARENT / "q20261011_wdsat_prefix_search"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_path = Q1469 / "freeze.json"
    parent = json.loads(parent_path.read_text())
    screen = json.loads((Q1469 / "analysis.json").read_text())
    deeper = json.loads((Q1468 / "verification.json").read_text())
    assert protocol["proposal_id"] == "Q1470"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["limits"]["left_branch_attempts_per_run"] == 1 << 23
    assert screen["status"] == "COMPLETE_PREFIX_SCREEN"
    assert deeper["status"] == "PASS" and len(deeper["runs"]) == 4
    assert sha(HERE / "priorities.py") == sha(Q1469 / "priorities.py")
    winners = {str(row["degree"]): row["mode"] for row in screen[
        "single_query_exploratory_winners"]}
    assert protocol["selected_mode_by_degree"] == winners
    arrays = {f"n{degree}": priorities(degree) for degree in (53, 83)}
    assert arrays == parent["priority_arrays"]
    output = {
        "proposal_id": "Q1470", "candidate_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "freeze_source_sha256": sha(Path(__file__)),
        "priority_source_sha256": sha(HERE / "priorities.py"),
        "build_source_sha256": sha(HERE / "build.py"),
        "runner_source_sha256": sha(HERE / "run.py"),
        "q1464_build_source_sha256": sha(Q1464 / "build.py"),
        "q1467_order_manifest_sha256": sha(Q1467 / "order_manifest.json"),
        "q1468_build_receipt_sha256": sha(Q1468 / "build_receipt.json"),
        "q1468_verification_sha256": sha(Q1468 / "verification.json"),
        "q1469_priority_source_sha256": sha(Q1469 / "priorities.py"),
        "q1469_freeze_sha256": sha(parent_path),
        "q1469_analysis_sha256": sha(Q1469 / "analysis.json"),
        "upstream_commit": protocol["solver"]["upstream_commit"],
        "priority_arrays": arrays,
        "cells": parent["cells"],
    }
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1470 frozen", len(winners), "selected modes")


if __name__ == "__main__":
    main()
