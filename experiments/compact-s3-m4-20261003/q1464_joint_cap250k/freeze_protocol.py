#!/usr/bin/env python3
"""Freeze Q1464's larger exact joint-pair cap on Q1458 inputs."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1455 = PARENT / "q1455_joint_tail"
Q1456 = PARENT / "q1456_joint_domain_profile"
Q1458 = PARENT / "q1458_batch_roots"
OUTPUT = HERE / "protocol.json"
RUN_ORDER = ("n53_known_sat_unpinned", "n53_ordinary", "n83_ordinary")
PAIR_CAP = 250000


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_protocol():
    base = json.loads((Q1458 / "protocol.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    build = json.loads((Q1458 / "compile_receipt.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert base["proposal_id"] == "Q1458"
    assert base["run_order"] == list(RUN_ORDER)
    assert control["proposal_id"] == "Q1464" and control["status"] == "pass"
    assert control["pair_candidate_cap"] == PAIR_CAP
    assert runtime["status"] == "verified"
    binary = Q1458 / "native_batch_solver"
    assert sha(binary) == base["binary_sha256"] == build[
        "solver_binary_sha256"] == control["binary_sha256"]
    cells = {}
    for name in RUN_ORDER:
        old = base["cells"][name]
        baseline_path = Q1458 / "runs" / name / "receipt.json"
        baseline = json.loads(baseline_path.read_text())
        archived_path = Q1456 / "runs" / name / "receipt.json"
        archived = json.loads(archived_path.read_text())
        assert baseline["workload_id"] == old["workload_id"]
        assert archived["workload_id"] == old["workload_id"]
        assert baseline["solver_status"] == "censored"
        assert baseline["pair_candidate_cap"] == old[
            "pair_candidate_cap"] == 4096
        cell = copy.deepcopy(old)
        cell.pop("baseline_q1457_receipt_sha256")
        cell["baseline_q1458_receipt_sha256"] = sha(baseline_path)
        cell["pair_candidate_cap"] = PAIR_CAP
        cell["archived_q1456_states_admitted_at_new_cap"] = sum(
            max(state["pair_candidate_counts"]) <= PAIR_CAP
            for state in archived["solver_report"]["domain_snapshots"])
        cells[name] = cell
    sources = [HERE / name for name in (
        "freeze_protocol.py", "run_controls.py", "run_stage.py",
        "verify_archive.py")]
    sources += [Q1458 / name for name in (
        "native_batch_solver.cpp", "batch_roots.hpp")]
    sources += [PARENT / name for name in (
        "q1446_joint_pair_span/theory_solver.cpp",
        "q1420_root_theory/root_field.hpp",
        "q1455_joint_tail/native_inputs.py",
        "q1455_joint_tail/joint_tail.py",
        "q1438_dense_base/verify_solver.py")]
    inputs = [HERE / "control_result.json", HERE / "sage_runtime_info.json",
              Q1458 / "protocol.json", Q1458 / "compile_receipt.json"]
    inputs += [PARENT / f"q1420_root_theory/n{n}_field.txt"
               for n in (53, 83)]
    for name in RUN_ORDER:
        inputs += [Q1455 / "runs" / name / leaf for leaf in (
            "receipt.json", "system.cnf.gz", "variables.txt",
            "targets.txt")]
        inputs += [Q1458 / "runs" / name / "receipt.json",
                   Q1456 / "runs" / name / "receipt.json"]
    return {
        "kind": "q1464_wide_exact_joint_pair_protocol",
        "proposal_id": "Q1464", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "method": (
            "Q1458's exact chained-S3 batched-root SAT propagator with "
            "a 250000-pair cap per partial leaf pair; same CNFs, "
            "target points, decision order and resource envelope"),
        "controlled_variable": "joint-rule pair_candidate_cap 4096 to 250000",
        "decision_policy": "joint_tail_leaf_interleave",
        "run_order": list(RUN_ORDER), "cells": cells,
        "binary_sha256": sha(binary),
        "q1458_protocol_sha256": sha(Q1458 / "protocol.json"),
        "control_result_sha256": sha(HERE / "control_result.json"),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "source_sha256": {str(path.relative_to(ROOT)): sha(path)
                          for path in sources},
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in inputs},
        "cpu_isolation_receipt": None,
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = make_protocol()
    if args.check:
        assert expected == json.loads(OUTPUT.read_text())
        print("Q1464 frozen wide-cap protocol: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(expected, sort_keys=True, indent=2) + "\n")
