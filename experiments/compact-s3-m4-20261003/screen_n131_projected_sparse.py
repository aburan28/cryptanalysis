#!/usr/bin/env python3
"""Count the cofactor-four sparse-x S3 circuit at n=131 without solving it."""

from __future__ import annotations

import json
import math
import random
import resource
import time
from pathlib import Path

from chain_s3_projected_sparse import build_projected_sparse_chain
from run_probe import HERE, curves, field, sha


def selector_counts(k):
    """Counts for four exact-base one-hot selectors, before any S3 gates."""
    width = max(1, (math.ceil(k) - 1).bit_length())
    clauses = 4 * (width * k + (1 << width))
    literals = 4 * ((2 * width + 1) * k + width * (1 << width))
    return {"folded_columns": k, "index_bits": width,
            "minimum_selector_cnf_clauses": clauses,
            "minimum_selector_cnf_literal_occurrences": literals,
            "selector_clause_log2": math.log2(clauses),
            "selector_literal_log2": math.log2(literals)}


def main():
    output = HERE / "runs/n131_projected_sparse_geometry.json"
    assert not output.exists()
    protocol_path = HERE / "protocol.json"
    sample_path = HERE / "runs/n131_weight6_stratified_sample.json"
    replay_path = HERE / "runs/n131_weight6_sage_independent_replay.json"
    runtime_path = HERE / "projected_sparse_sage_runtime_info.json"
    protocol = json.loads(protocol_path.read_text())
    sample = json.loads(sample_path.read_text())
    replay = json.loads(replay_path.read_text())
    assert replay["status"] == "PASS"
    assert sample["proposal_id"] == "Q1303"
    assert sample["curve_id"] == protocol[
        "degree_131_design"]["curve"]["curve_id"]
    assert protocol["degree_131_design"]["curve"]["cofactor"] == 4
    assert json.loads(runtime_path.read_text())["status"] == "verified"

    n, weight = 131, 6
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    generator = tuple(map(int, protocol[
        "degree_131_design"]["curve"]["generator"]))
    assert curve.onCurve(generator)
    target_x = onb.toCoords(generator[0])
    started = time.perf_counter()
    formula, raw, projected, mids = build_projected_sparse_chain(
        n, weight, target_x)
    build_seconds = time.perf_counter() - started
    assert len(raw) == len(projected) == 4 and len(mids) == 2
    formula_stats = {
        "variables": formula.variables,
        "cnf_clauses": len(formula.clauses),
        "xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "cnf_literal_occurrences": sum(len(row) for row in formula.clauses),
        "xor_literal_occurrences": sum(
            len(row) for row, _ in formula.xors),
    }

    rng = random.Random(131617)
    group_controls = []
    # The frozen sample and independent replay found no rational weight-one x.
    for weight in range(2, 7):
        checked = 0
        while checked < 8:
            positions = rng.sample(range(n), weight)
            mask = sum(1 << position for position in positions)
            x = onb.fromCoords(mask)
            point = curve.pointFromX(x)
            if point is None:
                continue
            projected_point = curve.mul(point, 4)
            if projected_point is None:
                continue
            x4 = onb.frob(x, 2)
            x8 = onb.frob(x, 3)
            x16 = onb.frob(x, 4)
            denominator = onb.add(onb.mul(x8, x4), x4)
            numerator = onb.add(onb.add(x16, x8), onb.one())
            assert denominator != 0
            assert onb.mul(projected_point[0], denominator) == numerator
            assert onb.trace(onb.add(x, onb.inv(x))) == 0
            group_controls.append(mask)
            checked += 1

    k = sample["conditional_folded_columns_estimate"]
    b_low, b_high = sample["conditional_B_normal_95_percent_interval"]
    k_interval = [b_low / (2 * n), b_high / (2 * n)]
    counts = selector_counts(k)
    assert all(selector_counts(value)["index_bits"] == counts[
        "index_bits"] for value in k_interval)
    receipt = {
        "kind": "n131_projected_sparse_s3_formula_geometry_screen",
        "proposal_id": "Q1318", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "curve_id": sample["curve_id"], "isogeny": "none",
        "n": n, "weight_bound": 6, "cofactor": 4,
        "formula_target_fixture": "protocol generator x; size screen only",
        "formula_target_x_coordinates": target_x,
        "formula": formula_stats,
        "formula_build_seconds": build_seconds,
        "peak_parent_rss_raw": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "peak_parent_rss_units": "bytes on Darwin, KiB on Linux",
        "group_control_seed": 131617,
        "group_control_raw_x_masks": group_controls,
        "group_control_count": len(group_controls),
        "exact_full_base_B": None,
        "exact_full_base_digest": None,
        "conditional_folded_columns_estimate": k,
        "conditional_folded_columns_normal_95_percent_interval": k_interval,
        "one_hot_exact_base_selector_screen": {
            "assumptions": "four leaves; binary index selector; one indicator per canonical base x orbit; sample-based K; counts exclude S3, Frobenius barrel, XOR rows, solver overhead and all other stages",
            "estimate": counts,
            "normal_95_percent_interval": [selector_counts(k_interval[0]),
                                           selector_counts(k_interval[1])],
            "is_complete_solve_projection": False,
        },
        "solver_invoked": False,
        "verified_relation": None,
        "field_operations": None,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(protocol_path),
        "n131_base_sample_receipt_sha256": sha(sample_path),
        "n131_base_replay_receipt_sha256": sha(replay_path),
        "runtime_info_sha256": sha(runtime_path),
        "core_source_sha256": sha(HERE / "chain_s3.py"),
        "factored_source_sha256": sha(HERE / "chain_s3_factored.py"),
        "projected_source_sha256": sha(HERE / "chain_s3_projected_sparse.py"),
        "source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"formula": formula_stats,
                      "build_seconds": build_seconds,
                      "group_controls": len(group_controls),
                      "one_hot_selector_clause_log2": counts[
                          "selector_clause_log2"]}))


if __name__ == "__main__":
    main()
