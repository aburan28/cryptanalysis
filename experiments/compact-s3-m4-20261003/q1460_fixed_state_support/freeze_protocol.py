#!/usr/bin/env python3
"""Freeze the Q1460 fixed-partial-state target-support screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1456 = PARENT / "q1456_joint_domain_profile"
Q1459 = PARENT / "q1459_leaf_lift_screen"
OUTPUT = HERE / "protocol.json"
RUN_ORDER = ("n53_known_sat_unpinned", "n53_ordinary", "n83_ordinary")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_protocol() -> dict:
    prior = json.loads((Q1459 / "protocol.json").read_text())
    prior_result = json.loads((Q1459 / "result.json").read_text())
    prior_verification = json.loads((Q1459 / "verification.json").read_text())
    build = json.loads((HERE / "compile_receipt.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert prior["proposal_id"] == prior_result["proposal_id"] == "Q1459"
    assert prior_verification["status"] == "pass"
    assert prior_result["protocol_sha256"] == sha(Q1459 / "protocol.json")
    assert prior["run_order"] == list(RUN_ORDER)
    assert build["proposal_id"] == "Q1460"
    assert runtime["status"] == "verified"
    sources = [HERE / name for name in (
        "build.py", "midpoint_profile.cpp", "freeze_protocol.py",
        "screen.py", "verify_archive.py")]
    sources += [PARENT / name for name in (
        "q1420_root_theory/root_field.hpp",
        "q1422_leaf_lift_gate/lift_gate.hpp",
        "q1458_batch_roots/batch_roots.hpp",
        "q1455_joint_tail/joint_tail.py",
        "s3_root_oracle.py", "chain_s3.py")]
    inputs = [HERE / name for name in (
        "compile_receipt.json", "sage_runtime_info.json")]
    inputs += [Q1459 / name for name in (
        "protocol.json", "result.json", "verification.json")]
    inputs += [Q1456 / "runs" / name / "receipt.json"
               for name in RUN_ORDER]
    inputs += [PARENT / "q1420_root_theory" / f"n{n}_field.txt"
               for n in (53, 83)]
    return {
        "kind": "q1460_fixed_state_target_x_support_protocol",
        "proposal_id": "Q1460", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "for each Q1459 archived partial state admitted by the raw or "
            "exact curve-lift-filtered 4096-pair cap, enumerate each "
            "pair's exact S3 midpoint x set with Q1458 batched roots; "
            "bound that fixed state's possible raw target x support by "
            "2 times the product of distinct midpoint-set sizes"),
        "scope": "fixed partial leaf states, not an adaptive search bound",
        "pair_candidate_cap": 4096,
        "generic_fixed_state_target_x_bound": 8 * 4096 * 4096,
        "run_order": list(RUN_ORDER),
        "cells": prior["cells"],
        "parent_q1459_protocol_sha256": sha(Q1459 / "protocol.json"),
        "parent_q1459_result_sha256": sha(Q1459 / "result.json"),
        "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sources},
        "input_sha256": {str(p.relative_to(ROOT)): sha(p) for p in inputs},
        "cpu_isolation_receipt": None,
        "successful_decomposition_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol = make_protocol()
    if args.check:
        assert protocol == json.loads(OUTPUT.read_text())
        print("Q1460 frozen support protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
        print("Q1460 support protocol frozen")


if __name__ == "__main__":
    main()
