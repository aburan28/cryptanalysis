#!/usr/bin/env python3
"""Freeze Q1464 source, controls, ordinary queries, and branch budget."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
Q1463 = PARENT / "q20261011_wdsat_ordinary"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    ordinary = json.loads((Q1463 / "freeze.json").read_text())
    controls = json.loads((Q1460 / "prepare_receipt.json").read_text())
    control_profiles = json.loads((PARENT / "q1419_partial_pin/protocol.json").read_text())["profiles"]
    verification = json.loads((Q1463 / "verification.json").read_text())
    assert protocol["proposal_id"] == "Q1464"
    assert verification["status"] == "PASS" and len(verification["runs"]) == 4
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == "none"
    cells = {}
    for degree in (53, 83):
        name = f"n{degree}"
        ordinary_record = ordinary["cells"][name]
        ordinary_archive = Q1463 / f"{name}_ordinary.xcnf.gz"
        control_name = f"{name}_full_lock"
        control_record = controls["cells"][control_name]
        control_archive = Q1460 / f"{control_name}.xcnf.gz"
        assert sha(ordinary_archive) == ordinary_record["derived_archive_sha256"]
        assert sha(control_archive) == control_record["derived_archive_sha256"]
        assert ordinary_record["curve_id"] == control_profiles[str(degree)]["curve_id"]
        assert ordinary_record["factor_base_actual_B"] == control_profiles[str(degree)]["factor_base_actual_B"]
        assert ordinary_record["factor_base_enumerated_set_sha256"] == control_profiles[str(degree)]["factor_base_enumerated_set_sha256"]
        cells[name] = {
            "curve_id": ordinary_record["curve_id"],
            "ordinary_workload_id": ordinary_record["workload_id"],
            "factor_base_actual_B": ordinary_record["factor_base_actual_B"],
            "factor_base_folded_columns_K": ordinary_record["factor_base_folded_columns_K"],
            "factor_base_enumerated_set_sha256": ordinary_record["factor_base_enumerated_set_sha256"],
            "public_target": ordinary_record["public_target"],
            "ordinary_archive_sha256": sha(ordinary_archive),
            "ordinary_source_archive_sha256": ordinary_record["source_archive_sha256"],
            "ordinary_raw_sha256": ordinary_record["derived_raw_sha256"],
            "ordinary_variables": ordinary_record["transform_stats"]["derived_variables"],
            "control_archive_sha256": sha(control_archive),
            "control_raw_sha256": control_record["derived_raw_sha256"],
            "control_source_archive_sha256": control_record["source_archive_sha256"],
            "control_variables": control_record["derived_variables"]}
    output = {"proposal_id": "Q1464", "candidate_id": None,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "freeze_source_sha256": sha(Path(__file__)),
              "build_source_sha256": sha(HERE / "build.py"),
              "shared_patch_source_sha256": sha(PARENT / "q20261011_wdsat_bridge/build.py"),
              "upstream_commit": protocol["solver"]["upstream_commit"],
              "parent_build_receipt_sha256": sha(Q1460 / "build_receipt.json"),
              "parent_control_prepare_receipt_sha256": sha(Q1460 / "prepare_receipt.json"),
              "control_profiles_protocol_sha256": sha(PARENT / "q1419_partial_pin/protocol.json"),
              "parent_ordinary_freeze_sha256": sha(Q1463 / "freeze.json"),
              "parent_ordinary_verification_sha256": sha(Q1463 / "verification.json"),
              "cells": cells}
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1464 frozen", len(cells), "degrees")


if __name__ == "__main__":
    main()
