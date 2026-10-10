#!/usr/bin/env python3
"""Replay fixed-seed pair counts and suffix coefficients independently."""

import hashlib
import json
from collections import Counter, defaultdict
from math import factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
SEED = 12004


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def suffix_coefficient(sizes):
    coefficients = [1] + [0]*10
    for size in sizes:
        for degree in range(10, 0, -1):
            coefficients[degree] += size*coefficients[degree-1]
    return coefficients[10]


def main():
    expected = json.loads((HERE / "support_count.json").read_text())
    mask_column = {}
    groups = defaultdict(set)
    for line in SUPPORT.read_text().splitlines():
        mask, column = map(int, line.split())
        mask_column[mask] = column
        groups[column].add(mask)
    pairs = []
    for mask in sorted(mask_column):
        partner = mask ^ SEED
        if mask < partner and partner in mask_column:
            if mask_column[mask] != mask_column[partner]:
                pairs.append((mask, partner))
    assert len(pairs) == expected["fixed_seed_unordered_distinct_column_mask_pairs"]
    signatures = Counter(tuple(sorted((len(groups[mask_column[a]]),
                                       len(groups[mask_column[b]]))))
                         for a, b in pairs)
    assert {f"{a}-{b}": amount for (a,b), amount in sorted(signatures.items())} == \
        expected["first_pair_column_size_types"]
    cached = {}
    total = 0
    for a, b in pairs:
        sig = tuple(sorted((len(groups[mask_column[a]]),
                            len(groups[mask_column[b]]))))
        if sig not in cached:
            sizes = [len(masks) for column, masks in groups.items()
                     if column not in (mask_column[a], mask_column[b])]
            cached[sig] = suffix_coefficient(sizes)
        total += 128*factorial(10)*cached[sig]
    assert str(total) == expected["distinct_column_signed_sixpair_tuples"]
    receipt = {"status": "PASS_INDEPENDENT_FIXEDSEED_SIXPAIR_COUNT",
               "seed": SEED,
               "unordered_mask_pairs": len(pairs),
               "suffix_coefficients": {f"{a}-{b}": str(value)
                                       for (a,b), value in sorted(cached.items())},
               "tuple_count": str(total),
               "sha256": {"script": sha(Path(__file__)),
                          "primary_count": sha(HERE / "support_count.json"),
                          "support": sha(SUPPORT)}}
    with (HERE / "support_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "tuple_count": str(total)}))


if __name__ == "__main__":
    main()
