#!/usr/bin/env python3
"""Bind the unpinned N53 slice to its archived satisfiable witness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from chain_s3 import field  # noqa: E402
from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1448_torsion_phi5.build_formula import ORDINARY, transformed_targets  # noqa: E402
from q1449_phi5_native_xor.common import sha, sha_bytes, xcnf_bytes  # noqa: E402
from q1451_phi5_fixed_target.build_formula import build  # noqa: E402

OUTPUT = HERE / "controls.json"
TARGET_INDEX = 201


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    parent_path = PARENT / "q1451_phi5_fixed_target/protocol.json"
    parent_controls_path = PARENT / "q1451_phi5_fixed_target/controls.json"
    validation_path = PARENT / "q1448_torsion_phi5/validation.json"
    parent = json.loads(parent_path.read_text())
    parent_controls = json.loads(parent_controls_path.read_text())
    validation = json.loads(validation_path.read_text())
    ordinary = json.loads(ORDINARY[53].read_text())
    witness = next(row for row in validation["rows"] if row["degree_n"] == 53)
    prior_control = next(row for row in parent_controls["rows"]
                         if row["degree_n"] == 53)
    assert parent["proposal_id"] == "Q1451"
    assert parent_controls["status"] == "pass"
    assert ordinary["raw_preimage_x_coordinates"][TARGET_INDEX] == (
        witness["raw_target_x"])
    assert witness["raw_target_x"] == prior_control["raw_target_x"]
    assert witness["public_target"] == ordinary["public_target"]
    assert prior_control["verified_relation"]["status"] == (
        "verified_four_point_relation")
    assert prior_control["verified_relation"]["public_target"] == (
        ordinary["public_target"])
    assert prior_control["verified_relation"]["raw_leaf_x"] == (
        witness["raw_leaf_x"])
    formula, meta = build(53, target_index=TARGET_INDEX)
    assert meta["raw_target_x_values"] == [witness["raw_target_x"]]
    assert meta["target_preimage_index"] == TARGET_INDEX
    assert meta["public_target"] == ordinary["public_target"]
    onb = field.Onb(53)
    for bits, mask in zip(meta["leaf_x_variables"], witness["raw_leaf_x"]):
        pin_bits(formula, bits, mask)
    for bits, mask in zip(meta["leaf_phi_variables"], witness["raw_leaf_x"]):
        pin_bits(formula, bits, transformed_targets(onb, [mask])[0])
    pinned_hash = sha_bytes(xcnf_bytes(formula))
    assert pinned_hash == prior_control["xcnf_sha256"]
    output = {
        "kind": "q1452_known_satisfiable_n53_slice_control",
        "proposal_id": "Q1452", "candidate_id": None,
        "isogeny": "none", "status": "pass",
        "degree_n": 53,
        "target_preimage_index": TARGET_INDEX,
        "selected_raw_target_x": witness["raw_target_x"],
        "public_target": ordinary["public_target"],
        "known_witness_raw_leaf_x": witness["raw_leaf_x"],
        "known_witness_distinct_columns": prior_control[
            "verified_relation"]["distinct_columns"],
        "pinned_xcnf_sha256": pinned_hash,
        "archived_pinned_solver_exit_code": prior_control["solver_exit_code"],
        "archived_pinned_verified_relation": prior_control[
            "verified_relation"],
        "witness_not_supplied_to_ordinary_solver": True,
        "parent_q1451_protocol_sha256": sha(parent_path),
        "parent_q1451_controls_sha256": sha(parent_controls_path),
        "q1448_validation_sha256": sha(validation_path),
        "ordinary_workload_sha256": sha(ORDINARY[53]),
        "cms_binary_sha256": parent["cms_binary_sha256"],
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
    }
    if args.check:
        assert output == json.loads(OUTPUT.read_text())
        print("Q1452 archived N53 satisfiability control: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
        print("Q1452 archived N53 satisfiability control: PASS")


if __name__ == "__main__":
    main()
