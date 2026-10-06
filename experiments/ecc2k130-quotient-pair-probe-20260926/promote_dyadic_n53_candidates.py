#!/usr/bin/env python3
"""Issue exact IC1 identities for the two verified n53 target-seeded pilots.

The linked pilot timings lack a calibrated total operation count and omit
preflight target membership validation.  Promotion names the complete
implemented method; it does not promote either run to a full work or rho
comparison.
"""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = {
    16: ("Q1019", "dyadic_n53_target_seed_dlp.py",
         "runs/n53_dyadic_target_seed_dlp.json"),
    64: ("Q1021", "dyadic_n53_target_seed_dlp_w64.py",
         "runs/n53_dyadic_target_seed_dlp_w64.json"),
}


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(window):
    proposal, source_name, receipt_name = SOURCE[window]
    receipt_path = HERE / receipt_name
    receipt = json.loads(receipt_path.read_text())
    reference = json.loads((HERE / "runs" / "n53_perf_prefix.json").read_text())
    assert receipt["proposal_id"] == proposal
    assert receipt["status"] == "verified_dlp"
    assert receipt["verified_single_target_dlp"]
    assert receipt["source_sha256"] == sha(HERE / source_name)
    assert receipt["curve_id"] == reference["curve_id"]
    assert receipt["target"] == reference["workload"]["target"]
    assert receipt["factor_base"]["actual_usable_points_B_before_folding"] == 4 * 53 * window
    source_hashes = {name: sha(HERE / name) for name in (
        source_name, "dyadic_base_geometry.py", "dyadic_n53_relation_probe.py",
        "batch_x_only.py", "x_only_cycle.py", "cycle_canonical.py",
        "curves.py", "field.py")}
    curve_record = dict(reference["curve_identity_record"]["curve"])
    curve_record["curve_id"] = reference["curve_id"]
    base = receipt["factor_base"]
    target = receipt["target"]
    record = {
        "field": reference["curve_identity_record"]["field"],
        "curve": curve_record,
        "isogeny": "none",
        "endomorphism": {
            "order_conductor": None,
            "frobenius_order_conductor": None,
            "ordinary_volcano_levels": None,
            "degree_2_volcano_level": "not_applicable",
        },
        "factor_base": {
            "construction": "signed-Frobenius closure of 2^k G and 2^k Q for 0<=k<L",
            "seed_points": [curve_record["generator"], target],
            "target_dependent": True,
            "doubling_window": window,
            "nominal_seed_count": 2,
            "geometric_point_count": base["actual_usable_points_B_before_folding"],
            "actual_usable_point_count_B": base["actual_usable_points_B_before_folding"],
            "enumerated_set_sha256": base["enumerated_set_sha256"],
            "point_coefficient_label_sha256": base["point_coefficient_label_sha256"],
            "subgroup_filtering": "both seeds verified in E[r]; doubling, sign, Frobenius preserve subgroup",
            "sign_frobenius_quotient_rule": "least cyclic x rotation; sign identified by x; full witness replay",
            "signed_frobenius_columns": base["signed_frobenius_columns"],
            "effective_unknown_log_columns": 1,
            "known_seed_log": 1,
            "unknown_seed": "public target Q",
        },
        "point_decomposition": {
            "m": 4,
            "summation_chain": "two group-law pair sums and target complement lookup",
            "weil_descent_encoding": "none",
            "equation_order": "none",
            "solver_family": "complete_quotient_pair_index",
            "implementation_version": "python_source_sha256",
            "source_sha256": source_hashes["dyadic_n53_relation_probe.py"],
            "monomial_order": "none",
            "internal_matrix_kernel": "none",
            "limits": {"max_known_log_queries": len(receipt["workload"]["query_scalars"])},
            "cache_policy": "target-dependent cold index; reuse within one target only",
        },
        "relation_collection": {
            "query_distribution": "uniform nonzero known scalar alpha times G; frozen scalar stream in workload",
            "rule": "first verified four-point relation with nonzero target coefficient",
            "filtering": "reject zero target coefficient and group-law replay failures",
            "duplicate_handling": "index stores first witness for each quotient pair-sum key",
            "stop_criterion": "one independent row or query limit",
            "source_sha256": source_hashes[source_name],
        },
        "relation_linear_algebra": {
            "modulus": str(reference["subgroup_order"]),
            "row_construction": "alpha = a + b*log_G(Q) mod r",
            "orbit_quotient": "signed Frobenius labels in a,b",
            "rank_criterion": "b nonzero mod prime r",
            "solver": "gauss",
            "matrix_shape": [1, 1],
            "implementation_version": "Python pow(b,-1,r)",
            "block_parameters": "none",
            "preconditioner": "none",
            "source_sha256": source_hashes[source_name],
        },
        "target_descent": {
            "policy": "direct recovery because public target is second factor-base seed",
            "recursive_solvers": "none",
            "success_rule": "[recovered scalar]G equals target",
            "stop_rule": "first verified scalar or frozen query limit",
            "source_sha256": source_hashes[source_name],
        },
        "implementation": {
            "source_sha256_by_component": {
                "main": source_hashes[source_name],
                "base": source_hashes["dyadic_base_geometry.py"],
                "pair_probe": source_hashes["dyadic_n53_relation_probe.py"],
                "batch_complement": source_hashes["batch_x_only.py"],
                "x_key": source_hashes["x_only_cycle.py"],
                "cyclic_coordinate": source_hashes["cycle_canonical.py"],
                "curve_arithmetic": source_hashes["curves.py"],
                "field_arithmetic": source_hashes["field.py"],
            },
            "algorithm_flags": {"window": window, "batch_complements": True,
                                "x_only_cyclic_key": True},
        },
    }
    b = base["actual_usable_points_B_before_folding"]
    digest = hashlib.sha256(frozen(record)).hexdigest()[:12]
    candidate_id = (f"IC1N53Ckb1fb{b}PDP4qpairRCsampleLAgaussTDdirectISO0h{digest}")
    manifest = {"candidate_id": candidate_id, "identity_record": record,
                "source_proposal_id": proposal,
                "source_receipt_sha256": sha(receipt_path),
                "source_receipt": receipt_name,
                "identity_hash_rule": "first 12 lowercase SHA-256 hex of sorted-key compact UTF-8 JSON identity_record"}
    candidate_dir = HERE / "candidates"
    candidate_dir.mkdir(exist_ok=True)
    manifest_path = candidate_dir / f"{candidate_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    run = {
        "kind": "candidate_linked_verified_scalar_pilot_with_incomplete_accounting",
        "candidate_id": candidate_id, "proposal_id": None,
        "source_proposal_id": proposal,
        "workload_id": receipt["workload_id"],
        "run_id": f"{candidate_id}W{receipt['workload_id']}R1",
        "curve_id": receipt["curve_id"],
        "target": target, "target_count": 1,
        "actual_usable_base_B": b,
        "signed_frobenius_columns": base["signed_frobenius_columns"],
        "effective_unknown_log_columns": 1,
        "verified_scalar": receipt["recovered_scalar"],
        "scalar_replay_verified": receipt["verified_single_target_dlp"],
        "ordinary_query_count": len(receipt["query_rows"]),
        "complete_miss_count": sum(row["ordinary_query"]["status"] ==
                                   "complete_index_miss" for row in receipt["query_rows"]),
        "pair_complement_probes_including_failed": receipt[
            "total_pair_complement_probes"],
        "index_keys": receipt["index_build"]["quotient_keys"],
        "measured_interval_seconds_after_preflight": receipt["online_wall_seconds"],
        "target_preflight_membership_time_seconds": None,
        "formal_online_wall_seconds": None,
        "total_calibrated_field_operations": None,
        "complete_work_log2": None,
        "paired_rho_online_seconds": None,
        "online_speedup": None,
        "accounting_limit": "preflight target subgroup validation preceded the timed interval; field operations and a paired rho run are missing",
        "manifest_sha256": sha(manifest_path),
        "source_receipt_sha256": sha(receipt_path),
    }
    out = HERE / "runs" / f"n53_dyadic_candidate_w{window}.json"
    out.write_text(json.dumps(run, indent=2) + "\n")
    return candidate_id, run["measured_interval_seconds_after_preflight"]


def main():
    print(json.dumps({window: build(window) for window in SOURCE}, indent=2))


if __name__ == "__main__":
    main()
