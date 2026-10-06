#!/usr/bin/env python3
"""Post-run pair-table check for the last Q1326 restricted search space.

This diagnostic runs only after the frozen compact-S3 attempts. A pair-table
witness proves that a restricted target is satisfiable; its work is not
credited to the compact-S3 solver.
"""

from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path

from run_q1326_nested_base_probe import inputs, packed_digest, selected_keys
from run_probe import HERE, ROOT, curves, field, sha

PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PAIR))
from orbit_key import OrbitKey  # noqa: E402
from probe_n53_relation import base_and_columns  # noqa: E402
from probe_n53_table import search  # noqa: E402


def main():
    out = HERE / "runs/n53_q1326_k128_support_diagnostic.json"
    assert not out.exists()
    protocol_path = HERE / "q1326_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    runtime_path = HERE / "q1326_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    baseline_path, baseline, base_path, base, all_keys, stages = inputs()
    assert protocol["search_restrictions"] == stages
    assert protocol["ordinary_target_receipt_sha256"] == sha(baseline_path)
    stage = stages[-1]
    assert stage["stage"] == "k128"
    keys = selected_keys(all_keys, stage)
    assert packed_digest(keys) == stage["eligible_set_sha256"]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    target = tuple(map(int, baseline["public_subgroup_target"]))
    r = int(base["curve"]["subgroup_order"])
    cofactor = int(base["curve"]["cofactor"])
    assert curve.onCurve(target) and curve.mul(target, r) is None

    began = time.perf_counter()
    full_base, reps, _ = base_and_columns(curve, onb, r, cofactor)
    assert len(full_base) == base["factor_base"][
        "actual_usable_points_B_before_folding"]
    assert len(reps) == base["factor_base"]["signed_frobenius_columns"]
    eligible_x = {onb.toCoords(onb.frob(onb.fromCoords(key), shift))
                  for key in keys for shift in range(53)}
    assert len(eligible_x) == stage[
        "eligible_actual_B_before_folding"] // 2
    eligible_base = [point for point in full_base
                     if onb.toCoords(point[0]) in eligible_x]
    assert len(eligible_base) == stage[
        "eligible_actual_B_before_folding"]
    setup_seconds = time.perf_counter() - began

    result = search(curve, eligible_base, target, OrbitKey(onb))
    relation = result["relation"]
    if relation is not None:
        point_set = set(eligible_base)
        points = [tuple(map(int, row)) for row in relation["points"]]
        assert len(points) == 4 and all(point in point_set for point in points)
        total = None
        for point in points:
            assert curve.onCurve(point) and curve.mul(point, r) is None
            total = curve.add(total, point)
        assert total == target
    report = {
        "kind": "post_run_q1326_k128_pair_table_support_diagnostic",
        "proposal_id": "Q1326", "candidate_id": None, "run_id": None,
        "workload_id": baseline["workload_id"],
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "oracle_assisted_compact_s3": False,
        "method": "independent signed-Frobenius quotient pair-table diagnostic",
        "role": "target-support check after the compact-S3 attempts; do not credit relation to compact S3",
        "public_target": list(target),
        "eligible_actual_B_before_folding": len(eligible_base),
        "eligible_folded_columns": len(keys),
        "eligible_set_sha256": stage["eligible_set_sha256"],
        "status": result["status"],
        "observed_verified_relation_count": int(relation is not None),
        "base_setup_wall_seconds": setup_seconds,
        "table_pair_samples": result["table_samples"],
        "query_pair_samples": result["query_samples"],
        "total_logical_pair_samples": (result["table_samples"] +
                                       result["query_samples"]),
        "table_wall_seconds": result["table_wall_ns"] / 1e9,
        "query_wall_seconds": result["query_wall_ns"] / 1e9,
        "relation": relation,
        "field_operations": None,
        "complete_solve_work_log2": None,
        "peak_parent_rss_raw": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "protocol_sha256": sha(protocol_path),
        "runtime_info_sha256": sha(runtime_path),
        "ordinary_target_receipt_sha256": sha(baseline_path),
        "parent_base_archive_sha256": sha(base_path),
        "prior_pair_search_source_sha256": sha(PAIR / "probe_n53_table.py"),
        "prior_base_source_sha256": sha(PAIR / "probe_n53_relation.py"),
        "orbit_key_source_sha256": sha(PAIR / "orbit_key.py"),
        "runner_source_sha256": sha(Path(__file__)),
    }
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "verified_relation": relation is not None,
                      "logical_pair_samples": report[
                          "total_logical_pair_samples"]}))


if __name__ == "__main__":
    main()
