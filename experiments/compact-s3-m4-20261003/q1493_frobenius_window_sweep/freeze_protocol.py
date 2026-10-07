#!/usr/bin/env python3
"""Freeze Q1493's Frobenius-swept first-window solver before runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run import DESIGN, HERE, INPUT_PATHS, PROTOCOL, sha


def build() -> dict:
    design = json.loads(DESIGN.read_text())
    assert design["proposal_id"] == "Q1493"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert [row["field_degree_n"] for row in design["profiles"]] == [53, 83]
    assert design["run_order"] == [
        "n53_known_rotation_44", "n53_sweep", "n83_sweep"]
    assert design["runs"]["n53_sweep"]["rotations"] == list(range(53))
    assert design["runs"]["n83_sweep"]["rotations"] == list(range(83))
    assert json.loads(INPUT_PATHS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    for label, path in INPUT_PATHS.items():
        assert sha(path) == design["frozen_inputs_sha256"][label], label
    return {
        "kind": "q1493_frozen_frobenius_first_window_sweep_protocol",
        "proposal_id": "Q1493", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "profiles": design["profiles"],
        "run_order": design["run_order"],
        "runs": design["runs"],
        "conflict_cap_per_rotation": design[
            "conflict_cap_per_rotation"],
        "pair_candidate_cap": design["pair_candidate_cap"],
        "decision_policy": design["decision_policy"],
        "coverage_argument": design["coverage_argument"],
        "stop_rule": design["stop_rule"],
        "success_gate": design["success_gate"],
        "design_sha256": sha(DESIGN),
        "source_sha256": sha(HERE / "run.py"),
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
        print("Q1493 protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to overwrite protocol"
        PROTOCOL.write_text(encoded)
        print("Q1493 protocol frozen")


if __name__ == "__main__":
    main()
