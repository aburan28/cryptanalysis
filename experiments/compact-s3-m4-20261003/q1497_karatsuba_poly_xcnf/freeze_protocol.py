#!/usr/bin/env python3
"""Freeze Q1497's exact arithmetic circuit, inputs, and solver limits."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from run import DESIGN, HERE, INPUTS, sha, solver_options

PROTOCOL = HERE / "protocol.json"


def snapshot() -> dict:
    design = json.loads(DESIGN.read_text())
    assert design["proposal_id"] == "Q1497"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert json.loads(INPUTS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    validation = json.loads(INPUTS["circuit_validation"].read_text())
    assert validation["proposal_id"] == "Q1497"
    assert validation["candidate_id"] is validation["run_id"] is None
    assert len(validation["cases"]) == 2
    for row in validation["cases"]:
        n = row["degree_n"]
        assert row["status"] == "PASS"
        assert row["bridge_sha256"] == sha(INPUTS[f"n{n}_bridge"])
        assert row["circuit_source_sha256"] == sha(
            HERE / "karatsuba_circuit.py")
        assert row["validation_source_sha256"] == sha(
            HERE / "validate_circuit.py")
        assert row["cms_binary_sha256"] == sha(INPUTS["cms_binary"])
    version = subprocess.run([str(INPUTS["cms_binary"]), "--version"],
                             capture_output=True, text=True, check=True)
    assert "CryptoMiniSat version 5.14.7" in version.stdout
    return {
        "kind": "q1497_karatsuba_polynomial_basis_s3_protocol",
        "proposal_id": "Q1497", "candidate_id": None, "run_id": None,
        "isogeny": "none", "challenge_dispatch_allowed": False,
        "complete_n131_log2_work": None,
        "design_sha256": sha(DESIGN),
        "freezer_source_sha256": sha(Path(__file__)),
        "runner_source_sha256": sha(HERE / "run.py"),
        "circuit_source_sha256": sha(HERE / "karatsuba_circuit.py"),
        "validator_source_sha256": sha(HERE / "validate_circuit.py"),
        "input_sha256": {label: sha(path) for label, path in
                         sorted(INPUTS.items())},
        "cms_version_first_line": version.stdout.splitlines()[1],
        "cms_command_options_ordinary": solver_options(design, 60),
        "cms_command_options_control": solver_options(design, 20),
        "degree_profiles": design["degree_profiles"],
        "run_order": design["run_order"],
        "runs": design["runs"],
        "solver_matrix_settings": design["solver_matrix_settings"],
        "claim_boundary": design["claim_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = snapshot()
    if args.check:
        assert json.loads(PROTOCOL.read_text()) == expected
        print("Q1497 Karatsuba S3 protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to replace protocol"
        PROTOCOL.write_text(json.dumps(expected, indent=2,
                                       sort_keys=True) + "\n")
        print("Q1497 Karatsuba S3 protocol written")


if __name__ == "__main__":
    main()
