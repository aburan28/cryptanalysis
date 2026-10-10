#!/usr/bin/env python3
"""Exact W15 twelve-column source count with two independent pair seeds."""

import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, getcontext
from math import comb, factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
CONTROL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010" / "control.json"
ORDER = 680564733841876926932320129493409985129
SEEDS = (12004, 9022)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def e8(counts):
    return sum(comb(counts[1], a) * comb(counts[2], b) * comb(counts[3], c)
               * 2**b * 3**c for a in range(9) for b in range(9-a)
               for c in [8-a-b] if a <= counts[1] and b <= counts[2]
               and c <= counts[3])


def main():
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    groups = defaultdict(list)
    for mask, column in columns.items():
        groups[column].append(mask)
    histogram = Counter(map(len, groups.values()))
    assert len(columns) == 16441 and len(groups) == 16381
    assert histogram == {1: 16323, 2: 56, 3: 2}
    control = json.loads(CONTROL.read_text())
    assert tuple(control["masks"][2*i] ^ control["masks"][2*i+1]
                 for i in range(2)) == SEEDS
    pairs = []
    for seed in SEEDS:
        pairs.append([(column, columns[mask ^ seed])
                      for mask, column in columns.items()
                      if (mask ^ seed) in columns and mask < (mask ^ seed)
                      and column != columns[mask ^ seed]])
    assert tuple(map(len, pairs)) == (4088, 4170)
    patterns = Counter()
    for c, d in pairs[0]:
        for e, f in pairs[1]:
            if c == e or c == f or d == e or d == f:
                continue
            removed = Counter((len(groups[c]), len(groups[d]),
                               len(groups[e]), len(groups[f])))
            patterns[tuple(removed[k] for k in (1, 2, 3))] += 1
    weighted = 0
    for pattern, amount in patterns.items():
        remaining = {k: histogram[k] - pattern[k-1] for k in (1, 2, 3)}
        weighted += amount * e8(remaining)
    # Two fixed unordered pairs: 2^2 pair orderings and 2^2 signs;
    # the other four pairs contribute 2^4 signs and ordered source masks.
    tuples = 4 * 4 * 16 * factorial(8) * weighted
    getcontext().prec = 55
    receipt = {
        "status": "PASS_EXACT_W15_TWO_FIXED_SEED_SOURCE_COUNT",
        "curve_id": "EC1N131Ckb1heb5f1998f20b", "candidate_id": None,
        "fixed_pair_seeds": list(SEEDS),
        "fixed_seed_policy": "first two pair XORs in archived constructed control",
        "factor_base_points_B": 197292, "folded_columns_K": 16381,
        "source_masks": len(columns),
        "unordered_distinct_column_pairs_by_seed": list(map(len, pairs)),
        "valid_first_two_pair_choices": sum(patterns.values()),
        "column_size_pattern_histogram": {"-".join(map(str, key)): amount
                                           for key, amount in sorted(patterns.items())},
        "distinct_column_signed_sixpair_tuples": str(tuples),
        "uniform_target_mean_before_nonzero_intermediate_filter":
            str(Decimal(tuples)/Decimal(ORDER)),
        "count_boundary": "two fixed first pair XOR seeds; twelve folded columns distinct; all source masks and pair sign choices exact; zero intermediates and group output not filtered",
        "sha256": {"script": sha(Path(__file__)), "support": sha(SUPPORT),
                   "constructed_control": sha(CONTROL)},
    }
    with (HERE / "support_count.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "valid_choices": receipt["valid_first_two_pair_choices"],
                      "mean": receipt["uniform_target_mean_before_nonzero_intermediate_filter"]}))


if __name__ == "__main__":
    main()
