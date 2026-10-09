#!/usr/bin/env python3
"""N23 natural-query comparison at equal 230-point geometry.

Five independent Frobenius seed orbits and one seed orbit closed under five
norm-bounded multiplier classes each give 230 usable points. Uniform known-
scalar queries are paired; verified triple witnesses become weighted relation
rows for the independent seed logs.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import random
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing, ZZ, matrix, set_random_seed, vector

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007"
sys.path.insert(0, str(PRIOR))
from sage_probes import (bits, curve, field, frobenius_orbits, multiplier_orbit,
                         norm_multipliers, normal_basis, point_key, wilson95)


def coords(P):
    return tuple(point_key(P)) if not P.is_zero() else None


def construct(K, E, r, lam):
    normal = normal_basis(K)
    xs = {normal[i] + normal[j] for i, j in itertools.combinations(range(23), 2)}
    seed_orbits = []
    for orbit in frobenius_orbits(K, xs):
        points = {}
        for x in orbit:
            for P in E.lift_x(x, all=True):
                if not P.is_zero() and (r * P).is_zero():
                    points[coords(P)] = P
        if points:
            seed_orbits.append(points)
        if len(seed_orbits) == 5:
            break
    assert len(seed_orbits) == 5
    reps = [next(iter(orbit.values())) for orbit in seed_orbits]
    seed = {key: P for orbit in seed_orbits for key, P in orbit.items()}
    transport = {}
    for index, rep in enumerate(reps):
        for power in range(23):
            coeff = pow(lam, power, r)
            P = coeff * rep
            transport[coords(P)] = (index, coeff)
            transport[coords(-P)] = (index, (-coeff) % r)
    assert all(key in transport for key in seed)
    classes = sorted({multiplier_orbit((a + b * lam) % r, lam, 23, r)
                      for a, b, _ in norm_multipliers(16)})
    assert 1 in classes and len(classes) >= 5
    selected = [1] + [value for value in classes if value != 1][:4]
    one_seed = seed_orbits[0]
    closure, closure_labels = {}, {}
    for scalar in selected:
        for key, P in one_seed.items():
            Q = scalar * P
            qkey = coords(Q)
            _, coefficient = transport[key]
            closure[qkey] = Q
            closure_labels[qkey] = (0, scalar * coefficient % r)
    assert len(seed) == len(closure) == 230
    assert all(coefficient * reps[index] == P
               for key, P in seed.items()
               for index, coefficient in [transport[key]])
    assert all(coefficient * reps[0] == P
               for key, P in closure.items()
               for _, coefficient in [closure_labels[key]])
    return selected, [("five_seed_orbits", seed, transport, reps),
                      ("one_seed_five_class_closure", closure,
                       closure_labels, reps[:1])]


def rank(rows, modulus, columns):
    if not rows:
        return 0
    return int(matrix(GF(modulus), rows, ncols=columns).rank())


def one_base(name, points, labels, reps, queries, r):
    values = list(points.values())
    keys = [coords(P) for P in values]
    columns = len(reps)
    pair = {}
    for i, P in enumerate(values):
        for j in range(i, len(values)):
            key = coords(P + values[j])
            if key is not None:
                pair.setdefault(key, (i, j))
    rows, rhs, statuses, rank_growth = [], [], [], []
    for target, target_scalar in queries:
        witness = None
        for k, P in enumerate(values):
            pair_key = coords(target - P)
            if pair_key in pair:
                i, j = pair[pair_key]
                witness = (i, j, k)
                break
        if witness is not None:
            assert sum((values[i] for i in witness), values[0].curve()(0)) == target
            row = [0] * columns
            for i in witness:
                column, coefficient = labels[keys[i]]
                row[column] = (row[column] + coefficient) % r
            rows.append(row)
            rhs.append(target_scalar)
            assert sum((row[i] * reps[i] for i in range(columns)),
                       reps[0].curve()(0)) == target
        statuses.append(witness is not None)
        rank_growth.append(rank(rows, r, columns))
    final_rank = rank_growth[-1]
    solved_logs = None
    replay = None
    if final_rank == columns:
        F = GF(r)
        solution = matrix(F, rows).solve_right(vector(F, rhs))
        solved_logs = [int(value) for value in solution]
        replay = all(sum(row[i] * solved_logs[i] for i in range(columns)) % r
                     == scalar for row, scalar in zip(rows, rhs))
    return {"base": name, "actual_usable_B": len(values),
            "folded_geometric_columns": len(values) // 46,
            "independent_log_columns": columns,
            "pair_index_entries": len(pair),
            "query_count": len(queries), "verified_triple_hits": sum(statuses),
            "target_hit_statuses": statuses,
            "hit_wilson95": wilson95(sum(statuses), len(statuses)),
            "relation_rank": final_rank,
            "first_full_rank_query": next((i + 1 for i, value in enumerate(rank_growth)
                                            if value == columns), None),
            "rank_growth": rank_growth, "solved_logs": solved_logs,
            "relation_rhs_replay": replay,
            "point_set_sha256": hashlib.sha256(json.dumps(sorted(points),
                                                  separators=(",", ":")).encode()).hexdigest()}


def main():
    out = HERE / "a1_equal_geometry.json"
    if out.exists():
        raise FileExistsError(out)
    set_random_seed(20261008)
    K, modulus = field(23)
    E = curve(K)
    order = int(E.order())
    r = int(max(p for p, _ in ZZ(order).factor()))
    assert ZZ(r).is_prime()
    cofactor = order // r
    G = E(0)
    for _ in range(100):
        G = cofactor * E.random_point()
        if not G.is_zero() and (r * G).is_zero():
            break
    assert not G.is_zero()
    tauG = E(G[0] ** 2, G[1] ** 2)
    R = PolynomialRing(GF(r), "l")
    l = R.gen()
    lam = next(int(root) for root, _ in (l*l+l+2).roots()
               if int(root) * G == tauG)
    selected, bases = construct(K, E, r, lam)
    rng = random.Random(20261008)
    queries = [(scalar * G, scalar) for scalar in
               (rng.randrange(1, r) for _ in range(256))]
    cells = [one_base(name, points, labels, reps, queries, r)
             for name, points, labels, reps in bases]
    # Independently replay every recovered representative log on G.
    for cell, (_, _, _, reps) in zip(cells, bases):
        if cell["solved_logs"] is not None:
            cell["scalar_replay_on_G"] = all(log * G == P for log, P in
                                              zip(cell["solved_logs"], reps))
        else:
            cell["scalar_replay_on_G"] = None
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "field_degree": 23, "field_modulus_bits": modulus,
              "curve_model": "y^2+xy=x^3+1", "subgroup_order": r,
              "cofactor": cofactor, "generator": point_key(G),
              "frobenius_scalar": lam, "norm_bound": 16,
              "selected_multiplier_classes": selected,
              "query_law": "256 uniform nonzero known-scalar subgroup points, seed 20261008",
              "target_points_sha256": hashlib.sha256(json.dumps(
                  [point_key(Q) for Q, _ in queries],
                  separators=(",", ":")).encode()).hexdigest(),
              "cells": cells,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"cells": [(cell["base"], cell["verified_triple_hits"],
                                  cell["relation_rank"]) for cell in cells]}))


if __name__ == "__main__":
    main()
