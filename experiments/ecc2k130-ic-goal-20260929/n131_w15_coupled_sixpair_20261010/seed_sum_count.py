#!/usr/bin/env python3
"""Exact W15 six-pair tuple count before cross-pair column exclusions."""

from collections import Counter, defaultdict
from decimal import Decimal, getcontext
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "n41_upper_xor_projection_20261010/seed_sum_count.json"
R = 680564733841876926932320129493409985129
getcontext().prec = 40


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fwht(vector):
    width = 1
    while width < len(vector):
        for base in range(0, len(vector), 2 * width):
            for offset in range(width):
                left, right = base + offset, base + offset + width
                a, b = vector[left], vector[right]
                vector[left], vector[right] = a + b, a - b
        width *= 2
    return vector


def count():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W15_N131_CONTROL_AND_PUBLIC_QUERY"
    assert protocol["source_sha256"]["w15_support"] == sha(HERE / "support_w15.tsv")
    rows = [tuple(map(int, line.split())) for line in
            (HERE / "support_w15.tsv").read_text().splitlines()]
    assert len(rows) == 16441
    n = 1 << 15
    source = [0] * n
    by_column = defaultdict(list)
    for mask, column in rows:
        assert 1 <= mask < n and source[mask] == 0
        source[mask] = 1
        by_column[column].append(mask)
    spectrum = fwht(source)
    correlation = fwht([value * value for value in spectrum])
    assert all(value % n == 0 for value in correlation)
    correlation = [value // n for value in correlation]
    same_column = Counter()
    for masks in by_column.values():
        for index, first in enumerate(masks):
            for second in masks[index + 1:]:
                same_column[first ^ second] += 1
    counts = [0] + [2 * correlation[s] - 4 * same_column[s]
                    for s in range(1, n)]
    assert all(value >= 0 and value % 4 == 0 for value in counts)
    signed = sum(counts)
    unordered = signed // 4
    assert unordered == 16441 * 16440 // 2 - sum(same_column.values())
    same_seed = sum(value * value for value in counts)
    tuples = signed * signed * same_seed * same_seed
    baseline = json.loads(BASELINE.read_text())["n131"]
    baseline_tuples = int(baseline["six_pair_tuple_count"])
    result = {
        "status": "PASS_EXACT_W15_SIX_PAIR_TUPLE_COUNT",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "policy": "six same-rotation signed W15 pairs; seed sums equal within pairs 2-3 and 4-5",
        "factor_base_B": protocol["actual_projected_factor_base_B"],
        "folded_columns_K": protocol["folded_columns_K"],
        "rational_masks": len(rows),
        "accepted_unordered_mask_pairs": unordered,
        "accepted_signed_pair_states_per_rotation": signed,
        "same_seed_two_pair_states": same_seed,
        "min_signed_pair_states_per_nonzero_seed": min(counts[1:]),
        "max_signed_pair_states_per_nonzero_seed": max(counts[1:]),
        "six_pair_tuple_count": str(tuples),
        "group_order": str(R),
        "group_wide_mean_before_cross_pair_column_filter": str(Decimal(tuples) / Decimal(R)),
        "w14_group_wide_mean_same_boundary": baseline["six_pair_two_equalities_group_mean"],
        "tuple_count_ratio_to_w14": str(Decimal(tuples) / Decimal(baseline_tuples)),
        "cross_pair_column_distinctness": "not imposed; the mean is an upper bound for row-valid tuples",
        "source_sha256": {
            "script": sha(__file__),
            "protocol": sha(HERE / "protocol.json"),
            "support": sha(HERE / "support_w15.tsv"),
            "w14_baseline": sha(BASELINE),
        },
    }
    with (HERE / "seed_sum_count.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "mean": result["group_wide_mean_before_cross_pair_column_filter"],
                      "ratio": result["tuple_count_ratio_to_w14"]}))


if __name__ == "__main__":
    count()
