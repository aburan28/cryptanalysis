#!/usr/bin/env python3
"""Conditional n83 operation vector for a target-seeded dyadic base."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    geometry_path = HERE / "runs" / "n83_dyadic_target_seed_geometry.json"
    perf_path = HERE / "runs" / "n83_dyadic_target_perf_L32.json"
    support_path = HERE / "dyadic_coefficient_support.json"
    geometry = json.loads(geometry_path.read_text())
    perf = json.loads(perf_path.read_text())
    support = json.loads(support_path.read_text())
    assert geometry["curve_id"] == perf["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert geometry["proposal_id"] == "Q1020" and perf["proposal_id"] == "Q1022"
    assert geometry["target"] == perf["target_seed"]
    base = geometry["factor_base"]
    assert base["actual_usable_points_B_before_folding"] == 332000
    assert base["signed_frobenius_columns"] == 2000
    assert base["effective_unknown_log_columns_after_dyadic_labels"] == 1
    measured = perf["ordinary_query_prefixes"][0]
    assert measured["lookups"] == 166 * 64
    assert measured["verified_hit_positions"] == []
    pair_count = int(geometry["conditional_direct_pair_screen"][
        "exact_cross_seed_unordered_pair_count"])
    order = int(geometry["subgroup_order"])
    expected_probes = order / pair_count
    support_row = next(row for row in support["rows"] if
                       row["degree"] == 83 and row["doubling_window"] == 1000)
    diagnostic_row = next(row for row in support["rows"] if
                          row["degree"] == 83 and row["doubling_window"] == 20)
    assert support_row["curve_id"] == geometry["curve_id"]
    assert support_row["cross_seed_pair_count"] == pair_count
    failed_probe_lower_log2 = support_row[
        "iid_uniform_expected_failed_pair_probes_lower_log2"]
    transferred_ratio = diagnostic_row["exact_two_sum_to_ordered_pair_ratio"]
    heuristic_sum_count = transferred_ratio * pair_count
    heuristic_probability = min(1.0, heuristic_sum_count**2 / (order - 1))
    heuristic_failed_probes_log2 = math.log2(
        pair_count * (1 / heuristic_probability - 1))
    unit_calls = dict(measured["field_api_operations"])
    assert unit_calls["mul"] == 5 * unit_calls["sqr"]
    unit_calls["direct_batch_formula_xors"] = 8 * unit_calls["sqr"]
    unit_calls["cyclic_word_rotations"] = measured[
        "canonical_operations"]["word_rotations"]
    per_probe = {name: count / measured["lookups"] for name, count in unit_calls.items()}
    naive_one_hit = {name: math.log2(expected_probes * count)
                     for name, count in per_probe.items() if count > 0}
    failed_lower = {name: failed_probe_lower_log2 + math.log2(count)
                    for name, count in per_probe.items() if count > 0}
    heuristic_counts = {name: heuristic_failed_probes_log2 + math.log2(count)
                        for name, count in per_probe.items() if count > 0}
    quotient_generators = geometry["conditional_direct_pair_screen"][
        "quotient_cross_seed_pair_generators"]
    report = {
        "kind": "n83_target_seed_two_seed_conditional_operation_projection",
        "proposal_id": "Q1020", "candidate_id": None,
        "curve_id": geometry["curve_id"], "isogeny": "none",
        "scope": "exact target-seeded base on the frozen public n83 point; same-curve L32 complete-index query operation vector is transferred conditionally to L1000; no n83 ordinary hit or DLP",
        "target_seed_policy": "public G with known log 1, public DLP target Q with unknown log; target-dependent base and index would be charged online",
        "actual_usable_base_B": 332000,
        "signed_frobenius_columns": 2000,
        "effective_unknown_log_columns": 1,
        "exact_cross_seed_unordered_pair_count": str(pair_count),
        "refuted_independent_pair_probe_model_log2": math.log2(expected_probes),
        "uniform_query_hit_probability_upper": support_row[
            "uniform_known_log_query_hit_probability_upper"],
        "expected_failed_full_scans_pair_probes_lower_log2": failed_probe_lower_log2,
        "heuristic_transferred_n83_window20_two_sum_ratio": transferred_ratio,
        "heuristic_expected_failed_scans_pair_probes_log2": heuristic_failed_probes_log2,
        "quotient_pair_generators_if_no_sum_orbit_collisions": quotient_generators,
        "minimum_11_byte_x_key_payload_bytes_model": 11 * quotient_generators,
        "measured_L32_base_B": 10624,
        "measured_L32_query_lookups": measured["lookups"],
        "measured_L32_field_api_and_word_counts": unit_calls,
        "measured_L32_calls_per_probe": per_probe,
        "refuted_independent_pair_count_log2_by_separate_unit": naive_one_hit,
        "expected_failed_scan_lower_bound_log2_by_separate_unit": failed_lower,
        "heuristic_failed_scan_log2_by_separate_unit": heuristic_counts,
        "model_assumptions": [
            "cross-seed pair-sum support is near the exact pair count",
            "first hit has nonzero Q coefficient",
            "a complete 166-million-key quotient index can be built and queried",
            "L32 operation counts transfer to L1000 despite memory and cache changes",
            "heuristic only: coefficient two-sum collision ratio transfers from L20 to L1000",
        ],
        "omitted_costs": ["target-dependent base construction", "index generation",
                          "index storage and cache misses", "failed full-query overhead",
                          "group-relation validation", "modular solve", "scalar replay"],
        "verified_complete_solve_work_log2": None,
        "ordinary_relation_yield_measured_n83": None,
        "target_scalar_recovered_n83": False,
        "geometry_receipt_sha256": sha(geometry_path),
        "coefficient_support_receipt_sha256": sha(support_path),
        "L32_perf_receipt_sha256": sha(perf_path),
        "source_sha256": sha(Path(__file__)),
    }
    out = HERE / "dyadic_two_seed_n83_projection.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": report["curve_id"],
                      "independent_probe_model_refuted_log2": math.log2(expected_probes),
                      "expected_failed_scan_probes_lower_log2": failed_probe_lower_log2,
                      "heuristic_failed_scan_probes_log2": heuristic_failed_probes_log2,
                      "failed_scan_separate_unit_lower_exponents": failed_lower}, indent=2))


if __name__ == "__main__":
    main()
