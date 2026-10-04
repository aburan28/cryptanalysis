#!/usr/bin/env python3
"""Exact cardinality ceiling for sparse S3 pair-intermediate support.

This is a combinatorial screen for uniformly sampled field intermediates,
not a solver-cost extrapolation. It gives no bound for a target-adaptive
intermediate distribution concentrated on the pair-sum image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PROTOCOL = HERE / "protocol.json"
EXACT_N131_BASE = PARENT / "runs/n131_q1413_projected_x_w6.json"
OUTPUT = HERE / "pair_support_screen.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row(n: int, weight: int, nominal_x: int, curve_id: str,
        actual_b: int, folded_k: int, base_digest: str) -> dict:
    assert 0 < weight < n
    assert nominal_x == sum(math.comb(n, j) for j in range(1, weight + 1))
    field_size = 1 << n
    fixed_a_support_ceiling = min(field_size, 2 * nominal_x)
    all_pair_support_ceiling = min(field_size, 2 * nominal_x * nominal_x)
    assert all_pair_support_ceiling < field_size
    return {
        "curve_id": curve_id,
        "field_degree_n": n,
        "normal_basis_weight_bound": weight,
        "nominal_nonzero_sparse_x_count": nominal_x,
        "actual_usable_factor_base_points_B": actual_b,
        "folded_columns_K": folded_k,
        "factor_base_enumerated_set_sha256": base_digest,
        "field_element_count": field_size,
        "fixed_a_pair_intermediate_support_cardinality_upper":
            fixed_a_support_ceiling,
        "fixed_a_uniform_mid_hit_probability_upper_fraction": {
            "numerator": fixed_a_support_ceiling,
            "denominator": field_size,
        },
        "fixed_a_uniform_mid_expected_trials_lower_log2": (
            n - math.log2(fixed_a_support_ceiling)),
        "any_sparse_a_pair_intermediate_support_cardinality_upper":
            all_pair_support_ceiling,
        "any_sparse_a_uniform_mid_hit_probability_upper_fraction": {
            "numerator": all_pair_support_ceiling,
            "denominator": field_size,
        },
        "any_sparse_a_uniform_mid_expected_trials_lower_log2": (
            n - math.log2(all_pair_support_ceiling)),
    }


def build() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    base131 = json.loads(EXACT_N131_BASE.read_text())
    assert protocol["proposal_id"] == "Q1425"
    assert protocol["candidate_id"] is None
    assert protocol["isogeny"] == "none"
    assert base131["proposal_id"] == "Q1413"
    assert base131["candidate_id"] is None
    assert base131["isogeny"] == "none"
    rows = []
    for n in (53, 83):
        workload = protocol["workloads"][f"n{n}_ordinary_reverse_target"]
        base = workload["stage_config_hash_input"]["factor_base"]
        rows.append(row(
            n, base["normal_basis_weight_bound"],
            base["nominal_x_mask_count"], workload["curve_id"],
            workload["factor_base_actual_B"],
            workload["folded_columns_K"],
            workload["factor_base_enumerated_set_sha256"]))
    rows.append(row(
        base131["field_degree_n"], base131["normal_basis_weight_bound"],
        base131["nominal_x_mask_count"], base131["curve_id"],
        base131["actual_usable_points_B_before_folding"],
        base131["signed_frobenius_columns_K"],
        base131["enumerated_set_sha256"]))
    assert [item["field_degree_n"] for item in rows] == [53, 83, 131]
    return {
        "kind": "q1425_exact_sparse_s3_pair_support_cardinality_screen",
        "proposal_id": "Q1425",
        "candidate_id": None,
        "isogeny": "none",
        "status": "PASS_EXACT_CARDINALITY_SCREEN",
        "proof": (
            "In characteristic two, S3(a,b,m)=(ab+(a+b)m)^2+abm+1. "
            "For nonzero a,b this is a nonzero polynomial in m of degree "
            "at most two: if a=b, its linear coefficient is a^2 != 0. "
            "Thus each ordered sparse pair (a,b) contributes at most two "
            "intermediate coordinates m. A fixed a has at most 2*M such "
            "coordinates, and the union over all sparse a has at most "
            "2*M^2, where M=sum(C(n,j), j=1..weight). Curve lifting and "
            "factor-base membership can only shrink these supports."),
        "sampling_law_for_probability_and_trials": (
            "Each proposed intermediate m is independent and uniform over "
            "all 2^n field elements. The fixed-a bound additionally fixes "
            "a independently of m. The all-pair bound permits choosing "
            "a after observing m, but retains uniform m. With independent "
            "uniform trials, the expected first hit is at least the "
            "reciprocal of the probability ceiling."),
        "scope_limit": (
            "These are exact support-cardinality ceilings and conditional "
            "uniform-sampling trial lower bounds. They do not bound "
            "target-adaptive or algebraically guided m, nor ordinary "
            "relation yield, field-operation cost, a complete N131 solve, "
            "or all point-decomposition algorithms."),
        "rows": rows,
        "is_empirical_solver_measurement": False,
        "degree131_complete_solve_work_log2": None,
        "protocol_sha256": sha(PROTOCOL),
        "n131_exact_base_receipt_sha256": sha(EXACT_N131_BASE),
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(build(), sort_keys=True, indent=2) + "\n"
    if args.check:
        assert OUTPUT.read_text() == content
    else:
        assert not OUTPUT.exists()
        OUTPUT.write_text(content)
    print(OUTPUT)


if __name__ == "__main__":
    main()
