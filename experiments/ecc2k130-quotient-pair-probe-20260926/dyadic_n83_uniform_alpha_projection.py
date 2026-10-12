#!/usr/bin/env python3
"""Project fresh-alpha n83 query work from exact support and measured L32 API calls."""

import json
import math
from pathlib import Path

from perf_probe import sha

HERE = Path(__file__).resolve().parent


def main():
    stage_path = HERE / "runs" / "n83_uniform_alpha_L32_stage.json"
    support_path = HERE / "runs" / "n83_dyadic_G_pair_scalar_support_L1000.json"
    stage = json.loads(stage_path.read_text())
    support = json.loads(support_path.read_text())
    assert stage["curve_id"] == support["curve_id"]
    assert stage["factor_base"]["actual_usable_points_B_before_folding"] == 10624
    assert support["factor_base"]["actual_usable_points_B_before_folding"] == 332000
    order = int(support["subgroup_order"])
    pair_support = int(support["L1000_exact_distinct_G_pair_sums"])
    p = pair_support / order
    expected_trials = order / pair_support
    trials95 = math.ceil(math.log(0.05) / math.log1p(-p))
    blocks = stage["ordinary_query_blocks"]
    attempts = sum(row["attempts_including_failed"] for row in blocks)
    assert attempts == stage["ordinary_attempts"] == 12288
    api_names = sorted({name for row in blocks
                        for name in row["field_api_operations"]})
    api_per_attempt = {name: sum(row["field_api_operations"].get(name, 0)
                                 for row in blocks) / attempts
                       for name in api_names}
    group_per_attempt = sum(row["logical_group_additions"]
                            for row in blocks) / attempts
    assert group_per_attempt <= 13
    assert all(row["quotient_hits"] == 0 for row in blocks)
    build_additions = int(support["L1000_unordered_pair_orbit_generators"])
    assert build_additions == 83083000
    report = {
        "kind": "n83_fresh_alpha_exact_support_work_projection",
        "scope": "exact geometric trial expectation under fresh independent uniform alpha; L32-to-L1000 per-trial API-call transfer is conditional; no n83 ordinary relation or complete IC work",
        "curve_id": stage["curve_id"],
        "isogeny": "none", "candidate_id": None,
        "L32_actual_B_before_folding": 10624,
        "L1000_actual_B_before_folding": 332000,
        "L1000_exact_G_pair_sum_support": pair_support,
        "subgroup_order": str(order),
        "exact_ideal_alpha_hit_probability": f"{pair_support}/{order}",
        "expected_attempts": expected_trials,
        "expected_attempts_log2": math.log2(expected_trials),
        "attempts_for_at_least_95pct_success": trials95,
        "attempts_for_at_least_95pct_success_log2": math.log2(trials95),
        "L32_measured_attempts": attempts,
        "L32_observed_ordinary_hits": stage["ordinary_quotient_hits"],
        "L32_measured_field_api_calls_per_attempt": api_per_attempt,
        "L32_measured_logical_group_additions_per_attempt": group_per_attempt,
        "L32_block_multiplications_per_attempt": [
            row["field_api_operations"].get("mul", 0) /
            row["attempts_including_failed"] for row in blocks],
        "L1000_transferred_expected_field_api_calls_log2": {
            name: math.log2(value * expected_trials)
            for name, value in api_per_attempt.items() if value},
        "L1000_transferred_95pct_field_api_calls_log2": {
            name: math.log2(value * trials95)
            for name, value in api_per_attempt.items() if value},
        "L1000_index_pair_additions": build_additions,
        "L1000_transferred_expected_group_additions_including_index_log2":
            math.log2(build_additions + group_per_attempt * expected_trials),
        "L1000_algorithmic_expected_group_additions_upper_log2":
            math.log2(build_additions + 13 * expected_trials),
        "L1000_algorithmic_95pct_group_additions_upper_log2":
            math.log2(build_additions + 13 * trials95),
        "complete_IC_work_log2": None,
        "proof_boundary": "Conditional on any fixed public target, past trials, and a chosen three-Q sum with nonzero coefficient b, a fresh independent uniform alpha makes alpha*G-b*Q uniform in the subgroup. A complete G-pair membership test therefore hits with exact probability |S|/r, and that hit yields k=(alpha-a)/b mod r. Expected attempts r/|S| and the 95% quantile follow geometrically. The frozen L32 OS-random stream measures implementation cost but its zero-hit prefix is not a yield estimator.",
        "transfer_boundary": "The field API vector is measured on 12,288 L32 ordinary trials and multiplied by the exact L1000 expected trial count. It omits L1000 memory/cache effects, index build field cost, target-dependent base cost, and any conversion from field API calls to calibrated field or bit operations. Group-addition bounds count at most ten radix-table additions for alpha*G, two for a Q triple, one for its complement, and all L1000 index pair additions; quotient key generation and lookup are separate work.",
        "source_sha256": sha(Path(__file__)),
        "stage_receipt_sha256": sha(stage_path),
        "support_receipt_sha256": sha(support_path),
    }
    out = HERE / "dyadic_n83_uniform_alpha_projection.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"expected_attempts_log2": report["expected_attempts_log2"],
                      "expected_mul_calls_log2": report[
                          "L1000_transferred_expected_field_api_calls_log2"]["mul"],
                      "95pct_mul_calls_log2": report[
                          "L1000_transferred_95pct_field_api_calls_log2"]["mul"],
                      "algorithmic_group_add_upper_log2": report[
                          "L1000_algorithmic_expected_group_additions_upper_log2"]}))


if __name__ == "__main__":
    main()
