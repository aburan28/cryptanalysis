#!/usr/bin/env python3
"""Freeze Q1085 only after the preceding n=83 rectangles are audited."""

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

import n83_full_spill_segment_work as segment_work
import n83_full_spill_work as work
import n83_q1079_full_plan as q1079_builder
from bench_n83_zero_run_stage import FROZEN, generated_sources
from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_full_spill_screen.json"
DESIGN = HERE / "n83_m32_wave_q1085_design.json"
Q1081_PLAN = HERE / "n83_q1081_m32_wave_plan.json"
Q1083_PLAN = HERE / "n83_q1083_m32_wave_plan.json"
Q1083_DESIGN = HERE / "n83_m32_wave_q1083_design.json"
Q1084_DESIGN = HERE / "n83_q1084_local_m33_design.json"
Q1084_PLAN = HERE / "n83_q1084_local_m33_plan.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
OUTPUT = HERE / "n83_q1085_m32_wave_plan.json"
M28 = 1 << 28
R27 = 1 << 27


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
    return {
        "receipt": str(path.relative_to(HERE)),
        "receipt_sha256": sha(path),
        "sage_audit": str(sage_path.relative_to(HERE)),
        "sage_audit_sha256": sha(sage_path),
    }


def freeze():
    assert Q1083_PLAN.is_file(), (
        "Q1083 has no frozen executable plan or terminal audits")
    screen = json.loads(SCREEN.read_text())
    design = json.loads(DESIGN.read_text())
    q1081 = json.loads(Q1081_PLAN.read_text())
    q1083 = json.loads(Q1083_PLAN.read_text())
    ledger = json.loads(LEDGER.read_text())
    validate_reference(screen)
    assert design["proposal_id"] == "Q1085"
    assert design["status"] == "design_waiting_for_Q1083_terminal_audits"
    assert design["candidate_id"] is None and design["run_id"] is None
    assert design["source_sha256"] == sha(HERE / "n83_q1085_m32_wave_design.py")
    assert design["Q1081_plan_sha256"] == sha(Q1081_PLAN)
    assert design["Q1083_design_sha256"] == sha(Q1083_DESIGN)
    assert design["Q1084_design_sha256"] == sha(Q1084_DESIGN)
    assert q1081["wave_proposal_id"] == "Q1081"
    assert q1083["wave_proposal_id"] == "Q1083"
    assert q1083["source_sha256"] == sha(HERE / "n83_q1083_full_plan.py")
    assert q1083["Q1083_design_sha256"] == sha(Q1083_DESIGN)
    assert q1083["prior_Q1081_plan_sha256"] == sha(Q1081_PLAN)
    assert len(q1083["terminal_prior_Q1081_audits"]) == 8
    for record in (design, q1081, q1083, ledger):
        assert record["curve_id"] == screen["curve_id"]
        assert record["isogeny"] == "none"
        assert record["factor_base_enumerated_set_sha256"] == screen[
            "factor_base"]["enumerated_set_sha256"]
        assert record["actual_usable_points_B_before_folding"] == screen[
            "factor_base"]["actual_usable_points_B_before_folding"]
        assert record["signed_frobenius_columns"] == screen[
            "factor_base"]["signed_frobenius_columns"]
    assert design["public_target"] == q1083["public_target"] == screen[
        "public_target"]
    assert ledger["source_sha256"] == sha(Path(segment_work.__file__)), (
        "regenerate the coverage ledger before freezing Q1085")
    assert ledger["complete_solve_work_log2"] is None
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    for key in ("noncompleted_Q1081_ci_bundles", "noncompleted_Q1083_ci_bundles",
                "pending_Q1074_terminal_receipts", "pending_Q1084_terminal_receipts"):
        assert not ledger[key], key

    starts = design["query_starts"]
    m, r = design["table_descriptors"], design["query_representatives"]
    assert len(starts) == 32
    assert m == q1083["table_descriptors"] == 1 << 32
    assert r == q1083["query_representatives"] == 1 << 29
    assert design["table_start"] == q1083["table_start"] == 0
    assert design["max_parallel_jobs"] == 8
    assert design["cpu_backend"] == q1083["cpu_backend"] == "x86_pclmul"
    assert design["prior_Q1084_query_end_exclusive"] == starts[0]
    assert starts == [starts[0] + i * r for i in range(32)]
    assert design["query_end_exclusive"] == starts[-1] + r
    assert q1083["query_end_exclusive"] + (1 << 30) == starts[0]
    assert design["query_end_exclusive"] <= math.comb(
        screen["factor_base"]["signed_frobenius_columns"], 2) * 166
    for entry in ledger["completed_receipts"]:
        path = HERE.parents[1] / entry["path"]
        row = json.loads(path.read_text())
        begin, end = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, starts[0]) >= min(end, design["query_end_exclusive"]), (
            entry["path"])
    for path in RUNS.rglob("*.started.json"):
        row = json.loads(path.read_text())
        if row.get("curve_id") != design["curve_id"]:
            continue
        begin, end = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, starts[0]) >= min(end, design["query_end_exclusive"]), (
            str(path))

    credited = {entry["path"]: entry["sha256"] for entry in ledger[
        "completed_receipts"]}
    q1074 = q1079_builder.q1074_state(screen, design)
    assert q1074["status"] == "completed_zero_audited", (
        "Q1074 needs a terminal independent zero-hit audit")
    q1074_receipt = HERE / q1074["terminal_audit"]["receipt"]
    assert credited[segment_work.repo_path(q1074_receipt)] == sha(q1074_receipt)

    completed, failed, noncompleted, proposals, sage_paths = (
        segment_work.q1083_ci_rows(screen))
    assert not failed and not noncompleted
    assert len(completed) == len(q1083["query_starts"]) == 16, (
        "all sixteen Q1083 jobs need terminal checked-Sage audits")
    assert {row["query_start"] for _, row in completed} == set(
        q1083["query_starts"])
    q1083_audits = []
    for path, row in sorted(completed, key=lambda pair: pair[1]["query_start"]):
        assert row["proposal_id"] == "Q1079"
        assert proposals[path] == "Q1083"
        audit = audited_zero(path, row, sage_paths[path], credited)
        bundle_path = path.with_name("bundle.json")
        bundle = json.loads(bundle_path.read_text())
        assert bundle["status"] == "completed_zero_hit"
        audit["bundle"] = str(bundle_path.relative_to(HERE))
        audit["bundle_sha256"] = sha(bundle_path)
        q1083_audits.append(audit)

    q1084_completed, q1084_failed, q1084_proposals, q1084_sages, pending = (
        segment_work.local_m33_q1084_rows(screen))
    assert not q1084_failed and not pending, (
        "a launched Q1084 job must have a terminal checked-Sage audit")
    assert len(q1084_completed) <= 1
    q1084_audit = None
    if q1084_completed:
        path, row = q1084_completed[0]
        assert q1084_proposals[path] == "Q1084"
        q1084_audit = audited_zero(path, row, q1084_sages[path], credited)
    if Q1084_PLAN.exists():
        q1084_plan = json.loads(Q1084_PLAN.read_text())
        assert q1084_plan["proposal_id"] == "Q1084"
        assert q1084_plan["query_end_exclusive"] == starts[0]
        assert q1084_plan["curve_id"] == screen["curve_id"]
        assert q1084_plan["isogeny"] == "none"

    sources = {
        "runner_source_sha256": HERE / "run_n83_zero_run_chunk.py",
        "source_generator_sha256": HERE / "bench_n83_zero_run_stage.py",
        "portable_native_source_sha256": HERE /
            "native_n83_orbit_query_spill_portable.cpp",
        "portable_core_source_sha256": HERE /
            "native_n83_bloom_core_portable.hpp",
        "portable_pairs_source_sha256": HERE / "native_n83_pairs_portable.cpp",
        "generated_field_sha256": HERE.parents[1] /
            "ecc2k130/runner/generated/eccF83.h",
    }
    for key, path in sources.items():
        assert q1083[key] == sha(path), key
    assert all(sha(path) == digest for path, digest in FROZEN.items())
    with tempfile.TemporaryDirectory() as temp:
        pairs, core, native = generated_sources(Path(temp))
        generated = {
            "zero_run_pairs_source_sha256": sha(pairs),
            "zero_run_core_source_sha256": sha(core),
            "zero_run_native_source_sha256": sha(native),
        }
    for key, digest in generated.items():
        assert q1083[key] == digest

    calls = field_calls(m, r)
    assert str(calls) == design["modeled_native_field_calls_per_job"]
    assert math.isclose(math.log2(len(starts) * calls), design[
        "modeled_native_field_calls_thirty_two_jobs_log2"])
    base = json.loads(work.BASE.read_text())
    fraction = (M28 / base["zero_pair_key_cap_before_accidental_collisions"]
                * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
                / base["unordered_query_pair_domain"])
    covered = ledger["M32_completed_zero_hit_model_check"][
        "unique_completed_primary_and_M32_extension_cells"]
    added = len(starts) * (r // R27) * (m // M28)
    assert added == design["additional_unique_M28_R27_cells_if_fresh"]
    delta = (work.intensity(covered + added, cell_fraction=fraction,
                            mean=base["heuristic_mean_four_point_multisets"])
             - work.intensity(covered, cell_fraction=fraction,
                              mean=base["heuristic_mean_four_point_multisets"]))
    return {
        "kind": "n83_q1085_source_bound_thirty_two_job_M32_R29_zero_run_plan",
        "proposal_id": "Q1079", "wave_proposal_id": "Q1085",
        "executable_proposal_id": "Q1079", "status": "ready_for_dispatch",
        "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "public_target": screen["public_target"], "target_count": 1,
        "table_start": 0, "table_descriptors": m,
        "query_starts": starts, "query_representatives": r,
        "query_end_exclusive": design["query_end_exclusive"],
        "cpu_backend": design["cpu_backend"],
        "workers": design["query_workers"],
        "representative_batch": design["representative_batch"],
        "bits_per_key": design["bits_per_key"],
        "hashes": design["hashes"],
        "max_parallel_jobs": design["max_parallel_jobs"],
        "minimum_mem_available_bytes": q1083["minimum_mem_available_bytes"],
        "minimum_root_free_bytes": q1083["minimum_root_free_bytes"],
        "minimum_spill_free_bytes": q1083["minimum_spill_free_bytes"],
        "timeout_seconds_per_job": q1083["timeout_seconds_per_job"],
        "modeled_native_field_calls_per_job": str(calls),
        "modeled_native_field_calls_thirty_two_jobs_log2": math.log2(
            len(starts) * calls),
        "finite_support_placement_model_additional_unique_M28_R27_cells":
            added,
        "finite_support_placement_model_hit_probability_thirty_two_jobs":
            -math.expm1(-delta),
        "measured_natural_relations": None,
        "measured_complete_solve_work_log2": None,
        "terminal_prior_Q1083_audits": q1083_audits,
        "Q1074_terminal_audit": q1074["terminal_audit"],
        "Q1084_terminal_audit_if_launched": q1084_audit,
        "Q1085_design_sha256": sha(DESIGN),
        "Q1083_frozen_plan_sha256": sha(Q1083_PLAN),
        "Q1084_frozen_plan_sha256": sha(Q1084_PLAN)
            if Q1084_PLAN.exists() else None,
        "coverage_ledger_sha256": sha(LEDGER),
        "screen_sha256": sha(SCREEN),
        "q1074_state_source_sha256": sha(Path(q1079_builder.__file__)),
        **{key: sha(path) for key, path in sources.items()},
        **generated,
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "This is a source-bound wave dispatch, not measured natural yield or a complete DLP.",
            "The added hit probability is a finite-support placement model, not a measured rate.",
            "Field calls exclude keying, Bloom, memory, disk, setup, failed work, and scalar replay.",
            "Any exact hit requires independent checked-Sage replay before a DLP or work claim."
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite frozen Q1085 plan"
    result = freeze()
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "wave_proposal_id": "Q1085", "plan": str(args.out),
        "prior_audits": len(result["terminal_prior_Q1083_audits"]),
        "modeled_thirty_two_job_field_calls_log2": result[
            "modeled_native_field_calls_thirty_two_jobs_log2"],
    }))


if __name__ == "__main__":
    main()
