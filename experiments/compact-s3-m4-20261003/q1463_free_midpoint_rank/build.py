#!/usr/bin/env python3
"""Build the Q1463 exact midpoint-rank screen without the SAT solver."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "exact_midpoint_rank.cpp"
BINARY = HERE / "exact_midpoint_rank"
RECEIPT = HERE / "compile_receipt.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    command = ["c++", "-std=c++17", "-O2", "-o", str(BINARY), str(SOURCE)]
    subprocess.run(command, check=True)
    receipt = {
        "command": ["c++", "-std=c++17", "-O2", "-o",
                    "exact_midpoint_rank", "exact_midpoint_rank.cpp"],
        "compiler": subprocess.check_output(["c++", "--version"],
                                            text=True).splitlines()[0],
        "source_sha256": sha(SOURCE),
        "parent_midpoint_source_sha256": sha(HERE.parent /
            "q1460_fixed_state_support/midpoint_profile.cpp"),
        "binary_sha256": sha(BINARY),
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
