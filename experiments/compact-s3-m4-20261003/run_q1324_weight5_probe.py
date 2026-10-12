#!/usr/bin/env python3
"""Measure Q1324 four-summand SAT on the exact Q1041 n83 base."""

from __future__ import annotations

import argparse
import json
import resource
import shutil
import time
from pathlib import Path

from chain_s3_base_orbit import build_base_orbit_chain, decode_base_choice
from q1324_inputs import read_inputs
from run_group_add_probe import archive, solve, stats
from run_probe import HERE, curves, field, lift, sha


def pin_bits(formula, variables, value):
    formula.clauses.extend(([bit if value >> i & 1 else -bit]
                            for i, bit in enumerate(variables)))


def planted_fixture(onb, curve, xkeys, config, order):
    choices = list(zip(config["representative_indices"],
                       config["frobenius_shifts"]))
    assert choices == sorted(choices)
    points = []
    for (index, shift), sign in zip(choices, config["signs"]):
        point = curve.pointFromX(onb.fromCoords(xkeys[index]))
        assert point is not None and curve.mul(point, order) is None
        point = curve.frob(point, shift)
        points.append(point if sign == 1 else curve.neg(point))
    first = curve.add(points[0], points[1])
    second = curve.add(first, points[2])
    target = curve.add(second, points[3])
    assert first is not None and second is not None and target is not None
    assert curve.mul(target, order) is None
    return choices, points, (first, second), target


def verify_model(onb, curve, order, xkeys, target, leaves, choices, model):
    selected = [decode_base_choice(choice, model) for choice in choices]
    assert selected == sorted(selected)
    assert all(0 <= index < len(xkeys) and 0 <= shift < 83
               for index, shift in selected)
    leaf_x, relation, status = lift(
        onb, curve, leaves, model, target, target, 1)
    for x, (index, shift) in zip(leaf_x, selected):
        expected = onb.toCoords(onb.frob(
            onb.fromCoords(xkeys[index]), shift))
        assert x == expected
        point = curve.pointFromX(onb.fromCoords(x))
        assert point is not None and curve.mul(point, order) is None
    if relation is not None:
        assert status == "verified_four_point_relation"
        assert relation["public_target"] == [str(value) for value in target]
    return selected, leaf_x, status, relation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("ordinary", "planted_locked"),
                        required=True)
    args = parser.parse_args()
    mode = args.mode
    stem = f"n83_q1324_{mode}"
    output = HERE / "runs" / f"{stem}.json"
    formula_path = HERE / "runs" / f"{stem}.xcnf"
    archive_path = formula_path.with_suffix(".xcnf.gz")
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in (
        output, formula_path, archive_path, stdout_path, stderr_path))
    runtime_path = HERE / "q1324_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"

    protocol_path = HERE / "q1324_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    (base_path, base, point_key_path, baseline_path, baseline, xkeys,
     x_digest) = read_inputs()
    assert protocol["proposal_id"] == "Q1324"
    assert protocol["candidate_id"] is None
    assert protocol["factor_base"]["derived_representative_x_sha256"] == x_digest
    assert protocol["factor_base"]["enumerated_set_sha256"] == base[
        "factor_base"]["enumerated_set_sha256"]
    assert protocol["factor_base"]["base_receipt_sha256"] == sha(base_path)
    assert protocol["factor_base"]["point_key_file_sha256"] == sha(
        point_key_path)
    assert protocol["ordinary_target_receipt_sha256"] == sha(baseline_path)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(base["curve_identity_record"]["curve"]["subgroup_order"])
    binary = Path(shutil.which("cryptominisat5"))
    fixture = None
    if mode == "ordinary":
        target = tuple(map(int, baseline["public_subgroup_target"]))
    else:
        selected, points, mids, target = planted_fixture(
            onb, curve, xkeys, protocol["planted_control"], order)
        fixture = {"selected_orbit_choices": selected,
                   "leaf_points": [list(point) for point in points],
                   "intermediate_points": [list(point) for point in mids]}
    assert curve.onCurve(target) and curve.mul(target, order) is None
    assert mode != "ordinary" or list(target) == list(map(
        int, protocol["ordinary_public_target"]))

    max_seconds = protocol["point_decomposition"][
        "ordinary_wall_limit_seconds" if mode == "ordinary" else
        "planted_locked_wall_limit_seconds"]
    max_conflicts = protocol["point_decomposition"]["max_conflicts"]
    started = time.perf_counter()
    formula, leaves, mid_variables, choices = build_base_orbit_chain(
        83, xkeys, onb.toCoords(target[0]), ordered_leaves=True)
    if fixture is not None:
        for choice, (index, shift) in zip(choices, selected):
            pin_bits(formula, choice[0], index)
            pin_bits(formula, choice[1], shift)
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
    decoded = leaf_x = lift_status = relation = None
    if result["model"] is not None:
        decoded, leaf_x, lift_status, relation = verify_model(
            onb, curve, order, xkeys, target, leaves, choices,
            result["model"])
    if mode == "planted_locked":
        assert relation is not None and decoded == selected
        assert relation["public_target"] == [str(value) for value in target]
    compressed, formula_bytes, formula_sha = archive(formula_path)
    receipt = {
        "kind": "q1324_exact_weight5_four_summand_s3_stage_probe",
        "proposal_id": "Q1324", "candidate_id": None, "run_id": None,
        "workload_id": baseline["workload_id"] if mode == "ordinary" else None,
        "mode": mode, "oracle_assisted": mode == "planted_locked",
        "curve_id": base["curve_id"], "isogeny": "none",
        "public_target": list(target),
        "factor_base_actual_B": base["factor_base"][
            "actual_usable_points_B_before_folding"],
        "factor_base_folded_columns": len(xkeys),
        "factor_base_enumerated_set_sha256": base["factor_base"][
            "enumerated_set_sha256"],
        "derived_representative_x_sha256": x_digest,
        "base_receipt_sha256": sha(base_path),
        "base_point_key_file_sha256": sha(point_key_path),
        "target_independent_base_load_excluded": True,
        "formula_build_seconds": build_seconds,
        "target_pdp_wall_seconds": (charged_seconds if mode == "ordinary"
                                    else None),
        "oracle_control_wall_seconds": (charged_seconds if fixture is not None
                                        else None),
        "solver_wall_seconds": result["wall_seconds"],
        "status": result["status"],
        "return_code": result["return_code"],
        "solver_conflicts_reported": result["conflicts_reported"],
        "formula": formula_stats,
        "xcnf_archive": compressed.name,
        "xcnf_sha256": formula_sha,
        "xcnf_bytes": formula_bytes,
        "chosen_orbit_choices": decoded,
        "leaf_x_coordinates": leaf_x,
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
        "base_selector_source_sha256": sha(HERE / "chain_s3_base_orbit.py"),
        "runner_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"mode": mode, "status": result["status"],
                      "verified_relation": relation is not None,
                      "formula": formula_stats,
                      "charged_seconds": charged_seconds}))


if __name__ == "__main__":
    main()
