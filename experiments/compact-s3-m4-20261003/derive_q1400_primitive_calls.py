#!/usr/bin/env python3
"""Expand pinned Q1400 batch arithmetic into field mul/sqr call vectors.

The result counts source-level F83 method calls on the recorded ordinary
no-hit path. It excludes conversion, canonicalization, Bloom/hash work,
memory traffic, runtime controls, and Sage export arithmetic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUT = HERE / "runs/n83_q1400_primitive_field_calls.json"
N = 83
INV_MUL = 8
INV_SQR = 82


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def batches(count: int, batch_size: int) -> int:
    assert count >= 0 and batch_size > 0
    return (count + batch_size - 1) // batch_size


def vector(mul: int, sqr: int, inv: int) -> dict:
    assert min(mul, sqr, inv) >= 0
    return {
        "top_level_field_mul_calls": mul,
        "top_level_field_sqr_calls": sqr,
        "top_level_field_inv_calls": inv,
        "inverse_inner_field_mul_calls": inv * INV_MUL,
        "inverse_inner_field_sqr_calls": inv * INV_SQR,
        "expanded_primitive_field_mul_calls": mul + inv * INV_MUL,
        "expanded_primitive_field_sqr_calls": sqr + inv * INV_SQR,
    }


def batch_add(count: int, batch_size: int) -> dict:
    # One product multiplication, two backward inverse-prefix
    # multiplications, one slope multiplication, one y multiplication,
    # one slope square, and one nonzero product inversion per batch.
    result = vector(5 * count, count, batches(count, batch_size))
    result.update({"point_pairs": count, "batch_count": batches(count, batch_size),
                   "exceptional_pair_count": 0})
    return result


def batch_signed_x(count: int, batch_count: int) -> dict:
    # As above, but one slope multiplication and one delta multiplication
    # replace the y multiplication; both signed x outputs take one square.
    result = vector(5 * count, 2 * count, batch_count)
    result.update({"center_pair_evaluations": count,
                   "batch_count": batch_count,
                   "exceptional_pair_count": 0})
    return result


def build() -> dict:
    protocol_path = HERE / "q1400_pair_protocol.json"
    input_path = HERE / "native_inputs/n83_q1400_pair_manifest.json"
    build_path = HERE / "native_q1400_pair_build_receipt.json"
    stage_path = HERE / "runs/n83_q1400_pair_comparator.json"
    source_path = HERE / "native_q1400_pair_comparator.cpp"
    dependency_path = HERE.parents[1] / (
        "experiments/koblitz-pair-claw-20260929/native_n83_pairs.cpp")
    header_path = HERE.parents[1] / (
        "experiments/koblitz-pair-claw-20260929/native_n83_bloom_core.hpp")
    protocol = json.loads(protocol_path.read_text())
    inputs = json.loads(input_path.read_text())
    native_build = json.loads(build_path.read_text())
    stage = json.loads(stage_path.read_text())
    native = stage["native_output"]
    pdp = protocol["point_decomposition"]
    assert protocol["proposal_id"] == inputs["proposal_id"] == (
        native_build["proposal_id"]) == stage["proposal_id"] == "Q1400"
    assert protocol["candidate_id"] is inputs["candidate_id"] is (
        native_build["candidate_id"]) is stage["candidate_id"] is None
    assert protocol["run_id"] is stage["run_id"] is None
    assert protocol["isogeny"] == stage["isogeny"] == "none"
    assert protocol["curve_id"] == inputs["curve_id"] == stage["curve_id"]
    assert protocol["workload_id"] == inputs["workload_id"] == stage["workload_id"]
    assert protocol["field_degree"] == inputs["field_degree"] == N
    assert protocol["factor_base_actual_B"] == inputs[
        "actual_usable_points_B"] == stage["factor_base_actual_B"]
    assert protocol["factor_base_folded_columns_K"] == inputs[
        "folded_columns_K"] == stage["factor_base_folded_columns_K"]
    assert protocol["point_decomposition"]["native_source_sha256"] == sha(
        source_path)
    assert protocol["point_decomposition"]["native_dependency_sha256"][
        "experiments/koblitz-pair-claw-20260929/native_n83_pairs.cpp"] == sha(
            dependency_path)
    assert protocol["point_decomposition"]["native_dependency_sha256"][
        "experiments/koblitz-pair-claw-20260929/native_n83_bloom_core.hpp"] == sha(
            header_path)
    assert native_build["native_source_sha256"] == sha(source_path)
    assert native_build["stage_protocol_sha256"] == sha(protocol_path)
    assert stage["stage_protocol_sha256"] == sha(protocol_path)
    assert stage["input_manifest_sha256"] == sha(input_path)
    assert stage["native_build_receipt_sha256"] == sha(build_path)
    assert stage["status"] == "no_exact_hit_at_cap"
    assert native["exact_hit_keys"] == native["exact_hit_queries"] == 0
    assert native["bloom_positive_queries"] == 258
    assert native["complement_identity_queries"] == 0
    assert native["table_descriptors"] == pdp["table_descriptors"]
    assert native["query_representatives"] == pdp["query_representatives"]
    assert native["table_batch"] == pdp["table_batch"]
    assert native["representative_batch"] == pdp["representative_batch"]
    assert native["query_workers"] == pdp["query_workers"] == 1
    assert native["lifted_query_pairs"] == 2 * N * pdp[
        "query_representatives"]
    assert stage["complete_work_log2"] is None
    assert stage["field_operation_equivalent_cost"] is None

    m = pdp["table_descriptors"]
    r = pdp["query_representatives"]
    table_batch = pdp["table_batch"]
    rep_batch = pdp["representative_batch"]
    query_batches = batches(r, rep_batch)
    base_k = protocol["factor_base_folded_columns_K"]
    phase = {
        "target_independent_base_orbit_expansion": {
            **vector(0, 2 * base_k * N, 0),
            "orbit_representatives": base_k,
            "scope": "load_base performs n squarings on each x and y per orbit; separate first-eight on_curve controls omitted",
        },
        "target_independent_table_build": batch_add(m, table_batch),
        "target_frobenius_setup_untimed": {
            **vector(0, 2 * N, 0),
            "scope": "two coordinates squared for n-1 conjugates plus two closure-check squares; occurs after control_seconds and before query_seconds",
        },
        "target_query_pair_build": batch_add(r, rep_batch),
        "target_signed_complement": batch_signed_x(r * N, query_batches),
        "target_exact_table_replay": batch_add(m, table_batch),
    }
    assert phase["target_independent_table_build"]["batch_count"] == 489
    assert query_batches == 1024
    assert native["bloom_positive_queries"] > 0, (
        "exact table replay is conditional on at least one Bloom positive")
    target_phases = ("target_frobenius_setup_untimed",
                     "target_query_pair_build", "target_signed_complement",
                     "target_exact_table_replay")
    charged_target = {
        key: sum(phase[name][key] for name in target_phases)
        for key in ("top_level_field_mul_calls", "top_level_field_sqr_calls",
                    "top_level_field_inv_calls",
                    "expanded_primitive_field_mul_calls",
                    "expanded_primitive_field_sqr_calls")
    }
    assert charged_target["expanded_primitive_field_mul_calls"] == 16_901_576
    assert charged_target["expanded_primitive_field_sqr_calls"] == 4_944_328
    return {
        "kind": "source_level_primitive_field_call_expansion_for_q1400_pair_stage",
        "proposal_id": "Q1400",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "curve_id": stage["curve_id"],
        "workload_id": stage["workload_id"],
        "factor_base_actual_B": stage["factor_base_actual_B"],
        "factor_base_folded_columns_K": base_k,
        "factor_base_enumerated_set_sha256": stage[
            "factor_base_enumerated_set_sha256"],
        "field_degree_n": N,
        "batch_add_formula": "For a nonexceptional pair, five top-level field mul and one sqr call; one nonzero inv per batch. Cross-orbit Q1400 pairs have distinct x-orbits.",
        "batch_signed_x_formula": "For a nonexceptional target/pair center, five top-level field mul and two sqr calls; one nonzero inv per batch. The recorded complement_identity_queries=0 rules out exceptional equal-x centers on this run.",
        "nonzero_inverse_expansion": {
            "field_mul_calls_per_inv": INV_MUL,
            "field_sqr_calls_per_inv": INV_SQR,
            "proof": "The pinned F83 Itoh-Tsujii chain computes x^(2^83-2) with eight mul calls and 82 sqr calls for every nonzero input; batch products are nonzero on the recorded nonexceptional path.",
        },
        "phase_call_vectors": phase,
        "target_dependent_phase_sum_including_untimed_frobenius": charged_target,
        "wall_timing_boundary": {
            "reported_target_query_plus_replay_seconds_exploratory": stage[
                "target_online_seconds_exploratory"],
            "target_frobenius_setup_wall_seconds": None,
            "all_target_dependent_wall_seconds": None,
            "reason": "The target Frobenius conjugates and closure check run before the native query timer; the frozen Q1400 stage receipt only times query and exact replay. Target-dependent control/conversion also run before that timer and are separate.",
        },
        "uncounted_components": [
            "target-independent and target-dependent native correctness controls",
            "checked-Sage base export arithmetic and launcher startup",
            "ONB/polynomial conversion, canonical x rotations, Bloom and exact-table hashing",
            "memory traffic, machine instructions, and timing-to-operation calibration",
        ],
        "unit_boundary": "source-level F83 mul/sqr calls, including Itoh-Tsujii inversion internals; no weighted common field-operation unit",
        "is_common_weighted_field_operation_unit": False,
        "is_complete_solve_projection": False,
        "source_sha256": sha(Path(__file__)),
        "q1400_protocol_sha256": sha(protocol_path),
        "q1400_input_manifest_sha256": sha(input_path),
        "q1400_native_build_receipt_sha256": sha(build_path),
        "q1400_stage_receipt_sha256": sha(stage_path),
        "native_source_sha256": sha(source_path),
        "native_pairs_dependency_sha256": sha(dependency_path),
        "native_bloom_dependency_sha256": sha(header_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    if args.check:
        assert OUT.read_text() == expected
        print(f"PASS {OUT}")
    else:
        assert not OUT.exists(), "refusing to overwrite frozen call expansion"
        OUT.write_text(expected)
        print(json.dumps(build()[
            "target_dependent_phase_sum_including_untimed_frobenius"]))


if __name__ == "__main__":
    main()
