#!/usr/bin/env python3
"""Freeze the next disjoint Q1083 wave only after eight Q1081 Sage audits."""

import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

import n83_full_spill_segment_work as segment_work
import n83_full_spill_work as work
import n83_q1079_full_plan as prior_builder
from bench_n83_zero_run_stage import FROZEN, generated_sources
from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "n83_full_spill_screen.json"
DESIGN = HERE / "n83_m32_wave_q1083_design.json"
PRIOR = HERE / "n83_q1081_m32_wave_plan.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
OUTPUT = HERE / "n83_q1083_m32_wave_plan.json"
M28 = 1 << 28
R27 = 1 << 27


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    screen = json.loads(SCREEN.read_text())
    design = json.loads(DESIGN.read_text())
    prior = json.loads(PRIOR.read_text())
    ledger = json.loads(LEDGER.read_text())
    validate_reference(screen)
    assert design["proposal_id"] == "Q1083"
    assert design["status"] == "design_waiting_for_Q1081_terminal_audits"
    assert design["candidate_id"] is None and design["run_id"] is None
    assert prior["wave_proposal_id"] == "Q1081"
    assert prior["proposal_id"] == prior["executable_proposal_id"] == "Q1079"
    assert prior["status"] == "ready_for_dispatch"
    assert design["prior_Q1081_plan_sha256"] == sha(PRIOR)
    assert design["prior_Q1081_run_id"] == 36801654799
    for record in (design, prior, ledger):
        assert record["curve_id"] == screen["curve_id"]
        assert record["isogeny"] == "none"
        assert record["factor_base_enumerated_set_sha256"] == screen[
            "factor_base"]["enumerated_set_sha256"]
        assert record["actual_usable_points_B_before_folding"] == screen[
            "factor_base"]["actual_usable_points_B_before_folding"]
        assert record["signed_frobenius_columns"] == screen[
            "factor_base"]["signed_frobenius_columns"]
    assert design["public_target"] == prior["public_target"] == screen[
        "public_target"]
    assert ledger["source_sha256"] == sha(Path(segment_work.__file__)), (
        "regenerate the coverage ledger before freezing another wave")
    assert ledger["complete_solve_work_log2"] is None
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    assert not ledger["noncompleted_Q1081_ci_bundles"]

    m, r = design["table_descriptors"], design["query_representatives"]
    assert design["table_start"] == prior["table_start"] == 0
    assert m == prior["table_descriptors"] == 1 << 32
    assert r == prior["query_representatives"] == 1 << 29
    starts = design["query_starts"]
    assert len(starts) == 16
    assert starts == [prior["query_end_exclusive"] + i * r for i in range(16)]
    assert design["prior_Q1081_query_end_exclusive"] == starts[0]
    assert design["query_end_exclusive"] == starts[-1] + r
    assert design["query_end_exclusive"] <= math.comb(
        screen["factor_base"]["signed_frobenius_columns"], 2) * 166
    for entry in ledger["completed_receipts"]:
        path = HERE.parents[1] / entry["path"]
        row = json.loads(path.read_text())
        begin, end = row["query_start"], row["query_start"] + row[
            "query_representatives"]
        assert max(begin, starts[0]) >= min(end, design["query_end_exclusive"]), (
            entry["path"])

    completed, failed, noncompleted, proposals, sage_paths = (
        segment_work.q1081_ci_rows(screen))
    assert not failed and not noncompleted
    assert len(completed) == len(prior["query_starts"]) == 8, (
        "all eight Q1081 jobs need terminal checked-Sage audits")
    assert {row["query_start"] for _, row in completed} == set(
        prior["query_starts"])
    credited = {entry["path"]: entry["sha256"] for entry in ledger[
        "completed_receipts"]}
    audited = []
    for path, row in sorted(completed, key=lambda item: item[1]["query_start"]):
        assert row["proposal_id"] == "Q1079"
        assert proposals[path] == "Q1081"
        assert row["native_result"]["exact_hit_queries"] == 0
        assert row["verified_public_target_relations"] == []
        assert not row["verified_public_target_quotient_table_dlp"]
        assert credited[segment_work.repo_path(path)] == sha(path)
        sage_path = sage_paths[path]
        sage = json.loads(sage_path.read_text())
        assert sage["receipt_sha256"] == sha(path)
        assert sage["verified_relation_count"] == 0
        assert not sage["natural_public_target_relation_verified"]
        bundle_path = path.with_name("bundle.json")
        bundle = json.loads(bundle_path.read_text())
        assert bundle["status"] == "completed_zero_hit"
        audited.append({
            "receipt": str(path.relative_to(HERE)),
            "receipt_sha256": sha(path),
            "sage_audit": str(sage_path.relative_to(HERE)),
            "sage_audit_sha256": sha(sage_path),
            "bundle": str(bundle_path.relative_to(HERE)),
            "bundle_sha256": sha(bundle_path),
        })
    q1074 = prior_builder.q1074_state(screen, design)
    assert q1074["status"] in ("active_uncredited", "completed_zero_audited")
    if q1074["status"] == "completed_zero_audited":
        terminal = q1074["terminal_audit"]
        receipt_path = HERE / terminal["receipt"]
        assert credited[segment_work.repo_path(receipt_path)] == sha(
            receipt_path)

    source_paths = {
        "runner_source_sha256": HERE / "run_n83_zero_run_chunk.py",
        "source_generator_sha256": HERE / "bench_n83_zero_run_stage.py",
        "portable_native_source_sha256": HERE /
        "native_n83_orbit_query_spill_portable.cpp",
        "portable_core_source_sha256": HERE /
        "native_n83_bloom_core_portable.hpp",
        "portable_pairs_source_sha256": HERE /
        "native_n83_pairs_portable.cpp",
        "generated_field_sha256": HERE.parents[1] /
        "ecc2k130/runner/generated/eccF83.h",
    }
    for key, path in source_paths.items():
        assert prior[key] == sha(path), key
    assert all(sha(path) == digest for path, digest in FROZEN.items())
    with tempfile.TemporaryDirectory() as temp:
        pairs, core, native = generated_sources(Path(temp))
        generated_hashes = {
            "zero_run_pairs_source_sha256": sha(pairs),
            "zero_run_core_source_sha256": sha(core),
            "zero_run_native_source_sha256": sha(native),
        }
    for key, digest in generated_hashes.items():
        assert prior[key] == digest

    per_job = field_calls(m, r)
    assert str(per_job) == design["modeled_native_field_calls_per_job"]
    assert math.isclose(math.log2(16 * per_job), design[
        "modeled_native_field_calls_sixteen_jobs_log2"])
    base = json.loads(work.BASE.read_text())
    cell_fraction = (
        M28 / base["zero_pair_key_cap_before_accidental_collisions"]
        * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
        / base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]
    completed_cells = ledger["M32_completed_zero_hit_model_check"][
        "unique_completed_primary_and_M32_extension_cells"]
    added_cells = len(starts) * (r // R27) * (m // M28)
    increment = work.intensity(
        completed_cells + added_cells, cell_fraction=cell_fraction, mean=mean
    ) - work.intensity(
        completed_cells, cell_fraction=cell_fraction, mean=mean)
    return {
        "kind": "n83_q1083_source_bound_sixteen_job_M32_R29_zero_run_plan",
        "proposal_id": "Q1079", "wave_proposal_id": "Q1083",
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
        "minimum_mem_available_bytes": prior["minimum_mem_available_bytes"],
        "minimum_root_free_bytes": prior["minimum_root_free_bytes"],
        "minimum_spill_free_bytes": prior["minimum_spill_free_bytes"],
        "timeout_seconds_per_job": prior["timeout_seconds_per_job"],
        "modeled_native_field_calls_per_job": str(per_job),
        "modeled_native_field_calls_sixteen_jobs_log2": math.log2(
            len(starts) * per_job),
        "finite_support_placement_model_additional_unique_M28_R27_cells":
            added_cells,
        "finite_support_placement_model_hit_probability_sixteen_jobs":
            -math.expm1(-increment),
        "measured_natural_relations": None,
        "measured_complete_solve_work_log2": None,
        "terminal_prior_Q1081_audits": audited,
        "Q1074_state": q1074,
        "Q1083_design_sha256": sha(DESIGN),
        "prior_Q1081_plan_sha256": sha(PRIOR),
        "coverage_ledger_sha256": sha(LEDGER),
        "screen_sha256": sha(SCREEN),
        **{key: sha(path) for key, path in source_paths.items()},
        **generated_hashes,
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
    assert not args.out.exists(), "refusing to overwrite frozen Q1083 plan"
    result = freeze()
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "wave_proposal_id": "Q1083", "plan": str(args.out),
        "prior_audits": len(result["terminal_prior_Q1081_audits"]),
        "modeled_sixteen_job_field_calls_log2": result[
            "modeled_native_field_calls_sixteen_jobs_log2"],
    }))


if __name__ == "__main__":
    main()
