#!/usr/bin/env python3
"""Freeze the Q1467 search order, inherited instances, and executable sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1466 = PARENT / "q20261011_wdsat_deep_plain"
Q1464 = PARENT / "q20261011_wdsat_workprobe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    manifest = json.loads((HERE / "order_manifest.json").read_text())
    prior_freeze_path = Q1466 / "freeze.json"
    prior_build_path = Q1466 / "build_receipt.json"
    prior_freeze = json.loads(prior_freeze_path.read_text())
    verification = json.loads((Q1466 / "verification.json").read_text())
    assert protocol["proposal_id"] == manifest["proposal_id"] == "Q1467"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert verification["status"] == "PASS" and len(verification["runs"]) == 4
    assert manifest["protocol_sha256"] == sha(HERE / "protocol.json")
    assert manifest["source_sha256"] == sha(HERE / "prepare.py")
    assert manifest["q1466_freeze_sha256"] == sha(prior_freeze_path)
    cells = {}
    for degree in (53, 83):
        name = f"n{degree}"
        order = manifest["cells"][name]
        for kind in ("full_lock", "ordinary"):
            cell = f"{name}_{kind}"
            source = prior_freeze["cells"][cell]
            if kind == "ordinary":
                assert source["curve_id"] == order["curve_id"]
                assert source["workload_id"] == order["ordinary_workload_id"]
                assert source["factor_base_actual_B"] == order["factor_base_actual_B"]
                assert source["factor_base_enumerated_set_sha256"] == order["factor_base_enumerated_set_sha256"]
                assert source["source_archive_sha256"] == sha(PARENT / "runs" / f"{name}_q{1410 if degree == 53 else 1408}_ordinary.xcnf.gz")
            cells[cell] = source
    output = {
        "proposal_id": "Q1467", "candidate_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "prepare_source_sha256": sha(HERE / "prepare.py"),
        "order_manifest_sha256": sha(HERE / "order_manifest.json"),
        "freeze_source_sha256": sha(Path(__file__)),
        "build_source_sha256": sha(HERE / "build.py"),
        "runner_source_sha256": sha(HERE / "run.py"),
        "q1466_freeze_sha256": sha(prior_freeze_path),
        "q1466_build_receipt_sha256": sha(prior_build_path),
        "q1466_verification_sha256": sha(Q1466 / "verification.json"),
        "q1464_build_source_sha256": sha(Q1464 / "build.py"),
        "upstream_commit": protocol["solver"]["upstream_commit"],
        "cells": cells,
    }
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1467 frozen", len(cells), "instances")


if __name__ == "__main__":
    main()
