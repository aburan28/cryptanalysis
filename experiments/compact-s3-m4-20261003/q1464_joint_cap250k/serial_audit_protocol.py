#!/usr/bin/env python3
"""Freeze first ordinary wide-rejection states for post-result serial replay."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
OUTPUT = HERE / "serial_audit_protocol.json"
CASES = ("n53_ordinary", "n83_ordinary")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_protocol():
    selections = []
    for name in CASES:
        receipt_path = HERE / "runs" / name / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["proposal_id"] == "Q1464"
        snapshot = receipt["solver_report"]["joint_rejection_snapshots"][0]
        assert max(snapshot["pair_candidate_counts"]) > 4096
        assert max(snapshot["pair_candidate_counts"]) <= 250000
        target_path = PARENT / "q1455_joint_tail/runs" / name / "targets.txt"
        target = target_path.read_text().splitlines()[
            1 + snapshot["target_preimage_index"]]
        selections.append({
            "case": name, "degree_n": receipt["degree_n"],
            "curve_id": receipt["curve_id"],
            "workload_id": receipt["workload_id"],
            "factor_base_actual_B": receipt["factor_base_actual_B"],
            "folded_columns_K": receipt["folded_columns_K"],
            "factor_base_enumerated_set_sha256": receipt[
                "factor_base_enumerated_set_sha256"],
            "normal_basis_weight_bound": receipt[
                "normal_basis_weight_bound"],
            "receipt_sha256": sha(receipt_path),
            "targets_sha256": sha(target_path),
            "selected_snapshot": snapshot,
            "selected_target_x_onb_hex": target,
        })
    return {
        "proposal_id": "Q1464", "kind": "post_result_serial_root_audit",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "selection_rule": "first retained ordinary wide no-chain snapshot at each degree",
        "pair_candidate_cap": 250000,
        "selections": selections,
        "audit_binary_sha256": sha(HERE / "serial_audit"),
        "source_sha256": {
            "serial_audit.cpp": sha(HERE / "serial_audit.cpp"),
            "serial_audit_protocol.py": sha(Path(__file__)),
            "serial_audit_run.py": sha(HERE / "serial_audit_run.py"),
            "root_field.hpp": sha(PARENT /
                                  "q1420_root_theory/root_field.hpp"),
        },
        "field_bridge_sha256": {
            str(n): sha(PARENT / f"q1420_root_theory/n{n}_field.txt")
            for n in (53, 83)
        },
        "checked_sage_runtime_info_sha256": sha(HERE /
                                                "sage_runtime_info.json"),
        "compiler": subprocess.check_output(["c++", "--version"],
                                             text=True).splitlines()[0],
        "command": "c++ -std=c++17 -O2 serial_audit.cpp -o serial_audit",
        "post_result_follow_up": True,
        "claim_scope": "exact x-only feasibility of two selected fixed states",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = make_protocol()
    if args.check:
        assert expected == json.loads(OUTPUT.read_text())
        print("Q1464 serial audit protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
