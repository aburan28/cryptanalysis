#!/usr/bin/env python3
"""Cross-check Q1447 against exact W6 receipts and its declared work units."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    record = json.loads((HERE / "measurement.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    exact_path = PARENT / "runs/n131_q1413_projected_x_w6.json"
    q1414_path = PARENT / "runs/n131_q1414_exact_uniform_query_bound.json"
    q1416_path = PARENT / "runs/n131_q1416_exact_base_pair_index_screen.json"
    exact = json.loads(exact_path.read_text())
    q1414 = json.loads(q1414_path.read_text())
    q1416 = json.loads(q1416_path.read_text())
    assert record["protocol_sha256"] == sha(HERE / "protocol.json")
    assert record["source_sha256"] == sha(HERE / "screen.py")
    assert record["exact_base_receipt_sha256"] == sha(exact_path)
    assert record["curve_id"] == protocol["curve_id"] == exact["curve_id"]
    assert record["isogeny"] == "none"
    assert record["candidate_id"] is record["run_id"] is None
    assert record["complete_solve_work_log2"] is None
    assert record["challenge_dispatch_allowed"] is False
    w6 = record["rows"][0]["model"]
    assert record["exact_weight6_B"] == w6["conditional_B"] == exact[
        "actual_usable_points_B_before_folding"]
    assert record["exact_weight6_K"] == w6["conditional_folded_K"] == exact[
        "signed_frobenius_columns_K"]
    assert record["exact_weight6_base_set_sha256"] == exact["enumerated_set_sha256"]
    assert w6["all_representations_returned_95pct_rank_query_floor"] == q1414[
        "query_bounds"]["rank_success_95_percent"]["minimum_uniform_nonidentity_queries"]
    assert math.isclose(w6["pure_pair_index_plus_K_rows_actions_model_log2"],
                        q1416["index_plus_K_rows_pair_actions_model_log2"],
                        abs_tol=1e-10)
    for spec, sample, row in zip(protocol["sampled_new_strata"],
                                  record["samples"], record["rows"][1:]):
        assert sample["weight"] == spec["weight"] == row["weight_bound"]
        assert sample["sampled_unique_frobenius_orbits"] == spec[
            "unique_frobenius_orbits"]
        assert sample["seed"] == spec["seed"]
        assert sample["trace_vs_point_from_x_controls"] == 64
        assert sample["cofactor_projected_controls"] == 32
        assert sample["nonidentity_projection_controls"] == 32
        assert sample["distinct_projected_x_orbits_in_controls"] == 32
        assert sample["subgroup_order_controls"] == 4
        assert sample["rational_x_orbits"] / sample[
            "sampled_unique_frobenius_orbits"] == sample["rational_fraction"]
        assert sample["rational_fraction_wilson95"][0] < sample[
            "rational_fraction"] < sample["rational_fraction_wilson95"][1]
        assert row["nominal_new_x_masks"] == math.comb(131, spec["weight"])
        assert row["nominal_new_x_orbits"] * 131 == row["nominal_new_x_masks"]
        m = row["model"]
        assert m["conditional_B"] == 262 * m["conditional_folded_K"]
        assert m["scalar_sparse_matrix_proxy_operations"] == 4 * m[
            "conditional_folded_K"] ** 2
        assert m["one_relation_returned_per_query_95pct_rank_query_floor"] >= m[
            "all_representations_returned_95pct_rank_query_floor"]
    assert record["rows"][1]["model"]["scalar_sparse_matrix_proxy_operations"] < 2**61
    assert record["rows"][2]["model"]["scalar_sparse_matrix_proxy_operations"] > 2**61
    print("PASS Q1447 exact-base cross-check and declared work units")


if __name__ == "__main__":
    main()
