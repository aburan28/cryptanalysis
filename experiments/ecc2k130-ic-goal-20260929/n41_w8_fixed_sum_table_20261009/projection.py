#!/usr/bin/env python3
"""Exact N131 d13 table-domain and cross-block clause-count projection."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n131_d13_same_rotation_pairs_20261009"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = HERE / "n131_table_projection.json"
    if output.exists():
        raise FileExistsError(output)
    codes = json.loads((SOURCE / "valid_codes.json").read_text())
    source_result = json.loads((SOURCE / "result.json").read_text())
    if (len(codes) != 4134 or len(set(codes)) != 4134 or
            source_result["valid_selector_count"] != 4134 or
            source_result["pair_count_max_bucket"] != 1102):
        raise ValueError("audited d13 selector source changed")
    values = set(codes)
    bucket = [(a, a ^ 1830) for a in codes
              if a < (a ^ 1830) and (a ^ 1830) in values]
    if len(bucket) != 1102 or len({x for pair in bucket for x in pair}) != 2204:
        raise ValueError("fixed-sum source bucket changed")
    pair_outputs = 2 * len(bucket)
    blocks = 12
    # Each mask-pair has two distinct x outputs. With the audited K=4134
    # column policy, different mask pairs use disjoint folded columns.
    same_pair_conflicts_per_two_blocks = 4 * len(bucket)
    block_pairs = blocks * (blocks - 1) // 2
    onehot_clauses_per_block = 3 * pair_outputs - 3
    result = {
        "status": "SOURCE_BOUND_N131_EXACT_TABLE_PROJECTION",
        "curve_id": "EC1N131Ckb1heb5f1998f20b",
        "candidate_id": None,
        "valid_leaf_codes": len(codes),
        "fixed_sum_code": 1830,
        "unordered_usable_mask_pairs": len(bucket),
        "x_output_descriptors_per_block": pair_outputs,
        "signed_group_states_per_block": 2 * pair_outputs,
        "block_count": blocks,
        "factor_base_folded_columns_K": 4134,
        "descriptor_selector_variables": blocks * pair_outputs,
        "sequential_onehot_auxiliary_variables": blocks * (pair_outputs - 1),
        "sequential_onehot_clauses_excluding_target_flags":
            blocks * onehot_clauses_per_block,
        "cross_block_conflict_clauses_under_frozen_column_policy":
            block_pairs * same_pair_conflicts_per_two_blocks,
        "field_output_bit_constraints_upper_count": blocks * 131,
        "balanced_outer_s3_link_count": blocks - 1,
        "result_scope": "exact finite-domain representation and clause counts; no search-time bound",
        "valid_codes_sha256": sha(SOURCE / "valid_codes.json"),
        "source_result_sha256": sha(SOURCE / "result.json"),
        "projection_source_sha256": sha(__file__),
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "x_output_descriptors_per_block",
                       "descriptor_selector_variables",
                       "sequential_onehot_clauses_excluding_target_flags",
                       "cross_block_conflict_clauses_under_frozen_column_policy")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
