#!/usr/bin/env python3
"""Reconcile matched N83 direct-mask and indexed-mask PDP stage receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DIRECT = HERE.parent / "n83-direct-point-pdp-20261006"
NAMES = ("pinned_planted_f0_v1", "unpinned_planted_f0_v1",
         "ordinary_f0_v1", "ordinary_f1_v1", "ordinary_f2_v1", "ordinary_f3_v1")


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row(root: Path, name: str) -> dict:
    folder = root / "runs" / name
    inner_path = folder / "receipt.json"
    outer_path = folder / "outer_receipt.json"
    inner, outer = read(inner_path), read(outer_path)
    started = read(folder / "started.json")
    assert outer["inner_receipt_sha256"] == sha(inner_path)
    assert inner["mode"] == outer["mode"] == started["mode"]
    assert inner["fiber_index"] == outer["fiber_index"] == started["fiber_index"]
    assert inner["candidate_id"] is outer["candidate_id"] is None
    assert outer["guard"] is None and outer["status"] == "INNER_COMPLETE"
    assert inner["status"] == "BOUNDED_UNKNOWN"
    if inner["mode"] != "pinned_planted":
        assert started["private_fixture_sha256_local_only"] is None
    phases = {
        "circuit_build_ns": inner["circuit_build_wall_ns"],
        "xcnf_write_ns": inner["xcnf_write_wall_ns"],
        "solver_ns": inner["solver_wall_ns"],
    }
    phases["inner_residual_ns"] = inner["attempt_wall_ns"] - sum(phases.values())
    phases["outer_residual_ns"] = outer["outer_wall_ns"] - inner["attempt_wall_ns"]
    assert min(phases.values()) >= 0 and sum(phases.values()) == outer["outer_wall_ns"]
    return {
        "run": name,
        "mode": inner["mode"], "fiber_index": inner["fiber_index"],
        "status": inner["status"],
        "target_Q": inner["target_Q"],
        "circuit": inner["circuit"],
        "xcnf_bytes": inner["xcnf_bytes"],
        "xcnf_sha256": inner["xcnf_sha256"],
        "outer_wall_ns": outer["outer_wall_ns"],
        "exclusive_phases_ns": phases,
        "sampled_process_tree_peak_rss_bytes": outer["sampled_process_tree_peak_rss_bytes"],
        "inner_receipt_sha256": sha(inner_path),
        "outer_receipt_sha256": sha(outer_path),
    }


def sign_row(root: Path) -> dict:
    receipt_path = root / "runs/sign_enum_v1/receipt.json"
    sage_path = root / "runs/sign_enum_v1/sage_replay.json"
    receipt, sage = read(receipt_path), read(sage_path)
    assert receipt["status"] == "SAT_GROUP_VERIFIED_PENDING_SAGE"
    assert sage["status"] == "PASS"
    assert sage["sign_enumeration_receipt_sha256"] == sha(receipt_path)
    assert receipt["candidate_id"] is None
    solve_ns = sum(branch["solver"]["solver_wall_ns"]
                   for branch in receipt["branches"])
    assert receipt["attempt_wall_ns"] >= solve_ns
    return {
        "branch_count": receipt["branch_count"],
        "sat_branch": next(branch["branch_index"] for branch in receipt["branches"]
                           if branch["status"] == "SAT_GROUP_VERIFIED_PENDING_SAGE"),
        "solver_reported_unsat_count": sum(branch["status"] == "UNSAT"
                                              for branch in receipt["branches"]),
        "independent_sage_status": sage["status"],
        "complete_wall_ns": receipt["attempt_wall_ns"],
        "solver_sum_ns": solve_ns,
        "variant_and_check_residual_ns": receipt["attempt_wall_ns"] - solve_ns,
        "receipt_sha256": sha(receipt_path),
        "sage_replay_sha256": sha(sage_path),
    }


def main() -> None:
    old = read(DIRECT / "protocol.json")
    new = read(HERE / "protocol.json")
    same = ("curve_id", "source_public_fixture_sha256",
            "full_w34_representatives_sha256", "solver_binary_sha256",
            "solver_threads", "solver_internal_seconds",
            "solver_max_conflicts", "external_wall_seconds",
            "max_process_tree_rss_bytes")
    assert all(old[key] == new[key] for key in same)
    direct_names = ("pinned_planted_f0_v2",) + NAMES[1:]
    direct = [row(DIRECT, name) for name in direct_names]
    indexed = [row(HERE, name) for name in NAMES]
    for a, b in zip(direct, indexed):
        assert a["mode"] == b["mode"] and a["fiber_index"] == b["fiber_index"]
        assert a["target_Q"] == b["target_Q"]
    direct_ordinary = direct[2:]
    indexed_ordinary = indexed[2:]
    assert [item["fiber_index"] for item in direct_ordinary] == list(range(4))
    assert len({tuple(item["target_Q"]) for item in direct_ordinary}) == 1
    assert all(item["status"] == "BOUNDED_UNKNOWN" for item in
               direct_ordinary + indexed_ordinary)
    record = {
        "schema_version": 1,
        "kind": "n83_w34_paired_pdp_stage_diagnostic",
        "curve_id": new["curve_id"],
        "candidate_id": None,
        "public_fixture_sha256": new["source_public_fixture_sha256"],
        "measured_factor_base_representatives_sha256":
            new["full_w34_representatives_sha256"],
        "actual_usable_projected_points_B": new["actual_usable_projected_points_B"],
        "effective_signed_frobenius_columns": new["effective_signed_frobenius_columns"],
        "matched_resource_policy": {key: new[key] for key in same[3:]},
        "direct_mask": {"protocol_sha256": sha(DIRECT / "protocol.json"),
                        "runs": direct, "pinned_sign_control": sign_row(DIRECT)},
        "indexed_factor": {"protocol_sha256": sha(HERE / "protocol.json"),
                           "runs": indexed, "pinned_sign_control": sign_row(HERE)},
        "ordinary_panel": {
            "public_target_Q": direct_ordinary[0]["target_Q"],
            "raw_fibers_of_one_target": 4,
            "independent_query_count_for_rate_estimation": 1,
            "direct_verified_relations": 0,
            "indexed_verified_relations": 0,
            "direct_status_counts": {"BOUNDED_UNKNOWN": 4},
            "indexed_status_counts": {"BOUNDED_UNKNOWN": 4},
            "direct_sum_outer_wall_ns_diagnostic_only": sum(
                item["outer_wall_ns"] for item in direct_ordinary),
            "indexed_sum_outer_wall_ns_diagnostic_only": sum(
                item["outer_wall_ns"] for item in indexed_ordinary),
            "natural_relation_yield": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
        },
        "cpu_isolation_receipt": None,
        "controlled_cpu_speedup": None,
        "single_target_ic_online_wall_ns": None,
        "paired_rho_online_wall_ns": None,
        "ic_online_speedup": None,
        "cold_total_wall_ns": None,
        "total_operations": None,
    }
    (HERE / "COST_COMPARISON.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")
    print("PASS: paired source-bound PDP stage costs; both ordinary panels bounded unknown")


if __name__ == "__main__":
    main()
