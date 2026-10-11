#!/usr/bin/env python3
"""Short independent affine blocks against a complete two-G quotient index.

The n53 run can find and verify a natural target relation. The n83 run uses
the already completed L1000 disk index and remains a bounded measurement.
All random block inputs are frozen before the timed query phase.
"""

import argparse
from collections import Counter
from decimal import Decimal, ROUND_CEILING, localcontext
import hashlib
import json
import math
import platform
import resource
import secrets
import time
from pathlib import Path

import numpy as np

import curves
import field
from compare_batch_x_only import CountingField
from dyadic_base_geometry import enumerate_points
from dyadic_n83_compact_index import ROW_DTYPE, encode_key
from dyadic_n83_g_pair_witness_index import hash_file
from perf_probe import sha
from quotient_pair_probe import transform
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
BLOCK_LENGTH = 4096
CONFIG = {53: {"window": 128, "max_blocks": 256, "proposal_id": "Q1034"},
          83: {"window": 1000, "max_blocks": 16, "proposal_id": "Q1033"}}


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def peak_rss_bytes():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if platform.system() == "Darwin" else rss * 1024


class MeasuredCurve(curves.Curve):
    def __init__(self, onb):
        super().__init__(onb)
        self.calls = Counter()

    def add(self, left, right):
        self.calls["add"] += 1
        return super().add(left, right)

    def dbl(self, point):
        self.calls["dbl"] += 1
        return super().dbl(point)

    def frob(self, point, j=1):
        self.calls["frob"] += 1
        return super().frob(point, j)

    def mul(self, point, scalar):
        self.calls["mul"] += 1
        return super().mul(point, scalar)


class DegreePackedIndex:
    """Sorted packed quotient rows with an explicit field-degree witness radix."""

    def __init__(self, rows, left_reps, right_base, curve, degree):
        self.rows = rows
        self.left_reps = left_reps
        self.right_base = right_base
        self.curve = curve
        self.degree = degree

    def decode(self, row):
        packed = int(row["witness"])
        shift = packed % self.degree
        packed //= self.degree
        right_index = packed % len(self.right_base)
        left_index = packed // len(self.right_base)
        pair = (transform(self.curve, self.left_reps[left_index], shift, 1),
                transform(self.curve, self.right_base[right_index], shift, 1))
        return self.curve.add(*pair), pair

    def get(self, key):
        hi, lo = encode_key(key)
        left, right = 0, len(self.rows)
        while left < right:
            middle = (left + right) // 2
            row = self.rows[middle]
            if (int(row["hi"]), int(row["lo"])) < (hi, lo):
                left = middle + 1
            else:
                right = middle
        if left == len(self.rows):
            return None
        row = self.rows[left]
        if (int(row["hi"]), int(row["lo"])) != (hi, lo):
            return None
        return self.decode(row)


def build_n53_index(curve, representatives, g_base, canonicalize):
    degree = canonicalize.degree
    assert degree == 53
    left_reps = sorted(representatives)
    right_base = sorted(g_base)
    orbit_keys = [canonicalize.key_and_shift(curve, point)[0]
                  for point in left_reps]
    assert len(set(orbit_keys)) == len(left_reps)
    orbit_number = {key: i for i, key in enumerate(orbit_keys)}
    buckets = [[] for _ in left_reps]
    for right_index, point in enumerate(right_base):
        key = canonicalize.key_and_shift(curve, point)[0]
        buckets[orbit_number[key]].append(right_index)
    assert all(len(bucket) == 2 * degree for bucket in buckets)
    generators = degree * len(left_reps) * (len(left_reps) + 1)
    rows = np.empty(generators, dtype=ROW_DTYPE)
    at = 0
    started = time.perf_counter_ns()
    for left_index, left in enumerate(left_reps):
        for bucket in buckets[left_index:]:
            for right_index in bucket:
                total = curve.add(left, right_base[right_index])
                key, shift = canonicalize.key_and_shift(curve, total)
                hi, lo = encode_key(key)
                packed = (left_index * len(right_base) + right_index) * degree + shift
                rows[at] = (hi, lo, packed)
                at += 1
    assert at == generators
    build_ns = time.perf_counter_ns() - started
    sort_started = time.perf_counter_ns()
    rows.sort(order=["hi", "lo"], kind="quicksort")
    keep = np.empty(generators, dtype=np.bool_)
    keep[0] = True
    keep[1:] = ((rows["hi"][1:] != rows["hi"][:-1]) |
                (rows["lo"][1:] != rows["lo"][:-1]))
    unique = rows[keep].copy()
    sort_ns = time.perf_counter_ns() - sort_started
    index = DegreePackedIndex(unique, left_reps, right_base, curve, degree)
    return index, {
        "unordered_pair_orbit_generators": generators,
        "quotient_keys": len(unique),
        "raw_array_bytes": rows.nbytes,
        "retained_array_bytes": unique.nbytes,
        "retained_array_sha256": hashlib.sha256(unique.tobytes()).hexdigest(),
        "pair_generation_seconds": build_ns / 1e9,
        "sort_and_dedup_seconds": sort_ns / 1e9,
    }


def bound(order, support, block_length):
    """Paley-Zygmund on pairwise-uniform affine samples, then independent restarts."""
    assert 1 <= support < order and 1 <= block_length < order
    with localcontext() as context:
        context.prec = 80
        mu = Decimal(block_length * support) / Decimal(order)
        q = Decimal(1) / (Decimal(1) + mu)
        # Add one block after rounding so decimal evaluation cannot weaken
        # the stated 95% guarantee at an integer boundary.
        blocks95 = int((Decimal(20).ln() / (Decimal(1) + mu).ln())
                       .to_integral_value(rounding=ROUND_CEILING)) + 1
        expected_upper = Decimal(order) / Decimal(support) + block_length
        return {
            "proof": "E[X]=T*M/r; Var(X)=E[X]*(1-M/r)*(r-T)/(r-1) <= E[X]; Paley-Zygmund gives P(hit per independent affine block) >= mu/(1+mu), mu=T*M/r. Restarting complete blocks gives E[trials] <= r/M+T and failure after K blocks <= (1+mu)^(-K).",
            "block_hit_probability_lower_decimal": str(mu / (1 + mu)),
            "block_failure_probability_upper_decimal": str(q),
            "expected_scan_attempts_upper_decimal": str(expected_upper),
            "expected_scan_attempts_upper_log2": math.log2(float(expected_upper)),
            "blocks_for_at_least_95pct_success": blocks95,
            "scan_attempts_for_at_least_95pct_success": blocks95 * block_length,
            "scan_attempts_for_at_least_95pct_success_log2": math.log2(
                blocks95 * block_length),
            "support_M": support,
            "subgroup_order_r": str(order),
            "block_length_T": block_length,
        }


def replay_hit(curve, index, complement, key, shift, labels,
               generator, target, alpha, order, degree):
    representative, pair = index.get(key)
    undo = (-shift) % degree
    aligned = transform(curve, representative, undo, 1)
    if aligned == complement:
        sign = 1
    elif curve.neg(aligned) == complement:
        sign = -1
    else:
        raise AssertionError("quotient-key collision failed point replay")
    pair = tuple(transform(curve, point, undo, sign) for point in pair)
    assert all(labels[point][0] == 0 for point in pair)
    assert labels[target] == (1, 1)
    coefficient = sum(labels[point][1] for point in pair) % order
    expected = curve.mul(generator, alpha)
    assert curve.add(curve.add(pair[0], pair[1]), target) == expected
    scalar = (alpha - coefficient) % order
    assert curve.mul(generator, scalar) == target
    return {"point_witness": [pair[0], pair[1], target],
            "known_G_coefficient_mod_r": str(coefficient),
            "target_Q_coefficient_mod_r": 1,
            "query_scalar_alpha": str(alpha),
            "recovered_scalar": str(scalar),
            "group_and_scalar_replay_verified": True}


def paths(degree, window):
    stem = f"n{degree}_affine_restart_L{window}"
    return HERE / "runs" / f"{stem}_inputs.json", HERE / "runs" / f"{stem}_stage.json"


def prepare(degree, window, max_blocks):
    input_path, _ = paths(degree, window)
    if input_path.exists():
        raise FileExistsError(input_path)
    reference_path = HERE / "runs" / f"n{degree}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    order = int(reference["subgroup_order"])
    rows = [[secrets.randbelow(order), 1 + secrets.randbelow(order - 1)]
            for _ in range(max_blocks)]
    report = {
        "kind": "frozen_independent_affine_restart_inputs",
        "curve_id": reference["curve_id"],
        "target": reference["workload"]["target"],
        "degree": degree, "G_doubling_window": window,
        "block_length": BLOCK_LENGTH, "max_blocks": max_blocks,
        "input_law": "independent OS-random alpha0 uniform Z_r and delta uniform nonzero Z_r per block",
        "rows": rows,
        "rows_sha256": hashlib.sha256(frozen(rows)).hexdigest(),
        "reference_sha256": sha(reference_path),
        "source_sha256": sha(Path(__file__)),
    }
    input_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"inputs": str(input_path), "sha256": sha(input_path),
                      "blocks": max_blocks}))


def run(degree, window, max_blocks):
    proposal_id = CONFIG[degree]["proposal_id"]
    reference_path = HERE / "runs" / f"n{degree}_perf_prefix.json"
    input_path, report_path = paths(degree, window)
    reference = json.loads(reference_path.read_text())
    inputs = json.loads(input_path.read_text())
    assert inputs["source_sha256"] == sha(Path(__file__))
    assert inputs["reference_sha256"] == sha(reference_path)
    assert inputs["curve_id"] == reference["curve_id"]
    assert inputs["degree"] == degree and inputs["G_doubling_window"] == window
    assert inputs["block_length"] == BLOCK_LENGTH
    assert inputs["max_blocks"] == max_blocks == len(inputs["rows"])
    assert inputs["rows_sha256"] == hashlib.sha256(frozen(
        inputs["rows"])).hexdigest()
    order = int(reference["subgroup_order"])
    assert curves.isPrimeBig(order)
    raw_field = field.Onb(degree)
    counted_field = CountingField(raw_field)
    curve = MeasuredCurve(counted_field)
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert tuple(inputs["target"]) == target
    assert curve.mul(generator, order) is None
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, order)
    assert pow(eigenvalue, degree, order) == 1
    assert all(pow(eigenvalue, j, order) not in (1, order - 1)
               for j in range(1, degree))
    canonicalize = XOnlyCycle(raw_field)
    precompute_started = time.perf_counter_ns()
    g_labels, g_reps, g_digests = enumerate_points(
        curve, counted_field, [generator], window, eigenvalue, order)
    g_base = sorted(g_labels)
    if degree == 53:
        index, index_info = build_n53_index(
            curve, g_reps, g_base, canonicalize)
    else:
        index_receipt_path = (HERE / "runs" /
            "n83_dyadic_G_pair_witness_index_L1000.json")
        index_receipt = json.loads(index_receipt_path.read_text())
        assert index_receipt["curve_id"] == reference["curve_id"]
        sorted_path = Path(index_receipt["local_sorted_rows"])
        assert sorted_path.stat().st_size == index_receipt["raw_array_bytes"]
        assert hash_file(sorted_path) == index_receipt["sorted_array_sha256"]
        rows = np.memmap(sorted_path, dtype=ROW_DTYPE, mode="r",
                         shape=(index_receipt["unordered_pair_orbit_generators"],))
        index = DegreePackedIndex(rows, sorted(g_reps), g_base, curve, degree)
        index_info = {
            "unordered_pair_orbit_generators": index_receipt[
                "unordered_pair_orbit_generators"],
            "quotient_keys": index_receipt["quotient_keys"],
            "raw_array_bytes": index_receipt["raw_array_bytes"],
            "sorted_array_sha256": index_receipt["sorted_array_sha256"],
            "index_receipt_sha256": sha(index_receipt_path),
            "index_cache_policy": "sequential SHA-256 pass before timed queries; OS page cache uncontrolled",
        }
    assert index.get(-1) is not None
    precompute_seconds = (time.perf_counter_ns() - precompute_started) / 1e9
    support = 1 + (index_info["quotient_keys"] - 1) * 2 * degree
    assert support < order
    if degree == 83:
        support_receipt = json.loads((HERE / "runs" /
            "n83_dyadic_G_pair_scalar_support_L1000.json").read_text())
        assert support == int(support_receipt[
            "L1000_exact_distinct_G_pair_sums"])
    work_bound = bound(order, support, BLOCK_LENGTH)
    counts_before_online = curve.calls.copy()
    fields_before_online = counted_field.counts.copy()
    online_started = time.perf_counter_ns()
    assert curve.mul(target, order) is None
    q_labels, q_reps, _ = enumerate_points(
        curve, counted_field, [target], 1, eigenvalue, order)
    assert set(g_labels).isdisjoint(q_labels)
    labels = dict(g_labels)
    labels.update({point: (1, coefficient)
                   for point, (_, coefficient) in q_labels.items()})
    assert labels[target] == (1, 1)
    encoded_points = json.dumps(sorted(labels), separators=(",", ":")).encode()
    encoded_labels = frozen(sorted((p[0], p[1], label[0], label[1])
                                   for p, label in labels.items()))
    base = {
        "construction": f"signed-Frobenius closure of {window} G doublings and one public Q orbit",
        "G_doubling_window": window, "Q_doubling_window": 1,
        "nominal_seed_columns": 2,
        "actual_usable_points_B_before_folding": len(labels),
        "signed_frobenius_columns": len(g_reps) + len(q_reps),
        "effective_unknown_log_columns_after_dyadic_labels": 1,
        "enumerated_set_sha256": hashlib.sha256(encoded_points).hexdigest(),
        "point_coefficient_label_sha256": hashlib.sha256(encoded_labels).hexdigest(),
        "G_only_point_set_sha256": g_digests["enumerated_set_sha256"],
    }
    base_seconds = (time.perf_counter_ns() - online_started) / 1e9
    blocks = []
    relation = None
    total_attempts = 0
    for block_number, (alpha0, delta) in enumerate(inputs["rows"], 1):
        assert 0 <= alpha0 < order and 0 < delta < order
        before_calls = curve.calls.copy()
        before_fields = counted_field.counts.copy()
        canonical_counts = {}
        started = time.perf_counter_ns()
        point = curve.add(curve.mul(generator, alpha0), curve.neg(target))
        step = curve.mul(generator, delta)
        alpha = alpha0
        attempts = 0
        for _ in range(BLOCK_LENGTH):
            attempts += 1
            key, shift = canonicalize.key_and_shift(
                curve, point, canonical_counts)
            if index.get(key) is not None:
                relation = replay_hit(curve, index, point, key, shift,
                                      labels, generator, target, alpha,
                                      order, degree)
                break
            point = curve.add(point, step)
            alpha = (alpha + delta) % order
        total_attempts += attempts
        blocks.append({
            "block": block_number,
            "alpha0": str(alpha0), "delta": str(delta),
            "attempts_including_failed": attempts,
            "status": "verified_relation" if relation else "bounded_miss",
            "wall_ns": time.perf_counter_ns() - started,
            "group_calls": dict(curve.calls - before_calls),
            "field_api_calls": dict(counted_field.counts - before_fields),
            "canonical_operations": canonical_counts,
        })
        if relation:
            break
    independently_verified = False
    if relation:
        independent_curve = curves.Curve(field.Onb(degree))
        independently_verified = (independent_curve.mul(
            generator, int(relation["recovered_scalar"])) == target)
        assert independently_verified
        # These solved receipts are controls, never inputs to the search.
        comparison_path = HERE / "runs" / (
            "n53_dyadic_target_seed_dlp_w64.json" if degree == 53
            else "n83_public_target_rho_solved.json")
        prior = json.loads(comparison_path.read_text())
        assert int(prior["recovered_scalar"]) == int(relation[
            "recovered_scalar"])
    online_seconds = (time.perf_counter_ns() - online_started) / 1e9
    workload = {
        "curve_id": reference["curve_id"], "target": target,
        "target_count": 1, "G_doubling_window": window,
        "Q_doubling_window": 1, "block_length": BLOCK_LENGTH,
        "input_law": inputs["input_law"],
        "frozen_inputs_sha256": sha(input_path),
        "max_blocks": max_blocks,
    }
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": f"n{degree}_short_affine_restart_relation_search",
        "scope": "complete exact G-pair lookup, frozen independent affine blocks, all misses charged, one-target scalar replay on any natural hit",
        "proposal_id": proposal_id, "candidate_id": None,
        "run_id": f"{proposal_id}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "factor_base": base,
        "target_independent_index": index_info,
        "target_independent_precompute_seconds": precompute_seconds,
        "online_target_base_seconds": base_seconds,
        "online_one_target_seconds": online_seconds,
        "online_interval": "first target-Q base enumeration through independent scalar replay or exhaustion of frozen bounded blocks",
        "ordinary_query_blocks": blocks,
        "ordinary_attempts_including_failed": total_attempts,
        "ordinary_quotient_hits": 1 if relation else 0,
        "relation": relation,
        "recovered_scalar": relation["recovered_scalar"] if relation else None,
        "verified_single_target_dlp": independently_verified,
        "complete_calibrated_work_log2": None,
        "group_calls_cold_including_input_preflight": dict(curve.calls),
        "field_api_calls_cold_including_input_preflight": dict(
            counted_field.counts),
        "group_calls_online": dict(curve.calls - counts_before_online),
        "field_api_calls_online": dict(counted_field.counts - fields_before_online),
        "restart_work_bound": work_bound,
        "peak_process_rss_bytes": peak_rss_bytes(),
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "compare_batch_x_only.py", "dyadic_base_geometry.py",
            "dyadic_n83_compact_index.py", "dyadic_n83_g_pair_witness_index.py",
            "perf_probe.py", "quotient_pair_probe.py", "x_only_cycle.py",
            "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
        "frozen_inputs_sha256": sha(input_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"degree": degree, "actual_B": len(labels),
                      "index_keys": index_info["quotient_keys"],
                      "ordinary_attempts": total_attempts,
                      "verified_dlp": independently_verified,
                      "online_seconds": round(online_seconds, 6),
                      "expected_work_log2": work_bound[
                          "expected_scan_attempts_upper_log2"]}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=sorted(CONFIG), required=True)
    parser.add_argument("--window", type=int)
    parser.add_argument("--max-blocks", type=int)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    cfg = CONFIG[args.degree]
    window = args.window or cfg["window"]
    max_blocks = args.max_blocks or cfg["max_blocks"]
    if window != cfg["window"] or max_blocks != cfg["max_blocks"]:
        raise ValueError("this stage has one frozen window and block budget per degree")
    if args.prepare:
        prepare(args.degree, window, max_blocks)
    else:
        run(args.degree, window, max_blocks)


if __name__ == "__main__":
    main()
