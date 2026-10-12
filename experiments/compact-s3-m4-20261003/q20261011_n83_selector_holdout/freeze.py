#!/usr/bin/env python3
"""Freeze the exact new N83 point, XCNFs, solver, and measurement code."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1472 = PARENT / "q20261011_wdsat_phase_restart"
Q1473 = PARENT / "q20261011_selector_polarity"
Q1474 = PARENT / "q20261011_n83_propagation_probe"
BASE = PARENT / "bases/n83_weight5_full_orbits.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    input_freeze = json.loads((HERE / "input_freeze.json").read_text())
    target = json.loads((HERE / "target.json").read_text())
    prior = json.loads((Q1473 / "freeze.json").read_text())
    smoke = json.loads((Q1473 / "smoke_receipt.json").read_text())
    assert protocol["proposal_id"] == target["proposal_id"] == "Q1476"
    assert protocol["workload_id"] is None
    assert input_freeze["protocol_sha256"] == sha(HERE / "protocol.json")
    assert target["input_freeze_sha256"] == sha(HERE / "input_freeze.json")
    assert target["source_sha256"] == sha(HERE / "prepare_target.py")
    assert target["generator_source_sha256"] == sha(Q1472 / "prepare_target.py")
    assert target["curve_id"] == protocol["curve_id"]
    assert target["factor_base_actual_B"] == protocol["factor_base_actual_B"]
    assert target["factor_base_folded_columns_K"] == protocol[
        "factor_base_folded_columns_K"]
    assert target["base_receipt_sha256"] == sha(BASE)
    assert target["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert target["q1472_target_sha256"] == sha(Q1472 / "target.json")
    assert target["workload_record"]["target_generation"]["seed"] == protocol[
        "target_generation_seed"]
    assert smoke["status"] == "PASS" and len(smoke["rows"]) == 4
    assert sha(Path(input_freeze["binary_path"])) == input_freeze[
        "binary_sha256"] == smoke["binary_sha256"]
    assert protocol["phase_order"] == [0, 1]
    assert prior["phase_schedule"]["1"]["flip_ids"] == [2140]
    archives = {}
    for kind, name in (("source", "original.xcnf.gz"),
                       ("derived", "width4.xcnf.gz")):
        path = HERE / name
        raw = gzip.decompress(path.read_bytes())
        assert sha(path) == target[f"{kind if kind == 'derived' else 'original'}_archive_sha256"]
        assert hashlib.sha256(raw).hexdigest() == target[
            f"{kind if kind == 'derived' else 'original'}_raw_sha256"]
        archives[kind] = {"archive_path": str(path), "archive_sha256": sha(path),
                          "raw_sha256": hashlib.sha256(raw).hexdigest()}
    files = {name: sha(HERE / name) for name in
             ("protocol.json", "input_freeze.py", "prepare_target.py",
              "freeze.py", "run.py", "validate.py")}
    cell = {"kind": "ordinary", "curve_id": target["curve_id"],
            "workload_id": target["workload_id"],
            "public_target": target["public_target"],
            "factor_base_actual_B": target["factor_base_actual_B"],
            "factor_base_folded_columns_K": target["factor_base_folded_columns_K"],
            "factor_base_enumerated_set_sha256": target[
                "factor_base_enumerated_set_sha256"],
            "original_variables": target["original_variables"],
            "derived_variables": target["derived_variables"]}
    for kind in ("source", "derived"):
        cell[f"{kind}_archive_path"] = archives[kind]["archive_path"]
        cell[f"{kind}_archive_sha256"] = archives[kind]["archive_sha256"]
        cell[f"{kind}_raw_sha256"] = archives[kind]["raw_sha256"]
    frozen = {
        "proposal_id": "Q1476", "candidate_id": None, "run_id": None,
        "workload_id": target["workload_id"],
        "files_sha256": files,
        "input_freeze_sha256": sha(HERE / "input_freeze.json"),
        "target_sha256": sha(HERE / "target.json"),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "q1472_generator_sha256": sha(Q1472 / "prepare_target.py"),
        "q1473_smoke_sha256": sha(Q1473 / "smoke_receipt.json"),
        "q1474_runner_sha256": sha(Q1474 / "run.py"),
        "binary_path": input_freeze["binary_path"],
        "binary_sha256": input_freeze["binary_sha256"],
        "ordinary_cell": cell,
        "phase_schedule": prior["phase_schedule"]}
    (HERE / "freeze.json").write_text(json.dumps(frozen, indent=2,
                                                 sort_keys=True) + "\n")
    print("Q1476 target frozen", target["workload_id"])


if __name__ == "__main__":
    main()
