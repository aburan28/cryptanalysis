#!/usr/bin/env python3
"""Independently account for Q1493 frozen sweep attempts and work totals."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
PREFLIGHT = HERE / "known_witness_preflight.json"
OUTPUT = HERE / "archive_audit.json"
OPERATION_KEYS = (
    "conflicts", "decisions", "propagations", "field_mul_calls",
    "field_sqr_calls", "field_inv_calls", "field_s3_root_calls",
    "conditioned_right_s3_evals",
)
PHASE_KEYS = (
    "target_encoding_ns", "materialization_ns", "native_process_ns",
    "relation_check_ns",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> dict:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    preflight = json.loads(PREFLIGHT.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1493"
    assert design["candidate_id"] is design["run_id"] is None
    assert design["isogeny"] == "none"
    assert protocol["design_sha256"] == sha(DESIGN)
    assert protocol["source_sha256"] == sha(HERE / "run.py")
    assert preflight["status"] == "PASS"
    assert preflight["design_sha256"] == sha(DESIGN)
    assert preflight["protocol_sha256"] == sha(PROTOCOL)
    assert preflight["source_sha256"] == sha(HERE / "run.py")
    assert preflight["rotation"] == 44
    assert preflight["first_window_starts"] == [0]
    assert preflight["q1490_witness_sha256"] == sha(
        PARENT / "q1490_ordinary_witness_bridge/runs/r2/bridge_result.json")
    parent53 = json.loads((PARENT /
        "q1482_window_s3/inputs/n53_ordinary/input.json").read_text())
    parent83 = json.loads((PARENT /
        "q1482_window_s3/inputs/n83_ordinary/input.json").read_text())
    parents = {53: parent53, 83: parent83}
    rows = []
    for cell_name in design["run_order"]:
        cell = design["runs"][cell_name]
        n = cell["degree_n"]
        profile = next(row for row in design["profiles"]
                       if row["field_degree_n"] == n)
        parent = parents[n]
        directory = HERE / "runs" / cell_name
        receipt_path = directory / "receipt.json"
        attempts_path = directory / "attempts.jsonl"
        receipt = json.loads(receipt_path.read_text())
        attempts = [json.loads(line) for line in
                    attempts_path.read_text().splitlines()]
        assert receipt["proposal_id"] == "Q1493"
        assert receipt["candidate_id"] is receipt["run_id"] is None
        assert receipt["isogeny"] == "none"
        assert receipt["cell"] == cell_name
        assert receipt["curve_id"] == parent["curve_id"] == profile[
            "curve_id"]
        assert receipt["factor_base_actual_B"] == parent[
            "factor_base_actual_B"] == profile["factor_base_actual_B"]
        assert receipt["factor_base_folded_columns_K"] == parent[
            "folded_columns_K"] == profile["factor_base_folded_columns_K"]
        assert receipt["factor_base_enumerated_set_sha256"] == parent[
            "factor_base_enumerated_set_sha256"] == profile[
                "factor_base_enumerated_set_sha256"]
        assert receipt["source_sha256"] == sha(HERE / "run.py")
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["rotation_attempts_sha256"] == sha(attempts_path)
        assert receipt["runtime_info_sha256"] == sha(
            HERE / "sage_runtime_info.json")
        assert receipt["rotation_attempt_count"] == len(attempts) == len(
            cell["rotations"])
        assert [row["rotation"] for row in attempts] == cell["rotations"]
        assert receipt["status"] == "no_verified_relation_at_caps"
        assert receipt["verified_relation_count"] == 0
        assert receipt["verified_rotation"] is None
        assert receipt["natural_relation_yield_estimate"] is None
        assert receipt["novel_rank_per_query"] is None
        assert receipt["complete_n131_log2_work"] is None
        assert receipt["challenge_run_admitted"] is False
        assert receipt["operation_vector_complete"] is True
        totals = {key: 0 for key in OPERATION_KEYS}
        phases = {key: 0 for key in PHASE_KEYS}
        statuses = {}
        for attempt in attempts:
            report = attempt["native_report"]
            assert report is not None
            assert attempt["status"] == attempt["native_status"] == (
                "censored")
            assert attempt["native_exit_code"] == 10
            assert report["status"] == 0
            assert report["stop_reason"] == "wall_cap"
            assert report["cnf_variables"] == parent["cnf_variables"]
            assert report["cnf_clauses"] == parent["cnf_clauses"] + 1
            assert report["target_preimage_count"] == parent[
                "target_preimage_x_count"]
            assert attempt["model_sha256"] is None
            assert attempt["independent_relation"] is None
            assert attempt["verification_error"] is None
            assert json.loads(attempt["native_stdout"]) == report
            assert attempt["native_stderr"] == ""
            assert attempt["original_target"] == parent["public_target"]
            assert attempt["target_preimage_count"] == parent[
                "target_preimage_x_count"]
            assert attempt["first_window_selector_variable"] > 0
            for key in OPERATION_KEYS:
                totals[key] += report[key]
            for key in PHASE_KEYS:
                phases[key] += attempt[f"{key}_exploratory"]
            statuses[attempt["status"]] = statuses.get(
                attempt["status"], 0) + 1
        assert totals == receipt["summed_native_operations"]
        assert phases == receipt["exclusive_phase_ns_exploratory"]
        assert sum(phases.values()) == receipt[
            "charged_stage_wall_ns_exploratory"]
        assert max(row["peak_child_rss_so_far_raw"]
                   for row in attempts) == receipt["peak_child_rss_raw"]
        rows.append({
            "cell": cell_name, "field_degree_n": n,
            "curve_id": profile["curve_id"],
            "factor_base_actual_B": profile["factor_base_actual_B"],
            "factor_base_folded_columns_K": profile[
                "factor_base_folded_columns_K"],
            "rotation_attempt_count": len(attempts),
            "status_mix": statuses,
            "verified_relation_count": 0,
            "summed_native_operations": totals,
            "exclusive_phase_ns_exploratory": phases,
            "charged_stage_wall_ns_exploratory": sum(phases.values()),
            "peak_child_rss_raw": receipt["peak_child_rss_raw"],
            "receipt_sha256": sha(receipt_path),
            "attempts_sha256": sha(attempts_path),
        })
    return {
        "kind": "q1493_independent_sweep_accounting_audit",
        "proposal_id": "Q1493", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "status": "PASS", "rows": rows,
        "n83_successful_ordinary_pdp_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "design_sha256": sha(DESIGN),
        "protocol_sha256": sha(PROTOCOL),
        "preflight_sha256": sha(PREFLIGHT),
        "audit_source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(audit(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUTPUT.read_text() == encoded
        print("Q1493 independent sweep accounting audit PASS (archived)")
    else:
        assert not OUTPUT.exists(), "refusing to overwrite audit"
        OUTPUT.write_text(encoded)
        print("Q1493 independent sweep accounting audit PASS")


if __name__ == "__main__":
    main()
