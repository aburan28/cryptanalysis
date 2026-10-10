#!/usr/bin/env python3
"""Exact twelve-column-distinct source count for six free W15 pairs."""

import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, getcontext
from math import factorial
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"
ORDER = 680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    columns = defaultdict(set)
    for row in SUPPORT.read_text().splitlines():
        mask, column = map(int, row.split())
        columns[column].add(mask)
    assert len(columns) == 16381
    assert sum(map(len, columns.values())) == 16441
    multiplicities = Counter(map(len, columns.values()))
    assert multiplicities == {1: 16323, 2: 56, 3: 2}
    e = [1] + [0]*12
    for masks in columns.values():
        size = len(masks)
        for degree in range(12, 0, -1):
            e[degree] += size*e[degree-1]
    tuples = 2**6*factorial(12)*e[12]
    raw_pair_states = 4*(16441*(16441-1)//2
                         -sum(size*(size-1)//2 for size in multiplicities.elements()))
    assert raw_pair_states == 540579832
    getcontext().prec = 50
    receipt = {"status": "PASS_EXACT_W15_SIX_FREE_PAIR_SOURCE_COUNT",
               "curve_id": "EC1N131Ckb1heb5f1998f20b",
               "candidate_id": None,
               "factor_base_points_B": 197292,
               "folded_columns_K": len(columns),
               "source_masks": 16441,
               "column_multiplicities": {str(k): v for k, v in sorted(multiplicities.items())},
               "signed_unordered_pair_states": raw_pair_states,
               "elementary_symmetric_e12": str(e[12]),
               "distinct_column_signed_sixpair_tuples": str(tuples),
               "uniform_target_mean_before_nonzero_intermediate_filter":
                   str(Decimal(tuples)/Decimal(ORDER)),
               "count_boundary": "twelve folded columns distinct; source masks and per-pair sign choices exact; zero intermediates and group output not filtered",
               "sha256": {"script": sha(Path(__file__)), "support": sha(SUPPORT)}}
    with (HERE / "support_count.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "mean": receipt["uniform_target_mean_before_nonzero_intermediate_filter"]}))


if __name__ == "__main__":
    main()
