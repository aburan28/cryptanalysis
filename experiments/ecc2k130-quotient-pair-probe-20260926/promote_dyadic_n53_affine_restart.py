#!/usr/bin/env python3
"""Name the verified n53 affine-restart method without a calibrated speed claim."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt_path = HERE / "runs" / "n53_affine_restart_L128_stage.json"
    input_path = HERE / "runs" / "n53_affine_restart_L128_inputs.json"
    reference_path = HERE / "runs" / "n53_perf_prefix.json"
    receipt = json.loads(receipt_path.read_text())
    reference = json.loads(reference_path.read_text())
    assert receipt["proposal_id"] == "Q1034"
    assert receipt["verified_single_target_dlp"]
    assert receipt["ordinary_quotient_hits"] == 1
    assert receipt["frozen_inputs_sha256"] == sha(input_path)
    assert receipt["curve_id"] == reference["curve_id"]
    assert receipt["curve_identity_record"] == reference[
        "curve_identity_record"]
    base = receipt["factor_base"]
    assert base["actual_usable_points_B_before_folding"] == 13674
    assert base["signed_frobenius_columns"] == 129
    curve = dict(receipt["curve_identity_record"]["curve"])
    curve["curve_id"] = receipt["curve_id"]
    components = {name: sha(HERE / name) for name in (
        "dyadic_affine_restart.py", "compare_batch_x_only.py",
        "dyadic_base_geometry.py", "dyadic_n83_compact_index.py",
        "dyadic_n83_g_pair_witness_index.py", "perf_probe.py",
        "quotient_pair_probe.py", "x_only_cycle.py", "curves.py", "field.py")}
    source_sha = components["dyadic_affine_restart.py"]
    assert receipt["source_sha256"] == source_sha
    record = {
        "field": receipt["curve_identity_record"]["field"],
        "curve": curve,
        "isogeny": "none",
        "endomorphism": {
            "order_conductor": None,
            "frobenius_order_conductor": None,
            "ordinary_volcano_levels": None,
            "degree_2_volcano_level": "not_applicable"},
        "factor_base": {
            "construction": "signed-Frobenius closure of 2^k G for 0<=k<128 and one public Q orbit",
            "seed_points": [curve["generator"], reference["workload"]["target"]],
            "target_dependent": True,
            "G_doubling_window": 128,
            "Q_doubling_window": 1,
            "nominal_seed_count": 2,
            "geometric_point_count": 13674,
            "actual_usable_point_count_B": 13674,
            "enumerated_set_sha256": base["enumerated_set_sha256"],
            "point_coefficient_label_sha256": base[
                "point_coefficient_label_sha256"],
            "subgroup_filtering": "G and Q verified in E[r]; doubling, sign and Frobenius preserve the subgroup",
            "sign_frobenius_quotient_rule": "least cyclic x rotation; sign distinguished by full point replay",
            "signed_frobenius_columns": 129,
            "effective_unknown_log_columns": 1,
            "known_seed_log": 1,
            "unknown_seed": "public target Q"},
        "point_decomposition": {
            "m": 3,
            "summation_chain": "complete unordered two-G pair-sum quotient index, queried by alpha G minus Q",
            "weil_descent_encoding": "none", "equation_order": "none",
            "solver_family": "packed_three_point_quotient_pair_index",
            "implementation_version": "python_source_sha256",
            "source_sha256": source_sha,
            "monomial_order": "none", "internal_matrix_kernel": "none",
            "limits": {"block_length": 4096, "max_blocks": 256},
            "cache_policy": "G-only pair index is built before the target online interval and reused across target blocks"},
        "relation_collection": {
            "query_distribution": "independent OS-random alpha0 uniform Z_r and delta uniform nonzero Z_r for every affine block",
            "rule": "scan alpha_j=alpha0+j*delta, then restart independently after each complete miss",
            "filtering": "verify quotient hit by full point addition and independent scalar replay",
            "duplicate_handling": "retain first witness per signed-Frobenius pair-sum key",
            "stop_criterion": "first verified relation or 256 complete 4096-query blocks",
            "source_sha256": source_sha},
        "relation_linear_algebra": {
            "modulus": str(reference["subgroup_order"]),
            "row_construction": "alpha = a + log_G(Q) mod r",
            "orbit_quotient": "signed-Frobenius coefficient labels",
            "rank_criterion": "the target coefficient is one in the prime subgroup",
            "solver": "gauss", "matrix_shape": [1, 1],
            "implementation_version": "modular subtraction",
            "block_parameters": "none", "preconditioner": "none",
            "source_sha256": source_sha},
        "target_descent": {
            "policy": "direct recovery from a three-point relation containing public Q",
            "recursive_solvers": "none",
            "success_rule": "recovered scalar independently reproduces public Q",
            "stop_rule": "first verified relation or frozen block budget",
            "source_sha256": source_sha},
        "implementation": {
            "source_sha256_by_component": components,
            "algorithm_flags": {
                "G_window": 128, "Q_window": 1,
                "block_length": 4096, "max_blocks": 256,
                "random_law": "independent OS-random alpha0 and nonzero delta per block",
                "packed_binary_search": True,
                "x_only_cyclic_key": True}},
    }
    digest = hashlib.sha256(frozen(record)).hexdigest()[:12]
    candidate_id = ("IC1N53Ckb1fb13674PDP3qpairRCaffineLAgaussTDdirectISO0h"
                    + digest)
    manifest = {
        "candidate_id": candidate_id,
        "identity_record": record,
        "source_proposal_id": "Q1034",
        "source_receipt_sha256": sha(receipt_path),
        "source_receipt": str(receipt_path.relative_to(HERE)),
        "identity_hash_rule": "first 12 lowercase SHA-256 hex of sorted-key compact UTF-8 JSON identity_record"}
    manifest_path = HERE / "candidates" / f"{candidate_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    run = {
        "kind": "candidate_linked_verified_n53_affine_restart_dlp",
        "candidate_id": candidate_id,
        "proposal_id": None,
        "source_proposal_id": "Q1034",
        "workload_id": receipt["workload_id"],
        "run_id": f"{candidate_id}W{receipt['workload_id']}R1",
        "curve_id": receipt["curve_id"],
        "target": reference["workload"]["target"],
        "target_count": 1,
        "actual_usable_base_B": 13674,
        "signed_frobenius_columns": 129,
        "effective_unknown_log_columns": 1,
        "verified_scalar": receipt["recovered_scalar"],
        "scalar_replay_verified": receipt["verified_single_target_dlp"],
        "ordinary_attempts_including_failed": receipt[
            "ordinary_attempts_including_failed"],
        "index_keys": receipt["target_independent_index"]["quotient_keys"],
        "online_one_target_seconds": receipt["online_one_target_seconds"],
        "target_independent_precompute_seconds": receipt[
            "target_independent_precompute_seconds"],
        "cold_group_call_vector": receipt[
            "group_calls_cold_including_input_preflight"],
        "cold_field_api_call_vector": receipt[
            "field_api_calls_cold_including_input_preflight"],
        "total_calibrated_field_operations": None,
        "complete_work_log2": None,
        "paired_rho_online_seconds": None,
        "online_speedup": None,
        "accounting_limit": "verified one-target online interval and logical call vectors; no calibrated common field/bit-operation total or paired same-target rho wall time",
        "manifest_sha256": sha(manifest_path),
        "source_receipt_sha256": sha(receipt_path)}
    run_path = HERE / "runs" / "n53_affine_restart_L128_candidate.json"
    run_path.write_text(json.dumps(run, indent=2) + "\n")
    print(json.dumps({"candidate_id": candidate_id,
                      "run_id": run["run_id"],
                      "verified_scalar": run["verified_scalar"]}))


if __name__ == "__main__":
    main()
