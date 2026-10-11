#!/usr/bin/env python3
"""Paired bounded quotient-lookup benchmark for ONB cycle canonicalization."""

import argparse
import hashlib
import json
import platform
import resource
import statistics
import time
from pathlib import Path

import curves
from cycle_canonical import CycleCanonical
from fast_canonical import canonical_x_first
from perf_probe import COFACTOR, base_prefix, frozen_json, sha
from quotient_pair_probe import CountedCurve, point_key, transform

HERE = Path(__file__).resolve().parent
PROPOSALS = {53: {"xfirst": "Q1002", "cycle": "Q1007"},
             83: {"xfirst": "Q1004", "cycle": "Q1008"}}


def build_index(curve, base, reps, degree, canonicalize):
    counted = CountedCurve(curve)
    counts = {}
    index = {}
    started = time.perf_counter_ns()
    for left in reps:
        for right in base:
            total = counted.add(left, right)
            key, shift, sign = canonicalize(counted, total, counts)
            if key not in index:
                index[key] = (transform(counted, left, shift, sign),
                              transform(counted, right, shift, sign))
    elapsed = time.perf_counter_ns() - started
    for key, pair in index.items():
        assert point_key(curve.add(*pair)) == key
    return index, {"wall_ns": elapsed, "generators": len(reps) * len(base),
                   "keys": len(index), "point_operations": counted.counts,
                   "canonical_operations": counts,
                   "index_sha256": hashlib.sha256(frozen_json(
                       sorted((key, pair) for key, pair in index.items()))).hexdigest()}


def query_prefix(curve, index, target, degree, canonicalize, limit):
    counted = CountedCurve(curve)
    counts = {}
    started = time.perf_counter_ns()
    lookups = 0
    hits = []
    for key, left_pair in index.items():
        point = None if key == (-1, -1) else key
        for shift in range(degree):
            for sign in (1, -1):
                candidate = point if sign == 1 else counted.neg(point)
                complement = counted.add(target, counted.neg(candidate))
                comp_key, comp_shift, comp_sign = canonicalize(counted, complement, counts)
                lookups += 1
                counted.counts["lookup"] += 1
                match = index.get(comp_key)
                if match is not None:
                    first = tuple(transform(counted, p, shift, sign) for p in left_pair)
                    second = tuple(transform(counted, p, (-comp_shift) % degree,
                                             comp_sign) for p in match)
                    total = None
                    for p in first + second:
                        total = curve.add(total, p)
                    assert total == target, "four-point witness failed replay"
                    hits.append(lookups)
                if lookups == limit:
                    return {"status": "bounded_prefix", "lookups": lookups,
                            "verified_hit_positions": hits,
                            "wall_ns": time.perf_counter_ns() - started,
                            "point_operations": counted.counts,
                            "canonical_operations": counts}
            point = counted.frob(point)
    raise AssertionError("lookup limit exceeds complete index scan")


def run(degree, blocks, repetitions, lookups):
    reference_path = HERE / "runs" / f"n{degree}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    order = int(reference["subgroup_order"])
    assert curves.curveOrder(degree) == COFACTOR[degree] * order
    onb, curve, base, reps, base_info = base_prefix(
        degree, COFACTOR[degree], order, 2)
    assert base_info["base_sha256"] == reference["base"]["base_sha256"]
    target = tuple(reference["workload"]["target"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    assert curve.mul(generator, reference["target_fixture_scalar"]) == target
    cycle = CycleCanonical(onb)
    variants = {"xfirst": lambda c, p, counts: canonical_x_first(c, p, degree, counts),
                "cycle": cycle.canonical}
    indexes = {}
    builds = {}
    for variant, canonicalize in variants.items():
        indexes[variant], builds[variant] = build_index(
            curve, base, reps, degree, canonicalize)
    assert builds["xfirst"]["index_sha256"] == reference[
        "index_prefix"]["index_prefix_sha256"]
    assert builds["cycle"]["keys"] == builds["xfirst"]["keys"]
    samples = []
    for block in range(1, blocks + 1):
        for variant in (("xfirst", "cycle") if block % 2 else ("cycle", "xfirst")):
            measured = [query_prefix(curve, indexes[variant], target, degree,
                                     variants[variant], lookups)
                        for _ in range(repetitions)]
            samples.append({"variant": variant, "proposal_id": PROPOSALS[degree][variant],
                            "run_id": f"{PROPOSALS[degree][variant]}W{reference['workload_id']}R{block+6}",
                            "block": block, "repetitions": measured,
                            "median_wall_ns": int(statistics.median(
                                row["wall_ns"] for row in measured))})
        left, right = samples[-2:]
        assert [r["verified_hit_positions"] for r in left["repetitions"]] == [
            r["verified_hit_positions"] for r in right["repetitions"]]
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        peak *= 1024
    return {"kind": "paired_bounded_quotient_cycle_stage", "candidate_id": None,
            "claim_boundary": "complete selected two-orbit base index and bounded lookup prefixes; no full PDP, relation yield, matrix, DLP, or rho comparison",
            "curve_id": reference["curve_id"], "curve_identity_record": reference["curve_identity_record"],
            "workload_id": "W" + reference["workload_id"], "target": target,
            "target_fixture_scalar_replay_verified": True,
            "isogeny": "none", "endomorphism_order_conductor": None,
            "factor_base": {"nominal_normal_x_weight": 2,
                            "selected_rational_x_orbits": 2,
                            "geometric_points_before_projection": 4 * degree,
                            "actual_usable_points_B_before_folding": len(base),
                            "effective_columns_after_sign_frobenius_folding": len(reps),
                            "base_sha256": base_info["base_sha256"]},
            "index_builds": builds, "lookup_budget_per_repetition": lookups,
            "paired_blocks": blocks, "repetitions_per_block": repetitions,
            "samples": samples, "peak_process_rss_bytes": peak,
            "python": platform.python_version(), "machine": platform.machine(),
            "source_sha256": sha(Path(__file__)),
            "dependency_sha256": {name: sha(HERE / name) for name in (
                "cycle_canonical.py", "fast_canonical.py", "perf_probe.py",
                "quotient_pair_probe.py", "curves.py", "field.py")},
            "frozen_reference_sha256": sha(reference_path),
            "verified_single_target_dlp": False,
            "verified_full_dlp_work_log2": None,
            "verified_single_target_online_work_log2": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--blocks", type=int, default=6)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--lookups", type=int, default=2048)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.blocks, args.repetitions, args.lookups) < 1:
        parser.error("blocks, repetitions, and lookups must be positive")
    result = run(args.degree, args.blocks, args.repetitions, args.lookups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"degree": args.degree, "curve_id": result["curve_id"],
                      "factor_base_B": result["factor_base"]["actual_usable_points_B_before_folding"],
                      "index_keys": {k: v["keys"] for k, v in result["index_builds"].items()},
                      "median_ns": {name: int(statistics.median(
                          row["median_wall_ns"] for row in result["samples"]
                          if row["variant"] == name)) for name in ("xfirst", "cycle")}}))


if __name__ == "__main__":
    main()
