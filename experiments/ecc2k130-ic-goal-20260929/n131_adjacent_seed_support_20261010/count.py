#!/usr/bin/env python3
"""Exact six-pair adjacent-window support by direct enumeration and XOR FWHT."""
import collections
import hashlib
import json
import resource
import sys
import time
from decimal import Decimal, getcontext
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ORDER = 680564733841876926932320129493409985129
getcontext().prec = 45


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fwht(values):
    step = 1
    while step < len(values):
        view = values.reshape(-1, 2 * step)
        left = view[:, :step].copy()
        right = view[:, step:].copy()
        view[:, :step] = left + right
        view[:, step:] = left - right
        step *= 2
    return values


def geometry(d, support):
    rows = [tuple(map(int, line.split())) for line in support.read_text().splitlines()]
    assert len(rows) == (8220 if d == 14 else 16441)
    powers = sorted(set(range(1, d + 1)) | set(range(2, 2*d + 1, 2)))
    position = {degree: index for index, degree in enumerate(powers)}

    def code(mask, shift):
        value = 0
        for degree in range(1, d + 1):
            if mask >> (degree - 1) & 1:
                value ^= 1 << position[degree << shift]
        return value

    left = np.array([code(mask, 0) for mask, _ in rows], dtype=np.int64)
    right = np.array([code(mask, 1) for mask, _ in rows], dtype=np.int64)
    columns = np.array([column for _, column in rows], dtype=np.int64)
    return rows, left, right, columns, len(powers)


def direct(left, right, columns, size):
    result = np.zeros(size, dtype=np.uint32)
    for start in range(0, len(left), 128):
        seed = left[start:start+128, None] ^ right[None, :]
        usable = columns[start:start+128, None] != columns[None, :]
        result += np.bincount(seed[usable], minlength=size).astype(np.uint32)
    return result


def convolution(left, right, columns, size):
    first = np.zeros(size, dtype=np.int64)
    second = np.zeros(size, dtype=np.int64)
    first[left] = 1
    second[right] = 1
    values = fwht(fwht(first) * fwht(second))
    assert np.all(values % size == 0)
    values //= size
    by_column = collections.defaultdict(list)
    for a, b, column in zip(left, right, columns):
        by_column[int(column)].append((int(a), int(b)))
    for points in by_column.values():
        for a, _ in points:
            for _, b in points:
                values[a ^ b] -= 1
    assert int(values.min()) >= 0
    return values, by_column


def count_width(d, support, baseline):
    started = time.monotonic_ns()
    rows, left, right, columns, rank = geometry(d, support)
    size = 1 << rank
    direct_counts = direct(left, right, columns, size)
    fwht_counts, by_column = convolution(left, right, columns, size)
    assert np.array_equal(direct_counts, fwht_counts)
    counts = direct_counts.astype(np.int64)
    accepted_pairs = int(counts.sum())
    same_column_excluded = sum(len(points)**2 for points in by_column.values())
    assert accepted_pairs == len(rows)**2 - same_column_excluded
    signed_pair_states = 4 * accepted_pairs
    same_seed_block_states = 16 * int(np.dot(counts, counts))
    tuples = signed_pair_states**2 * same_seed_block_states**2
    suffix = signed_pair_states * same_seed_block_states**2
    minimum_prefixes = (ORDER + 2*suffix - 1) // (2*suffix)
    reference_tuples = int(baseline["six_pair_tuple_count"])
    histogram = np.bincount(direct_counts).tolist()
    return {"source_degree": d, "seed_space_rank": rank,
            "source_masks": len(rows), "folded_columns_K": len(by_column),
            "accepted_ordered_mask_pairs": accepted_pairs,
            "same_column_excluded_ordered_pairs": same_column_excluded,
            "signed_pair_states_per_rotation": signed_pair_states,
            "same_seed_two_pair_states": same_seed_block_states,
            "seed_bucket_pair_count_histogram": histogram,
            "nonempty_seed_buckets": size - histogram[0],
            "maximum_mask_pairs_per_seed": len(histogram)-1,
            "seed_count_sha256_u16le": hashlib.sha256(
                direct_counts.astype("<u2").tobytes()).hexdigest(),
            "six_pair_tuple_count": str(tuples), "group_order": str(ORDER),
            "group_wide_mean_before_cross_pair_columns": str(Decimal(tuples)/Decimal(ORDER)),
            "same_rotation_group_wide_mean": str(Decimal(reference_tuples)/Decimal(ORDER)),
            "adjacent_to_same_rotation_tuple_ratio": str(
                Decimal(tuples)/Decimal(reference_tuples)),
            "minimum_one_free_pair_prefixes_for_half_union_ceiling": minimum_prefixes,
            "necessary_average_microseconds_per_prefix_in_600s": str(
                Decimal(600_000_000)/Decimal(minimum_prefixes)),
            "source_sha256": sha(support),
            "count_wall_ns": time.monotonic_ns()-started}


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_COUNT"
    paths = {"count": HERE / "count.py",
             "w14_support": ROOT / "n131_w14_ten_source_gate_20261009/support_w14.tsv",
             "w15_support": ROOT / "n131_w15_coupled_sixpair_20261010/support_w15.tsv",
             "w14_baseline": ROOT / "n41_upper_xor_projection_20261010/seed_sum_count.json",
             "w15_baseline": ROOT / "n131_w15_coupled_sixpair_20261010/seed_sum_count.json"}
    assert protocol["source_sha256"] == {name: sha(path) for name, path in paths.items()}
    assert not (HERE / "result.json").exists()
    started = time.monotonic_ns()
    w14_baseline = json.loads(paths["w14_baseline"].read_text())["n131"]
    w15_baseline = json.loads(paths["w15_baseline"].read_text())
    w14 = count_width(14, paths["w14_support"], w14_baseline)
    w15 = count_width(15, paths["w15_support"], w15_baseline)
    elapsed = time.monotonic_ns()-started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    status = "PASS_EXACT_ADJACENT_SEED_SUPPORT"
    if elapsed > protocol["wall_cap_seconds"] * 10**9:
        status = "CENSORED_TIME"
    if peak > protocol["rss_cap_bytes"]:
        status = "CENSORED_MEMORY"
    result = {"status": status, "candidate_id": None,
              "curve_id": protocol["curve_id"], "target_count": 0,
              "policy": protocol["policy"], "w14": w14, "w15": w15,
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": protocol["source_sha256"],
              "wall_ns": elapsed, "peak_rss_bytes": peak}
    (HERE / "result.json").write_text(json.dumps(result, sort_keys=True,
                                                 indent=2) + "\n")
    print(json.dumps({"status": status, "w14_mean": w14[
        "group_wide_mean_before_cross_pair_columns"], "w15_mean": w15[
        "group_wide_mean_before_cross_pair_columns"],
        "wall_ns": elapsed, "peak_rss_bytes": peak}))


if __name__ == "__main__":
    main()
