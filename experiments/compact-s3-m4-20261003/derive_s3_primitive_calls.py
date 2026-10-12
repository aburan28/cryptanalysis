#!/usr/bin/env python3
"""Expand counted S3 field inversions into pinned source-level field calls.

The pinned Gf2/Gf2_128 Itoh-Tsujii chain uses n-1 squarings and
bit_length(n-1) + popcount(n-1) - 2 multiplications per nonzero inverse.
This records *method calls*, not machine instructions or a weighted unit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUT = HERE / "runs/n53_n83_s3_primitive_field_calls.json"
PINNED_CRYPTO_GIT_HEAD = "ea8892a530505a07ca1274f614cdba3b16f96c5c"
PINNED_FIELD_SOURCE_SHA256 = (
    "c7ac4f4c206085ddee1d1d12d6cba7ceb369f639e8d81403afd2f507b0b43338")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand(n: int, counts: dict) -> dict:
    exponent = n - 1
    inner_mul_per_nonzero_inv = (exponent.bit_length()
                                 + exponent.bit_count() - 2)
    inner_sqr_per_nonzero_inv = exponent
    inversions = counts["field_inv_calls"]
    return {
        "top_level_field_mul_calls": counts["field_mul_calls"],
        "top_level_field_sqr_calls": counts["field_sqr_calls"],
        "top_level_field_inv_calls": inversions,
        "inner_mul_calls_per_nonzero_inv": inner_mul_per_nonzero_inv,
        "inner_sqr_calls_per_nonzero_inv": inner_sqr_per_nonzero_inv,
        "expanded_primitive_field_mul_calls": (
            counts["field_mul_calls"] + inversions * inner_mul_per_nonzero_inv),
        "expanded_primitive_field_sqr_calls": (
            counts["field_sqr_calls"] + inversions * inner_sqr_per_nonzero_inv),
        "basis_conversions": counts["basis_conversions"],
        "canonical_rotation_steps": counts["canonical_rotation_steps"],
        "s3_root_calls": counts["s3_root_calls"],
        "point_add_calls": counts["point_add_calls"],
        "point_lifts": counts["point_lifts"],
        "relation_candidates_checked": counts["relation_candidates_checked"],
    }


def build() -> dict:
    build_path = HERE / "native_build_receipt.json"
    build_receipt = json.loads(build_path.read_text())
    assert build_receipt["status"] == "PASS"
    assert build_receipt["crypto_git_head"] == PINNED_CRYPTO_GIT_HEAD
    assert build_receipt["crypto_arithmetic_sources_sha256"][
        "src/cryptanalysis/semaev_decomp.rs"] == PINNED_FIELD_SOURCE_SHA256
    assert build_receipt["source_sha256"] == sha(HERE / "native_s3_root.rs")

    rows = []
    for n, proposals in ((53, (("Q1327", "n53_native_root_full.json"),
                              ("Q1330", "n53_batch_root_full.json"))),
                         (83, (("Q1328", "n83_native_root_capped_2m.json"),
                              ("Q1331", "n83_batch_root_capped_2m.json")))):
        for proposal, name in proposals:
            path = HERE / "runs" / name
            stage = json.loads(path.read_text())
            assert stage["proposal_id"] == proposal
            assert stage["field_degree"] == n
            assert stage["candidate_id"] is None and stage["run_id"] is None
            assert stage["isogeny"] == "none"
            assert stage["native_source_sha256"] == build_receipt[
                "source_sha256"]
            assert stage["cargo_manifest_sha256"] == build_receipt[
                "cargo_manifest_sha256"]
            assert stage["verified_single_target_dlp"] is False
            assert stage["complete_work_log2"] is None
            if n == 83:
                assert stage["status"] == "state_cap_no_relation"
                assert stage["index_satisfiable_s3_states"] == stage[
                    "index_pair_states_examined"]
                assert stage["target_table_hits"] == 0
            else:
                assert stage["status"] == "native_relation_found"
                assert stage["relation"] is not None
            rows.append({
                "proposal_id": proposal,
                "curve_id": stage["curve_id"],
                "workload_id": stage["workload_id"],
                "factor_base_actual_B": stage["actual_usable_points_B"],
                "factor_base_folded_columns_K": stage["folded_columns_K"],
                "n": n,
                "status": stage["status"],
                "phase_call_vectors": {
                    phase: expand(n, counts)
                    for phase, counts in stage["operation_counts"].items()
                },
                "stage_receipt_sha256": sha(path),
            })

    for direct, windowed in ((rows[0], rows[1]), (rows[2], rows[3])):
        assert direct["curve_id"] == windowed["curve_id"]
        assert direct["workload_id"] == windowed["workload_id"]
        assert direct["factor_base_actual_B"] == windowed[
            "factor_base_actual_B"]
        assert direct["factor_base_folded_columns_K"] == windowed[
            "factor_base_folded_columns_K"]
        assert direct["status"] == windowed["status"]

    return {
        "kind": "source_level_primitive_field_call_expansion_for_s3_stages",
        "candidate_id": None,
        "run_id": None,
        "isogeny": "none",
        "field_implementation_crypto_git_head": PINNED_CRYPTO_GIT_HEAD,
        "field_implementation_source_sha256": PINNED_FIELD_SOURCE_SHA256,
        "inverse_chain_formula": {
            "nonzero_inverse_field_mul_calls": "bit_length(n-1)+popcount(n-1)-2",
            "nonzero_inverse_field_sqr_calls": "n-1",
            "zero_inverse_field_mul_calls": 0,
            "zero_inverse_field_sqr_calls": 0,
            "nonzero_input_proof_scope": "Native S3 roots only invert nonzero p, a, or a*ps; batch inversion only inverts a product of nonzero denominators; point_add and point_lifts guard zero denominators. These guards are in the source-bound native stage.",
        },
        "rows": rows,
        "unit_boundary": "source-level calls to the pinned field mul and sqr methods, including calls inside nonzero inv; basis conversion, Frobenius rotations, hash probes, memory traffic, scheduler costs and machine instructions are separate",
        "is_common_weighted_field_operation_unit": False,
        "is_complete_solve_projection": False,
        "source_sha256": sha(Path(__file__)),
        "native_build_receipt_sha256": sha(build_path),
        "native_source_sha256": sha(HERE / "native_s3_root.rs"),
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
        OUT.write_text(expected)
        print(json.dumps({
            "status": "written",
            "proposal_ids": [row["proposal_id"] for row in build()["rows"]],
        }))


if __name__ == "__main__":
    main()
