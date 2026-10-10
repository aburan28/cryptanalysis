#!/usr/bin/env python3
"""Count all signed five-pair tuples with twelve distinct folded columns."""

import hashlib
import json
from collections import Counter
from decimal import Decimal, getcontext
from math import factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_coupled_sixpair_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symmetric(weights, degree):
    values = [1] + [0]*degree
    for weight in weights:
        for k in range(degree, 0, -1):
            values[k] += weight*values[k-1]
    return values[degree]


def main():
    inp = json.loads((HERE / "input.json").read_text())
    previous = json.loads((BASE / "seed_sum_count.json").read_text())
    support = BASE / "support_w15.tsv"
    multiplicities = Counter(int(line.split()[1]) for line in support.read_text().splitlines())
    assert len(multiplicities) == 16381 and sum(multiplicities.values()) == 16441
    n = 4*symmetric(multiplicities.values(), 2)
    assert n == previous["accepted_signed_pair_states_per_rotation"] == 540579832
    excluded = {column: multiplicities.pop(column) for column in inp["prefix_columns"]}
    assert len(multiplicities) == 16379 and sum(multiplicities.values()) == 16436
    e10 = symmetric(multiplicities.values(), 10)
    # Ten labelled slots, two sign choices per leaf, and quotient by swapping
    # the two different columns inside each of five pair slots.
    tuples = (2**10 // 2**5)*factorial(10)*e10
    r = int(previous["group_order"])
    getcontext().prec = 50
    receipt = {
        "status": "PASS_EXACT_DISTINCT_COLUMN_FIVEPAIR_TUPLE_COUNT",
        "candidate_id": None,
        "curve_id": inp["curve_id"],
        "prefix_masks": inp["prefix_masks"],
        "prefix_columns": inp["prefix_columns"],
        "excluded_column_multiplicities": excluded,
        "remaining_column_count": len(multiplicities),
        "remaining_rational_mask_count": sum(multiplicities.values()),
        "signed_unordered_pair_states_before_prefix_exclusion": n,
        "elementary_symmetric_e10": str(e10),
        "distinct_column_signed_unordered_fivepair_tuples": str(tuples),
        "group_order": str(r),
        "uniform_target_mean_before_nonzero_intermediate_filter": str(Decimal(tuples)/r),
        "pre_cross_pair_upper_mean": str(Decimal(n**5)/r),
        "distinct_column_fraction_of_upper_count": str(Decimal(tuples)/Decimal(n**5)),
        "count_boundary": "all twelve folded columns distinct, source support and signs exact; intermediate nonzero and group output not filtered",
        "source_sha256": {"script": sha(Path(__file__)),
                          "input": sha(HERE / "input.json"),
                          "support": sha(support),
                          "pair_count": sha(BASE / "seed_sum_count.json")},
    }
    with (HERE / "support_count.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "group_mean": receipt["uniform_target_mean_before_nonzero_intermediate_filter"],
                      "fraction": receipt["distinct_column_fraction_of_upper_count"]}))


if __name__ == "__main__":
    main()
