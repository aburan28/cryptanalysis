#!/usr/bin/env python3
"""Audit the physical x86 Q1078 artifact and checked-Sage planted replay."""

import argparse
import hashlib
import json
import statistics
import tempfile
from pathlib import Path

import bench_n83_zero_run_stage as stage
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "n83_full_spill_screen.json"
REFERENCE = HERE / "runs/n83_fast_low_memory_planted.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timing(rows, phase):
    return [row[phase] for row in rows]


def paired_ratio(original, alternate):
    values = [a / b for a in original for b in alternate]
    return {"median_ratio": statistics.median(original) /
            statistics.median(alternate),
            "all_cross_pair_ratio_range": [min(values), max(values)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--github-run-id", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--artifact-digest", required=True)
    args = parser.parse_args()
    root = args.artifact_dir
    output = root / "audit.json"
    assert not output.exists(), "refusing to overwrite a completed audit"
    host_path = root / "host.json"
    workflow_path = root / "workflow_snapshot.yml"
    stage_path = root / "n83_zero_run_stage_bounded_comparison.json"
    planted_path = root / "n83_zero_run_stage_planted_receipt.json"
    sage_path = root / "sage_verify.json"
    host = json.loads(host_path.read_text())
    result = json.loads(stage_path.read_text())
    planted = json.loads(planted_path.read_text())
    sage = json.loads(sage_path.read_text())
    screen = json.loads(SCREEN.read_text())
    reference = json.loads(REFERENCE.read_text())
    validate_reference(screen)

    assert len(args.head_sha) == 40
    assert args.artifact_digest.startswith("sha256:")
    assert host["workflow_sha256"] == sha(workflow_path)
    assert host["screen_sha256"] == sha(SCREEN)
    assert host["curve_id"] == result["curve_id"] == screen["curve_id"]
    assert host["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert host["host_arch"] == result["host_arch"] == "x86_64"
    assert host["host_os"].startswith("Linux-")
    assert host["cpu_pclmul_available"] is True
    assert result["cpu_backend"] == "x86_pclmul"
    assert result["proposal_id"] == planted["proposal_id"] == "Q1078"
    assert result["candidate_id"] is planted["candidate_id"] is None
    assert result["run_id"] is planted["run_id"] is None
    assert result["isogeny"] == planted["isogeny"] == "none"
    assert result["curve_identity_record"] == planted[
        "curve_identity_record"] == screen["curve_identity_record"]
    assert result["factor_base"] == planted[
        "factor_base"] == screen["factor_base"]
    assert result["public_target"] == screen["public_target"]
    assert result["source_sha256"] == planted["source_sha256"] == sha(
        HERE / "bench_n83_zero_run_stage.py")
    assert result["screen_sha256"] == sha(SCREEN)
    assert result["checked_sage_runtime_info_sha256"] is None
    assert result["complete_solve_work_log2"] is None
    for name, digest in result["frozen_sources_sha256"].items():
        assert digest == sha(HERE / name)
    with tempfile.TemporaryDirectory(prefix="n83-q1078-audit-") as directory:
        generated = stage.generated_sources(Path(directory))
        assert {path.name: sha(path) for path in generated} == result[
            "zero_run_generated_source_sha256"]

    original_plant = result["planted_original_native_result"]
    alternate_plant = result["planted_zero_run_native_result"]
    stage.same_outcome(original_plant, alternate_plant)
    assert original_plant["exact_hit_queries"] == 1
    assert alternate_plant["hits"] == [reference[
        "matched_previously_verified_hit"]]
    assert planted["native_result"] == alternate_plant
    assert planted["verified_relation"] == reference["verified_relation"]
    assert planted["fixture_target"] == reference["fixture_target"]
    assert sage["receipt_sha256"] == sha(planted_path)
    assert sage["verified_relation_count"] == 1
    assert sage["verified_relations"][0]["scalar_replay"] is True
    assert sage["verified_relations"][0]["four_point_sum"] is True
    assert sage["natural_public_target_relation_verified"] is False
    assert sage["verified_relations"][0]["recovered_scalar"] == str(
        reference["verified_relation"]["recovered_scalar"])

    originals = result["public_original_native_results"]
    alternatives = result["public_zero_run_native_results"]
    assert len(originals) == len(alternatives) == 2
    for row in originals + alternatives:
        stage.same_outcome(row, originals[0])
        assert row["table_descriptors"] == 1 << 20
        assert row["query_representatives"] == 1 << 18
        assert row["exact_hit_queries"] == 0
    original_query = timing(originals, "query_seconds")
    alternate_query = timing(alternatives, "query_seconds")
    original_online = [row["query_seconds"] + row["exact_replay_seconds"]
                       for row in originals]
    alternate_online = [row["query_seconds"] + row["exact_replay_seconds"]
                        for row in alternatives]
    audit = {
        "kind": "n83_q1078_physical_x86_bounded_stage_audit",
        "proposal_id": "Q1078", "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "github_run_id": args.github_run_id,
        "github_run_url": ("https://github.com/aburan28/cryptanalysis/actions/runs/"
                           + str(args.github_run_id)),
        "head_sha": args.head_sha,
        "github_artifact_digest": args.artifact_digest,
        "physical_backend": "x86_64 Linux PCLMUL",
        "planted_exact_hit_queries": 1,
        "independent_checked_sage_scalar_replay": True,
        "public_exact_hit_queries": 0,
        "query_phase_seconds_original": original_query,
        "query_phase_seconds_zero_run": alternate_query,
        "query_phase_speedup": paired_ratio(original_query, alternate_query),
        "query_plus_replay_seconds_original": original_online,
        "query_plus_replay_seconds_zero_run": alternate_online,
        "query_plus_replay_speedup": paired_ratio(original_online,
                                                  alternate_online),
        "natural_relation_yield": False,
        "complete_solve_work_log2": None,
        "limits": "bounded M20/R18 stage only; no natural n=83 relation, full-size rate, or complete target DLP",
        "host_sha256": sha(host_path),
        "frozen_workflow_sha256": sha(workflow_path),
        "stage_receipt_sha256": sha(stage_path),
        "planted_receipt_sha256": sha(planted_path),
        "sage_verify_sha256": sha(sage_path),
        "source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({"audit": str(output),
                      "query_speedup": audit["query_phase_speedup"],
                      "verified_plant": True}))


if __name__ == "__main__":
    main()
