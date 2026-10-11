#!/usr/bin/env python3
"""Q1419 bounded partial-pinning diagnostic on archived balanced S3 XCNFs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import resource
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from run_group_add_probe import archive, coordinates, solve, stats  # noqa: E402
from run_probe import curves, field, sha  # noqa: E402

PROTOCOL = HERE / "protocol.json"
CELLS = {
    "full_lock": ((0, 1, 2, 3), True, True),
    "free_mids": ((0, 1, 2, 3), False, True),
    "free_target": ((0, 1, 2, 3), False, False),
    "three_leaves": ((0, 1, 2), False, True),
    "two_split": ((0, 2), False, True),
    "two_same": ((0, 1), False, True),
    "one_leaf": ((0,), False, True),
    "target_only": ((), False, True),
}


def canonical_digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def pin_bits(formula, bits, value):
    formula.clauses.extend(([bit if value >> position & 1 else -bit]
                            for position, bit in enumerate(bits)))


def read_profile(protocol, n):
    profile = protocol["profiles"][str(n)]
    assert profile["field_degree_n"] == n
    for name in ("parent_receipt", "fixture_receipt", "formula_archive",
                 "factor_base_archive"):
        path = ROOT / profile[name]["path"]
        assert sha(path) == profile[name]["sha256"]
    parent = json.loads((ROOT / profile["parent_receipt"]["path"]).read_text())
    fixture = json.loads((ROOT / profile["fixture_receipt"]["path"]).read_text())
    assert parent["curve_id"] == fixture["curve_id"] == profile["curve_id"]
    assert parent["factor_base_actual_B"] == fixture[
        "factor_base_actual_B"] == profile["factor_base_actual_B"]
    assert parent["factor_base_folded_columns"] == fixture[
        "factor_base_folded_columns"] == profile["folded_columns_K"]
    assert (parent["factor_base_enumerated_set_sha256"] ==
            fixture["factor_base_enumerated_set_sha256"] ==
            profile["factor_base_enumerated_set_sha256"])
    assert (parent["public_target"] == fixture["public_target"] ==
            profile["public_target"])
    assert parent["attempts"][0]["xcnf_sha256"] == profile[
        "formula_raw_sha256"]
    return profile, parent, fixture


def build_cell(profile, parent, fixture, cell):
    n = profile["field_degree_n"]
    formula, leaves, mids, _, selector = build_balanced(
        n, profile["normal_basis_weight_bound"],
        parent["raw_preimage_x_coordinates"])
    onb = field.Onb(n)
    selected_x = onb.toCoords(int(fixture["fixture"]["raw_sum"][0]))
    choice = parent["raw_preimage_x_coordinates"].index(selected_x)
    fixture_data = fixture["fixture"]
    leaf_indices, pin_mids, pin_selector = CELLS[cell]
    for index in leaf_indices:
        pin_bits(formula, leaves[index], fixture_data["raw_leaf_x"][index])
    if pin_mids:
        for bits, point in zip(mids, fixture_data["raw_pair_sum_points"]):
            pin_bits(formula, bits, onb.toCoords(int(point[0])))
    if pin_selector:
        pin_bits(formula, selector, choice)
    return formula, leaves, choice


def read_base_keys(profile, onb):
    path = ROOT / profile["factor_base_archive"]["path"]
    n = profile["field_degree_n"]
    if n == 53:
        import base64
        with gzip.open(path, "rt") as stream:
            base = json.load(stream)
        encoded = base64.b64decode(base["factor_base"][
            "packed_canonical_x_keys_base64"], validate=True)
        assert hashlib.sha256(encoded).hexdigest() == profile[
            "factor_base_enumerated_set_sha256"]
        keys = {int.from_bytes(encoded[i:i + 7], "little")
                for i in range(0, len(encoded), 7)}
    else:
        encoded = path.read_bytes()
        assert hashlib.sha256(encoded).hexdigest() == profile[
            "factor_base_enumerated_set_sha256"]
        assert len(encoded) % 21 == 0
        keys = {int.from_bytes(encoded[i:i + 21], "little")
                for i in range(0, len(encoded), 21)}
    assert len(keys) == profile["folded_columns_K"]
    return keys


def canonical_x(onb, x):
    values = []
    for _ in range(onb.m):
        values.append(onb.toCoords(x))
        x = onb.sqr(x)
    return min(values)


def check_formula_model(formula, model):
    assert model is not None and len(model) == formula.variables
    assert all(any(model[abs(lit)] == (lit > 0) for lit in clause)
               for clause in formula.clauses)
    assert all((sum(model[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)


def verify_relation(profile, model, leaves):
    n = profile["field_degree_n"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    order = profile["subgroup_order_r"]
    cofactor = profile["cofactor"]
    public = tuple(map(int, profile["public_target"]))
    keys = read_base_keys(profile, onb)
    orbit = OrbitKey(onb) if n == 83 else None
    raw_coords, raw_points, projected, columns = [], [], [], []
    for bits in leaves:
        xcoords = coordinates(bits, model)
        assert 0 < xcoords < (1 << n)
        assert xcoords.bit_count() <= profile["normal_basis_weight_bound"]
        point = curve.pointFromX(onb.fromCoords(xcoords))
        if point is None:
            return {"status": "nonrational_raw_x", "raw_leaf_x":
                    raw_coords + [xcoords]}
        subgroup = curve.mul(point, cofactor)
        if subgroup is None:
            return {"status": "identity_projection", "raw_leaf_x":
                    raw_coords + [xcoords]}
        assert curve.mul(subgroup, order) is None
        key = canonical_x(onb, subgroup[0]) if n == 53 else (
            orbit.canonical(subgroup)[0])
        if key not in keys:
            return {"status": "outside_exact_base", "raw_leaf_x":
                    raw_coords + [xcoords]}
        raw_coords.append(xcoords)
        raw_points.append(point)
        projected.append(subgroup)
        columns.append(key)
    if len(set(columns)) != 4:
        return {"status": "duplicate_columns", "raw_leaf_x": raw_coords}
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(raw_points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if total is not None and curve.mul(total, cofactor) == public:
            return {
                "status": "verified_four_point_relation",
                "raw_leaf_x": raw_coords,
                "signs": list(signs),
                "projected_points": [[int(x), int(y)] for x, y in projected],
                "distinct_columns": 4,
                "public_target": list(public),
            }
    return {"status": "no_signed_public_sum", "raw_leaf_x": raw_coords}


def protocol_check(protocol):
    assert protocol["proposal_id"] == "Q1419"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["runner_source_sha256"] == sha(Path(__file__))
    for source, digest in protocol["dependency_sha256"].items():
        assert sha(ROOT / source) == digest
    binary = Path(shutil.which("cryptominisat5"))
    assert sha(binary) == protocol["solver_binary_sha256"]
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    assert protocol["runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    return binary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--cell", choices=tuple(CELLS), required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    binary = protocol_check(protocol)
    profile, parent, fixture = read_profile(protocol, args.degree)
    cell = args.cell
    assert protocol["cells"][cell] == {
        "pinned_leaf_indices": list(CELLS[cell][0]),
        "pin_pair_intermediates": CELLS[cell][1],
        "pin_target_preimage_selector": CELLS[cell][2],
    }
    output_dir = HERE / "runs" / f"n{args.degree}_{cell}"
    if not args.preflight:
        assert not output_dir.exists()
        output_dir.mkdir(parents=True)
    start_build = time.perf_counter()
    formula, leaves, choice = build_cell(profile, parent, fixture, cell)
    formula_build_seconds = time.perf_counter() - start_build
    if args.preflight:
        print(json.dumps({"status": "PREFLIGHT", "degree": args.degree,
                          "cell": cell, "variables": formula.variables,
                          "clauses": len(formula.clauses),
                          "fixture_target_choice": choice}))
        return
    formula_path = output_dir / "system.xcnf"
    formula.write(formula_path)
    solver_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = solve(formula_path, binary, protocol["solver_wall_cap_seconds"],
                   protocol["solver_conflict_cap"])
    solver_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path = output_dir / "solver.stdout.txt"
    stderr_path = output_dir / "solver.stderr.txt"
    stdout_path.write_text(result["stdout"])
    stderr_path.write_text(result["stderr"])
    checked = None
    relation_check_start = time.perf_counter()
    if result["model"] is not None:
        check_formula_model(formula, result["model"])
        checked = verify_relation(profile, result["model"], leaves)
    relation_check_seconds = time.perf_counter() - relation_check_start
    compressed, formula_bytes, formula_digest = archive(formula_path)
    identity = {
        "field": profile["field"],
        "curve": profile["curve"],
        "isogeny": "none",
        "factor_base": profile["factor_base"],
        "point_decomposition": {
            "m": 4, "stage_code": "PDP4sat",
            "summation_tree": "balanced pair-pair S3",
            "encoding_source_sha256": protocol["encoding_source_sha256"],
            "solver_binary_sha256": protocol["solver_binary_sha256"],
            "pinning_policy": protocol["cells"][cell],
        },
    }
    config_digest = canonical_digest(identity)
    stage_id = (f"PS1N{args.degree}Ckb1fb{profile['factor_base_actual_B']}"
                f"PDP4sath{config_digest[:12]}")
    receipt = {
        "kind": "q1419_balanced_s3_partial_pinning_stage_diagnostic",
        "proposal_id": "Q1419", "candidate_id": None, "run_id": None,
        "stage_config_id": stage_id,
        "stage_config_sha256_full": config_digest,
        "stage_config_hash_input": identity,
        "stage_run_id": f"{stage_id}W{profile['workload_id']}R1",
        "curve_id": profile["curve_id"], "isogeny": "none",
        "field_degree_n": args.degree,
        "factor_base_actual_B": profile["factor_base_actual_B"],
        "folded_columns_K": profile["folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "workload_id": profile["workload_id"],
        "input_law": profile["workload_record"]["input_law"],
        "cell": cell,
        "pinning_policy": protocol["cells"][cell],
        "known_witness_target_choice": choice,
        "formula": stats(formula),
        "formula_raw_bytes": formula_bytes,
        "formula_raw_sha256": formula_digest,
        "formula_archive_sha256": sha(compressed),
        "solver_status": result["status"],
        "solver_return_code": result["return_code"],
        "solver_conflicts_reported": result["conflicts_reported"],
        "solver_wall_seconds_exploratory": result["wall_seconds"],
        "formula_build_seconds_exploratory": formula_build_seconds,
        "relation_check_seconds_exploratory": relation_check_seconds,
        "peak_child_rss_raw": solver_after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "child_user_cpu_seconds": solver_after.ru_utime - solver_before.ru_utime,
        "child_system_cpu_seconds": solver_after.ru_stime - solver_before.ru_stime,
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "model_present": result["model"] is not None,
        "model_check": checked,
        "verified_relation_count": int(checked is not None and checked[
            "status"] == "verified_four_point_relation"),
        "natural_relation_yield_estimate": None,
        "is_ordinary_yield_measurement": False,
        "is_complete_solve_projection": False,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(PROTOCOL),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "runner_source_sha256": sha(Path(__file__)),
        "parent_receipt_sha256": sha(ROOT / profile["parent_receipt"]["path"]),
        "fixture_receipt_sha256": sha(ROOT / profile["fixture_receipt"]["path"]),
    }
    (output_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"degree": args.degree, "cell": cell,
                      "status": result["status"],
                      "verified_relations": receipt["verified_relation_count"],
                      "solver_seconds": result["wall_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
