#!/usr/bin/env python3
"""Freeze Q1492's partial-pin source and four bounded cells."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_partial import DESIGN, HERE, INPUT_PATHS, PROTOCOL, sha


def build() -> dict:
    design = json.loads(DESIGN.read_text())
    assert design["proposal_id"] == "Q1492"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert [row["name"] for row in design["cells"]] == [
        "target_plus_both_mids", "target_plus_second_mid",
        "target_plus_first_mid", "target_only"]
    assert json.loads(INPUT_PATHS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    for label, path in INPUT_PATHS.items():
        assert sha(path) == design["frozen_inputs_sha256"][label], label
    return {
        "kind": "q1492_frozen_ordinary_partial_pin_protocol",
        "proposal_id": "Q1492", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "curve_id": design["curve_id"],
        "field_degree_n": design["field_degree_n"],
        "factor_base_actual_B": design["factor_base_actual_B"],
        "factor_base_folded_columns_K": design[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "parent_workload_id": design["parent_workload_id"],
        "target_preimage_index": design["target_preimage_index"],
        "cells": design["cells"],
        "input_law": design["input_law"],
        "native_wall_cap_seconds": design["native_wall_cap_seconds"],
        "external_safeguard_seconds": design[
            "external_safeguard_seconds"],
        "conflict_cap": design["conflict_cap"],
        "pair_candidate_cap": design["pair_candidate_cap"],
        "decision_policy": design["decision_policy"],
        "success_gate": design["success_gate"],
        "design_sha256": sha(DESIGN),
        "source_sha256": sha(HERE / "run_partial.py"),
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
        print("Q1492 protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to overwrite protocol"
        PROTOCOL.write_text(encoded)
        print("Q1492 protocol frozen")


if __name__ == "__main__":
    main()
