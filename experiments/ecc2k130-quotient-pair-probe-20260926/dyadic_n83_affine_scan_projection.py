#!/usr/bin/env python3
"""Transfer n83 affine-scan API counts to the rigorous L1000 block bound."""

import json
import math
from pathlib import Path

from perf_probe import sha

HERE = Path(__file__).resolve().parent


def main():
    stage_path = HERE / "runs" / "n83_affine_scan_L32_stage.json"
    support_path = HERE / "runs" / "n83_dyadic_G_pair_scalar_support_L1000.json"
    stage = json.loads(stage_path.read_text())
    support = json.loads(support_path.read_text())
    assert stage["curve_id"] == support["curve_id"]
    order = int(stage["subgroup_order"])
    pair_support = int(support["L1000_exact_distinct_G_pair_sums"])
    length = (2 * order + pair_support - 1) // pair_support
    q = (order - pair_support) * (order - length) / (
        (order - 1) * length * pair_support)
    assert 0 < q < 0.5
    expected_trials_upper = length / (1 - q)
    trials95_upper = 5 * length
    assert length == stage["L1000_affine_block_length_for_mu_at_least_2"]
    assert math.isclose(q, stage[
        "L1000_one_block_failure_probability_upper"], abs_tol=1e-12)
    blocks = stage["ordinary_query_blocks"]
    attempts = sum(row["attempts_including_failed"] for row in blocks)
    assert attempts == stage["ordinary_attempts"] == 12288
    field_names = sorted({name for row in blocks
                          for name in row["field_api_operations"]})
    per_attempt = {name: sum(row["field_api_operations"].get(name, 0)
                             for row in blocks) / attempts
                   for name in field_names}
    rotations_per_attempt = sum(row["canonical_operations"]["word_rotations"]
                                for row in blocks) / attempts
    assert rotations_per_attempt == 82
    key_comparisons_per_attempt_upper = math.ceil(math.log2(
        int(support["L1000_exact_quotient_keys"]) + 1))
    report = {
        "kind": "n83_affine_scan_second_moment_work_projection",
        "scope": "rigorous scan trial bound under independent random affine blocks, with conditional L32-to-L1000 API-call transfer; no observed n83 relation or complete IC work",
        "curve_id": stage["curve_id"],
        "candidate_id": None, "isogeny": "none",
        "L32_actual_B_before_folding": stage["factor_base"][
            "actual_usable_points_B_before_folding"],
        "L1000_projected_actual_B_before_folding": 166 * (1000 + 1),
        "L1000_exact_G_pair_support": pair_support,
        "subgroup_order": str(order),
        "block_length": length,
        "one_block_failure_probability_upper": q,
        "expected_trials_upper": expected_trials_upper,
        "expected_trials_upper_log2": math.log2(expected_trials_upper),
        "95pct_trials_upper": trials95_upper,
        "95pct_trials_upper_log2": math.log2(trials95_upper),
        "L32_measured_attempts": attempts,
        "L32_ordinary_hits": stage["ordinary_quotient_hits"],
        "L32_measured_field_api_calls_per_attempt": per_attempt,
        "L32_measured_word_rotations_per_attempt": rotations_per_attempt,
        "L1000_transferred_expected_field_api_calls_upper_log2": {
            name: math.log2(value * expected_trials_upper)
            for name, value in per_attempt.items() if value},
        "L1000_transferred_95pct_field_api_calls_upper_log2": {
            name: math.log2(value * trials95_upper)
            for name, value in per_attempt.items() if value},
        "L1000_expected_word_rotations_upper_log2": math.log2(
            rotations_per_attempt * expected_trials_upper),
        "L1000_binary_search_key_comparisons_per_attempt_upper":
            key_comparisons_per_attempt_upper,
        "L1000_expected_key_comparisons_upper_log2": math.log2(
            key_comparisons_per_attempt_upper * expected_trials_upper),
        "L1000_G_pair_index_additions": int(support[
            "L1000_unordered_pair_orbit_generators"]),
        "L1000_expected_progression_plus_index_additions_upper_log2":
            stage["L1000_expected_point_additions_including_index_upper_log2"],
        "complete_IC_work_log2": None,
        "proof_boundary": stage["proof_boundary"],
        "transfer_boundary": "The exact second-moment bound concerns trial counts and one progression point addition per trial. API calls and cyclic rotations are transferred from three 4,096-trial L32 prefixes; their per-trial values include block-start scalar multiplication overhead, which is proportionally smaller at the much longer L1000 blocks. L1000 point-index lookup locality, construction field cost, actual n83 relation yield, and calibrated field/bit-operation totals remain unmeasured. Binary-search comparison count is a format bound, not a measured memory-traffic cost.",
        "source_sha256": sha(Path(__file__)),
        "stage_receipt_sha256": sha(stage_path),
        "support_receipt_sha256": sha(support_path),
    }
    out = HERE / "dyadic_n83_affine_scan_projection.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"expected_trials_upper_log2": report[
        "expected_trials_upper_log2"],
                      "expected_mul_calls_upper_log2": report[
                          "L1000_transferred_expected_field_api_calls_upper_log2"]["mul"],
                      "expected_inv_calls_upper_log2": report[
                          "L1000_transferred_expected_field_api_calls_upper_log2"]["inv"],
                      "expected_rotations_upper_log2": report[
                          "L1000_expected_word_rotations_upper_log2"]}))


if __name__ == "__main__":
    main()
