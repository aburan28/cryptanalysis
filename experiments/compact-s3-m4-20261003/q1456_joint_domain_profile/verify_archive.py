#!/usr/bin/env python3
"""Recompute every Q1456 pair-domain count from archived SAT states."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1455 = PARENT / "q1455_joint_tail"
sys.path.insert(0, str(PARENT))

from q1438_dense_base.verify_solver import model_relation  # noqa: E402
from q1455_joint_tail.joint_tail import PartialLeaf, option_count  # noqa: E402
from q1455_joint_tail.native_inputs import make_case  # noqa: E402

PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "verification.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(name: str, cell: dict, protocol: dict) -> dict:
    run = HERE / "runs" / name
    receipt_path = run / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    parent_run = Q1455 / "runs" / name
    assert receipt["proposal_id"] == "Q1456"
    assert receipt["candidate_id"] is None
    assert receipt["isogeny"] == "none"
    assert receipt["case"] == name
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == sha(HERE / "run_stage.py")
    assert receipt["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert receipt["binary_sha256"] == sha(HERE / "domain_probe") == protocol[
        "binary_sha256"]
    assert receipt["parent_receipt_sha256"] == sha(parent_run /
                                                   "receipt.json")
    assert receipt["workload_id"] == cell["workload_id"]
    assert receipt["solver_stdout_sha256"] == sha(run / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(run / "solver.stderr.txt")
    assert receipt["solver_model_sha256"] == (
        sha(run / "solver.model.txt") if (run / "solver.model.txt").exists()
        else None)
    report = receipt["solver_report"]
    if report is None:
        assert receipt["solver_status"] in ("external_timeout", "error")
        return {"case": name, "solver_status": receipt["solver_status"],
                "unique_partial_states": None,
                "min_max_pair_candidates": None,
                "all_domain_snapshots_independently_checked": 0,
                "verified_relation_count": 0,
                "receipt_sha256": sha(receipt_path)}
    assert report == json.loads((run / "solver.stdout.txt").read_text())
    assert report["cnf_variables"] == cell["cnf_variables"]
    assert report["cnf_clauses"] == cell["cnf_clauses"]
    assert report["pair_cap"] == cell["pair_candidate_cap"]
    snapshots = report["domain_snapshots"]
    assert len(snapshots) == report["unique_partial_states"]
    n = cell["degree_n"]
    target_count = len((parent_run / "targets.txt").read_text().splitlines()) - 1
    pair_counts = []
    for snapshot in snapshots:
        assert 0 <= snapshot["target_preimage_index"] < target_count
        leaves = [PartialLeaf(int(mask, 16), int(ones, 16))
                  for mask, ones in zip(
                      snapshot["leaf_fixed_mask_onb_hex"],
                      snapshot["leaf_ones_onb_hex"])]
        assert len(leaves) == 4
        assert all(leaf.fixed_mask.bit_count() < n for leaf in leaves)
        options = [option_count(leaf, n, cell[
            "normal_basis_weight_bound"]) for leaf in leaves]
        expected = [options[0] * options[1],
                    options[2] * options[3]]
        assert snapshot["pair_candidate_counts"] == expected
        pair_counts.append(expected)
    histogram = Counter(max(pair).bit_length() - 1 if max(pair) else 0
                        for pair in pair_counts)
    assert report["max_pair_log2_histogram"] == [
        {"floor_log2": bucket, "unique_states": histogram[bucket]}
        for bucket in sorted(histogram)]
    assert report["min_pair0_candidates"] == (
        min(pair[0] for pair in pair_counts) if pair_counts else 0)
    assert report["min_pair1_candidates"] == (
        min(pair[1] for pair in pair_counts) if pair_counts else 0)
    assert report["min_max_pair_candidates"] == (
        min(max(pair) for pair in pair_counts) if pair_counts else 0)
    assert report["min_sum_pair_candidates"] == (
        min(sum(pair) for pair in pair_counts) if pair_counts else 0)
    assert report["unique_partial_states"] <= report["partial_events"]
    assert report["joint_checks"] + report["cap_skips"] <= report[
        "partial_events"]
    if receipt["solver_status"] == "sat":
        raw, _, _, formula, meta, variables, clauses = make_case(name)
        assert hashlib.sha256(raw).hexdigest() == cell["cnf_sha256"]
        parent = json.loads((PARENT /
            "q1438_dense_base/solver_protocol.json").read_text())
        relation = model_relation(
            raw, formula, meta, variables, clauses,
            run / "solver.model.txt", parent["instances"][str(n)])
        assert relation == receipt["model_check"]
        assert receipt["verified_relation_count"] == int(
            relation["status"] == "verified_four_point_relation")
    else:
        assert receipt["verified_relation_count"] == 0
    return {"case": name, "degree_n": n,
            "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "solver_status": receipt["solver_status"],
            "stop_reason": report["stop_reason"],
            "partial_events": report["partial_events"],
            "unique_partial_states": report["unique_partial_states"],
            "cap_skips": report["cap_skips"],
            "joint_checks": report["joint_checks"],
            "min_pair0_candidates": report["min_pair0_candidates"],
            "min_pair1_candidates": report["min_pair1_candidates"],
            "min_max_pair_candidates": report[
                "min_max_pair_candidates"],
            "min_sum_pair_candidates": report[
                "min_sum_pair_candidates"],
            "max_pair_log2_histogram": report[
                "max_pair_log2_histogram"],
            "all_domain_snapshots_independently_checked": len(snapshots),
            "verified_relation_count": receipt["verified_relation_count"],
            "exploratory_solver_wall_ns": receipt[
                "solver_process_wall_ns_exploratory"],
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1456"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for relative, digest in protocol["input_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    rows = [audit(name, protocol["cells"][name], protocol)
            for name in protocol["run_order"]]
    result = {"kind": "q1456_exact_joint_pair_domain_profile_audit",
              "proposal_id": "Q1456", "candidate_id": None,
              "isogeny": "none", "status": "pass",
              "rows": rows, "protocol_sha256": sha(PROTOCOL),
              "successful_ordinary_decomposition_cost_measured": False,
              "natural_relation_yield_estimate": None,
              "complete_n131_log2_work": None,
              "challenge_run_admitted": False}
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1456 domain-profile archive audit: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1456",
                          "min_max_pair_candidates": [
                              row["min_max_pair_candidates"] for row in rows]}))


if __name__ == "__main__":
    main()
