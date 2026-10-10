#!/usr/bin/env python3
"""Exact seed-sum tuple counts for a six-pair W14 coupled-source proposal."""

from collections import Counter, defaultdict
from decimal import Decimal, getcontext
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
W14 = GOAL / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
N41 = GOAL / "n41_w5_pair_index_20261010/pair_index.json"
R131 = 680564733841876926932320129493409985129
R41 = 549756390943
getcontext().prec = 35


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fwht(vector):
    n = len(vector)
    width = 1
    while width < n:
        for base in range(0, n, width * 2):
            for offset in range(width):
                i, j = base + offset, base + offset + width
                x, y = vector[i], vector[j]
                vector[i], vector[j] = x + y, x - y
        width *= 2
    return vector


def w14_pair_states():
    rows = [tuple(map(int, line.split())) for line in W14.read_text().splitlines()]
    assert len(rows) == 8220 and len({mask for mask, _ in rows}) == 8220
    n = 1 << 14
    source = [0] * n
    by_column = defaultdict(list)
    for mask, column in rows:
        assert 1 <= mask < n
        source[mask] = 1
        by_column[column].append(mask)
    spectrum = fwht(source)
    correlation = fwht([value * value for value in spectrum])
    assert all(value % n == 0 for value in correlation)
    correlation = [value // n for value in correlation]
    same_column = Counter()
    for masks in by_column.values():
        for i, first in enumerate(masks):
            for second in masks[i + 1:]:
                same_column[first ^ second] += 1
    # c_s counts ordered masks. Divide by two, remove same-column pairs,
    # then retain all four sign choices for each unordered source-mask pair.
    counts = [0] + [2 * correlation[s] - 4 * same_column[s]
                    for s in range(1, n)]
    assert all(value >= 0 and value % 4 == 0 for value in counts)
    unordered = sum(counts) // 4
    expected_unordered = 8220 * 8219 // 2 - sum(same_column.values())
    assert unordered == expected_unordered
    return counts, {"support_masks": len(rows), "folded_columns": len(by_column),
                    "same_column_unordered_pairs": sum(same_column.values()),
                    "accepted_unordered_mask_pairs": unordered,
                    "accepted_signed_pair_states": sum(counts),
                    "distinct_nonzero_seed_sums": sum(bool(value) for value in counts[1:]),
                    "min_states_per_seed_sum": min(counts[1:]),
                    "max_states_per_seed_sum": max(counts[1:])}


def n41_pair_states():
    entries = json.loads(N41.read_text())["entries"]
    counts = [0] * 32
    for item in entries:
        counts[item["mask_a"] ^ item["mask_b"]] += len(item["raw_output_points"])
    assert sum(counts) == 528 and all(value % 4 == 0 for value in counts)
    return counts


def estimates(counts, order):
    m = sum(counts)
    a = sum(value * value for value in counts)
    # These are exact group-wide means if every tuple is mapped to its group
    # sum; cross-pair folded-column collisions are not yet removed.
    five = m**5
    five_one_equality = a * m**3
    six_two_equalities = a * a * m * m
    return {
        "signed_pair_states_per_rotation": m,
        "same_seed_two_pair_states": a,
        "one_equality_fraction": str(Decimal(a) / Decimal(m * m)),
        "five_pair_unconstrained_group_mean": str(Decimal(five) / Decimal(order)),
        "five_pair_one_equality_group_mean": str(Decimal(five_one_equality) / Decimal(order)),
        "six_pair_two_equalities_group_mean": str(Decimal(six_two_equalities) / Decimal(order)),
        "group_order": str(order),
        "six_pair_tuple_count": str(six_two_equalities),
    }


def main():
    n131, geometry = w14_pair_states()
    n41 = n41_pair_states()
    result = {
        "status": "PASS_EXACT_SEED_SUM_TUPLE_COUNTS",
        "method": "Walsh XOR autocorrelation with exact same-column exclusions",
        "policy": "six same-rotation unordered signed W14 pairs at rotations 0,13,26,39,52,65; seed sums of pairs 0 and 1 equal, and seed sums of pairs 2 and 3 equal; pairs 4 and 5 free",
        "cross_pair_folded_column_distinctness": "not imposed; means are upper bounds for row-valid tuples",
        "n131": {"geometry": geometry, **estimates(n131, R131),
                 "actual_factor_base_points_B": 98640,
                 "effective_folded_columns_K": 8160},
        "n41_control": estimates(n41, R41),
        "source_sha256": {"script": sha(Path(__file__)), "w14_support": sha(W14),
                          "n41_pair_index": sha(N41)},
    }
    with (HERE / "seed_sum_count.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "n131": result["n131"],
                      "n41_control": result["n41_control"]}))


if __name__ == "__main__":
    main()
