#!/usr/bin/env python3
"""Freeze the archived free-midpoint cells used by Q1463."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
CASES = ("n53_known_sat_unpinned", "n53_ordinary", "n83_ordinary")
OUTPUT = HERE / "protocol.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_protocol():
    cells = []
    for name in CASES:
        receipt = PARENT / "q1456_joint_domain_profile/runs" / name / "receipt.json"
        row = json.loads(receipt.read_text())
        assert row["proposal_id"] == "Q1456" and row["candidate_id"] is None
        assert row["isogeny"] == "none" and row["solver_report"] is not None
        cells.append({
            "name": name,
            "receipt_sha256": sha(receipt),
            "curve_id": row["curve_id"],
            "workload_id": row["workload_id"],
            "degree_n": row["degree_n"],
            "factor_base_actual_B": row["factor_base_actual_B"],
            "folded_columns_K": row["folded_columns_K"],
            "factor_base_enumerated_set_sha256": row[
                "factor_base_enumerated_set_sha256"],
            "archived_partial_state_count": len(row["solver_report"][
                "domain_snapshots"]),
        })
    return {
        "proposal_id": "Q1463",
        "kind": "posthoc_free_midpoint_rank_screen",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "pair_candidate_cap_for_exact_midpoint_rank": 4096,
        "cells": cells,
        "field_bridge_sha256": {
            str(n): sha(PARENT / f"q1420_root_theory/n{n}_field.txt")
            for n in (53, 83)
        },
        "q1460_result_sha256": sha(PARENT /
                                   "q1460_fixed_state_support/result.json"),
        "q1460_midpoint_source_sha256": sha(PARENT /
            "q1460_fixed_state_support/midpoint_profile.cpp"),
        "source_sha256": {name: sha(HERE / name) for name in (
            "freeze_protocol.py", "build.py", "run_screen.py",
            "exact_midpoint_rank.cpp", "verify_sage.py")},
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "claim_scope": "archived fixed-state linear-span screen only",
        "challenge_run_admitted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = make_protocol()
    if args.check:
        assert json.loads(OUTPUT.read_text()) == expected
        print("Q1463 protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
