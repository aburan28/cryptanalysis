#!/usr/bin/env python3
"""Count distinct-column five-pair tuples when each raw pair lies in 4E."""

import hashlib
import json
from collections import defaultdict
from decimal import Decimal, getcontext
from math import comb, factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
PRIOR = HERE.parent / "n131_w15_unrestricted_fivepair_public_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symmetric(multiplicities, degree):
    values = [1] + [0]*degree
    for size in multiplicities:
        for k in range(degree, 0, -1):
            values[k] += size*values[k-1]
    return values


def main():
    census = json.loads((HERE / "census.json").read_text())
    bits = (HERE / "class_bits.bin").read_bytes()
    inp = json.loads((PRIOR / "input.json").read_text())
    old = json.loads((PRIOR / "support_count.json").read_text())
    assert census["sha256"]["class_bits"] == sha(HERE / "class_bits.bin")
    columns = defaultdict(list)
    for row in SUPPORT.read_text().splitlines():
        mask, column = map(int, row.split())
        columns[column].append(mask)
    excluded = set(inp["prefix_columns"])
    assert len(excluded) == 2 and len(columns) == 16381
    class_columns = {0: [], 1: []}
    for column, masks in columns.items():
        if column in excluded:
            continue
        classes = {bits[mask] for mask in masks}
        assert len(classes) == 1
        class_columns[classes.pop()].append(len(masks))
    e0 = symmetric(class_columns[0], 10)
    e1 = symmetric(class_columns[1], 10)
    unrestricted = 32*factorial(10)*sum(e0[j]*e1[10-j]
                                     for j in range(11))
    assert str(unrestricted) == old["distinct_column_signed_unordered_fivepair_tuples"]
    constrained = 32*sum(comb(5, pairs_one)
                         *factorial(2*pairs_one)*factorial(10-2*pairs_one)
                         *e1[2*pairs_one]*e0[10-2*pairs_one]
                         for pairs_one in range(6))
    order = int(json.loads((HERE / "protocol.json").read_text())["subgroup_order"])
    getcontext().prec = 50
    result = {"status": "PASS_EXACT_FIVEPAIR_SUBGROUP_CLASS_COUNT",
              "count_boundary": "ten free masks in five labelled pairs, each pair's two raw atoms have equal 4E class; all twelve folded columns distinct",
              "prefix_masks": inp["prefix_masks"],
              "prefix_class_xor": bits[inp["prefix_masks"][0]] ^ bits[inp["prefix_masks"][1]],
              "remaining_columns_by_class": {str(k): len(v) for k, v in class_columns.items()},
              "unrestricted_tuple_count": str(unrestricted),
              "subgroup_pair_tuple_count": str(constrained),
              "subgroup_pair_fraction": str(Decimal(constrained)/Decimal(unrestricted)),
              "uniform_subgroup_target_mean_before_nonzero_filter": str(Decimal(constrained)/Decimal(order)),
              "source_sha256": {"script": sha(Path(__file__)),
                                "support": sha(SUPPORT),
                                "class_bits": sha(HERE / "class_bits.bin"),
                                "census": sha(HERE / "census.json"),
                                "prior_input": sha(PRIOR / "input.json"),
                                "prior_count": sha(PRIOR / "support_count.json")}}
    with (HERE / "count.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "mean": result["uniform_subgroup_target_mean_before_nonzero_filter"],
                      "fraction": result["subgroup_pair_fraction"]}))


if __name__ == "__main__":
    main()
