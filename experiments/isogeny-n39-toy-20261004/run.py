#!/usr/bin/env sage -python
"""Paired four-summand base geometry on a tractable split-prime descent.

This is a group pair-index stage control, not an implicit PDP or a complete
index-calculus candidate.  Target scalars construct held-out public points;
they are never supplied to the decomposition lookup.
"""

import argparse
import hashlib
import json
import math
from itertools import combinations_with_replacement
from pathlib import Path
import random
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ, set_random_seed
from sage.version import version as sage_version


HERE = Path(__file__).resolve().parent
N = 39
ELL = 79
R = ZZ(68616367)
H = ZZ(8012)
TORSION_SEED = 20261004
TARGET_SEED = 1419


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trace_at_degree(n):
    previous, current = ZZ(2), ZZ(-1)
    for _ in range(2, n + 1):
        previous, current = current, -current - 2*previous
    return current


def halftrace(value):
    answer = value
    for _ in range((N - 1)//2):
        answer = answer**4 + value
    return answer


def field_integer(value):
    return sum(int(bit) << index for index, bit in
               enumerate(value.polynomial().list()))


def point_key(point):
    if point.is_zero():
        return None
    return [field_integer(point[0]), field_integer(point[1])]


def key_tuple(point):
    encoded = point_key(point)
    return None if encoded is None else tuple(encoded)


def random_point_over_tower(curve, base, tower):
    u = tower.gen()
    for _ in range(1000):
        x = tower(base.random_element()) + tower(base.random_element())*u
        if x == 0:
            continue
        c = x + 1/(x*x)
        parts = c.lift().list()
        c0 = base(parts[0])
        c1 = base(parts[1]) if len(parts) > 1 else base(0)
        if c1.trace() != 0:
            continue
        q = halftrace(c1)
        assert q*q + q == c1
        rhs = c0 + q*q
        if rhs.trace() != 0:
            q += 1
            rhs += 1
        p = halftrace(rhs)
        assert p*p + p == rhs
        return curve([x, x*(tower(p) + tower(q)*u)])
    raise RuntimeError("tower point sampler exhausted")


def kernel_from_torsion(point, base, tower):
    ring = PolynomialRing(base, "X")
    xvar = ring.gen()
    polynomial = ring.one()
    roots = set()
    multiple = point
    for _ in range((ELL - 1)//2):
        x = multiple[0]
        assert x**(2**N) == x
        parts = x.lift().list()
        assert not any(parts[1:])
        root = base(parts[0])
        encoded = field_integer(root)
        assert encoded not in roots
        roots.add(encoded)
        polynomial *= xvar - root
        multiple += point
    assert polynomial.degree() == (ELL - 1)//2
    return polynomial


def rational_lift(curve, x):
    a1, a2, a3, a4, a6 = curve.ainvs()
    assert (a1, a2, a3) == (x.parent()(1), x.parent()(0), x.parent()(0))
    if x == 0:
        return None
    c = (x**3 + a4*x + a6)/(x*x)
    if c.trace() != 0:
        return None
    z = halftrace(c)
    assert z*z + z == c
    y = x*z
    if field_integer(y + x) < field_integer(y):
        y += x
    return curve([x, y])


def deterministic_base(curve, field, decode, size):
    started = time.perf_counter_ns()
    points = []
    seen = set()
    scan = 0
    geometric = 0
    while len(points) < size:
        scan += 1
        if scan > 100000:
            raise RuntimeError("base x-scan exceeded 100000")
        point = rational_lift(curve, decode(scan))
        if point is None:
            continue
        geometric += 1
        projected = H*point
        if projected.is_zero():
            continue
        assert R*projected == curve(0)
        key, negative = key_tuple(projected), key_tuple(-projected)
        if key in seen or negative in seen:
            continue
        seen.add(key)
        points.append(projected)
    return tuple(points), {"raw_x_scanned": scan, "rational_lifts": geometric,
                           "usable_points": len(points),
                           "wall_ns": time.perf_counter_ns() - started,
                           "recipe": "ascending_polynomial_basis_x;canonical_y;cofactor_8012;one_per_sign_pair"}


def pair_table(curve, base):
    started = time.perf_counter_ns()
    table = {}
    pairs = []
    for i, j in combinations_with_replacement(range(len(base)), 2):
        total = base[i] + base[j]
        pairs.append((total, i, j))
        table.setdefault(key_tuple(total), (i, j))
    return (table, pairs), {"unordered_pairs": len(pairs),
                   "distinct_pair_sums": len(table),
                   "wall_ns": time.perf_counter_ns() - started}


def lookup_four(curve, base, pair_index, target):
    started = time.perf_counter_ns()
    probes = 0
    table, pairs = pair_index
    for pair_sum, i, j in pairs:
        complement = target - pair_sum
        probes += 1
        other = table.get(key_tuple(complement))
        if other is None:
            continue
        witness = (i, j, *other)
        assert sum((base[index] for index in witness), curve(0)) == target
        return {"status": "verified_relation", "probes": probes,
                "witness": witness, "wall_ns": time.perf_counter_ns() - started}
    return {"status": "no_relation", "probes": probes, "witness": None,
            "wall_ns": time.perf_counter_ns() - started}


def experiment(base_size, target_count):
    assert 4 <= base_size <= 512 and 1 <= target_count <= 1024
    started = time.perf_counter_ns()
    t1, t39, t78 = (trace_at_degree(degree) for degree in (1, N, 2*N))
    assert t1 == -1 and t39 == 1481485
    q = 2**N
    order = q + 1 - t39
    assert order == H*R and R.is_prime()
    assert 4*q - t39*t39 == 7*24569**2
    assert 24569 == ELL*311
    assert [value for value in range(ELL) if (value*value + value + 2) % ELL == 0] == [12, 66]
    lambda_q = (int(t39)*pow(2, -1, ELL)) % ELL
    assert lambda_q == ELL - 1
    order_q2 = q*q + 1 - t78
    assert order_q2 % ELL**2 == 0 and order_q2 % ELL**3 != 0

    f2ring = PolynomialRing(GF(2), "t")
    t = f2ring.gen()
    modulus = t**N + t**4 + 1
    assert modulus.is_irreducible()
    field = GF(2**N, "t", modulus=modulus)
    uring = PolynomialRing(field, "u")
    u = uring.gen()
    tower = field.extension(u*u + u + 1, "u")
    source = EllipticCurve(field, [1, 0, 0, 0, 1])
    source_tower = source.change_ring(tower)

    def decode(value):
        return field(sum(t**index for index in range(value.bit_length())
                         if value & (1 << index)))

    set_random_seed(TORSION_SEED)
    cofactor = ZZ(order_q2)//ELL**2
    first_attempts = []
    torsion = None
    for attempt in range(1, 31):
        candidate = cofactor*random_point_over_tower(source_tower, field, tower)
        status = "zero" if candidate.is_zero() else "order_check"
        if not candidate.is_zero() and ELL*candidate == source_tower(0):
            torsion = candidate
            status = "order_79"
        first_attempts.append({"attempt": attempt, "status": status})
        if torsion is not None:
            break
    assert torsion is not None
    assert source_tower([torsion[0]**q, torsion[1]**q]) == -torsion
    f_kernel = kernel_from_torsion(torsion, field, tower)
    forward = source.isogeny(f_kernel, check=True)
    target_curve = forward.codomain()
    if target_curve.j_invariant() == source.j_invariant():
        raise RuntimeError("seed selected a horizontal kernel; change torsion seed")
    forward_seconds = (time.perf_counter_ns() - started)/1e9

    complement_attempts = []
    other_torsion = None
    for attempt in range(1, 31):
        candidate = cofactor*random_point_over_tower(source_tower, field, tower)
        status = "zero" if candidate.is_zero() else "forward_kernel"
        if not candidate.is_zero() and f_kernel(candidate[0]) != 0:
            other_torsion = candidate
            status = "complementary_79_line"
        complement_attempts.append({"attempt": attempt, "status": status})
        if other_torsion is not None:
            break
    assert other_torsion is not None
    image_torsion = forward._eval(other_torsion)
    assert not image_torsion.is_zero() and ELL*image_torsion == image_torsion.curve()(0)
    d_kernel = kernel_from_torsion(image_torsion, field, tower)
    dual_raw = target_curve.isogeny(d_kernel, check=True)
    assert dual_raw.codomain().is_isomorphic(source)
    iso = dual_raw.codomain().isomorphism_to(source)

    source_base, source_build = deterministic_base(source, field, decode, base_size)
    native_base, native_build = deterministic_base(target_curve, field, decode, base_size)
    g = source_base[0]
    mapped_g = forward(g)
    assert not mapped_g.is_zero() and R*mapped_g == target_curve(0)
    recovered_g = iso(dual_raw(mapped_g))
    if recovered_g == ELL*g:
        sign = 1
    elif recovered_g == -ELL*g:
        sign = -1
    else:
        raise AssertionError("dual composition is not ±[79]")
    ell_inverse = ZZ(ELL).inverse_mod(R)

    def pullback(point):
        return ell_inverse*sign*iso(dual_raw(point))

    transport_started = time.perf_counter_ns()
    transported_base = tuple(forward(point) for point in source_base)
    transport_ns = time.perf_counter_ns() - transport_started
    pullback_started = time.perf_counter_ns()
    pullback_base = tuple(pullback(point) for point in native_base)
    pullback_ns = time.perf_counter_ns() - pullback_started
    assert all(forward(point) == image for point, image in
               zip(source_base, transported_base))
    assert all(forward(point) == image for point, image in
               zip(pullback_base, native_base))
    assert all(len({key_tuple(point) for point in base}) == base_size for base in
               (source_base, native_base, transported_base, pullback_base))

    policies = {
        "source": (source, source_base),
        "descendant_native": (target_curve, native_base),
        "transported": (target_curve, transported_base),
        "pullback": (source, pullback_base),
    }
    tables = {}
    table_build = {}
    for name, (curve, base) in policies.items():
        tables[name], table_build[name] = pair_table(curve, base)

    rng = random.Random(TARGET_SEED)
    scalars = rng.sample(range(1, int(R)), target_count)
    rows = []
    for index, scalar in enumerate(scalars):
        public = ZZ(scalar)*g
        map_started = time.perf_counter_ns()
        mapped = forward(public)
        map_ns = time.perf_counter_ns() - map_started
        assert pullback(mapped) == public
        results = {}
        for name, (curve, base) in policies.items():
            query = public if curve == source else mapped
            results[name] = lookup_four(curve, base, tables[name], query)
        hits = {name: result["status"] == "verified_relation"
                for name, result in results.items()}
        assert hits["source"] == hits["transported"]
        assert hits["descendant_native"] == hits["pullback"]
        rows.append({"index": index, "fixture_scalar": scalar,
                     "source_target": point_key(public),
                     "descendant_target": point_key(mapped),
                     "target_map_wall_ns": map_ns,
                     "policies": results})
        if (index + 1) % 32 == 0:
            print("held-out targets checked", index + 1, flush=True)

    rates = {name: sum(row["policies"][name]["status"] == "verified_relation"
                       for row in rows) for name in policies}
    source_only = sum(row["policies"]["source"]["status"] == "verified_relation"
                      and row["policies"]["descendant_native"]["status"] != "verified_relation"
                      for row in rows)
    native_only = sum(row["policies"]["descendant_native"]["status"] == "verified_relation"
                      and row["policies"]["source"]["status"] != "verified_relation"
                      for row in rows)
    return {
        "kind": "n39_degree79_paired_four_base_group_lookup",
        "proposal_id": "Q1419", "candidate_id": None,
        "status": "verified_stage_control", "sage_version": sage_version,
        "field": {"p": 2, "n": N, "polynomial_low_terms": [0, 4, 39],
                  "element_encoding": "little_endian_polynomial_basis_integer"},
        "source_curve": {"ainvs": [1, 0, 0, 0, 1], "order": int(order),
                         "subgroup_order": int(R), "cofactor": int(H),
                         "generator": point_key(g), "trace": int(t39),
                         "endomorphism_order_conductor": 1,
                         "frobenius_order_conductor": 24569},
        "descendant_curve": {"ainvs": [field_integer(a) for a in target_curve.ainvs()],
                             "generator": point_key(mapped_g),
                             "endomorphism_order_conductor": ELL},
        "isogeny": {"degree": ELL, "direction": "descending",
                    "forward_kernel_coefficients": [field_integer(a) for a in f_kernel.list()],
                    "dual_kernel_coefficients": [field_integer(a) for a in d_kernel.list()],
                    "dual_isomorphism_tuple": [field_integer(a) for a in iso.tuple()],
                    "dual_composition_sign": sign,
                    "ell_inverse_mod_subgroup_order": int(ell_inverse),
                    "first_torsion_attempts": first_attempts,
                    "complement_torsion_attempts": complement_attempts,
                    "forward_construction_seconds": forward_seconds,
                    "all_base_transport_wall_ns": transport_ns,
                    "all_native_base_pullback_wall_ns": pullback_ns},
        "factor_bases": {
            "source": dict(source_build, points=[point_key(p) for p in source_base]),
            "descendant_native": dict(native_build, points=[point_key(p) for p in native_base]),
            "transported": {"usable_points": base_size,
                            "points": [point_key(p) for p in transported_base]},
            "pullback": {"usable_points": base_size,
                         "points": [point_key(p) for p in pullback_base]},
        },
        "pair_tables": table_build,
        "workload": {"input_law": "uniform_nonzero_scalar_times_fixed_generator",
                     "target_seed": TARGET_SEED, "target_count": target_count,
                     "base_size": base_size, "summands": 4,
                     "target_generation_outside_lookup_timing": True},
        "held_out_rows": rows,
        "verified_hit_counts": rates,
        "paired_source_only": source_only,
        "paired_native_only": native_only,
        "complete_ic_online_ms": None,
        "rho_online_ms": None,
        "speedup": None,
        "total_wall_seconds": (time.perf_counter_ns() - started)/1e9,
        "source_sha256": sha256(Path(__file__)),
        "runtime_info_sha256": sha256(HERE / "runtime-info.json"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--base-size", type=int, default=160)
    parser.add_argument("--targets", type=int, default=192)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"output already exists: {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = experiment(args.base_size, args.targets)
    except Exception as error:
        failure = {"kind": "n39_degree79_paired_four_base_group_lookup",
                   "proposal_id": "Q1419", "candidate_id": None,
                   "status": "failure", "error_type": type(error).__name__,
                   "error_message": str(error),
                   "base_size": args.base_size, "target_count": args.targets,
                   "source_sha256": sha256(Path(__file__)),
                   "runtime_info_sha256": sha256(HERE / "runtime-info.json")}
        args.out.write_text(json.dumps(failure, indent=2) + "\n")
        raise
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "verified_hit_counts": result["verified_hit_counts"],
                      "paired_source_only": result["paired_source_only"],
                      "paired_native_only": result["paired_native_only"],
                      "total_wall_seconds": result["total_wall_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
