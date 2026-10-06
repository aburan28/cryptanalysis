#!/usr/bin/env python3
"""Freeze the first disjoint M32/R29 wave for one previously unseen point."""

import hashlib
import json
import math
import tempfile
from pathlib import Path

from bench_n83_zero_run_stage import FROZEN, generated_sources
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "n83_full_spill_screen.json"
HOLDOUT = HERE / "n83_holdout_target_20261001.json"
OUTPUT = HERE / "n83_q1090_holdout_m32_wave_plan.json"
M = 1 << 32
R = 1 << 29
K = 48194
L = 166


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    holdout = json.loads(HOLDOUT.read_text())
    assert holdout["curve_id"] == screen["curve_id"]
    assert holdout["curve_identity_record"] == screen["curve_identity_record"]
    assert holdout["isogeny"] == "none"
    assert holdout["fixture_scalar_retained"] is False
    assert holdout["sage_scalar_replay_at_freeze"] is True
    assert holdout["public_target"] != screen["public_target"]
    base = screen["factor_base"]
    assert holdout["factor_base_enumerated_set_sha256"] == base[
        "enumerated_set_sha256"]
    assert base["actual_usable_points_B_before_folding"] == K * L
    assert base["signed_frobenius_columns"] == K
    assert holdout["workload"]["targets"] == [holdout["public_target"]]
    assert holdout["workload"]["target_count"] == 1
    assert holdout["workload_id"] == holdout[
        "workload_record_sha256"][:12]
    candidate_paths = [
        path for path in (HERE / "candidates").glob("IC1N83Ckb1fb8000204*.json")
        if (lambda row: row["implementation"].get(
            "wrapper_source_sha256") == sha(HERE / "run_n83_holdout_chunk.py")
            and row["implementation"]["cpu_backend"] == "x86_pclmul"
            and row["point_decomposition"]["filter"]["bits_per_key"] == 20
        )(json.loads(path.read_text()))
    ]
    assert len(candidate_paths) == 1
    candidate_path = candidate_paths[0]
    candidate = json.loads(candidate_path.read_text())
    candidate_id = candidate["candidate_id"]
    assert candidate_path.stem == candidate_id
    assert candidate["curve"]["curve_id"] == screen["curve_id"]
    assert candidate["factor_base"]["enumerated_set_sha256"] == base[
        "enumerated_set_sha256"]
    assert candidate["isogeny"] == "none"
    assert candidate["point_decomposition"]["table_descriptors_per_job"] == M
    assert candidate["point_decomposition"]["query_representatives_per_job"] == R
    assert candidate["implementation"]["native_source_sha256"] == (
        "33d21efe3386d65359ee07b1e2b307168e23ec57927b0f32f069d1a2865bb81f")

    starts = [i * R for i in range(16)]
    assert starts[-1] + R <= math.comb(K, 2) * L
    source_paths = {
        "runner_source_sha256": HERE / "run_n83_holdout_chunk.py",
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
    assert all(sha(path) == digest for path, digest in FROZEN.items())
    with tempfile.TemporaryDirectory() as temp:
        pairs, core, native = generated_sources(Path(temp))
        generated = {
            "zero_run_pairs_source_sha256": sha(pairs),
            "zero_run_core_source_sha256": sha(core),
            "zero_run_native_source_sha256": sha(native),
        }
    field_calls = 26 * M + 13 * R + 13 * R * 83 + 90 * (
        2 * math.ceil(M / 1024) + 2 * math.ceil(R / 8))
    return {
        "kind": "n83_q1090_fresh_holdout_source_bound_m32_r29_wave",
        "proposal_id": "Q1090", "status": "ready_for_dispatch",
        "candidate_id": candidate_id,
        "candidate_manifest": str(candidate_path.relative_to(HERE)),
        "candidate_manifest_sha256": sha(candidate_path),
        "workload_id": holdout["workload_id"],
        "run_id": candidate_id + "W" + holdout["workload_id"] + "R1",
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": K * L,
        "signed_frobenius_columns": K,
        "public_target": holdout["public_target"], "target_count": 1,
        "table_start": 0, "table_descriptors": M,
        "query_starts": starts, "query_representatives": R,
        "query_end_exclusive": starts[-1] + R,
        "cpu_backend": "x86_pclmul", "workers": 4,
        "representative_batch": 8, "bits_per_key": 20,
        "hashes": 10,
        "minimum_mem_available_bytes": 13 * (1 << 30),
        "minimum_root_free_bytes": 10 * (1 << 30),
        "minimum_spill_free_bytes": 10 * (1 << 30),
        "timeout_seconds_per_job": 21600,
        "modeled_native_field_calls_per_job": str(field_calls),
        "modeled_native_field_calls_sixteen_jobs_log2": math.log2(
            16 * field_calls),
        "measured_natural_relations": None,
        "measured_complete_solve_work_log2": None,
        "holdout_target_sha256": sha(HOLDOUT),
        "factor_base_screen_sha256": sha(SCREEN),
        **{name: sha(path) for name, path in source_paths.items()},
        **generated,
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "The new point was sampled uniformly and its fixture scalar was discarded before search.",
            "This plan predicts no observed relation yield or complete DLP.",
            "A field-call model excludes keying, Bloom, memory, disk, failed work, and replay.",
            "An exact hit requires independent checked-Sage scalar replay.",
        ],
    }


def main():
    assert not OUTPUT.exists(), "refusing to overwrite frozen holdout plan"
    result = freeze()
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"run_id": result["run_id"],
                      "jobs": len(result["query_starts"]),
                      "plan": str(OUTPUT)}))


if __name__ == "__main__":
    main()
