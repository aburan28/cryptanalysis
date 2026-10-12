#!/usr/bin/env python3
"""Freeze Q1469 priority code and exact N53/N83 inputs before timing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from priorities import MODES, priorities

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1467 = PARENT / "q20261011_wdsat_order"
Q1464 = PARENT / "q20261011_wdsat_workprobe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_path = Q1467 / "freeze.json"
    parent = json.loads(parent_path.read_text())
    order_path = Q1467 / "order_manifest.json"
    prior_verification = json.loads((Q1467 / "verification.json").read_text())
    assert protocol["proposal_id"] == "Q1469"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert tuple(protocol["modes"]) == MODES
    assert prior_verification["status"] == "PASS" and len(prior_verification["runs"]) == 8
    arrays = {f"n{degree}": priorities(degree) for degree in (53, 83)}
    output = {
        "proposal_id": "Q1469", "candidate_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "freeze_source_sha256": sha(Path(__file__)),
        "priority_source_sha256": sha(HERE / "priorities.py"),
        "build_source_sha256": sha(HERE / "build.py"),
        "runner_source_sha256": sha(HERE / "run.py"),
        "q1464_build_source_sha256": sha(Q1464 / "build.py"),
        "q1467_freeze_sha256": sha(parent_path),
        "q1467_build_receipt_sha256": sha(Q1467 / "build_receipt.json"),
        "q1467_order_manifest_sha256": sha(order_path),
        "q1467_verification_sha256": sha(Q1467 / "verification.json"),
        "upstream_commit": protocol["solver"]["upstream_commit"],
        "priority_arrays": arrays,
        "cells": parent["cells"],
    }
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1469 frozen", len(arrays), "degrees and", len(MODES), "modes")


if __name__ == "__main__":
    main()
