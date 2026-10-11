#!/usr/bin/env python3
"""Freeze one M34/R31 ARM search after terminal Q1074 and Q1081 audits."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import n83_full_spill_segment_work as segment_work
import n83_full_spill_work as work
import n83_q1079_full_plan as prior_builder
from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
REPO = HERE.parents[1]
SCREEN = HERE / "n83_full_spill_screen.json"
DESIGN = HERE / "n83_q1086_m34_feasibility.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
CONTROL = RUNS / "n83_q1086_b16_arm_control_v2_bundle.json"
Q1081_PLAN = HERE / "n83_q1081_m32_wave_plan.json"
Q1083_PLAN = HERE / "n83_q1083_m32_wave_plan.json"
Q1085_DESIGN = HERE / "n83_m32_wave_q1085_design.json"
Q1074_PLAN = HERE / "n83_local_arm_m33_r30_q1074_plan.json"
Q1074_RECEIPT = RUNS / "n83_local_arm_m33_r30_q1074.json"
OUTPUT = HERE / "n83_q1086_local_m34_plan.json"
M28 = 1 << 28
R27 = 1 << 27
M34 = 1 << 34
R31 = 1 << 31


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audited_zero(path, row, sage_path, credited):
    assert row["native_result"]["exact_hit_queries"] == 0
    assert row["verified_public_target_relations"] == []
    assert not row["verified_public_target_quotient_table_dlp"]
    assert credited[segment_work.repo_path(path)] == sha(path)
    sage = json.loads(sage_path.read_text())
    assert sage["receipt_sha256"] == sha(path)
    assert sage["verified_relation_count"] == 0
    assert not sage["natural_public_target_relation_verified"]
    return {"receipt": str(path.relative_to(HERE)),
            "receipt_sha256": sha(path),
            "sage_audit": str(sage_path.relative_to(HERE)),
            "sage_audit_sha256": sha(sage_path)}


def freeze():
    screen = json.loads(SCREEN.read_text())
    design = json.loads(DESIGN.read_text())
    ledger = json.loads(LEDGER.read_text())
    control = json.loads(CONTROL.read_text())
    q1081 = json.loads(Q1081_PLAN.read_text())
    q1083 = json.loads(Q1083_PLAN.read_text())
    q1085 = json.loads(Q1085_DESIGN.read_text())
    validate_reference(screen)
    assert design["proposal_id"] == "Q1086"
    assert design["candidate_id"] is None and design["run_id"] is None
    assert design["status"].startswith("design_only_")
    assert design["source_sha256"] == sha(
        HERE / "n83_q1086_m34_feasibility.py")
    assert design["screen_sha256"] == sha(SCREEN)
    assert design["Q1085_design_sha256"] == sha(Q1085_DESIGN)
    assert control["proposal_id"] == "Q1086"
    assert control["executable_proposal_id"] == "Q1061"
    assert control["status"] == "completed_zero_hit_independent_sage_audit"
    assert control["native_exact_hit_queries"] == 0
    assert control["verified_relation_count"] == 0
    assert not control["coverage_credited"]
    for name, artifact in control["artifacts"].items():
        path = HERE / artifact["path"]
        assert path.is_file(), name
        assert sha(path) == artifact["sha256"], name
    control_plan = json.loads((HERE / control[
        "artifacts"]["plan"]["path"]).read_text())
    assert control_plan["status"] == "frozen_bounded_control_v2"
    assert control_plan["table_start"] == 0
    assert control_plan["table_descriptors"] == control["table_descriptors"]
    assert control_plan["query_representatives"] == control[
        "query_representatives"]
    assert control["artifacts"]["derived_runner"]["sha256"] == sha(
        HERE / "run_n83_q1086_portable_b16_chunk.py")
    assert control["artifacts"]["generator"]["sha256"] == sha(
        HERE / "generate_n83_q1086_portable_b16_runner.py")
    for row in (design, ledger, control, q1081, q1083, q1085):
        assert row["curve_id"] == screen["curve_id"]
        assert row["isogeny"] == "none"
        assert row["factor_base_enumerated_set_sha256"] == screen[
            "factor_base"]["enumerated_set_sha256"]
        assert row["actual_usable_points_B_before_folding"] == screen[
            "factor_base"]["actual_usable_points_B_before_folding"]
        assert row["signed_frobenius_columns"] == screen[
            "factor_base"]["signed_frobenius_columns"]
    assert design["public_target"] == control["public_target"] == q1081[
        "public_target"] == screen["public_target"]
    assert ledger["source_sha256"] == sha(Path(segment_work.__file__)), (
        "regenerate the coverage ledger after source changes")
    assert ledger["M34_two_range_accounting_enabled"]
    assert not ledger["pending_Q1086_terminal_receipts"]
    assert ledger["complete_solve_work_log2"] is None
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    assert not ledger["noncompleted_Q1081_ci_bundles"]
    assert not ledger["pending_Q1074_terminal_receipts"]
    assert not ledger["pending_Q1084_terminal_receipts"]

    start, end = design["query_start"], design["query_end_exclusive"]
    assert design["table_start"] == control_plan["table_start"] == 0
    assert design["table_descriptors"] == M34
    assert design["query_representatives"] == R31
    assert design["bits_per_key"] == control["bits_per_key"] == 16
    assert design["hashes"] == control["hashes"] == 10
    assert control["cpu_backend"] == "arm_pmull"
    assert start == control["query_start"] == q1085[
        "query_end_exclusive"] == 50 * (1 << 30)
    assert end == start + R31
    assert q1083["query_end_exclusive"] <= start
    assert q1081["query_end_exclusive"] <= start
    domain = math.comb(screen["factor_base"]["signed_frobenius_columns"], 2)
    domain *= screen["factor_base"]["signed_frobenius_orbit_size"]
    assert end <= domain and M34 <= domain
    for entry in ledger["completed_receipts"]:
        path = REPO / entry["path"]
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

    q1074 = prior_builder.q1074_state(
        screen, {"table_start": 0, "query_starts": [start]})
    assert q1074["status"] == "completed_zero_audited", (
        "Q1074 needs a terminal checked-Sage zero-hit audit")
    assert Q1074_RECEIPT.is_file()
    assert q1074["terminal_audit"]["receipt_sha256"] == sha(Q1074_RECEIPT)
    credited = {entry["path"]: entry["sha256"] for entry in ledger[
        "completed_receipts"]}
    assert credited[segment_work.repo_path(Q1074_RECEIPT)] == sha(
        Q1074_RECEIPT)
    (q1081_rows, q1081_failed, q1081_pending,
     proposals, sage_paths) = segment_work.q1081_ci_rows(screen)
    assert not q1081_failed and not q1081_pending
    assert len(q1081_rows) == len(q1081["query_starts"]) == 8
    assert {row["query_start"] for _, row in q1081_rows} == set(
        q1081["query_starts"])
    audited_q1081 = []
    for path, row in sorted(q1081_rows,
                            key=lambda pair: pair[1]["query_start"]):
        assert row["proposal_id"] == "Q1079"
        assert proposals[path] == "Q1081"
        audited = audited_zero(path, row, sage_paths[path], credited)
        bundle = path.with_name("bundle.json")
        assert json.loads(bundle.read_text())["status"] == "completed_zero_hit"
        audited["bundle"] = str(bundle.relative_to(HERE))
        audited["bundle_sha256"] = sha(bundle)
        audited_q1081.append(audited)
    (q1084_rows, q1084_failed, q1084_proposals,
     q1084_sages, q1084_pending) = segment_work.local_m33_q1084_rows(screen)
    assert not q1084_failed and not q1084_pending, (
        "a launched Q1084 job must have a terminal checked-Sage audit")
    assert len(q1084_rows) <= 1
    q1084_audit = None
    if q1084_rows:
        path, row = q1084_rows[0]
        assert q1084_proposals[path] == "Q1084"
        q1084_audit = audited_zero(path, row, q1084_sages[path], credited)

    sources = {
        "portable_wrapper_source_sha256": HERE /
            "run_n83_q1086_portable_b16_chunk.py",
        "portable_native_source_sha256": HERE /
            "native_n83_orbit_query_spill_portable.cpp",
        "portable_core_source_sha256": HERE /
            "native_n83_bloom_core_portable.hpp",
        "portable_pairs_source_sha256": HERE / "native_n83_pairs_portable.cpp",
        "generated_field_header_sha256": REPO /
            "ecc2k130/runner/generated/eccF83.h",
        "base_receipt_sha256": RUNS / "n83_knownlog_orbit_base_k48194.json",
    }
    assert design["native_source_sha256"] == sha(
        sources["portable_native_source_sha256"])
    assert design["bloom_core_source_sha256"] == sha(
        sources["portable_core_source_sha256"])
    assert control["artifacts"]["native_source"]["sha256"] == sha(
        sources["portable_native_source_sha256"])
    assert control["artifacts"]["bloom_core"]["sha256"] == sha(
        sources["portable_core_source_sha256"])
    calls = field_calls(M34, R31)
    assert str(calls) == design["modeled_native_field_calls"]
    assert math.isclose(math.log2(calls), design[
        "modeled_native_field_calls_log2"])
    base = json.loads(work.BASE.read_text())
    fraction = (M28 / base["zero_pair_key_cap_before_accidental_collisions"]
                * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
                / base["unordered_query_pair_domain"])
    covered = sum(ledger[key] for key in (
        "completed_disjoint_M28_by_R27_cells",
        "completed_M32_extension_M28_by_R27_cells",
        "completed_M33_extension_M28_by_R27_cells"))
    added = (M34 // M28) * (R31 // R27)
    assert added == design["additional_unique_M28_R27_cells_if_fresh"]
    delta = work.intensity(covered + added, cell_fraction=fraction,
                           mean=base["heuristic_mean_four_point_multisets"])
    delta -= work.intensity(covered, cell_fraction=fraction,
                            mean=base["heuristic_mean_four_point_multisets"])
    return {
        "kind": "n83_q1086_source_bound_local_arm_M34_R31_plan",
        "proposal_id": "Q1086", "executable_proposal_id": "Q1061",
        "status": "ready_for_local_launch",
        "candidate_id": None, "run_id": None,
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
        "cpu_backend": "arm_pmull", "query_workers": 4,
        "representative_batch": 8,
        "bits_per_key": 16, "hashes": 10,
        "preferred_spill_root": "/Volumes/SSD990/llm/tmp",
        "minimum_system_free_memory_bytes_before_launch": 36 << 30,
        "minimum_spill_volume_free_bytes_before_launch": 16 << 30,
        "modeled_native_field_calls": str(calls),
        "modeled_native_field_calls_log2": math.log2(calls),
        "exact_bloom_allocation_bytes": design[
            "exact_b16_bloom_allocation_bytes"],
        "projected_candidate_spool_bytes": design[
            "projected_b16_candidate_spool_bytes"],
        "modeled_additional_unique_M28_R27_cells": added,
        "finite_support_placement_model_hit_probability": -math.expm1(
            -delta),
        "measured_natural_relations": None,
        "measured_complete_solve_work_log2": None,
        "Q1074_terminal_audit": q1074["terminal_audit"],
        "Q1074_receipt_sha256": sha(Q1074_RECEIPT),
        "terminal_prior_Q1081_audits": audited_q1081,
        "Q1084_terminal_audit_if_launched": q1084_audit,
        "Q1086_bounded_control_bundle_sha256": sha(CONTROL),
        "Q1086_feasibility_sha256": sha(DESIGN),
        "Q1081_frozen_plan_sha256": sha(Q1081_PLAN),
        "Q1083_frozen_plan_sha256": sha(Q1083_PLAN),
        "Q1085_design_sha256": sha(Q1085_DESIGN),
        "Q1074_plan_sha256": sha(Q1074_PLAN),
        "q1074_state_source_sha256": sha(Path(prior_builder.__file__)),
        "local_launcher_source_sha256": sha(
            HERE / "launch_n83_local_arm_m34_r31_q1086.py"),
        "coverage_ledger_sha256": sha(LEDGER),
        "screen_sha256": sha(SCREEN),
        **{key: sha(path) for key, path in sources.items()},
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "This plan is a gated search dispatch, not measured natural yield or a complete DLP.",
            "The hit probability is a finite-support placement model, not a measured rate.",
            "The 16-bit M34 RSS and full-size wall time remain unmeasured before launch.",
            "Field calls exclude keying, Bloom, memory, disk, failed work, setup, and scalar replay.",
            "Any exact hit requires independent checked-Sage scalar replay."
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite frozen Q1086 plan"
    plan = freeze()
    args.out.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"proposal_id": "Q1086", "plan": str(args.out),
                      "modeled_field_calls_log2": plan[
                          "modeled_native_field_calls_log2"],
                      "prior_Q1081_audits": len(plan[
                          "terminal_prior_Q1081_audits"])}))


if __name__ == "__main__":
    main()
