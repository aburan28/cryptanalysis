#!/usr/bin/env python3
"""Conditional direct-pair-index operation screen on an enumerated n83 base.

This curve uses a polynomial field representation and has a different curve
ID from the ONB n83 timing panel.  The two are never treated as one measured
candidate.  Pair-sum uniformity and independent rank are model assumptions.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "n83_d12_inputs"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    curve_path = INPUTS / "n83_toy_curve.json"
    base_path = INPUTS / "n83_d12_frobenius_orbit_base_geometry.json"
    curve = json.loads(curve_path.read_text())
    base = json.loads(base_path.read_text())
    assert curve["curve_id"] == base["curve_id"] == "EC1N83Ckb1hc1776f347753"
    assert curve["field"]["basis"] == "polynomial"
    assert curve["curve"]["cofactor"] == 4
    assert curve["checks"]["r_prime_proved"]
    n = curve["field"]["n"]
    r = curve["curve"]["subgroup_order_r"]
    b = base["actual_subgroup_usable_points_before_orbit_folding"]
    k = base["signed_frobenius_columns"]
    orbit_size = 2 * n
    assert (n, b, k) == (83, 326024, 1964)
    assert b == k * orbit_size
    assert base["subgroup_membership_argument"]
    # Only pairs from distinct columns can be useful as independent rows.
    unordered_cross_column_pairs = math.comb(b, 2) - k * math.comb(orbit_size, 2)
    assert unordered_cross_column_pairs == math.comb(k, 2) * orbit_size**2
    pair_generators_one_representative_per_first_column = math.comb(k, 2) * orbit_size
    probes_per_hit = r / unordered_cross_column_pairs
    rank_plus_target_probes = (k + 1) * probes_per_hit
    budget = 2**61
    report = {
        "kind": "n83_d12_direct_pair_index_conditional_work_screen",
        "candidate_id": None,
        "scope": "optimistic four-summand relation collection plus one target; no implemented full solver or measured ordinary relation yield",
        "curve_id": curve["curve_id"], "field_representation": "polynomial",
        "isogeny": "none", "endomorphism_order_conductor": None,
        "factor_base": {"nominal_seed_w_dimension": base["seed_w_dimension"],
                        "geometric_projected_seed_points": base["geometric_projected_seed_points"],
                        "actual_usable_points_B_before_folding": b,
                        "effective_signed_frobenius_columns": k,
                        "closure_point_set_sha256": base["closure_point_set_sha256"]},
        "subgroup_order": str(r),
        "exact_unordered_cross_column_pair_count": str(unordered_cross_column_pairs),
        "cross_column_pair_count_log2": math.log2(unordered_cross_column_pairs),
        "optimistic_quotient_pair_generators": pair_generators_one_representative_per_first_column,
        "quotient_key_count_if_no_sum_orbit_collisions": pair_generators_one_representative_per_first_column,
        "minimum_11_byte_x_key_payload_bytes_model": 11 * pair_generators_one_representative_per_first_column,
        "pair_complement_probes_per_hit_uniform_model_log2": math.log2(probes_per_hit),
        "pair_complement_probes_for_K_rows_and_one_target_optimistic_log2": math.log2(
            rank_plus_target_probes),
        "word_rotations_per_probe_as_written": n - 1,
        "word_rotations_for_K_rows_and_one_target_model_log2": math.log2(
            (n - 1) * rank_plus_target_probes),
        "maximum_field_operations_per_probe_to_fit_2pow61_if_all_other_costs_zero":
            budget / rank_plus_target_probes,
        "max_field_operations_per_probe_log2": math.log2(budget / rank_plus_target_probes),
        "verified_complete_solve_work_log2": None,
        "verified_single_target_online_work_log2": None,
        "field_operations_per_probe_calibrated": None,
        "ordinary_relation_yield_measured": None,
        "final_rank_measured": None,
        "target_scalar_recovered": False,
        "rho_online_comparison": None,
        "assumptions": [
            "distinct cross-column pair sums are uniformly distributed over the prime subgroup",
            "every verified ordinary relation adds one independent matrix row",
            "the quotient table can be built and queried at the modeled size",
            "one four-summand target relation suffices after all base logarithms are known",
        ],
        "unit_warning": "pair-complement probes, word rotations, field operations, memory bytes, and wall time are distinct units; no cross-unit conversion is justified by the small ONB timing panel",
        "curve_input_sha256": sha(curve_path),
        "base_input_sha256": sha(base_path),
        "source_sha256": sha(Path(__file__)),
    }
    out = HERE / "n83_d12_work_screen.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in (
        "curve_id", "pair_complement_probes_per_hit_uniform_model_log2",
        "pair_complement_probes_for_K_rows_and_one_target_optimistic_log2",
        "maximum_field_operations_per_probe_to_fit_2pow61_if_all_other_costs_zero")}))


if __name__ == "__main__":
    main()
