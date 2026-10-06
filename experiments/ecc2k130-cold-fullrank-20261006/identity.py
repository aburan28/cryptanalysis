#!/usr/bin/env python3
"""Assign canonical IC1/curve/workload/run IDs to replayed successful cells."""
import argparse
import hashlib
import json
from pathlib import Path

from verify import records, only

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "CONFIG.json").read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def cell_identity(run, replay, n):
    audit = next(x for x in replay["cells"] if x["n"] == n)
    assert audit["status"] == "PASS_INDEPENDENT_GROUP_ROW_RANK_SCALAR_REPLAY"
    direct = records(run / f"n{n}-direct.stdout.jsonl")
    rho = only(records(run / f"n{n}-rho.stdout.jsonl"), "rho_public_fixture")
    factor = only(direct, "point_defined_factor_base")
    pre = only(direct, "relation_rank_summary", 0)
    target = only(direct, "relation_rank_summary", 1)
    batch = only(direct, "retained_support_batch_summary")
    run_config = next(x for x in CONFIG["curves"] if x["n"] == n)
    r = int(rho["subgroup_order"])
    cofactor = int(factor["cofactor"])
    field = {
        "p": 2,
        "n": n,
        "representation": "polynomial_basis",
        "defining_modulus_bits": audit["field_modulus"],
        "element_encoding": "nonnegative_int_with_bit_i_as_x_power_i",
    }
    curve_without_id = {
        "model": "binary_weierstrass_y2_plus_xy_eq_x3_plus_ax2_plus_b",
        "coefficients": {"a": 0, "b": 1},
        "curve_order": cofactor*r,
        "trace": (1 << n)+1-cofactor*r,
        "subgroup_order": r,
        "cofactor": cofactor,
        "generator": rho["generator"],
        "target_group": "prime_order_subgroup_generated_by_G",
        "point_encoding": "affine_pair_of_polynomial_basis_integers; infinity_null",
    }
    curve_id = f"EC1N{n}Ckb0h{sha({'field': field, 'curve': curve_without_id})[:12]}"
    curve = {**curve_without_id, "curve_id": curve_id}
    source = CONFIG["producer"]
    base_seed = int(factor["factor_base_seed"])
    factor_base = {
        "construction": "LCG_abscissa_scan_then_cofactor_projection_then_signed_frobenius_orbits_from_pinned_rank_fixture",
        "factor_base_seed": base_seed,
        "selection_eta": {"numerator": run_config["eta"][0], "denominator": run_config["eta"][1]},
        "exact_point_set_digest": audit["factor_base_point_list_sha256"],
        "point_set_digest_encoding": "sha256_of_compact_json_array_of_all_affine_integer_pairs_in_producer_order",
        "representative_key_digest_blake3": factor["base_hash"],
        "nominal_subspace_dimension": None,
        "geometric_point_count": audit["factor_base_points"],
        "actual_usable_subgroup_points_B": audit["factor_base_points"],
        "subgroup_filtering": "cofactor_projection_with_exact_curve_order; independent_every_orbit_representative_subgroup_check_and_all_points_on_curve",
        "sign_frobenius_quotient": "signed_frobenius_orbit; lambda_from_curve; no partial orbit savings",
        "effective_relation_columns": audit["orbit_columns"],
        "source_sha256": source["rank_fixture_sha256"],
    }
    candidate_record = {
        "field": field,
        "curve": curve,
        "isogeny": "none",
        "endomorphism": {"endo_order_conductor": None, "frobenius_order_conductor": None, "volcano_levels": {}},
        "factor_base": factor_base,
        "point_decomposition": {
            "summands": 4,
            "summation_polynomial_or_chain": "none_group_pair_index",
            "weil_descent_encoding": "none",
            "equation_order": "group_pair_meet_in_the_middle",
            "solver_family": "mitm",
            "implementation_version": source["commit"],
            "source_sha256": source["rank_fixture_sha256"],
            "monomial_order": "none",
            "internal_matrix_kernel": "none",
            "pair_index_mode": run_config["pair_mode"],
            "query_mode": run_config["query_mode"],
            "exact_x_prefilter_bits": factor["support_x_prefilter_bits"],
            "x_prefilter_hashes": factor["support_x_prefilter_hashes"],
            "resource_limit_bytes": CONFIG["resource_cap_bytes"],
            "cache_policy": "one_fresh_support_index_retained_through_single_target",
        },
        "relation_collection": {
            "query_distribution": "independent_uniform_linear_combinations_of_public_G_and_Q",
            "rule": "exact_support_sample_until_full_rank_plus_32_then_one_target_relation",
            "target_mode": run_config["target_mode"],
            "filtering": "exact_pair_support_and_group_verification",
            "duplicate_handling": "incremental_rank_and_duplicate_tracking",
            "stop_criterion": "precompute_rank_matrix_columns_plus_32; target_one_verified_relation",
            "source_sha256": source["rank_fixture_sha256"],
        },
        "relation_linear_algebra": {
            "modulus": r,
            "row_construction": "signed_frobenius_orbit_coefficients_plus_target_scalar_column",
            "orbit_quotient": "signed_frobenius",
            "rank_criterion": "matrix_columns_full_rank_plus_32_surplus_precompute",
            "solver": "gauss",
            "implementation_version": source["commit"],
            "block_parameters": "none",
            "preconditioner": "none",
            "source_sha256": source["rank_fixture_sha256"],
        },
        "target_descent": {
            "policy": "direct_one_relation_over_retained_factor_logs",
            "recursive_solvers": "none",
            "success_rule": "recovered_scalar_replays_public_Q",
            "source_sha256": source["rank_fixture_sha256"],
        },
        "implementation": {
            "repository": source["repository"],
            "commit": source["commit"],
            "rank_fixture_source_sha256": source["rank_fixture_sha256"],
            "rank_fixture_binary_sha256": json.loads((run / f"n{n}-direct.resource.json").read_text())["binary_sha256"],
            "cargo_toml_sha256": source["cargo_toml_sha256"],
            "cargo_lock_sha256": source["cargo_lock_sha256"],
            "effective_flags_from_receipts": {
                "shared_factor_log_precomputation": pre["shared_factor_log_precomputation"],
                "summary_only": pre["summary_only_timing"],
                "construction_only": False,
                "incremental_rank_crosscheck_mode": pre["rank_crosscheck_mode"],
                "post_full_rank_crosscheck": pre["post_full_rank_crosscheck"],
                "required_surplus_relations": pre["required_surplus_relations"],
                "relation_cap_extra": pre["relation_cap_extra"],
                "batch_fixtures": batch["batch_fixtures"],
                "batch_corpus": batch["batch_corpus"] or "none",
                "shared_public_fixture_domain": batch["shared_public_fixture_domain"],
                "shared_public_fixture_offset": batch["shared_public_fixture_offset"],
                "exact_x_prefilter_bits": factor["support_x_prefilter_bits"],
                "x_prefilter_hashes": factor["support_x_prefilter_hashes"],
            },
        },
    }
    candidate_id = f"IC1N{n}Ckb0fb{audit['factor_base_points']}PDP4mitmRCsampleLAgaussTDdirectISO0h{sha(candidate_record)[:12]}"
    candidate = {**candidate_record, "candidate_id": candidate_id}
    workload_record = {
        "curve_id": curve_id,
        "subgroup_order": r,
        "target_count": 1,
        "cold_target_count": 1,
        "warm_target_count": 0,
        "target_point": target["published_q"],
        "precomputation_auxiliary_public_point": pre["published_q"],
        "input_law": "public_synthetic_point_from_preregistered_seed;_scalar_validation_sidecar_only",
        "direct_seed": run_config["direct_seed"],
        "rho_seed": run_config["rho_seed"],
        "rho_effective_fixture_seed": rho["fixture_seed"],
        "precomputation_fixture_seed": pre["fixture_seed"],
        "target_fixture_seed": target["fixture_seed"],
    }
    workload_id = sha(workload_record)[:12]
    workload = {**workload_record, "workload_id": workload_id}
    phases = {
        "target_query": target["fixture_setup_ms"],
        "target_pdp": target["collection_ms"]-target["linear_solve_ms"]-target["solution_validation_ms"],
        "target_relation_check": target["reference_validation_ms"],
        "target_descent": 0.0,
        "target_recovery_check": target["linear_solve_ms"]+target["solution_validation_ms"],
    }
    assert abs(sum(phases.values())-audit["timing_exploratory_ms"]["online_target_exclusive_corrected"]) < 1e-6
    run_id = f"{candidate_id}W{workload_id}R1"
    run_record = {
        "run_id": run_id,
        "candidate_id": candidate_id,
        "workload_id": workload_id,
        "status": audit["status"],
        "host_isolation_receipt": None,
        "timing_class": "exploratory_unisolated_host",
        "primary_target_point": target["published_q"],
        "verified_scalar": target["recovered_fixture_scalar"],
        "rho_reference": {"solver": "signed_frobenius_packed_rho", "source_sha256": source["rho_fixture_sha256"], "public_target_point": rho["published_q"], "verified_scalar": rho["recovered_fixture_scalar"], "online_ms_exploratory": audit["timing_exploratory_ms"]["rho_online"], "worker_count": 1, "resource_cap_bytes": CONFIG["resource_cap_bytes"]},
        "online_exclusive_phase_ms_exploratory": phases,
        "online_ms_exploratory": audit["timing_exploratory_ms"]["online_target_exclusive_corrected"],
        "cold_ms_exploratory": audit["timing_exploratory_ms"]["cold_one_target_exclusive_corrected"],
        "online_speedup": None,
        "cold_speedup": None,
        "factor_base_points": audit["factor_base_points"],
        "folded_columns": audit["orbit_columns"],
        "matrix_columns_including_target": audit["matrix_columns"],
        "precompute_admitted_verified_relations": pre["admitted_relations"],
        "precompute_rank": pre["terminal_rank"],
        "target_relations": target["admitted_relations"],
        "target_support_queries": target["support_queries"],
        "memory_peak_bytes": audit["direct_resource"]["child_peak_rss_bytes"],
        "correctness_certificate": "runs/verification.json",
        "executed_runner_git_commit": "d4e67c34eac8a7f1696a8d974d5836db50d2a789",
        "raw_receipt_prefix": f"runs/n{n}",
    }
    return candidate, workload, run_record


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, default=HERE / "runs")
    p.add_argument("--out-dir", type=Path, default=HERE / "identities")
    args = p.parse_args()
    replay = json.loads((args.run_dir / "verification.json").read_text())
    assert replay["status"] == "PASS_WITH_CENSORED_N53"
    args.out_dir.mkdir(exist_ok=True)
    records_ = []
    for n in (37, 41):
        candidate, workload, run_record = cell_identity(args.run_dir, replay, n)
        write(args.out_dir / f"n{n}-candidate.json", candidate)
        write(args.out_dir / f"n{n}-workload.json", workload)
        write(args.out_dir / f"n{n}-run.json", run_record)
        records_.append({"n":n,"candidate_id":candidate["candidate_id"],"workload_id":workload["workload_id"],"run_id":run_record["run_id"]})
    write(args.out_dir / "index.json", records_)
    print(json.dumps(records_, sort_keys=True))


if __name__ == "__main__":
    main()
