#!/usr/bin/env python3
"""Project the exact n83 dyadic base into separate operation-count units."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    geometry_path = HERE / "runs" / "n83_dyadic_base_geometry.json"
    batch_path = HERE / "runs" / "n83_batch_x_only_comparison.json"
    geometry = json.loads(geometry_path.read_text())
    batch = json.loads(batch_path.read_text())
    assert geometry["curve_id"] == batch["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert geometry["proposal_id"] == "Q1013" and batch["proposal_id"] == "Q1012"
    assert geometry["factor_base"]["actual_usable_points_B_before_folding"] == 332000
    assert geometry["factor_base"]["effective_unknown_log_columns_after_dyadic_labels"] == 99
    assert batch["factor_base"]["actual_usable_points_B_before_folding"] == 332
    assert batch["lookup_budget_per_repetition"] == 2048
    measured = next(row for row in batch["samples"] if row["variant"] == "batch")[
        "repetitions"][0]
    assert measured["lookups"] == 2048 and measured["verified_hit_positions"] == []
    pair_count = int(geometry["conditional_direct_pair_screen"][
        "exact_cross_seed_unordered_pair_count"])
    order = int(geometry["subgroup_order"])
    rows_plus_target = geometry["conditional_direct_pair_screen"][
        "rank_rows_plus_one_target"]
    expected_probes_per_hit = order / pair_count
    expected_total_probes = rows_plus_target * expected_probes_per_hit
    unit_calls = dict(measured["field_api_operations"])
    assert unit_calls["mul"] == 5 * unit_calls["sqr"]
    unit_calls["direct_batch_formula_xors"] = 8 * unit_calls["sqr"]
    unit_calls["cyclic_word_rotations"] = measured[
        "canonical_operations"]["word_rotations"]
    per_probe = {name: count / measured["lookups"]
                 for name, count in unit_calls.items()}
    model_exponents = {name: math.log2(expected_total_probes * per_probe[name])
                       for name in per_probe if per_probe[name] > 0}
    quotient_generators = geometry["conditional_direct_pair_screen"][
        "quotient_cross_seed_pair_generators"]
    report = {
        "kind": "n83_dyadic_base_conditional_operation_vector_projection",
        "proposal_id": "Q1013", "candidate_id": None,
        "curve_id": geometry["curve_id"], "isogeny": "none",
        "scope": "same-curve small-base batch query operation vector applied to enumerated large-base uniform-support and novel-rank model; not a measured relation yield, complete index, or DLP",
        "estimate_status": "unvalidated independence and novel-rank hypothesis for the 100-seed base; the two-seed coefficient-support audit does not numerically bound this different base",
        "actual_usable_base_B": 332000,
        "effective_unknown_log_columns": 99,
        "exact_cross_seed_unordered_pair_count": str(pair_count),
        "rank_rows_plus_one_target_model": rows_plus_target,
        "pair_complement_probes_per_hit_model_log2": math.log2(expected_probes_per_hit),
        "rank_plus_target_pair_probes_model_log2": math.log2(expected_total_probes),
        "quotient_pair_generators_if_no_sum_orbit_collisions": quotient_generators,
        "minimum_11_byte_x_key_payload_bytes_model": 11 * quotient_generators,
        "bounded_same_curve_query_B": 332,
        "bounded_query_lookups": measured["lookups"],
        "measured_small_base_field_api_and_word_counts": unit_calls,
        "measured_small_base_calls_per_probe": per_probe,
        "conditional_rank_plus_target_count_log2_by_separate_unit": model_exponents,
        "unit_warning": "field multiplies, inversions, squarings, Frobenius calls, XORs, word rotations, hash probes, and wall time are separate units; the large-base memory and cache behavior and ordinary rank yield are unmeasured",
        "verified_complete_solve_work_log2": None,
        "ordinary_relation_yield_measured": None,
        "final_rank_measured": None,
        "target_scalar_recovered": False,
        "geometry_receipt_sha256": sha(geometry_path),
        "small_base_batch_receipt_sha256": sha(batch_path),
        "source_sha256": sha(Path(__file__)),
    }
    out = HERE / "dyadic_n83_work_projection.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": report["curve_id"],
                      "total_pair_probes_log2": report[
                          "rank_plus_target_pair_probes_model_log2"],
                      "separate_unit_exponents": model_exponents}, indent=2))


if __name__ == "__main__":
    main()
