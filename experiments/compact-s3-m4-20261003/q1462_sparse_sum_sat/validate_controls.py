#!/usr/bin/env python3
"""Replay planted N53/N83 relations through Q1462's SAT propagator."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1420 = PARENT / "q1420_root_theory"
Q1438 = PARENT / "q1438_dense_base"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(Q1420))

from q1420_root_theory.verify_archive import model_from_file  # noqa: E402
from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)
from q1438_dense_base.build_formula import build_cnf  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402

OUTPUT = HERE / "control_result.json"
POLICY = "sparse_sum_joint_pair_span"
SUM_CAP = 100000


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def common_free_bits(n: int, leaves: list[list[int]], model: list[int]) -> set[int]:
    positive = [{index for index, bit in enumerate(leaf) if model[bit]}
                for leaf in leaves]
    choices = itertools.product(*(sorted(bits) for bits in positive))
    selected = next((set(choice) for choice in choices
                     if all(1 <= len(set(choice) & bits) <= 2
                            for bits in positive)), None)
    assert selected is not None
    zeros = [index for index in range(n)
             if all(index not in bits for bits in positive)]
    assert len(zeros) >= 20 - len(selected)
    free = selected | set(zeros[:20 - len(selected)])
    assert len(free) == 20
    assert all(1 <= len(free & bits) <= 2 for bits in positive)
    return free


def validate_one(n: int) -> dict:
    archived_ordinary = PARENT / f"q1446_joint_pair_span/runs/n{n}_ordinary"
    guard_completed = subprocess.run(
        [str(HERE / "control_guard"),
         str(Q1420 / f"n{n}_field.txt"),
         str(archived_ordinary / "variables.txt"),
         str(archived_ordinary / "targets.txt"),
         str(PARENT / f"q1461_sparse_sum_inverse/n{n}_inputs.txt"),
         str(SUM_CAP)], check=True, capture_output=True, text=True)
    guard_control = json.loads(guard_completed.stdout)
    assert guard_control["degree_n"] == n
    assert guard_control["positive_exact_pairs"] >= 1
    assert guard_control["negative_guard_literals"] > n
    parent = json.loads((Q1438 / "solver_protocol.json").read_text())
    workload = parent["workloads"][f"n{n}_free_partner"]
    raw, varmap, formula, meta, variables, clauses = build_cnf(
        n, "free_partner")
    assert hashlib.sha256(raw).hexdigest() == workload["cnf_raw_sha256"]
    assert hashlib.sha256(varmap).hexdigest() == workload["variable_map_sha256"]
    archived = Q1438 / f"runs/n{n}_free_partner/solver.model.txt"
    model = model_from_file(archived)
    assert len(model) == variables
    free_positions = common_free_bits(n, meta["leaf_variables"], model)
    units = []
    for leaf in meta["leaf_variables"]:
        for index, bit in enumerate(leaf):
            if index not in free_positions:
                units.append(bit if model[bit] else -bit)
    for row in (*meta["pair_mid_variables"],
                meta["target_selector_variables"]):
        units.extend(bit if model[bit] else -bit for bit in row)
    head, tail = raw.split(b"\n", 1)
    assert head == f"p cnf {variables} {clauses}".encode()
    augmented = (f"p cnf {variables} {clauses + len(units)}\n".encode() +
                 tail + b"".join(f"{lit} 0\n".encode() for lit in units))
    q1436 = json.loads((PARENT /
        "q1436_affine_pair/protocol.json").read_text())[
            "workloads"][f"n{n}_free_partner"]
    q1420 = json.loads((Q1420 / "protocol.json").read_text())[
        "workloads"][q1436["parent_q1420_key"]]
    targets = encode_targets(n, target_list(n, "free_mids", q1420))
    assert hashlib.sha256(targets).hexdigest() == workload[
        "target_input_sha256"]
    with tempfile.TemporaryDirectory(prefix=f"q1462_n{n}_control_") as tmp:
        directory = Path(tmp)
        cnf = directory / "system.cnf"
        varmap_path = directory / "variables.txt"
        target_path = directory / "targets.txt"
        model_path = directory / "solver.model.txt"
        cnf.write_bytes(augmented)
        varmap_path.write_bytes(varmap)
        target_path.write_bytes(targets)
        command = [str(HERE / "native_solver"),
                   str(Q1420 / f"n{n}_field.txt"), str(cnf),
                   str(varmap_path), str(model_path), "1000000", "30",
                   POLICY, str(target_path), str(SUM_CAP)]
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=45)
        assert completed.returncode == 0, (completed.returncode,
                                           completed.stderr,
                                           completed.stdout[-1000:])
        report = json.loads(completed.stdout)
        assert report["status"] == 10 and report["sum_cap"] == SUM_CAP
        assert report["decision_policy"] == POLICY
        assert report["sum_checks"] == (report["sum_checks_pair0"] +
                                         report["sum_checks_pair1"])
        relation = model_relation(raw, formula, meta, variables, clauses,
                                  model_path, parent["instances"][str(n)])
    assert relation["status"] == "verified_four_point_relation"
    assert relation["distinct_columns"] == 4
    return {
        "degree_n": n, "control_law": "archived planted free-partner witness",
        "curve_id": workload["curve_id"],
        "factor_base_actual_B": workload["factor_base_actual_B"],
        "folded_columns_K": workload["folded_columns_K"],
        "factor_base_enumerated_set_sha256": workload[
            "factor_base_enumerated_set_sha256"],
        "cnf_raw_sha256": workload["cnf_raw_sha256"],
        "augmented_cnf_sha256": hashlib.sha256(augmented).hexdigest(),
        "variable_map_sha256": workload["variable_map_sha256"],
        "target_input_sha256": workload["target_input_sha256"],
        "archived_witness_model_sha256": sha(archived),
        "free_leaf_bits_each": 20,
        "direct_guard_control": guard_control,
        "sum_checks": report["sum_checks"],
        "sum_rejections": report["sum_rejections"],
        "sum_x_only_hits": report["sum_x_only_hits"],
        "sum_checked_sums": report["sum_checked_sums"],
        "sum_check_mul_calls": report["sum_check_mul_calls"],
        "sum_check_sqr_calls": report["sum_check_sqr_calls"],
        "sum_check_inv_calls": report["sum_check_inv_calls"],
        "point_relation": relation,
    }


def make_result() -> dict:
    return {
        "kind": "q1462_sparse_sum_sat_prerun_controls",
        "proposal_id": "Q1462", "candidate_id": None, "run_id": None,
        "isogeny": "none", "status": "pass",
        "sum_candidate_cap": SUM_CAP,
        "rows": [validate_one(n) for n in (53, 83)],
        "solver_source_sha256": sha(HERE / "native_solver.cpp"),
        "solver_binary_sha256": sha(HERE / "native_solver"),
        "validator_source_sha256": sha(Path(__file__)),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_result()
    if args.check:
        assert json.loads(OUTPUT.read_text()) == result
        print("Q1462 N53/N83 positive SAT controls: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": "pass", "sum_checks": {
            row["degree_n"]: row["sum_checks"] for row in result["rows"]}}))


if __name__ == "__main__":
    main()
