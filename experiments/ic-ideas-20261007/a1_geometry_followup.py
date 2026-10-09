#!/usr/bin/env python3
"""Small-field geometry control for norm-bounded multiplier closure.

This compares exact pair/triple coverage at a fixed seed-base log dimension.
It is not an N53 relation-yield or solving-time measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path

from sage.all import GF, PolynomialRing, ZZ, set_random_seed

from sage_probes import (bits, curve, field, frobenius_orbits, multiplier_orbit,
                         norm_multipliers, normal_basis, point_key, wilson95)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def coords(P):
    return tuple(point_key(P)) if not P.is_zero() else None


def pair_sums(points):
    result = set()
    for i, P in enumerate(points):
        for Q in points[i:]:
            value = coords(P+Q)
            if value is not None:
                result.add(value)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed-orbits", type=int, default=1)
    parser.add_argument("--targets", type=int, default=16)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve prior receipt")
    if args.seed_orbits < 1 or args.targets < 1:
        parser.error("positive seed-orbits and targets required")
    started = time.perf_counter_ns()
    set_random_seed(20261008)
    K, modulus = field(23)
    E = curve(K)
    group_order = int(E.order())
    r = int(max(p for p, _ in ZZ(group_order).factor()))
    cofactor = group_order // r
    G = E(0)
    for _ in range(100):
        G = cofactor*E.random_point()
        if not G.is_zero() and (r*G).is_zero():
            break
    assert not G.is_zero()
    tauG = E(G[0]**2, G[1]**2)
    R = PolynomialRing(GF(r), "l")
    l = R.gen()
    roots = [int(root) for root, _ in (l*l+l+2).roots()]
    lam = next(value for value in roots if value*G == tauG)
    classes = sorted({multiplier_orbit((a+b*lam) % r, lam, 23, r)
                      for a, b, _ in norm_multipliers(16)})
    normal = normal_basis(K)
    xs = {normal[i]+normal[j] for i in range(23) for j in range(i+1, 23)}
    seed_orbits = []
    for orbit in frobenius_orbits(K, xs):
        points = {}
        for x in orbit:
            for P in E.lift_x(x, all=True):
                if not P.is_zero() and (r*P).is_zero():
                    points[coords(P)] = P
        if points:
            seed_orbits.append(points)
        if len(seed_orbits) == args.seed_orbits:
            break
    if len(seed_orbits) != args.seed_orbits:
        raise ValueError("insufficient usable seed orbits")
    original = {key: P for orbit in seed_orbits for key, P in orbit.items()}
    representatives = [next(iter(orbit.values())) for orbit in seed_orbits]
    seed_transport = {}
    for index, representative in enumerate(representatives):
        for power in range(23):
            coefficient = pow(lam, power, r)
            image = coefficient*representative
            seed_transport[coords(image)] = (index, coefficient)
            seed_transport[coords(-image)] = (index, (-coefficient) % r)
    assert set(original).issubset(seed_transport)
    closure = {}
    closure_transport = {}
    for scalar in classes:
        for key, P in original.items():
            image = scalar*P
            image_key = coords(image)
            index, coefficient = seed_transport[key]
            transported = (scalar*coefficient) % r
            assert transported*representatives[index] == image
            closure[image_key] = image
            closure_transport.setdefault(image_key, (index, transported))
    assert set(original).issubset(closure)
    rng = random.Random(20261008)
    targets = [rng.randrange(1, r)*G for _ in range(args.targets)]
    cells = []
    for name, points in (("seed", original), ("multiplier_closure", closure)):
        values = list(points.values())
        sums = pair_sums(values)
        status = []
        for T in targets:
            m2 = coords(T) in sums
            m3 = any(coords(T-P) in sums for P in values)
            status.append({"m2": m2, "m3": m3})
        cells.append({
            "base": name, "actual_usable_B": len(values),
            "geometric_folded_columns": len(frobenius_orbits(K, {P[0] for P in values})),
            "independent_log_columns_after_known_transport": args.seed_orbits,
            "distinct_pair_sums": len(sums), "m2_hits": sum(s["m2"] for s in status),
            "m3_hits": sum(s["m3"] for s in status), "target_statuses": status,
            "m2_wilson95": wilson95(sum(s["m2"] for s in status), len(status)),
            "m3_wilson95": wilson95(sum(s["m3"] for s in status), len(status)),
            "point_set_sha256": hashlib.sha256(json.dumps(sorted(points),
                                                  separators=(",", ":")).encode()).hexdigest(),
        })
    answer = {
        "schema_version": 1, "proposal_id": "A1", "candidate_id": None,
        "run_id": None, "field_degree": 23, "field_modulus_bits": modulus,
        "curve_model": "y^2+xy=x^3+1", "subgroup_order": r,
        "cofactor": cofactor, "generator": point_key(G),
        "frobenius_scalar": lam, "norm_bound": 16,
        "classes_after_sign_frobenius": len(classes), "class_scalars": classes,
        "seed_transport_verified_points": len(seed_transport),
        "closure_transport_verified_points": len(closure_transport),
        "target_points": [point_key(T) for T in targets], "cells": cells,
        "stage_wall_ns": time.perf_counter_ns()-started,
        "source_sha256": sha(Path(__file__)),
        "sage_probes_sha256": sha(Path(__file__).with_name("sage_probes.py")),
        "scope": "N23 exact finite-base coverage at fixed known log dimension; no N53 relation-rank or F4 solve",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"cells": [{k: cell[k] for k in (
        "base", "actual_usable_B", "m2_hits", "m3_hits")}
        for cell in cells], "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
