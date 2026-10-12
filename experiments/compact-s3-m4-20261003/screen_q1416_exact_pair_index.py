#!/usr/bin/env python3
"""Exact-base logical-action screen for the pure N131 quotient pair index.

The pair-key law is a stated heuristic. This screen charges neither field
arithmetic nor the complete IC pipeline; it cannot certify a solve exponent.
"""

from __future__ import annotations

import argparse
import json
import math
from fractions import Fraction
from pathlib import Path

from run_probe import HERE, sha


BASE = HERE / "runs/n131_q1413_projected_x_w6.json"
BASE_PROTOCOL = HERE / "q1413_projected_x_protocol.json"
PARENT = HERE / "protocol.json"
OUT = HERE / "runs/n131_q1416_exact_base_pair_index_screen.json"


def log2_fraction(value: Fraction) -> float:
    return math.log2(value.numerator) - math.log2(value.denominator)


def build() -> dict:
    base = json.loads(BASE.read_text())
    base_protocol = json.loads(BASE_PROTOCOL.read_text())
    parent = json.loads(PARENT.read_text())["degree_131_design"]
    n = base["field_degree_n"]
    b = base["actual_usable_points_B_before_folding"]
    k = base["signed_frobenius_columns_K"]
    r = parent["curve"]["subgroup_order"]
    assert n == 131 and b == 2 * n * k
    assert base["proposal_id"] == base_protocol["proposal_id"] == "Q1413"
    assert base["parent_base_proposal_id"] == parent["proposal_id"] == "Q1303"
    assert base["curve_id"] == parent["curve"]["curve_id"]
    assert base["normal_basis_weight_bound"] == 6
    assert base["protocol_sha256"] == sha(BASE_PROTOCOL)
    assert parent["curve"]["order"] == 4 * r
    index_states = n * k * k
    one_row_pair_probes = Fraction(2 * r, b * b)
    all_rows_pair_probes = k * one_row_pair_probes
    total_actions = index_states + all_rows_pair_probes
    minimum_key_bytes = 17 * index_states
    return {
        "kind": "q1416_exact_base_pure_quotient_pair_index_model_screen",
        "proposal_id": "Q1416",
        "parent_base_proposal_id": "Q1303",
        "candidate_id": None, "workload_id": None, "run_id": None,
        "curve_id": base["curve_id"], "isogeny": "none",
        "field_degree_n": n, "summands_m": 4,
        "subgroup_order_r": r,
        "normal_basis_weight_bound": 6,
        "actual_usable_points_B_before_folding": b,
        "folded_columns_K": k,
        "base_set_sha256": base["enumerated_set_sha256"],
        "method_family": "pure signed-Frobenius quotient pair index",
        "model_law": (
            "Build n*K^2 pair states; under uniform pair keys and one novel "
            "rank row per match, draw K*2*r/B^2 logical pair probes."),
        "index_states_exact": index_states,
        "index_states_log2": math.log2(index_states),
        "minimum_17_byte_key_storage_bytes_exact": minimum_key_bytes,
        "minimum_17_byte_key_storage_log2_bytes": math.log2(minimum_key_bytes),
        "one_row_pair_probes_model_exact_fraction": {
            "numerator": one_row_pair_probes.numerator,
            "denominator": one_row_pair_probes.denominator,
        },
        "one_row_pair_probes_model_log2": log2_fraction(one_row_pair_probes),
        "K_rows_pair_probes_model_exact_fraction": {
            "numerator": all_rows_pair_probes.numerator,
            "denominator": all_rows_pair_probes.denominator,
        },
        "K_rows_pair_probes_model_log2": log2_fraction(all_rows_pair_probes),
        "index_plus_K_rows_pair_actions_model_log2": log2_fraction(total_actions),
        "pair_action_gap_above_2pow61_model_log2": log2_fraction(total_actions) - 61,
        "scope": (
            "Pure full quotient-pair index; uniform pair-key model; all K "
            "matched rows optimistically novel. The 17-byte storage minimum "
            "excludes witnesses and indexing overhead. Counts logical pair "
            "actions, not calibrated field-operation equivalents. Base "
            "construction, target descent, final relation matrix, and "
            "correctness replay are excluded. Other PDP families are outside "
            "this model."),
        "is_empirical_relation_yield": False,
        "is_lower_bound_on_other_pdp_algorithms": False,
        "is_complete_solve_projection": False,
        "complete_solve_work_log2": None,
        "challenge_dispatch_allowed": False,
        "base_receipt_sha256": sha(BASE),
        "base_protocol_sha256": sha(BASE_PROTOCOL),
        "parent_protocol_sha256": sha(PARENT),
        "source_sha256": sha(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = json.dumps(build(), indent=2) + "\n"
    if args.check:
        assert OUT.read_text() == content
        print("PASS: Q1416 exact-base pure pair-index model")
    else:
        assert not OUT.exists()
        OUT.write_text(content)
        print(OUT)


if __name__ == "__main__":
    main()
