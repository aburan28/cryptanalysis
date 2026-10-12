#!/usr/bin/env python3
"""Freeze Q1490 bridge inputs and source before the correctness run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bridge import DESIGN, HERE, INPUT_PATHS, PROTOCOL, RUNTIME, sha


def build() -> dict:
    design = json.loads(DESIGN.read_text())
    runtime = json.loads(RUNTIME.read_text())
    assert design["proposal_id"] == "Q1490"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert runtime["status"] == "verified"
    for label, path in INPUT_PATHS.items():
        assert sha(path) == design["frozen_inputs_sha256"][label], label
    return {
        "kind": "q1490_frozen_ordinary_witness_bridge_protocol",
        "proposal_id": "Q1490",
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
        "source_sha256": sha(HERE / "bridge.py"),
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
        print("Q1490 bridge protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to overwrite protocol"
        PROTOCOL.write_text(encoded)
        print("Q1490 bridge protocol frozen")


if __name__ == "__main__":
    main()
