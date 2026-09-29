#!/usr/bin/env python3
"""Name the complete n53 five-sum pipeline without promoting its work claim."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source_path = HERE / "runs" / "n53_dyadic_five_sum_dlp.json"
    receipt = json.loads(source_path.read_text())
    reference = json.loads((HERE / "runs" / "n53_perf_prefix.json").read_text())
    assert receipt["proposal_id"] == "Q1024"
    assert receipt["verified_single_target_dlp"]
    assert receipt["source_sha256"] == sha(HERE / "dyadic_n53_five_sum_dlp.py")
    assert receipt["curve_id"] == reference["curve_id"]
    assert receipt["target"] == reference["workload"]["target"]
    base = receipt["factor_base"]
    assert base["actual_usable_points_B_before_folding"] == 13568
    curve = dict(receipt["curve_identity_record"]["curve"])
    curve["curve_id"] = receipt["curve_id"]
    components = {name: sha(HERE / name) for name in (
        "dyadic_n53_five_sum_dlp.py", "dyadic_base_geometry.py",
        "quotient_pair_probe.py", "x_only_cycle.py", "curves.py", "field.py")}
    main_sha = components["dyadic_n53_five_sum_dlp.py"]
    record = {
        "field": receipt["curve_identity_record"]["field"],
        "curve": curve,
        "isogeny": "none",
        "endomorphism": {
            "order_conductor": None, "frobenius_order_conductor": None,
            "ordinary_volcano_levels": None,
            "degree_2_volcano_level": "not_applicable"},
        "factor_base": {
            "construction": "signed-Frobenius closure of 2^k G and 2^k Q for 0<=k<64",
            "seed_points": [curve["generator"], receipt["target"]],
            "target_dependent": True,
            "doubling_window": 64,
            "nominal_seed_count": 2,
            "geometric_point_count": 13568,
            "actual_usable_point_count_B": 13568,
            "enumerated_set_sha256": base["enumerated_set_sha256"],
            "point_coefficient_label_sha256": base["point_coefficient_label_sha256"],
            "subgroup_filtering": "both seeds verified in E[r]; doubling, sign, Frobenius preserve subgroup",
            "sign_frobenius_quotient_rule": "least cyclic x rotation; sign identified by x; full witness replay",
            "signed_frobenius_columns": 128,
            "effective_unknown_log_columns": 1,
            "known_seed_log": 1,
            "unknown_seed": "public target Q"},
        "point_decomposition": {
            "m": 5,
            "summation_chain": "complete two-G pair-sum quotient index; sample three Q-base points and look up alpha G minus their sum",
            "weil_descent_encoding": "none", "equation_order": "none",
            "solver_family": "two_plus_three_quotient_pair_index",
            "implementation_version": "python_source_sha256",
            "source_sha256": main_sha,
            "monomial_order": "none", "internal_matrix_kernel": "none",
            "limits": {"max_triple_attempts": receipt["workload"]["max_triple_attempts"]},
            "cache_policy": "target-dependent cold G-pair index; reuse within one target only"},
        "relation_collection": {
            "query_distribution": "one uniform nonzero alpha G; independent uniform target-base triples with replacement",
            "rule": "first verified five-point relation with nonzero target coefficient",
            "filtering": "reject zero target coefficient and group-law replay failures",
            "duplicate_handling": "index stores first witness for each signed-Frobenius pair-sum key",
            "stop_criterion": "one independent row or triple-attempt limit",
            "source_sha256": main_sha},
        "relation_linear_algebra": {
            "modulus": str(reference["subgroup_order"]),
            "row_construction": "alpha = a + b*log_G(Q) mod r",
            "orbit_quotient": "signed Frobenius labels in a,b",
            "rank_criterion": "b nonzero mod prime r", "solver": "gauss",
            "matrix_shape": [1, 1],
            "implementation_version": "Python pow(b,-1,r)",
            "block_parameters": "none", "preconditioner": "none",
            "source_sha256": main_sha},
        "target_descent": {
            "policy": "direct recovery because public target is second factor-base seed",
            "recursive_solvers": "none",
            "success_rule": "[recovered scalar]G equals target",
            "stop_rule": "first verified scalar or frozen triple-attempt limit",
            "source_sha256": main_sha},
        "implementation": {
            "source_sha256_by_component": components,
            "algorithm_flags": {"window": 64,
                                "triple_sampling": "Python Random with replacement",
                                "x_only_cyclic_key": True}},
    }
    digest = hashlib.sha256(frozen(record)).hexdigest()[:12]
    candidate_id = ("IC1N53Ckb1fb13568PDP5q23RCsampleLAgaussTDdirectISO0h"
                    + digest)
    manifest = {
        "candidate_id": candidate_id, "identity_record": record,
        "source_proposal_id": "Q1024",
        "source_receipt_sha256": sha(source_path),
        "source_receipt": str(source_path.relative_to(HERE)),
        "identity_hash_rule": "first 12 lowercase SHA-256 hex of sorted-key compact UTF-8 JSON identity_record"}
    manifest_path = HERE / "candidates" / f"{candidate_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    run = {
        "kind": "candidate_linked_verified_scalar_pilot_with_incomplete_accounting",
        "candidate_id": candidate_id, "proposal_id": None,
        "source_proposal_id": "Q1024",
        "workload_id": receipt["workload_id"],
        "run_id": f"{candidate_id}W{receipt['workload_id']}R1",
        "curve_id": receipt["curve_id"],
        "target": receipt["target"], "target_count": 1,
        "actual_usable_base_B": 13568,
        "signed_frobenius_columns": 128,
        "effective_unknown_log_columns": 1,
        "verified_scalar": receipt["recovered_scalar"],
        "scalar_replay_verified": receipt["verified_single_target_dlp"],
        "triple_attempts_including_failed": receipt["query"][
            "triple_attempts_including_failed"],
        "index_keys": receipt["index_build"]["quotient_keys"],
        "measured_online_wall_seconds_including_target_preflight": receipt[
            "online_wall_seconds"],
        "formal_online_wall_seconds": None,
        "total_calibrated_field_operations": None,
        "complete_work_log2": None,
        "paired_rho_online_seconds": None,
        "online_speedup": None,
        "accounting_limit": "the online interval includes preflight, index and failed queries, but exclusive phase costs do not yet sum to the interval; field operations and paired rho are missing",
        "manifest_sha256": sha(manifest_path),
        "source_receipt_sha256": sha(source_path)}
    run_path = HERE / "runs" / "n53_dyadic_five_sum_candidate.json"
    run_path.write_text(json.dumps(run, indent=2) + "\n")
    print(json.dumps({"candidate_id": candidate_id,
                      "run_id": run["run_id"],
                      "verified_scalar": run["verified_scalar"]}))


if __name__ == "__main__":
    main()
