"""Exact GF(2) rank of Boolean quadratic features of same-seed quad x outputs."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


FEATURES = 821  # 1, 40 x bits 1..40, and their 780 pair products.


def features(x):
    active = [i for i in range(40) if (x >> (i + 1)) & 1]
    row = 1
    for i in active:
        row |= 1 << (i + 1)
    feature = 41
    active_set = set(active)
    for i in range(40):
        for j in range(i + 1, 40):
            if i in active_set and j in active_set:
                row |= 1 << feature
            feature += 1
    assert feature == FEATURES
    return row


def rank(rows):
    pivots = {}
    for row in rows:
        while row:
            pivot = row.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = row
                break
            row ^= pivots[pivot]
    return len(pivots)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tsv", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    grouped = defaultdict(set)
    witness_rows = 0
    by_seed_witnesses = defaultdict(int)
    with args.tsv.open(newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        assert reader.fieldnames == ["seed", "x", "y", "first_pair", "second_pair", "columns"]
        for row in reader:
            seed, x = int(row["seed"]), int(row["x"])
            assert 1 <= seed < 64 and 0 <= x < 1 << 41
            grouped[seed].add(x)
            by_seed_witnesses[seed] += 1
            witness_rows += 1
    assert len(grouped) == 63
    bins = []
    for seed in range(1, 64):
        xs = sorted(grouped[seed])
        r = rank(features(x) for x in xs)
        baseline = min(len(xs), FEATURES)
        bins.append({"seed": seed, "witness_rows": by_seed_witnesses[seed],
                     "distinct_x": len(xs), "quadratic_rank": r,
                     "rank_defect_beyond_cardinality": baseline - r,
                     "quadratic_kernel_dimension": FEATURES - r})
    result = {
        "status": "EXACT_QUADRATIC_SAME_SEED_QUAD_RANK",
        "input_sha256": hashlib.sha256(args.tsv.read_bytes()).hexdigest(),
        "feature_order": "constant; field x bits 1..40; lexicographic products of those bits",
        "feature_count": FEATURES,
        "witness_rows": witness_rows,
        "distinct_x_across_bins": sum(b["distinct_x"] for b in bins),
        "bins_with_extra_rank_defect": sum(b["rank_defect_beyond_cardinality"] != 0 for b in bins),
        "max_extra_rank_defect": max(b["rank_defect_beyond_cardinality"] for b in bins),
        "bins": bins,
    }
    with args.output.open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print({k: v for k, v in result.items() if k != "bins"})


if __name__ == "__main__":
    main()
