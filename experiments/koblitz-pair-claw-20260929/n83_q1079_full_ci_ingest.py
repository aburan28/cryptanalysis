#!/usr/bin/env python3
"""Validate and archive one Q1079 physical-x86 full-wave artifact."""

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

from bench_n83_zero_run_stage import FROZEN
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PLAN = HERE / "n83_q1079_m32_wave_plan.json"
SCREEN = HERE / "n83_full_spill_screen.json"
RUNNER = HERE / "run_n83_zero_run_chunk.py"
GENERATOR = HERE / "bench_n83_zero_run_stage.py"
REFERENCE = HERE.parent / "ecc2k130-quotient-pair-probe-20260926/runs/n83_perf_prefix.json"
RHO = HERE.parent / "ecc2k130-quotient-pair-probe-20260926/runs/n83_public_target_rho_solved.json"
BASE = RUNS / "n83_knownlog_orbit_base_k48194.json"
SCHEDULE = RUNS / "n53_n83_unique_schedule_perf.json"
FIELD = HERE.parents[1] / "ecc2k130/runner/generated/eccF83.h"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_calls(m, r):
    inversions = 2 * math.ceil(m / 1024) + 2 * math.ceil(r / 8)
    return 26 * m + 13 * r + 13 * 83 * r + 90 * inversions


def verify_row(screen, plan, path, source_dir, binary, *, full, start):
    row = json.loads(path.read_text())
    validate_receipt(screen, row)
    assert row["kind"] == "n83_public_target_signed_x_query_k48194_exact_replay_chunk"
    assert row["proposal_id"] == "Q1079"
    assert row["cpu_backend"] == "x86_pclmul"
    assert row["table_start"] == 0
    assert row["table_descriptors"] == (1 << 32 if full else 1 << 20)
    assert row["query_representatives"] == (1 << 29 if full else 1 << 14)
    assert row["query_start"] == start
    assert row["query_workers"] == 4 and row["representative_batch"] == 8
    assert row["bits_per_key"] == 20 and row["hashes"] == 10
    assert row["keyer_variant"] == "exact_longest_zero_run"
    assert row["fast_keyer_enabled"] and row["candidate_spill_enabled"]
    assert row["wrapper_source_sha256"] == sha(RUNNER)
    assert row["zero_run_source_generator_sha256"] == sha(GENERATOR)
    assert row["frozen_portable_source_sha256"] == {
        source.name: digest for source, digest in FROZEN.items()}
    for key, reference in (
        ("base_receipt_sha256", BASE),
        ("schedule_receipt_sha256", SCHEDULE),
        ("reference_sha256", REFERENCE),
        ("rho_reference_receipt_sha256", RHO),
        ("generated_field_sha256", FIELD),
    ):
        assert row[key] == sha(reference), key
    for key, name in (
        ("native_pairs_sha256", "alt_pairs.cpp"),
        ("bloom_core_sha256", "alt_core.hpp"),
        ("native_source_sha256", "alt_main.cpp"),
        ("generated_field_sha256", "eccF83.h"),
    ):
        assert row[key] == sha(source_dir / name), key
    assert row["compiled_binary_sha256"] == sha(binary)
    if full:
        for key, row_key in (
            ("zero_run_pairs_source_sha256", "native_pairs_sha256"),
            ("zero_run_core_source_sha256", "bloom_core_sha256"),
            ("zero_run_native_source_sha256", "native_source_sha256"),
        ):
            assert plan[key] == row[row_key]
    native = row["native_result"]
    assert native["candidate_store_mode"] == "unlinked_file"
    assert native["table_descriptors"] == row["table_descriptors"]
    assert native["query_representatives"] == row["query_representatives"]
    assert native["query_start"] == start
    assert native["peak_rss_bytes"] >= native["bloom_bytes"]
    assert native["false_positive_queries"] == (
        native["bloom_positive_queries"] - native["exact_hit_queries"])
    assert native["candidate_spill_bytes"] == 24 * native["bloom_positive_queries"]
    calls = field_calls(row["table_descriptors"], row["query_representatives"])
    assert row["native_field_add_mul_sqr_call_model"] == str(calls)
    assert math.isclose(row["native_field_add_mul_sqr_call_model_log2"],
                        math.log2(calls), abs_tol=1e-12)
    assert row["verified_public_target_quotient_table_dlp"] == bool(
        row["verified_public_target_relations"])
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--query-start", type=int, required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--workflow-snapshot", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, default=RUNS)
    args = parser.parse_args()
    assert args.run_id > 0
    assert args.artifact_digest.startswith("sha256:")
    assert args.archive_root.is_absolute() and args.archive_root.is_dir()
    artifact = args.artifact_dir.resolve()
    assert artifact.is_dir()
    plan = json.loads(PLAN.read_text())
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    assert plan["proposal_id"] == "Q1079" and plan["status"] == "ready_for_dispatch"
    assert plan["curve_id"] == screen["curve_id"]
    assert plan["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert plan["screen_sha256"] == sha(SCREEN)
    assert args.query_start in plan["query_starts"]
    assert plan["table_descriptors"] == 1 << 32
    assert plan["query_representatives"] == 1 << 29
    host_path = artifact / "host.json"
    assert host_path.is_file(), "host preflight receipt missing"
    host = json.loads(host_path.read_text())
    assert host["kind"] == "n83_q1079_M32_R29_physical_x86_preflight"
    assert host["proposal_id"] == "Q1079"
    assert host["candidate_id"] is None and host["run_id"] is None
    assert host["curve_id"] == plan["curve_id"]
    assert host["isogeny"] == "none"
    assert host["factor_base_enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    assert host["actual_usable_points_B_before_folding"] == plan[
        "actual_usable_points_B_before_folding"]
    assert host["signed_frobenius_columns"] == plan["signed_frobenius_columns"]
    assert host["query_start"] == args.query_start
    assert host["table_descriptors"] == 1 << 32
    assert host["query_representatives"] == 1 << 29
    assert host["architecture"].lower() in ("x86_64", "amd64")
    assert host["plan_sha256"] == sha(PLAN)
    assert host["Q1074_state_at_plan_freeze"] == plan["Q1074_state"]["status"]
    assert host["workflow_sha256"] == sha(args.workflow_snapshot)
    resources_ok = (host["mem_available_bytes"] >= host[
        "minimum_mem_available_bytes"] and host["root_free_bytes"] >= host[
            "minimum_root_free_bytes"])
    control_path = artifact / "control.json"
    full_path = artifact / "full.json"
    assert not (control_path.exists() and (artifact / "control.started.json").exists())
    assert not (full_path.exists() and (artifact / "full.started.json").exists())
    control = None
    if control_path.exists():
        control = json.loads(control_path.read_text())
        validate_receipt(screen, control)
        assert control["proposal_id"] == "Q1079"
        if control["kind"] == "n83_public_target_signed_x_query_k48194_exact_replay_chunk":
            control = verify_row(screen, plan, control_path,
                                 artifact / "control-sources", artifact / "control-bin",
                                 full=False, start=args.query_start)
        else:
            assert control["kind"] == "n83_public_target_signed_x_query_k48194_chunk_failed"
            assert control["native_phase_counts"] is None
    full = None
    if full_path.exists():
        assert resources_ok and control is not None
        assert control["kind"] == "n83_public_target_signed_x_query_k48194_exact_replay_chunk"
        full = json.loads(full_path.read_text())
        validate_receipt(screen, full)
        assert full["proposal_id"] == "Q1079"
        assert full["query_start"] == args.query_start
        assert full["table_descriptors"] == 1 << 32
        assert full["query_representatives"] == 1 << 29
        assert full["public_target"] == control["public_target"]
        if full["kind"] == "n83_public_target_signed_x_query_k48194_exact_replay_chunk":
            full = verify_row(screen, plan, full_path,
                              artifact / "full-sources", artifact / "full-bin",
                              full=True, start=args.query_start)
            assert full["factor_base"] == control["factor_base"]
        else:
            assert full["kind"] == "n83_public_target_signed_x_query_k48194_chunk_failed"
            assert full["native_phase_counts"] is None
            assert not full["verified_public_target_quotient_table_dlp"]
    status = ("host_preflight_failed" if not resources_ok else
              "incomplete_no_control_receipt" if control is None else
              "failed_bounded_control" if control["kind"].endswith("_failed") else
              "incomplete_no_terminal_full_receipt" if full is None else
              "failed_full_segment_unknown_work" if full["kind"].endswith("_failed") else
              "native_verified_hit_needs_independent_sage" if full[
                  "verified_public_target_quotient_table_dlp"] else
              "unverified_exact_hit_requires_review" if full[
                  "native_result"]["exact_hit_queries"] else
              "bounded_control_exact_hit_requires_review" if control[
                  "native_result"]["exact_hit_queries"] else
              "completed_zero_hit")
    destination = args.archive_root / (
        f"n83_zero_run_q1079_M32_R29_ci_{args.run_id}_qstart{args.query_start}")
    assert not destination.exists(), "refusing to overwrite archived artifact"
    destination.mkdir()
    copied = {}
    for name in ("host.json", "control.json", "control.started.json",
                 "full.json", "full.started.json", "control-bin", "full-bin"):
        source = artifact / name
        if source.is_file():
            copied[name] = sha(source)
            shutil.copyfile(source, destination / name)
    for name in ("control-sources", "full-sources"):
        source = artifact / name
        if source.is_dir():
            shutil.copytree(source, destination / name)
            copied[name] = {str(path.relative_to(source)): sha(path)
                            for path in source.rglob("*") if path.is_file()}
    shutil.copyfile(args.workflow_snapshot, destination / "workflow_snapshot.yml")
    bundle = {
        "kind": "n83_q1079_physical_x86_M32_R29_ci_bundle",
        "proposal_id": "Q1079", "candidate_id": None, "run_id": None,
        "curve_id": plan["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "table_descriptors": 1 << 32,
        "query_start": args.query_start,
        "query_representatives": 1 << 29,
        "github_run_id": args.run_id,
        "github_run_url": (
            "https://github.com/aburan28/cryptanalysis/actions/runs/"
            f"{args.run_id}"),
        "github_artifact_digest": args.artifact_digest,
        "status": status,
        "artifact_sha256": copied,
        "plan_sha256": sha(PLAN),
        "workflow_snapshot_sha256": sha(args.workflow_snapshot),
        "screen_sha256": sha(SCREEN),
        "runner_source_sha256": sha(RUNNER),
        "source_generator_sha256": sha(GENERATOR),
        "source_sha256": sha(Path(__file__)),
        "native_exact_hit_queries": full["native_result"]["exact_hit_queries"]
        if full is not None and full["kind"].endswith("_chunk") else None,
        "natural_public_target_relation_verified": False,
        "complete_solve_work_log2": None,
    }
    (destination / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    print(json.dumps({"bundle": str(destination / "bundle.json"),
                      "status": status, "query_start": args.query_start}))


if __name__ == "__main__":
    main()
