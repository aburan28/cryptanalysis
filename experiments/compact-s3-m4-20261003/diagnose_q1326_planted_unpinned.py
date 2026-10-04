#!/usr/bin/env python3
"""Unpinned S3 search on a known-satisfiable Q1326 K64 target."""

from __future__ import annotations

import json
import resource
import shutil
import time
from pathlib import Path

from chain_s3_base_orbit import build_base_orbit_chain, decode_base_choice
from run_group_add_probe import archive, solve, stats
from run_probe import HERE, curves, field, lift, sha
from run_q1326_nested_base_probe import inputs, selected_keys


def main():
    stem = "n53_q1326_planted_unpinned"
    receipt_path = HERE / "runs" / f"{stem}.json"
    xcnf_path = HERE / "runs" / f"{stem}.xcnf"
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in (
        receipt_path, xcnf_path, xcnf_path.with_suffix(".xcnf.gz"),
        stdout_path, stderr_path))
    protocol_path = HERE / "q1326_protocol.json"
    runtime_path = HERE / "q1326_sage_runtime_info.json"
    control_path = HERE / "runs/n53_q1326_planted_locked.json"
    protocol = json.loads(protocol_path.read_text())
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    control = json.loads(control_path.read_text())
    _, baseline, _, base, all_keys, stages = inputs()
    assert protocol["search_restrictions"] == stages
    stage = stages[0]
    assert stage["stage"] == "k64"
    keys = selected_keys(all_keys, stage)
    assert control["eligible_set_sha256"] == stage["eligible_set_sha256"]
    target = tuple(map(int, control["public_target"]))
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    r = int(base["curve"]["subgroup_order"])
    assert curve.onCurve(target) and curve.mul(target, r) is None
    assert control["control"]["relation"] is not None
    cap = 60

    started = time.perf_counter()
    formula, leaves, _, choices = build_base_orbit_chain(
        53, keys, onb.toCoords(target[0]), ordered_leaves=True)
    formula_stats = stats(formula)
    formula.write(xcnf_path)
    build_seconds = time.perf_counter() - started
    binary = Path(shutil.which("cryptominisat5"))
    result = solve(xcnf_path, binary, cap - build_seconds, 1_000_000)
    pdp_seconds = time.perf_counter() - started
    stdout_path.write_text(result["stdout"])
    stderr_path.write_text(result["stderr"])
    relation = None
    decoded = None
    lift_status = None
    check_started = time.perf_counter()
    if result["model"] is not None:
        decoded = [decode_base_choice(choice, result["model"])
                   for choice in choices]
        assert decoded == sorted(decoded)
        leaf_x, relation, lift_status = lift(
            onb, curve, leaves, result["model"], target, target, 1)
        for x, (index, shift) in zip(leaf_x, decoded):
            assert index < len(keys) and shift < 53
            assert x == onb.toCoords(onb.frob(
                onb.fromCoords(keys[index]), shift))
            point = curve.pointFromX(onb.fromCoords(x))
            assert point is not None and curve.mul(point, r) is None
    check_seconds = time.perf_counter() - check_started
    compressed, size, digest = archive(xcnf_path)
    receipt = {
        "kind": "known_satisfiable_nested_n53_base_unpinned_s3_probe",
        "proposal_id": "Q1326", "candidate_id": None, "run_id": None,
        "workload_id": None, "planted_target": True,
        "oracle_assisted_solver": False,
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "public_target": list(target),
        "eligible_actual_B_before_folding": stage[
            "eligible_actual_B_before_folding"],
        "eligible_folded_columns": stage["eligible_folded_columns"],
        "eligible_set_sha256": stage["eligible_set_sha256"],
        "formula": formula_stats,
        "status": result["status"],
        "return_code": result["return_code"],
        "solver_conflicts_reported": result["conflicts_reported"],
        "formula_build_and_write_seconds": build_seconds,
        "solver_wall_seconds": result["wall_seconds"],
        "target_pdp_wall_seconds": pdp_seconds,
        "target_relation_check_wall_seconds": check_seconds,
        "target_pdp_wall_cap_seconds": cap,
        "xcnf_archive": compressed.name,
        "xcnf_sha256": digest,
        "xcnf_bytes": size,
        "solver_command": result["command"],
        "solver_binary_sha256": sha(binary),
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "chosen_orbit_choices": decoded,
        "lift_status": lift_status,
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "field_operations": None,
        "complete_solve_work_log2": None,
        "peak_parent_rss_raw": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "peak_child_rss_raw_cumulative": resource.getrusage(
            resource.RUSAGE_CHILDREN).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "planted_control_receipt_sha256": sha(control_path),
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "runner_source_sha256": sha(Path(__file__)),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "verified_relation": relation is not None,
                      "target_pdp_wall_seconds": pdp_seconds}))


if __name__ == "__main__":
    main()
