#!/usr/bin/env python3
"""Separate exact five-sum support limits from conditional n83 work models."""

import json
import math
from pathlib import Path

from perf_probe import sha

HERE = Path(__file__).resolve().parent


def main():
    receipt_path = HERE / "runs" / "n83_dyadic_five_sum_stage.json"
    receipt = json.loads(receipt_path.read_text())
    geometry_path = HERE / "runs" / "n83_dyadic_target_seed_geometry.json"
    geometry = json.loads(geometry_path.read_text())
    support_path = HERE / "runs" / "n83_dyadic_G_pair_scalar_support_L1000.json"
    support = json.loads(support_path.read_text())
    assert receipt["curve_id"] == geometry["curve_id"]
    assert support["curve_id"] == geometry["curve_id"]
    assert receipt["factor_base"]["actual_usable_points_B_before_folding"] == 10624
    assert geometry["factor_base"]["actual_usable_points_B_before_folding"] == 332000
    order = int(receipt["subgroup_order"])
    n32 = receipt["factor_base"]["actual_usable_points_B_before_folding"] // 2
    n1000 = geometry["factor_base"]["actual_usable_points_B_before_folding"] // 2
    exact32 = receipt["exact_two_G_pair_sum_support"]
    max32 = n32 * (n32 + 1) // 2
    max1000 = n1000 * (n1000 + 1) // 2
    ratio32 = exact32 / max32
    exact1000 = support["L1000_exact_distinct_G_pair_sums"]
    assert support["L1000_exact_quotient_keys"] == 82843900
    assert exact1000 == 1 + (support["L1000_exact_quotient_keys"] - 1) * 166
    assert exact1000 <= max1000
    median = sorted(receipt["ordinary_blocks"], key=lambda row: row["wall_ns"])[1]
    attempts = median["attempts_including_failed"]
    vector = {name: value / attempts for name, value in
              median["field_api_operations"].items()}
    vector["cyclic_word_rotations"] = median["canonical_operations"][
        "word_rotations"] / attempts
    conditional_probes_floor = order / max1000
    conditional_probes_exact_support = order / exact1000
    report = {
        "kind": "n83_five_sum_conditional_single_target_work_projection",
        "proposal_id": "Q1025", "candidate_id": None,
        "curve_id": receipt["curve_id"], "isogeny": "none",
        "scope": "exact L32 and L1000 G-pair support; stopping-time and operation projections conditional, no n83 natural hit or DLP",
        "L32_actual_base_B": 2 * n32,
        "L32_G_points_N": n32,
        "L32_exact_two_G_pair_sum_support": exact32,
        "L32_unordered_pair_count_cap": max32,
        "L32_support_to_pair_count_ratio": ratio32,
        "L1000_actual_base_B": 2 * n1000,
        "L1000_G_points_N": n1000,
        "L1000_unordered_pair_sum_support_cap": max1000,
        "L1000_quotient_key_count_cap_from_support": math.ceil(max1000 / 166),
        "L1000_exact_quotient_keys": support["L1000_exact_quotient_keys"],
        "L1000_exact_G_pair_sum_support": exact1000,
        "L1000_exact_support_to_pair_count_ratio": exact1000 / max1000,
        "L1000_minimum_11_byte_key_payload_bytes": 11 * support[
            "L1000_exact_quotient_keys"],
        "L1000_conditional_24_byte_packed_rows_bytes": 24 * support[
            "L1000_exact_quotient_keys"],
        "L1000_pair_generators_for_this_index": n1000 * 1000,
        "conditional_uniform_independent_complement_model": {
            "expected_triple_probes_at_maximum_support": conditional_probes_floor,
            "expected_triple_probes_at_maximum_support_log2": math.log2(conditional_probes_floor),
            "expected_triple_probes_at_exact_G_pair_support": conditional_probes_exact_support,
            "expected_triple_probes_at_exact_G_pair_support_log2": math.log2(conditional_probes_exact_support),
            "median_L32_batched_query_field_API_calls_per_triple": vector,
            "conditional_exact_support_probe_count_times_L32_calls_log2_by_separate_unit": {
                name: math.log2(conditional_probes_exact_support * rate)
                for name, rate in vector.items() if rate > 0},
            "conditional_exact_support_probe_count_times_L32_wall_seconds":
                conditional_probes_exact_support * median["wall_ns"] / attempts / 1e9,
        },
        "model_assumptions": [
            "The fixed-target triple complements behave as independent uniform subgroup points; coverage of the fixed target is unproved.",
            "Every index collision yields a nonzero target coefficient; this is unmeasured at n83.",
            "The L32 batched operation vector transfers to L1000 despite larger index and cache footprint.",
            "The 24-byte packed row size transfers from the cross-seed index to a not-yet-built two-G witness index only as a memory model.",
        ],
        "omitted_costs": [
            "target-dependent base and index construction",
            "index storage, sorting, and random-access memory traffic",
            "failed-run tail and relation replay",
            "field arithmetic calibration to a common work unit",
            "paired rho online solve",
        ],
        "verified_complete_solve_work_log2": None,
        "ordinary_relation_yield_measured_n83": None,
        "target_scalar_recovered_n83": False,
        "stage_receipt_sha256": sha(receipt_path),
        "geometry_receipt_sha256": sha(geometry_path),
        "exact_support_receipt_sha256": sha(support_path),
        "source_sha256": sha(Path(__file__)),
    }
    out = HERE / "dyadic_five_sum_n83_projection.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"exact_support": exact1000,
                      "conditional_expected_probes_log2": math.log2(conditional_probes_exact_support),
                      "conditional_mul_calls_log2": report[
                          "conditional_uniform_independent_complement_model"][
                              "conditional_exact_support_probe_count_times_L32_calls_log2_by_separate_unit"]["mul"]}))


if __name__ == "__main__":
    main()
