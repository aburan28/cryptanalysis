#!/usr/bin/env python3
"""Two-table signed-Frobenius pair-sum match on an ordinary n=53 target."""

import hashlib
import json
import platform
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n53_perf_prefix.json")
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey
from probe_n53_relation import base_and_columns
from run_n23 import frozen, point_digest, sha

TABLE_SAMPLES = 500000
QUERY_SAMPLES = 1500000
TABLE_SEED = 530930
QUERY_SEED = 530931


def pair_sample(rng, base):
    first = rng.randrange(len(base))
    second = rng.randrange(len(base))
    return first, second


def witness(curve, base, base_set, target, orbit, zero, one):
    first0, second0, exponent0, sign0 = zero
    first1, second1, exponent1, sign1 = one
    shift = (exponent0 - exponent1) % orbit.n
    sign = sign0 * sign1
    left = [curve.frob(base[first0], shift),
            curve.frob(base[second0], shift)]
    if sign < 0:
        left = [curve.neg(point) for point in left]
    points = left + [base[first1], base[second1]]
    assert all(point in base_set for point in points)
    if any(points[i] == curve.neg(points[j])
           for i in range(4) for j in range(i)):
        return None
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == target
    return {"points": [list(point) for point in points],
            "zero_meta": list(zero), "one_meta": list(one),
            "frobenius_shift_of_zero_pair": shift,
            "sign_of_zero_pair": sign}


def search(curve, base, target, orbit):
    table_rng = random.Random(TABLE_SEED)
    query_rng = random.Random(QUERY_SEED)
    table = {}
    table_repeats = 0
    skipped_identity = 0
    started = time.perf_counter_ns()
    for _ in range(TABLE_SAMPLES):
        first, second = pair_sample(table_rng, base)
        pair = curve.add(base[first], base[second])
        if pair is None:
            skipped_identity += 1
            continue
        key, exponent, sign = orbit.canonical(pair)
        if key in table:
            table_repeats += 1
        else:
            table[key] = (first, second, exponent, sign)
    table_ns = time.perf_counter_ns() - started
    base_set = set(base)
    query_started = time.perf_counter_ns()
    proper_rejections = 0
    for query_number in range(1, QUERY_SAMPLES + 1):
        first, second = pair_sample(query_rng, base)
        pair = curve.add(base[first], base[second])
        if pair is None:
            skipped_identity += 1
            continue
        point = curve.add(target, curve.neg(pair))
        key, exponent, sign = orbit.canonical(point)
        earlier = table.get(key)
        if earlier is None:
            continue
        relation = witness(curve, base, base_set, target, orbit,
                           earlier, (first, second, exponent, sign))
        if relation is not None:
            return {"status": "verified_four_point_relation",
                    "table_samples": TABLE_SAMPLES,
                    "table_distinct_keys": len(table),
                    "table_same_key_repeats": table_repeats,
                    "query_samples": query_number,
                    "skipped_identity_pairs": skipped_identity,
                    "proper_rejections": proper_rejections,
                    "table_wall_ns": table_ns,
                    "query_wall_ns": time.perf_counter_ns() - query_started,
                    "relation": relation}
        proper_rejections += 1
    return {"status": "budget", "table_samples": TABLE_SAMPLES,
            "table_distinct_keys": len(table),
            "table_same_key_repeats": table_repeats,
            "query_samples": QUERY_SAMPLES,
            "skipped_identity_pairs": skipped_identity,
            "proper_rejections": proper_rejections,
            "table_wall_ns": table_ns,
            "query_wall_ns": time.perf_counter_ns() - query_started,
            "relation": None}


def main():
    reference = json.loads(REFERENCE.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N53Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == curve_id
    order = identity["curve"]["subgroup_order"]
    cofactor = identity["curve"]["cofactor"]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    target = tuple(reference["workload"]["target"])
    generator = tuple(identity["curve"]["generator"])
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    setup_started = time.perf_counter_ns()
    base, representatives, rational_x = base_and_columns(curve, onb,
                                                           order, cofactor)
    setup_ns = time.perf_counter_ns() - setup_started
    assert len(base) == 24062 and len(representatives) == 227
    orbit = OrbitKey(onb)
    result = search(curve, base, target, orbit)
    workload = {"curve_id": curve_id, "target": list(target),
                "target_count": 1, "target_input_law": "fixed public subgroup point",
                "normal_x_weight_bound": 3,
                "table_seed": TABLE_SEED, "query_seed": QUERY_SEED,
                "table_sample_cap": TABLE_SAMPLES,
                "query_sample_cap": QUERY_SAMPLES,
                "quotient_rule": "signed Frobenius"}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "n53_full_weight3_base_two_table_signed_frobenius_pair_match",
        "scope": "one ordinary public target; relation stage only, no base logs or DLP",
        "proposal_id": "Q1040", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "workload_id": workload_id, "workload": workload,
        "isogeny": "none",
        "factor_base": {
            "construction": "all nonzero type-II ONB x supports of weight at most three; rational lift; cofactor projection; both signs; full Frobenius closure",
            "cofactor_projection": cofactor,
            "rational_x_coordinates": rational_x,
            "actual_usable_points_B_before_folding": len(base),
            "signed_frobenius_columns": len(representatives),
            "enumerated_set_sha256": point_digest(base)},
        "target_independent_base_and_column_setup_ns": setup_ns,
        "ordinary_query": result,
        "verified_relation_count": int(result["relation"] is not None),
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "base_source_sha256": sha(HERE / "probe_n53_relation.py"),
        "orbit_key_sha256": sha(HERE / "orbit_key.py"),
        "reference_sha256": sha(REFERENCE),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
    }
    path = HERE / "runs" / "n53_weight3_quotient_table_probe.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": curve_id, "B": len(base),
                      "columns": len(representatives),
                      "status": result["status"],
                      "table_distinct_keys": result["table_distinct_keys"],
                      "query_samples": result["query_samples"],
                      "table_s": result["table_wall_ns"] / 1e9,
                      "query_s": result["query_wall_ns"] / 1e9,
                      "receipt": str(path)}))


if __name__ == "__main__":
    main()
