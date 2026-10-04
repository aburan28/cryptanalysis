#!/usr/bin/env python3
"""Frozen Q1403 ordered-raw-leaf comparison on the exact Q1325 N83 base."""

from __future__ import annotations

import argparse
import json
import resource
import shutil
import time
from pathlib import Path

from chain_s3_projected_sparse_ordered import (
    build_ordered_projected_sparse_chain,
)
from q1325_inputs import read_inputs
from run_group_add_probe import archive, solve, stats
from run_probe import HERE, curves, field, sha
from run_q1325_full_weight5_probe import (
    pin_bits, planted_fixture, verify_model,
)


SOURCES = (
    "chain_s3.py",
    "chain_s3_factored.py",
    "chain_s3_ordered.py",
    "chain_s3_projected_sparse.py",
    "chain_s3_projected_sparse_ordered.py",
    "run_q1325_full_weight5_probe.py",
    "run_group_add_probe.py",
    "run_q1403_ordered_q1325.py",
)


def sorted_fixture(onb, curve, key_set, seed):
    raw_x, points, _, _ = planted_fixture(onb, curve, key_set, seed)
    ordered = sorted(zip(raw_x, points), key=lambda item: item[0])
    raw_x = [raw for raw, _ in ordered]
    points = [point for _, point in ordered]
    first = curve.add(points[0], points[1])
    second = curve.add(first, points[2])
    target = curve.add(second, points[3])
    assert first is not None and second is not None and target is not None
    return raw_x, points, (first, second), target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=(
        "ordinary", "planted_unpinned", "planted_locked"), required=True)
    args = parser.parse_args()
    mode = args.mode
    stem = f"n83_q1403_{mode}"
    output = HERE / "runs" / f"{stem}.json"
    formula_path = HERE / "runs" / f"{stem}.xcnf"
    archive_path = formula_path.with_suffix(".xcnf.gz")
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in (
        output, formula_path, archive_path, stdout_path, stderr_path))

    protocol_path = HERE / "q1403_ordered_q1325_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1403"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    for source in SOURCES:
        assert protocol["source_sha256"][source] == sha(HERE / source)
    runtime_path = HERE / "q1403_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"

    base_path, base, key_path, keys, baseline_path, baseline = read_inputs()
    assert protocol["q1325_base_receipt_sha256"] == sha(base_path)
    assert protocol["q1325_point_keys_sha256"] == sha(key_path)
    assert protocol["ordinary_target_receipt_sha256"] == sha(baseline_path)
    assert protocol["factor_base_actual_B"] == base["factor_base"][
        "actual_usable_points_B_before_folding"]
    assert protocol["factor_base_folded_columns"] == base["factor_base"][
        "signed_frobenius_columns"]
    assert protocol["factor_base_enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]
    assert protocol["curve_id"] == base["curve"]["curve_id"]
    assert protocol["ordinary_workload_id"] == baseline["workload_id"]
    assert protocol["ordinary_public_target"] == baseline[
        "public_subgroup_target"]
    key_set = set(keys)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(base["curve"]["subgroup_order"])
    binary = Path(shutil.which("cryptominisat5"))

    fixture = None
    if mode == "ordinary":
        target = tuple(map(int, baseline["public_subgroup_target"]))
    else:
        raw_x, points, mids, target = sorted_fixture(
            onb, curve, key_set, protocol["planted_seed"])
        fixture = {
            "raw_leaf_x": raw_x,
            "projected_leaf_points": [list(point) for point in points],
            "intermediate_points": [list(point) for point in mids],
        }
    assert curve.onCurve(target) and curve.mul(target, order) is None
    max_seconds = protocol["limits_seconds"][mode]
    max_conflicts = protocol["max_conflicts"]

    started = time.perf_counter()
    formula, raw_leaves, projected_leaves, mid_variables = (
        build_ordered_projected_sparse_chain(
            83, 5, onb.toCoords(target[0])))
    if mode == "planted_locked":
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
        result = {
            "command": None, "status": "no_solver_budget",
            "return_code": None, "wall_seconds": 0.0,
            "conflicts_reported": None, "stdout": "", "stderr": "",
            "model": None,
        }
    target_pdp_seconds = time.perf_counter() - started
    parent_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    stdout_path.write_text(result["stdout"])
    stderr_path.write_text(result["stderr"])

    verification_started = time.perf_counter()
    decoded_raw = decoded_projected = lift_status = relation = None
    if result["model"] is not None:
        decoded_raw, decoded_projected, lift_status, relation = verify_model(
            onb, curve, order, key_set, target, raw_leaves,
            projected_leaves, result["model"])
    relation_check_seconds = time.perf_counter() - verification_started
    if mode == "planted_locked":
        assert relation is not None and decoded_raw == raw_x
        assert decoded_projected == [onb.toCoords(point[0])
                                     for point in points]
    compressed, formula_bytes, formula_sha = archive(formula_path)

    receipt = {
        "kind": "q1403_ordered_implicit_q1325_s3_stage_probe",
        "proposal_id": "Q1403", "candidate_id": None, "run_id": None,
        "workload_id": (baseline["workload_id"] if mode == "ordinary"
                        else None),
        "mode": mode,
        "oracle_assisted": mode == "planted_locked",
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
        "target_pdp_wall_seconds": (target_pdp_seconds if mode == "ordinary"
                                    else None),
        "target_relation_check_wall_seconds": (
            relation_check_seconds if mode == "ordinary" else None),
        "target_dependent_stage_wall_seconds": (
            target_pdp_seconds + relation_check_seconds
            if mode == "ordinary" else None),
        "control_pdp_wall_seconds": (
            target_pdp_seconds if mode != "ordinary" else None),
        "control_relation_check_wall_seconds": (
            relation_check_seconds if mode != "ordinary" else None),
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
        "source_sha256": {source: sha(HERE / source)
                          for source in SOURCES},
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({
        "mode": mode, "status": result["status"],
        "verified_relation": relation is not None,
        "formula": formula_stats,
        "charged_stage_seconds": target_pdp_seconds + relation_check_seconds,
    }))


if __name__ == "__main__":
    main()
