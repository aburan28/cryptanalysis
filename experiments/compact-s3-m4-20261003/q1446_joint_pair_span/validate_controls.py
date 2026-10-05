#!/usr/bin/env python3
"""Check the joint-pair policy against Q1438's exact-base witnesses."""

from __future__ import annotations

import argparse
import hashlib
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

from q1423_target_coupled.target_inputs import (  # noqa: E402
    encode_targets, target_list)
from q1438_dense_base.build_formula import build_cnf  # noqa: E402
from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1420_root_theory.verify_archive import model_from_file  # noqa: E402

OUTPUT = HERE / "validation.json"
POLICY = "joint_pair_span"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_cell(n):
    parent = json.loads((Q1438 / "solver_protocol.json").read_text())
    workload = parent["workloads"][f"n{n}_free_partner"]
    raw, varmap, formula, meta, variables, clauses = build_cnf(
        n, "free_partner")
    assert hashlib.sha256(raw).hexdigest() == workload["cnf_raw_sha256"]
    assert hashlib.sha256(varmap).hexdigest() == workload["variable_map_sha256"]
    q1436 = json.loads((PARENT / "q1436_affine_pair/protocol.json").read_text())[
        "workloads"][f"n{n}_free_partner"]
    q1420 = json.loads((Q1420 / "protocol.json").read_text())[
        "workloads"][q1436["parent_q1420_key"]]
    targets = encode_targets(n, target_list(n, "free_mids", q1420))
    assert hashlib.sha256(targets).hexdigest() == workload[
        "target_input_sha256"]
    with tempfile.TemporaryDirectory(prefix=f"q1446_n{n}_") as temporary:
        tmp = Path(temporary)
        cnf = tmp / "system.cnf"
        varmap_path = tmp / "variables.txt"
        target_path = tmp / "targets.txt"
        model_path = tmp / "solver.model.txt"
        cnf.write_bytes(raw)
        varmap_path.write_bytes(varmap)
        target_path.write_bytes(targets)
        command = [str(HERE / "theory_solver"),
                   str(Q1420 / f"n{n}_field.txt"),
                   str(cnf), str(varmap_path), str(model_path),
                   "1000000", "30", POLICY, str(target_path)]
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=40)
        assert completed.returncode == 0, (completed.returncode,
                                           completed.stderr,
                                           completed.stdout[-1000:])
        report = json.loads(completed.stdout)
        assert report["status"] == 10
        assert report["decision_policy"] == POLICY
        assert report["target_coupled_active"] is True
        assert report["span_checks"] == (report["span_checks_pair0"] +
                                          report["span_checks_pair1"])
        assert report["span_rejections"] == (
            report["span_rejections_pair0"] +
            report["span_rejections_pair1"])
        relation = model_relation(raw, formula, meta, variables, clauses,
                                  model_path, parent["instances"][str(n)])
        assert relation["status"] == "verified_four_point_relation"
        assert relation["distinct_columns"] == 4
        return {"degree": n, "status": "verified_four_point_relation",
                "curve_id": workload["curve_id"],
                "factor_base_actual_B": workload["factor_base_actual_B"],
                "folded_columns_K": workload["folded_columns_K"],
                "factor_base_enumerated_set_sha256": workload[
                    "factor_base_enumerated_set_sha256"],
                "cnf_raw_sha256": workload["cnf_raw_sha256"],
                "variable_map_sha256": workload["variable_map_sha256"],
                "target_input_sha256": workload["target_input_sha256"],
                "span_checks_pair0": report["span_checks_pair0"],
                "span_checks_pair1": report["span_checks_pair1"],
                "span_rejections_pair0": report["span_rejections_pair0"],
                "span_rejections_pair1": report["span_rejections_pair1"],
                "point_relation": relation}


def validate_partial_n53():
    """Force a known ordinary witness through both partial-pair guards."""
    n = 53
    parent = json.loads((Q1438 / "solver_protocol.json").read_text())
    workload = parent["workloads"]["n53_ordinary"]
    raw, varmap, formula, meta, variables, clauses = build_cnf(n, "ordinary")
    assert hashlib.sha256(raw).hexdigest() == workload["cnf_raw_sha256"]
    assert hashlib.sha256(varmap).hexdigest() == workload["variable_map_sha256"]
    archived = Q1438 / "runs/n53_free_partner/solver.model.txt"
    model = model_from_file(archived)
    assert len(model) == variables
    free_counts = []
    units = []
    for leaf in meta["leaf_variables"]:
        ones = [bit for bit in leaf if model[bit]]
        zeros = [bit for bit in leaf if not model[bit]]
        assert len(ones) == 3 and len(zeros) >= 13
        free = {ones[0], *zeros[:13]}
        free_counts.append(len(free))
        for bit in leaf:
            if bit not in free:
                units.append(bit if model[bit] else -bit)
    for row in (meta["pair_mid_variables"] +
                [meta["target_selector_variables"]]):
        units.extend(bit if model[bit] else -bit for bit in row)
    head, tail = raw.split(b"\n", 1)
    assert head == f"p cnf {variables} {clauses}".encode()
    augmented = (f"p cnf {variables} {clauses + len(units)}\n".encode() +
                 tail + b"".join(f"{lit} 0\n".encode() for lit in units))
    q1436 = json.loads((PARENT / "q1436_affine_pair/protocol.json").read_text())[
        "workloads"]["n53_ordinary"]
    q1420 = json.loads((Q1420 / "protocol.json").read_text())[
        "workloads"][q1436["parent_q1420_key"]]
    targets = encode_targets(n, target_list(n, "ordinary", q1420))
    assert hashlib.sha256(targets).hexdigest() == workload[
        "target_input_sha256"]
    with tempfile.TemporaryDirectory(prefix="q1446_n53_partial_") as temporary:
        tmp = Path(temporary)
        cnf = tmp / "system.cnf"
        varmap_path = tmp / "variables.txt"
        target_path = tmp / "targets.txt"
        model_path = tmp / "solver.model.txt"
        cnf.write_bytes(augmented)
        varmap_path.write_bytes(varmap)
        target_path.write_bytes(targets)
        command = [str(HERE / "theory_solver"),
                   str(Q1420 / "n53_field.txt"),
                   str(cnf), str(varmap_path), str(model_path),
                   "1000000", "30", POLICY, str(target_path)]
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=40)
        assert completed.returncode == 0, (completed.returncode,
                                           completed.stderr,
                                           completed.stdout[-1000:])
        report = json.loads(completed.stdout)
        assert report["status"] == 10
        assert report["span_checks_pair0"] > 0
        assert report["span_checks_pair1"] > 0
        relation = model_relation(raw, formula, meta, variables, clauses,
                                  model_path, parent["instances"]["53"])
        assert relation["status"] == "verified_four_point_relation"
        return {"status": "verified_four_point_relation",
                "free_leaf_bits_each": free_counts,
                "span_checks_pair0": report["span_checks_pair0"],
                "span_checks_pair1": report["span_checks_pair1"],
                "span_rejections_pair0": report["span_rejections_pair0"],
                "span_rejections_pair1": report["span_rejections_pair1"],
                "ordinary_cnf_sha256": workload["cnf_raw_sha256"],
                "known_model_sha256": sha(archived),
                "point_relation": relation}


def validate():
    return {"proposal_id": "Q1446", "candidate_id": None,
            "isogeny": "none", "policy": POLICY,
            "solver_source_sha256": sha(HERE / "theory_solver.cpp"),
            "solver_binary_sha256": sha(HERE / "theory_solver"),
            "controls": [validate_cell(n) for n in (53, 83)],
            "partial_n53_control": validate_partial_n53(),
            "status": "pass"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.check:
        assert json.loads(OUTPUT.read_text()) == result
        print("Q1446 controls: PASS")
    else:
        assert not OUTPUT.exists(), "refuse overwrite"
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": "pass",
                          "controls": [{"degree": c["degree"],
                                        "status": c["status"],
                                        "span_checks_pair0": c[
                                            "span_checks_pair0"],
                                        "span_checks_pair1": c[
                                            "span_checks_pair1"]}
                                       for c in result["controls"]]},
                         sort_keys=True))
