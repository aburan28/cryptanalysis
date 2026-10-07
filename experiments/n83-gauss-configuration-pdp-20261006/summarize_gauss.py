#!/usr/bin/env python3
"""Reconcile the frozen N83 Gaussian-policy and query-stage receipts."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
SLOPE = HERE.parent / "n83-slope-witness-pdp-20261006"
CASES = ("pinned_planted_f0", "unpinned_planted_f0",
         "ordinary_f0", "ordinary_f1", "ordinary_f2", "ordinary_f3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def run_row(name: str, protocol_path: Path, runner_path: Path,
            expected_input_sha: str, require_sage: bool = False) -> dict:
    folder = HERE / "runs" / name
    receipt_path = folder / "receipt.json"
    started_path = folder / "started.json"
    receipt = read(receipt_path)
    started = read(started_path)
    assert started["protocol_sha256"] == receipt["protocol_sha256"] == sha(protocol_path)
    assert started["source_sha256"] == sha(runner_path)
    assert started["input_xcnf_sha256"] == expected_input_sha
    assert started["sage_runtime_info_sha256"] == sha(folder / "sage_runtime_info.json")
    assert receipt["started_sha256"] == sha(started_path)
    assert receipt["solver_wall_ns"] >= 0
    assert receipt["verification_wall_ns"] >= 0
    assert receipt["solver_wall_ns"] + receipt["verification_wall_ns"] == \
        receipt["total_wall_ns"]
    assert receipt["candidate_id"] is None and receipt["online_speedup"] is None
    with gzip.open(folder / "solver.stdout.txt.gz", "rb") as archive:
        data = archive.read()
    assert hashlib.sha256(data).hexdigest() == receipt["solver_stdout_sha256"]
    log = data.decode(errors="replace")
    conflicts = re.findall(r"(?m)^c conflicts\s+:\s+(\d+)\b", log)
    decisions = re.findall(r"(?m)^c decisions\s+:\s+(\d+)\b", log)
    matrix50 = bool(re.search(r"Good\s+matrix\s+\d+\s+2075 x50\d{3}", log))
    too_many50 = bool(re.search(r"Too many columns in matrix: 50\d{3}", log))
    sage_status = None
    sage_sha = None
    if require_sage or receipt["status"] == "SAT_GROUP_VERIFIED_PENDING_SAGE":
        sage_path = folder / "sage_replay.json"
        sage = read(sage_path)
        assert sage["status"] == "PASS"
        assert sage["receipt_sha256"] == sha(receipt_path)
        assert sage["sage_runtime_info_sha256"] == \
            sha(folder / "sage_replay_runtime_info.json")
        sage_status = sage["status"]
        sage_sha = sha(sage_path)
    return {
        "name": name,
        "status": receipt["status"],
        "solver_exit_code": receipt["solver_exit_code"],
        "solver_wall_ns": receipt["solver_wall_ns"],
        "verification_wall_ns": receipt["verification_wall_ns"],
        "total_wall_ns": receipt["total_wall_ns"],
        "sampled_process_tree_cpu_seconds":
            receipt["sampled_process_tree_cpu_seconds"],
        "sampled_process_tree_peak_rss_bytes":
            receipt["sampled_process_tree_peak_rss_bytes"],
        "guard": receipt["guard"],
        "solver_reported_conflicts": int(conflicts[-1]) if conflicts else None,
        "solver_reported_decisions": int(decisions[-1]) if decisions else None,
        "large_approximately_50000_column_matrix_used": matrix50,
        "large_approximately_50000_column_matrix_rejected": too_many50,
        "sage_replay_status": sage_status,
        "sage_replay_sha256": sage_sha,
        "started_sha256": sha(started_path),
        "receipt_sha256": sha(receipt_path),
        "solver_log_gzip_sha256": sha(folder / "solver.stdout.txt.gz"),
    }


def main() -> None:
    p15 = HERE / "protocol.json"
    p60 = HERE / "protocol_wide.json"
    pq = HERE / "protocol_queries.json"
    protocol15, protocol60, protocolq = map(read, (p15, p60, pq))
    assert protocol60["parent_protocol_sha256"] == sha(p15)
    assert protocolq["source_wide_protocol_sha256"] == sha(p60)
    fully_pinned_sha = protocol15["input_xcnf_sha256"]
    assert protocol60["input_xcnf_sha256"] == fully_pinned_sha
    assert sha(SLOPE / "runs/fully_pinned_planted_f0_v1/control.xcnf") == fully_pinned_sha
    controls = {
        "large_gauss": run_row("large_gauss_v1", p15, HERE / "run_gauss_gate.py",
                               fully_pinned_sha),
        "persistent_gauss": run_row("persistent_gauss_v1", p15,
                                    HERE / "run_gauss_gate.py", fully_pinned_sha),
        "wide_gauss": run_row("wide_gauss_v1", p60,
                              HERE / "run_wide_gauss_gate.py",
                              fully_pinned_sha, require_sage=True),
    }
    assert controls["large_gauss"]["status"] == "BOUNDED_UNKNOWN"
    assert controls["persistent_gauss"]["status"] == "BOUNDED_UNKNOWN"
    assert controls["wide_gauss"]["status"] == "SAT_GROUP_VERIFIED_PENDING_SAGE"
    assert controls["wide_gauss"]["sage_replay_status"] == "PASS"
    assert protocolq["positive_control_receipt_sha256"] == \
        controls["wide_gauss"]["receipt_sha256"]
    assert protocolq["positive_control_sage_replay_sha256"] == \
        controls["wide_gauss"]["sage_replay_sha256"]
    queries = {}
    public = read(HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json")
    for case in CASES:
        item = protocolq["cases"][case]
        parent = SLOPE / "runs" / item["parent_run"]
        assert sha(parent / "receipt.json") == item["parent_receipt_sha256"]
        assert sha(parent / "branch.xcnf") == item["input_xcnf_sha256"]
        row = run_row(case + "_v1", pq, HERE / "run_wide_query.py",
                      item["input_xcnf_sha256"])
        receipt = read(HERE / "runs" / (case + "_v1") / "receipt.json")
        started = read(HERE / "runs" / (case + "_v1") / "started.json")
        assert receipt["case"] == started["case"] == case
        assert receipt["mode"] == started["mode"] == item["mode"]
        assert receipt["fiber_index"] == started["fiber_index"] == item["fiber_index"]
        kind = "ordinary" if item["mode"] == "ordinary" else "planted"
        assert receipt["target_Q"] == started["target_Q"] == public[kind]["target_Q"]
        assert (started["private_fixture_sha256_local_only"] is not None) == \
            (item["mode"] == "pinned_planted")
        queries[case] = row
    ordinary = [queries[f"ordinary_f{i}"] for i in range(4)]
    assert all(row["status"] == "BOUNDED_UNKNOWN" for row in ordinary)
    assert queries["pinned_planted_f0"]["status"] == "BOUNDED_UNKNOWN"
    assert queries["unpinned_planted_f0"]["status"] == "BOUNDED_UNKNOWN"
    baseline_path = SLOPE / "runs/fully_pinned_planted_f0_v1/receipt.json"
    baseline = read(baseline_path)
    assert baseline["status"] == "BOUNDED_UNKNOWN"
    assert baseline["xcnf_sha256"] == fully_pinned_sha
    record = {
        "schema_version": 1,
        "kind": "n83_wide_gaussian_solver_policy_stage_ledger",
        "candidate_id": None,
        "curve_id": protocolq["curve_id"],
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": {"large": sha(p15), "wide": sha(p60),
                            "queries": sha(pq)},
        "fully_pinned_input_xcnf_sha256": fully_pinned_sha,
        "default_fully_pinned_control": {
            "status": baseline["status"],
            "solver_wall_ns": baseline["solver_wall_ns"],
            "receipt_sha256": sha(baseline_path),
        },
        "gaussian_policy_controls": controls,
        "query_panel": queries,
        "ordinary_panel": {
            "public_target_Q": public["ordinary"]["target_Q"],
            "raw_fibers_of_one_target": 4,
            "independent_query_count_for_rate_estimation": 1,
            "verified_relations": 0,
            "status_counts": {"BOUNDED_UNKNOWN": 4},
            "sum_solver_wall_ns_exploratory_only": sum(
                row["solver_wall_ns"] for row in ordinary),
            "sum_total_wall_ns_exploratory_only": sum(
                row["total_wall_ns"] for row in ordinary),
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
        "claim_boundary": "Fully pinned SAT and Sage PASS are correctness controls. All mask-only, public-only planted, and four ordinary attempts were bounded unknown. No verified ordinary relation, complete IC target DLP, paired rho, or isolated speedup exists."
    }
    (HERE / "RESULTS.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print("PASS: source-bound wide-Gauss controls and six query attempts reconciled")


if __name__ == "__main__":
    main()
