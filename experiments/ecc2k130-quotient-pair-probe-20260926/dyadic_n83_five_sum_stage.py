#!/usr/bin/env python3
"""N83 two-G quotient index and bounded batched three-Q ordinary queries."""

import hashlib
import json
import platform
import random
import resource
import statistics
import time
from pathlib import Path

import curves
import field
from batch_x_only import batch_add_fixed_left
from compare_batch_x_only import CountingField
from dyadic_base_geometry import enumerate_points
from dyadic_five_sum_batch import batch_add_pairs
from dyadic_n53_five_sum_dlp import build_g_pair_index
from perf_probe import sha
from quotient_pair_probe import transform
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1025"
WINDOW = 32
QUERY_SEED = 202609290583
BLOCK_SIZE = 4096
BATCH_SIZE = 512
BLOCKS = 3


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def peak_rss_bytes():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if platform.system() == "Darwin" else rss * 1024


def replay_hit(curve, index, complement, triple, key, shift, canonicalize,
               labels, generator, target_seed, alpha_g, alpha, order):
    representative, pair = index[key]
    undo = (-shift) % 83
    aligned = transform(curve, representative, undo, 1)
    if aligned == complement:
        sign = 1
    elif curve.neg(aligned) == complement:
        sign = -1
    else:
        raise AssertionError("x-only quotient collision")
    pair = tuple(transform(curve, point, undo, sign) for point in pair)
    witness = pair + triple
    total = None
    for point in witness:
        total = curve.add(total, point)
    assert total == alpha_g
    a = sum(labels[point][1] for point in pair) % order
    b = sum(labels[point][1] for point in triple) % order
    assert all(labels[point][0] == 0 for point in pair)
    assert all(labels[point][0] == 1 for point in triple)
    assert curve.add(curve.mul(generator, a),
                     curve.mul(target_seed, b)) == alpha_g
    scalar = None
    if alpha is not None and b:
        scalar = (alpha - a) * pow(b, -1, order) % order
        assert curve.mul(generator, scalar) == target_seed
    return {"point_witness": witness, "known_G_coefficient_mod_r": a,
            "target_Q_coefficient_mod_r": b,
            "recovered_scalar": scalar,
            "group_and_seed_coefficient_replay_verified": True,
            "independent_scalar_replay_verified": scalar is not None}


def run_block(onb, index, q_base, labels, generator, target_seed,
              alpha_g, alpha, order, canonicalize, rng):
    counting_field = CountingField(onb)
    curve = curves.Curve(counting_field)
    canonical_counts = {}
    started = time.perf_counter_ns()
    attempts = 0
    quotient_hits = 0
    verified_relations = []
    for _ in range(BLOCK_SIZE // BATCH_SIZE):
        triples = [tuple(q_base[rng.randrange(len(q_base))] for _ in range(3))
                   for _ in range(BATCH_SIZE)]
        first = batch_add_pairs(curve, [(a, b, ) for a, b, _ in triples])
        sums = batch_add_pairs(curve, list(zip(first, (t[2] for t in triples))))
        complements = batch_add_fixed_left(
            curve, alpha_g, [curve.neg(total) for total in sums])
        for triple, complement in zip(triples, complements):
            attempts += 1
            key, shift = canonicalize.key_and_shift(curve, complement,
                                                    canonical_counts)
            if key not in index:
                continue
            quotient_hits += 1
            relation = replay_hit(curve, index, complement, triple, key,
                                  shift, canonicalize, labels, generator,
                                  target_seed, alpha_g, alpha, order)
            verified_relations.append({"attempt": attempts, "relation": relation})
    elapsed = time.perf_counter_ns() - started
    assert attempts == BLOCK_SIZE
    return {"status": "bounded_ordinary_triple_queries",
            "attempts_including_failed": attempts,
            "quotient_hits": quotient_hits,
            "verified_relations": verified_relations,
            "batch_size": BATCH_SIZE,
            "batches": BLOCK_SIZE // BATCH_SIZE,
            "wall_ns": elapsed,
            "field_api_operations": dict(counting_field.counts),
            "canonical_operations": canonical_counts}


def main():
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target_seed = tuple(reference["workload"]["target"])
    assert curve.mul(target_seed, order) is None
    lam = curves.frobeniusEigenvalue(curve, generator, order)
    assert pow(lam, 83, order) == 1
    assert all(pow(lam, j, order) not in (1, order - 1) for j in range(1, 83))
    canonicalize = XOnlyCycle(onb)
    started = time.perf_counter()
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target_seed], WINDOW, lam, order)
    base_seconds = time.perf_counter() - started
    assert len(labels) == 4 * 83 * WINDOW == 10624
    g_base = [p for p in sorted(labels) if labels[p][0] == 0]
    q_base = [p for p in sorted(labels) if labels[p][0] == 1]
    g_reps = [p for p in sorted(representatives) if labels[p][0] == 0]
    index, build = build_g_pair_index(curve, g_base, g_reps, canonicalize)
    assert -1 in index
    exact_support = 1 + (len(index) - 1) * 2 * 83
    rng = random.Random(QUERY_SEED)
    alpha = rng.randrange(1, order)
    alpha_g = curve.mul(generator, alpha)
    workload = {"curve_id": reference["curve_id"], "target": target_seed,
                "input_law": reference["workload"], "target_count": 1,
                "known_query_scalar_alpha": alpha,
                "triple_sample_seed": QUERY_SEED,
                "doubling_window": WINDOW,
                "blocks": BLOCKS, "block_size": BLOCK_SIZE,
                "batch_size": BATCH_SIZE,
                "input_law_triples": "independent uniform point draws with replacement from target-seed signed-Frobenius base"}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    blocks = [run_block(onb, index, q_base, labels, generator, target_seed,
                        alpha_g, alpha, order, canonicalize, rng)
              for _ in range(BLOCKS)]
    first_key = next(key for key in index if key != -1)
    representative, pair = index[first_key]
    triple = tuple(q_base[:3])
    planted_target = curve.add(representative,
                               curve.add(curve.add(triple[0], triple[1]), triple[2]))
    planted_complement = curve.add(planted_target,
                                   curve.neg(curve.add(curve.add(triple[0], triple[1]), triple[2])))
    planted_key, planted_shift = canonicalize.key_and_shift(curve, planted_complement)
    assert planted_key == first_key
    planted = replay_hit(curve, index, planted_complement, triple, planted_key,
                         planted_shift, canonicalize, labels, generator,
                         target_seed, planted_target, None, order)
    report = {
        "kind": "n83_target_seed_five_point_two_plus_three_batched_stage",
        "scope": "complete two-G quotient index, three bounded ordinary triple-sampling blocks, planted five-point control; no measured natural relation yield or DLP",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "target_seed": target_seed,
        "subgroup_order": str(order),
        "factor_base": {"construction": "signed-Frobenius closure of 32 doublings of G and public Q",
                        "nominal_seed_columns": 2,
                        "doubling_window": WINDOW,
                        "actual_usable_points_B_before_folding": len(labels),
                        "signed_frobenius_columns": len(representatives),
                        "effective_unknown_log_columns_after_dyadic_labels": 1,
                        **digests},
        "frobenius_eigenvalue_mod_r": str(lam),
        "base_enumeration_seconds": base_seconds,
        "index_build": build,
        "exact_two_G_pair_sum_support": exact_support,
        "ordinary_blocks": blocks,
        "median_block_wall_ns": int(statistics.median(row["wall_ns"] for row in blocks)),
        "planted_positive_control": planted,
        "peak_process_rss_bytes": peak_rss_bytes(),
        "ordinary_relation_yield_measured": None,
        "verified_single_target_dlp": any(
            hit["relation"]["recovered_scalar"] is not None
            for block in blocks for hit in block["verified_relations"]),
        "calibrated_complete_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "dyadic_base_geometry.py", "dyadic_five_sum_batch.py",
            "dyadic_n53_five_sum_dlp.py", "batch_x_only.py",
            "compare_batch_x_only.py", "x_only_cycle.py", "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
    }
    output = HERE / "runs" / "n83_dyadic_five_sum_stage.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": report["curve_id"],
                      "B": len(labels), "index_keys": len(index),
                      "exact_pair_sum_support": exact_support,
                      "build_seconds": build["build_seconds"],
                      "ordinary_attempts": BLOCKS * BLOCK_SIZE,
                      "ordinary_hits": sum(row["quotient_hits"] for row in blocks),
                      "median_block_ms": report["median_block_wall_ns"] / 1e6,
                      "planted_replay": planted["group_and_seed_coefficient_replay_verified"]}))


if __name__ == "__main__":
    main()
