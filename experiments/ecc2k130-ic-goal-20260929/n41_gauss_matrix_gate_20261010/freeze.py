#!/usr/bin/env python3
"""Freeze the native-XOR Gaussian N41 gate before any solver work."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n41_upper_xor_projection_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
BASE_FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
              "--random=20261010"]
GAUSS_FLAGS = [*BASE_FLAGS, "--maxmatrixrows=2000",
               "--maxmatrixcols=5000", "--autodisablegauss=0",
               "--gaussusefulcutoff=0"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = {
        "freeze": Path(__file__),
        "runner": HERE / "run.py",
        "solver": SOLVER,
        "all_fixed_formula": SOURCE / "all_fixed/projected.xcnf",
        "public_formula": SOURCE / "public/projected.xcnf",
        "all_fixed_projection": SOURCE / "all_fixed/result.json",
        "public_projection": SOURCE / "public/result.json",
        "source_control_audit": SOURCE / "control_audit.json",
        "source_protocol": SOURCE / "protocol.json",
        "sage_runtime": HERE / "sage_runtime_info.json",
    }
    assert json.loads(sources["sage_runtime"].read_text())["status"] == "verified"
    assert json.loads(sources["source_control_audit"].read_text())[
        "status"] == "PASS_EXACT_XCNF_PROJECTION_AND_LIFT"
    protocol = {
        "status": "FROZEN_BEFORE_N41_GAUSSIAN_MATRIX_GATE",
        "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "public_target_q": [1458168294740, 1672312028033],
        "target_count": 1,
        "workers": 1,
        "rss_cap_bytes": 4 * 1024**3,
        "run_order": ["baseline_all_fixed", "gauss_all_fixed",
                      "gauss_public_if_positive_control_passes"],
        "caps_seconds": {"baseline_all_fixed": 20, "gauss_all_fixed": 20,
                         "gauss_public": 120},
        "flags": {"baseline_all_fixed": BASE_FLAGS,
                  "gauss_all_fixed": GAUSS_FLAGS,
                  "gauss_public": GAUSS_FLAGS},
        "input_law": (
            "same archived N41 public point, same projected known-satisfiable "
            "output-fixed formula for paired controls; unpinned public formula "
            "only after audited tuned positive control"
        ),
        "source_sha256": {name: sha(path) for name, path in sources.items()},
    }
    with (HERE / "protocol.json").open("x") as out:
        json.dump(protocol, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": protocol["status"]}))


if __name__ == "__main__":
    main()
