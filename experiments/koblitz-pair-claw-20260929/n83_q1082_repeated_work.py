#!/usr/bin/env python3
"""Charge Q1082's four audited repeats without granting new coverage."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "n83_q1082_m28_r24_bloom_paired_plan.json"
BUNDLE = HERE / "runs/n83_q1082_x86_ci_36792009510"
OUTPUT = HERE / "n83_q1082_repeated_work.json"
ORDER = ("b20a", "b16a", "b16b", "b20b")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads(PLAN.read_text())
    audit_path = BUNDLE / "audit.json"
    assert audit_path.is_file(), "terminal independent Q1082 audit missing"
    audit = json.loads(audit_path.read_text())
    assert audit["proposal_id"] == plan["proposal_id"] == "Q1082"
    assert audit["candidate_id"] is audit["run_id"] is None
    assert audit["curve_id"] == plan["curve_id"]
    assert audit["isogeny"] == plan["isogeny"] == "none"
    assert audit["plan_sha256"] == sha(PLAN)
    assert audit["factor_base_enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    assert audit["actual_usable_points_B_before_folding"] == plan[
        "actual_usable_points_B_before_folding"]
    assert audit["signed_frobenius_columns"] == plan[
        "signed_frobenius_columns"]
    assert audit["novel_coverage_cells"] == 0
    rows = []
    for name in ORDER:
        receipt = BUNDLE / f"{name}.json"
        sage_path = BUNDLE / f"{name}_sage_verify.json"
        assert audit["receipt_sha256"][name] == sha(receipt)
        assert audit["sage_verify_sha256"][name] == sha(sage_path)
        row = json.loads(receipt.read_text())
        sage = json.loads(sage_path.read_text())
        assert row["curve_id"] == plan["curve_id"]
        assert row["public_target"] == plan["public_target"]
        assert row["bits_per_key"] == plan["bits_per_key_by_run"][name]
        assert row["native_field_add_mul_sqr_call_model"] == plan[
            "modeled_native_field_calls_per_run"]
        assert sage["receipt_sha256"] == sha(receipt)
        assert sage["verified_relation_count"] == 0
        assert row["native_result"]["exact_hit_queries"] == 0
        rows.append(row)
    calls = int(plan["modeled_native_field_calls_per_run"])
    assert math.isclose(math.log2(4 * calls), plan[
        "modeled_four_run_field_calls_log2"], abs_tol=1e-12)
    assert audit["modeled_native_field_calls_four_runs_log2"] == plan[
        "modeled_four_run_field_calls_log2"]
    return {
        "kind": "n83_q1082_repeated_rectangle_charged_work",
        "proposal_id": "Q1082", "candidate_id": None, "run_id": None,
        "curve_id": plan["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "target_count": 1, "public_target": plan["public_target"],
        "table_start": plan["table_start"],
        "table_descriptors": plan["table_descriptors"],
        "query_start": plan["query_start"],
        "query_representatives": plan["query_representatives"],
        "successful_attempt_count": len(rows),
        "novel_rectangle_count": 0,
        "full_M28_by_R27_grid_cells_credited": 0,
        "per_attempt_modeled_native_field_calls": str(calls),
        "all_four_attempts_modeled_native_field_calls": str(4 * calls),
        "all_four_attempts_modeled_native_field_calls_log2": math.log2(
            4 * calls),
        "target_online_seconds": audit["target_online_seconds"],
        "target_online_speedup_b20_over_b16": audit[
            "target_online_speedup_b20_over_b16"],
        "exact_hit_queries_per_attempt": 0,
        "natural_public_target_relation_verified": False,
        "complete_solve_work_log2": None,
        "work_boundary": "nominal native field add/mul/sqr calls with inversion expanded; excludes keying, Bloom, memory, disk, setup, and scalar replay",
        "coverage_boundary": "four repetitions of Q1080's audited M28/R24 rectangle; zero novel coverage",
        "audit_sha256": sha(audit_path),
        "plan_sha256": sha(PLAN),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    assert not OUTPUT.exists(), "refusing to overwrite Q1082 work receipt"
    report = build()
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"proposal_id": "Q1082", "attempts": 4,
                      "novel_rectangles": 0,
                      "four_attempt_work_log2": report[
                          "all_four_attempts_modeled_native_field_calls_log2"]}))


if __name__ == "__main__":
    main()
