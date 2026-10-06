#!/usr/bin/env python3
"""Exact two-seed dyadic bases: G has known log, one seed is unknown."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import curves
import field
from dyadic_base_geometry import (enumerate_points, replay_sample_labels,
                                  select_seeds)
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
CONFIG = {53: {"window": 16, "seed": 20260929053, "proposal_id": "Q1017"},
          83: {"window": 1000, "seed": 20260929083, "proposal_id": "Q1018"}}


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def main(n):
    cfg = CONFIG[n]
    reference_path = HERE / "runs" / f"n{n}_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    assert reference["field_degree"] == n
    order = int(reference["subgroup_order"])
    cofactor = reference["cofactor"]
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    assert curve.mul(generator, order) is None
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, order)
    canonicalize = XOnlyCycle(onb)
    started = time.perf_counter()
    seeds, selected, stats = select_seeds(curve, onb, canonicalize,
                                          generator, cofactor, 2,
                                          cfg["window"], cfg["seed"])
    selection_seconds = time.perf_counter() - started
    labels, representatives, digests = enumerate_points(
        curve, onb, seeds, cfg["window"], eigenvalue, order)
    label_replays = replay_sample_labels(curve, seeds, cfg["window"],
                                         eigenvalue, order)
    enumeration_seconds = time.perf_counter() - started - selection_seconds
    assert len(selected) == len(representatives) == 2 * cfg["window"]
    points_per_seed = 2 * n * cfg["window"]
    b = len(labels)
    assert b == 2 * points_per_seed
    cross_pairs = points_per_seed**2
    quotient_generators = cross_pairs // (2 * n)
    assert quotient_generators * 2 * n == cross_pairs
    workload = {"curve_id": reference["curve_id"],
                "kind": "exact_two_seed_dyadic_window_base_enumeration",
                "seed": cfg["seed"], "seed_columns": 2,
                "doubling_window": cfg["window"], "cold": True}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "enumerated_two_seed_signed_frobenius_dyadic_base_geometry",
        "scope": "exact factor-base geometry and conditional pair work; no ordinary relation yield, solved seed log, target DLP, or online speedup",
        "proposal_id": cfg["proposal_id"], "candidate_id": None,
        "run_id": f"{cfg['proposal_id']}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "subgroup_order": str(order), "cofactor": cofactor,
        "generator_seed_index": 0, "generator_seed_log": 1,
        "other_seed_log": "unknown",
        "seed_selection": "one fixed G plus one deterministic uniform normal-coordinate x draw, rational lift, cofactor projection, and disjoint dyadic signed-Frobenius window",
        "seed_selection_stats": stats, "seed_points": seeds,
        "factor_base": {
            "nominal_seed_columns": 2, "doubling_window": cfg["window"],
            "geometric_selected_seed_inputs": 2,
            "dyadic_seed_orbits_before_sign_frobenius": 2 * cfg["window"],
            "actual_usable_points_B_before_folding": b,
            "signed_frobenius_columns": 2 * cfg["window"],
            "effective_unknown_log_columns_after_dyadic_labels": 1,
            "points_per_seed_column": points_per_seed,
            **digests,
        },
        "subgroup_membership_argument": "#E=cofactor*r, r prime; G and projected seed lie in E[r], and doubling, negation, Frobenius preserve E[r]",
        "frobenius_eigenvalue_mod_r": str(eigenvalue),
        "coefficient_rule": "point=sign*Frobenius^j([2]^power seed_i), coefficient=sign*lambda^j*2^power mod r",
        "sample_scalar_label_replays": label_replays,
        "conditional_direct_pair_screen": {
            "assumptions": ["uniform distinct cross-seed pair sums",
                            "one ordinary verified relation has nonzero unknown-seed coefficient",
                            "a complete quotient index and target descent are implementable"],
            "exact_cross_seed_unordered_pair_count": str(cross_pairs),
            "pair_complement_probes_per_hit_model_log2": math.log2(order / cross_pairs),
            "one_seed_log_relation_plus_one_target_pair_probes_model_log2": math.log2(
                2 * order / cross_pairs),
            "quotient_cross_seed_pair_generators": quotient_generators,
            "verified_complete_solve_work_log2": None,
            "ordinary_relation_yield_measured": None,
            "target_scalar_recovered": False,
        },
        "timing_seconds": {"selection": selection_seconds,
                           "enumeration_and_digest": enumeration_seconds},
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {"dyadic_base_geometry.py": sha(HERE / "dyadic_base_geometry.py")},
        "reference_sha256": sha(reference_path),
    }
    path = HERE / "runs" / f"n{n}_dyadic_two_seed_geometry.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"degree": n, "curve_id": report["curve_id"],
                      "B": b, "unknown_log_columns": 1,
                      "rank_plus_target_pair_probes_model_log2": report[
                          "conditional_direct_pair_screen"][
                              "one_seed_log_relation_plus_one_target_pair_probes_model_log2"],
                      "seconds": selection_seconds + enumeration_seconds}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    main(parser.parse_args().degree)
