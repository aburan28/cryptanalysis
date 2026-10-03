#!/usr/bin/env python3
"""Source-bound feasibility screen for one fresh M34/R31 n=83 search."""

import hashlib
import json
import math
from pathlib import Path

import n83_full_spill_work as work
from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_full_spill_screen.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
Q1085 = HERE / "n83_m32_wave_q1085_design.json"
Q1083 = HERE / "n83_m32_wave_q1083_design.json"
Q1074 = HERE / "n83_local_arm_m33_r30_q1074_plan.json"
Q1073_RECEIPT = RUNS / "n83_local_arm_m33_q1073_retry2.json"
Q1073_AUDIT = RUNS / "n83_local_arm_m33_q1073_retry2_sage_verify.json"
Q1073_RUNTIME = RUNS / "n83_local_arm_m33_q1073_retry2_runtime_info.json"
Q1082_DIR = RUNS / "n83_q1082_x86_ci_36792009510"
Q1082_B16 = Q1082_DIR / "b16a.json"
Q1082_B20 = Q1082_DIR / "b20a.json"
Q1082_B16_AUDIT = Q1082_DIR / "b16a_sage_verify.json"
Q1082_B20_AUDIT = Q1082_DIR / "b20a_sage_verify.json"
Q1082_RUNTIME = Q1082_DIR / "runtime_info.json"
Q1074_PREFLIGHT = RUNS / "n83_local_arm_m33_r30_q1074_preflight.json"
NATIVE = HERE / "native_n83_orbit_query_spill_portable.cpp"
CORE = HERE / "native_n83_bloom_core_portable.hpp"
OUTPUT = HERE / "n83_q1086_m34_feasibility.json"
M28 = 1 << 28
R27 = 1 << 27
M34 = 1 << 34
R31 = 1 << 31


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audited_zero(screen, receipt_path, audit_path, runtime_path):
    receipt = json.loads(receipt_path.read_text())
    audit = json.loads(audit_path.read_text())
    runtime = json.loads(runtime_path.read_text())
    validate_receipt(screen, receipt)
    assert runtime["status"] == "verified"
    if receipt["sage_runtime_info_sha256"] is not None:
        assert receipt["sage_runtime_info_sha256"] == sha(runtime_path)
    assert audit["sage_runtime_info_sha256"] == sha(runtime_path)
    assert receipt["native_result"]["exact_hit_queries"] == 0
    assert not receipt["verified_public_target_quotient_table_dlp"]
    assert not receipt["verified_public_target_relations"]
    assert audit["receipt_sha256"] == sha(receipt_path)
    assert audit["verified_relation_count"] == 0
    assert not audit["natural_public_target_relation_verified"]
    return receipt


def main():
    screen = json.loads(SCREEN.read_text())
    ledger = json.loads(LEDGER.read_text())
    q1085 = json.loads(Q1085.read_text())
    q1083 = json.loads(Q1083.read_text())
    q1074 = json.loads(Q1074.read_text())
    preflight = json.loads(Q1074_PREFLIGHT.read_text())
    validate_reference(screen)
    for row in (ledger, q1085, q1074, preflight):
        assert row["curve_id"] == screen["curve_id"]
        assert row["isogeny"] == "none"
        assert row["factor_base_enumerated_set_sha256"] == screen[
            "factor_base"]["enumerated_set_sha256"]
        assert row["actual_usable_points_B_before_folding"] == screen[
            "factor_base"]["actual_usable_points_B_before_folding"]
        assert row["signed_frobenius_columns"] == screen[
            "factor_base"]["signed_frobenius_columns"]
    assert q1085["proposal_id"] == "Q1085"
    assert q1083["proposal_id"] == "Q1083"
    assert q1083["curve_id"] == screen["curve_id"]
    assert q1083["isogeny"] == "none"
    assert q1083["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert q1085["status"] == "design_waiting_for_Q1083_terminal_audits"
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    assert preflight["proposal_id"] == "Q1074"
    assert preflight["system_memory_bytes"] == 48 * (1 << 30)

    q1073 = audited_zero(
        screen, Q1073_RECEIPT, Q1073_AUDIT, Q1073_RUNTIME)
    b16 = audited_zero(screen, Q1082_B16, Q1082_B16_AUDIT, Q1082_RUNTIME)
    b20 = audited_zero(screen, Q1082_B20, Q1082_B20_AUDIT, Q1082_RUNTIME)
    assert q1073["table_descriptors"] == 1 << 33
    assert q1073["query_representatives"] == 1 << 29
    assert q1073["bits_per_key"] == 20
    assert b16["table_descriptors"] == b20["table_descriptors"] == M28
    assert b16["query_representatives"] == b20[
        "query_representatives"] == 1 << 24
    assert b16["bits_per_key"] == 16 and b20["bits_per_key"] == 20
    assert b16["hashes"] == b20["hashes"] == q1073["hashes"] == 10
    assert b16["public_target"] == b20["public_target"] == q1073[
        "public_target"] == screen["public_target"]
    assert b16["native_result"]["bloom_bytes"] == (
        (M28 * 16 + 511) // 512 + 1024) * 64

    start = q1085["query_end_exclusive"]
    end = start + R31
    domain = math.comb(screen["factor_base"]["signed_frobenius_columns"], 2)
    domain *= screen["factor_base"]["signed_frobenius_orbit_size"]
    assert start % R31 == 0
    assert end <= domain and M34 <= domain
    for entry in ledger["completed_receipts"]:
        path = HERE.parents[1] / entry["path"]
        row = json.loads(path.read_text())
        left, right = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(left, start) >= min(right, end), entry["path"]
    for path in RUNS.rglob("*.started.json"):
        row = json.loads(path.read_text())
        if row.get("curve_id") != screen["curve_id"]:
            continue
        left, right = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(left, start) >= min(right, end), str(path)

    b16_positives = b16["native_result"]["bloom_positive_queries"]
    b20_positives = b20["native_result"]["bloom_positive_queries"]
    scale = R31 // b16["query_representatives"]
    predicted_16_positives = b16_positives * scale
    predicted_20_positives = b20_positives * scale
    local_20_positives = q1073["native_result"][
        "bloom_positive_queries"] * (R31 // q1073["query_representatives"])
    bloom_bytes = ((M34 * 16 + 511) // 512 + 1024) * 64
    candidate_slot_bytes = (predicted_16_positives * 10 // 7 + 1024) * 28
    spool_bytes = predicted_16_positives * 24
    assert candidate_slot_bytes < bloom_bytes
    assert preflight["system_memory_bytes"] > bloom_bytes
    calls = field_calls(M34, R31)
    base = json.loads(work.BASE.read_text())
    cell_fraction = (
        M28 / base["zero_pair_key_cap_before_accidental_collisions"]
        * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
        / base["unordered_query_pair_domain"])
    covered = sum(ledger[key] for key in (
        "completed_disjoint_M28_by_R27_cells",
        "completed_M32_extension_M28_by_R27_cells",
        "completed_M33_extension_M28_by_R27_cells"))
    added = (M34 // M28) * (R31 // R27)
    q1083_calls = len(q1083["query_starts"]) * field_calls(
        q1083["table_descriptors"], q1083["query_representatives"])
    assert (len(q1083["query_starts"])
            * (q1083["table_descriptors"] // M28)
            * (q1083["query_representatives"] // R27)) == added
    assert math.isclose(math.log2(q1083_calls), q1083[
        "modeled_native_field_calls_sixteen_jobs_log2"])
    intensity = work.intensity(
        covered + added, cell_fraction=cell_fraction,
        mean=base["heuristic_mean_four_point_multisets"])
    intensity -= work.intensity(
        covered, cell_fraction=cell_fraction,
        mean=base["heuristic_mean_four_point_multisets"])
    result = {
        "kind": "n83_q1086_single_fresh_M34_R31_sixteen_bit_bloom_feasibility_screen",
        "proposal_id": "Q1086", "candidate_id": None, "run_id": None,
        "status": "design_only_waiting_for_Q1074_and_Q1081_terminal_audits",
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "public_target": screen["public_target"], "target_count": 1,
        "table_start": 0, "table_descriptors": M34,
        "query_start": start, "query_representatives": R31,
        "query_end_exclusive": end,
        "bits_per_key": 16, "hashes": 10,
        "modeled_native_field_calls": str(calls),
        "modeled_native_field_calls_log2": math.log2(calls),
        "additional_unique_M28_R27_cells_if_fresh": added,
        "Q1083_equal_cell_sixteen_job_modeled_field_calls_log2": math.log2(
            q1083_calls),
        "Q1086_to_Q1083_equal_cell_modeled_field_call_ratio": calls /
            q1083_calls,
        "finite_support_placement_model_hit_probability_at_screen":
            -math.expm1(-intensity),
        "measured_natural_relations": None,
        "measured_complete_solve_work_log2": None,
        "Q1082_M28_R24_measured_b16_positives": b16_positives,
        "Q1082_M28_R24_measured_b20_positives": b20_positives,
        "Q1073_M33_R29_measured_b20_positives": q1073[
            "native_result"]["bloom_positive_queries"],
        "projected_M34_R31_b16_positives": predicted_16_positives,
        "projected_M34_R31_b20_positives_from_Q1082": predicted_20_positives,
        "projected_M34_R31_b20_positives_from_Q1073": local_20_positives,
        "projected_b20_positive_crosscheck_relative_difference": abs(
            predicted_20_positives - local_20_positives) /
            local_20_positives,
        "exact_b16_bloom_allocation_bytes": bloom_bytes,
        "projected_b16_candidate_spool_bytes": spool_bytes,
        "projected_b16_candidate_slot_bytes": candidate_slot_bytes,
        "Q1074_preflight_physical_memory_bytes": preflight[
            "system_memory_bytes"],
        "launch_gates": [
            "Do not launch concurrently with Q1074 or any other memory-heavy local search.",
            "Require Q1074 and all Q1081 jobs to have terminal checked-Sage audits, and stop on any verified or unresolved exact hit.",
            "Extend the coverage ledger to represent M34's table shards 32 through 63 and independently verify a bounded M34-compatible control.",
            "Require at least 36 GiB available physical memory and 16 GiB free SSD spill before a source-bound full plan or launch.",
            "Use the repository checked-Sage launcher and save runtime info before measured arithmetic."
        ],
        "limits": [
            "This is a feasibility screen, not a frozen plan, run, relation, or complete DLP.",
            "Positive count and candidate storage scale Q1082's physical x86 M28/R24 observations by 128; full-size ARM memory and wall time are unmeasured.",
            "The two 20-bit positive-count projections cross-check scaling across Q1082 and Q1073 but do not validate a 16-bit full-size run.",
            "Bloom allocation is exact for the current source; RSS, temporary allocation, SSD consumption, and runtime are not upper-bounded by this screen.",
            "The hit probability is a finite-support placement model at the current audited coverage, not measured natural yield.",
            "The equal-cell Q1083 comparison is a field-call model, not a same-host wall-time comparison.",
            "Field calls omit keying, Bloom, memory, disk, setup, failed work, and scalar replay."
        ],
        "screen_sha256": sha(SCREEN),
        "coverage_ledger_sha256": sha(LEDGER),
        "Q1085_design_sha256": sha(Q1085),
        "Q1083_design_sha256": sha(Q1083),
        "Q1074_plan_sha256": sha(Q1074),
        "Q1074_preflight_sha256": sha(Q1074_PREFLIGHT),
        "Q1073_receipt_sha256": sha(Q1073_RECEIPT),
        "Q1073_sage_audit_sha256": sha(Q1073_AUDIT),
        "Q1073_runtime_info_sha256": sha(Q1073_RUNTIME),
        "Q1082_b16_receipt_sha256": sha(Q1082_B16),
        "Q1082_b16_sage_audit_sha256": sha(Q1082_B16_AUDIT),
        "Q1082_b20_receipt_sha256": sha(Q1082_B20),
        "Q1082_b20_sage_audit_sha256": sha(Q1082_B20_AUDIT),
        "Q1082_runtime_info_sha256": sha(Q1082_RUNTIME),
        "native_source_sha256": sha(NATIVE),
        "bloom_core_source_sha256": sha(CORE),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "proposal_id": "Q1086", "modeled_field_calls_log2": math.log2(calls),
        "fresh_cells": added,
        "modeled_hit_probability": -math.expm1(-intensity),
        "exact_bloom_gib": bloom_bytes / (1 << 30),
        "projected_candidate_spool_gib": spool_bytes / (1 << 30),
    }))


if __name__ == "__main__":
    main()
