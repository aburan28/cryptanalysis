#!/usr/bin/env python3
"""Freeze Q1084 only after Q1074 and Q1081 zero-hit audits and a wall gate."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import n83_full_spill_work as work
import n83_q1079_full_plan as prior_builder
import n83_q1083_full_plan as q1083_builder
from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
DESIGN = HERE / "n83_q1084_local_m33_design.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
SCREEN = HERE / "n83_full_spill_screen.json"
Q1074_PLAN = HERE / "n83_local_arm_m33_r30_q1074_plan.json"
Q1071_RECEIPT = RUNS / "n83_local_arm_m32_q1071.json"
Q1071_AUDIT = RUNS / "n83_local_arm_m32_q1071_sage_verify.json"
Q1074_RECEIPT = RUNS / "n83_local_arm_m33_r30_q1074.json"
Q1083_PLAN = HERE / "n83_q1083_m32_wave_plan.json"
OUTPUT = HERE / "n83_q1084_local_m33_plan.json"
M28 = 1 << 28
R27 = 1 << 27


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    design = json.loads(DESIGN.read_text())
    ledger = json.loads(LEDGER.read_text())
    screen = json.loads(SCREEN.read_text())
    q1074_plan = json.loads(Q1074_PLAN.read_text())
    validate_reference(screen)
    assert design["proposal_id"] == "Q1084"
    assert design["status"] == (
        "design_waiting_for_Q1074_and_Q1081_terminal_audits")
    assert design["candidate_id"] is None and design["run_id"] is None
    assert design["Q1074_plan_sha256"] == sha(Q1074_PLAN)
    assert design["Q1083_design_sha256"] == sha(
        HERE / "n83_m32_wave_q1083_design.json")
    for row in (design, ledger, q1074_plan):
        assert row["curve_id"] == screen["curve_id"]
        assert row["isogeny"] == "none"
        assert row["factor_base_enumerated_set_sha256"] == screen[
            "factor_base"]["enumerated_set_sha256"]
        assert row["actual_usable_points_B_before_folding"] == screen[
            "factor_base"]["actual_usable_points_B_before_folding"]
        assert row["signed_frobenius_columns"] == screen[
            "factor_base"]["signed_frobenius_columns"]
    assert design["public_target"] == screen["public_target"]
    assert design["table_start"] == q1074_plan["table_start"] == 0
    assert design["table_descriptors"] == q1074_plan[
        "table_descriptors"] == 1 << 33
    assert design["query_representatives"] == q1074_plan[
        "query_representatives"] == 1 << 30
    assert design["query_end_exclusive"] == design["query_start"] + (
        1 << 30)
    assert design["cpu_backend"] == "arm_pmull"
    assert design["preferred_spill_root"] == "/Volumes/SSD990/llm/tmp"
    assert design["minimum_spill_volume_free_bytes_before_launch"] >= (
        8 << 30)
    assert design["minimum_system_free_memory_bytes_before_launch"] >= (
        24 << 30)
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    assert ledger["complete_solve_work_log2"] is None

    # This gate replays every Q1081 archive and Q1074's checked-Sage state.
    q1083 = q1083_builder.freeze()
    assert len(q1083["terminal_prior_Q1081_audits"]) == 8
    assert q1083["Q1074_state"]["status"] == "completed_zero_audited", (
        "Q1074 needs a terminal independent zero-hit audit")
    assert q1083["query_end_exclusive"] == design["query_start"]
    if Q1083_PLAN.exists():
        frozen_q1083 = json.loads(Q1083_PLAN.read_text())
        for key in ("curve_id", "factor_base_enumerated_set_sha256",
                    "public_target", "query_starts", "query_end_exclusive",
                    "Q1083_design_sha256", "prior_Q1081_plan_sha256"):
            assert frozen_q1083[key] == q1083[key], key
        # Q1083 may have frozen while Q1074 was still live, so its recorded
        # Q1074 state can correctly differ from the current terminal state.
    q1074 = json.loads(Q1074_RECEIPT.read_text())
    q1074_wall = q1074["target_online_seconds"]
    assert q1074_wall > 0
    q1071_check = prior_builder.terminal_zero(
        screen, Q1071_RECEIPT, Q1071_AUDIT,
        start=11811160064, descriptors=1 << 32, reps=1 << 29)
    q1071 = json.loads(Q1071_RECEIPT.read_text())
    assert q1071["native_source_sha256"] == q1074[
        "native_source_sha256"] == q1074_plan[
            "portable_native_source_sha256"]
    assert q1071["runtime"]["platform"] == q1074["runtime"][
        "platform"]
    for key in ("cpu_backend", "query_workers", "representative_batch",
                "bits_per_key", "hashes"):
        assert q1071[key] == q1074[key] == design[key], key
    q1071_wall = q1071["target_online_seconds"]
    assert q1071_wall > 0
    ratio = q1074_wall / (4 * q1071_wall)
    assert ratio < 1, (
        "Q1074 M33/R30 target-online time per 256 cells did not beat "
        "four same-host Q1071-shaped M32/R29 calls")

    start, end = design["query_start"], design["query_end_exclusive"]
    for entry in ledger["completed_receipts"]:
        path = HERE.parents[1] / entry["path"]
        row = json.loads(path.read_text())
        begin, finish = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, start) >= min(finish, end), entry["path"]
    for path in RUNS.rglob("*.started.json"):
        row = json.loads(path.read_text())
        if row.get("curve_id") != design["curve_id"]:
            continue
        begin, finish = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, start) >= min(finish, end), str(path)

    paths = {
        "portable_native_source_sha256": HERE /
            "native_n83_orbit_query_spill_portable.cpp",
        "portable_core_source_sha256": HERE /
            "native_n83_bloom_core_portable.hpp",
        "portable_pairs_source_sha256": HERE /
            "native_n83_pairs_portable.cpp",
        "portable_wrapper_source_sha256": HERE /
            "run_n83_portable_chunk.py",
        "generated_field_header_sha256": HERE.parents[1] /
            "ecc2k130/runner/generated/eccF83.h",
        "base_receipt_sha256": RUNS /
            "n83_knownlog_orbit_base_k48194.json",
    }
    for key, path in paths.items():
        assert q1074_plan[key] == sha(path), key
    calls = field_calls(1 << 33, 1 << 30)
    assert str(calls) == design["modeled_native_field_calls"]
    assert math.isclose(math.log2(calls), design[
        "modeled_native_field_calls_log2"])
    base = json.loads(work.BASE.read_text())
    fraction = (M28 / base[
        "zero_pair_key_cap_before_accidental_collisions"] * R27 * base[
            "factor_base"]["signed_frobenius_orbit_size"] / base[
                "unordered_query_pair_domain"])
    covered = sum(ledger[key] for key in (
        "completed_disjoint_M28_by_R27_cells",
        "completed_M32_extension_M28_by_R27_cells",
        "completed_M33_extension_M28_by_R27_cells"))
    delta = work.intensity(covered + 256, cell_fraction=fraction,
                           mean=base["heuristic_mean_four_point_multisets"])
    delta -= work.intensity(covered, cell_fraction=fraction,
                            mean=base["heuristic_mean_four_point_multisets"])
    assert delta > 0
    return {
        **{key: value for key, value in design.items() if key not in (
            "status", "launch_gates", "limits",
            "relation_placement_heuristic_hit_probability")},
        "kind": "n83_q1084_source_bound_local_arm_M33_R30_plan",
        "status": "ready_for_local_launch",
        "relation_placement_heuristic_hit_probability": -math.expm1(-delta),
        "modeled_additional_unique_M28_R27_cells": 256,
        "Q1074_terminal_audit": q1083["Q1074_state"]["terminal_audit"],
        "Q1074_receipt_sha256": sha(Q1074_RECEIPT),
        "Q1074_target_online_seconds": q1074_wall,
        "Q1074_peak_rss_bytes": q1074["native_result"]["peak_rss_bytes"],
        "Q1074_candidate_spill_bytes": q1074[
            "native_result"]["candidate_spill_bytes"],
        "Q1071_terminal_audit": q1071_check,
        "Q1071_target_online_seconds": q1071_wall,
        "M33_vs_four_M32_same_host_online_time_ratio": ratio,
        "terminal_prior_Q1081_audits": q1083[
            "terminal_prior_Q1081_audits"],
        "Q1083_frozen_plan_sha256": sha(Q1083_PLAN)
            if Q1083_PLAN.exists() else None,
        "Q1083_builder_source_sha256": sha(Path(q1083_builder.__file__)),
        "Q1074_state_source_sha256": sha(Path(prior_builder.__file__)),
        "finite_support_model_source_sha256": sha(Path(work.__file__)),
        "field_call_model_source_sha256": sha(
            HERE / "n83_full_spill_screen.py"),
        "coverage_ledger_sha256": sha(LEDGER),
        "screen_sha256": sha(SCREEN),
        "Q1084_design_sha256": sha(DESIGN),
        **{key: sha(path) for key, path in paths.items()},
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "The added hit probability is a finite-support placement model, not measured natural yield.",
            "The local online-wall comparison uses Q1071 and Q1074 on the same ARM backend but different intervals and dates.",
            "Field calls exclude keying, Bloom, memory, disk, failed work, setup, and scalar replay.",
            "Any exact hit requires independent checked-Sage replay before a DLP or complete-work claim."
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite frozen Q1084 plan"
    plan = freeze()
    args.out.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"proposal_id": "Q1084", "plan": str(args.out),
                      "modeled_native_field_calls_log2": plan[
                          "modeled_native_field_calls_log2"]}))


if __name__ == "__main__":
    main()
