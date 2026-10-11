"""Exact W20 fixed-seed pair counts and selected seven-window factor base."""

import collections
import hashlib
import json
import resource
import time
from fractions import Fraction
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
R = 680564733841876926932320129493409985129
WIDTH = 20
ROTATIONS = [0, 18, 36, 54, 72, 90, 108]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fwht(values):
    step = 1
    while step < len(values):
        view = values.reshape(-1, 2*step)
        left = view[:, :step].copy()
        right = view[:, step:].copy()
        view[:, :step] = left + right
        view[:, step:] = left - right
        step *= 2
    return values


def main():
    protocol_path = HERE / "count_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "table": HERE / "support_w20.tsv",
             "export_receipt": HERE / "export_receipt.json",
             "export_run": HERE / "export_run_result.json",
             "numpy_version": HERE / "numpy_version.txt"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    assert protocol["rss_cap_bytes"] == 4294967296
    export = json.loads(paths["export_receipt"].read_text())
    assert export["status"] == "COMPLETE_W20_GEOMETRY"
    assert export["reciprocal_frobenius_hits"] == 0
    assert export["seven_window_usable_points_B"] == (
        2 * len(ROTATIONS) * export["rational_masks"])
    started = time.monotonic_ns()

    rows = [tuple(map(int, line.split())) for line in paths["table"].read_text().splitlines()]
    assert len(rows) == export["rational_masks"]
    source = {}
    by_column = collections.defaultdict(list)
    indicator = np.zeros(1 << WIDTH, dtype=np.int64)
    for mask, column, shift in rows:
        assert 0 < mask < len(indicator) and mask not in source
        assert 0 <= shift < 131 and 0 < column < len(indicator)
        source[mask] = (column, shift)
        by_column[column].append(mask)
        indicator[mask] = 1
    assert len(by_column) == export["folded_columns_K"]
    loaded = time.monotonic_ns()

    spectrum = fwht(indicator)
    correlation = fwht(spectrum * spectrum)
    assert np.all(correlation % len(correlation) == 0)
    correlation //= len(correlation)
    assert np.all(correlation[1:] % 2 == 0)
    pair_counts = correlation // 2
    pair_counts[0] = 0
    excluded_same_column_pairs = np.zeros(1 << WIDTH, dtype=np.int64)
    for masks in by_column.values():
        for index, first in enumerate(masks):
            for second in masks[index+1:]:
                excluded_same_column_pairs[first ^ second] += 1
    pair_counts -= excluded_same_column_pairs
    assert pair_counts[0] == 0 and int(pair_counts.min()) >= 0
    seed = int(np.argmax(pair_counts[1:])) + 1
    maximum = int(pair_counts[seed])
    assert maximum > 0
    transformed = time.monotonic_ns()

    edges = [(mask, mask ^ seed) for mask, (column, shift) in source.items()
             if mask < (mask ^ seed) and mask ^ seed in source and
             column != source[mask ^ seed][0]]
    assert len(edges) == maximum
    selected_masks = {mask for edge in edges for mask in edge}
    union_by_column = {}
    for mask in selected_masks:
        column, shift = source[mask]
        bits = union_by_column.get(column, 0)
        for rotation in ROTATIONS:
            bits |= 1 << ((shift + rotation) % 131)
        union_by_column[column] = bits
    selected_distinct_w = sum(bits.bit_count() for bits in union_by_column.values())
    assert selected_distinct_w == len(ROTATIONS) * len(selected_masks)
    selected_B = 2 * selected_distinct_w
    signed_pair_states = 4 * maximum
    labeled_tuples = signed_pair_states ** len(ROTATIONS)
    mean = Fraction(labeled_tuples, R)
    counted = time.monotonic_ns()
    result = {"status": "PASS_EXACT_W20_SEVEN_PAIR_SOURCE_SUPPORT",
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "candidate_id": None, "target_count": 0,
              "source_dimension": WIDTH,
              "searched_nonzero_seed_count": (1 << WIDTH) - 1,
              "selected_seed_mask": seed,
              "selected_valid_unordered_pairs_per_slot": maximum,
              "selected_same_column_pair_exclusions": int(excluded_same_column_pairs[seed]),
              "selected_rational_masks_per_window": len(selected_masks),
              "selected_folded_columns_K": len(union_by_column),
              "selected_usable_points_B_seven_rotations": selected_B,
              "slot_rotations": ROTATIONS,
              "signed_pair_states_per_slot": signed_pair_states,
              "labeled_seven_pair_tuple_ceiling": str(labeled_tuples),
              "uniform_target_labeled_mean_upper_ceiling": str(mean),
              "uniform_target_labeled_mean_upper_ceiling_decimal": format(float(mean), ".9g"),
              "cross_slot_column_exclusions": "omitted from tuple ceiling",
              "phase_ns": {"load_source": loaded-started,
                           "all_seed_fwht_and_same_column_correction": transformed-loaded,
                           "selected_source_and_base": counted-transformed},
              "wall_ns": counted-started,
              "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "count_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "seed": seed,
                      "valid_pairs": maximum,
                      "selected_B": selected_B,
                      "selected_K": len(union_by_column),
                      "mean_ceiling": result["uniform_target_labeled_mean_upper_ceiling_decimal"]}))


if __name__ == "__main__":
    main()
