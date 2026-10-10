#!/usr/bin/env python3
"""Reconcile immutable N83 PDP receipts into an exclusive diagnostic ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
GEOMETRY = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_full_w4_geometry_v1/progress.json"
DIRECT_RUNS = (
    "pinned_planted_f0_v2", "unpinned_planted_f0_v1",
    "ordinary_f0_v1", "ordinary_f1_v1", "ordinary_f2_v1", "ordinary_f3_v1",
)
SIGN_RUNS = ("sign_enum_v1", "unpinned_sign_enum_v1")


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def direct_row(name: str) -> dict:
    folder = RUNS / name
    inner_path, outer_path = folder / "receipt.json", folder / "outer_receipt.json"
    inner, outer = read(inner_path), read(outer_path)
    started = read(folder / "started.json")
    assert outer["inner_receipt_sha256"] == sha(inner_path)
    assert inner["mode"] == outer["mode"] == started["mode"]
    assert inner["fiber_index"] == outer["fiber_index"] == started["fiber_index"]
    assert inner["candidate_id"] is outer["candidate_id"] is None
    assert inner["status"] == "BOUNDED_UNKNOWN"
    assert outer["status"] == "INNER_COMPLETE" and outer["guard"] is None
    if inner["mode"] != "pinned_planted":
        assert started["private_fixture_sha256_local_only"] is None
    phases = {
        "circuit_build_ns": inner["circuit_build_wall_ns"],
        "xcnf_write_ns": inner["xcnf_write_wall_ns"],
        "solver_ns": inner["solver_wall_ns"],
    }
    phases["inner_parse_and_overhead_ns"] = inner["attempt_wall_ns"] - sum(phases.values())
    phases["outer_watchdog_and_launch_ns"] = outer["outer_wall_ns"] - inner["attempt_wall_ns"]
    assert min(phases.values()) >= 0 and sum(phases.values()) == outer["outer_wall_ns"]
    return {
        "run": name, "mode": inner["mode"], "fiber_index": inner["fiber_index"],
        "status": inner["status"], "verified_witnesses": 0,
        "public_target_Q": inner["target_Q"],
        "outer_wall_ns": outer["outer_wall_ns"],
        "exclusive_phases_ns": phases,
        "sampled_process_tree_peak_rss_bytes": outer["sampled_process_tree_peak_rss_bytes"],
        "circuit": inner["circuit"],
        "inner_receipt_sha256": sha(inner_path),
        "outer_receipt_sha256": sha(outer_path),
        "xcnf_sha256": inner["xcnf_sha256"],
        "solver_stdout_sha256": inner["solver"]["stdout_sha256"],
    }


def sign_row(name: str) -> dict:
    path = RUNS / name / "receipt.json"
    receipt = read(path)
    assert receipt["candidate_id"] is None
    assert receipt["branch_count"] == len(receipt["branches"])
    assert [branch["branch_index"] for branch in receipt["branches"]] == \
        list(range(receipt["branch_count"]))
    solve_ns = sum(branch["solver"]["solver_wall_ns"] for branch in receipt["branches"])
    overhead_ns = receipt["attempt_wall_ns"] - solve_ns
    assert overhead_ns >= 0
    statuses = sorted({branch["status"] for branch in receipt["branches"]})
    return {
        "run": name, "status": receipt["status"],
        "branch_count": receipt["branch_count"],
        "branch_status_counts": {status: sum(branch["status"] == status
                                      for branch in receipt["branches"])
                                 for status in statuses},
        "attempt_wall_ns": receipt["attempt_wall_ns"],
        "exclusive_phases_ns": {
            "solver_sum_ns": solve_ns,
            "xcnf_variants_verification_and_overhead_ns": overhead_ns,
        },
        "max_sampled_branch_process_tree_rss_bytes": max(
            branch["solver"]["sampled_process_tree_peak_rss_bytes"]
            for branch in receipt["branches"]),
        "receipt_sha256": sha(path),
        "protocol_sha256": receipt["protocol_sha256"],
    }


def main() -> None:
    protocol = read(HERE / "protocol.json")
    geometry = read(GEOMETRY)["last_checkpoint"]
    assert geometry["actual_usable_projected_points_B"] == 1936390
    assert geometry["effective_signed_frobenius_columns"] == 11665
    direct = [direct_row(name) for name in DIRECT_RUNS]
    sign = [sign_row(name) for name in SIGN_RUNS]
    ordinary = [row for row in direct if row["mode"] == "ordinary"]
    assert [row["fiber_index"] for row in ordinary] == list(range(4))
    assert len({tuple(row["public_target_Q"]) for row in ordinary}) == 1
    assert all(row["verified_witnesses"] == 0 for row in ordinary)
    sage = read(RUNS / "sign_enum_v1/sage_replay.json")
    assert sage["status"] == "PASS" and sage["sign_enumeration_receipt_sha256"] == \
        sign[0]["receipt_sha256"]
    assert sign[1]["branch_status_counts"] == {"BOUNDED_UNKNOWN": 32}
    record = {
        "schema_version": 1,
        "kind": "n83_direct_point_stage_diagnostic_cost_ledger",
        "curve_id": "EC1N83Ckb1h2bcb59d56ad6",
        "candidate_id": None,
        "accounting_scope": "Exploratory stage diagnostics on a contended host; four raw fibers are correlated views of one ordinary subgroup target.",
        "public_fixture_sha256": protocol["source_public_fixture_sha256"],
        "direct_point_protocol_sha256": sha(HERE / "protocol.json"),
        "direct_resource_policy": {
            "solver_threads": protocol["solver_threads"],
            "solver_internal_seconds": protocol["solver_internal_seconds"],
            "solver_max_conflicts": protocol["solver_max_conflicts"],
            "outer_wall_seconds": protocol["external_wall_seconds"],
            "max_process_tree_rss_bytes": protocol["max_process_tree_rss_bytes"],
        },
        "actual_usable_factor_base_points_B": geometry["actual_usable_projected_points_B"],
        "effective_signed_frobenius_columns": geometry["effective_signed_frobenius_columns"],
        "factor_base_geometry_sha256": sha(GEOMETRY),
        "direct_runs": direct,
        "sign_enumerations": sign,
        "pinned_sign_sage_replay_sha256": sha(RUNS / "sign_enum_v1/sage_replay.json"),
        "ordinary_panel": {
            "public_target_Q": ordinary[0]["public_target_Q"],
            "raw_fiber_count": 4,
            "verified_witness_count": 0,
            "status_counts": {"BOUNDED_UNKNOWN": 4},
            "sum_outer_wall_ns_diagnostic_only": sum(row["outer_wall_ns"] for row in ordinary),
            "max_sampled_process_tree_peak_rss_bytes": max(
                row["sampled_process_tree_peak_rss_bytes"] for row in ordinary),
            "independent_query_count_for_rate_estimation": 1,
            "verified_natural_relation_rate": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
        },
        "factor_log_matrix_build_ns": None,
        "factor_log_matrix_solve_ns": None,
        "single_target_ic_online_wall_ns": None,
        "paired_same_point_rho_online_wall_ns": None,
        "online_speedup": None,
        "cold_total_wall_ns": None,
        "total_operations": None,
        "S_over_sqrt_r": None,
    }
    (HERE / "COST_LEDGER.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print("PASS: source-bound exclusive stage ledger; four ordinary fibers bounded unknown")


if __name__ == "__main__":
    main()
