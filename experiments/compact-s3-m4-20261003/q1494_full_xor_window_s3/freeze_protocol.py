#!/usr/bin/env python3
"""Freeze source, exact inputs and native XOR solver before Q1494 runs."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from run import DESIGN, HERE, INPUTS, sha

PROTOCOL = HERE / "protocol.json"


def snapshot() -> dict:
    design = json.loads(DESIGN.read_text())
    assert design["proposal_id"] == "Q1494"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    runtime = json.loads(INPUTS["sage_runtime_info"].read_text())
    assert runtime["status"] == "verified"
    version = subprocess.run([str(INPUTS["cms_binary"]), "--version"],
                             capture_output=True, text=True, check=True)
    assert "CryptoMiniSat version 5.14.7" in version.stdout
    return {
        "kind": "q1494_full_native_xor_three_s3_protocol",
        "proposal_id": "Q1494", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "challenge_dispatch_allowed": False,
        "complete_n131_log2_work": None,
        "design_sha256": sha(DESIGN),
        "freezer_source_sha256": sha(Path(__file__)),
        "runner_source_sha256": sha(HERE / "run.py"),
        "input_sha256": {label: sha(path) for label, path in
                         sorted(INPUTS.items())},
        "cms_version_first_line": version.stdout.splitlines()[1],
        "cms_command_options": ["--verb", "1", "--threads", "1",
                                "--maxtime", "<frozen cap>",
                                "--maxconfl", str(design["conflict_cap"])],
        "degree_profiles": design["degree_profiles"],
        "run_order": design["run_order"],
        "runs": design["runs"],
        "control_wall_cap_seconds": design[
            "control_wall_cap_seconds"],
        "claim_boundary": design["claim_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = snapshot()
    if args.check:
        assert json.loads(PROTOCOL.read_text()) == expected
        print("Q1494 full native-XOR protocol PASS (frozen)")
    else:
        assert not PROTOCOL.exists(), "refusing to replace protocol"
        PROTOCOL.write_text(json.dumps(expected, indent=2,
                                       sort_keys=True) + "\n")
        print("Q1494 full native-XOR protocol written")


if __name__ == "__main__":
    main()
