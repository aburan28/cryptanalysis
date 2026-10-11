#!/usr/bin/env python3
"""Validate and archive one conditional Q1083 physical-x86 wave artifact."""

import argparse
import json
import shutil
from pathlib import Path

import n83_q1079_full_ci_ingest as prior
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PLAN = HERE / "n83_q1083_m32_wave_plan.json"
SCREEN = HERE / "n83_full_spill_screen.json"
SUCCESS = "n83_public_target_signed_x_query_k48194_exact_replay_chunk"
FAILED = "n83_public_target_signed_x_query_k48194_chunk_failed"


def sha(path):
    return prior.sha(path)


def validated_row(screen, plan, path, source_dir, binary, *, full, start):
    row = json.loads(path.read_text())
    validate_receipt(screen, row)
    assert row["proposal_id"] == "Q1079"
    assert row["query_start"] == start
    assert row["table_descriptors"] == (1 << 32 if full else 1 << 20)
    assert row["query_representatives"] == (1 << 29 if full else 1 << 14)
    if row["kind"] == SUCCESS:
        return prior.verify_row(screen, plan, path, source_dir, binary,
                                full=full, start=start)
    assert row["kind"] == FAILED
    assert row["native_phase_counts"] is None
    assert not row["verified_public_target_quotient_table_dlp"]
    return row


def ingest(artifact, run_id, query_start, artifact_digest,
           workflow_snapshot, archive_root):
    assert run_id > 0 and artifact_digest.startswith("sha256:")
    assert artifact.is_dir() and archive_root.is_absolute()
    assert archive_root.is_dir() and workflow_snapshot.is_file()
    assert PLAN.is_file(), "Q1083 executable plan has not been frozen"
    plan = json.loads(PLAN.read_text())
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    assert plan["proposal_id"] == "Q1079"
    assert plan["wave_proposal_id"] == "Q1083"
    assert plan["executable_proposal_id"] == "Q1079"
    assert plan["status"] == "ready_for_dispatch"
    assert plan["candidate_id"] is plan["run_id"] is None
    assert plan["curve_id"] == screen["curve_id"]
    assert plan["isogeny"] == "none"
    assert plan["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert plan["actual_usable_points_B_before_folding"] == screen[
        "factor_base"]["actual_usable_points_B_before_folding"]
    assert plan["signed_frobenius_columns"] == screen[
        "factor_base"]["signed_frobenius_columns"]
    assert plan["public_target"] == screen["public_target"]
    assert query_start in plan["query_starts"]
    assert plan["table_descriptors"] == 1 << 32
    assert plan["query_representatives"] == 1 << 29
    assert plan["screen_sha256"] == sha(SCREEN)
    assert plan["runner_source_sha256"] == sha(prior.RUNNER)
    assert plan["source_generator_sha256"] == sha(prior.GENERATOR)
    for key, path in (
        ("portable_native_source_sha256", prior.HERE /
         "native_n83_orbit_query_spill_portable.cpp"),
        ("portable_core_source_sha256", prior.HERE /
         "native_n83_bloom_core_portable.hpp"),
        ("portable_pairs_source_sha256", prior.HERE /
         "native_n83_pairs_portable.cpp"),
        ("generated_field_sha256", prior.FIELD),
    ):
        assert plan[key] == sha(path), key
    host_path = artifact / "host.json"
    assert host_path.is_file(), "host preflight receipt missing"
    host = json.loads(host_path.read_text())
    assert host["kind"] == "n83_q1083_M32_R29_physical_x86_preflight"
    assert host["proposal_id"] == "Q1083"
    assert host["executable_proposal_id"] == "Q1079"
    assert host["candidate_id"] is host["run_id"] is None
    assert host["curve_id"] == plan["curve_id"]
    assert host["isogeny"] == "none"
    assert host["factor_base_enumerated_set_sha256"] == plan[
        "factor_base_enumerated_set_sha256"]
    assert host["actual_usable_points_B_before_folding"] == plan[
        "actual_usable_points_B_before_folding"]
    assert host["signed_frobenius_columns"] == plan[
        "signed_frobenius_columns"]
    assert host["query_start"] == query_start
    assert host["table_descriptors"] == plan["table_descriptors"]
    assert host["query_representatives"] == plan["query_representatives"]
    assert host["architecture"].lower() in ("x86_64", "amd64")
    assert host["plan_sha256"] == sha(PLAN)
    assert host["workflow_sha256"] == sha(workflow_snapshot)
    assert host["Q1074_state_at_plan_freeze"] == plan["Q1074_state"]["status"]
    resources_ok = (host["mem_available_bytes"] >= host[
        "minimum_mem_available_bytes"] and host["root_free_bytes"] >= host[
            "minimum_root_free_bytes"])
    control_path = artifact / "control.json"
    full_path = artifact / "full.json"
    assert not (control_path.exists() and (artifact / "control.started.json").exists())
    assert not (full_path.exists() and (artifact / "full.started.json").exists())
    control = (validated_row(screen, plan, control_path,
                             artifact / "control-sources", artifact / "control-bin",
                             full=False, start=query_start)
               if control_path.exists() else None)
    if full_path.exists():
        assert resources_ok and control is not None
        assert control["kind"] == SUCCESS
        full = validated_row(screen, plan, full_path,
                             artifact / "full-sources", artifact / "full-bin",
                             full=True, start=query_start)
        assert full["public_target"] == control["public_target"]
        if full["kind"] == SUCCESS:
            assert full["factor_base"] == control["factor_base"]
    else:
        full = None
    status = ("host_preflight_failed" if not resources_ok else
              "incomplete_no_control_receipt" if control is None else
              "failed_bounded_control" if control["kind"] == FAILED else
              "incomplete_no_terminal_full_receipt" if full is None else
              "failed_full_segment_unknown_work" if full["kind"] == FAILED else
              "native_verified_hit_needs_independent_sage" if full[
                  "verified_public_target_quotient_table_dlp"] else
              "unverified_exact_hit_requires_review" if full[
                  "native_result"]["exact_hit_queries"] else
              "bounded_control_exact_hit_requires_review" if control[
                  "native_result"]["exact_hit_queries"] else
              "completed_zero_hit")
    destination = archive_root / (
        f"n83_zero_run_q1083_M32_R29_ci_{run_id}_qstart{query_start}")
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
    shutil.copyfile(workflow_snapshot, destination / "workflow_snapshot.yml")
    bundle = {
        "kind": "n83_q1083_physical_x86_M32_R29_ci_bundle",
        "proposal_id": "Q1083", "executable_proposal_id": "Q1079",
        "candidate_id": None, "run_id": None,
        "curve_id": plan["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["signed_frobenius_columns"],
        "table_descriptors": 1 << 32,
        "query_start": query_start,
        "query_representatives": 1 << 29,
        "github_run_id": run_id,
        "github_run_url": (
            "https://github.com/aburan28/cryptanalysis/actions/runs/"
            f"{run_id}"),
        "github_artifact_digest": artifact_digest,
        "status": status,
        "artifact_sha256": copied,
        "plan_sha256": sha(PLAN),
        "workflow_snapshot_sha256": sha(workflow_snapshot),
        "screen_sha256": sha(SCREEN),
        "runner_source_sha256": sha(prior.RUNNER),
        "source_generator_sha256": sha(prior.GENERATOR),
        "source_sha256": sha(Path(__file__)),
        "native_exact_hit_queries": full["native_result"]["exact_hit_queries"]
        if full is not None and full["kind"] == SUCCESS else None,
        "natural_public_target_relation_verified": False,
        "complete_solve_work_log2": None,
    }
    (destination / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    return {"bundle": str(destination / "bundle.json"),
            "status": status, "query_start": query_start}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--query-start", type=int, required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--workflow-snapshot", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, default=RUNS)
    args = parser.parse_args()
    print(json.dumps(ingest(args.artifact_dir.resolve(), args.run_id,
                            args.query_start, args.artifact_digest,
                            args.workflow_snapshot, args.archive_root.resolve())))


if __name__ == "__main__":
    main()
