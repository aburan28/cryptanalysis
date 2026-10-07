#!/usr/bin/env python3
"""Freeze Q1493's post-run rotated-CNF witness compatibility control."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_control import DESIGN, HERE, INPUT_PATHS, PROTOCOL, sha


def build() -> dict:
    design = json.loads(DESIGN.read_text())
    assert design["proposal_id"] == "Q1493"
    assert design["control_id"] == "Q1493C1"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert design["rotation"] == 44
    assert design["target_preimage_index"] == 141
    assert design["expected_extra_witness_pins"] == 327
    for label, path in INPUT_PATHS.items():
        assert sha(path) == design["frozen_inputs_sha256"][label], label
    return {
        "kind": "q1493_frozen_rotated_cnf_witness_control_protocol",
        "proposal_id": "Q1493", "control_id": "Q1493C1",
        "candidate_id": None, "run_id": None,
        "isogeny": "none",
        "curve_id": design["curve_id"],
        "field_degree_n": design["field_degree_n"],
        "factor_base_actual_B": design["factor_base_actual_B"],
        "factor_base_folded_columns_K": design[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "rotation": design["rotation"],
        "target_preimage_index": design["target_preimage_index"],
        "expected_extra_witness_pins": design[
            "expected_extra_witness_pins"],
        "native_wall_cap_seconds": design["native_wall_cap_seconds"],
        "external_safeguard_seconds": design[
            "external_safeguard_seconds"],
        "conflict_cap": design["conflict_cap"],
        "pair_candidate_cap": design["pair_candidate_cap"],
        "decision_policy": design["decision_policy"],
        "success_gate": design["success_gate"],
        "design_sha256": sha(DESIGN),
        "source_sha256": sha(HERE / "run_control.py"),
        "freezer_source_sha256": sha(Path(__file__)),
        "frozen_inputs_sha256": {
            label: sha(path) for label, path in INPUT_PATHS.items()},
        "challenge_dispatch_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert PROTOCOL.read_text() == encoded
        print("Q1493 rotated-CNF control protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to overwrite protocol"
        PROTOCOL.write_text(encoded)
        print("Q1493 rotated-CNF control protocol frozen")


if __name__ == "__main__":
    main()
