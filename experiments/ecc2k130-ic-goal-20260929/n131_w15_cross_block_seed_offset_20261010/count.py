#!/usr/bin/env python3
"""Exact Walsh census for cross-block W15 seed-offset constraints."""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w15_coupled_sixpair_20261010/support_w15.tsv"
REFERENCE = BASE / "n131_w15_coupled_sixpair_20261010/seed_sum_count.json"
WIDTH = 15
SIZE = 1 << WIDTH


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def walsh(values):
    values = values[:]
    step = 1
    while step < len(values):
        for start in range(0, len(values), 2*step):
            for i in range(start, start+step):
                a, b = values[i], values[i+step]
                values[i], values[i+step] = a+b, a-b
        step *= 2
    return values


def xor_autocorrelation(values):
    spectrum = walsh(values)
    folded = walsh([v*v for v in spectrum])
    assert all(v % len(values) == 0 for v in folded)
    return [v//len(values) for v in folded]


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W15_CROSS_BLOCK_COUNT"
    assert protocol["source_sha256"] == {"count": sha(__file__),
             "support": sha(SUPPORT), "reference": sha(REFERENCE)}
    assert not (HERE / "result.json").exists()
    support = {}
    by_column = {}
    for line in SUPPORT.read_text().splitlines():
        mask, column = map(int, line.split())
        assert 0 < mask < SIZE and mask not in support
        support[mask] = column
        by_column.setdefault(column, []).append(mask)
    assert len(support) == 16441 and len(by_column) == 16381
    indicators = [int(mask in support) for mask in range(SIZE)]
    ordered = xor_autocorrelation(indicators)
    aliases = [0]*SIZE
    for masks in by_column.values():
        for i, a in enumerate(masks):
            for b in masks[i+1:]:
                aliases[a^b] += 1
    signed = [0]*SIZE
    for s in range(1, SIZE):
        assert ordered[s] % 2 == 0
        signed[s] = 2*ordered[s]-4*aliases[s]
        assert signed[s] > 0 and signed[s] % 4 == 0
    n = sum(signed)
    m = sum(v*v for v in signed)
    reference = json.loads(REFERENCE.read_text())
    assert n == reference["accepted_signed_pair_states_per_rotation"]
    assert m == reference["same_seed_two_pair_states"]
    assert min(signed[1:]) == reference["min_signed_pair_states_per_nonzero_seed"]
    assert max(signed[1:]) == reference["max_signed_pair_states_per_nonzero_seed"]
    cross = xor_autocorrelation([v*v for v in signed])
    assert sum(cross) == m*m
    offsets = protocol["offsets"]
    assert offsets == list(range(8))
    selected = sum(cross[delta] for delta in offsets)
    r = int(protocol["subgroup_order"])
    assert r == int(reference["group_order"])
    ratio = Fraction(selected, m*m)
    mean = Fraction(n*n*selected, r)
    suffix = n*selected
    q50 = (r+2*suffix-1)//(2*suffix)
    with (HERE / "signed_seed_counts.tsv").open("x") as stream:
        for s in range(1, SIZE):
            stream.write(f"{s} {signed[s]}\n")
    with (HERE / "offset_support.tsv").open("x") as stream:
        for delta, count in enumerate(cross):
            stream.write(f"{delta} {count}\n")
    result = {"status": "PASS_EXACT_CROSS_BLOCK_OFFSET_SUPPORT",
              "candidate_id": None, "curve_id": protocol["curve_id"],
              "source_sha256": protocol["source_sha256"],
              "protocol_sha256": sha(protocol_path),
              "signed_seed_counts_sha256": sha(HERE / "signed_seed_counts.tsv"),
              "offset_support_sha256": sha(HERE / "offset_support.tsv"),
              "rational_masks": len(support), "folded_columns_K": len(by_column),
              "signed_pair_states_N": n, "same_seed_block_states_M": m,
              "offsets": offsets,
              "per_offset_two_block_states": {str(delta): str(cross[delta])
                                               for delta in offsets},
              "selected_two_block_states": str(selected),
              "selected_fraction_of_unrestricted_two_blocks":
                  {"numerator": str(ratio.numerator),
                   "denominator": str(ratio.denominator)},
              "six_pair_tuple_upper": str(n*n*selected),
              "uniform_group_mean_upper": {"numerator": str(mean.numerator),
                                           "denominator": str(mean.denominator)},
              "one_free_pair_suffix_upper": str(suffix),
              "q50_target_independent_one_free_prefix_union_bound": str(q50),
              "necessary_ms_per_prefix_in_600s":
                  {"numerator": 600000, "denominator": str(q50)},
              "offset_support_min": str(min(cross)),
              "offset_support_max": str(max(cross)),
              "offset_support_argmax": max(range(SIZE), key=cross.__getitem__)}
    with (HERE / "result.json").open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "selected_mean_decimal": str(float(mean)),
                      "q50": q50, "fraction": float(ratio)}))


if __name__ == "__main__":
    main()
