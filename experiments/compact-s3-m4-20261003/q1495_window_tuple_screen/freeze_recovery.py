#!/usr/bin/env python3
"""Freeze Q1495 R2 after preserving the first control's encoding error."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import screen

HERE = Path(__file__).resolve().parent
RECOVERY = HERE / "recovery_protocol.json"


def snapshot() -> dict:
    design = json.loads(screen.DESIGN.read_text())
    recovery_design_path = HERE / "design_recovery.json"
    recovery_design = json.loads(recovery_design_path.read_text())
    r1_path = HERE / "runs/r1/failure.json"
    r1 = json.loads(r1_path.read_text())
    assert design["proposal_id"] == recovery_design[
        "proposal_id"] == r1["proposal_id"] == "Q1495"
    assert r1["status"] == "producer_failure"
    assert recovery_design["r1_failure_sha256"] == screen.sha(r1_path)
    original_protocol = json.loads((HERE / "protocol.json").read_text())
    assert original_protocol["screen_source_sha256"] == screen.sha(
        HERE / "screen.py")
    assert original_protocol["n53_control_source_sha256"] == screen.sha(
        HERE / "validate_n53.py")
    assert original_protocol["input_sha256"] == {
        label: screen.sha(path) for label, path in
        sorted(screen.INPUTS.items())}
    return {
        "kind": "q1495_fixed_window_tuple_support_recovery_protocol",
        "proposal_id": "Q1495", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "attempt_id": "Q1495R2",
        "challenge_dispatch_allowed": False,
        "complete_n131_log2_work": None,
        "design_sha256": screen.sha(screen.DESIGN),
        "recovery_design_sha256": screen.sha(recovery_design_path),
        "r1_failure_sha256": screen.sha(r1_path),
        "original_protocol_sha256": screen.sha(HERE / "protocol.json"),
        "original_control_source_sha256": screen.sha(
            HERE / "validate_n53.py"),
        "freezer_source_sha256": screen.sha(Path(__file__)),
        "screen_source_sha256": screen.sha(HERE / "screen.py"),
        "screen_r2_source_sha256": screen.sha(HERE / "screen_r2.py"),
        "n53_control_source_sha256": screen.sha(
            HERE / "validate_n53_r2.py"),
        "input_sha256": {label: screen.sha(path) for label, path in
                         sorted(screen.INPUTS.items())},
        "curve_id": design["curve_id"],
        "field_degree_n": design["field_degree_n"],
        "nominal_window_dimension_d": design[
            "nominal_window_dimension_d"],
        "factor_base_actual_B": design["factor_base_actual_B"],
        "factor_base_folded_columns_K": design[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "support_levels_decimal": design["support_levels_decimal"],
        "claim_boundary": design["claim_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = snapshot()
    if args.check:
        assert json.loads(RECOVERY.read_text()) == expected
        print("Q1495 R2 support protocol PASS (frozen)")
    else:
        assert not RECOVERY.exists(), "refusing to replace R2 protocol"
        RECOVERY.write_text(json.dumps(expected, indent=2,
                                       sort_keys=True) + "\n")
        print("Q1495 R2 support protocol written")


if __name__ == "__main__":
    main()
