#!/usr/bin/env python3
"""Conditional n=83 pair-claw work screen; no n=83 candidate is issued."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n83_perf_prefix.json")
STAGE = HERE / "runs" / "n53_n83_step_perf.json"
OUTPUT = HERE / "n83_conditional_screen.json"
HYPOTHETICAL_B = 4000000
ORBIT_SIZE = 166
DISTINGUISHED_BITS = 18


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reference = json.loads(REFERENCE.read_text())
    benchmark = json.loads(STAGE.read_text())
    assert reference["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    stage_n83 = next(row for row in benchmark["runs"] if row["curve_id"] == reference["curve_id"])
    order = int(reference["subgroup_order"])
    columns = math.ceil(HYPOTHETICAL_B / ORBIT_SIZE)
    pair_domain = math.comb(HYPOTHETICAL_B + 1, 2)
    multisets = math.comb(HYPOTHETICAL_B + 3, 4)
    sqrt_log2 = math.log2(order) / 2
    collector_proxy_log2 = math.log2(columns + 1) + sqrt_log2
    conditional_steps = (columns + 1) * math.sqrt(order)
    report = {
        "kind": "n83_hypothetical_four_point_pair_claw_screen",
        "scope": "parameterized toy-to-n83 work screen; no enumerated n83 base, relation, DLP, or verified work claim",
        "candidate_id": None,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none",
        "public_target": reference["workload"]["target"],
        "actual_usable_points_B_before_folding": None,
        "effective_columns": None,
        "hypothetical_B": HYPOTHETICAL_B,
        "hypothetical_full_signed_frobenius_orbit_size": ORBIT_SIZE,
        "hypothetical_columns_ceil": columns,
        "hypothetical_pair_multiset_count": str(pair_domain),
        "hypothetical_pair_domain_log2": math.log2(pair_domain),
        "hypothetical_four_point_multiset_count": str(multisets),
        "uniform_independent_sum_expected_representations": multisets / order,
        "distinguished_bits": DISTINGUISHED_BITS,
        "rho_square_root_subgroup_proxy_log2": sqrt_log2,
        "conditional_one_relation_walk_proxy_log2": sqrt_log2,
        "conditional_setup_plus_one_target_sqrt_order_walk_proxy_log2": collector_proxy_log2,
        "conditional_distinguished_endpoint_rows_proxy_log2": (
            sqrt_log2 - DISTINGUISHED_BITS),
        "field_operations_per_walk_evaluation_at_2pow61_gate_ignoring_all_other_work":
            2 ** (61 - collector_proxy_log2),
        "measured_n83_stage_base_B": stage_n83["stage_base_B_before_folding"],
        "measured_n83_median_python_step_ns_on_stage_base": stage_n83["median_ns_per_step"],
        "conditional_one_core_python_years_at_measured_stage_rate": (
            conditional_steps * stage_n83["median_ns_per_step"] / 1e9 /
            (365.25 * 24 * 3600)),
        "wall_extrapolation_limit": "The timed n83 stage base has only 256 points; cache and memory behavior for a hypothetical 4,000,000-point base are unmeasured. The random-claw work law is also unverified.",
        "assumptions": [
            "A target-independent factor base with exactly 4,000,000 distinct subgroup points must first be enumerated and given an immutable candidate identity.",
            "Every selected point has a full signed-Frobenius orbit of size 166; the actual column count and rank yield are unknown.",
            "Pair sums distribute approximately uniformly in the prime subgroup, and the fixed public target has a valid proper four-point representation.",
            "The two-color map and distinguished-point walks behave like a random claw search with a constant multiple of sqrt(r) evaluations per verified relation.",
            "Every verified relation adds one rank row, setup and matrix costs are ignored, and walk evaluations have not been calibrated to field operations.",
            "The one-target descent costs one additional sqrt(r) claw search after setup; no n83 relation or target DLP was found.",
        ],
        "measured_n83_relation_yield": None,
        "verified_n83_dlp": False,
        "complete_work_log2": None,
        "reference_sha256": sha(REFERENCE),
        "stage_benchmark_sha256": sha(STAGE),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"hypothetical_B": HYPOTHETICAL_B,
                      "columns": columns,
                      "collector_proxy_log2": collector_proxy_log2,
                      "max_field_ops_per_walk_eval": report[
                          "field_operations_per_walk_evaluation_at_2pow61_gate_ignoring_all_other_work"]}))


if __name__ == "__main__":
    main()
