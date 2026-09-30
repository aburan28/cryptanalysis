#!/usr/bin/env python3
"""Keep every N53 W3-root pair, including the failed harness row."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
NAMES = ("n53_w3_root_pair_v1", "n53_w3_root_pair_v2",
         "n53_w3_root_pair_v3", "n53_w3_root_pair_v4")
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


def wilson95(successes, trials):
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z*z/trials
    center = (p + z*z/(2*trials)) / denominator
    half = z*math.sqrt(p*(1-p)/trials + z*z/(4*trials*trials))/denominator
    return [max(0.0, center-half), min(1.0, center+half)]


def bootstrap95_geometric(values):
    rng = random.Random(53053)
    logs = [math.log(value) for value in values]
    draws = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs))))
                   for _ in range(10000))
    return [draws[249], draws[9749]]


def contract_row(directory, receipt, ic, replay):
    verified = replay is not None and replay["status"] == "PASS"
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
        verified = replay is not None and replay["status"] == "PASS"
        assert receipt["candidate_id"] == (replay or receipt)["candidate_id"]
        assert receipt["workload_id"] == (replay or receipt)["workload_id"]
        assert ic["target"] == rho["target_point"] == receipt["target_point"]
        row = {
            "candidate_id": receipt["candidate_id"],
            "workload_id": receipt["workload_id"], "run_id": receipt["run_id"],
            "directory": name, "target_point": json.dumps(receipt["target_point"], separators=(",", ":")),
            "status": "VERIFIED_COMPLETE" if verified else "HARNESS_FAILURE",
            "failure_detail": "time_l_sysctl_denied" if name.endswith("v1") else "",
            "target_count": 1, "ic_workers": 1, "rho_workers": 1,
            "wall_limit_seconds_each": receipt["resource_envelope"]["wall_limit_seconds_each"],
            "ic_online_ms": replay["ic_online_ms"] if verified else None,
            "rho_online_ms": replay["rho_online_ms"] if verified else None,
            "rho_over_ic_online": replay["online_speedup"] if verified else None,
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
            "ic_scalar_replay_verified": verified and replay["ic_scalar_replay_verified"],
            "rho_scalar_replay_verified": verified and replay["rho_scalar_replay_verified"],
        }
        rows.append(row)
        contract_rows.append(contract_row(directory, receipt, ic, replay))
    assert len({row["run_id"] for row in rows}) == len(rows)
    assert len({row["candidate_id"] for row in rows}) == 1
    completed = [row for row in rows if row["status"] == "VERIFIED_COMPLETE"]
    assert len(completed) == 3
    assert len({row["workload_id"] for row in completed}) == 3
    assert len({row["target_point"] for row in completed}) == 3
    ratios = [row["rho_over_ic_online"] for row in completed]
    yields = [row["novel_rows_per_query"] for row in completed]
    summary = {
        "kind": "n53_w3_root_independent_one_target_pairs",
        "candidate_id": completed[0]["candidate_id"],
        "curve_id": completed[0]["curve_id"],
        "all_run_rows": len(rows), "harness_failures": len(rows) - len(completed),
        "verified_one_target_pairs": len(completed),
        "different_frozen_targets": len({row["target_point"] for row in completed}),
        "median_ic_online_ms": statistics.median(row["ic_online_ms"] for row in completed),
        "ic_online_ms_range": [min(row["ic_online_ms"] for row in completed),
                               max(row["ic_online_ms"] for row in completed)],
        "median_rho_online_ms": statistics.median(row["rho_online_ms"] for row in completed),
        "rho_online_ms_range": [min(row["rho_online_ms"] for row in completed),
                                max(row["rho_online_ms"] for row in completed)],
        "median_paired_rho_over_ic": statistics.median(ratios),
        "paired_ratio_range": [min(ratios), max(ratios)],
        "verified_ordinary_queries": sum(row["ordinary_query_verified_relations"] for row in completed),
        "ordinary_query_attempts": sum(row["ordinary_query_attempts"] for row in completed),
        "verified_query_rate_wilson95_naive": wilson95(
            sum(row["ordinary_query_verified_relations"] for row in completed),
            sum(row["ordinary_query_attempts"] for row in completed)),
        "novel_rows": sum(row["novel_relation_rows"] for row in completed),
        "novel_row_rate_wilson95_naive": wilson95(
            sum(row["novel_relation_rows"] for row in completed),
            sum(row["ordinary_query_attempts"] for row in completed)),
        "geometric_mean_paired_rho_over_ic": math.exp(statistics.mean(math.log(x) for x in ratios)),
        "paired_ratio_bootstrap95": bootstrap95_geometric(ratios),
        "novel_row_yield_per_query_range": [min(yields), max(yields)],
        "uncertainty": "The paired 95% interval is a three-target percentile bootstrap and is exploratory. Wilson query-rate intervals assume independent Bernoulli attempts, which this adaptive rank-stopped stream does not establish; use them only as descriptive diagnostics.",
        "claim": "The root-index IC completed all three N53 targets, but rho was faster on every paired online wall clock. These results do not measure FC-Hamming SAT scaling or N83.",
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
