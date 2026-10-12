#!/usr/bin/env python3
"""Enumerate a signed-Frobenius dyadic-window factor base exactly.

The generator is the first seed and has known logarithm 1. Other seeds are
selected by public x coordinates and cofactor projection; their logarithms
are not used. Each seed contributes a short [2]^k window, then both signs
and all Frobenius images. Labels retain the scalar relating every point to
its seed, giving fewer unknown log columns than sign/Frobenius folding alone.
"""

import argparse
import hashlib
import json
import math
import random
import resource
import time
from pathlib import Path

import curves
import field
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
CONFIG = {53: {"seed_columns": 8, "doubling_window": 4, "seed": 20260928053,
               "proposal_id": "Q1014"},
          83: {"seed_columns": 100, "doubling_window": 20,
               "seed": 20260928083, "proposal_id": "Q1013"}}


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def window(curve, point, length):
    values = []
    for _ in range(length):
        if point is None:
            raise AssertionError("dyadic window reached identity")
        values.append(point)
        point = curve.dbl(point)
    return values


def select_seeds(curve, onb, canonicalize, generator, cofactor, count, length, seed):
    rng = random.Random(seed)
    accepted = []
    occupied = set()
    attempted_x = 0
    rational_x = 0
    rejected_overlap = 0
    for candidate in [generator]:
        keys = [canonicalize.key_and_shift(curve, point)[0]
                for point in window(curve, candidate, length)]
        assert len(set(keys)) == length and -1 not in keys
        accepted.append(candidate)
        occupied.update(keys)
    while len(accepted) < count:
        attempted_x += 1
        x = onb.fromCoords(rng.getrandbits(onb.m))
        raw = curve.pointFromX(x)
        if raw is None:
            continue
        rational_x += 1
        candidate = curve.mul(raw, cofactor)
        if candidate is None:
            continue
        keys = [canonicalize.key_and_shift(curve, point)[0]
                for point in window(curve, candidate, length)]
        if len(set(keys)) != length or occupied.intersection(keys):
            rejected_overlap += 1
            continue
        occupied.update(keys)
        accepted.append(candidate)
    return accepted, occupied, {"attempted_x": attempted_x,
                                "rational_x": rational_x,
                                "rejected_overlap": rejected_overlap}


def enumerate_points(curve, onb, seeds, length, eigenvalue, order):
    labels = {}
    orbit_representatives = set()
    for seed_index, seed in enumerate(seeds):
        for power, start in enumerate(window(curve, seed, length)):
            coefficient = pow(2, power, order)
            orbit_representatives.add(start)
            point = start
            for _ in range(onb.m):
                negative = curve.neg(point)
                assert point != negative and point is not None
                for signed_point, signed_coefficient in (
                        (point, coefficient),
                        (negative, (-coefficient) % order)):
                    if signed_point in labels:
                        raise AssertionError("point collision across seed windows")
                    labels[signed_point] = (seed_index, signed_coefficient)
                point = curve.frob(point)
                coefficient = coefficient * eigenvalue % order
            assert point == start
    encoded_points = json.dumps(sorted(labels), separators=(",", ":")).encode()
    encoded_labels = frozen(sorted((point[0], point[1], label[0], label[1])
                                   for point, label in labels.items()))
    return labels, orbit_representatives, {
        "enumerated_set_sha256": hashlib.sha256(encoded_points).hexdigest(),
        "point_coefficient_label_sha256": hashlib.sha256(encoded_labels).hexdigest(),
        "encoded_point_set_bytes": len(encoded_points),
        "encoded_point_label_bytes": len(encoded_labels),
    }


def replay_sample_labels(curve, seeds, length, eigenvalue, order):
    checks = []
    for seed_index in sorted(set((0, 1, len(seeds) // 2, len(seeds) - 1))):
        seed = seeds[seed_index]
        for power in sorted(set((0, length // 2, length - 1))):
            for shift in (0, 1, curve.f.m // 2):
                point = window(curve, seed, power + 1)[-1]
                point = curve.frob(point, shift)
                coefficient = pow(2, power, order) * pow(eigenvalue, shift, order) % order
                assert curve.mul(seed, coefficient) == point
                checks.append([seed_index, power, shift, coefficient,
                               point[0], point[1]])
    return checks


def main(degree):
    cfg = CONFIG[degree]
    reference_path = HERE / "runs" / f"n{degree}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    assert reference["field_degree"] == degree
    order = int(reference["subgroup_order"])
    cofactor = reference["cofactor"]
    assert curves.curveOrder(degree) == cofactor * order
    onb = field.Onb(degree)
    curve = curves.Curve(onb)
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    assert curve.onCurve(generator) and curve.mul(generator, order) is None
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, order)
    assert curve.mul(generator, eigenvalue) == curve.frob(generator)
    canonicalize = XOnlyCycle(onb)
    started = time.perf_counter()
    seeds, selected_keys, selection = select_seeds(
        curve, onb, canonicalize, generator, cofactor,
        cfg["seed_columns"], cfg["doubling_window"], cfg["seed"])
    selection_seconds = time.perf_counter() - started
    for point in seeds[:min(16, len(seeds))]:
        assert curve.onCurve(point) and curve.mul(point, order) is None
    labels, representatives, digests = enumerate_points(
        curve, onb, seeds, cfg["doubling_window"], eigenvalue, order)
    sample_label_replays = replay_sample_labels(
        curve, seeds, cfg["doubling_window"], eigenvalue, order)
    enumeration_seconds = time.perf_counter() - started - selection_seconds
    b = len(labels)
    k = cfg["seed_columns"]
    length = cfg["doubling_window"]
    assert len(selected_keys) == len(representatives) == k * length
    assert b == 2 * degree * k * length
    # Exclude pairs drawn from the same seed column in this optimistic model.
    per_seed = 2 * degree * length
    cross_seed_pairs = math.comb(k, 2) * per_seed**2
    assert cross_seed_pairs == math.comb(b, 2) - k * math.comb(per_seed, 2)
    rank_rows = k - 1  # generator seed log is 1
    probes_per_hit = order / cross_seed_pairs
    modeled_rank_and_target_probes = (rank_rows + 1) * probes_per_hit
    workload = {"curve_id": reference["curve_id"],
                "kind": "exact_dyadic_window_base_enumeration",
                "seed": cfg["seed"], "seed_columns": k,
                "doubling_window": length, "cold": True}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "kind": "enumerated_signed_frobenius_dyadic_window_base_geometry",
        "scope": "exact factor-base geometry and conditional direct-pair work only; no ordinary relation yield, factor logs, target DLP, or online speedup",
        "proposal_id": cfg["proposal_id"], "candidate_id": None,
        "run_id": f"{cfg['proposal_id']}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "subgroup_order": str(order), "cofactor": cofactor,
        "generator_seed_index": 0, "generator_seed_log": 1,
        "other_seed_logs": "unknown",
        "seed_selection": "deterministic uniform normal-coordinate x draw, rational lift, cofactor projection, reject dyadic signed-Frobenius overlap",
        "seed_selection_stats": selection,
        "seed_points": seeds,
        "factor_base": {
            "nominal_seed_columns": k, "doubling_window": length,
            "seed_points_before_closure": k,
            "dyadic_seed_orbits_before_sign_frobenius": k * length,
            "geometric_selected_seed_inputs": k,
            "actual_usable_points_B_before_folding": b,
            "signed_frobenius_columns": k * length,
            "effective_unknown_log_columns_after_dyadic_labels": rank_rows,
            "points_per_seed_column": per_seed,
            **digests,
        },
        "subgroup_membership_argument": "#E=cofactor*r, r prime; every selected seed is a cofactor projection or G, and doubling, negation, and Frobenius preserve E[r]; 16 seeds checked by [r]",
        "frobenius_eigenvalue_mod_r": str(eigenvalue),
        "coefficient_rule": "point=sign*Frobenius^j([2]^power seed_i), coefficient=sign*lambda^j*2^power mod r",
        "sample_scalar_label_replays": sample_label_replays,
        "conditional_direct_pair_screen": {
            "assumptions": ["uniform distinct cross-seed pair sums",
                            "every ordinary hit adds one independent unknown-log row",
                            "a complete quotient index and target descent are implementable"],
            "exact_cross_seed_unordered_pair_count": str(cross_seed_pairs),
            "pair_complement_probes_per_hit_model_log2": math.log2(probes_per_hit),
            "rank_rows_plus_one_target": rank_rows + 1,
            "rank_plus_target_pair_probes_model_log2": math.log2(
                modeled_rank_and_target_probes),
            "quotient_cross_seed_pair_generators": math.comb(k, 2) * per_seed**2 // (2 * degree),
            "verified_complete_solve_work_log2": None,
            "ordinary_relation_yield_measured": None,
            "factor_log_rank_measured": None,
            "target_scalar_recovered": False,
        },
        "timing_seconds": {"selection": selection_seconds,
                           "enumeration_and_digest": enumeration_seconds},
        "peak_process_rss_bytes": peak_rss,
        "source_sha256": sha(Path(__file__)),
        "reference_sha256": sha(reference_path),
    }
    path = HERE / "runs" / f"n{degree}_dyadic_base_geometry.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"degree": degree, "curve_id": report["curve_id"],
                      "B": b, "signed_frobenius_columns": k * length,
                      "unknown_log_columns": rank_rows,
                      "rank_plus_target_pair_probes_model_log2": report[
                          "conditional_direct_pair_screen"][
                              "rank_plus_target_pair_probes_model_log2"],
                      "seconds": selection_seconds + enumeration_seconds}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    main(parser.parse_args().degree)
