#!/usr/bin/env python3
"""Probe nested exact n53 sub-bases with the compact four-leaf S3 chain.

The subset order, sizes, and caps are frozen before the ordinary solve. A
subset is only a search restriction: every point remains in Q1301's parent
base. All failed attempts are charged to the same frozen public target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import resource
import shutil
import time
from pathlib import Path

from chain_s3_base_orbit import build_base_orbit_chain, decode_base_choice
from run_base_orbit_probe import lock_control, read_inputs
from run_group_add_probe import archive, solve, stats
from run_probe import HERE, curves, field, lift, sha

PROPOSAL = "Q1326"
SEED = 530326
SCHEDULE = ((64, 30), (96, 60), (128, 90))
MAX_CONFLICTS = 1_000_000


def packed_digest(keys):
    return hashlib.sha256(b"".join(key.to_bytes(7, "little")
                                   for key in keys)).hexdigest()


def inputs():
    baseline_path, baseline, base_path, base, all_keys = read_inputs(
        53, "ordinary")
    assert base["proposal_id"] == "Q1301"
    assert base["candidate_id"] is None and base["isogeny"] == "none"
    assert baseline["workload_id"] == "74f2979b3e68"
    lengths = base["factor_base"]["orbit_lengths"]
    assert len(all_keys) == len(lengths) == 227
    order = list(range(len(all_keys)))
    random.Random(SEED).shuffle(order)
    stages = []
    for count, cap in SCHEDULE:
        indices = sorted(order[:count])
        keys = [all_keys[index] for index in indices]
        usable_b = 2 * sum(lengths[index] for index in indices)
        stages.append({
            "stage": f"k{count}", "selection_seed": SEED,
            "selection_rule": "prefix of seeded shuffled parent orbit indices",
            "parent_orbit_indices": indices,
            "eligible_actual_B_before_folding": usable_b,
            "eligible_folded_columns": count,
            "eligible_set_sha256": packed_digest(keys),
            "uniform_target_mean_distinct_four_subsets_exact": {
                "numerator": math.comb(usable_b, 4),
                "denominator": base["curve"]["subgroup_order"],
            },
            "target_pdp_wall_cap_seconds": cap,
        })
    return (baseline_path, baseline, base_path, base, all_keys, stages)


def frozen_protocol():
    baseline_path, baseline, base_path, base, _, stages = inputs()
    return {
        "kind": "nested_exact_n53_base_compact_s3_stage_protocol",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "field": base["field"], "curve": base["curve"],
        "isogeny": "none",
        "parent_factor_base": {
            "proposal_id": "Q1301",
            "actual_usable_points_B_before_folding": base[
                "factor_base"]["actual_usable_points_B_before_folding"],
            "signed_frobenius_columns": base[
                "factor_base"]["signed_frobenius_columns"],
            "enumerated_set_sha256": base[
                "factor_base"]["enumerated_set_sha256"],
            "archive_sha256": sha(base_path),
        },
        "search_restrictions": stages,
        "point_decomposition": {
            "m": 4,
            "summation_chain": "three compact S3 links with two free intermediate x coordinates",
            "leaf_choice": "one nested eligible signed-Frobenius orbit subset per attempt, then exact orbit and shift selector",
            "ordered_leaves": True,
            "solver": "cryptominisat5 native XOR, one thread",
            "max_conflicts_per_attempt": MAX_CONFLICTS,
            "stop": "first independently verified public-target relation, else preserve all censored attempts",
        },
        "ordinary_workload_id": baseline["workload_id"],
        "ordinary_public_target": baseline["public_subgroup_target"],
        "ordinary_target_receipt_sha256": sha(baseline_path),
        "relation_collection": None,
        "relation_linear_algebra": None,
        "target_descent": None,
        "complete_solve_cost_log2": None,
    }


def selected_keys(all_keys, stage):
    keys = [all_keys[index] for index in stage["parent_orbit_indices"]]
    assert len(keys) == stage["eligible_folded_columns"]
    assert packed_digest(keys) == stage["eligible_set_sha256"]
    return keys


def write_protocol(check):
    path = HERE / "q1326_protocol.json"
    data = json.dumps(frozen_protocol(), indent=2, sort_keys=True) + "\n"
    if check:
        assert path.read_text() == data
    else:
        assert not path.exists()
        path.write_text(data)
    print(json.dumps({"proposal_id": PROPOSAL,
                      "protocol_sha256": sha(path),
                      "eligible_B": [stage[
                          "eligible_actual_B_before_folding"]
                          for stage in frozen_protocol()[
                              "search_restrictions"]]}))


def read_frozen():
    protocol_path = HERE / "q1326_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol == frozen_protocol()
    runtime_path = HERE / "q1326_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    return protocol_path, protocol, runtime_path


def planted_control():
    protocol_path, protocol, runtime_path = read_frozen()
    output = HERE / "runs/n53_q1326_planted_locked.json"
    assert not output.exists()
    _, baseline, _, base, all_keys, stages = inputs()
    stage = stages[0]
    keys = selected_keys(all_keys, stage)
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    points = [curve.pointFromX(onb.fromCoords(key)) for key in keys[:4]]
    assert all(point is not None and curve.mul(point, base["curve"][
        "subgroup_order"]) is None for point in points)
    target = None
    for point in points:
        target = curve.add(target, point)
    assert target is not None
    formula, leaves, mids, choices = build_base_orbit_chain(
        53, keys, onb.toCoords(target[0]), ordered_leaves=True)
    started = time.perf_counter()
    result = lock_control(formula, leaves, mids, choices, keys, onb, curve,
                          target, protocol_path, points)
    receipt = {
        "kind": "nested_exact_n53_base_planted_encoding_control",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "workload_id": None, "oracle_assisted": True,
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "eligible_actual_B_before_folding": stage[
            "eligible_actual_B_before_folding"],
        "eligible_folded_columns": stage["eligible_folded_columns"],
        "eligible_set_sha256": stage["eligible_set_sha256"],
        "public_target": [int(value) for value in target],
        "status": result["status"],
        "oracle_control_wall_seconds": time.perf_counter() - started,
        "formula": stats(formula),
        "control": result,
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "runner_source_sha256": sha(Path(__file__)),
        "base_chain_source_sha256": sha(
            HERE / "chain_s3_base_orbit.py"),
        "complete_solve_work_log2": None,
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "oracle_control_wall_seconds": receipt[
                          "oracle_control_wall_seconds"]}))


def ordinary_search():
    protocol_path, protocol, runtime_path = read_frozen()
    output = HERE / "runs/n53_q1326_ordinary_summary.json"
    assert not output.exists()
    baseline_path, baseline, base_path, base, all_keys, stages = inputs()
    target = tuple(map(int, baseline["public_subgroup_target"]))
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    subgroup_order = int(base["curve"]["subgroup_order"])
    assert curve.onCurve(target) and curve.mul(target, subgroup_order) is None
    binary = Path(shutil.which("cryptominisat5"))
    rows = []
    total_pdp_seconds = total_check_seconds = 0.0
    verified = None
    for stage in stages:
        stem = f"n53_q1326_ordinary_{stage['stage']}"
        receipt_path = HERE / "runs" / f"{stem}.json"
        xcnf_path = HERE / "runs" / f"{stem}.xcnf"
        stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
        stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
        assert not any(path.exists() for path in (
            receipt_path, xcnf_path, xcnf_path.with_suffix(".xcnf.gz"),
            stdout_path, stderr_path))
        keys = selected_keys(all_keys, stage)
        started = time.perf_counter()
        formula, leaves, mids, choices = build_base_orbit_chain(
            53, keys, onb.toCoords(target[0]), ordered_leaves=True)
        formula_stats = stats(formula)
        formula.write(xcnf_path)
        formula_seconds = time.perf_counter() - started
        remaining = stage["target_pdp_wall_cap_seconds"] - formula_seconds
        result = solve(xcnf_path, binary, remaining, MAX_CONFLICTS)
        pdp_seconds = time.perf_counter() - started
        stdout_path.write_text(result["stdout"])
        stderr_path.write_text(result["stderr"])
        relation = None
        lift_status = None
        choices_decoded = None
        check_started = time.perf_counter()
        if result["model"] is not None:
            choices_decoded = [decode_base_choice(choice, result["model"])
                               for choice in choices]
            assert choices_decoded == sorted(choices_decoded)
            leaf_x, relation, lift_status = lift(
                onb, curve, leaves, result["model"], target, target, 1)
            for x, (index, shift) in zip(leaf_x, choices_decoded):
                assert index < len(keys) and shift < 53
                assert x == onb.toCoords(onb.frob(
                    onb.fromCoords(keys[index]), shift))
                point = curve.pointFromX(onb.fromCoords(x))
                assert point is not None
                assert curve.mul(point, subgroup_order) is None
        check_seconds = time.perf_counter() - check_started
        compressed, formula_bytes, formula_sha = archive(xcnf_path)
        receipt = {
            "kind": "nested_exact_n53_base_compact_s3_stage_attempt",
            "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
            "workload_id": baseline["workload_id"],
            "curve_id": baseline["curve_id"], "isogeny": "none",
            "oracle_assisted": False, "stage": stage["stage"],
            "public_target": list(target),
            "parent_base_actual_B": base["factor_base"][
                "actual_usable_points_B_before_folding"],
            "parent_base_folded_columns": len(all_keys),
            "parent_base_enumerated_set_sha256": base[
                "factor_base"]["enumerated_set_sha256"],
            "eligible_actual_B_before_folding": stage[
                "eligible_actual_B_before_folding"],
            "eligible_folded_columns": stage["eligible_folded_columns"],
            "eligible_set_sha256": stage["eligible_set_sha256"],
            "uniform_target_mean_distinct_four_subsets_exact": stage[
                "uniform_target_mean_distinct_four_subsets_exact"],
            "status": result["status"],
            "return_code": result["return_code"],
            "solver_conflicts_reported": result["conflicts_reported"],
            "formula": formula_stats,
            "formula_build_and_write_seconds": formula_seconds,
            "solver_wall_seconds": result["wall_seconds"],
            "target_pdp_wall_seconds": pdp_seconds,
            "target_relation_check_wall_seconds": check_seconds,
            "target_pdp_wall_cap_seconds": stage[
                "target_pdp_wall_cap_seconds"],
            "xcnf_archive": compressed.name,
            "xcnf_sha256": formula_sha,
            "xcnf_bytes": formula_bytes,
            "solver_command": result["command"],
            "solver_binary_sha256": sha(binary),
            "solver_stdout_sha256": sha(stdout_path),
            "solver_stderr_sha256": sha(stderr_path),
            "chosen_orbit_choices": choices_decoded,
            "lift_status": lift_status,
            "verified_relation": relation,
            "observed_verified_relation_count": int(relation is not None),
            "natural_relation_yield_estimate": None,
            "field_operations": None,
            "complete_solve_work_log2": None,
            "peak_parent_rss_raw": resource.getrusage(
                resource.RUSAGE_SELF).ru_maxrss,
            "peak_child_rss_raw_cumulative": resource.getrusage(
                resource.RUSAGE_CHILDREN).ru_maxrss,
            "peak_rss_units": "bytes on Darwin, KiB on Linux",
            "protocol_sha256": sha(protocol_path),
            "runtime_info_sha256": sha(runtime_path),
            "ordinary_target_receipt_sha256": sha(baseline_path),
            "parent_base_archive_sha256": sha(base_path),
            "runner_source_sha256": sha(Path(__file__)),
            "base_chain_source_sha256": sha(
                HERE / "chain_s3_base_orbit.py"),
        }
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        total_pdp_seconds += pdp_seconds
        total_check_seconds += check_seconds
        rows.append({"stage": stage["stage"],
                     "receipt_sha256": sha(receipt_path),
                     "status": result["status"],
                     "verified_relation_count": int(relation is not None),
                     "target_pdp_wall_seconds": pdp_seconds,
                     "target_relation_check_wall_seconds": check_seconds})
        print(json.dumps({"stage": stage["stage"],
                          "status": result["status"],
                          "verified_relation_count": int(relation is not None),
                          "target_pdp_wall_seconds": pdp_seconds}),
              flush=True)
        if relation is not None:
            verified = stage["stage"]
            break
    summary = {
        "kind": "nested_exact_n53_base_compact_s3_ordinary_search",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "workload_id": baseline["workload_id"],
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "oracle_assisted": False, "public_target": list(target),
        "stage_attempts": rows,
        "status": "verified_four_point_relation" if verified else "censored",
        "verified_stage": verified,
        "total_target_pdp_wall_seconds": total_pdp_seconds,
        "total_target_relation_check_wall_seconds": total_check_seconds,
        "observed_verified_relation_count": int(verified is not None),
        "field_operations": None, "natural_relation_yield_estimate": None,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "runner_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"status": summary["status"],
                      "attempts": len(rows),
                      "charged_pdp_seconds": total_pdp_seconds}))


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--planted", action="store_true")
    group.add_argument("--ordinary", action="store_true")
    args = parser.parse_args()
    if args.freeze or args.check:
        write_protocol(args.check)
    elif args.planted:
        planted_control()
    else:
        ordinary_search()


if __name__ == "__main__":
    main()
