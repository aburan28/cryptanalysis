#!/usr/bin/env python3
"""Account for Q1080's four charged M28/R24 runs and one novel rectangle."""

import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "n83_q1080_m28_r24_paired_plan.json"
BUNDLE = HERE / "runs/n83_q1080_x86_ci_36770585105"
OUTPUT = HERE / "n83_q1080_partial_work.json"
ORDER = ("original1", "zero_run1", "zero_run2", "original2")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads(PLAN.read_text())
    audit_path = BUNDLE / "audit.json"
    assert audit_path.is_file(), "terminal independent Q1080 audit missing"
    audit = json.loads(audit_path.read_text())
    assert audit["proposal_id"] == plan["proposal_id"] == "Q1080"
    assert audit["curve_id"] == plan["curve_id"]
    assert audit["isogeny"] == plan["isogeny"] == "none"
    assert audit["factor_base_enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    assert audit["plan_sha256"] == sha(PLAN)
    assert audit["table_start"] == plan["table_start"] == 0
    assert audit["table_descriptors"] == plan["table_descriptors"] == 1 << 28
    assert audit["query_start"] == plan["query_start"] == 22548578304
    assert audit["query_representatives"] == plan[
        "query_representatives"] == 1 << 24
    rows = []
    for name in ORDER:
        path = BUNDLE / f"{name}.json"
        sage_path = BUNDLE / f"{name}_sage_verify.json"
        assert path.is_file() and sage_path.is_file()
        assert audit["receipt_sha256"][name] == sha(path)
        assert audit["sage_verify_sha256"][name] == sha(sage_path)
        row = json.loads(path.read_text())
        sage = json.loads(sage_path.read_text())
        assert row["proposal_id"] == ("Q1079" if name.startswith("zero_run")
                                      else "Q1061")
        assert row["curve_id"] == plan["curve_id"]
        assert row["isogeny"] == "none"
        assert row["factor_base"]["enumerated_set_sha256"] == plan[
            "factor_base_enumerated_set_sha256"]
        assert row["public_target"] == plan["public_target"]
        assert row["table_start"] == plan["table_start"]
        assert row["table_descriptors"] == plan["table_descriptors"]
        assert row["query_start"] == plan["query_start"]
        assert row["query_representatives"] == plan["query_representatives"]
        assert row["native_field_add_mul_sqr_call_model"] == plan[
            "modeled_native_field_calls_per_run"]
        assert sage["receipt_sha256"] == sha(path)
        assert bool(sage["verified_relation_count"]) == row[
            "verified_public_target_quotient_table_dlp"]
        rows.append(row)
    exact_hits = rows[0]["native_result"]["exact_hit_queries"]
    assert all(row["native_result"]["exact_hit_queries"] == exact_hits
               for row in rows)
    assert audit["exact_hit_queries"] == exact_hits
    calls = int(plan["modeled_native_field_calls_per_run"])
    assert math.isclose(math.log2(calls), plan[
        "modeled_native_field_calls_per_run_log2"], rel_tol=0, abs_tol=1e-12)
    assert math.isclose(math.log2(4 * calls), plan[
        "modeled_four_run_field_calls_log2"], rel_tol=0, abs_tol=1e-12)
    return {
        "kind": "n83_q1080_partial_rectangle_charged_work",
        "proposal_id": "Q1080", "candidate_id": None, "run_id": None,
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
        "query_end_exclusive": plan["query_end_exclusive"],
        "novel_rectangle_count": 1,
        "full_M28_by_R27_grid_cells_credited": 0,
        "successful_attempt_count": len(rows),
        "per_attempt_modeled_native_field_calls": str(calls),
        "per_attempt_modeled_native_field_calls_log2": math.log2(calls),
        "per_variant_two_attempt_modeled_native_field_calls": str(2 * calls),
        "all_four_attempts_modeled_native_field_calls": str(4 * calls),
        "all_four_attempts_modeled_native_field_calls_log2": math.log2(
            4 * calls),
        "original_target_online_seconds": [rows[i]["target_online_seconds"]
                                           for i in (0, 3)],
        "zero_run_target_online_seconds": [rows[i]["target_online_seconds"]
                                           for i in (1, 2)],
        "original_target_online_median_seconds": statistics.median(
            rows[i]["target_online_seconds"] for i in (0, 3)),
        "zero_run_target_online_median_seconds": statistics.median(
            rows[i]["target_online_seconds"] for i in (1, 2)),
        "exact_hit_queries_per_attempt": exact_hits,
        "natural_public_target_relation_verified": audit[
            "natural_public_target_relation_verified"],
        "complete_solve_work_log2": None,
        "work_boundary": "nominal regular native field add/mul/sqr calls with inversions expanded at 90 calls; excludes keying, Bloom, memory, disk, setup, and scalar replay",
        "coverage_boundary": "one M28/R24 table/query rectangle; repeated ABBA runs do not add coverage and this partial R24 interval is not a complete R27 grid cell",
        "audit_sha256": sha(audit_path),
        "plan_sha256": sha(PLAN),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    assert not OUTPUT.exists(), "refusing to overwrite Q1080 work receipt"
    report = build()
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"proposal_id": "Q1080",
                      "novel_rectangles": report["novel_rectangle_count"],
                      "full_R27_cells": 0,
                      "four_attempt_work_log2": report[
                          "all_four_attempts_modeled_native_field_calls_log2"]}))


if __name__ == "__main__":
    main()
