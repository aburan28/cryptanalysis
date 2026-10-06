#!/usr/bin/env python3
"""Conditional operation-count model for one ECC2K-130 DLP via pair indexing.

The output is an extrapolation, not a measured run or a candidate manifest.
It deliberately keeps unknown complete-DLP costs null.
"""

import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = 680564733841876926932320129493409985129
N = 131


def log2(value):
    return math.log2(value)


def scenario(name, base_points, columns, provenance):
    # Pair-probe law: the direct pair index matches a target complement with
    # probability about B^2/(2r) per probe while that probability is small.
    # This law was calibrated on complete toy DLPs in the pair-index gate.
    probes_per_relation = 2 * R / base_points**2
    raw_pair_entries = base_points * (base_points + 1) / 2
    quotient_keys = raw_pair_entries / (2 * N)
    pair_generators = base_points**2 / (2 * N)
    out = {
        "name": name,
        "provenance": provenance,
        "base_points_B_input": base_points,
        "base_points_log2": log2(base_points),
        "effective_columns_K_input": columns,
        "raw_pair_entries_model_log2": log2(raw_pair_entries),
        "signed_frobenius_quotient_keys_model_log2": log2(quotient_keys),
        "quotient_pair_generators_model_log2": log2(pair_generators),
        "pair_probes_per_verified_relation_model_log2": log2(probes_per_relation),
        "minimum_point_frobenius_calls_per_relation_as_written_model_log2":
            log2(N * probes_per_relation),
        "minimum_key_only_quotient_index_bytes_model_log2":
            log2(17 * quotient_keys),
        "verified_full_dlp_work_log2": None,
        "verified_single_target_online_work_log2": None,
    }
    if columns is not None:
        # Treat every successful relation as novel: deliberately optimistic.
        rank_probes = columns * probes_per_relation
        out.update({
            "effective_columns_K_log2": log2(columns),
            "rank_collection_pair_probes_model_log2": log2(rank_probes),
            "optimistic_matrix_row_operations_model_log2": 2 * log2(columns),
            "minimum_point_frobenius_calls_for_rank_as_written_model_log2":
                log2(N * rank_probes),
            "rank_plus_one_target_pair_probes_model_log2":
                log2(rank_probes + probes_per_relation),
        })
    else:
        out.update({
            "effective_columns_K_log2": None,
            "rank_collection_pair_probes_model_log2": None,
            "optimistic_matrix_row_operations_model_log2": None,
            "minimum_point_frobenius_calls_for_rank_as_written_model_log2": None,
            "rank_plus_one_target_pair_probes_model_log2": None,
        })
    return out


def main():
    weight_gate = json.loads((HERE / "weight5_support_gate.json").read_text())
    window_path = HERE / "u_window28_131_sample.json"
    window_sample = json.loads(window_path.read_text())
    assert window_sample["field_degree"] == N and window_sample["window_dimension"] == 28
    pair_gate_path = HERE / "pair_index_gate_report.json"
    pair_gate = json.loads(pair_gate_path.read_text())
    calibration = [{"degree": row["n"],
                    "observed_over_predicted_rank_probes":
                        row["blocks"][0]["observed_over_predicted_probes"]}
                   for row in pair_gate["measured_panel"]]
    assert max(abs(row["observed_over_predicted_rank_probes"] - 1)
               for row in calibration) < 0.04
    stage_calibration = []
    stage_receipt_hashes = {}
    for degree in (53, 83):
        path = HERE / "runs" / f"n{degree}_perf_prefix.json"
        run = json.loads(path.read_text())
        index = run["index_prefix"]
        queries = run["query_runs"]
        budget = run["query_lookup_budget"]
        assert run["field_degree"] == degree
        assert index["generators_processed"] == index["eligible_generator_pairs"]
        assert len(queries) == 3 and all(row["lookups"] == budget for row in queries)
        assert all(row["verified_hits_in_prefix"] == 0 for row in queries)
        stage_calibration.append({
            "degree": degree,
            "actual_selected_base_B": run["base"]["actual_usable_points_B"],
            "complete_selected_base_index_generators": index["generators_processed"],
            "selected_base_quotient_keys": index["index_keys_in_prefix"],
            "index_build_wall_ms": index["build_wall_ns"] / 1_000_000,
            "index_build_ms_per_generator": index["build_wall_ns"] / 1_000_000 / index["generators_processed"],
            "ordinary_target_query_prefix_lookups": budget,
            "query_repetitions": len(queries),
            "median_query_wall_ms": statistics.median(row["wall_ns"] for row in queries) / 1_000_000,
            "median_query_ms_per_lookup": statistics.median(row["wall_ns"] for row in queries) / 1_000_000 / budget,
            "point_frobenius_calls_per_lookup": queries[0]["operations"]["frob"] / budget,
            "point_negations_per_lookup": queries[0]["operations"]["neg"] / budget,
            "point_additions_per_lookup": queries[0]["operations"]["add"] / budget,
            "verified_hits_in_measured_prefix": 0,
        })
        stage_receipt_hashes[str(degree)] = hashlib.sha256(path.read_bytes()).hexdigest()
    cap = weight_gate["subgroup_usable_point_upper_bound_B"]
    rows = [
        scenario("normal_weight_at_most_five_point_cap", cap, None,
                 "rigorous upper bound on B, not an enumerated actual base; probe estimate assumes the measured pair-index support law transfers"),
        scenario("normal_u_window_degree_28_sample",
                 window_sample["estimated_geometric_point_count"],
                 window_sample["estimated_signed_frobenius_columns"],
                 "sampled geometric points treated optimistically as distinct subgroup-usable B; sampled folded columns treated as independent rank; actual subgroup-usable B and final rank are unmeasured at n=131"),
    ]
    report = {
        "kind": "ecc2k130_pair_index_conditional_work_estimate",
        "scope": "direct four-summand pair-index family; group-probe and key-count units, not calibrated field operations or a verified DLP",
        "candidate_id": None,
        "subgroup_order": str(R),
        "field_degree": N,
        "signed_frobenius_orbit_size": 2 * N,
        "operation_unit": "one pair-complement group/hash probe; pair-table generation and matrix row operations are reported separately and never summed into this unit",
        "support_law": "approximately 2*r/B^2 pair probes per verified relation, with uniform subgroup targets and a direct pair index; toy full-DLP calibration in experiments/koblitz-pair-index-gate-20260924",
        "rank_law": "K independent relations; every successful relation assumed novel, all failed probes included",
        "target_descent_assumption": "after logs are precomputed, draw known-offset variants of one target until a verified four-point decomposition is found; no such n=131 descent was implemented",
        "toy_full_dlp_probe_law_calibration": calibration,
        "measured_bounded_stage_throughput": stage_calibration,
        "bounded_stage_receipt_sha256": stage_receipt_hashes,
        "bounded_stage_caveat": "n53/n83 measurements use only two weight-two x orbits, a complete index for that selected base, and fixed 2048-lookup ordinary-target prefixes; no n131 wall-time extrapolation or solve claim",
        "quotient_size_law": "B*(B+1)/(4*n) generic full-length signed-Frobenius pair-sum orbits; a heuristic, not a measured n=131 table",
        "as_written_canonicalization": "canonical() applies at least n point Frobenius maps for each complement lookup",
        "rho_signed_orbit_state_proxy_log2": 0.5 * log2(R / (2 * N)),
        "rho_repo_expected_iteration_log2": 60.9,
        "rho_comparison_valid": False,
        "missing_for_full_solve": [
            "enumerated n=131 subgroup-usable base and actual folded columns",
            "ordinary n=131 relation coverage and novel rank trajectory",
            "calibrated cost per pair probe and index construction",
            "complete relation matrix solve and verified factor logs",
            "single-target descent, scalar recovery, and paired rho online wall time",
        ],
        "scenarios": rows,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "support_receipt_sha256": hashlib.sha256((HERE / "weight5_support_gate.json").read_bytes()).hexdigest(),
        "window_sample_receipt_sha256": hashlib.sha256(window_path.read_bytes()).hexdigest(),
        "pair_index_gate_sha256": hashlib.sha256(pair_gate_path.read_bytes()).hexdigest(),
    }
    output = HERE / "work_estimate.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    for row in rows:
        print(row["name"], "B=2^%.2f" % row["base_points_log2"],
              "one_relation_probes=2^%.2f" % row["pair_probes_per_verified_relation_model_log2"],
              "rank_probes=" + ("unknown" if row["rank_collection_pair_probes_model_log2"] is None
                                else "2^%.2f" % row["rank_collection_pair_probes_model_log2"]))


if __name__ == "__main__":
    main()
