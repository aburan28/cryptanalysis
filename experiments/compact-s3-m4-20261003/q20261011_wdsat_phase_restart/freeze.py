#!/usr/bin/env python3
"""Freeze exact Q1472 controls, new ordinary input, phases, and sources."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from phase_schedule import INDICES, phases

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1460 = PARENT / "q20261011_wdsat_shared_prefix"
Q1464 = PARENT / "q20261011_wdsat_workprobe"
Q1467 = PARENT / "q20261011_wdsat_order"
Q1469 = PARENT / "q20261011_wdsat_prefix_search"
Q1419 = PARENT / "q1419_partial_pin"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cell(kind: str, source: Path, derived: Path, workload_id: str,
         public_target: list[int], target: dict) -> dict:
    raw_source, raw_derived = gzip.decompress(source.read_bytes()), gzip.decompress(derived.read_bytes())
    source_vars = int(raw_source.splitlines()[0].split()[2])
    derived_vars = int(raw_derived.splitlines()[0].split()[2])
    assert (source_vars, derived_vars) == (target["original_variables"],
                                          target["derived_variables"])
    return {"kind": kind, "curve_id": target["curve_id"],
            "workload_id": workload_id, "public_target": public_target,
            "factor_base_actual_B": target["factor_base_actual_B"],
            "factor_base_folded_columns_K": target["factor_base_folded_columns_K"],
            "factor_base_enumerated_set_sha256": target["factor_base_enumerated_set_sha256"],
            "source_archive_path": str(source),
            "source_archive_sha256": sha(source),
            "source_raw_sha256": hashlib.sha256(raw_source).hexdigest(),
            "derived_archive_path": str(derived),
            "derived_archive_sha256": sha(derived),
            "derived_raw_sha256": hashlib.sha256(raw_derived).hexdigest(),
            "original_variables": source_vars, "derived_variables": derived_vars}


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    target_path = HERE / "target.json"
    target = json.loads(target_path.read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    q1469_build_path = Q1469 / "build_receipt.json"
    q1469_build = json.loads(q1469_build_path.read_text())
    q1419_protocol = json.loads((Q1419 / "protocol.json").read_text())
    control_profile = q1419_protocol["profiles"]["83"]
    assert protocol["proposal_id"] == target["proposal_id"] == "Q1472"
    assert protocol["candidate_id"] is protocol["run_id"] is None
    assert protocol["isogeny"] == target["isogeny"] == "none"
    assert protocol["curve_id"] == target["curve_id"] == control_profile["curve_id"]
    assert protocol["workload_id"] == target["workload_id"]
    assert protocol["factor_base_actual_B"] == target["factor_base_actual_B"]
    assert protocol["factor_base_folded_columns_K"] == target["factor_base_folded_columns_K"]
    assert runtime["status"] == "verified"
    assert target["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert target["source_sha256"] == sha(HERE / "prepare_target.py")
    assert target["q1469_build_receipt_sha256"] == sha(q1469_build_path)
    assert target["q1467_order_manifest_sha256"] == sha(Q1467 / "order_manifest.json")
    assert len(protocol["solver"]["phase_indices"]) == len(INDICES)
    assert tuple(protocol["solver"]["phase_indices"]) == INDICES
    schedule = phases()
    assert len(schedule) == 9 and schedule[0]["flip_ids"] == []
    assert q1469_build["per_degree"]["n83"]["branch_patch"]["branch_cap"] == 1 << 20
    control_source = Q1419 / "runs/n83_full_lock/system.xcnf.gz"
    control_derived = Q1460 / "n83_full_lock.xcnf.gz"
    ordinary_source = HERE / "original.xcnf.gz"
    ordinary_derived = HERE / "width4.xcnf.gz"
    assert sha(ordinary_source) == target["original_archive_sha256"]
    assert sha(ordinary_derived) == target["derived_archive_sha256"]
    control = cell("control", control_source, control_derived,
                   control_profile["workload_id"], control_profile["public_target"],
                   target)
    ordinary = cell("ordinary", ordinary_source, ordinary_derived,
                    target["workload_id"], target["public_target"], target)
    q1467_order = json.loads((Q1467 / "order_manifest.json").read_text())["cells"]["n83"]
    assert len(q1467_order["selector_priority"] + q1467_order["pair_mid_first_ids"]) == 168
    output = {"proposal_id": "Q1472", "candidate_id": None,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "target_sha256": sha(target_path),
              "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
              "prepare_target_source_sha256": sha(HERE / "prepare_target.py"),
              "freeze_source_sha256": sha(Path(__file__)),
              "phase_source_sha256": sha(HERE / "phase_schedule.py"),
              "build_source_sha256": sha(HERE / "build.py"),
              "runner_source_sha256": sha(HERE / "run.py"),
              "q1464_build_source_sha256": sha(Q1464 / "build.py"),
              "q1469_build_source_sha256": sha(Q1469 / "build.py"),
              "q1469_build_receipt_sha256": sha(q1469_build_path),
              "q1419_protocol_sha256": sha(Q1419 / "protocol.json"),
              "q1419_group_verifier_source_sha256": sha(Q1419 / "run_cell.py"),
              "q1467_order_manifest_sha256": sha(Q1467 / "order_manifest.json"),
              "upstream_commit": protocol["solver"]["upstream_commit"],
              "phase_schedule": {str(index): schedule[index] for index in INDICES},
              "cells": {"control": control, "ordinary": ordinary}}
    (HERE / "freeze.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1472 frozen", target["workload_id"], len(schedule), "phases")


if __name__ == "__main__":
    main()
