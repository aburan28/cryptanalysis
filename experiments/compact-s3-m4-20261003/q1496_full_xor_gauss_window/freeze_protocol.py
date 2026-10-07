#!/usr/bin/env python3
"""Freeze Q1496 source, matched Q1494 receipts, and solver settings."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from run import DESIGN, HERE, INPUTS, sha, solver_options

PROTOCOL = HERE / "protocol.json"


def snapshot() -> dict:
    design = json.loads(DESIGN.read_text())
    assert design["proposal_id"] == "Q1496"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert json.loads(INPUTS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    version = subprocess.run([str(INPUTS["cms_binary"]), "--version"],
                             capture_output=True, text=True, check=True)
    assert "CryptoMiniSat version 5.14.7" in version.stdout
    return {
        "kind": "q1496_bounded_gauss_protocol",
        "proposal_id": "Q1496", "candidate_id": None, "run_id": None,
        "isogeny": "none", "challenge_dispatch_allowed": False,
        "complete_n131_log2_work": None,
        "design_sha256": sha(DESIGN),
        "freezer_source_sha256": sha(Path(__file__)),
        "runner_source_sha256": sha(HERE / "run.py"),
        "input_sha256": {key: sha(value) for key, value in
                         sorted(INPUTS.items())},
        "cms_version_first_line": version.stdout.splitlines()[1],
        "cms_command_options_ordinary": solver_options(design, 60),
        "cms_command_options_control": solver_options(design, 20),
        "degree_profiles": design["degree_profiles"],
        "run_order": design["run_order"],
        "runs": design["runs"],
        "matrix_settings": design["matrix_settings"],
        "claim_boundary": design["claim_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = snapshot()
    if args.check:
        assert json.loads(PROTOCOL.read_text()) == expected
        print("Q1496 bounded-Gauss protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to replace protocol"
        PROTOCOL.write_text(json.dumps(expected, indent=2,
                                       sort_keys=True) + "\n")
        print("Q1496 bounded-Gauss protocol written")


if __name__ == "__main__":
    main()
