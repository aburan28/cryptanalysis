#!/usr/bin/env python3
"""Freeze Q1466's exact N53/N83 controls, ordinary inputs, and budgets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1463 = PARENT / "q20261011_wdsat_ordinary"
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
Q1464 = PARENT / "q20261011_wdsat_workprobe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent = json.loads((Q1464 / "freeze.json").read_text())
    verification = json.loads((Q1464 / "verification.json").read_text())
    profiles = json.loads((PARENT / "q1419_partial_pin/protocol.json").read_text())["profiles"]
    assert protocol["proposal_id"] == "Q1466"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    assert verification["status"] == "PASS" and len(verification["runs"]) == 8
    cells = {}
    for degree in (53, 83):
        name = f"n{degree}"
        data = parent["cells"][name]
        assert data["curve_id"] == profiles[str(degree)]["curve_id"]
        for kind in ("full_lock", "ordinary"):
            cell = f"{name}_{kind}"
            if kind == "ordinary":
                archive = Q1463 / f"{name}_ordinary.xcnf.gz"
                source = PARENT / "runs" / f"{name}_q{1410 if degree == 53 else 1408}_ordinary.xcnf.gz"
                archive_key, source_key, raw_key, variables_key = (
                    "ordinary_archive_sha256", "ordinary_source_archive_sha256",
                    "ordinary_raw_sha256", "ordinary_variables")
                workload = data["ordinary_workload_id"]
                target = data["public_target"]
            else:
                archive = Q1460 / f"{name}_full_lock.xcnf.gz"
                source = PARENT / "q1419_partial_pin/runs" / f"{name}_full_lock/system.xcnf.gz"
                archive_key, source_key, raw_key, variables_key = (
                    "control_archive_sha256", "control_source_archive_sha256",
                    "control_raw_sha256", "control_variables")
                workload = profiles[str(degree)]["workload_id"]
                target = profiles[str(degree)]["public_target"]
            assert sha(archive) == data[archive_key]
            assert sha(source) == data[source_key]
            cells[cell] = {"curve_id": data["curve_id"], "degree": degree,
                           "kind": kind, "workload_id": workload,
                           "public_target": target,
                           "factor_base_actual_B": data["factor_base_actual_B"],
                           "factor_base_folded_columns_K": data["factor_base_folded_columns_K"],
                           "factor_base_enumerated_set_sha256": data["factor_base_enumerated_set_sha256"],
                           "derived_archive_sha256": sha(archive),
                           "derived_raw_sha256": data[raw_key],
                           "source_archive_sha256": sha(source),
                           "derived_variables": data[variables_key]}
    output = {"proposal_id": "Q1466", "candidate_id": None,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "freeze_source_sha256": sha(Path(__file__)),
              "build_source_sha256": sha(HERE / "build.py"),
              "q1464_build_source_sha256": sha(Q1464 / "build.py"),
              "q1464_build_receipt_sha256": sha(Q1464 / "build_receipt.json"),
              "q1464_freeze_sha256": sha(Q1464 / "freeze.json"),
              "q1464_verification_sha256": sha(Q1464 / "verification.json"),
              "profiles_protocol_sha256": sha(PARENT / "q1419_partial_pin/protocol.json"),
              "upstream_commit": protocol["solver"]["upstream_commit"],
              "cells": cells}
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1466 frozen", len(cells), "cells")


if __name__ == "__main__":
    main()
