#!/usr/bin/env python3
"""Q1409: balanced S3 on Q1301's exact N53 factor base and target."""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import resource
import shutil
import sys
import time
from pathlib import Path

from chain_s3_balanced_multitarget import build_balanced
from chain_s3_multitarget import decode_choice
from cofactor_preimages import kernel_of_cofactor
from run_group_add_probe import archive, solve, stats
from run_probe import HERE, ROOT, curves, field, lift, sha

sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402

SOURCE_PATHS = (
    "ecc2k130/codegen/field.py",
    "ecc2k130/codegen/curves.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
    "experiments/compact-s3-m4-20261003/chain_s3.py",
    "experiments/compact-s3-m4-20261003/chain_s3_factored.py",
    "experiments/compact-s3-m4-20261003/chain_s3_multitarget.py",
    "experiments/compact-s3-m4-20261003/chain_s3_balanced_multitarget.py",
    "experiments/compact-s3-m4-20261003/cofactor_preimages.py",
    "experiments/compact-s3-m4-20261003/run_group_add_probe.py",
    "experiments/compact-s3-m4-20261003/run_probe.py",
    "experiments/compact-s3-m4-20261003/run_q1409_balanced_s3_n53.py",
)


def base_keys(base):
    packed = base64.b64decode(base["factor_base"]["packed_canonical_x_keys_base64"],
                              validate=True)
    assert len(packed) == 7 * base["factor_base"]["signed_frobenius_columns"]
    keys = [int.from_bytes(packed[i:i + 7], "little")
            for i in range(0, len(packed), 7)]
    assert keys == sorted(set(keys))
    return keys


def preimage_coset(onb, curve, order, cofactor, public, kernel):
    base = curve.mul(public, pow(cofactor, -1, order))
    assert base is not None and curve.mul(base, cofactor) == public
    points = {curve.add(base, torsion) for torsion in kernel}
    assert len(points) == cofactor and None not in points
    assert all(curve.mul(point, cofactor) == public for point in points)
    ordered = sorted(points, key=lambda point: (
        onb.toCoords(point[0]), onb.toCoords(point[1])))
    xs = [onb.toCoords(point[0]) for point in ordered]
    assert len(set(xs)) == cofactor
    return ordered, xs


def pin_bits(formula, bits, value):
    formula.clauses.extend([[bit if value >> position & 1 else -bit]
                            for position, bit in enumerate(bits)])


def verify_model(onb, curve, order, cofactor, keys, public, raw_points,
                 raw_xs, leaves, selector, model):
    choice = decode_choice(selector, model)
    assert 0 <= choice < len(raw_points)
    coordinates, relation, status = lift(
        onb, curve, leaves, model, raw_points[choice], public, cofactor)
    assert all(0 < value < (1 << 53) and value.bit_count() <= 3
               for value in coordinates)
    distinct = None
    if relation is not None:
        orbit = OrbitKey(onb)
        columns = []
        for values in relation["projected_points"]:
            point = tuple(map(int, values))
            assert curve.onCurve(point) and curve.mul(point, order) is None
            column = orbit.canonical(point)[0]
            assert column in keys
            columns.append(column)
        distinct = len(set(columns)) == 4
        assert relation["public_target"] == [str(value) for value in public]
    return choice, raw_xs[choice], coordinates, status, relation, distinct


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=(
        "ordinary", "planted_unpinned", "planted_locked"), required=True)
    mode = parser.parse_args().mode
    kind = "ordinary" if mode == "ordinary" else "planted"
    stem = f"n53_q1409_{mode}"
    output = HERE / "runs" / f"{stem}.json"
    initial_formula = HERE / "runs" / f"{stem}.xcnf"
    assert not output.exists() and not initial_formula.exists()
    assert not initial_formula.with_suffix(".xcnf.gz").exists()
    protocol_path = HERE / "q1409_balanced_s3_n53_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q1409"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    for source in SOURCE_PATHS:
        assert protocol["source_sha256"][source] == sha(ROOT / source)
    runtime_path = HERE / "q1409_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    base_path = HERE / "bases/n53_weight3_orbits.json.gz"
    with gzip.open(base_path, "rt") as stream:
        base = json.load(stream)
    baseline_path = HERE / "runs" / f"n53_{kind}_frozen.json"
    baseline = json.loads(baseline_path.read_text())
    coset_path = HERE / "runs" / f"n53_{kind}_raw_preimages.json"
    expected_coset = json.loads(coset_path.read_text())
    assert protocol["base_archive_sha256"] == sha(base_path)
    assert protocol[f"{kind}_baseline_sha256"] == sha(baseline_path)
    assert protocol[f"{kind}_coset_sha256"] == sha(coset_path)
    assert protocol["curve_id"] == base["curve"]["curve_id"] == baseline[
        "curve_id"] == expected_coset["curve_id"]
    fb = base["factor_base"]
    assert protocol["factor_base_actual_B"] == fb[
        "actual_usable_points_B_before_folding"]
    assert protocol["factor_base_folded_columns"] == fb[
        "signed_frobenius_columns"]
    assert protocol["factor_base_enumerated_set_sha256"] == fb[
        "enumerated_set_sha256"]
    assert protocol[f"{kind}_workload_id"] == baseline["workload_id"]
    keys = set(base_keys(base))
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    order = int(base["curve"]["subgroup_order"])
    cofactor = int(base["curve"]["cofactor"])
    assert cofactor == 428
    binary = Path(shutil.which("cryptominisat5"))
    kernel_started = time.perf_counter()
    kernel, kernel_generators, kernel_trials = kernel_of_cofactor(
        curve, onb, order, cofactor, protocol["kernel_seed"])
    kernel_setup_seconds = time.perf_counter() - kernel_started
    public = tuple(map(int, baseline["public_subgroup_target"]))
    assert curve.onCurve(public) and curve.mul(public, order) is None
    fixture = None
    if kind == "planted":
        raw_x = baseline["fixture"]["planted_leaf_x"]
        fixture_points = [curve.pointFromX(onb.fromCoords(value))
                          for value in raw_x]
        assert all(point is not None for point in fixture_points)
        pair_sums = (curve.add(fixture_points[0], fixture_points[1]),
                     curve.add(fixture_points[2], fixture_points[3]))
        assert all(point is not None for point in pair_sums)
        raw_sum = curve.add(*pair_sums)
        assert raw_sum == tuple(map(int, baseline["raw_target"]))
        assert curve.mul(raw_sum, cofactor) == public
        fixture = {"raw_leaf_x": raw_x,
                   "raw_leaf_points": [list(point) for point in fixture_points],
                   "raw_pair_sum_points": [list(point) for point in pair_sums],
                   "raw_sum": list(raw_sum)}
    max_seconds = protocol["limits_seconds"][mode]
    max_conflicts = protocol["max_conflicts"]
    max_models = protocol["max_models"]
    target_started = time.perf_counter()
    raw_points, raw_xs = preimage_coset(
        onb, curve, order, cofactor, public, kernel)
    target_preimage_seconds = time.perf_counter() - target_started
    assert raw_xs == expected_coset["raw_target_x_coordinates"]
    assert [list(point) for point in raw_points] == [
        [int(value) for value in point]
        for point in expected_coset["raw_target_points"]]
    if kind == "planted":
        assert raw_sum in raw_points
    formula_started = time.perf_counter()
    formula, leaves, mids, _, selector = build_balanced(53, 3, raw_xs)
    if mode == "planted_locked":
        for bits, value in zip(leaves, raw_x):
            pin_bits(formula, bits, value)
        for bits, point in zip(mids, pair_sums):
            pin_bits(formula, bits, onb.toCoords(point[0]))
        pin_bits(formula, selector, raw_points.index(raw_sum))
    formula_build_seconds = time.perf_counter() - formula_started
    formula_stats = stats(formula)
    attempts = []
    relation = decoded = None
    relation_check_seconds = instrument_seconds = 0.0
    deadline = target_started + max_seconds
    for index in range(max_models):
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        formula_path = (initial_formula if index == 0 else HERE / "runs" /
                        f"{stem}.attempt{index}.xcnf")
        assert not formula_path.exists()
        clause_count = len(formula.clauses)
        formula.write(formula_path)
        remaining = deadline - time.perf_counter()
        result = (solve(formula_path, binary, remaining, max_conflicts)
                  if remaining > 0 else {
                      "command": None, "status": "no_solver_budget",
                      "return_code": None, "wall_seconds": 0.0,
                      "conflicts_reported": None, "stdout": "", "stderr": "",
                      "model": None})
        stdout_path = HERE / "runs" / f"{stem}.attempt{index}.stdout.txt"
        stderr_path = HERE / "runs" / f"{stem}.attempt{index}.stderr.txt"
        began = time.perf_counter()
        stdout_path.write_text(result["stdout"])
        stderr_path.write_text(result["stderr"])
        instrument_seconds += time.perf_counter() - began
        began = time.perf_counter()
        if result["model"] is not None:
            decoded = verify_model(
                onb, curve, order, cofactor, keys, public, raw_points,
                raw_xs, leaves, selector, result["model"])
            relation = decoded[4]
            if relation is None and index + 1 < max_models:
                formula.clauses.append([
                    -bit if result["model"].get(bit, False) else bit
                    for row in leaves for bit in row] + [
                        -bit if result["model"].get(bit, False) else bit
                        for bit in selector])
        relation_check_seconds += time.perf_counter() - began
        began = time.perf_counter()
        compressed, formula_bytes, formula_sha = archive(formula_path)
        instrument_seconds += time.perf_counter() - began
        attempts.append({
            "index": index, "status": result["status"],
            "return_code": result["return_code"],
            "solver_wall_seconds": result["wall_seconds"],
            "solver_conflicts_reported": result["conflicts_reported"],
            "solver_command": result["command"],
            "solver_stdout_sha256": sha(stdout_path),
            "solver_stderr_sha256": sha(stderr_path),
            "xcnf_archive": compressed.name,
            "xcnf_sha256": formula_sha,
            "xcnf_bytes": formula_bytes,
            "formula_cnf_clauses": clause_count,
            "decoded_choice": decoded[0] if decoded else None,
            "decoded_raw_target_x": decoded[1] if decoded else None,
            "lift_status": decoded[3] if decoded else None,
            "verified_relation": relation,
            "four_distinct_columns": decoded[5] if decoded else None,
        })
        if relation is not None or result["status"] != "sat":
            break
    target_total_seconds = time.perf_counter() - target_started - instrument_seconds
    target_pdp_seconds = (target_total_seconds - target_preimage_seconds
                          - relation_check_seconds)
    if mode == "planted_locked":
        assert relation is not None and decoded is not None
        assert decoded[0] == raw_points.index(raw_sum)
        assert decoded[2] == raw_x
    receipt = {
        "kind": "q1409_balanced_n53_s3_stage_probe",
        "proposal_id": "Q1409", "candidate_id": None, "run_id": None,
        "mode": mode,
        "workload_id": baseline["workload_id"] if kind == "ordinary" else None,
        "curve_id": base["curve"]["curve_id"], "isogeny": "none",
        "public_target": list(public),
        "factor_base_actual_B": fb["actual_usable_points_B_before_folding"],
        "factor_base_folded_columns": fb["signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": fb["enumerated_set_sha256"],
        "raw_preimage_x_coordinates": raw_xs,
        "raw_preimage_count": len(raw_xs),
        "kernel_size": len(kernel),
        "kernel_generator_points": [list(point) for point in kernel_generators],
        "kernel_generation_trials": kernel_trials,
        "target_independent_kernel_setup_seconds_exploratory": kernel_setup_seconds,
        "artifact_instrument_wall_seconds_excluded": instrument_seconds,
        "target_preimage_wall_seconds": target_preimage_seconds if kind == "ordinary" else None,
        "target_pdp_wall_seconds": target_pdp_seconds if kind == "ordinary" else None,
        "target_relation_check_wall_seconds": relation_check_seconds if kind == "ordinary" else None,
        "target_dependent_stage_wall_seconds": target_total_seconds if kind == "ordinary" else None,
        "control_stage_wall_seconds": target_total_seconds if kind == "planted" else None,
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
        "peak_parent_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_child_rss_raw": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "base_archive_sha256": sha(base_path),
        "baseline_sha256": sha(baseline_path),
        "coset_sha256": sha(coset_path),
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "solver_binary_sha256": sha(binary),
        "source_sha256": {source: sha(ROOT / source) for source in SOURCE_PATHS},
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"mode": mode, "status": receipt["status"],
                      "verified_relation": relation is not None,
                      "target_stage_seconds": target_total_seconds,
                      "formula": formula_stats}))


if __name__ == "__main__":
    main()
