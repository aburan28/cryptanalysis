#!/usr/bin/env python3
"""Known-log two-G index plus sampled three-Q sums for one n53 DLP."""

import hashlib
import json
import random
import resource
import time
from pathlib import Path

import curves
import field
from dyadic_base_geometry import enumerate_points
from perf_probe import sha
from quotient_pair_probe import CountedCurve, transform
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1024"
WINDOW = 64
QUERY_SEED = 202609290553
MAX_TRIPLE_ATTEMPTS = 5_000_000


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def build_g_pair_index(curve, g_base, g_representatives, canonicalize):
    counted = CountedCurve(curve)
    index = {}
    generators = 0
    started = time.perf_counter()
    for left in g_representatives:
        for right in g_base:
            generators += 1
            total = counted.add(left, right)
            key, shift = canonicalize.key_and_shift(counted, total)
            if key not in index:
                pair = (transform(counted, left, shift, 1),
                        transform(counted, right, shift, 1))
                representative = curve.add(*pair)
                assert canonicalize.key_and_shift(curve, representative) == (key, 0)
                index[key] = (representative, pair)
    return index, {"pair_generators": generators, "quotient_keys": len(index),
                   "build_seconds": time.perf_counter() - started,
                   "point_operations": counted.counts,
                   "index_sha256": hashlib.sha256(
                       frozen(sorted(index.items()))).hexdigest()}


def sample_triples(curve, index, q_base, labels, alpha_g, alpha, generator,
                   target_seed, order, canonicalize, rng, limit):
    counted = CountedCurve(curve)
    started = time.perf_counter()
    attempts = 0
    quotient_hits = 0
    verified_group_relations = 0
    zero_target_coefficient = 0
    relation = None
    for _ in range(limit):
        attempts += 1
        triple = tuple(q_base[rng.randrange(len(q_base))] for _ in range(3))
        triple_sum = counted.add(counted.add(triple[0], triple[1]), triple[2])
        complement = counted.add(alpha_g, counted.neg(triple_sum))
        key, comp_shift = canonicalize.key_and_shift(counted, complement)
        match = index.get(key)
        counted.counts["lookup"] += 1
        if match is None:
            continue
        quotient_hits += 1
        representative, pair = match
        undo = (-comp_shift) % 53
        aligned = transform(counted, representative, undo, 1)
        if aligned == complement:
            sign = 1
        elif counted.neg(aligned) == complement:
            sign = -1
        else:
            raise AssertionError("x-only quotient collision")
        pair = tuple(transform(counted, point, undo, sign) for point in pair)
        witness = pair + triple
        total = None
        for point in witness:
            total = curve.add(total, point)
        assert total == alpha_g
        verified_group_relations += 1
        a = sum(labels[point][1] for point in pair) % order
        b = sum(labels[point][1] for point in triple) % order
        assert all(labels[point][0] == 0 for point in pair)
        assert all(labels[point][0] == 1 for point in triple)
        replay = curve.add(curve.mul(generator, a), curve.mul(target_seed, b))
        assert replay == alpha_g
        if not b:
            zero_target_coefficient += 1
            continue
        scalar = (alpha - a) * pow(b, -1, order) % order
        assert curve.mul(generator, scalar) == target_seed
        relation = {"point_witness": witness,
                    "known_G_coefficient_mod_r": a,
                    "target_Q_coefficient_mod_r": b,
                    "known_query_scalar_alpha": alpha,
                    "recovered_scalar": scalar,
                    "group_sum_and_seed_coefficient_replay_verified": True,
                    "independent_scalar_replay_verified": True}
        break
    return relation, {"triple_attempts_including_failed": attempts,
                      "quotient_hits": quotient_hits,
                      "verified_group_relations": verified_group_relations,
                      "zero_target_coefficient_hits": zero_target_coefficient,
                      "wall_seconds": time.perf_counter() - started,
                      "point_operations": counted.counts,
                      "status": "verified_dlp" if relation else "attempt_limit_no_relation"}


def main():
    reference_path = HERE / "runs" / "n53_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    canonicalize = XOnlyCycle(onb)
    rng = random.Random(QUERY_SEED)
    alpha = rng.randrange(1, order)
    workload = {"curve_id": reference["curve_id"],
                "target": target, "input_law": reference["workload"],
                "target_count": 1, "known_query_scalar_alpha": alpha,
                "triple_sample_seed": QUERY_SEED,
                "max_triple_attempts": MAX_TRIPLE_ATTEMPTS,
                "doubling_window": WINDOW,
                "seed_policy": "public G known log 1 and public target Q unknown log"}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report_path = HERE / "runs" / "n53_dyadic_five_sum_dlp.json"
    started = time.perf_counter()
    assert curve.onCurve(target) and curve.mul(target, order) is None
    lam = curves.frobeniusEigenvalue(curve, generator, order)
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target], WINDOW, lam, order)
    base_seconds = time.perf_counter() - started
    assert len(labels) == 4 * 53 * WINDOW == 13568
    g_base = [p for p in sorted(labels) if labels[p][0] == 0]
    q_base = [p for p in sorted(labels) if labels[p][0] == 1]
    g_reps = [p for p in sorted(representatives) if labels[p][0] == 0]
    assert len(g_base) == len(q_base) == 2 * 53 * WINDOW
    assert len(g_reps) == WINDOW
    index, build = build_g_pair_index(curve, g_base, g_reps, canonicalize)
    alpha_g = curve.mul(generator, alpha)
    relation, query = sample_triples(
        curve, index, q_base, labels, alpha_g, alpha, generator, target,
        order, canonicalize, rng, MAX_TRIPLE_ATTEMPTS)
    scalar = relation["recovered_scalar"] if relation else None
    if scalar is not None:
        assert scalar == reference["target_fixture_scalar"]
    elapsed = time.perf_counter() - started
    report = {
        "kind": "n53_target_seed_five_point_two_plus_three_quotient_dlp",
        "scope": "one public target; target-dependent base and index charged; random ordinary triple search with all failed attempts retained",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "target": target, "subgroup_order": str(order),
        "factor_base": {"construction": "signed-Frobenius closure of 64 doublings of G and Q",
                        "nominal_seed_columns": 2,
                        "doubling_window": WINDOW,
                        "actual_usable_points_B_before_folding": len(labels),
                        "signed_frobenius_columns": len(representatives),
                        "effective_unknown_log_columns_after_dyadic_labels": 1,
                        **digests},
        "frobenius_eigenvalue_mod_r": str(lam),
        "index_build": build,
        "query": query,
        "relation": relation,
        "recovered_scalar": scalar,
        "verified_single_target_dlp": scalar is not None,
        "online_wall_seconds": elapsed,
        "base_enumeration_and_target_preflight_seconds": base_seconds,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "calibrated_field_operation_total": None,
        "complete_work_log2": None,
        "paired_rho_online_speedup": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "dyadic_base_geometry.py", "quotient_pair_probe.py",
            "x_only_cycle.py", "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": query["status"],
                      "attempts": query["triple_attempts_including_failed"],
                      "quotient_hits": query["quotient_hits"],
                      "index_keys": build["quotient_keys"],
                      "index_build_seconds": build["build_seconds"],
                      "online_seconds": elapsed,
                      "verified_scalar": scalar}), flush=True)


if __name__ == "__main__":
    main()
