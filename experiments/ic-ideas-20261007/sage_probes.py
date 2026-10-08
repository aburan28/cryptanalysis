#!/usr/bin/env python3
"""Exact small-field probes for G1, G2, G4, A1, A2, and N1.

Run only through /Volumes/SSD990/cryptanalysis/sage -python.  Each command
writes one immutable JSON receipt.  These are stage diagnostics, not IC1 runs.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, Matrix, PolynomialRing, ZZ, matrix, set_random_seed, vector

from boolean_core import ANFField, echelon, evaluate, replay_trace, sparse_macaulay

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bits(value) -> int:
    return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))


def from_bits(K, value: int):
    answer = K(0)
    power = K(1)
    root = K.gen()
    while value:
        if value & 1:
            answer += power
        power *= root
        value >>= 1
    return answer


def field(degree: int):
    K = GF(2**degree, f"a{degree}")
    modulus = sum(int(c) << i for i, c in enumerate(K.modulus().list()))
    return K, modulus


def curve(K):
    return EllipticCurve(K, [1, 0, 0, 0, 1])


def point_key(P):
    return None if P.is_zero() else [bits(P[0]), bits(P[1])]


def report_base(proposal_id: str, degree: int, modulus: int) -> dict:
    return {"schema_version": 1, "proposal_id": proposal_id,
            "candidate_id": None, "run_id": None, "curve_id": None,
            "field_degree": degree, "field_modulus_bits": modulus,
            "scope": "bounded stage diagnostic; no complete IC method or DLP speedup",
            "source_sha256": digest(Path(__file__)),
            "boolean_core_sha256": digest(HERE / "boolean_core.py")}


def candidate_x_points(E, K, dimension: int):
    """All x in a small polynomial-basis span; both signs where liftable."""
    basis = [from_bits(K, 1 << i) for i in range(dimension)]
    representatives = []
    for mask in range(1 << dimension):
        x = sum((basis[i] for i in range(dimension) if mask >> i & 1), K(0))
        if x:
            representatives.extend(E.lift_x(x, all=True))
    return basis, representatives


def planted_targets(points, arity: int, count: int):
    targets = []
    seen = set()
    for indices in itertools.product(range(len(points)), repeat=arity):
        Q = sum((points[i] for i in indices), points[0].curve()(0))
        if Q.is_zero():
            continue
        key = tuple(point_key(Q))
        if key not in seen:
            seen.add(key)
            targets.append((Q, indices))
        if len(targets) == count:
            return targets
    raise ValueError(f"only {len(targets)} distinct planted targets")


def g1_one(K, modulus: int, E, arity: int, n_targets: int):
    dimension = 3
    basis, points = candidate_x_points(E, K, dimension)
    targets = planted_targets(points, arity, n_targets)
    anf = ANFField(31, modulus)
    leaves = [anf.linear(list(range(i * dimension, (i + 1) * dimension)),
                         [bits(value) for value in basis]) for i in range(arity)]
    nvars = arity * dimension
    systems = []
    for Q, _ in targets:
        target = anf.constant(bits(Q[0]))
        equations = (anf.s3(leaves[0], leaves[1], target) if arity == 2
                     else anf.s4(leaves[0], leaves[1], leaves[2], target))
        systems.append(equations)
    fixed_degrees = [max((term.bit_count() for system in systems for term in system[i]),
                         default=-1) for i in range(31)]
    degree = max(d for d in fixed_degrees if d >= 0)
    baseline_ns = []
    build_ns = []
    elimination_ns = []
    replay_ns = []
    same_sources = []
    same_basis = []
    trace = None
    original_sources = None
    for i, equations in enumerate(systems):
        start = time.perf_counter_ns()
        macaulay = sparse_macaulay(equations, nvars, degree,
                                   fixed_degrees=fixed_degrees,
                                   max_columns=100_000, max_rows=100_000)
        packed = macaulay.packed_rows()
        built = time.perf_counter_ns()
        fresh, fresh_trace = echelon(packed)
        finished = time.perf_counter_ns()
        build_ns.append(built-start)
        elimination_ns.append(finished-built)
        baseline_ns.append(finished-start)
        if i == 0:
            trace, original_sources = fresh_trace, macaulay.sources
            replay_ns.append(None)
            same_sources.append(True)
            same_basis.append(True)
            continue
        shape_equal = macaulay.sources == original_sources
        same_sources.append(shape_equal)
        if shape_equal:
            start = time.perf_counter_ns()
            replayed = replay_trace(packed, trace, verify=False)
            replay_ns.append(time.perf_counter_ns() - start)
            same_basis.append(replayed == fresh)
        else:
            replay_ns.append(None)
            same_basis.append(False)
    ratios = [b / r for b, r, ok in zip(baseline_ns, replay_ns, same_basis)
              if ok and r is not None and r > 0]
    charged_ratios = [b / (setup + replay) for b, setup, replay, ok in
                      zip(baseline_ns, build_ns, replay_ns, same_basis)
                      if ok and replay is not None and setup + replay > 0]
    return {"arity": arity, "leaf_dimension": dimension,
            "boolean_variables": nvars, "degree": degree,
            "target_count": n_targets, "macaulay_rows_first": len(original_sources),
            "macaulay_columns_first": len(macaulay.columns),
            "fixed_generator_degree_schedule": fixed_degrees,
            "same_row_sources": same_sources, "same_echelon_basis": same_basis,
            "baseline_build_plus_eliminate_ns": baseline_ns,
            "macaulay_build_ns": build_ns,
            "fresh_elimination_ns": elimination_ns,
            "trace_replay_only_ns": replay_ns,
            "median_stage_ratio_excluding_build": statistics.median(ratios) if ratios else None,
            "median_stage_ratio_including_replay_build":
                statistics.median(charged_ratios) if charged_ratios else None,
            "passes_table_falsifier": all(same_basis) and bool(ratios)
                and min(charged_ratios) >= 3,
            "planted_target_coordinates": [point_key(Q) for Q, _ in targets],
            "warning": "Macaulay row-elimination trace only, not an F4 symbolic trace or full basis solver. The charged ratio includes matrix construction on both paths; CPU timing is exploratory without host isolation."}


def g1(args):
    K, modulus = field(31)
    E = curve(K)
    output = report_base("G1", 31, modulus)
    output["cells"] = [g1_one(K, modulus, E, m, args.targets) for m in (2, 3)]
    return output


def order_two_mod(prime):
    value = 2 % prime
    order = 1
    while value != 1:
        value = value * 2 % prime
        order += 1
    return order


def g2(args):
    result = {"schema_version": 1, "proposal_id": "G2", "candidate_id": None,
              "run_id": None, "scope": "algebraic symmetry/DFT gate, not F4 Macaulay block timing",
              "source_sha256": digest(Path(__file__)), "cases": []}
    for n in (19, 23, 131):
        order = order_two_mod(n)
        nontrivial_orbits = (n - 1) // order
        cell = {"shift_length": n, "character_extension_degree": order,
                "irreducible_rational_blocks": 1 + nontrivial_orbits,
                "two_block_claim_applies": nontrivial_orbits == 1}
        coordinate_variables = 3*n  # two leaves and a freely shifted target
        squarefree_degree2 = 1 + coordinate_variables + math.comb(coordinate_variables, 2)
        assert (squarefree_degree2-1) % n == 0
        monomial_orbits = 1 + (squarefree_degree2-1)//n
        cell["degree2_monomial_module"] = {
            "variables": coordinate_variables,
            "squarefree_columns": squarefree_degree2,
            "cyclic_monomial_orbits": monomial_orbits,
            "trivial_character_dimension": monomial_orbits,
            "nontrivial_rational_block_dimensions":
                [(monomial_orbits-1)*order]*nontrivial_orbits,
            "scope": "full-coordinate degree-two module; not an F4 Macaulay matrix or the window/barrel input"}
        if n != 131:
            K, modulus = field(n)
            rng = random.Random(20261007 + n)
            triples = [[from_bits(K, rng.randrange(1 << n)) for _ in range(3)]
                       for _ in range(args.samples)]
            def s3(a, b, c):
                return (a*b + a*c + b*c)**2 + a*b*c + 1
            cell["frobenius_equivariance_samples"] = len(triples)
            cell["frobenius_equivariance_passed"] = all(
                s3(a**2, b**2, c**2) == s3(a, b, c)**2
                for a, b, c in triples)
            L = GF(2**order, f"u{n}")
            root = L.multiplicative_generator() ** ((2**order - 1) // n)
            if root.multiplicative_order() != n:
                raise AssertionError("DFT root order")
            V = matrix(L, n, n, lambda i, j: root ** (i*j))
            coefficients = [L(rng.randrange(2)) for _ in range(n)]
            A = matrix(L, n, n, lambda i, j: coefficients[(i-j) % n])
            transformed = V.inverse() * A * V
            cell["circulant_dft_diagonal"] = all(
                not transformed[i, j] for i in range(n) for j in range(n) if i != j)
            cell["field_modulus_bits"] = modulus
        result["cases"].append(cell)
    return result


def norm_multipliers(bound: int, mu: int = -1):
    values = []
    for a in range(-bound, bound + 1):
        for b in range(-bound, bound + 1):
            norm = a*a + mu*a*b + 2*b*b
            if 0 < norm <= bound and (a > 0 or (a == 0 and b > 0)):
                values.append((a, b, norm))
    return values


def multiplier_orbit(scalar: int, lam: int, order: int, modulus: int):
    value = scalar % modulus
    best = modulus
    for _ in range(order):
        best = min(best, value, (-value) % modulus)
        value = value * lam % modulus
    return best


def a1(args):
    source = REPO / "experiments/koblitz-n53-one-target-20260929/run_r1/rho.json"
    paired_source = REPO / "experiments/koblitz-n53-one-target-20260929/run_r1/paired_run.json"
    fixture = json.loads(source.read_text())
    paired = json.loads(paired_source.read_text())
    r, lam = int(fixture["subgroup_order"]), int(fixture["lambda"])
    assert (lam*lam + lam + 2) % r == 0 and pow(lam, 53, r) == 1
    multipliers = norm_multipliers(16)
    classes = {}
    for a, b, norm in multipliers:
        scalar = (a + b*lam) % r
        key = multiplier_orbit(scalar, lam, 53, r)
        classes.setdefault(key, []).append([a, b, norm])
    result = {"schema_version": 1, "proposal_id": "A1", "candidate_id": None,
              "run_id": None, "curve_id": paired["curve_id"],
              "field_degree": 53, "subgroup_order": r, "frobenius_scalar": lam,
              "norm_bound": 16, "multipliers_up_to_sign": len(multipliers),
              "classes_after_existing_sign_frobenius_folding": len(classes),
              "classes": {str(k): v for k, v in sorted(classes.items())},
              "source_sha256": digest(Path(__file__)),
              "reference_fixture_sha256": digest(source),
              "paired_fixture_sha256": digest(paired_source),
              "scope": "exact scalar/orbit closure gate; no relation yield, rank, or speedup measured"}
    if args.k == 0:
        return result
    # Evaluate actual point images of a deterministic prefix of a retained base.
    # Use the accepted field polynomial, not Sage's unrelated default basis.
    polynomial_ring = PolynomialRing(GF(2), "t")
    t = polynomial_ring.gen()
    K = GF(2**53, "z53", modulus=t**53 +
           sum((t**i for i in fixture["field_modulus_low_terms"]), polynomial_ring(0)))
    E = curve(K)
    source_base = REPO / "experiments/koblitz-n53-one-target-20260929/run_r1/factor_base_header.jsonl"
    header = json.loads(source_base.open().readline())
    raw = header["factor_base_point_coordinates"][:args.k]
    points = [E(from_bits(K, x), from_bits(K, y)) for x, y in raw]
    assert all((r*P).is_zero() for P in points)
    modulus_bits = (1 << 53) | sum(1 << i for i in fixture["field_modulus_low_terms"])
    square_images = ANFField(53, modulus_bits).reductions[::2]
    def square_bits(value):
        answer = 0
        while value:
            low = value & -value
            answer ^= square_images[low.bit_length()-1]
            value ^= low
        return answer
    if points:
        assert square_bits(bits(points[0][0])) == bits(points[0][0]**2)
        assert square_bits(bits(points[0][1])) == bits(points[0][1]**2)
    def canon(P):
        best = None
        x, y = bits(P[0]), bits(P[1])
        for _ in range(53):
            key = (x, y)
            # On y^2+xy=x^3+1, negation is (x,y+x).
            other = (x, y ^ x)
            best = min(best, key, other) if best is not None else min(key, other)
            x, y = square_bits(x), square_bits(y)
        return best
    representatives = {}
    for P in points:
        representatives.setdefault(canon(P), P)
    original = set(representatives)
    images = set()
    for key in classes:
        scalar = int(key)
        for P in representatives.values():
            images.add(canon(scalar*P))
    result.update({"sample_base_points": len(points),
                   "sample_original_folded_columns": len(original),
                   "scalar_image_point_operations": len(classes)*len(representatives),
                   "closure_folded_columns": len(images),
                   "closure_factor": len(images) / len(original) if original else None,
                   "original_columns_retained": len(original & images),
                   "base_header_sha256": digest(source_base)})
    return result


def frobenius_orbits(K, xs):
    unseen = set(xs)
    answer = []
    for start in sorted(unseen, key=bits):
        if start not in unseen:
            continue
        orbit = []
        value = start
        visited = set()
        while value not in visited:
            orbit.append(value)
            visited.add(value)
            value = value**2
        for value in orbit:
            unseen.discard(value)
        answer.append(tuple(orbit))
    return sorted(answer, key=lambda orbit: min(bits(x) for x in orbit))


def normal_basis(K, seed=20261007):
    rng = random.Random(seed)
    for _ in range(1000):
        root = from_bits(K, rng.randrange(1, 1 << K.degree()))
        values = [root ** (2**i) for i in range(K.degree())]
        rows = [[(bits(value) >> i) & 1 for value in values]
                for i in range(K.degree())]
        if Matrix(GF(2), rows).rank() == K.degree():
            return values
    raise RuntimeError("normal basis search failed")


def wilson95(hits: int, count: int):
    z = 1.959963984540054
    p = hits / count
    denominator = 1 + z*z/count
    center = (p + z*z/(2*count))/denominator
    radius = z*math.sqrt(p*(1-p)/count + z*z/(4*count*count))/denominator
    return [center-radius, center+radius]


def a2(args):
    K, modulus = field(23)
    E = curve(K)
    gamma = K.multiplicative_generator() ** ((2**23 - 1) // 47)
    assert gamma.multiplicative_order() == 47
    powers = [gamma**i for i in range(47)]
    cyclotomic = {powers[i] + powers[j] for i in range(47) for j in range(i+1, 47)}
    cyclotomic_w3 = {powers[i] + powers[j] + powers[k]
                     for i in range(47) for j in range(i+1, 47)
                     for k in range(j+1, 47)}
    normal = normal_basis(K)
    hamming = {normal[i] + normal[j] for i in range(23) for j in range(i+1, 23)}
    hamming_w3 = {normal[i] + normal[j] + normal[k]
                  for i in range(23) for j in range(i+1, 23)
                  for k in range(j+1, 23)}
    cylo_orbits = frobenius_orbits(K, cyclotomic | cyclotomic_w3)
    hw_orbits = frobenius_orbits(K, hamming | hamming_w3)
    group_order = int(E.order())
    factorization = list(ZZ(group_order).factor())
    r = int(max(p for p, _ in factorization))
    cofactor = group_order // r
    def usable_orbits(orbits):
        usable = []
        for orbit in orbits:
            points = {}
            for x in orbit:
                # For this ordinary b=1 curve, an odd-order subgroup point is
                # a double and its x-coordinate has field trace zero.
                if x.trace() != 0:
                    continue
                for P in E.lift_x(x, all=True):
                    if not P.is_zero() and (r*P).is_zero():
                        points[tuple(point_key(P))] = P
            if points:
                usable.append((orbit, points))
        return usable
    cylo_usable = usable_orbits(cylo_orbits)
    hw_usable = usable_orbits(hw_orbits)
    matched = min(len(cylo_usable), len(hw_usable))
    selected = {"cyclotomic_weight2_or_3": cylo_usable[:matched],
                "normal_weight2": hw_usable[:matched]}
    bases = {name: {key: point for _, orbit_points in orbits
                    for key, point in orbit_points.items()}
             for name, orbits in selected.items()}
    rng = random.Random(20261007)
    G = None
    for _ in range(100):
        P = E.random_point()
        trial = cofactor*P
        if not trial.is_zero() and (r*trial).is_zero():
            G = trial
            break
    if G is None:
        raise RuntimeError("subgroup generator search failed")
    targets = [rng.randrange(1, r)*G for _ in range(args.targets)]
    cells = []
    for name, points in bases.items():
        point_set = set(points)
        P = list(points.values())
        pair_sums = {tuple(point_key(left + right)) for left in P for right in P
                     if not (left + right).is_zero()}
        statuses = []
        for Q in targets:
            key = tuple(point_key(Q))
            m2 = key in pair_sums
            m3 = any(tuple(point_key(Q - point)) in pair_sums for point in P
                     if not (Q - point).is_zero())
            statuses.append({"m2": m2, "m3": m3})
        cells.append({"base": name, "selected_x_orbits": len(selected[name]),
                      "selected_x_count": sum(len(orbit) for orbit, _ in selected[name]),
                      "selected_weight2_orbits": sum(
                          selected_orbit[0][0] in (cyclotomic if name.startswith("cyclotomic")
                                                  else hamming)
                          for selected_orbit in selected[name]),
                      "selected_weight3_orbits": sum(
                          selected_orbit[0][0] in (cyclotomic_w3 if name.startswith("cyclotomic")
                                                  else hamming_w3)
                          for selected_orbit in selected[name]),
                      "actual_usable_B": len(P),
                      "folded_x_columns": len(frobenius_orbits(
                          K, {point[0] for point in P})),
                      "m2_hits": sum(s["m2"] for s in statuses),
                      "m3_hits": sum(s["m3"] for s in statuses),
                      "m2_wilson95": wilson95(sum(s["m2"] for s in statuses), len(statuses)),
                      "m3_wilson95": wilson95(sum(s["m3"] for s in statuses), len(statuses)),
                      "target_statuses": statuses,
                      "base_point_sha256": hashlib.sha256(json.dumps(
                          sorted(point_set), separators=(",", ":")).encode()).hexdigest()})
    result = report_base("A2", 23, modulus)
    result.update({"gamma_bits": bits(gamma), "gamma_order": 47,
                   "cyclotomic_weight2_x_count": len(cyclotomic),
                   "cyclotomic_weight3_x_count": len(cyclotomic_w3),
                   "cyclotomic_weight3_trace_zero_x_count":
                       sum(x.trace() == 0 for x in cyclotomic_w3),
                   "cyclotomic_weight3_satisfying_x263_equals_1":
                       sum(x**263 == 1 for x in cyclotomic_w3),
                   "cyclotomic_weight2_x_orbits": len(frobenius_orbits(K, cyclotomic)),
                   "cyclotomic_weight2_or3_x_orbits": len(cylo_orbits),
                   "cyclotomic_usable_x_orbits": len(cylo_usable),
                   "normal_weight2_x_count": len(hamming),
                   "normal_weight3_x_count": len(hamming_w3),
                   "normal_weight3_trace_zero_x_count":
                       sum(x.trace() == 0 for x in hamming_w3),
                   "normal_weight2_x_orbits": len(frobenius_orbits(K, hamming)),
                   "normal_weight2_or3_x_orbits": len(hw_orbits),
                   "normal_usable_x_orbits": len(hw_usable),
                   "cyclotomic_weight2_satisfying_x47_equals_1": sum(x**47 == 1 for x in cyclotomic),
                   "cyclotomic_weight2_satisfying_x263_equals_1": sum(x**263 == 1 for x in cyclotomic),
                   "claimed_membership_equation_valid": all(x**263 == 1 for x in cyclotomic),
                   "subgroup_order": r, "cofactor": cofactor,
                   "target_points": [point_key(Q) for Q in targets],
                   "cells": cells,
                   "paired_m3_discordant": {
                       "cyclotomic_only": sum(a["m3"] and not b["m3"] for a,b in
                           zip(cells[0]["target_statuses"], cells[1]["target_statuses"])),
                       "normal_only": sum(b["m3"] and not a["m3"] for a,b in
                           zip(cells[0]["target_statuses"], cells[1]["target_statuses"]))},
                   "warning": "Matched whole usable x Frobenius orbits and checked actual B and folded columns. Pair/triple yield is exact for these selected finite bases; no F4 or WDSat solving-degree measurement."})
    return result


def ring_add(*values):
    answer = 0
    for value in values:
        answer ^= value
    return answer


def ring_mul(a: int, b: int, length: int) -> int:
    answer = 0
    while a:
        low_a = a & -a
        i = low_a.bit_length() - 1
        value = b
        while value:
            low_b = value & -value
            j = low_b.bit_length() - 1
            answer ^= 1 << ((i+j) % length)
            value ^= low_b
        a ^= low_a
    return answer


def ring_s3(a: int, b: int, c: int, length: int) -> int:
    ab = ring_mul(a, b, length)
    ac = ring_mul(a, c, length)
    bc = ring_mul(b, c, length)
    e2 = ring_add(ab, ac, bc)
    return ring_add(ring_mul(e2, e2, length), ring_mul(ab, c, length), 1)


def n1(args):
    K, modulus = field(23)
    E = curve(K)
    gamma = K.multiplicative_generator() ** ((2**23 - 1) // 47)
    basis = [gamma**i for i in range(23)]
    change = matrix(GF(2), 23, 23,
                    lambda i, j: (bits(basis[j]) >> i) & 1).inverse()
    def lift(value):
        coordinates = change * vector(GF(2), [(bits(value) >> i) & 1 for i in range(23)])
        return sum(int(coordinates[i]) << i for i in range(23))
    def project(value):
        return sum((gamma**i for i in range(47) if value >> i & 1), K(0))
    rng = random.Random(20261007)
    G = E.random_point()
    while G.is_zero():
        G = E.random_point()
    exact = 0
    examples = []
    for sample in range(args.targets):
        P1 = rng.randrange(1, 1 << 22)*G
        P2 = rng.randrange(1, 1 << 22)*G
        Q = P1 + P2
        if P1.is_zero() or P2.is_zero() or Q.is_zero():
            continue
        x1, x2, xq = P1[0], P2[0], Q[0]
        lifted = ring_s3(lift(x1), lift(x2), lift(xq), 47)
        assert project(lifted) == 0
        exact += lifted == 0
        if len(examples) < 4:
            examples.append({"x": [bits(x1), bits(x2), bits(xq)],
                             "lifted_s3_weight": lifted.bit_count(),
                             "exact_lift": lifted == 0})
    result = report_base("N1", 23, modulus)
    result.update({"group_algebra_length": 47, "quotient_dimension": 23,
                   "kernel_dimension": 24, "gamma_bits": bits(gamma),
                   "section": "coordinates in 1,gamma,...,gamma^22",
                   "planted_s3_samples": args.targets, "exact_lifts": exact,
                   "sample_examples": examples,
                   "warning": "Exact lifting depends on the declared section. All samples project to valid S3 identities; planted positives do not estimate ordinary PDP yield."})
    return result


def g4(args):
    K, modulus = field(19)
    E = curve(K)
    dimension = 2
    basis, points = candidate_x_points(E, K, dimension)
    targets = planted_targets(points, 3, min(args.targets, 8))
    R = PolynomialRing(K, names=[f"u{i}" for i in range(6)] + ["z"])
    generators = R.gens()
    leaves = [sum((basis[j]*generators[i*2+j] for j in range(2)), R(0))
              for i in range(3)]
    def s3(a, b, c):
        return (a*b+a*c+b*c)**2 + a*b*c + 1
    xq = targets[0][0][0]
    mixed = [s3(leaves[0], leaves[1], generators[-1]),
             s3(generators[-1], leaves[2], xq)]
    mixed += [u*u+u for u in generators[:-1]]
    gb_status = "not_requested"
    gb_seconds = None
    gb_size = None
    if args.solve_seconds:
        class TimedOut(Exception):
            pass
        def alarm_handler(_signum, _frame):
            raise TimedOut()
        old_handler = signal.signal(signal.SIGALRM, alarm_handler)
        started = time.perf_counter()
        try:
            signal.alarm(args.solve_seconds)
            gb = R.ideal(mixed).groebner_basis()
            gb_status, gb_size = "completed", len(gb)
        except TimedOut:
            gb_status = "timeout"
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
            gb_seconds = time.perf_counter() - started
    anf = ANFField(19, modulus)
    leaf_anf = [anf.linear([2*i, 2*i+1], [bits(b) for b in basis]) for i in range(3)]
    middle_anf = anf.linear(list(range(6, 25)), [1 << i for i in range(19)])
    boolean_equations = anf.s3(leaf_anf[0], leaf_anf[1], middle_anf)
    boolean_equations += anf.s3(middle_anf, leaf_anf[2], anf.constant(bits(xq)))
    boolean_sage = None
    if args.boolean_sage_seconds:
        B = PolynomialRing(GF(2), names=[f"w{i}" for i in range(25)])
        variables = B.gens()
        def as_sage(poly):
            answer = B(0)
            for term in poly:
                product = B(1)
                for i in range(25):
                    if term >> i & 1:
                        product *= variables[i]
                answer += product
            return answer
        generators_b = [as_sage(eq) for eq in boolean_equations if eq]
        generators_b += [v*v+v for v in variables]
        class TimedOutBoolean(Exception):
            pass
        def boolean_alarm(_signum, _frame):
            raise TimedOutBoolean()
        old_handler = signal.signal(signal.SIGALRM, boolean_alarm)
        started_boolean = time.perf_counter()
        try:
            signal.alarm(args.boolean_sage_seconds)
            basis_b = B.ideal(generators_b).groebner_basis()
            status_b, size_b = "completed", len(basis_b)
        except TimedOutBoolean:
            status_b, size_b = "timeout", None
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        boolean_sage = {"status": status_b,
                        "wall_seconds": time.perf_counter()-started_boolean,
                        "basis_size": size_b,
                        "limit_seconds": args.boolean_sage_seconds,
                        "solver": "Sage ideal.groebner_basis on Boolean GF(2) polynomial ring"}
    boolean_f4 = None
    if args.boolean_f4_seconds:
        names = [f"v{i}" for i in range(25)]
        def polynomial_text(poly):
            return "+".join("1" if term == 0 else "*".join(
                names[i] for i in range(25) if term >> i & 1)
                for term in sorted(poly, key=lambda mask: (mask.bit_count(), mask)))
        input_path = args.output.with_suffix(".ms")
        solver_output = args.output.with_suffix(".msolve.out")
        if input_path.exists() or solver_output.exists():
            raise FileExistsError("preserve prior Boolean F4 input/output")
        all_equations = [polynomial_text(eq) for eq in boolean_equations if eq]
        all_equations += [f"v{i}^2+v{i}" for i in range(25)]
        input_path.write_text(",".join(names) + "\n2\n" +
                              ",\n".join(all_equations) + "\n")
        command = ["/opt/homebrew/bin/msolve", "-g", "2", "-t", "1",
                   "-f", str(input_path), "-o", str(solver_output)]
        started_f4 = time.perf_counter_ns()
        try:
            proc = subprocess.run(command, capture_output=True, text=True,
                                  timeout=args.boolean_f4_seconds)
            status = "completed" if proc.returncode == 0 else "solver_error"
            exit_code = proc.returncode
            stdout, stderr = proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            status, exit_code = "timeout", None
            stdout = (exc.stdout or b"").decode(errors="replace")
            stderr = (exc.stderr or b"").decode(errors="replace")
        boolean_f4 = {"solver": "Msolve GF(2) F4 with Boolean field equations",
                      "status": status, "exit_code": exit_code,
                      "wall_ns_including_launch": time.perf_counter_ns()-started_f4,
                      "input_sha256": digest(input_path),
                      "input_bytes": input_path.stat().st_size,
                      "output_sha256": digest(solver_output) if solver_output.exists() else None,
                      "output_bytes": solver_output.stat().st_size if solver_output.exists() else None,
                      "stdout": stdout[:4000], "stderr": stderr[:4000],
                      "limit_seconds": args.boolean_f4_seconds,
                      "binary_sha256": digest(command[0])}
    # Exhaustively check the 2^(3d) leaf assignments.  The intermediate must
    # be in GF(2^19), unlike an unconstrained mixed-field algebraic closure.
    T = PolynomialRing(K, "t")
    t = T.gen()
    field_roots = 0
    resultant_roots = 0
    for mask in range(1 << 6):
        xs = [sum((basis[j] for j in range(2) if mask >> (2*i+j) & 1), K(0))
              for i in range(3)]
        first = s3(xs[0], xs[1], t)
        second = s3(t, xs[2], xq)
        has_field_root = any(second(root) == 0 for root, _ in first.roots())
        resultant_zero = first.resultant(second) == 0
        field_roots += has_field_root
        resultant_roots += resultant_zero
    result = report_base("G4", 19, modulus)
    result.update({"arity": 3, "leaf_dimension": dimension,
                   "mixed_field_variables": 7, "boolean_variables": 25,
                   "mixed_equations": len(mixed),
                   "boolean_coefficient_equations": sum(bool(e) for e in boolean_equations),
                   "mixed_max_total_degree": int(max(f.total_degree() for f in mixed)),
                   "boolean_max_total_degree": max((term.bit_count()
                       for equation in boolean_equations for term in equation), default=0),
                   "mixed_groebner_status": gb_status,
                   "mixed_groebner_seconds": gb_seconds,
                   "mixed_groebner_basis_size": gb_size,
                   "boolean_sage_groebner": boolean_sage,
                   "boolean_f4": boolean_f4,
                   "leaf_assignments": 64,
                   "field_rational_intermediate_assignments": field_roots,
                   "algebraic_closure_intermediate_assignments": resultant_roots,
                   "target_point": point_key(targets[0][0]),
                   "warning": "Sage mixed/Boolean Groebner and Msolve Boolean F4 are separate method diagnostics. Extra algebraic-closure roots need a z^(2^19)-z constraint; no exact matched F4 speed claim."})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe", choices=("g1", "g2", "g4", "a1", "a2", "n1"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--targets", type=int, default=16)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--k", type=int, default=0, help="A1 base prefix (0 = scalar gate only)")
    parser.add_argument("--solve-seconds", type=int, default=0)
    parser.add_argument("--boolean-f4-seconds", type=int, default=0)
    parser.add_argument("--boolean-sage-seconds", type=int, default=0)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("preserve previous receipt")
    if (args.targets < 1 or args.samples < 1 or args.k < 0
            or args.solve_seconds < 0 or args.boolean_f4_seconds < 0
            or args.boolean_sage_seconds < 0):
        parser.error("counts and time budgets must be nonnegative; targets/samples positive")
    set_random_seed(20261007)
    started = time.perf_counter_ns()
    result = globals()[args.probe](args)
    result["stage_wall_ns"] = time.perf_counter_ns() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"proposal_id": result["proposal_id"],
                      "stage_wall_ns": result["stage_wall_ns"],
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
