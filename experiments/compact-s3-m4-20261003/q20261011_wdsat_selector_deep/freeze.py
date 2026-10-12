#!/usr/bin/env python3
"""Freeze the Q1468 deeper search before solver timing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1467 = PARENT / "q20261011_wdsat_order"
Q1464 = PARENT / "q20261011_wdsat_workprobe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent_freeze_path = Q1467 / "freeze.json"
    parent_build_path = Q1467 / "build_receipt.json"
    order_path = Q1467 / "order_manifest.json"
    parent = json.loads(parent_freeze_path.read_text())
    prior_verification = json.loads((Q1467 / "verification.json").read_text())
    assert protocol["proposal_id"] == "Q1468"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert protocol["limits"]["left_branch_attempts_per_run"] == 1 << 23
    assert prior_verification["status"] == "PASS" and len(prior_verification["runs"]) == 8
    output = {
        "proposal_id": "Q1468", "candidate_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "freeze_source_sha256": sha(Path(__file__)),
        "build_source_sha256": sha(HERE / "build.py"),
        "runner_source_sha256": sha(HERE / "run.py"),
        "q1464_build_source_sha256": sha(Q1464 / "build.py"),
        "q1467_freeze_sha256": sha(parent_freeze_path),
        "q1467_build_receipt_sha256": sha(parent_build_path),
        "q1467_order_manifest_sha256": sha(order_path),
        "q1467_verification_sha256": sha(Q1467 / "verification.json"),
        "upstream_commit": protocol["solver"]["upstream_commit"],
        "cells": parent["cells"],
    }
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1468 frozen", len(output["cells"]), "instances")


if __name__ == "__main__":
    main()
