#!/usr/bin/env python3
"""Freeze Q1495's audited base dependencies and exact screen sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from screen import DESIGN, HERE, INPUTS, PROTOCOL, sha


def snapshot() -> dict:
    design = json.loads(DESIGN.read_text())
    assert design["proposal_id"] == "Q1495"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    runtime = json.loads(INPUTS["sage_runtime_info"].read_text())
    assert runtime["status"] == "verified"
    audit = json.loads(INPUTS["q1484_archive_audit"].read_text())
    assert audit["status"] == "PASS"
    return {
        "kind": "q1495_fixed_window_tuple_support_protocol",
        "proposal_id": "Q1495", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "challenge_dispatch_allowed": False,
        "complete_n131_log2_work": None,
        "design_sha256": sha(DESIGN),
        "freezer_source_sha256": sha(Path(__file__)),
        "screen_source_sha256": sha(HERE / "screen.py"),
        "n53_control_source_sha256": sha(HERE / "validate_n53.py"),
        "input_sha256": {label: sha(path) for label, path in
                         sorted(INPUTS.items())},
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
        assert json.loads(PROTOCOL.read_text()) == expected
        print("Q1495 fixed-window support protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to replace protocol"
        PROTOCOL.write_text(json.dumps(expected, indent=2,
                                       sort_keys=True) + "\n")
        print("Q1495 fixed-window support protocol written")


if __name__ == "__main__":
    main()
