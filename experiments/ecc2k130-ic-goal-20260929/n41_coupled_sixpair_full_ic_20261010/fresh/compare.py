#!/usr/bin/env python3
"""Bind the independent fresh target's verified IC and rho receipts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    candidate = json.loads((ROOT / "candidate_manifest.json").read_text())
    workload = json.loads((HERE / "canonical_workload.json").read_text())
    collection = json.loads((ROOT / "collection_result.json").read_text())
    factor_audit = json.loads((ROOT / "sage_audit.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    ic = json.loads((HERE / "ic_native.json").read_text())
    rho = json.loads((HERE / "rho_native.json").read_text())
    audit = json.loads((HERE / "sage_audit.json").read_text())
    assert audit["status"] == "PASS_FRESH_ONE_TARGET_IC_AND_RHO_INDEPENDENT_SAGE"
    assert collection["final_rank"] == factor_audit["verified_factor_logs"] == 26
    assert protocol["target"] == audit["target"] == rho["target"]
    assert workload["identity_record"]["targets"] == [protocol["target"]]
    assert ic["status"] == "VERIFIED_SCALAR"
    assert rho["status"] == "VERIFIED_ONE_TARGET_RHO"
    assert ic["recovered_scalar"] == rho["recovered_scalar"] == audit["recovered_scalar"]
    assert sum(ic["exclusive_phase_ns"].values()) == ic["online_ns"]
    assert sum(rho["exclusive_stage_phase_ns"].values()) == rho["rho_online_wall_ns"]
    assert ic["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert rho["peak_rss_bytes"] < protocol["rss_cap_bytes"]
    assert protocol["workers_ic"] == protocol["workers_rho"] == 1
    candidate_id, workload_id = candidate["candidate_id"], workload["workload_id"]
    receipt = {
        "status": "FRESH_PAIRED_VERIFIED_N41_ONE_TARGET_EXPLORATORY_TIMING",
        "candidate_id": candidate_id, "workload_id": workload_id,
        "run_id": f"{candidate_id}W{workload_id}R1",
        "curve_id": workload["curve_id"], "target": audit["target"],
        "target_count": 1, "recovered_scalar": audit["recovered_scalar"],
        "factor_base_points_B": candidate["identity_record"]["factor_base"]["actual_usable_points_B"],
        "folded_columns_K": 26,
        "precomputation": {"setup_queries": collection["attempted_queries"],
                           "verified_relations": factor_audit["setup_relation_count"],
                           "novel_rows": collection["novel_rows"],
                           "verified_factor_logs": factor_audit["verified_factor_logs"],
                           "collection_process_wall_seconds": collection["collection_process_wall_seconds"],
                           "cold_total_ns": None},
        "ic": {"status": ic["status"], "online_ns": ic["online_ns"],
               "exclusive_phase_ns": ic["exclusive_phase_ns"],
               "accepted_probes": ic["accepted_probes"],
               "target_independent_native_setup_ns": ic["setup_ns"],
               "peak_rss_bytes": ic["peak_rss_bytes"],
               "independent_sage_replay": True,
               "independent_sage_check_ns_outside_online": (
                   audit["relation_check_ns_outside_online"]
                   + audit["scalar_recovery_check_ns_outside_online"])},
        "rho": {"status": rho["status"], "online_ns": rho["rho_online_wall_ns"],
                "exclusive_phase_ns": rho["exclusive_stage_phase_ns"],
                "walk_policy": rho["quotient_mode"] + "_16_jumps",
                "collision_policy": "exact_canonical_point",
                "workers": 1, "distinguished_point_memory_bytes": 0,
                "walk_steps": rho["walk_steps"],
                "peak_rss_bytes": rho["peak_rss_bytes"],
                "independent_sage_replay": True},
        "observed_rho_online_ns_div_ic_online_ns": (
            rho["rho_online_wall_ns"] / ic["online_ns"]),
        "timing_class": "exploratory_unisolated_host",
        "isolated_host_receipt": None, "promoted_online_speedup": None,
        "operation_count_boundary": None,
        "source_sha256": {name: sha(path) for name, path in {
            "script": __file__, "candidate_manifest": ROOT / "candidate_manifest.json",
            "workload_manifest": HERE / "canonical_workload.json",
            "protocol": HERE / "protocol.json", "collection": ROOT / "collection_result.json",
            "factor_audit": ROOT / "sage_audit.json", "ic_native": HERE / "ic_native.json",
            "rho_native": HERE / "rho_native.json", "sage_audit": HERE / "sage_audit.json",
        }.items()},
    }
    with (HERE / "paired_comparison.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "ratio": receipt[
        "observed_rho_online_ns_div_ic_online_ns"],
                      "ic_online_ns": ic["online_ns"],
                      "rho_online_ns": rho["rho_online_wall_ns"]}))


if __name__ == "__main__":
    main()
