#!/usr/bin/env python3
"""Sweep the frozen N131 base-weight counts under Q1505's scan model."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SOURCES = {
    "w5": PARENT / "runs/n131_q1413_projected_x_w5.json",
    "w6": PARENT / "runs/n131_q1413_projected_x_w6.json",
    "w7_w8": PARENT / "q20261011_weight7_screen/measurement.json",
    "kernel": PARENT / "q20261012_n83_deferred_y_scan/analysis.json",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def row(weight, b, k, status, order, source, digest=None):
    assert b == 262 * k
    second_pairs = b * (b + 1) // 2
    four_sign_scan_mul = 10 * b
    hit_upper_num = 4 * second_pairs
    hit_upper_den = order - 1
    mean_four_multisets_num = (b + 3) * (b + 2) * (b + 1) * b // 24
    mean_four_multisets_den = order - 1
    work_log2 = (math.log2(k) + math.log2(hit_upper_den) -
                 math.log2(hit_upper_num) + math.log2(four_sign_scan_mul))
    return {
        "weight_bound": weight, "base_status": status, "source": source,
        "B": b, "K": k, "enumerated_set_sha256": digest,
        "four_sign_full_scan_batch_mul_calls_zero_hits": four_sign_scan_mul,
        "four_sign_full_scan_batch_mul_log2": math.log2(four_sign_scan_mul),
        "four_sign_hit_probability_upper_numerator": hit_upper_num,
        "four_sign_hit_probability_upper_denominator": str(hit_upper_den),
        "four_sign_hit_probability_upper_log2":
            math.log2(hit_upper_num) - math.log2(hit_upper_den),
        "expected_K_unordered_pair_matches_batch_mul_lower_log2_independent_uniform_first_pair": work_log2,
        "gap_above_2pow61_bits_in_that_unit": work_log2 - 61,
        "uniform_four_multiset_mean_upper_log2":
            math.log2(mean_four_multisets_num) - math.log2(mean_four_multisets_den),
        "scalar_sparse_matrix_proxy_modular_operations": 4 * k * k,
        "scalar_sparse_matrix_proxy_log2": math.log2(4 * k * k),
        "four_sign_batch_inversions": {
            str(batch): 4 * math.ceil((b // 2) / batch)
            for batch in (128, 512, 2048, 8192)
        },
    }


def main():
    protocol = read(HERE / "protocol.json")
    assert {label: sha(path) for label, path in SOURCES.items()} == protocol["source_sha256"]
    w5, w6, sampled, kernel = (read(SOURCES[name]) for name in SOURCES)
    order = int(sampled["subgroup_order_r"])
    assert order == int(protocol["subgroup_order_r"])
    assert kernel["n131_exact_weight6_B"] == w6["actual_usable_points_B_before_folding"]
    rows = []
    for label, data in (("w5", w5), ("w6", w6)):
        rows.append(row(data["normal_basis_weight_bound"],
                        data["actual_usable_points_B_before_folding"],
                        data["signed_frobenius_columns_K"], "exact_enumerated",
                        order, label, data["enumerated_set_sha256"]))
    for sampled_row in sampled["rows"][1:]:
        weight = sampled_row["weight_bound"]
        central = row(weight, sampled_row["conditional_B"],
                      sampled_row["conditional_folded_K"],
                      "sampled_conditional_projection_count", order, "w7_w8")
        endpoints = []
        for k in sampled_row["conditional_K_interval_from_componentwise_wilson95"]:
            endpoints.append(row(weight, 262 * k, k,
                                 "sampled_conditional_K_interval_endpoint", order, "w7_w8"))
        central["conditional_K_interval_endpoints"] = endpoints
        rows.append(central)
    assert [r["weight_bound"] for r in rows] == [5, 6, 7, 8]
    output = {
        "proposal_id": "Q1506", "candidate_id": None, "run_id": None,
        "curve_id": "EC1N131Ckb1h6816f880945e", "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "protocol_sha256": sha(HERE / "protocol.json"),
        "source_sha256": {label: sha(path) for label, path in SOURCES.items()},
        "subgroup_order_r": str(order),
        "scope": "Q1505 zero-hit complete four-sign scan under independent uniform nonidentity queries and a fixed first x-pair selected independently of each target. All trials and failures charged. The probability of any match is at most 4*C(B+1,2)/(r-1) by a union bound, and the expected number of signed-complement/unordered-second-pair matches per scan is at most the same quantity by linearity. Each such match supplies at most one rank row, even when one scan returns multiple raw x-key hits. No first-pair search, novel-rank loss, inversion internals, setup, final LA, target descent or replay is charged. Conditional W7/W8 counts are estimates, not enumerated sets.",
        "rows": rows,
        "complete_n131_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
    }
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
