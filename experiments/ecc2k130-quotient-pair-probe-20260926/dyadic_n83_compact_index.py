#!/usr/bin/env python3
"""Packed n83 quotient index with exact-key controls against the dict index."""

import argparse
import hashlib
import json
import platform
import random
import resource
import statistics
import time
from pathlib import Path

import numpy as np

import curves
import field
from batch_x_only import query_prefix_batch
from compare_batch_x_only import CountingField
from dyadic_base_geometry import enumerate_points
from dyadic_n53_relation_probe import build_cross_seed_index
from perf_probe import sha
from quotient_pair_probe import CountedCurve, transform
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
WINDOW = 32
DEGREE = 83
PREFIX_LOOKUPS = 166 * 64
PROPOSAL_ID = "Q1023"
ROW_DTYPE = np.dtype([("hi", "<u8"), ("lo", "<u8"), ("witness", "<u8")])
LOW_MASK = (1 << 64) - 1


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def peak_rss_bytes():
    result = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return result if platform.system() == "Darwin" else result * 1024


def encode_key(key):
    encoded = key + 1  # identity -1 maps to zero
    assert 0 <= encoded <= (1 << DEGREE)
    return encoded >> 64, encoded & LOW_MASK


class PackedIndex:
    def __init__(self, rows, left_reps, right_base, curve, canonicalize):
        self.rows = rows
        self.left_reps = left_reps
        self.right_base = right_base
        self.curve = curve
        self.canonicalize = canonicalize

    def __len__(self):
        return len(self.rows)

    def decode(self, row):
        packed = int(row["witness"])
        shift = packed % DEGREE
        packed //= DEGREE
        right_index = packed % len(self.right_base)
        left_index = packed // len(self.right_base)
        pair = (transform(self.curve, self.left_reps[left_index], shift, 1),
                transform(self.curve, self.right_base[right_index], shift, 1))
        representative = self.curve.add(*pair)
        return representative, pair

    def values(self):
        for row in self.rows:
            yield self.decode(row)

    def get(self, key):
        hi, lo = encode_key(key)
        left, right = 0, len(self.rows)
        while left < right:
            middle = (left + right) // 2
            row = self.rows[middle]
            current = (int(row["hi"]), int(row["lo"]))
            if current < (hi, lo):
                left = middle + 1
            else:
                right = middle
        if left == len(self.rows):
            return None
        row = self.rows[left]
        if (int(row["hi"]), int(row["lo"])) != (hi, lo):
            return None
        return self.decode(row)

    def keys(self):
        for row in self.rows:
            encoded = (int(row["hi"]) << 64) | int(row["lo"])
            yield encoded - 1


def build_packed(curve, left_reps, right_base, canonicalize):
    generators = len(left_reps) * len(right_base)
    rows = np.empty(generators, dtype=ROW_DTYPE)
    counted = CountedCurve(curve)
    started = time.perf_counter()
    at = 0
    for left_index, left in enumerate(left_reps):
        for right_index, right in enumerate(right_base):
            total = counted.add(left, right)
            key, shift = canonicalize.key_and_shift(counted, total)
            hi, lo = encode_key(key)
            packed = (left_index * len(right_base) + right_index) * DEGREE + shift
            rows[at] = (hi, lo, packed)
            at += 1
    assert at == generators
    rows.sort(order=["hi", "lo"], kind="quicksort")
    keep = np.empty(generators, dtype=np.bool_)
    keep[0] = True
    keep[1:] = (rows["hi"][1:] != rows["hi"][:-1]) | (
        rows["lo"][1:] != rows["lo"][:-1])
    unique = rows[keep].copy()
    elapsed = time.perf_counter() - started
    index = PackedIndex(unique, left_reps, right_base, curve, canonicalize)
    return index, {
        "pair_generators": generators,
        "quotient_keys": len(unique),
        "build_seconds": elapsed,
        "point_operations": counted.counts,
        "row_bytes": ROW_DTYPE.itemsize,
        "raw_array_bytes": rows.nbytes,
        "retained_array_bytes": unique.nbytes,
        "retained_array_sha256": hashlib.sha256(unique.tobytes()).hexdigest(),
        "key_sha256": hashlib.sha256(frozen(list(index.keys()))).hexdigest(),
        "peak_rss_bytes": peak_rss_bytes(),
    }


def measured_prefix(onb, raw_index, target, canonicalize):
    counted_field = CountingField(onb)
    curve = curves.Curve(counted_field)
    index = PackedIndex(raw_index.rows, raw_index.left_reps,
                        raw_index.right_base, curve, canonicalize)
    result = query_prefix_batch(curve, index, target, DEGREE, canonicalize,
                                PREFIX_LOOKUPS)
    result["field_api_operations"] = dict(counted_field.counts)
    result["field_api_operation_boundary"] = (
        "includes packed witness reconstruction for each scanned index row "
        "and target complements; does not decompose internal bit work")
    return result


def main(mode):
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    baseline_path = HERE / "runs" / "n83_dyadic_target_perf_L32.json"
    baseline = json.loads(baseline_path.read_text())
    onb = field.Onb(DEGREE)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target_seed = tuple(reference["workload"]["target"])
    lam = curves.frobeniusEigenvalue(curve, generator, order)
    canonicalize = XOnlyCycle(onb)
    started = time.perf_counter()
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target_seed], WINDOW, lam, order)
    base_seconds = time.perf_counter() - started
    assert len(labels) == 10624
    assert digests["enumerated_set_sha256"] == baseline["factor_base"][
        "enumerated_set_sha256"]
    left_reps = [point for point in sorted(representatives) if labels[point][0] == 0]
    right_base = [point for point in sorted(labels) if labels[point][0] == 1]
    assert len(left_reps) == WINDOW and len(right_base) == 2 * DEGREE * WINDOW
    compact, build = build_packed(curve, left_reps, right_base, canonicalize)
    assert len(compact) == baseline["index_build"]["quotient_keys"] == 169984
    alpha = baseline["workload"]["known_log_query_scalar"]
    known_log_query_target = curve.mul(generator, alpha)
    workload = {"curve_id": reference["curve_id"],
                "target": target_seed, "input_law": reference["workload"],
                "target_count": 1, "known_log_query_scalar": alpha,
                "doubling_window": WINDOW,
                "bounded_lookups_per_repetition": PREFIX_LOOKUPS,
                "repetitions": 3, "index_variant": "packed_numpy_structured_array",
                "mode": mode}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    comparison = None
    if mode == "compare":
        full, full_build = build_cross_seed_index(
            curve, sorted(labels), representatives, labels, canonicalize)
        full_key_digest = hashlib.sha256(frozen(sorted(full))).hexdigest()
        assert full_key_digest == build["key_sha256"]
        rng = random.Random(202609290483)
        sample_keys = [next(iter(full)), *rng.sample(sorted(full), 1000)]
        for key in sample_keys:
            old_representative, old_pair = full[key]
            new = compact.get(key)
            assert new is not None
            new_representative, new_pair = new
            assert canonicalize.key_and_shift(curve, old_representative)[0] == key
            assert canonicalize.key_and_shift(curve, new_representative)[0] == key
            assert curve.add(*new_pair) == new_representative
            assert curve.add(*old_pair) == old_representative
        comparison = {"full_dict_key_sha256": full_key_digest,
                      "full_dict_index_sha256": full_build["index_sha256"],
                      "baseline_dict_index_sha256": baseline["index_build"]["index_sha256"],
                      "sampled_witness_replays": len(sample_keys),
                      "full_dict_keys": len(full),
                      "full_dict_build_seconds": full_build["build_seconds"]}
        assert full_build["index_sha256"] == baseline["index_build"]["index_sha256"]
    prefixes = [measured_prefix(onb, compact, known_log_query_target, canonicalize)
                for _ in range(3)]
    assert all(row["verified_hit_positions"] == [] for row in prefixes)
    first = next(compact.values())[0]
    second = compact.decode(compact.rows[1])[0]
    planted = curve.add(first, second)
    positive = query_prefix_batch(curve, compact, planted, DEGREE,
                                  canonicalize, 166)
    assert positive["verified_hit_positions"] == [1]
    report = {
        "kind": "n83_target_seed_L32_packed_quotient_index",
        "scope": "complete packed L32 quotient index, bounded ordinary prefixes, planted correctness control; no n83 ordinary relation-yield or DLP claim",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R{1 if mode == 'packed' else 2}",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"], "isogeny": "none",
        "factor_base": {"actual_usable_points_B_before_folding": len(labels),
                        "signed_frobenius_columns": len(representatives),
                        "effective_unknown_log_columns_after_dyadic_labels": 1,
                        **digests},
        "base_enumeration_seconds": base_seconds,
        "packed_build": build,
        "ordinary_query_prefixes": prefixes,
        "ordinary_query_prefix_median_wall_ns": int(statistics.median(
            row["wall_ns"] for row in prefixes)),
        "planted_positive_control": positive,
        "dictionary_comparison": comparison,
        "peak_process_rss_bytes": peak_rss_bytes(),
        "ordinary_relation_yield_measured": None,
        "verified_single_target_dlp": False,
        "verified_complete_solve_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "dyadic_base_geometry.py", "dyadic_n53_relation_probe.py",
            "batch_x_only.py", "compare_batch_x_only.py", "x_only_cycle.py",
            "curves.py", "field.py")},
        "baseline_receipt_sha256": sha(baseline_path),
        "reference_sha256": sha(reference_path),
    }
    output = HERE / "runs" / f"n83_dyadic_compact_{mode}.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"mode": mode, "keys": len(compact),
                      "retained_array_bytes": build["retained_array_bytes"],
                      "build_seconds": build["build_seconds"],
                      "median_prefix_ms": report["ordinary_query_prefix_median_wall_ns"] / 1e6,
                      "peak_rss_bytes": report["peak_process_rss_bytes"],
                      "comparison_verified": comparison is not None}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("packed", "compare"), required=True)
    main(parser.parse_args().mode)
