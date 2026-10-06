#!/usr/bin/env python3
"""Measure compact S3 on the full, exact n83 weight-five projected base."""

from __future__ import annotations

import argparse
import json
import random
import resource
import shutil
import time
from pathlib import Path

from chain_s3_projected_sparse import build_projected_sparse_chain
from q1325_inputs import read_inputs
from run_group_add_probe import archive, solve, stats
from run_probe import HERE, ROOT, curves, field, lift, sha

import sys
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402


def coordinates(bits, model):
    return sum(1 << i for i, bit in enumerate(bits) if model.get(bit, False))


def pin_bits(formula, bits, value):
    formula.clauses.extend(([bit if value >> i & 1 else -bit]
                            for i, bit in enumerate(bits)))


def planted_fixture(onb, curve, key_set, seed):
    rng = random.Random(seed)
    orbit = OrbitKey(onb)
    raw_x = []
    projected = []
    while len(raw_x) < 4:
        mask = sum(1 << bit for bit in rng.sample(range(83), 5))
        if mask in raw_x:
            continue
        point = curve.pointFromX(onb.fromCoords(mask))
        if point is None:
            continue
        subgroup = curve.mul(point, 4)
        if subgroup is None:
            continue
        assert orbit.canonical(subgroup)[0] in key_set
        raw_x.append(mask)
        projected.append(subgroup)
    first = curve.add(projected[0], projected[1])
    second = curve.add(first, projected[2])
    target = curve.add(second, projected[3])
    assert first is not None and second is not None and target is not None
    return raw_x, projected, (first, second), target


def verify_model(onb, curve, order, key_set, target, raw_leaves,
                 projected_leaves, model):
    orbit = OrbitKey(onb)
    raw_x = [coordinates(bits, model) for bits in raw_leaves]
    projected_x = [coordinates(bits, model) for bits in projected_leaves]
    for raw, expected in zip(raw_x, projected_x):
        assert raw and raw.bit_count() <= 5
        point = curve.pointFromX(onb.fromCoords(raw))
        assert point is not None
        subgroup = curve.mul(point, 4)
        assert subgroup is not None and curve.mul(subgroup, order) is None
        assert onb.toCoords(subgroup[0]) == expected
        assert orbit.canonical(subgroup)[0] in key_set
    decoded_x, relation, status = lift(
        onb, curve, projected_leaves, model, target, target, 1)
    assert decoded_x == projected_x
    if relation is not None:
        assert status == "verified_four_point_relation"
        assert relation["public_target"] == [str(value) for value in target]
    return raw_x, projected_x, status, relation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("ordinary", "planted_locked"),
                        required=True)
    args = parser.parse_args()
    mode = args.mode
    stem = f"n83_q1325_{mode}"
    output = HERE / "runs" / f"{stem}.json"
    formula_path = HERE / "runs" / f"{stem}.xcnf"
    archive_path = formula_path.with_suffix(".xcnf.gz")
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in (
        output, formula_path, archive_path, stdout_path, stderr_path))
    runtime_path = HERE / "q1325_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    protocol_path = HERE / "q1325_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    base_path, base, key_path, keys, baseline_path, baseline = read_inputs()
    assert protocol["factor_base"]["base_receipt_sha256"] == sha(base_path)
    assert protocol["factor_base"]["point_key_file_sha256"] == sha(key_path)
    assert protocol["factor_base"]["enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]
    assert protocol["ordinary_target_receipt_sha256"] == sha(baseline_path)
    key_set = set(keys)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(base["curve"]["subgroup_order"])
    binary = Path(shutil.which("cryptominisat5"))
    fixture = None
    if mode == "ordinary":
        target = tuple(map(int, baseline["public_subgroup_target"]))
    else:
        raw_x, points, mids, target = planted_fixture(
            onb, curve, key_set,
            protocol["planted_control"]["normal_x_support_seed"])
        fixture = {"raw_leaf_x": raw_x,
                   "projected_leaf_points": [list(point) for point in points],
                   "intermediate_points": [list(point) for point in mids]}
    assert curve.onCurve(target) and curve.mul(target, order) is None
    assert mode != "ordinary" or list(target) == list(map(
        int, protocol["ordinary_public_target"]))
    max_seconds = protocol["point_decomposition"][
        "ordinary_wall_limit_seconds" if mode == "ordinary" else
        "planted_locked_wall_limit_seconds"]
    max_conflicts = protocol["point_decomposition"]["max_conflicts"]

    started = time.perf_counter()
    formula, raw_leaves, projected_leaves, mid_variables = (
        build_projected_sparse_chain(83, 5, onb.toCoords(target[0])))
    if fixture is not None:
        for bits, value in zip(raw_leaves, raw_x):
            pin_bits(formula, bits, value)
        for bits, point in zip(projected_leaves, points):
            pin_bits(formula, bits, onb.toCoords(point[0]))
        for bits, point in zip(mid_variables, mids):
            pin_bits(formula, bits, onb.toCoords(point[0]))
    build_seconds = time.perf_counter() - started
    formula_stats = stats(formula)
    formula.write(formula_path)
    remaining = max_seconds - (time.perf_counter() - started)
    if remaining > 0:
        result = solve(formula_path, binary, remaining, max_conflicts)
    else:
        result = {"command": None, "status": "no_solver_budget",
                  "return_code": None, "wall_seconds": 0.0,
                  "conflicts_reported": None, "stdout": "", "stderr": "",
                  "model": None}
    charged_seconds = time.perf_counter() - started
    parent_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    stdout_path.write_text(result["stdout"])
    stderr_path.write_text(result["stderr"])
    decoded_raw = decoded_projected = lift_status = relation = None
    if result["model"] is not None:
        decoded_raw, decoded_projected, lift_status, relation = verify_model(
            onb, curve, order, key_set, target, raw_leaves,
            projected_leaves, result["model"])
    if mode == "planted_locked":
        assert relation is not None and decoded_raw == raw_x
        assert decoded_projected == [onb.toCoords(point[0])
                                     for point in points]
    compressed, formula_bytes, formula_sha = archive(formula_path)
    receipt = {
        "kind": "q1325_full_weight5_projected_s3_stage_probe",
        "proposal_id": "Q1325", "candidate_id": None, "run_id": None,
        "workload_id": baseline["workload_id"] if mode == "ordinary" else None,
        "mode": mode, "oracle_assisted": mode == "planted_locked",
        "curve_id": base["curve"]["curve_id"], "isogeny": "none",
        "public_target": list(target),
        "factor_base_actual_B": base["factor_base"][
            "actual_usable_points_B_before_folding"],
        "factor_base_folded_columns": base["factor_base"][
            "signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": base["factor_base"][
            "enumerated_set_sha256"],
        "base_receipt_sha256": sha(base_path),
        "base_point_key_file_sha256": sha(key_path),
        "target_independent_base_load_excluded": True,
        "formula_build_seconds": build_seconds,
        "target_pdp_wall_seconds": charged_seconds if mode == "ordinary" else None,
        "oracle_control_wall_seconds": charged_seconds if fixture is not None else None,
        "solver_wall_seconds": result["wall_seconds"],
        "status": result["status"],
        "return_code": result["return_code"],
        "solver_conflicts_reported": result["conflicts_reported"],
        "formula": formula_stats,
        "xcnf_archive": compressed.name,
        "xcnf_sha256": formula_sha,
        "xcnf_bytes": formula_bytes,
        "raw_leaf_x_coordinates": decoded_raw,
        "projected_leaf_x_coordinates": decoded_projected,
        "lift_status": lift_status,
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "natural_relation_yield_estimate": None,
        "field_operations": None,
        "complete_solve_work_log2": None,
        "fixture": fixture,
        "peak_parent_rss_raw": parent_rss,
        "peak_child_rss_raw": child_rss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "max_seconds": max_seconds,
        "max_conflicts": max_conflicts,
        "solver_command": result["command"],
        "solver_binary_sha256": sha(binary),
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "ordinary_target_receipt_sha256": sha(baseline_path),
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "projected_source_sha256": sha(HERE / "chain_s3_projected_sparse.py"),
        "runner_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"mode": mode, "status": result["status"],
                      "verified_relation": relation is not None,
                      "formula": formula_stats,
                      "charged_seconds": charged_seconds}))


if __name__ == "__main__":
    main()
