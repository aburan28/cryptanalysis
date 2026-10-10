#!/usr/bin/env python3
"""Bind the verified IC and rho runs to one canonical target workload."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "candidate_manifest.json").read_text())
    workload = json.loads((HERE / "canonical_workload.json").read_text())
    collection = json.loads((HERE / "collection_result.json").read_text())
    factor_audit = json.loads((HERE / "sage_audit.json").read_text())
    ic = json.loads((HERE / "online_native.json").read_text())
    ic_audit = json.loads((HERE / "online_sage_audit.json").read_text())
    rho = json.loads((HERE / "rho_native.json").read_text())
    rho_audit = json.loads((HERE / "rho_sage_audit.json").read_text())
    target = workload["identity_record"]["targets"][0]
    assert ic_audit["status"] == "PASS_INDEPENDENT_SAGE_WARM_ONE_TARGET_DLP"
    assert rho_audit["status"] == "PASS_INDEPENDENT_SAGE_SAME_POINT_RHO"
    assert factor_audit["status"] == "PASS_INDEPENDENT_SAGE_N41_FACTOR_LOGS_AND_26_RELATIONS"
    assert collection["final_rank"] == 26
    assert ic["status"] == "VERIFIED_SCALAR"
    assert rho["status"] == "VERIFIED_ONE_TARGET_RHO"
    assert target == ic_audit["target"] == rho_audit["target"] == rho["target"]
    assert ic["recovered_scalar"] == rho["recovered_scalar"] == ic_audit["recovered_scalar"]
    assert sum(ic["exclusive_phase_ns"].values()) == ic["online_ns"]
    assert sum(rho["exclusive_stage_phase_ns"].values()) == rho["rho_online_wall_ns"]
    assert ic["peak_rss_bytes"] < rho["limits"]["peak_rss_bytes"]
    assert rho["peak_rss_bytes"] < rho["limits"]["peak_rss_bytes"]
    candidate_id = manifest["candidate_id"]
    workload_id = workload["workload_id"]
    ratio = rho["rho_online_wall_ns"] / ic["online_ns"]
    receipt = {
        "status": "PAIRED_VERIFIED_N41_ONE_TARGET_EXPLORATORY_TIMING",
        "candidate_id": candidate_id, "workload_id": workload_id,
        "run_id": f"{candidate_id}W{workload_id}R1",
        "curve_id": workload["curve_id"],
        "prior_curve_id_alias_in_source_receipts": manifest["prior_curve_id_alias_in_frozen_stage_receipts"],
        "target_count": 1, "target": target,
        "recovered_scalar": ic["recovered_scalar"],
        "subgroup_order": workload["identity_record"]["subgroup_order"],
        "factor_base_points_B": manifest["identity_record"]["factor_base"]["actual_usable_points_B"],
        "folded_columns_K": manifest["identity_record"]["factor_base"]["effective_columns"],
        "precomputation": {
            "setup_queries": collection["attempted_queries"],
            "verified_relations": factor_audit["setup_relation_count"],
            "novel_rows": collection["novel_rows"],
            "final_rank": collection["final_rank"],
            "verified_factor_logs": factor_audit["verified_factor_logs"],
            "collection_process_wall_seconds": collection["collection_process_wall_seconds"],
            "cold_total_ns": None,
        },
        "ic": {
            "status": ic["status"], "online_ns": ic["online_ns"],
            "exclusive_phase_ns": ic["exclusive_phase_ns"],
            "target_independent_native_setup_ns": ic["setup_ns"],
            "accepted_probes": ic["accepted_probes"],
            "group_hits": ic["group_hits"],
            "peak_rss_bytes": ic["peak_rss_bytes"],
            "independent_sage_replay": True,
        },
        "rho": {
            "status": rho["status"], "online_ns": rho["rho_online_wall_ns"],
            "exclusive_phase_ns": rho["exclusive_stage_phase_ns"],
            "walk_policy": rho["quotient_mode"] + "_16_jumps",
            "collision_policy": "exact_canonical_point",
            "workers": 1, "distinguished_point_memory_bytes": 0,
            "walk_steps": rho["walk_steps"],
            "table_entries": rho["table_entries"],
            "peak_rss_bytes": rho["peak_rss_bytes"],
            "independent_sage_replay": True,
        },
        "observed_rho_online_ns_div_ic_online_ns": ratio,
        "timing_class": "exploratory_unisolated_host",
        "isolated_host_receipt": None,
        "promoted_online_speedup": None,
        "operation_count_boundary": None,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "candidate_manifest": HERE / "candidate_manifest.json",
            "workload_manifest": HERE / "canonical_workload.json",
            "collection": HERE / "collection_result.json",
            "factor_audit": HERE / "sage_audit.json",
            "ic_native": HERE / "online_native.json",
            "ic_audit": HERE / "online_sage_audit.json",
            "rho_native": HERE / "rho_native.json",
            "rho_audit": HERE / "rho_sage_audit.json",
        }.items()},
    }
    with (HERE / "paired_comparison.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "observed_ratio": ratio,
                      "ic_online_ns": ic["online_ns"],
                      "rho_online_ns": rho["rho_online_wall_ns"]}))


if __name__ == "__main__":
    main()
