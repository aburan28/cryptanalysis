#!/usr/bin/env python3
"""Conditional n=83 pair-claw work screen; no n=83 candidate is issued."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n83_perf_prefix.json")
BASE_RECEIPT = HERE / "runs" / "n83_weight5_orbit_base.json"
STAGE = HERE / "runs" / "n53_n83_step_perf.json"
OUTPUT = HERE / "n83_conditional_screen.json"
ORBIT_SIZE = 166
DISTINGUISHED_BITS = 18


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reference = json.loads(REFERENCE.read_text())
    enumerated = json.loads(BASE_RECEIPT.read_text())
    benchmark = json.loads(STAGE.read_text())
    assert reference["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert enumerated["curve_id"] == reference["curve_id"]
    stage_n83 = next(row for row in benchmark["runs"] if row["curve_id"] == reference["curve_id"])
    order = int(reference["subgroup_order"])
    actual_B = enumerated["factor_base"]["actual_usable_points_B_before_folding"]
    columns = enumerated["factor_base"]["signed_frobenius_columns"]
    assert actual_B == ORBIT_SIZE * columns == 4000102
    pair_domain = math.comb(actual_B + 1, 2)
    multisets = math.comb(actual_B + 3, 4)
    sqrt_log2 = math.log2(order) / 2
    collector_proxy_log2 = math.log2(columns + 1) + sqrt_log2
    conditional_steps = (columns + 1) * math.sqrt(order)
    report = {
        "kind": "n83_exact_base_conditional_four_point_pair_claw_screen",
        "scope": "enumerated n83 base and measured bounded step cost; random-claw relation yield and full work remain unverified",
        "candidate_id": None,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none",
        "public_target": reference["workload"]["target"],
        "actual_usable_points_B_before_folding": actual_B,
        "effective_columns": columns,
        "factor_base_enumerated_set_sha256": enumerated["factor_base"]["enumerated_set_sha256"],
        "full_signed_frobenius_orbit_size": ORBIT_SIZE,
        "pair_multiset_count": str(pair_domain),
        "pair_domain_log2": math.log2(pair_domain),
        "four_point_multiset_count": str(multisets),
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
        "wall_extrapolation_limit": "The direct-walk timing uses only a 256-point stage base; full-base direct-walk cache and memory behavior and its random-claw yield are unmeasured.",
        "assumptions": [
            "The exact target-independent factor base has 4,000,102 distinct subgroup points and 24,097 full signed-Frobenius orbits; its base logs and rank yield are unknown, so no complete candidate identity is issued.",
            "Pair sums distribute approximately uniformly in the prime subgroup, and the fixed public target has a valid proper four-point representation.",
            "The two-color map and distinguished-point walks behave like a random claw search with a constant multiple of sqrt(r) evaluations per verified relation.",
            "Every verified relation adds one rank row, setup and matrix costs are ignored, and walk evaluations have not been calibrated to field operations.",
            "The one-target descent costs one additional sqrt(r) claw search after setup; no n83 relation or target DLP was found.",
        ],
        "measured_n83_relation_yield": None,
        "verified_n83_dlp": False,
        "complete_work_log2": None,
        "reference_sha256": sha(REFERENCE),
        "base_receipt_sha256": sha(BASE_RECEIPT),
        "stage_benchmark_sha256": sha(STAGE),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"actual_B": actual_B,
                      "columns": columns,
                      "collector_proxy_log2": collector_proxy_log2,
                      "max_field_ops_per_walk_eval": report[
                          "field_operations_per_walk_evaluation_at_2pow61_gate_ignoring_all_other_work"]}))


if __name__ == "__main__":
    main()
