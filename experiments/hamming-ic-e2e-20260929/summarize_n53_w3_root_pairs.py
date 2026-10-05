#!/usr/bin/env python3
"""Keep every N53 W3-root pair; exclude a reused target from primary results."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
NAMES = ("n53_w3_root_pair_v1", "n53_w3_root_pair_v2",
         "n53_w3_root_pair_v3", "n53_w3_root_pair_v4",
         "n53_w3_root_pair_v5")
OUT = RUNS / "n53_w3_root_pair_summary"
PHASES = ("setup", "isogeny", "factor_base", "precompute", "queries", "pdp",
          "relation_check", "matrix_build", "relation_la", "target_descent",
          "recovery_check")
ONLINE = ("target_query", "target_pdp", "target_relation_check",
          "target_descent", "target_recovery_check")


def read(path):
    return json.loads(path.read_text())


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def contract_row(directory, receipt, ic, replay):
    replay_verified = replay is not None and replay["status"] == "PASS"
    verified = replay_verified and directory.name != "n53_w3_root_pair_v2"
    timing = ic["timing_ms"]
    online_ns = round(timing["target_online_after_reusable_setup"] * 1_000_000) if verified else None
    if verified:
        online = {name: round(timing[source] * 1_000_000) for name, source in (
            ("target_query", "target_query"),
            ("target_pdp", "target_pdp_charged"),
            ("target_relation_check", "target_relation_check"),
            ("target_descent", "target_descent"),
            ("target_recovery_check", "target_recovery_check"))}
        online["target_descent"] += online_ns - sum(online.values())
        assert sum(online.values()) == online_ns and all(value >= 0 for value in online.values())
    else:
        online = dict.fromkeys(ONLINE)
    workload = read(directory / "workload.json")["record"]
    source = read(directory / "candidate.json")["record"]["implementation"]["source_sha256"]
    counts = {"ordinary_queries": ic["rank_attempts"],
              "solved_queries": ic["rank_verified_relations"],
              "verified_decompositions": ic["rank_verified_relations"],
              "verified_relations": ic["rank_verified_relations"],
              "novel_rows": ic["rank_new_rows"], "effective_columns": ic["orbit_columns"],
              "final_rank": ic["rank"], "pdp_attempts": ic["rank_attempts"],
              "pdp_verified": ic["rank_verified_relations"],
              "pdp_proved_unsat": 0, "pdp_timeout": 0, "pdp_budget": 0,
              "pdp_error": ic["rank_failures"], "pdp_lift_rejected": 0}
    assert sum(counts[name] for name in ("pdp_verified", "pdp_proved_unsat", "pdp_timeout",
                                         "pdp_budget", "pdp_error", "pdp_lift_rejected")) == counts["pdp_attempts"]
    return {"schema_version": 2, "kind": "full_dlp" if verified else "stage",
            "status": "complete" if verified else "error", "candidate_id": receipt["candidate_id"],
            "cpu_isolation_status": "unverified_mac_host",
            "controlled_speedup_eligible": False,
            "online_interval_qualification": "in_process_scalar_replay; independent_sage_replay_after_online_unpriced",
            "exclusion_reason": "target_reused_after_harness_failure"
                                if replay_verified and not verified else
                                "harness_wrapper_exit_nonzero" if not replay_verified else None,
            "observed_scalar_replay_verified": replay_verified,
            "proposal_id": None, "workload_id": receipt["workload_id"],
            "run_id": receipt["run_id"],
            "pair_block_id": "W" + receipt["workload_id"] + "R" + receipt["run_id"].rsplit("R", 1)[1],
            "source_curve_ref": receipt["curve_id"], "isogeny_route_ref": "none",
            "profile_id": "n53_weight3_four_summand_root_index",
            "provenance": {"workload_fixture_sha256": digest(workload),
                           "source_sha256": digest(source),
                           "host_id": "sha256:" + hashlib.sha256(
                               receipt["resource_envelope"]["host"].encode()).hexdigest()[:12],
                           "resource_envelope_id": "one_arm64_cpu_worker_120s_unlimited_memory",
                           "calibration_id": "same_host_packed_rust_online_ns_operations_unpriced"},
            "counts": counts, "subgroup_order": str(ic["subgroup_order"]),
            "target_count": 1, "precomputation_ready": verified,
            "target_point_sha256": hashlib.sha256((directory / "target_point.json").read_bytes()).hexdigest(),
            "peak_rss_bytes": receipt["ic"]["process"]["peak_rss_bytes"],
            "wall_ns": receipt["ic"]["process"]["process_wall_ns"],
            "online_phase_wall_ns": online, "online_wall_ns": online_ns,
            "rho_online_wall_ns": round(replay["rho_online_ms"]*1_000_000) if verified else None,
            "verified_scalar": verified, "rho_verified": verified,
            "scalar_certificate_ref": str(directory / "sage_replay.json") if verified else None,
            "phase_operations": dict.fromkeys(PHASES),
            "phase_wall_ns": dict.fromkeys(PHASES),
            "total_operations": None, "rho_operations": None}


def main():
    rows = []
    contract_rows = []
    for name in NAMES:
        directory = RUNS / name
        receipt = read(directory / "receipt.json")
        ic = read(directory / "ic_result.jsonl")
        rho = read(directory / "rho.stdout.txt")
        replay_path = directory / "sage_replay.json"
        replay = read(replay_path) if replay_path.exists() else None
        replay_verified = replay is not None and replay["status"] == "PASS"
        verified = replay_verified and name not in ("n53_w3_root_pair_v2",)
        assert receipt["candidate_id"] == (replay or receipt)["candidate_id"]
        assert receipt["workload_id"] == (replay or receipt)["workload_id"]
        assert ic["target"] == rho["target_point"] == receipt["target_point"]
        row = {
            "candidate_id": receipt["candidate_id"],
            "workload_id": receipt["workload_id"], "run_id": receipt["run_id"],
            "directory": name, "target_point": json.dumps(receipt["target_point"], separators=(",", ":")),
            "status": "VERIFIED_COMPLETE" if verified else
                      "VERIFIED_REUSE_CONTROL" if replay_verified else "HARNESS_FAILURE",
            "failure_detail": "time_l_sysctl_denied" if name.endswith("v1") else
                              "target_reused_after_v1" if name.endswith("v2") else "",
            "target_count": 1, "ic_workers": 1, "rho_workers": 1,
            "wall_limit_seconds_each": receipt["resource_envelope"]["wall_limit_seconds_each"],
            "ic_online_ms": replay["ic_online_ms"] if verified else None,
            "rho_online_ms": replay["rho_online_ms"] if verified else None,
            "rho_over_ic_online": None,
            "observed_rho_over_ic_exploratory": replay["online_speedup"] if verified else None,
            "cpu_isolation_status": "unverified_mac_host",
            "independent_sage_replay_charged_online": False if replay_verified else None,
            "controlled_speedup_eligible": False,
            "raw_ic_online_ms_diagnostic": ic["timing_ms"]["target_online_after_reusable_setup"],
            "raw_rho_online_ms_diagnostic": rho["online_ms"],
            "curve_id": receipt["curve_id"],
            "factor_base_actual_points": ic["factor_base_points"],
            "factor_base_effective_columns": ic["orbit_columns"],
            "factor_base_construct_ms": ic["timing_ms"]["factor_base_construct"],
            "root_index_build_ms": ic["timing_ms"]["index_build"],
            "reusable_setup_ms": ic["timing_ms"]["reusable_setup_total"],
            "regular_index_states": ic["regular_states"],
            "root_table_entries": ic["root_table_entries"],
            "ordinary_query_attempts": ic["rank_attempts"],
            "ordinary_query_verified_relations": ic["rank_verified_relations"],
            "ordinary_query_pdp_failures": ic["rank_failures"],
            "novel_relation_rows": ic["rank_new_rows"],
            "dependent_rows": ic["rank_dependent_rows"],
            "final_rank": ic["rank"],
            "novel_rows_per_query": ic["rank_new_rows"] / ic["rank_attempts"],
            "cost_per_novel_row_ms": ic["timing_ms"]["rank_collection_total"] / ic["rank_new_rows"],
            "relation_collection_ms": ic["timing_ms"]["rank_collection_total"],
            "relation_pdp_wall_ms": ic["timing_ms"]["rank_pdp_wall"],
            "relation_group_check_ms": ic["timing_ms"]["rank_relation_check"],
            "relation_matrix_build_ms": ic["timing_ms"]["rank_matrix_build"],
            "relation_incremental_gauss_ms": ic["timing_ms"]["rank_linear_algebra_incremental"],
            "target_relation_found": ic["target_relation_found"],
            "target_query_ms": ic["timing_ms"]["target_query"],
            "target_pdp_charged_ms": ic["timing_ms"]["target_pdp_charged"],
            "target_relation_check_ms": ic["timing_ms"]["target_relation_check"],
            "target_descent_ms": ic["timing_ms"]["target_descent"],
            "target_recovery_check_ms": ic["timing_ms"]["target_recovery_check"],
            "ic_peak_rss_bytes": receipt["ic"]["process"]["peak_rss_bytes"],
            "rho_peak_rss_bytes": receipt["rho"]["process"]["peak_rss_bytes"],
            "rho_walk_steps": rho["walk_steps"],
            "rho_table_entries": rho["table_entries"],
            "ic_scalar_replay_verified": replay_verified and replay["ic_scalar_replay_verified"],
            "rho_scalar_replay_verified": replay_verified and replay["rho_scalar_replay_verified"],
        }
        rows.append(row)
        contract_rows.append(contract_row(directory, receipt, ic, replay))
    assert len({row["run_id"] for row in rows}) == len(rows)
    assert len({row["candidate_id"] for row in rows}) == 1
    completed = [row for row in rows if row["status"] == "VERIFIED_COMPLETE"]
    assert len(completed) == 3
    assert len({row["workload_id"] for row in completed}) == 3
    assert len({row["target_point"] for row in completed}) == 3
    ratios = [row["observed_rho_over_ic_exploratory"] for row in completed]
    yields = [row["novel_rows_per_query"] for row in completed]
    summary = {
        "kind": "n53_w3_root_independent_one_target_pairs",
        "candidate_id": completed[0]["candidate_id"],
        "curve_id": completed[0]["curve_id"],
        "all_run_rows": len(rows), "harness_failures": sum(row["status"] == "HARNESS_FAILURE" for row in rows),
        "verified_reuse_controls": sum(row["status"] == "VERIFIED_REUSE_CONTROL" for row in rows),
        "verified_one_target_pairs": len(completed),
        "different_frozen_targets": len({row["target_point"] for row in completed}),
        "controlled_online_speedup": None,
        "controlled_speedup_eligible_pairs": 0,
        "cpu_isolation_status": "unverified_mac_host",
        "independent_sage_replay_charged_online": False,
        "observed_median_ic_in_process_online_ms_exploratory": statistics.median(
            row["ic_online_ms"] for row in completed),
        "observed_ic_in_process_online_ms_range_exploratory": [
            min(row["ic_online_ms"] for row in completed),
            max(row["ic_online_ms"] for row in completed)],
        "observed_median_rho_online_ms_exploratory": statistics.median(
            row["rho_online_ms"] for row in completed),
        "observed_rho_online_ms_range_exploratory": [
            min(row["rho_online_ms"] for row in completed),
            max(row["rho_online_ms"] for row in completed)],
        "observed_median_rho_over_ic_exploratory": statistics.median(ratios),
        "observed_paired_ratio_range_exploratory": [min(ratios), max(ratios)],
        "verified_ordinary_queries": sum(row["ordinary_query_verified_relations"] for row in completed),
        "ordinary_query_attempts": sum(row["ordinary_query_attempts"] for row in completed),
        "ordinary_query_generalization_rate": None,
        "novel_rows": sum(row["novel_relation_rows"] for row in completed),
        "controlled_paired_cost_ci95": None,
        "novel_row_yield_per_query_range": [min(yields), max(yields)],
        "four_point_multisets_with_repetition": "12551410757022501",
        "mean_four_point_multisets_per_subgroup_element": "596.4122274090428",
        "uncertainty": "Three selected target seeds and an adaptive rank-stopped relation stream do not support a population yield interval. No CPU isolation receipt exists, so paired costs have no controlled confidence interval. Independent Sage replay was outside the recorded online interval and its cost was not measured.",
        "claim": "Independent Sage replay validates the three N53 DLP answers and all recorded relation witnesses. The archived IC and rho timings are exploratory process-internal diagnostics; controlled online speedup and general ordinary-query yield are unknown. This is not FC-Hamming SAT or N83 evidence.",
    }
    OUT.mkdir(exist_ok=True)
    with (OUT / "rows.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "contract_v2.jsonl").write_text("".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in contract_rows))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
