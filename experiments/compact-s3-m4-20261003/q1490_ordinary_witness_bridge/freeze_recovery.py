#!/usr/bin/env python3
"""Freeze Q1490 R2 bridge source and recovery inputs before execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bridge_v2 import (DESIGN, HERE, INPUT_PATHS, PARENT_PROTOCOL,
                       PROTOCOL, R1_FAILURE, RECOVERY_DESIGN, RUNTIME, sha)


def build() -> dict:
    design = json.loads(DESIGN.read_text())
    recovery = json.loads(RECOVERY_DESIGN.read_text())
    failure = json.loads(R1_FAILURE.read_text())
    runtime = json.loads(RUNTIME.read_text())
    assert design["proposal_id"] == "Q1490"
    assert recovery["attempt_id"] == "Q1490R2"
    assert failure["attempt_id"] == "Q1490R1"
    assert failure["status"] == "source_validation_error"
    assert recovery["r1_failure_sha256"] == sha(R1_FAILURE)
    assert recovery["frozen_parent_protocol_sha256"] == sha(PARENT_PROTOCOL)
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert runtime["status"] == "verified"
    for label, path in INPUT_PATHS.items():
        assert sha(path) == design["frozen_inputs_sha256"][label], label
    return {
        "kind": "q1490_r2_frozen_ordinary_witness_bridge_protocol",
        "proposal_id": "Q1490",
        "attempt_id": "Q1490R2",
        "candidate_id": None, "run_id": None,
        "isogeny": "none",
        "curve_id": design["curve_id"],
        "field_degree_n": design["field_degree_n"],
        "factor_base_actual_B": design["factor_base_actual_B"],
        "factor_base_folded_columns_K": design[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "input_law": design["measurement_scope"],
        "success_gate": design["success_gate"],
        "design_sha256": sha(DESIGN),
        "recovery_design_sha256": sha(RECOVERY_DESIGN),
        "r1_failure_sha256": sha(R1_FAILURE),
        "parent_protocol_sha256": sha(PARENT_PROTOCOL),
        "source_sha256": sha(HERE / "bridge_v2.py"),
        "freezer_source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(RUNTIME),
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
        print("Q1490 R2 bridge protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to overwrite protocol"
        PROTOCOL.write_text(encoded)
        print("Q1490 R2 bridge protocol frozen")


if __name__ == "__main__":
    main()
