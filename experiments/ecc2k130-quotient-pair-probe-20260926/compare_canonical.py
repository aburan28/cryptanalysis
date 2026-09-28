#!/usr/bin/env python3
"""Matched, bounded quotient-canonicalization stage runs at n=53 and n=83."""

import argparse
import hashlib
import json
import platform
import resource
import statistics
import time
from pathlib import Path

import curves
from fast_canonical import canonical_x_first
from perf_probe import COFACTOR as TOY_COFACTOR, base_prefix, frozen_json, sha
from quotient_pair_probe import CountedCurve, canonical, point_key, transform

HERE = Path(__file__).resolve().parent
COFACTOR = {**TOY_COFACTOR, 131: 4}
PROPOSALS = {(53, "scan"): "Q1001", (53, "xfirst"): "Q1002",
             (83, "scan"): "Q1003", (83, "xfirst"): "Q1004",
             (131, "scan"): "Q1005", (131, "xfirst"): "Q1006"}


def canonicalize(counted, point, degree, variant, field_counts):
    if variant == "scan":
        return canonical(counted, point, degree)
    return canonical_x_first(counted, point, degree, field_counts)


def build_index(curve, base, reps, degree, variant):
    counted = CountedCurve(curve)
    field_counts = {}
    index = {}
    started = time.perf_counter_ns()
    for left in reps:
        for right in base:
            total = counted.add(left, right)
            key, shift, sign = canonicalize(
                counted, total, degree, variant, field_counts)
            if key not in index:
                index[key] = (transform(counted, left, shift, sign),
                              transform(counted, right, shift, sign))
    wall_ns = time.perf_counter_ns() - started
    for key, pair in index.items():
        if point_key(curve.add(*pair)) != key:
            raise AssertionError("canonical pair witness failed replay")
    digest = hashlib.sha256(frozen_json(
        sorted((key, pair) for key, pair in index.items()))).hexdigest()
    return index, {"eligible_generators": len(reps) * len(base),
                   "quotient_keys": len(index), "index_sha256": digest,
                   "wall_ns": wall_ns, "point_operations": counted.counts,
                   "field_operations": field_counts}


def query_prefix(curve, index, target, degree, variant, lookup_budget):
    counted = CountedCurve(curve)
    field_counts = {}
    started = time.perf_counter_ns()
    lookups = 0
    verified = 0
    hit_positions = []
    for key, left_pair in index.items():
        current = None if key == (-1, -1) else key
        for shift in range(degree):
            for sign in (1, -1):
                candidate = current if sign == 1 else counted.neg(current)
                complement = counted.add(target, counted.neg(candidate))
                comp_key, comp_shift, comp_sign = canonicalize(
                    counted, complement, degree, variant, field_counts)
                lookups += 1
                counted.counts["lookup"] += 1
                match = index.get(comp_key)
                if match is not None:
                    first = tuple(transform(counted, point, shift, sign)
                                  for point in left_pair)
                    second = tuple(transform(counted, point,
                                             (-comp_shift) % degree, comp_sign)
                                   for point in match)
                    total = None
                    for point in first + second:
                        total = curve.add(total, point)
                    if total != target:
                        raise AssertionError("four-point witness failed replay")
                    verified += 1
                    hit_positions.append(lookups)
                if lookups == lookup_budget:
                    return {"status": "budgeted_prefix", "lookups": lookups,
                            "verified_hits": verified,
                            "hit_positions": hit_positions,
                            "wall_ns": time.perf_counter_ns() - started,
                            "point_operations": counted.counts,
                            "field_operations": field_counts}
            current = counted.frob(current)
    raise AssertionError("lookup budget exceeds index traversal")


def run(degree, variant, run_number, repetitions, lookup_budget):
    run_started = time.perf_counter_ns()
    reference_name = ("n131_stage_reference.json" if degree == 131
                      else f"n{degree}_perf_prefix.json")
    reference_path = HERE / "runs" / reference_name
    reference = json.loads(reference_path.read_text())
    subgroup_order = int(reference["subgroup_order"])
    assert curves.curveOrder(degree) == COFACTOR[degree] * subgroup_order
    _, curve, base, reps, base_info = base_prefix(
        degree, COFACTOR[degree], subgroup_order, 2)
    if base_info["base_sha256"] != reference["base"]["base_sha256"]:
        raise AssertionError("factor base changed from frozen reference")
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    if curve.mul(generator, reference["target_fixture_scalar"]) != target:
        raise AssertionError("ordinary target fixture failed scalar replay")
    index, build = build_index(curve, base, reps, degree, variant)
    if build["index_sha256"] != reference["index_prefix"]["index_prefix_sha256"]:
        raise AssertionError("quotient index differs from frozen reference")
    query_runs = [query_prefix(curve, index, target, degree, variant,
                               lookup_budget) for _ in range(repetitions)]
    if len({tuple(row["hit_positions"]) for row in query_runs}) != 1:
        raise AssertionError("repeated query traces differ")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        peak *= 1024
    proposal_id = PROPOSALS[(degree, variant)]
    report = {"kind": "matched_quotient_canonicalization_stage",
            "claim_boundary": "complete two-orbit selected-base index; bounded repeated ordinary-target lookup prefix; no relation-yield, DLP, or rho-speedup claim",
            "proposal_id": proposal_id, "candidate_id": None,
            "run_id": f"{proposal_id}W{reference['workload_id']}R{run_number}",
            "workload_id": reference["workload_id"],
            "pair_block_id": f"n{degree}_seed{reference['workload']['seed']}_r{run_number}",
            "curve_id": reference["curve_id"],
            "curve_identity_sha256": hashlib.sha256(frozen_json(
                reference["curve_identity_record"])).hexdigest(),
            "isogeny": "none", "isogeny_route_ref": "none",
            "endomorphism_order_conductor": None,
            "field_degree": degree, "subgroup_order": reference["subgroup_order"],
            "factor_base": {"nominal_normal_x_weight": 2,
                            "selected_rational_x_orbits": 2,
                            "geometric_points_before_projection": 4 * degree,
                            "actual_usable_points_B_before_folding": len(base),
                            "effective_columns_after_sign_frobenius_folding": len(reps),
                            "base_sha256": base_info["base_sha256"],
                            "base_build_ns": base_info["base_build_ns"],
                            "selection": reference["base_policy"]},
            "target": target,
            "target_point_sha256": hashlib.sha256(frozen_json(target)).hexdigest(),
            "target_fixture_seed": reference["workload"]["seed"],
            "target_fixture_scalar_replay_verified": True,
            "variant": variant, "index_build": build,
            "lookup_budget_per_repetition": lookup_budget,
            "query_repetitions": repetitions,
            "query_runs": query_runs,
            "query_wall_ns_median": int(statistics.median(
                row["wall_ns"] for row in query_runs)),
            "peak_process_rss_bytes": peak,
            "python": platform.python_version(),
            "machine": platform.machine(),
            "source_sha256": sha(Path(__file__)),
            "dependency_sha256": {name: sha(HERE / name) for name in (
                "fast_canonical.py", "perf_probe.py", "quotient_pair_probe.py",
                "curves.py", "field.py")},
            "frozen_reference_sha256": sha(reference_path)}
    report["run_wall_ns"] = time.perf_counter_ns() - run_started
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83, 131), required=True)
    parser.add_argument("--variant", choices=("scan", "xfirst"), required=True)
    parser.add_argument("--run-number", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--lookups", type=int, default=2048)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.run_number, args.repetitions, args.lookups) < 1:
        parser.error("run number, repetitions, and lookup budget must be positive")
    report = run(args.degree, args.variant, args.run_number,
                 args.repetitions, args.lookups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"degree": args.degree, "variant": args.variant,
                      "index_build_ns": report["index_build"]["wall_ns"],
                      "query_median_ns": report["query_wall_ns_median"],
                      "hits": report["query_runs"][0]["verified_hits"]}))


if __name__ == "__main__":
    main()
