#!/usr/bin/env python3
"""Exact explicit-index capacity screen for the coupled-seed W14 transfer."""

from collections import Counter
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
COUNT = HERE / "seed_sum_count.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    counted = json.loads(COUNT.read_text())
    assert counted["status"] == "PASS_EXACT_SEED_SUM_TUPLE_COUNTS"
    sizes = Counter(int(line.split()[1]) for line in SUPPORT.read_text().splitlines())
    n = sum(sizes.values())
    assert n == 8220 and len(sizes) == 8160
    m = int(counted["n131"]["signed_pair_states_per_rotation"])
    same_seed = int(counted["n131"]["same_seed_two_pair_states"])
    # Each signed unordered pair that uses column c has four sign choices.
    incidence = {column: 4 * size * (n - size) for column, size in sizes.items()}
    assert sum(incidence.values()) == 2 * m
    free_collision_union = sum(value * value for value in incidence.values())
    free_disjoint_lower = m * m - free_collision_union
    # In a fixed seed-sum bucket, one column of size at most three contributes
    # at most 4*3 signed pairs. The union bound sums over both pair columns.
    max_fixed_bucket_incidence = 4 * max(sizes.values())
    same_seed_collision_union = max_fixed_bucket_incidence * 2 * m
    same_seed_disjoint_lower = same_seed - same_seed_collision_union
    capacity = (4 * 1024**3) // 17
    result = {
        "status": "PASS_EXPLICIT_W14_PAIR_JOIN_CAPACITY_BOUND",
        "source_masks": n, "folded_columns": len(sizes),
        "signed_pair_states_per_rotation": m,
        "free_four_atom_states_before_cross_pair_columns": str(m * m),
        "free_four_atom_distinct_column_lower_bound": str(free_disjoint_lower),
        "same_seed_four_atom_states_before_cross_pair_columns": str(same_seed),
        "same_seed_four_atom_distinct_column_lower_bound": str(same_seed_disjoint_lower),
        "minimum_compressed_group_point_bytes": 17,
        "four_gib_capacity_at_17_bytes_per_state": capacity,
        "free_explicit_index_minimum_bytes": str(17 * free_disjoint_lower),
        "same_seed_explicit_index_minimum_bytes": str(17 * same_seed_disjoint_lower),
        "same_seed_capacity_factor_lower_bound": (
            same_seed_disjoint_lower + capacity - 1) // capacity,
        "scope": "one explicit compressed group point key per distinct-column four-atom state; descriptors and hash overhead excluded; compact symbolic representations outside bound",
        "source_sha256": {"script": sha(Path(__file__)),
                          "support": sha(SUPPORT), "count": sha(COUNT)},
    }
    assert same_seed_disjoint_lower > capacity
    with (HERE / "transfer_w14.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
