#!/usr/bin/env python3
"""Source-bound N131 storage gate for this exact fixed-sum join structure."""

import collections
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent.parent
VALID = GOAL / "n131_d13_same_rotation_pairs_20261009/valid_codes.json"
R = 680564733841876926932320129493409985129
RSS_CAP = 4 * 1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = HERE / "n131_projection.json"
    if output.exists():
        raise FileExistsError(output)
    codes = json.loads(VALID.read_text())
    if len(codes) != 4134 or len(set(codes)) != len(codes):
        raise ValueError("audited d13 code set changed")
    buckets = collections.Counter(a ^ b for i, a in enumerate(codes)
                                  for b in codes[i+1:])
    max_pairs = max(buckets.values())
    sums = [code for code, size in buckets.items() if size == max_pairs]
    if max_pairs != 1102 or sums != [1830]:
        raise ValueError("audited fixed-sum bucket changed")
    states = 4 * max_pairs
    triples = states**3
    # Two 131-bit coordinates need 17 bytes each in a lossless direct point
    # record; descriptors, hash-table slots, and allocator overhead add more.
    direct_point_bytes = 2 * ((131 + 7) // 8)
    minimum_direct_table_bytes = triples * direct_point_bytes
    result = {"status": "SOURCE_BOUND_N131_DIRECT_JOIN_GATE",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "candidate_id": None, "valid_leaf_codes": len(codes),
              "fixed_sum_code": sums[0],
              "unordered_usable_pairs": max_pairs,
              "signed_pair_states_per_block": states,
              "three_block_state_count": triples,
              "direct_point_record_bytes": direct_point_bytes,
              "minimum_direct_three_block_table_bytes":
                  minimum_direct_table_bytes,
              "memory_cap_bytes": RSS_CAP,
              "minimum_family_reduction_factor_to_fit":
                  (minimum_direct_table_bytes + RSS_CAP - 1) // RSS_CAP,
              "twelve_block_uniform_support_numerator": states**12,
              "twelve_block_uniform_support_denominator": R,
              "method": "Exact code-bucket count and direct full-point table storage lower bound; no solver extrapolation",
              "valid_codes_sha256": sha(VALID),
              "projection_source_sha256": sha(__file__)}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "fixed_sum_code", "unordered_usable_pairs",
                       "signed_pair_states_per_block", "three_block_state_count",
                       "minimum_direct_three_block_table_bytes",
                       "minimum_family_reduction_factor_to_fit")}, sort_keys=True))


if __name__ == "__main__":
    main()
