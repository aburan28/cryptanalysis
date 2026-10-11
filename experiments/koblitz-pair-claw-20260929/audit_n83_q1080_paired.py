#!/usr/bin/env python3
"""Audit Q1080's archived physical-x86 ABBA rectangle and Sage replays."""

import argparse
import hashlib
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "n83_q1080_m28_r24_paired_plan.json"
SCREEN = HERE / "n83_full_spill_screen.json"
sys.path.insert(0, str(HERE))
from bench_n83_zero_run_stage import FROZEN, generated_sources  # noqa: E402
from n83_identity_contract import validate_receipt, validate_reference  # noqa: E402

ORDER = ("original1", "zero_run1", "zero_run2", "original2")
NATIVE_KEYS = (
    "actual_B", "table_descriptors", "query_representatives",
    "lifted_query_pairs", "bloom_positive_queries",
    "duplicate_positive_keys", "exact_hit_keys", "exact_hit_queries",
    "false_positive_queries", "complement_identity_queries", "hits",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ratios(first, second):
    values = [a / b for a in first for b in second]
    return {"ratio_of_medians": statistics.median(first) /
            statistics.median(second),
            "all_cross_pair_ratio_range": [min(values), max(values)]}


def audit(bundle, github_run_id, artifact_digest, head_sha):
    plan = json.loads(PLAN.read_text())
    screen = json.loads(SCREEN.read_text())
    host = json.loads((bundle / "host.json").read_text())
    paired = json.loads((bundle / "paired.json").read_text())
    validate_reference(screen)
    assert plan["proposal_id"] == paired["proposal_id"] == host[
        "proposal_id"] == "Q1080"
    assert plan["status"] == "ready_for_bounded_paired_dispatch"
    assert plan["candidate_id"] is plan["run_id"] is None
    assert plan["curve_id"] == screen["curve_id"] == host["curve_id"] == paired[
        "curve_id"]
    assert plan["isogeny"] == screen["isogeny"] == host["isogeny"] == "none"
    assert host["host_arch"].lower() in ("x86_64", "amd64")
    assert host["cpu_pclmul_available"]
    assert host["mem_available_bytes"] >= plan["minimum_mem_available_bytes"]
    assert host["root_free_bytes"] >= plan["minimum_root_free_bytes"]
    assert host["plan_sha256"] == sha(PLAN)
    assert host["workflow_sha256"] == sha(bundle / "workflow_snapshot.yml")
    assert plan["screen_sha256"] == sha(SCREEN)
    assert plan["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert plan["actual_usable_points_B_before_folding"] == 8000204
    assert plan["signed_frobenius_columns"] == 48194
    assert plan["query_start"] == paired["query_start"] == 22548578304
    assert plan["execution_order"] == [
        "Q1061", "Q1079", "Q1079", "Q1061"]
    for key, path in (
        ("Q1061_runner_sha256", HERE / "run_n83_portable_chunk.py"),
        ("Q1079_runner_sha256", HERE / "run_n83_zero_run_chunk.py"),
        ("Q1078_generator_sha256", HERE / "bench_n83_zero_run_stage.py"),
        ("portable_native_source_sha256", HERE /
         "native_n83_orbit_query_spill_portable.cpp"),
        ("portable_core_source_sha256", HERE /
         "native_n83_bloom_core_portable.hpp"),
        ("portable_pairs_source_sha256", HERE /
         "native_n83_pairs_portable.cpp"),
        ("generated_field_sha256", HERE.parents[1] /
         "ecc2k130/runner/generated/eccF83.h"),
    ):
        assert plan[key] == sha(path), key
    assert all(sha(path) == digest for path, digest in FROZEN.items())
    rows = []
    sage_rows = []
    for name in ORDER:
        path = bundle / f"{name}.json"
        row = json.loads(path.read_text())
        sage = json.loads((bundle / f"{name}_sage_verify.json").read_text())
        validate_receipt(screen, row)
        expected_proposal = "Q1079" if name.startswith("zero_run") else "Q1061"
        assert row["proposal_id"] == sage["proposal_id"] == expected_proposal
        assert row["candidate_id"] is sage["candidate_id"] is None
        assert row["curve_id"] == sage["curve_id"] == plan["curve_id"]
        assert row["isogeny"] == sage["isogeny"] == "none"
        assert row["factor_base"] == screen["factor_base"]
        assert row["public_target"] == plan["public_target"]
        assert row["table_start"] == plan["table_start"]
        assert row["table_descriptors"] == plan["table_descriptors"]
        assert row["query_start"] == plan["query_start"]
        assert row["query_representatives"] == plan["query_representatives"]
        assert row["cpu_backend"] == "x86_pclmul"
        assert row["query_workers"] == plan["workers"]
        assert row["representative_batch"] == plan["representative_batch"]
        assert row["bits_per_key"] == plan["bits_per_key"]
        assert row["hashes"] == plan["hashes"]
        assert row["native_field_add_mul_sqr_call_model"] == plan[
            "modeled_native_field_calls_per_run"]
        assert math.isclose(row["native_field_add_mul_sqr_call_model_log2"],
                            plan["modeled_native_field_calls_per_run_log2"])
        assert sage["receipt_sha256"] == sha(path)
        assert sage["natural_public_target_relation_verified"] == bool(
            sage["verified_relation_count"])
        assert row["verified_public_target_quotient_table_dlp"] == bool(
            sage["verified_relation_count"])
        assert row["compiled_binary_sha256"] == sha(bundle / f"{name}-bin")
        for key, source in (
            ("generated_field_sha256", HERE.parents[1] /
             "ecc2k130/runner/generated/eccF83.h"),
            ("reference_sha256", HERE.parent /
             "ecc2k130-quotient-pair-probe-20260926/runs/n83_perf_prefix.json"),
        ):
            assert row[key] == sha(source), key
        if name.startswith("zero_run"):
            source_dir = bundle / ("sources1" if name == "zero_run1" else
                                   "sources2")
            assert row["wrapper_source_sha256"] == plan["Q1079_runner_sha256"]
            assert row["zero_run_source_generator_sha256"] == plan[
                "Q1078_generator_sha256"]
            assert row["native_source_sha256"] == sha(source_dir / "alt_main.cpp")
            assert row["bloom_core_sha256"] == sha(source_dir / "alt_core.hpp")
            assert row["native_pairs_sha256"] == sha(source_dir / "alt_pairs.cpp")
            assert row["generated_field_sha256"] == sha(source_dir / "eccF83.h")
        else:
            assert row["wrapper_source_sha256"] == plan["Q1061_runner_sha256"]
            assert row["native_source_sha256"] == plan[
                "portable_native_source_sha256"]
            assert row["bloom_core_sha256"] == plan[
                "portable_core_source_sha256"]
            assert row["native_pairs_sha256"] == plan[
                "portable_pairs_source_sha256"]
        rows.append(row)
        sage_rows.append(sage)
    with tempfile.TemporaryDirectory() as temp:
        generated = generated_sources(Path(temp))
        for source, archived in zip(generated, (
            bundle / "sources1/alt_pairs.cpp", bundle / "sources1/alt_core.hpp",
            bundle / "sources1/alt_main.cpp")):
            assert sha(source) == sha(archived)
    for name in ("alt_pairs.cpp", "alt_core.hpp", "alt_main.cpp", "eccF83.h"):
        assert sha(bundle / "sources1" / name) == sha(
            bundle / "sources2" / name)
    assert all(all(row["native_result"][key] == rows[0][
        "native_result"][key] for key in NATIVE_KEYS) for row in rows[1:])
    native = rows[0]["native_result"]
    assert paired["all_four_exact_outcomes_equal"]
    assert paired["exact_hit_queries"] == native["exact_hit_queries"]
    assert paired["bloom_positive_queries"] == native["bloom_positive_queries"]
    assert bool(native["exact_hit_queries"]) == bool(sage_rows[0][
        "verified_relation_count"])
    original = [rows[i]["native_result"]["query_seconds"] for i in (0, 3)]
    zero_run = [rows[i]["native_result"]["query_seconds"] for i in (1, 2)]
    original_online = [rows[i]["target_online_seconds"] for i in (0, 3)]
    zero_run_online = [rows[i]["target_online_seconds"] for i in (1, 2)]
    assert paired["original_query_seconds"] == original
    assert paired["zero_run_query_seconds"] == zero_run
    assert paired["original_query_plus_replay_seconds"] == original_online
    assert paired["zero_run_query_plus_replay_seconds"] == zero_run_online
    return {
        "kind": "n83_q1080_physical_x86_M28_R24_paired_audit",
        "proposal_id": "Q1080", "candidate_id": None, "run_id": None,
        "curve_id": plan["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "github_run_id": github_run_id,
        "github_run_url": f"https://github.com/aburan28/cryptanalysis/actions/runs/{github_run_id}",
        "head_sha": head_sha,
        "github_artifact_digest": artifact_digest,
        "physical_backend": "x86_64 Linux PCLMUL",
        "table_start": plan["table_start"],
        "table_descriptors": plan["table_descriptors"],
        "query_start": plan["query_start"],
        "query_representatives": plan["query_representatives"],
        "exact_hit_queries": native["exact_hit_queries"],
        "bloom_positive_queries": native["bloom_positive_queries"],
        "natural_public_target_relation_verified": bool(
            sage_rows[0]["verified_relation_count"]),
        "query_seconds_original": original,
        "query_seconds_zero_run": zero_run,
        "query_speedup": ratios(original, zero_run),
        "query_plus_replay_seconds_original": original_online,
        "query_plus_replay_seconds_zero_run": zero_run_online,
        "query_plus_replay_speedup": ratios(original_online, zero_run_online),
        "modeled_native_field_calls_per_run_log2": plan[
            "modeled_native_field_calls_per_run_log2"],
        "modeled_native_field_calls_four_runs_log2": plan[
            "modeled_four_run_field_calls_log2"],
        "novel_rectangle_coverage_credit": 1,
        "complete_solve_work_log2": None,
        "limits": "same-host stage timing and one small public rectangle; four runs charged, coverage credited once; no complete-solve exponent",
        "plan_sha256": sha(PLAN),
        "host_sha256": sha(bundle / "host.json"),
        "paired_sha256": sha(bundle / "paired.json"),
        "receipt_sha256": {name: sha(bundle / f"{name}.json") for name in ORDER},
        "sage_verify_sha256": {name: sha(bundle / f"{name}_sage_verify.json")
                               for name in ORDER},
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--github-run-id", type=int, required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite audit"
    report = audit(args.bundle, args.github_run_id,
                   args.artifact_digest, args.head_sha)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
