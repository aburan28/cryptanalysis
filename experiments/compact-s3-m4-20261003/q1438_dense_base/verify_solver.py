#!/usr/bin/env python3
"""Verify Q1438 compact-S3 models with exact curve arithmetic."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT / "q1420_root_theory"))
from q1420_root_theory.verify_archive import (  # noqa: E402
    check_cnf, model_from_file)
from run_probe import ROOT, curves, field, sha  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402
from q1438_dense_base.build_formula import build_cnf  # noqa: E402

sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402
from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402


def model_relation(raw, formula, meta, variables, clauses, model_path,
                   instance):
    model = model_from_file(model_path)
    check_cnf(raw, model, variables, clauses)
    assert all(any(model[abs(lit)] == (lit > 0) for lit in clause)
               for clause in formula.clauses)
    assert all((sum(model[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    n = meta["degree_n"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    leaves, mids = meta["leaf_variables"], meta["pair_mid_variables"]

    def value(bits):
        return sum(1 << i for i, bit in enumerate(bits) if model[bit])

    for side in range(2):
        a = onb.fromCoords(value(leaves[2 * side]))
        b = onb.fromCoords(value(leaves[2 * side + 1]))
        mid = value(mids[side])
        roots = {onb.toCoords(x) for x in s3_roots(onb, a, b)}
        assert mid in roots

    raw_points, projected_points, projected_keys, raw_masks = [], [], [], []
    for bits in leaves:
        mask = value(bits)
        assert 0 < mask < (1 << n)
        assert mask.bit_count() <= instance["new_weight_bound"]
        point = curve.pointFromX(onb.fromCoords(mask))
        if point is None:
            return {"status": "nonrational_raw_x", "raw_leaf_x": raw_masks + [mask]}
        subgroup = curve.mul(point, instance["cofactor"])
        if subgroup is None:
            return {"status": "identity_projection", "raw_leaf_x": raw_masks + [mask]}
        assert curve.mul(subgroup, instance["subgroup_order"]) is None
        key = canonical_rotation(orbit.cycle_bits(subgroup[0]), n)
        raw_points.append(point)
        projected_points.append(subgroup)
        projected_keys.append(key)
        raw_masks.append(mask)
    if len(set(projected_keys)) != 4:
        return {"status": "duplicate_columns", "raw_leaf_x": raw_masks}
    public = tuple(map(int, meta["public_target"]))
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(raw_points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if total is not None and curve.mul(total, instance["cofactor"]) == public:
            return {
                "status": "verified_four_point_relation",
                "raw_leaf_x": raw_masks,
                "signs": list(signs),
                "projected_points": [[int(x), int(y)]
                                     for x, y in projected_points],
                "projected_columns": projected_keys,
                "distinct_columns": 4,
                "public_target": list(public),
            }
    return {"status": "no_signed_public_sum", "raw_leaf_x": raw_masks}


def verify_cell(protocol, key):
    workload = protocol["workloads"][key]
    n = workload["degree_n"]
    instance = protocol["instances"][str(n)]
    output = HERE / "runs" / key
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["proposal_id"] == "Q1438"
    assert receipt["candidate_id"] is None and receipt["isogeny"] == "none"
    assert receipt["stage_run_id"] == workload["stage_run_id"]
    assert receipt["workload_id"] == workload["workload_id"]
    assert receipt["protocol_sha256"] == sha(HERE / "solver_protocol.json")
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "run_solver.py"]
    assert receipt["solver_binary_sha256"] == protocol["solver_binary_sha256"]
    assert receipt["runtime_info_sha256"] == protocol["runtime_info_sha256"]
    assert receipt["cnf_archive_sha256"] == sha(output / "system.cnf.gz")
    assert receipt["variable_map_sha256"] == sha(output / "variables.txt")
    assert receipt["target_input_sha256"] == sha(output / "targets.txt")
    assert receipt["solver_stdout_sha256"] == sha(output / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(output / "solver.stderr.txt")
    raw, varmap, formula, meta, variables, clauses = build_cnf(
        n, workload["cell"])
    assert hashlib.sha256(raw).hexdigest() == workload["cnf_raw_sha256"]
    assert hashlib.sha256(varmap).hexdigest() == workload["variable_map_sha256"]
    assert raw == gzip.decompress((output / "system.cnf.gz").read_bytes())
    assert receipt["cnf_raw_sha256"] == workload["cnf_raw_sha256"]
    assert receipt["cnf_variables"] == variables
    assert receipt["cnf_clauses"] == clauses
    assert meta["curve_id"] == workload["curve_id"]
    assert meta["factor_base_actual_B"] == workload["factor_base_actual_B"]
    assert receipt["curve_id"] == workload["curve_id"]
    assert receipt["factor_base_actual_B"] == workload["factor_base_actual_B"]
    assert receipt["folded_columns_K"] == workload["folded_columns_K"]
    assert receipt["factor_base_enumerated_set_sha256"] == workload[
        "factor_base_enumerated_set_sha256"]
    if receipt["solver_status"] in ("sat", "censored", "unsat"):
        assert receipt["solver_report_error"] is None
        assert receipt["solver_report"] is not None
        assert receipt["solver_report"]["cnf_variables"] == variables
        assert receipt["solver_report"]["cnf_clauses"] == clauses
    if receipt["solver_status"] == "sat":
        model_path = output / "solver.model.txt"
        assert receipt["solver_model_sha256"] == sha(model_path)
        assert receipt["model_check_error"] is None
        checked = model_relation(raw, formula, meta, variables, clauses,
                                 model_path, instance)
        assert checked == receipt["model_check"]
        assert receipt["verified_relation_count"] == int(
            checked["status"] == "verified_four_point_relation")
        status = checked["status"]
    else:
        assert receipt["solver_status"] in ("censored", "external_timeout",
                                             "unsat", "error")
        assert receipt["solver_model_sha256"] is None
        assert receipt["model_check"] is None
        assert receipt["verified_relation_count"] == 0
        status = receipt["solver_status"]
    assert receipt["natural_relation_yield_estimate"] is None
    assert receipt["complete_solve_work_log2"] is None
    return {"key": key, "status": status,
            "verified_relation_count": receipt["verified_relation_count"],
            "receipt_sha256": sha(receipt_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((HERE / "solver_protocol.json").read_text())
    assert protocol["source_sha256"]["verify_solver.py"] == sha(Path(__file__))
    rows = [verify_cell(protocol, key) for key in protocol["run_order"]]
    result = {"kind": "q1438_dense_base_solver_archive_verification",
              "status": "passed", "proposal_id": "Q1438",
              "candidate_id": None, "isogeny": "none", "rows": rows,
              "protocol_sha256": sha(HERE / "solver_protocol.json"),
              "source_sha256": sha(Path(__file__)),
              "scope": "independent model replay and source-bound archive check; censored rows are not relation-yield estimates"}
    if args.emit:
        path = HERE / "solver_verification.json"
        assert not path.exists(), "refuse to overwrite solver verification"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
