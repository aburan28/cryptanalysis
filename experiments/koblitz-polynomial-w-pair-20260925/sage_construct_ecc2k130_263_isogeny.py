#!/usr/bin/env sage -python
"""Construct one degree-263 isogeny without factoring the division polynomial."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ, set_random_seed


HERE = Path(__file__).resolve().parent
N = 131
ELL = 263
R = ZZ(680564733841876926932320129493409985129)
SEED = 20260926


def field_integer(value):
    """Polynomial-basis binary encoding declared by the field modulus."""
    return sum(int(bit) << index for index, bit in enumerate(value.polynomial().list()))


def curve_order_at_degree(n):
    previous, current = ZZ(2), ZZ(-1)
    for _ in range(2, n + 1):
        previous, current = current, -current - 2 * previous
    return 2**n + 1 - current


def halftrace(value):
    """Solve z^2+z=value over the odd-degree base field when trace is zero."""
    answer = value
    for _ in range((N - 1) // 2):
        answer = answer**4 + value
    return answer


def random_point_over_tower(curve, k, l):
    """Use the explicit quadratic tower when Sage exposes only generic curve methods."""
    u = l.gen()
    for _ in range(1000):
        x = l(k.random_element()) + l(k.random_element()) * u
        if x == 0:
            continue
        c = x + 1 / (x*x)
        parts = c.lift().list()
        c0 = k(parts[0])
        c1 = k(parts[1]) if len(parts) > 1 else k.zero()
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
        y = x * (l(p) + l(q) * u)
        return curve([x, y])
    raise RuntimeError("No point sampled in 1000 x-values")


def main():
    started = time.perf_counter()
    set_random_seed(SEED)
    f2x = PolynomialRing(GF(2), "t")
    t = f2x.gen()
    modulus = t**N + t**13 + t**2 + t + 1
    k = GF(2**N, "t", modulus=modulus)
    uk = PolynomialRing(k, "u")
    u = uk.gen()
    l = k.extension(u*u + u + 1, "u")
    e = EllipticCurve(k, [1, 0, 0, 0, 1])
    el = e.change_ring(l)
    group_order = curve_order_at_degree(2 * N)
    assert curve_order_at_degree(N) == 4 * R
    assert group_order % (ELL * ELL) == 0
    assert group_order % (ELL**3) != 0
    cofactor = group_order // (ELL * ELL)
    print("field and group order ready", round(time.perf_counter() - started, 3), flush=True)

    attempts = []
    q = None
    for index in range(1, 11):
        point = random_point_over_tower(el, k, l)
        candidate = cofactor * point
        status = "zero" if candidate.is_zero() else "order_check"
        if not candidate.is_zero() and ELL * candidate == el(0):
            q = candidate
            status = "order_263"
        attempts.append({"attempt": index, "status": status})
        if q is not None:
            break
    assert q is not None
    assert el([q[0] ** (2**N), q[1] ** (2**N)]) == -q
    print("anti-invariant torsion ready", attempts,
          round(time.perf_counter() - started, 3), flush=True)

    ring = PolynomialRing(k, "X")
    x = ring.gen()
    kernel = ring.one()
    roots = set()
    multiple = q
    for _ in range((ELL - 1) // 2):
        xi = multiple[0]
        assert xi ** (2**N) == xi
        coefficients = xi.lift().list()
        assert not any(coefficients[1:])
        base_x = k(coefficients[0])
        encoded = field_integer(base_x)
        assert encoded not in roots
        roots.add(encoded)
        kernel *= x - base_x
        multiple += q
    assert len(roots) == (ELL - 1) // 2
    assert kernel.degree() == (ELL - 1) // 2
    print("kernel polynomial ready", round(time.perf_counter() - started, 3), flush=True)

    isogeny = e.isogeny(kernel, check=False)
    target = isogeny.codomain()
    assert isogeny.degree() == ELL
    assert target.j_invariant() != e.j_invariant()
    assert isogeny.kernel_polynomial().monic().list() == kernel.monic().list()
    print("isogeny ready", round(time.perf_counter() - started, 3), flush=True)

    g = 4 * e.random_point()
    assert not g.is_zero() and R * g == e(0)
    transported = isogeny(g)
    assert not transported.is_zero() and R * transported == target(0)
    assert isogeny(7 * g) == 7 * transported
    scalar = ZZ(123456789)
    public = scalar * g
    mapped_public = isogeny(public)
    assert mapped_public == scalar * transported

    result = {
        "kind": "explicit_ecc2k130_degree263_isogeny_control",
        "candidate_id": None,
        "curve_field_degree": N,
        "field_modulus_low_terms": [0, 1, 2, 13],
        "element_encoding": "little_endian_polynomial_basis_integer",
        "source_model": "y^2+x*y=x^3+1",
        "subgroup_order": str(R),
        "isogeny_degree": ELL,
        "kernel_polynomial_coefficients": [field_integer(c) for c in kernel.list()],
        "kernel_polynomial_sha256": hashlib.sha256(json.dumps(
            [field_integer(c) for c in kernel.list()], separators=(",", ":")
        ).encode()).hexdigest(),
        "codomain_ainvs": [field_integer(c) for c in target.ainvs()],
        "codomain_j": field_integer(target.j_invariant()),
        "source_generator": [field_integer(g[0]), field_integer(g[1])],
        "transported_generator": [field_integer(transported[0]), field_integer(transported[1])],
        "source_public_fixture": [field_integer(public[0]), field_integer(public[1])],
        "transported_public_fixture": [field_integer(mapped_public[0]),
                                       field_integer(mapped_public[1])],
        "fixture_scalar": int(scalar),
        "kernel_point_checks": {"torsion_order_263": True,
                                "frobenius_131_equals_negation": True,
                                "all_kernel_x_in_base_field": True,
                                "distinct_kernel_x": len(roots)},
        "transport_checks": {"source_generator_order_r": True,
                             "mapped_generator_order_r": True,
                             "homomorphism_7g": True,
                             "fixture_scalar_replay": True},
        "random_seed": SEED,
        "torsion_projection_attempts": attempts,
        "setup_wall_seconds": time.perf_counter() - started,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    out = HERE / "ecc2k130_degree263_isogeny_control.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key in ("kind", "isogeny_degree", "codomain_j",
                                 "setup_wall_seconds", "transport_checks")}, indent=2))


if __name__ == "__main__":
    main()
