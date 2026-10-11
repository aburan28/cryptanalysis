#!/usr/bin/env python3
"""Summarize independently audited Q1091 zero-prefix stage measurements.

The output is a compact diagnostic for completed shards, not a complete
one-target solve row. Raw receipts remain in the triggering CI run.
"""

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE / "n83_q1090_terminal_wave_audit.json"
PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
SNAPSHOT = (HERE / "runs/q1091_raw_ci_37069216423" /
            "workflow_snapshot.yml")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def summarize(audit_dir, prefix_shards):
    prior = load(PRIOR)
    plan = load(PLAN)
    assert prior["completed_jobs"] == 16
    assert prior["independently_verified_natural_relations"] == 0
    assert plan["prior_Q1090_terminal_audit_sha256"] == sha(PRIOR)
    assert len(plan["query_starts"]) == 64
    assert 1 <= prefix_shards <= 64
    for key in ("curve_id", "candidate_id", "workload_id", "run_id",
                "isogeny", "factor_base_enumerated_set_sha256",
                "actual_usable_points_B_before_folding",
                "signed_frobenius_columns"):
        assert prior[key] == plan[key], key

    rows = []
    for index in range(prefix_shards):
        path = audit_dir / f"shard-{index}.json"
        assert path.is_file(), f"missing audited zero-prefix shard {index}"
        row = load(path)
        assert row["terminal_status"] == "completed_independently_verified_zero"
        assert row["plan_sha256"] == sha(PLAN)
        assert row["workflow_snapshot_sha256"] == sha(SNAPSHOT)
        for key in ("curve_id", "candidate_id", "workload_id", "run_id",
                    "isogeny", "factor_base_enumerated_set_sha256",
                    "actual_usable_points_B_before_folding",
                    "signed_frobenius_columns"):
            assert row[key] == plan[key], key
        assert row["query_start"] == plan["query_starts"][index]
        assert row["query_end_exclusive"] == (row["query_start"] +
                                              plan["query_representatives"])
        assert row["coverage_credit"] == plan["query_representatives"]
        assert row["exact_hit_queries"] == row[
            "independently_verified_relations"] == 0
        assert row["control_exact_hit_queries"] == 0
        assert row.get("control_independently_verified_relations", 0) == 0
        assert row["bloom_positive_queries"] == row[
            "false_positive_queries"]
        assert row["lifted_query_pairs"] == (plan[
            "query_representatives"] * 166)
        artifact_dir = (audit_dir.parent /
                        f"n83-q1091-holdout-M32-R29-shard-{index}")
        full_path = artifact_dir / "full.json"
        sage_path = artifact_dir / "sage_verify.json"
        assert sha(full_path) == row["full_sha256"]
        assert sha(sage_path) == row["sage_verify_sha256"]
        full = load(full_path)
        sage = load(sage_path)
        native = full["native_result"]
        assert sage["receipt_sha256"] == row["full_sha256"]
        assert sage["verified_relation_count"] == 0
        assert not sage["natural_public_target_relation_verified"]
        assert full["target_online_seconds"] == row[
            "target_phase_seconds_on_this_host"]
        assert full["wrapper_subprocess_wall_seconds"] == row[
            "wrapper_subprocess_wall_seconds"]
        assert math.isclose(full["target_online_seconds"],
                            native["query_seconds"] +
                            native["exact_replay_seconds"],
                            rel_tol=0, abs_tol=1e-6)
        assert math.isclose(full["target_independent_filter_build_seconds"],
                            native["allocation_seconds"] +
                            native["build_seconds"],
                            rel_tol=0, abs_tol=1e-6)
        for receipt_key, audit_key in (
            ("bloom_positive_queries", "bloom_positive_queries"),
            ("false_positive_queries", "false_positive_queries"),
            ("peak_rss_bytes", "peak_rss_bytes"),
        ):
            assert native[receipt_key] == row[audit_key]
        rows.append({
            "shard": index,
            "query_start": row["query_start"],
            "target_phase_host_seconds": row[
                "target_phase_seconds_on_this_host"],
            "wrapper_subprocess_host_seconds": row[
                "wrapper_subprocess_wall_seconds"],
            "query_seconds": native["query_seconds"],
            "exact_replay_seconds": native["exact_replay_seconds"],
            "filter_build_seconds": full[
                "target_independent_filter_build_seconds"],
            "bloom_positives": row["bloom_positive_queries"],
            "false_positives": row["false_positive_queries"],
            "peak_rss_bytes": row["peak_rss_bytes"],
            "audit_sha256": sha(path),
        })
    q1091_target = [row["target_phase_host_seconds"] for row in rows]
    q1091_wrapper = [row["wrapper_subprocess_host_seconds"] for row in rows]
    query_seconds = sum(row["query_seconds"] for row in rows)
    replay_seconds = sum(row["exact_replay_seconds"] for row in rows)
    build_seconds = sum(row["filter_build_seconds"] for row in rows)
    target_seconds = sum(q1091_target)
    assert math.isclose(target_seconds, query_seconds + replay_seconds,
                        rel_tol=0, abs_tol=1e-5)
    q1091_lifted = len(rows) * plan["query_representatives"] * 166
    q1091_positives = sum(row["bloom_positives"] for row in rows)
    combined_positives = prior["total_bloom_positives"] + q1091_positives
    combined_lifted = prior["total_lifted_query_pairs"] + q1091_lifted
    return {
        "kind": "n83_q1090_q1091_audited_zero_prefix_stage_diagnostic",
        "status": "partial_verified_zero_prefix_no_fresh_dlp",
        "curve_id": plan["curve_id"],
        "candidate_id": plan["candidate_id"],
        "workload_id": plan["workload_id"],
        "run_id": plan["run_id"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "prior_Q1090_completed_zero_shards": 16,
        "frozen_Q1091_zero_prefix_shards": prefix_shards,
        "Q1091_completed_independently_verified_zero_shards": len(rows),
        "combined_credited_query_representatives": (
            prior["total_query_representatives"] +
            len(rows) * plan["query_representatives"]),
        "combined_lifted_query_pairs": combined_lifted,
        "combined_bloom_positives": combined_positives,
        "combined_false_positives": (prior["total_false_positives"] +
                                     q1091_positives),
        "combined_bloom_positive_fraction_per_lifted_pair": (
            combined_positives / combined_lifted),
        "combined_independently_verified_natural_relations": 0,
        "Q1091_target_phase_host_seconds_sum": target_seconds,
        "Q1091_target_phase_host_seconds_mean": statistics.mean(q1091_target),
        "Q1091_target_phase_host_seconds_min": min(q1091_target),
        "Q1091_target_phase_host_seconds_max": max(q1091_target),
        "Q1091_query_seconds_sum": query_seconds,
        "Q1091_query_seconds_mean": query_seconds / len(rows),
        "Q1091_exact_replay_seconds_sum": replay_seconds,
        "Q1091_exact_replay_seconds_mean": replay_seconds / len(rows),
        "Q1091_target_independent_filter_build_seconds_sum": build_seconds,
        "Q1091_target_independent_filter_build_seconds_mean": (
            build_seconds / len(rows)),
        "Q1091_exact_replay_fraction_of_target_phase": (
            replay_seconds / target_seconds),
        "Q1091_fixed_query_time_hypothetical_replay_free_speedup_ceiling": (
            target_seconds / query_seconds),
        "Q1091_wrapper_subprocess_host_seconds_sum": sum(q1091_wrapper),
        "Q1091_peak_single_job_rss_bytes": max(
            row["peak_rss_bytes"] for row in rows),
        "Q1091_shards": rows,
        "prior_Q1090_terminal_audit_sha256": sha(PRIOR),
        "Q1091_plan_sha256": sha(PLAN),
        "Q1091_workflow_snapshot_sha256": sha(SNAPSHOT),
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "Only the requested consecutive prefix of terminal, independently replayed zero-hit Q1091 artifacts is summarized; later completed shards are excluded from this frozen checkpoint.",
            "Host seconds are summed stage diagnostics, not a continuous one-target online wall interval.",
            "The replay-free speedup ceiling holds query time fixed and makes exact replay cost zero; a changed filter can alter query time, memory, and work, so this is not a predicted variant speedup.",
            "Bloom positives are false positives in these zero-hit receipts; they do not estimate natural relation yield.",
            "The positive fraction divides by lifted signed-query-pair probes and is descriptive for the completed ranges only.",
            "No complete DLP, calibrated field-operation total, or one-target rho speedup follows from this partial diagnostic.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-audits", type=Path, required=True)
    parser.add_argument("--prefix-shards", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite stage diagnostic"
    result = summarize(args.artifact_audits, args.prefix_shards)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "Q1091_completed_independently_verified_zero_shards",
        "combined_credited_query_representatives",
        "combined_bloom_positive_fraction_per_lifted_pair",
        "Q1091_target_phase_host_seconds_mean")}))


if __name__ == "__main__":
    main()
