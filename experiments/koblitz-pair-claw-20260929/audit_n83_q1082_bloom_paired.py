#!/usr/bin/env python3
"""Audit Q1082's archived physical-x86 Bloom-density comparison."""

import argparse
import hashlib
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "n83_q1082_m28_r24_bloom_paired_plan.json"
SCREEN = HERE / "n83_full_spill_screen.json"
sys.path.insert(0, str(HERE))
from bench_n83_zero_run_stage import FROZEN, generated_sources  # noqa: E402
from generate_n83_q1082_bloom_runner import derived_bytes  # noqa: E402
from n83_identity_contract import validate_receipt, validate_reference  # noqa: E402

ORDER = ("b20a", "b16a", "b16b", "b20b")
EXACT_KEYS = (
    "actual_B", "table_descriptors", "query_representatives",
    "lifted_query_pairs", "exact_hit_keys", "exact_hit_queries",
    "complement_identity_queries", "hits",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ratios(b20, b16):
    cross = [a / b for a in b20 for b in b16]
    return {"ratio_of_medians": statistics.median(b20) / statistics.median(b16),
            "all_cross_pair_ratio_range": [min(cross), max(cross)]}


def audit(bundle, github_run_id, artifact_digest, head_sha):
    plan = json.loads(PLAN.read_text())
    screen = json.loads(SCREEN.read_text())
    host = json.loads((bundle / "host.json").read_text())
    paired = json.loads((bundle / "paired.json").read_text())
    validate_reference(screen)
    assert plan["proposal_id"] == host["proposal_id"] == paired[
        "proposal_id"] == "Q1082"
    assert plan["candidate_id"] is plan["run_id"] is None
    assert paired["candidate_id"] is paired["run_id"] is None
    assert plan["curve_id"] == screen["curve_id"] == host["curve_id"] == paired[
        "curve_id"]
    assert plan["isogeny"] == screen["isogeny"] == host["isogeny"] == paired[
        "isogeny"] == "none"
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
    assert plan["execution_order"] == list(ORDER)
    assert plan["Q1080_plan_sha256"] == sha(
        HERE / "n83_q1080_m28_r24_paired_plan.json")
    prior = HERE / "runs/n83_q1080_x86_ci_36770585105"
    assert plan["Q1080_audit_sha256"] == sha(prior / "audit.json")
    assert plan["Q1080_paired_sha256"] == sha(prior / "paired.json")
    for key, path in (
        ("Q1079_runner_sha256", HERE / "run_n83_zero_run_chunk.py"),
        ("Q1082_generator_sha256", HERE / "generate_n83_q1082_bloom_runner.py"),
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
    derived = derived_bytes()
    assert hashlib.sha256(derived).hexdigest() == plan[
        "Q1082_derived_runner_sha256"]
    assert (bundle / "q1082_generated_bloom_runner.py").read_bytes() == derived
    rows, sage_rows = [], []
    for name in ORDER:
        path = bundle / f"{name}.json"
        row = json.loads(path.read_text())
        sage = json.loads((bundle / f"{name}_sage_verify.json").read_text())
        validate_receipt(screen, row)
        assert row["proposal_id"] == sage["proposal_id"] == "Q1079"
        assert row["candidate_id"] is row["run_id"] is sage[
            "candidate_id"] is None
        assert row["factor_base"] == screen["factor_base"]
        assert row["public_target"] == plan["public_target"]
        assert row["table_start"] == plan["table_start"]
        assert row["table_descriptors"] == plan["table_descriptors"]
        assert row["query_start"] == plan["query_start"]
        assert row["query_representatives"] == plan["query_representatives"]
        assert row["cpu_backend"] == "x86_pclmul"
        assert row["query_workers"] == plan["workers"]
        assert row["representative_batch"] == plan["representative_batch"]
        assert row["bits_per_key"] == plan["bits_per_key_by_run"][name]
        assert row["hashes"] == plan["hashes"]
        assert row["native_field_add_mul_sqr_call_model"] == plan[
            "modeled_native_field_calls_per_run"]
        assert row["wrapper_source_sha256"] == plan[
            "Q1082_derived_runner_sha256"]
        assert row["zero_run_source_generator_sha256"] == plan[
            "Q1078_generator_sha256"]
        assert row["compiled_binary_sha256"] == sha(bundle / f"{name}-bin")
        source = bundle / f"sources-{name}"
        assert row["native_source_sha256"] == sha(source / "alt_main.cpp")
        assert row["bloom_core_sha256"] == sha(source / "alt_core.hpp")
        assert row["native_pairs_sha256"] == sha(source / "alt_pairs.cpp")
        assert row["generated_field_sha256"] == sha(source / "eccF83.h")
        assert sage["receipt_sha256"] == sha(path)
        assert sage["sage_runtime_info_sha256"] == sha(
            bundle / "runtime_info.json")
        assert sage["verified_relation_count"] == len(sage["verified_relations"])
        assert row["verified_public_target_quotient_table_dlp"] == bool(
            sage["verified_relation_count"])
        rows.append(row)
        sage_rows.append(sage)
    with tempfile.TemporaryDirectory() as temp:
        generated = generated_sources(Path(temp))
        for source, archived in zip(generated, (
            bundle / "sources-b20a/alt_pairs.cpp",
            bundle / "sources-b20a/alt_core.hpp",
            bundle / "sources-b20a/alt_main.cpp")):
            assert sha(source) == sha(archived)
    for name in ("alt_pairs.cpp", "alt_core.hpp", "alt_main.cpp", "eccF83.h"):
        assert len({sha(bundle / f"sources-{run}" / name) for run in ORDER}) == 1
    assert all(all(row["native_result"][key] == rows[0][
        "native_result"][key] for key in EXACT_KEYS) for row in rows[1:])
    assert paired["exact_hit_queries"] == rows[0]["native_result"][
        "exact_hit_queries"]
    assert bool(paired["exact_hit_queries"]) == bool(sage_rows[0][
        "verified_relation_count"])
    for name, row in zip(ORDER, rows):
        assert paired["bloom_positive_queries"][name] == row[
            "native_result"]["bloom_positive_queries"]
        assert paired["query_seconds"][name] == row["native_result"][
            "query_seconds"]
        assert paired["exact_replay_seconds"][name] == row[
            "native_result"]["exact_replay_seconds"]
        assert paired["target_online_seconds"][name] == row[
            "target_online_seconds"]
        assert paired["wrapper_subprocess_wall_seconds"][name] == row[
            "wrapper_subprocess_wall_seconds"]
    b20_online = [rows[i]["target_online_seconds"] for i in (0, 3)]
    b16_online = [rows[i]["target_online_seconds"] for i in (1, 2)]
    online_ratio = ratios(b20_online, b16_online)
    assert math.isclose(paired["median_target_online_speedup_b20_over_b16"],
                        online_ratio["ratio_of_medians"])
    return {
        "kind": "n83_q1082_physical_x86_M28_R24_bloom_paired_audit",
        "proposal_id": "Q1082", "candidate_id": None, "run_id": None,
        "curve_id": plan["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "github_run_id": github_run_id,
        "github_run_url": f"https://github.com/aburan28/cryptanalysis/actions/runs/{github_run_id}",
        "head_sha": head_sha, "github_artifact_digest": artifact_digest,
        "physical_backend": "x86_64 Linux PCLMUL",
        "table_start": plan["table_start"],
        "table_descriptors": plan["table_descriptors"],
        "query_start": plan["query_start"],
        "query_representatives": plan["query_representatives"],
        "exact_hit_queries": paired["exact_hit_queries"],
        "natural_public_target_relation_verified": bool(sage_rows[0][
            "verified_relation_count"]),
        "bloom_positive_queries": paired["bloom_positive_queries"],
        "query_seconds": paired["query_seconds"],
        "exact_replay_seconds": paired["exact_replay_seconds"],
        "target_online_seconds": paired["target_online_seconds"],
        "target_online_speedup_b20_over_b16": online_ratio,
        "modeled_native_field_calls_four_runs_log2": plan[
            "modeled_four_run_field_calls_log2"],
        "novel_coverage_cells": 0,
        "complete_solve_work_log2": None,
        "limits": "same-host stage timing on a repeated public rectangle; no novel coverage or complete-solve exponent",
        "plan_sha256": sha(PLAN), "host_sha256": sha(bundle / "host.json"),
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
