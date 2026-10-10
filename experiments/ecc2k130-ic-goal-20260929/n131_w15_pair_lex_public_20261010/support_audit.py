#!/usr/bin/env python3
"""Independent incidence-count replay of the two fixed-seed W15 source."""

import hashlib
import json
from collections import Counter, defaultdict
from math import comb, factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
SEEDS = (12004, 9022)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coefficient(counts):
    result = 0
    for one in range(9):
        for two in range(9-one):
            three = 8-one-two
            if one <= counts[1] and two <= counts[2] and three <= counts[3]:
                result += (comb(counts[1], one) * comb(counts[2], two)
                           * comb(counts[3], three) * (2**two) * (3**three))
    return result


def main():
    columns = {}
    sizes = Counter()
    for row in SUPPORT.read_text().splitlines():
        mask, column = map(int, row.split())
        columns[mask] = column
        sizes[column] += 1
    hist = Counter(sizes.values())
    pairs = []
    for seed in SEEDS:
        pairs.append([(columns[a], columns[b])
                      for a in columns for b in [a ^ seed]
                      if b in columns and a < b and columns[a] != columns[b]])
    second_types = Counter()
    incident = defaultdict(set)
    for index, (c, d) in enumerate(pairs[1]):
        second_types[tuple(sorted((sizes[c], sizes[d])))] += 1
        incident[c].add(index)
        incident[d].add(index)
    weighted = 0
    valid = 0
    for c, d in pairs[0]:
        remaining_types = second_types.copy()
        for index in incident[c] | incident[d]:
            e, f = pairs[1][index]
            remaining_types[tuple(sorted((sizes[e], sizes[f])))] -= 1
        valid += sum(remaining_types.values())
        for (left, right), amount in remaining_types.items():
            if not amount:
                continue
            remaining = hist.copy()
            for size in (sizes[c], sizes[d], left, right):
                remaining[size] -= 1
            weighted += amount * coefficient(remaining)
    tuples = 256 * factorial(8) * weighted
    primary = json.loads((HERE / "support_count.json").read_text())
    assert valid == primary["valid_first_two_pair_choices"] == 17042784
    assert str(tuples) == primary["distinct_column_signed_sixpair_tuples"]
    receipt = {"status": "PASS_INDEPENDENT_TWO_FIXED_SEED_SOURCE_COUNT",
               "seeds": list(SEEDS), "valid_pair_choices": valid,
               "distinct_column_signed_sixpair_tuples": str(tuples),
               "sha256": {"script": sha(Path(__file__)),
                          "support": sha(SUPPORT),
                          "primary_count": sha(HERE / "support_count.json")}}
    with (HERE / "support_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"], "valid_choices": valid,
                      "source_count": str(tuples)}))


if __name__ == "__main__":
    main()
