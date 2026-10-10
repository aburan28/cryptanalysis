#!/usr/bin/env python3
"""Exact twelve-column W5 tuple count under two pair-seed equalities."""

from collections import defaultdict
from decimal import Decimal, getcontext
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
INDEX = GOAL / "n41_w5_pair_index_20261010/pair_index.json"
GEOMETRY = GOAL / "n41_w5_ten_source_gate_20261010/geometry_result.json"
R = 549756390943
getcontext().prec = 35


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group(entries, equal_seed):
    result = defaultdict(int)
    for seed1, columns1, weight1 in entries:
        for seed2, columns2, weight2 in entries:
            if equal_seed and seed1 != seed2:
                continue
            if columns1 & columns2:
                continue
            result[columns1 | columns2] += weight1 * weight2
    return result


def main():
    geometry = json.loads(GEOMETRY.read_text())
    orbit = {int(mask): tuple(value)
             for mask, value in geometry["mask_columns"].items()}
    keys = {value: index for index, value in enumerate(sorted(set(orbit.values())))}
    assert len(keys) == 14
    raw = json.loads(INDEX.read_text())["entries"]
    entries = []
    for item in raw:
        a, b = item["mask_a"], item["mask_b"]
        assert orbit[a] != orbit[b]
        bits = (1 << keys[orbit[a]]) | (1 << keys[orbit[b]])
        entries.append((a ^ b, bits, len(item["raw_output_points"])))
    assert len(entries) == 264 and sum(weight for _, _, weight in entries) == 528
    same = group(entries, True)
    free = group(entries, False)
    first_eight = defaultdict(int)
    for mask_a, count_a in same.items():
        for mask_b, count_b in same.items():
            if not mask_a & mask_b:
                first_eight[mask_a | mask_b] += count_a * count_b
    total = sum(count_a * count_c
                for mask_a, count_a in first_eight.items()
                for mask_c, count_c in free.items()
                if not mask_a & mask_c)
    assert total > 0
    receipt = {
        "status": "PASS_EXACT_N41_DISTINCT_COLUMN_TUPLE_COUNT",
        "policy": "six same-rotation W5 signed unordered pairs; first two pairs share XOR seed sum, next two pairs share XOR seed sum, last two free; all twelve folded columns distinct",
        "paired_rotations": [0, 7, 14, 21, 28, 35],
        "actual_factor_base_points_B": 204,
        "effective_folded_columns_K": 14,
        "same_seed_four_leaf_column_sets": len(same),
        "free_four_leaf_column_sets": len(free),
        "first_eight_leaf_column_sets": len(first_eight),
        "valid_twelve_state_tuples": str(total),
        "exact_group_wide_mean_rows_per_subgroup_target": str(Decimal(total) / Decimal(R)),
        "uniform_target_relation_probability_upper_bound": str(min(Decimal(1), Decimal(total) / Decimal(R))),
        "source_sha256": {"script": sha(Path(__file__)),
                          "pair_index": sha(INDEX), "geometry": sha(GEOMETRY)},
    }
    with (HERE / "n41_distinct_count.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
