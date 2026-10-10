#!/usr/bin/env python3
"""Exact distinct-column source count with first-pair XOR seed 12004."""

import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, getcontext
from math import comb, factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
ORDER = 680564733841876926932320129493409985129
SEED = 12004


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def e10(counts):
    return sum(comb(counts[1], a)*comb(counts[2], b)*comb(counts[3], c)
               *2**b*3**c for a in range(11) for b in range(11-a)
               for c in [10-a-b] if c <= counts[3] and b <= counts[2]
               and a <= counts[1])


def main():
    columns = {}
    groups = defaultdict(list)
    for row in SUPPORT.read_text().splitlines():
        mask, col = map(int, row.split())
        columns[mask] = col
        groups[col].append(mask)
    assert len(columns) == 16441 and len(groups) == 16381
    histogram = Counter(map(len, groups.values()))
    assert histogram == {1: 16323, 2: 56, 3: 2}
    pair_types = Counter()
    for a, col_a in columns.items():
        b = a ^ SEED
        if b in columns and a < b and col_a != columns[b]:
            pair_types[tuple(sorted((len(groups[col_a]),
                                     len(groups[columns[b]]))))] += 1
    assert sum(pair_types.values()) > 0
    suffixes = {}
    tuples = 0
    for key, amount in sorted(pair_types.items()):
        counts = histogram.copy()
        counts[key[0]] -= 1
        counts[key[1]] -= 1
        suffixes[f"{key[0]}-{key[1]}"] = str(e10(counts))
        tuples += 4*32*factorial(10)*amount*e10(counts)
    getcontext().prec = 50
    receipt = {"status": "PASS_EXACT_W15_FIXED_SEED_SIXPAIR_SOURCE_COUNT",
               "curve_id": "EC1N131Ckb1heb5f1998f20b",
               "candidate_id": None,
               "fixed_seed": SEED,
               "fixed_seed_policy": "XOR of first pair masks in the archived constructed control",
               "factor_base_points_B": 197292,
               "folded_columns_K": len(groups),
               "source_masks": len(columns),
               "fixed_seed_unordered_distinct_column_mask_pairs": sum(pair_types.values()),
               "fixed_seed_signed_pair_states": 4*sum(pair_types.values()),
               "first_pair_column_size_types": {f"{a}-{b}": n
                                                for (a,b), n in sorted(pair_types.items())},
               "suffix_e10_by_first_pair_size_type": suffixes,
               "distinct_column_signed_sixpair_tuples": str(tuples),
               "uniform_target_mean_before_nonzero_intermediate_filter":
                   str(Decimal(tuples)/Decimal(ORDER)),
               "count_boundary": "fixed first pair XOR seed; twelve folded columns distinct; all source masks and sign choices exact; zero intermediates and group output not filtered",
               "sha256": {"script": sha(Path(__file__)), "support": sha(SUPPORT),
                          "constructed_control": sha(HERE.parent / "n131_w14_coupled_sixpair_sat_20261010" / "control.json")}}
    with (HERE / "support_count.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "fixed_seed_signed_pair_states": receipt["fixed_seed_signed_pair_states"],
                      "mean": receipt["uniform_target_mean_before_nonzero_intermediate_filter"]}))


if __name__ == "__main__":
    main()
