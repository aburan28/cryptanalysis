#!/usr/bin/env python3
"""Complete ordinary-target four-summand search on the dyadic n53 base."""

import hashlib
import json
import time
from pathlib import Path

import curves
import field
from batch_x_only import batch_add_fixed_left
from dyadic_base_geometry import CONFIG, enumerate_points, select_seeds
from perf_probe import sha
from quotient_pair_probe import CountedCurve, transform
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
DEGREE = 53


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def build_cross_seed_index(curve, base, representatives, labels, canonicalize):
    counted = CountedCurve(curve)
    index = {}
    generators = 0
    started = time.perf_counter()
    for left in sorted(representatives):
        seed = labels[left][0]
        for right in base:
            if labels[right][0] == seed:
                continue
            generators += 1
            total = counted.add(left, right)
            key, shift = canonicalize.key_and_shift(counted, total)
            if key not in index:
                pair = (transform(counted, left, shift, 1),
                        transform(counted, right, shift, 1))
                representative = curve.add(*pair)
                assert canonicalize.key_and_shift(curve, representative) == (key, 0)
                index[key] = (representative, pair)
    elapsed = time.perf_counter() - started
    return index, {"pair_generators": generators, "quotient_keys": len(index),
                   "build_seconds": elapsed, "point_operations": counted.counts,
                   "index_sha256": hashlib.sha256(frozen(sorted(index.items()))).hexdigest()}


def extract_first(curve, index, target, canonicalize):
    """Search the complete index; the scalar is deliberately absent here."""
    counted = CountedCurve(curve)
    started = time.perf_counter()
    lookups = 0
    for representative, pair in index.values():
        point = representative
        negatives = []
        variants = []
        for shift in range(DEGREE):
            for sign in (1, -1):
                candidate = point if sign == 1 else counted.neg(point)
                negatives.append(counted.neg(candidate))
                variants.append((shift, sign))
            point = counted.frob(point)
        complements = batch_add_fixed_left(curve, target, negatives)
        counted.counts["add"] += len(complements)
        for complement, (shift, sign) in zip(complements, variants):
            lookups += 1
            key, comp_shift = canonicalize.key_and_shift(counted, complement)
            match = index.get(key)
            if match is None:
                continue
            other_representative, other_pair = match
            undo = (-comp_shift) % DEGREE
            aligned = transform(counted, other_representative, undo, 1)
            if aligned == complement:
                other_sign = 1
            elif counted.neg(aligned) == complement:
                other_sign = -1
            else:
                raise AssertionError("x-only orbit collision")
            first = tuple(transform(counted, p, shift, sign) for p in pair)
            second = tuple(transform(counted, p, undo, other_sign)
                           for p in other_pair)
            witness = first + second
            total = None
            for p in witness:
                total = curve.add(total, p)
            assert total == target
            return witness, {"status": "verified_relation",
                             "lookups_including_failed": lookups,
                             "wall_seconds": time.perf_counter() - started,
                             "point_operations": counted.counts}
    return None, {"status": "complete_index_miss",
                  "lookups_including_failed": lookups,
                  "wall_seconds": time.perf_counter() - started,
                  "point_operations": counted.counts}


def main():
    reference_path = HERE / "runs" / "n53_perf_prefix.json"
    geometry_path = HERE / "runs" / "n53_dyadic_base_geometry.json"
    reference = json.loads(reference_path.read_text())
    geometry = json.loads(geometry_path.read_text())
    assert geometry["curve_id"] == reference["curve_id"]
    cfg = CONFIG[DEGREE]
    onb = field.Onb(DEGREE)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    eigenvalue = int(geometry["frobenius_eigenvalue_mod_r"])
    assert curve.mul(generator, eigenvalue) == curve.frob(generator)
    canonicalize = XOnlyCycle(onb)
    seeds, _, _ = select_seeds(curve, onb, canonicalize, generator,
                               reference["cofactor"], cfg["seed_columns"],
                               cfg["doubling_window"], cfg["seed"])
    assert seeds == [tuple(p) for p in geometry["seed_points"]]
    labels, representatives, digests = enumerate_points(
        curve, onb, seeds, cfg["doubling_window"], eigenvalue, order)
    assert digests["enumerated_set_sha256"] == geometry["factor_base"][
        "enumerated_set_sha256"]
    assert digests["point_coefficient_label_sha256"] == geometry["factor_base"][
        "point_coefficient_label_sha256"]
    base = sorted(labels)
    index, build = build_cross_seed_index(
        curve, base, representatives, labels, canonicalize)
    assert build["pair_generators"] == 2 * geometry[
        "conditional_direct_pair_screen"]["quotient_cross_seed_pair_generators"]
    target = tuple(reference["workload"]["target"])
    fixture_scalar = reference["target_fixture_scalar"]
    assert curve.mul(generator, fixture_scalar) == target
    witness, query = extract_first(curve, index, target, canonicalize)
    relation = None
    if witness is not None:
        vector = [0] * cfg["seed_columns"]
        for point in witness:
            seed, coefficient = labels[point]
            vector[seed] = (vector[seed] + coefficient) % order
        scalar_replay = None
        for seed_index, coefficient in enumerate(vector):
            if coefficient:
                scalar_replay = curve.add(
                    scalar_replay, curve.mul(seeds[seed_index], coefficient))
        assert scalar_replay == target
        relation = {"point_witness": witness,
                    "seed_coefficient_vector_mod_r": vector,
                    "unknown_seed_coefficients_nonzero": any(vector[1:]),
                    "known_scalar_rhs_after_generator_seed":
                        (fixture_scalar - vector[0]) % order,
                    "fixture_scalar_validation_only": fixture_scalar,
                    "group_sum_verified": True}
    workload = {"curve_id": reference["curve_id"],
                "target": target, "input_law": reference["workload"],
                "base_geometry_sha256": sha(geometry_path),
                "complete_cross_seed_index": True}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "n53_dyadic_base_ordinary_relation_search",
        "scope": "one frozen ordinary public target; exact complete cross-seed quotient index; no factor logs, matrix, target DLP, or n83 relation claim",
        "proposal_id": "Q1015", "candidate_id": None,
        "run_id": f"Q1015W{workload_id}R1", "workload_id": workload_id,
        "workload": workload, "curve_id": reference["curve_id"],
        "isogeny": "none", "target": target,
        "factor_base": geometry["factor_base"],
        "index_build": build, "ordinary_query": query,
        "relation": relation,
        "verified_single_target_dlp": False,
        "verified_complete_solve_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "dyadic_base_geometry.py", "batch_x_only.py", "x_only_cycle.py",
            "cycle_canonical.py", "curves.py", "field.py")},
        "geometry_receipt_sha256": sha(geometry_path),
        "reference_sha256": sha(reference_path),
    }
    path = HERE / "runs" / "n53_dyadic_ordinary_relation.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": query["status"],
                      "lookups": query["lookups_including_failed"],
                      "query_seconds": query["wall_seconds"],
                      "quotient_keys": build["quotient_keys"],
                      "unknown_coefficients_nonzero": relation and relation[
                          "unknown_seed_coefficients_nonzero"]}))


if __name__ == "__main__":
    main()
