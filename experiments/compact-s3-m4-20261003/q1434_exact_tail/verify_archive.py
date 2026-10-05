#!/usr/bin/env python3
"""Independently verify Q1434 exact-tail runs and sampled clauses."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1420 = PARENT / "q1420_root_theory"
Q1426 = PARENT / "q1426_symbolic_pair"
Q1430 = PARENT / "q1430_partial_trail"
Q1431 = PARENT / "q1431_guarded_span"
Q1432 = PARENT / "q1432_coefficient_cache"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(Q1420))

from q1420_root_theory.verify_archive import (  # noqa: E402
    check_cnf, check_math, model_from_file)
from q1426_symbolic_pair.build_formula import build_cnf  # noqa: E402
from q1428_bilinear_span.screen import relaxed_feasible, s3  # noqa: E402
from chain_s3 import field  # noqa: E402

PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_cell(protocol: dict, key: str) -> dict:
    workload = protocol["workloads"][key]
    output = HERE / "runs" / key
    receipt_path = output / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    n, cell = receipt["degree_n"], receipt["cell"]
    assert key == f"n{n}_{cell}"
    assert receipt["proposal_id"] == "Q1434"
    assert receipt["candidate_id"] is None
    assert receipt["isogeny"] == "none"
    for name in ("curve_id", "factor_base_actual_B", "folded_columns_K",
                 "factor_base_enumerated_set_sha256", "public_target",
                 "stage_config_id", "workload_id", "stage_run_id",
                 "target_input_sha256", "target_preimage_x_count",
                 "removed_partner_pin_units"):
        assert receipt[name] == workload[name]
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["runner_source_sha256"] == protocol["source_sha256"][
        "run_stage.py"]
    assert receipt["solver_binary_sha256"] == protocol[
        "solver_binary_sha256"]
    assert receipt["runtime_info_sha256"] == protocol[
        "sage_runtime_info_sha256"]
    parent_path = (Q1420 / "runs" / workload["parent_q1420_key"] /
                   "receipt.json")
    assert sha(parent_path) == workload[
        "parent_q1420_receipt_sha256"] == receipt[
            "parent_q1420_receipt_sha256"]
    matched_path = (Q1432 / "runs" / workload["matched_q1432_key"] /
                    "receipt.json")
    assert sha(matched_path) == workload[
        "matched_q1432_receipt_sha256"] == receipt[
            "matched_q1432_receipt_sha256"]
    matched = json.loads(matched_path.read_text())
    assert matched["stage_run_id"] == receipt[
        "matched_q1432_stage_run_id"] == workload[
            "matched_q1432_stage_run_id"]
    for name in ("workload_id", "curve_id", "factor_base_actual_B",
                 "folded_columns_K", "factor_base_enumerated_set_sha256",
                 "public_target", "target_input_sha256"):
        assert matched[name] == receipt[name]
    raw, formula, meta, removed, variables, clauses = build_cnf(n, cell)
    assert sha(output / "solver.stdout.txt") == receipt[
        "solver_stdout_sha256"]
    assert sha(output / "solver.stderr.txt") == receipt[
        "solver_stderr_sha256"]
    assert hashlib.sha256(raw).hexdigest() == receipt[
        "cnf_raw_sha256"] == workload["cnf_raw_sha256"]
    assert len(raw) == workload["cnf_raw_bytes"]
    assert variables == receipt["cnf_variables"] == workload["cnf_variables"]
    assert clauses == receipt["cnf_clauses"] == workload["cnf_clauses"]
    assert removed == workload["removed_partner_pin_units"]
    assert meta["curve_id"] == workload["curve_id"]
    report = receipt["solver_report"]
    sampled_span_checks = []
    sampled_rejection_checks = []
    sampled_tail_zero = sampled_tail_unique = 0
    if report is not None:
        assert report["status"] == {"sat": 10, "censored": 0,
                                     "unsat": 20}[receipt["solver_status"]]
        assert report["decision_policy"] == "interleave_pair1"
        assert report["target_coupled_active"] is True
        assert report["reverse_pair_active"] is True
        assert report["cnf_variables"] == variables
        assert report["cnf_clauses"] == clauses
        assert report["target_preimage_count"] == workload[
            "target_preimage_x_count"]
        assert report["cached_pair_assignments"] == (
            report["pair0_root_calls"] + report["pair1_root_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_pair0_calls"] + report["reverse_pair1_calls"])
        assert report["cached_reverse_assignments"] == (
            report["reverse_zero_candidates"] +
            report["reverse_one_candidate"] +
            report["reverse_two_candidates"])
        assert report["screen_window_free_threshold_each_leaf"] == (
            14 if n == 53 else 20)
        assert 0 <= report["screen_window_events"] <= (
            report["unsaturated_mid1_events"])
        assert report["unsaturated_mid1_events"] <= (
            report["both_partial_mid1_events"])
        assert report["screen_window_distinct_capped"] <= 256
        assert len(report["screen_snapshots"]) <= min(
            16, report["screen_window_distinct_capped"])
        assert report["span_checks"] == report["span_checked_state_count"]
        assert report["span_checks"] <= report["screen_window_events"]
        assert report["span_rejections"] <= report["span_checks"]
        assert report["span_field_inv_calls"] == 0
        assert report["span_field_mul_calls"] <= report["field_mul_calls"]
        assert report["span_field_sqr_calls"] <= report["field_sqr_calls"]
        assert report["span_guard_literals"] >= n * report[
            "span_rejections"]
        assert report["cache_gamma_tables_retained"] <= 64
        assert report["cache_linear_rows_retained"] <= 16384
        assert report["cache_pair_build_mul_calls"] == report[
            "cache_pair_build_sqr_calls"]
        assert report["cache_pair_build_mul_calls"] + report[
            "cache_gamma_build_mul_calls"] <= report[
                "span_field_mul_calls"]
        assert report["cache_payload_bytes_lower_bound"] >= 0
        assert len(report["span_rejection_snapshots"]) <= min(
            16, report["span_rejections"])
        assert report["tail_checks"] == sum(report[name] for name in
                                             ("tail_zero", "tail_unique",
                                              "tail_multiple"))
        assert report["tail_checks"] <= report["span_checks"] - report[
            "span_rejections"]
        assert report["tail_field_inv_calls"] == 0
        assert report["span_field_mul_calls"] + report[
            "tail_field_mul_calls"] <= report["field_mul_calls"]
        assert report["span_field_sqr_calls"] + report[
            "tail_field_sqr_calls"] <= report["field_sqr_calls"]
        assert len(report["tail_zero_snapshots"]) <= min(
            16, report["tail_zero"])
        assert len(report["tail_unique_snapshots"]) <= min(
            16, report["tail_unique"])
        if report["screen_snapshots"] or report[
                "span_rejection_snapshots"] or report[
                    "tail_zero_snapshots"] or report[
                        "tail_unique_snapshots"]:
            onb = field.Onb(n)
            basis = [onb.fromCoords(1 << i) for i in range(n)]
            weight = workload["stage_config_hash_input"][
                "factor_base"]["normal_basis_weight_bound"]
            mask = (1 << n) - 1
            for kind, snapshots in (
                    ("screen", report["screen_snapshots"]),
                    ("rejection", report["span_rejection_snapshots"])):
                for snapshot in snapshots:
                    m = int(snapshot["mid_onb_hex"], 16)
                    a_fixed = int(snapshot["a_fixed_mask_onb_hex"], 16)
                    a_ones = int(snapshot["a_ones_onb_hex"], 16)
                    b_fixed = int(snapshot["b_fixed_mask_onb_hex"], 16)
                    b_ones = int(snapshot["b_ones_onb_hex"], 16)
                    assert m & ~mask == 0
                    for fixed, ones, side in ((a_fixed, a_ones, "a"),
                                              (b_fixed, b_ones, "b")):
                        assert fixed & ~mask == 0
                        assert ones & ~fixed == 0
                        assert 1 <= n - fixed.bit_count() <= (
                            14 if n == 53 else 20)
                        assert snapshot[f"free_{side}"] == (
                            n - fixed.bit_count())
                        assert 1 <= snapshot[f"slack_{side}"] == (
                            weight - ones.bit_count()) <= 2
                    free_a = [i for i in range(n) if not a_fixed >> i & 1]
                    free_b = [i for i in range(n) if not b_fixed >> i & 1]
                    check = relaxed_feasible(
                        onb, basis, onb.fromCoords(a_ones),
                        onb.fromCoords(b_ones), onb.fromCoords(m),
                        free_a, free_b)
                    if kind == "screen":
                        sampled_span_checks.append(check)
                    else:
                        assert not check["constant_in_span"]
                        sampled_rejection_checks.append(check)
            for kind, items in (("zero", report["tail_zero_snapshots"]),
                                ("unique", report[
                                    "tail_unique_snapshots"])):
                for item in items:
                    snapshot = item if kind == "zero" else item["partial"]
                    m = int(snapshot["mid_onb_hex"], 16)
                    a_fixed = int(snapshot["a_fixed_mask_onb_hex"], 16)
                    a_ones = int(snapshot["a_ones_onb_hex"], 16)
                    b_fixed = int(snapshot["b_fixed_mask_onb_hex"], 16)
                    b_ones = int(snapshot["b_ones_onb_hex"], 16)
                    assert snapshot["slack_a"] == snapshot["slack_b"] == 1
                    assert weight - a_ones.bit_count() == 1
                    assert weight - b_ones.bit_count() == 1
                    free_a = [j for j in range(n) if not a_fixed >> j & 1]
                    free_b = [j for j in range(n) if not b_fixed >> j & 1]
                    a_values = [a_ones] + [a_ones | 1 << j for j in free_a]
                    b_values = [b_ones] + [b_ones | 1 << j for j in free_b]
                    m_field = onb.fromCoords(m)
                    b_fields = [onb.fromCoords(value) for value in b_values]
                    roots = [(a_value, b_value)
                             for a_value in a_values
                             for b_value, b_element in zip(b_values,
                                                            b_fields)
                             if s3(onb, onb.fromCoords(a_value), b_element,
                                   m_field) == 0]
                    if kind == "zero":
                        assert roots == []
                        sampled_tail_zero += 1
                    else:
                        assert len(roots) == 1
                        assert item["candidates"] == len(a_values) * len(
                            b_values)
                        assert item["solutions"] == 1
                        assert roots[0] == (
                            int(item["unique_a_onb_hex"], 16),
                            int(item["unique_b_onb_hex"], 16))
                        sampled_tail_unique += 1
    if receipt["solver_status"] == "sat":
        assert receipt["solver_model_sha256"] == sha(
            output / "solver.model.txt")
        model = model_from_file(output / "solver.model.txt")
        check_cnf(raw, model, variables, clauses)
        relation = check_math(formula, meta, model)
        assert relation == receipt["model_check"]
        assert receipt["verified_relation_count"] == int(
            relation["status"] == "verified_four_point_relation")
    else:
        assert receipt["solver_model_sha256"] is None
        assert receipt["model_check"] is None
        assert receipt["verified_relation_count"] == 0
        assert receipt["solver_status"] in ("censored", "external_timeout",
                                            "unsat", "error")
    assert receipt["natural_relation_yield_estimate"] is None
    assert receipt["complete_solve_work_log2"] is None
    return {
        "key": key, "status": receipt["solver_status"],
        "verified_relation_count": receipt["verified_relation_count"],
        "solver_process_wall_seconds_exploratory": receipt[
            "solver_process_wall_seconds_exploratory"],
        "sampled_span_checks": len(sampled_span_checks),
        "sampled_span_rejections": sum(
            not row["constant_in_span"] for row in sampled_span_checks),
        "sampled_span_max_columns_tested": max(
            (row["cross_columns_tested"] for row in sampled_span_checks),
            default=0),
        "sampled_rejection_checks": len(sampled_rejection_checks),
        "sampled_rejection_false_claims": sum(
            row["constant_in_span"] for row in sampled_rejection_checks),
        "sampled_tail_zero_checks": sampled_tail_zero,
        "sampled_tail_unique_checks": sampled_tail_unique,
        "tail_checks": (report or {}).get("tail_checks"),
        "tail_zero": (report or {}).get("tail_zero"),
        "tail_unique": (report or {}).get("tail_unique"),
        "tail_candidate_pairs": (report or {}).get("tail_candidate_pairs"),
        "receipt_sha256": sha(receipt_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["source_sha256"]["verify_archive.py"] == sha(
        HERE / "verify_archive.py")
    checks, missing = [], []
    for key in protocol["run_order"]:
        if (HERE / "runs" / key / "receipt.json").exists():
            checks.append(verify_cell(protocol, key))
        else:
            missing.append(key)
    assert not args.require_complete or not missing
    report = {
        "kind": "q1434_exact_tail_archive_verification",
        "proposal_id": "Q1434", "candidate_id": None,
        "protocol_sha256": sha(PROTOCOL),
        "verifier_source_sha256": sha(Path(__file__)),
        "checks": checks, "missing": missing, "complete": not missing,
        "natural_relation_yield_estimate": None,
        "complete_solve_work_log2": None,
    }
    if args.emit:
        (HERE / "verification.json").write_text(json.dumps(
            report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"checked": len(checks), "missing": missing,
                      "verified_relations": sum(row[
                          "verified_relation_count"] for row in checks)}))


if __name__ == "__main__":
    main()
