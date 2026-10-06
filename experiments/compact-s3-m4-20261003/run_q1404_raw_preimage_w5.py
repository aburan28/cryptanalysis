#!/usr/bin/env python3
"""Q1404: direct raw W<=5 S3 chain for Q1325's projected factor base."""

from __future__ import annotations

import argparse
import json
import resource
import shutil
import sys
import time
from pathlib import Path

from chain_s3_multitarget import build_multitarget, decode_choice
from cofactor_preimages import kernel_of_cofactor
from q1325_inputs import read_inputs
from run_group_add_probe import archive, solve, stats
from run_probe import HERE, ROOT, curves, field, lift, sha
from run_q1325_full_weight5_probe import pin_bits, planted_fixture


sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402


SOURCE_PATHS = (
    "ecc2k130/codegen/field.py",
    "ecc2k130/codegen/curves.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "experiments/compact-s3-m4-20261003/cofactor_preimages.py",
    "experiments/compact-s3-m4-20261003/q1325_inputs.py",
    "experiments/compact-s3-m4-20261003/run_group_add_probe.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/compact-s3-m4-20261003/run_q1325_full_weight5_probe.py",
    "experiments/compact-s3-m4-20261003/run_q1404_raw_preimage_w5.py",
)


def preimage_coset(onb, curve, order, target, kernel):
    base = curve.mul(target, pow(4, -1, order))
    assert base is not None and curve.mul(base, 4) == target
    points = {curve.add(base, torsion) for torsion in kernel}
    assert len(points) == 4 and None not in points
    assert all(curve.mul(point, 4) == target for point in points)
    ordered = sorted(points, key=lambda point: (
        onb.toCoords(point[0]), onb.toCoords(point[1])))
    xs = [onb.toCoords(point[0]) for point in ordered]
    assert len(set(xs)) == 4
    return ordered, xs


def fixture_target(onb, curve, key_set, seed):
    raw_x, projected, _, target = planted_fixture(
        onb, curve, key_set, seed)
    raw_points = [curve.pointFromX(onb.fromCoords(value)) for value in raw_x]
    assert all(point is not None for point in raw_points)
    first = curve.add(raw_points[0], raw_points[1])
    second = curve.add(first, raw_points[2])
    raw_sum = curve.add(second, raw_points[3])
    assert first is not None and second is not None and raw_sum is not None
    assert curve.mul(raw_sum, 4) == target
    assert all(curve.mul(point, 4) == expected
               for point, expected in zip(raw_points, projected))
    return raw_x, raw_points, (first, second), raw_sum, target


def verify_model(onb, curve, order, key_set, public, raw_points,
                 raw_xs, leaves, selector, model):
    choice = decode_choice(selector, model)
    assert 0 <= choice < len(raw_points)
    coordinates, relation, status = lift(
        onb, curve, leaves, model, raw_points[choice], public, 4)
    assert all(0 < value < (1 << 83) and value.bit_count() <= 5
               for value in coordinates)
    distinct_columns = None
    if relation is not None:
        orbit = OrbitKey(onb)
        columns = []
        for values in relation["projected_points"]:
            point = tuple(map(int, values))
            assert curve.onCurve(point) and curve.mul(point, order) is None
            column = orbit.canonical(point)[0]
            assert column in key_set
            columns.append(column)
        distinct_columns = len(set(columns)) == 4
        assert relation["public_target"] == [str(value) for value in public]
    return choice, raw_xs[choice], coordinates, status, relation, distinct_columns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=(
        "ordinary", "planted_unpinned", "planted_locked"), required=True)
    args = parser.parse_args()
    mode = args.mode
    stem = f"n83_q1404_{mode}"
    output = HERE / "runs" / f"{stem}.json"
    initial_formula_path = HERE / "runs" / f"{stem}.xcnf"
    assert not output.exists() and not initial_formula_path.exists()
    assert not initial_formula_path.with_suffix(".xcnf.gz").exists()

    protocol_path = HERE / "q1404_raw_preimage_w5_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1404"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    for source in SOURCE_PATHS:
        assert protocol["source_sha256"][source] == sha(ROOT / source)
    runtime_path = HERE / "q1404_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    base_path, base, key_path, keys, baseline_path, baseline = read_inputs()
    assert protocol["q1325_base_receipt_sha256"] == sha(base_path)
    assert protocol["q1325_point_keys_sha256"] == sha(key_path)
    assert protocol["ordinary_target_receipt_sha256"] == sha(baseline_path)
    assert protocol["curve_id"] == base["curve"]["curve_id"]
    assert protocol["factor_base_actual_B"] == base["factor_base"][
        "actual_usable_points_B_before_folding"]
    assert protocol["factor_base_folded_columns"] == base["factor_base"][
        "signed_frobenius_columns"]
    assert protocol["factor_base_enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]
    assert protocol["ordinary_workload_id"] == baseline["workload_id"]
    assert protocol["ordinary_public_target"] == baseline[
        "public_subgroup_target"]
    key_set = set(keys)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(base["curve"]["subgroup_order"])
    assert int(base["curve"]["cofactor"]) == 4
    binary = Path(shutil.which("cryptominisat5"))

    kernel_started = time.perf_counter()
    kernel, kernel_generators, kernel_trials = kernel_of_cofactor(
        curve, onb, order, 4, protocol["kernel_seed"])
    kernel_setup_seconds = time.perf_counter() - kernel_started
    assert len(kernel) == 4
    fixture = None
    coset_path = HERE / "runs/n83_ordinary_raw_preimages.json"
    expected_coset = None
    if mode == "ordinary":
        public = tuple(map(int, baseline["public_subgroup_target"]))
        expected_coset = json.loads(coset_path.read_text())
        assert protocol["ordinary_coset_receipt_sha256"] == sha(coset_path)
    else:
        raw_x, fixture_points, mids, raw_sum, public = fixture_target(
            onb, curve, key_set, protocol["planted_seed"])
        fixture = {
            "raw_leaf_x": raw_x,
            "raw_leaf_points": [list(point) for point in fixture_points],
            "raw_intermediate_points": [list(point) for point in mids],
            "raw_sum": list(raw_sum),
        }

    max_seconds = protocol["limits_seconds"][mode]
    max_conflicts = protocol["max_conflicts"]
    max_models = protocol["max_models"]
    target_started = time.perf_counter()
    assert curve.onCurve(public) and curve.mul(public, order) is None
    raw_points, raw_xs = preimage_coset(
        onb, curve, order, public, kernel)
    target_preimage_seconds = time.perf_counter() - target_started
    if mode == "ordinary":
        assert raw_xs == expected_coset["raw_target_x_coordinates"]
        assert [list(point) for point in raw_points] == [
            [int(value) for value in point]
            for point in expected_coset["raw_target_points"]]
    else:
        assert raw_sum in raw_points

    formula_started = time.perf_counter()
    formula, leaves, mids_variables, target_variables, selector = (
        build_multitarget(83, 5, raw_xs))
    if mode == "planted_locked":
        for bits, value in zip(leaves, raw_x):
            pin_bits(formula, bits, value)
        for bits, point in zip(mids_variables, mids):
            pin_bits(formula, bits, onb.toCoords(point[0]))
        pin_bits(formula, selector, raw_points.index(raw_sum))
    formula_build_seconds = time.perf_counter() - formula_started
    formula_stats = stats(formula)
    attempts = []
    relation = None
    decoded = None
    relation_check_seconds = 0.0
    instrument_seconds = 0.0
    deadline = target_started + max_seconds
    for index in range(max_models):
        decoded = None
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        formula_path = (initial_formula_path if index == 0 else
                        HERE / "runs" / f"{stem}.attempt{index}.xcnf")
        assert not formula_path.exists()
        formula_clause_count = len(formula.clauses)
        formula.write(formula_path)
        remaining = deadline - time.perf_counter()
        if remaining > 0:
            result = solve(formula_path, binary, remaining, max_conflicts)
        else:
            result = {
                "command": None, "status": "no_solver_budget",
                "return_code": None, "wall_seconds": 0.0,
                "conflicts_reported": None, "stdout": "", "stderr": "",
                "model": None,
            }
        stdout_path = HERE / "runs" / f"{stem}.attempt{index}.stdout.txt"
        stderr_path = HERE / "runs" / f"{stem}.attempt{index}.stderr.txt"
        instrument_started = time.perf_counter()
        stdout_path.write_text(result["stdout"])
        stderr_path.write_text(result["stderr"])
        instrument_seconds += time.perf_counter() - instrument_started
        check_started = time.perf_counter()
        if result["model"] is not None:
            decoded = verify_model(
                onb, curve, order, key_set, public, raw_points,
                raw_xs, leaves, selector, result["model"])
            relation = decoded[4]
            if relation is None and index + 1 < max_models:
                formula.clauses.append([
                    -bit if result["model"].get(bit, False) else bit
                    for row in leaves for bit in row] + [
                        -bit if result["model"].get(bit, False) else bit
                        for bit in selector])
        relation_check_seconds += time.perf_counter() - check_started
        instrument_started = time.perf_counter()
        compressed, formula_bytes, formula_sha = archive(formula_path)
        instrument_seconds += time.perf_counter() - instrument_started
        attempts.append({
            "index": index,
            "status": result["status"],
            "return_code": result["return_code"],
            "solver_wall_seconds": result["wall_seconds"],
            "solver_conflicts_reported": result["conflicts_reported"],
            "solver_command": result["command"],
            "solver_stdout_sha256": sha(stdout_path),
            "solver_stderr_sha256": sha(stderr_path),
            "xcnf_archive": compressed.name,
            "xcnf_sha256": formula_sha,
            "xcnf_bytes": formula_bytes,
            "formula_cnf_clauses": formula_clause_count,
            "decoded_choice": decoded[0] if decoded is not None else None,
            "decoded_raw_target_x": decoded[1] if decoded is not None else None,
            "lift_status": decoded[3] if decoded is not None else None,
            "verified_relation": relation,
            "four_distinct_columns": decoded[5] if decoded is not None else None,
        })
        if relation is not None or result["status"] != "sat":
            break
    target_total_seconds = time.perf_counter() - target_started - instrument_seconds
    target_pdp_seconds = target_total_seconds - target_preimage_seconds - relation_check_seconds
    parent_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if mode == "planted_locked":
        assert relation is not None and decoded is not None
        assert decoded[0] == raw_points.index(raw_sum)
        assert decoded[2] == raw_x

    receipt = {
        "kind": "q1404_raw_preimage_weight5_s3_stage_probe",
        "proposal_id": "Q1404", "candidate_id": None, "run_id": None,
        "mode": mode,
        "workload_id": baseline["workload_id"] if mode == "ordinary" else None,
        "curve_id": base["curve"]["curve_id"], "isogeny": "none",
        "public_target": list(public),
        "factor_base_actual_B": base["factor_base"][
            "actual_usable_points_B_before_folding"],
        "factor_base_folded_columns": base["factor_base"][
            "signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": base["factor_base"][
            "enumerated_set_sha256"],
        "raw_preimage_x_coordinates": raw_xs,
        "raw_preimage_count": len(raw_xs),
        "kernel_size": len(kernel),
        "kernel_generator_points": [list(point) for point in kernel_generators],
        "kernel_generation_trials": kernel_trials,
        "target_independent_kernel_setup_seconds_exploratory": (
            kernel_setup_seconds),
        "target_independent_base_load_excluded": True,
        "artifact_instrument_wall_seconds_excluded": instrument_seconds,
        "target_preimage_wall_seconds": (
            target_preimage_seconds if mode == "ordinary" else None),
        "target_pdp_wall_seconds": (
            target_pdp_seconds if mode == "ordinary" else None),
        "target_relation_check_wall_seconds": (
            relation_check_seconds if mode == "ordinary" else None),
        "target_dependent_stage_wall_seconds": (
            target_total_seconds if mode == "ordinary" else None),
        "control_stage_wall_seconds": (
            target_total_seconds if mode != "ordinary" else None),
        "formula_build_seconds": formula_build_seconds,
        "formula": formula_stats,
        "attempts": attempts,
        "status": attempts[-1]["status"] if attempts else "no_solver_budget",
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "natural_relation_yield_rate_estimate": None,
        "field_operations": None,
        "complete_solve_work_log2": None,
        "fixture": fixture,
        "max_seconds": max_seconds,
        "max_conflicts": max_conflicts,
        "max_models": max_models,
        "peak_parent_rss_raw": parent_rss,
        "peak_child_rss_raw": child_rss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "q1325_base_receipt_sha256": sha(base_path),
        "q1325_point_keys_sha256": sha(key_path),
        "ordinary_target_receipt_sha256": sha(baseline_path),
        "ordinary_coset_receipt_sha256": (
            sha(HERE / "runs/n83_ordinary_raw_preimages.json")
            if mode == "ordinary" else None),
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "solver_binary_sha256": sha(binary),
        "source_sha256": {source: sha(ROOT / source)
                          for source in SOURCE_PATHS},
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({
        "mode": mode, "status": receipt["status"],
        "verified_relation": relation is not None,
        "target_stage_seconds": target_total_seconds,
        "formula": formula_stats,
    }))


if __name__ == "__main__":
    main()
