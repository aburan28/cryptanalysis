#!/usr/bin/env python3
"""Freeze every input and implementation component before SAT timing."""

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
ROOT = HERE.parents[2]
CMS = Path("/opt/homebrew/bin/cryptominisat5")

FILES = {
    "freezer": HERE / "freeze.py",
    "builder": HERE / "build_forward.py",
    "chart_auditor": HERE / "chart_audit.py",
    "chart": HERE / "forward_chart.json",
    "chart_builder": HERE / "chart_formula.py",
    "chart_build": HERE / "chart_build.json",
    "chart_formula": HERE / "chart.xcnf",
    "control_build": HERE / "control_build.json",
    "control_formula": HERE / "control.xcnf",
    "public_build": HERE / "public_build.json",
    "public_formula": HERE / "public.xcnf",
    "runner": HERE / "run_forward.py",
    "auditor": HERE / "audit_forward.py",
    "model_checker": GOAL / "n41_n131_zero_sum_joint_20261009/run.py",
    "joint_block_builder": GOAL / "n41_n131_zero_sum_joint_20261009/build_n41.py",
    "joint_s5_builder": GOAL / "n41_n131_zero_sum_joint_20261009/build_s5.py",
    "functional_pair_root": GOAL / "functional_pair_root_circuit.py",
    "functional_inverse": GOAL / "functional_inverse_circuit.py",
    "lowpower_pair_root": GOAL / "n41_lowpower_w8_s6_circuit.py",
    "karatsuba": ROOT / "experiments/koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py",
    "circuit": ROOT / "experiments/koblitz-s5-invariant-20260924/circuit_sat.py",
    "runtime": HERE / "sage_runtime_info.json",
    "source_input": GOAL / "n41_n131_zero_sum_triple_20261009/input_public.txt",
    "source_public_result": GOAL / "n41_n131_zero_sum_triple_20261009/public/result.json",
    "solver_binary": CMS,
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "protocol.json"
    if output.exists():
        raise FileExistsError(output)
    chart = json.loads((HERE / "forward_chart.json").read_text())
    assert chart["status"] == "PASS_FORWARD_ROOT_CHART"
    for mode in ("chart", "control", "public"):
        formula = HERE / f"{mode}.xcnf"
        build = json.loads((HERE / f"{mode}_build.json").read_text())
        assert build["sha256"]["formula"] == sha(formula)
    assert CMS.exists()
    receipt = {
        "status": "FROZEN_FORWARD",
        "proposal_id": chart["proposal_id"], "candidate_id": None,
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "target_count": 1, "target": chart["target"],
        "method": "four functional two-root W7 zero-sum triple blocks and exact target-ended S5",
        "control_policy": "chart pins source masks, pair and block outputs, root bits and target fiber; control pins only source masks; public pins nothing",
        "limits": {"chart_seconds": 30, "control_seconds": 60,
                   "public_seconds": 120, "workers": 1,
                   "combined_rss_bytes": 4_294_967_296},
        "files": {name: os.path.relpath(path, HERE) for name, path in FILES.items()},
        "sha256": {name: sha(path) for name, path in FILES.items()},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "files": len(FILES),
                      "sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
