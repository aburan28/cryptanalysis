#!/usr/bin/env python3
"""Reconcile the first natural n=83 hit and the charged search attempts.

The arithmetic count is a *model* of native field API calls. It is not a
measured instruction count or a complete calibrated IC operation total.
"""

import hashlib
import json
import math
from pathlib import Path

from n83_full_spill_screen import field_calls

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
OUTPUT = HERE / "n83_verified_solve_accounting.json"
HIT = RUNS / (
    "n83_zero_run_q1083_M32_R29_ci_36817149475_qstart27380416512")
DIRECT_KINDS = {
    "n83_public_target_signed_x_query_k48194_exact_replay_chunk",
    "n83_public_target_signed_x_query_k48194_chunk_failed",
    "n83_public_target_orbit_query_k48194_exact_replay_chunk",
    "n83_public_target_orbit_query_k48194_chunk_failed",
    "n83_public_target_two_shard_query_k48194_exact_replay_chunk",
    "n83_public_target_two_shard_query_k48194_chunk_failed",
    "n83_q1073_local_arm_M33_R29_interrupted_attempt",
}
START_KIND = "n83_public_target_signed_x_query_k48194_chunk_started"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(HERE.parents[1]))


def main():
    screen = json.loads((HERE / "n83_full_spill_screen.json").read_text())
    ledger = json.loads((HERE / "n83_full_spill_segment_work.json").read_text())
    hit = json.loads((HIT / "full.json").read_text())
    sage = json.loads((HIT / "sage_verify.json").read_text())
    jobs_path = RUNS / "n83_q1083_ci_36817149475_terminal_jobs.json"
    jobs = json.loads(jobs_path.read_text())
    assert len(jobs) == 16 and all(j["status"] == "completed" for j in jobs)
    assert sum(j["conclusion"] == "success" for j in jobs) == 7
    assert sum(j["conclusion"] == "cancelled" for j in jobs) == 9
    assert hit["curve_id"] == sage["curve_id"] == screen["curve_id"]
    assert hit["public_target"] == screen["public_target"]
    assert hit["isogeny"] == sage["isogeny"] == "none"
    base = screen["factor_base"]
    assert hit["factor_base"]["enumerated_set_sha256"] == base[
        "enumerated_set_sha256"] == sage["factor_base_enumerated_set_sha256"]
    assert sage["receipt_sha256"] == sha(HIT / "full.json")
    assert sage["natural_public_target_relation_verified"]
    assert sage["verified_relation_count"] == 1
    assert sage["verified_relations"][0]["scalar_replay"]
    assert sage["verified_relations"][0]["four_point_sum"]
    assert ledger["verified_quotient_table_dlp_receipts"] == [
        relative(HIT / "full.json")]
    assert not ledger["unverified_exact_hit_receipts"]
    assert hit["native_result"]["exact_hit_queries"] == 1
    assert int(hit["native_field_add_mul_sqr_call_model"]) == field_calls(
        hit["table_descriptors"], hit["query_representatives"])

    # Charge every direct target receipt, including repeated archived copies.
    # A missing terminal count is charged one complete planned rectangle. The
    # older orbit-query path makes twice as many target complements as the
    # signed-x path, hence its factor of two. These are shape ceilings within
    # the stated regular-batch call model, not audited dynamic call counts.
    attempts = []
    for path in sorted(RUNS.rglob("*.json")):
        try:
            row = json.loads(path.read_text())
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        if kind not in DIRECT_KINDS | {START_KIND}:
            continue
        if row.get("curve_id") != screen["curve_id"]:
            continue
        if row.get("public_target") != screen["public_target"]:
            continue
        factor_base = row.get("factor_base") or {}
        digest = (row.get("factor_base_enumerated_set_sha256") or
                  factor_base.get("enumerated_set_sha256"))
        assert digest == base["enumerated_set_sha256"], path
        assert row.get("isogeny") == "none", path
        m, r = row["table_descriptors"], row["query_representatives"]
        shape = field_calls(m, r)
        if "orbit_query" in kind or "two_shard" in kind:
            shape *= 2
        declared = row.get("native_field_add_mul_sqr_call_model")
        if declared is not None:
            assert int(declared) <= shape, path
        attempts.append({
            "path": relative(path), "sha256": sha(path),
            "kind": kind, "table_descriptors": m,
            "query_representatives": r,
            "declared_regular_path_calls": declared,
            "charged_shape_calls": str(shape),
            "terminal_receipt": kind != START_KIND,
        })
    assert any(item["path"] == relative(HIT / "full.json") for item in attempts)
    start_paths = [item for item in attempts if not item["terminal_receipt"]]
    assert len(start_paths) == 5  # four cancelled CI jobs plus Q1073
    assert sum("q1083" in x["path"] for x in start_paths) == 4
    assert any("q1073" in x["path"] for x in start_paths)

    charged = sum(int(item["charged_shape_calls"]) for item in attempts)
    complete = int(ledger["completed_selected_route_field_calls"])
    assert charged >= complete
    result = {
        "kind": "n83_verified_public_target_solve_search_accounting",
        "curve_id": screen["curve_id"], "isogeny": "none",
        "proposal_id": "Q1083", "candidate_id": None, "run_id": None,
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": base[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": base["signed_frobenius_columns"],
        "one_public_target": screen["public_target"],
        "recovered_scalar": sage["verified_relations"][0]["recovered_scalar"],
        "natural_four_point_relation_count": 1,
        "independent_sage_scalar_replay": True,
        "hit_full_receipt": relative(HIT / "full.json"),
        "hit_full_receipt_sha256": sha(HIT / "full.json"),
        "hit_sage_audit": relative(HIT / "sage_verify.json"),
        "hit_sage_audit_sha256": sha(HIT / "sage_verify.json"),
        "hit_target_online_seconds": hit["target_online_seconds"],
        "hit_regular_path_field_calls": hit[
            "native_field_add_mul_sqr_call_model"],
        "hit_regular_path_field_calls_log2": math.log2(int(hit[
            "native_field_add_mul_sqr_call_model"])),
        "ledger_completed_selected_route_field_calls": str(complete),
        "ledger_completed_selected_route_field_calls_log2": math.log2(complete),
        "charged_direct_receipt_or_start_count": len(attempts),
        "charged_unfinished_start_count": len(start_paths),
        "conservative_search_shape_calls": str(charged),
        "conservative_search_shape_calls_log2": math.log2(charged),
        "search_shape_below_2_61": charged < 1 << 61,
        "Q1083_terminal_jobs_sha256": sha(jobs_path),
        "Q1083_terminal_job_counts": {"success": 7, "cancelled": 9},
        "accounting_boundary": (
            "all archived direct attempts on this exact public target and base; "
            "charge each receipt and unfinished start marker a full planned "
            "rectangle, including redundant copies, and double the older "
            "orbit-query regular-path formula"),
        "not_priced_by_field_call_model": [
            "key canonicalization, Bloom hashing and probes, allocation, "
            "candidate spill, memory and SSD traffic",
            "exceptional point branches and independent Sage verification",
            "nested stage-comparison controls and target-dependent adaptation",
        ],
        "complete_calibrated_solve_operations": None,
        "complete_calibrated_solve_work_log2": None,
        "online_speedup_vs_paired_rho": None,
        "direct_attempts": attempts,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "natural_four_point_relation_count", "charged_direct_receipt_or_start_count",
        "conservative_search_shape_calls_log2", "complete_calibrated_solve_work_log2")}, indent=2))


if __name__ == "__main__":
    main()
