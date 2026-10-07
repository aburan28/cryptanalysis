#!/usr/bin/env python3
"""Reconcile source-bound N83 point-circuit stage receipts without speed claims."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEXED = HERE.parent / "n83-indexed-factor-pdp-20261006"
DIRECT = HERE.parent / "n83-direct-point-pdp-20261006"
NAMES = ("pinned_planted_f0", "unpinned_planted_f0",
         "ordinary_f0", "ordinary_f1", "ordinary_f2", "ordinary_f3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def row(folder: Path) -> dict:
    receipt_path = folder / "receipt.json"
    outer_path = folder / "outer_receipt.json"
    inner = read(receipt_path)
    outer = read(outer_path)
    started = read(folder / "started.json")
    outer_started = read(folder / "outer_started.json")
    assert outer["inner_receipt_sha256"] == sha(receipt_path)
    assert outer["outer_started_sha256"] == sha(folder / "outer_started.json")
    assert inner["started_sha256"] == sha(folder / "started.json")
    assert inner["mode"] == outer["mode"] == started["mode"] == outer_started["mode"]
    assert inner["fiber_index"] == outer["fiber_index"] == started["fiber_index"]
    assert inner["target_Q"] == read(HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json")[inner["target_kind"]]["target_Q"]
    assert inner["candidate_id"] is outer["candidate_id"] is None
    if folder.parent == HERE / "runs":
        source_paths = {
            "runner": HERE / "run_slope_branch.py",
            "indexed_factor": INDEXED / "indexed_factor.py",
            "slope_witness_circuit": HERE / "slope_witness_circuit.py",
            "generic_circuit": HERE.parent / "hamming-ic-e2e-20260929/circuit.py",
            "gf2n": HERE.parent / "pdp-scaling/gf2n.py",
            "model_verifier": HERE.parent / "hamming-ic-e2e-20260929/run_n83_w34_sat_branch.py",
        }
        assert started["source_sha256"] == {
            key: sha(path) for key, path in source_paths.items()
        }
        assert outer_started["watchdog_sha256"] == sha(HERE / "bounded_slope.py")
        assert started["protocol_sha256"] == outer["protocol_sha256"] == sha(HERE / "protocol.json")
    with gzip.open(folder / "solver.stdout.txt.gz", "rb") as solver_stdout:
        assert hashlib.sha256(solver_stdout.read()).hexdigest() == \
            inner["solver"]["stdout_sha256"]
    assert sha(folder / "producer.stdout.txt") == outer["producer_stdout_sha256"]
    assert outer["guard"] is None and outer["status"] == "INNER_COMPLETE"
    runtime_path = folder / "sage_runtime_info.json"
    if "sage_runtime_info_sha256" in outer_started:
        assert runtime_path.is_file()
        assert outer_started["sage_runtime_info_sha256"] == sha(runtime_path)
    if inner["mode"] != "pinned_planted":
        assert started["private_fixture_sha256_local_only"] is None
    phases = {
        "circuit_build_ns": inner["circuit_build_wall_ns"],
        "xcnf_write_ns": inner["xcnf_write_wall_ns"],
        "solver_ns": inner["solver_wall_ns"],
    }
    phases["inner_residual_ns"] = inner["attempt_wall_ns"] - sum(phases.values())
    phases["outer_residual_ns"] = outer["outer_wall_ns"] - inner["attempt_wall_ns"]
    assert min(phases.values()) >= 0
    assert sum(phases.values()) == outer["outer_wall_ns"]
    return {
        "run": folder.name,
        "mode": inner["mode"],
        "fiber_index": inner["fiber_index"],
        "target_Q": inner["target_Q"],
        "status": inner["status"],
        "group_verified": inner.get("group_verified", False),
        "circuit": inner["circuit"],
        "xcnf_bytes": inner["xcnf_bytes"],
        "xcnf_sha256": inner["xcnf_sha256"],
        "outer_wall_ns": outer["outer_wall_ns"],
        "exclusive_phases_ns": phases,
        "sampled_process_tree_cpu_seconds": outer["sampled_process_tree_cpu_seconds"],
        "sampled_process_tree_peak_rss_bytes": outer["sampled_process_tree_peak_rss_bytes"],
        "sage_runtime_info_sha256": sha(runtime_path) if runtime_path.is_file() else None,
        "inner_receipt_sha256": sha(receipt_path),
        "outer_receipt_sha256": sha(outer_path),
    }


def main() -> None:
    new = read(HERE / "protocol.json")
    old = read(INDEXED / "protocol.json")
    direct_protocol = read(DIRECT / "protocol.json")
    controlled = ("curve_id", "source_public_fixture_sha256",
                  "full_w34_representatives_sha256", "solver_binary_sha256",
                  "solver_threads", "solver_internal_seconds",
                  "solver_max_conflicts", "external_wall_seconds",
                  "max_process_tree_rss_bytes")
    assert all(new[key] == old[key] == direct_protocol[key] for key in controlled)
    assert all(new[key] == old[key] for key in
               ("actual_usable_projected_points_B", "effective_signed_frobenius_columns"))
    new_names = ("pinned_planted_f0_v2", "unpinned_planted_f0_v1",
                 "ordinary_f0_v1", "ordinary_f1_v1", "ordinary_f2_v1",
                 "ordinary_f3_v1")
    old_names = ("pinned_planted_f0_v1", "unpinned_planted_f0_v1",
                 "ordinary_f0_v1", "ordinary_f1_v1", "ordinary_f2_v1",
                 "ordinary_f3_v1")
    direct_names = ("pinned_planted_f0_v2",) + old_names[1:]
    panels = {
        "direct_mask": [row(DIRECT / "runs" / name) for name in direct_names],
        "indexed_factor": [row(INDEXED / "runs" / name) for name in old_names],
        "slope_witness": [row(HERE / "runs" / name) for name in new_names],
    }
    for slot in range(6):
        group = [runs[slot] for runs in panels.values()]
        assert len({(r["mode"], r["fiber_index"], tuple(r["target_Q"]))
                    for r in group}) == 1
    for runs in panels.values():
        assert [r["fiber_index"] for r in runs[2:]] == list(range(4))
        assert len({tuple(r["target_Q"]) for r in runs[2:]}) == 1
    failed_path = HERE / "runs/pinned_planted_f0_v1/outer_receipt.json"
    failed = read(failed_path)
    assert failed["status"] == "RESOURCE_GUARD" and failed["guard"] == "process_inspection_error"
    assert failed["inner_receipt_sha256"] is None
    full_path = HERE / "runs/fully_pinned_planted_f0_v1/receipt.json"
    full = read(full_path)
    assert full["status"] == "BOUNDED_UNKNOWN"
    with gzip.open(full_path.parent / "solver.stdout.txt.gz", "rb") as solver_stdout:
        assert hashlib.sha256(solver_stdout.read()).hexdigest() == \
            full["solver_stdout_sha256"]
    planted_path = HERE / "runs/known_boolean_witness_v1/receipt.json"
    sage_path = HERE / "runs/known_boolean_witness_v1/sage_replay.json"
    planted = read(planted_path)
    sage = read(sage_path)
    assert planted["status"] == "BOOLEAN_MODEL_VERIFIED_PENDING_SAGE"
    assert sage["status"] == "PASS" and sage["receipt_sha256"] == sha(planted_path)
    assert sage["sage_runtime_info_sha256"] == sha(sage_path.parent / "sage_replay_runtime_info.json")
    assert all(r["status"] == "BOUNDED_UNKNOWN" for runs in panels.values() for r in runs)
    record = {
        "schema_version": 1,
        "kind": "n83_w34_slope_witness_paired_pdp_stage_costs",
        "candidate_id": None,
        "curve_id": new["curve_id"],
        "public_fixture_sha256": new["source_public_fixture_sha256"],
        "factor_base_representatives_sha256": new["full_w34_representatives_sha256"],
        "actual_usable_projected_points_B": new["actual_usable_projected_points_B"],
        "effective_signed_frobenius_columns": new["effective_signed_frobenius_columns"],
        "matched_resource_policy": {key: new[key] for key in controlled[3:9]},
        "protocol_sha256": {"direct_mask": sha(DIRECT / "protocol.json"),
                            "indexed_factor": sha(INDEXED / "protocol.json"),
                            "slope_witness": sha(HERE / "protocol.json")},
        "panels": panels,
        "sandbox_process_inspection_failure": {
            "run": "pinned_planted_f0_v1",
            "status": failed["status"],
            "guard": failed["guard"],
            "guard_error": failed["guard_error"],
            "outer_wall_ns": failed["outer_wall_ns"],
            "outer_receipt_sha256": sha(failed_path),
        },
        "fully_pinned_solver_control": {
            "status": full["status"],
            "wall_ns": full["total_wall_ns"],
            "receipt_sha256": sha(full_path),
        },
        "known_witness_boolean_and_sage_control": {
            "status": planted["status"],
            "variables_fully_assigned": planted["variables_fully_assigned"],
            "cnf_clauses_verified": planted["cnf_clauses_verified"],
            "xor_rows_verified": planted["xor_rows_verified"],
            "independent_sage_status": sage["status"],
            "boolean_receipt_sha256": sha(planted_path),
            "sage_replay_sha256": sha(sage_path),
        },
        "ordinary_panel": {
            "public_target_Q": panels["slope_witness"][2]["target_Q"],
            "raw_fibers_of_one_target": 4,
            "independent_query_count_for_rate_estimation": 1,
            "verified_relations_by_method": {key: 0 for key in panels},
            "status_counts_by_method": {key: {"BOUNDED_UNKNOWN": 4} for key in panels},
            "sum_outer_wall_ns_diagnostic_only": {
                key: sum(r["outer_wall_ns"] for r in runs[2:])
                for key, runs in panels.items()
            },
            "natural_relation_yield": None,
            "novel_rank_per_query": None,
            "cost_per_useful_row": None,
        },
        "host_isolation_receipt": None,
        "controlled_cpu_speedup": None,
        "single_target_ic_online_wall_ns": None,
        "paired_same_point_rho_online_wall_ns": None,
        "ic_online_speedup": None,
        "cold_total_wall_ns": None,
        "total_operations_calibrated": None,
    }
    (HERE / "COST_COMPARISON.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")
    print("PASS: all three source-bound stage panels reconciled, including failures")


if __name__ == "__main__":
    main()
