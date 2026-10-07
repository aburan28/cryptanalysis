#!/usr/bin/env python3
"""Freeze Q1498's matched Q1497 formulas and Gaussian row limit."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from run import DESIGN, HERE, INPUTS, sha

PROTOCOL = HERE / "protocol.json"


def snapshot() -> dict:
    design = json.loads(DESIGN.read_text())
    assert design["proposal_id"] == "Q1498"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert json.loads(INPUTS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    parent = json.loads(INPUTS["q1497_design"].read_text())
    assert design["degree_profiles"] == parent["degree_profiles"]
    assert design["run_order"] == parent["run_order"]
    assert design["runs"] == parent["runs"]
    rows = dict(design["solver_matrix_settings"])
    old = dict(parent["solver_matrix_settings"])
    assert rows.pop("max_matrix_rows") == 16384
    assert old.pop("max_matrix_rows") == 512
    assert rows == old
    version = subprocess.run([str(INPUTS["cms_binary"]), "--version"],
                             capture_output=True, text=True, check=True)
    assert "CryptoMiniSat version 5.14.7" in version.stdout
    return {
        "kind": "q1498_matched_karatsuba_gauss_row_protocol",
        "proposal_id": "Q1498", "candidate_id": None, "run_id": None,
        "isogeny": "none", "challenge_dispatch_allowed": False,
        "complete_n131_log2_work": None,
        "design_sha256": sha(DESIGN),
        "runner_source_sha256": sha(HERE / "run.py"),
        "freezer_source_sha256": sha(Path(__file__)),
        "input_sha256": {label: sha(path) for label, path in
                         sorted(INPUTS.items())},
        "cms_version_first_line": version.stdout.splitlines()[1],
        "cms_command_options_ordinary": [
            "--verb", "1", "--threads", "1", "--maxtime", "60",
            "--maxconfl", str(design["conflict_cap"]),
            "--maxmatrixcols", "24576", "--maxmatrixrows", "16384",
            "--maxnummatrices", "8", "--autodisablegauss", "0"],
        "cms_command_options_control": [
            "--verb", "1", "--threads", "1", "--maxtime", "20",
            "--maxconfl", str(design["conflict_cap"]),
            "--maxmatrixcols", "24576", "--maxmatrixrows", "16384",
            "--maxnummatrices", "8", "--autodisablegauss", "0"],
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
        print("Q1498 Gaussian row-limit protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to replace protocol"
        PROTOCOL.write_text(json.dumps(expected, indent=2,
                                       sort_keys=True) + "\n")
        print("Q1498 Gaussian row-limit protocol written")


if __name__ == "__main__":
    main()
