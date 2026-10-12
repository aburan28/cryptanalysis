#!/usr/bin/env python3
"""Pair Q1458 and Q1457 exact joint states and primitive-call counts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1457 = HERE.parent / "q1457_joint_cap4096"
OUTPUT = HERE / "paired_comparison.json"
CASES = ("n53_known_sat_unpinned", "n53_ordinary", "n83_ordinary")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def make_comparison() -> dict:
    protocol_path = HERE / "protocol.json"
    verification_path = HERE / "verification.json"
    baseline_verification_path = Q1457 / "verification.json"
    protocol = json.loads(protocol_path.read_text())
    verification = json.loads(verification_path.read_text())
    baseline_verification = json.loads(baseline_verification_path.read_text())
    assert protocol["proposal_id"] == verification["proposal_id"] == "Q1458"
    assert baseline_verification["proposal_id"] == "Q1457"
    assert verification["status"] == baseline_verification["status"] == "pass"
    assert verification["protocol_sha256"] == sha(protocol_path)
    assert protocol["run_order"] == list(CASES)
    rows = []
    for name in CASES:
        before_path = Q1457 / "runs" / name / "receipt.json"
        after_path = HERE / "runs" / name / "receipt.json"
        before = json.loads(before_path.read_text())
        after = json.loads(after_path.read_text())
        a, b = before["solver_report"], after["solver_report"]
        cell = protocol["cells"][name]
        for key in ("curve_id", "workload_id", "factor_base_actual_B",
                    "folded_columns_K", "factor_base_enumerated_set_sha256",
                    "public_target", "cnf_sha256", "pair_candidate_cap",
                    "conflict_cap", "wall_cap_seconds"):
            assert before[key] == after[key] == cell[key], (name, key)
        assert after["baseline_q1457_receipt_sha256"] == sha(before_path)
        assert before["solver_status"] == after["solver_status"] == "censored"
        assert a["joint_rejection_snapshots"] == b[
            "joint_rejection_snapshots"]
        assert a["joint_hit_snapshots"] == b["joint_hit_snapshots"] == []
        for key in ("joint_eligible_checks", "joint_no_chain_rejections",
                    "joint_pair0_root_calls", "joint_pair1_root_calls",
                    "joint_final_root_calls"):
            assert a[key] == b[key], (name, key)
        assert b["batch_root_inputs"] == (
            a["joint_pair0_root_calls"] + a["joint_pair1_root_calls"] +
            a["joint_final_root_calls"])
        assert b["batch_denominators"] == a["joint_field_inv_calls"]
        before_calls = {kind: a[f"joint_field_{kind}_calls"]
                        for kind in ("mul", "sqr", "inv")}
        after_calls = {kind: b[f"joint_field_{kind}_calls"]
                       for kind in ("mul", "sqr", "inv")}
        saved = {kind: before_calls[kind] - after_calls[kind]
                 for kind in before_calls}
        assert all(value > 0 for value in saved.values())
        rows.append({
            "case": name,
            "curve_id": cell["curve_id"],
            "workload_id": cell["workload_id"],
            "same_rejection_states_sha256": digest(a[
                "joint_rejection_snapshots"]),
            "joint_checks": a["joint_eligible_checks"],
            "pair_root_calls": [a["joint_pair0_root_calls"],
                                a["joint_pair1_root_calls"]],
            "final_root_calls": a["joint_final_root_calls"],
            "serial_joint_field_calls": before_calls,
            "batched_joint_field_calls": after_calls,
            "joint_field_calls_saved": saved,
            "batch_inverse_batches": b["batch_inverse_batches"],
            "batch_denominators": b["batch_denominators"],
            "baseline_receipt_sha256": sha(before_path),
            "batched_receipt_sha256": sha(after_path),
            "both_censored_without_relation": True,
            "controlled_cpu_wall_speedup": None,
            "successful_decomposition_cost": None,
        })
    return {
        "kind": "q1458_q1457_paired_joint_state_operation_audit",
        "proposal_id": "Q1458", "candidate_id": None,
        "isogeny": "none", "status": "pass",
        "rows": rows,
        "protocol_sha256": sha(protocol_path),
        "verification_sha256": sha(verification_path),
        "baseline_verification_sha256": sha(baseline_verification_path),
        "source_sha256": sha(Path(__file__)),
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = make_comparison()
    if args.check:
        assert result == json.loads(OUTPUT.read_text())
        print("Q1458/Q1457 paired joint-state operation audit: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1458",
                          "joint_checks": [row["joint_checks"] for row
                                           in result["rows"]],
                          "joint_inversions_saved": [row[
                              "joint_field_calls_saved"]["inv"] for row
                              in result["rows"]]}))


if __name__ == "__main__":
    main()
