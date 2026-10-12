#!/usr/bin/env sage -python
"""Replay the degree-263 maps at infinity, 2-torsion, and every kernel point.

All nonzero kernel points are defined over F_(2^262), rather than F_(2^131).
For a kernel root x in the base field, the quadratic equation for y has
absolute trace one.  The fixed quadratic tower gives both points above x
without relying on a random lift or on the isogeny implementation to find
its own exceptional inputs.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ
from sage.version import version as sage_version

from sage_construct_ecc2k130_263_isogeny import ELL, N, halftrace
from degree263_transport import evaluate_with_kernel


HERE = Path(__file__).resolve().parent
FORWARD_REPORT = HERE / "ecc2k130_degree263_isogeny_control.json"
DUAL_REPORT = HERE / "ecc2k130_degree263_dual_control.json"
TRANSPORT_SOURCE = HERE / "degree263_transport.py"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True,
                        help="new receipt path; existing files are never overwritten")
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"receipt already exists: {args.out}")

    started = time.perf_counter()
    forward_report = json.loads(FORWARD_REPORT.read_text())
    dual_report = json.loads(DUAL_REPORT.read_text())
    f2ring = PolynomialRing(GF(2), "t")
    t = f2ring.gen()
    modulus = t**N + t**13 + t**2 + t + 1
    assert modulus.is_irreducible()
    k = GF(2**N, "t", modulus=modulus)
    uring = PolynomialRing(k, "u")
    u = uring.gen()
    tower = k.extension(u*u + u + 1, "u")
    assert tower.degree() == 2
    source = EllipticCurve(k, [1, 0, 0, 0, 1])

    def decode(value):
        return k(sum(t**index for index in range(value.bit_length())
                     if value & (1 << index)))

    def encode(value):
        return sum(int(bit) << index
                   for index, bit in enumerate(value.polynomial().list()))

    ring = PolynomialRing(k, "X")
    f_kernel = ring([decode(value) for value in forward_report[
        "kernel_polynomial_coefficients"]])
    d_kernel = ring([decode(value) for value in dual_report[
        "dual_kernel_polynomial_coefficients"]])
    forward = source.isogeny(f_kernel, check=True)
    target = forward.codomain()
    assert forward.degree() == ELL
    assert [encode(a) for a in target.ainvs()] == forward_report[
        "codomain_ainvs"]
    dual = target.isogeny(d_kernel, check=True)
    assert dual.degree() == ELL
    iso = dual.codomain().isomorphism_to(source)
    assert [encode(a) for a in iso.tuple()] == dual_report[
        "isomorphism_tuple_to_source"]
    sign = ZZ(dual_report["composition_sign_for_chosen_isomorphism"])
    assert sign in (-1, 1)
    construction_seconds = time.perf_counter() - started
    print("checked maps built", round(construction_seconds, 3), flush=True)

    # These are the only rational points with exceptional group coordinates.
    # They also check the full forward/dual composition away from the large
    # prime subgroup used by the saved generator and public-point fixture.
    assert evaluate_with_kernel(forward, f_kernel, source(0)).is_zero()
    assert evaluate_with_kernel(dual, d_kernel, target(0)).is_zero()
    assert evaluate_with_kernel(forward, f_kernel,
                                source.change_ring(tower)(0)).is_zero()
    assert evaluate_with_kernel(dual, d_kernel,
                                target.change_ring(tower)(0)).is_zero()
    order_two = source([k(0), k(1)])
    assert order_two != source(0) and 2*order_two == source(0)
    mapped_two = forward(order_two)
    assert evaluate_with_kernel(forward, f_kernel, order_two) == mapped_two
    assert not mapped_two.is_zero() and 2*mapped_two == target(0)
    assert sign*iso(dual(mapped_two)) == ELL*order_two
    for fixture in ("source_generator", "source_public_fixture"):
        point = source([decode(value) for value in forward_report[fixture]])
        image = forward(point)
        assert evaluate_with_kernel(forward, f_kernel, point) == image
        assert evaluate_with_kernel(dual, d_kernel, image) == dual(image)
        assert sign*iso(dual(image)) == ELL*point
        lifted_point = source.change_ring(tower)([tower(point[0]), tower(point[1])])
        lifted_image = target.change_ring(tower)([tower(image[0]), tower(image[1])])
        assert evaluate_with_kernel(forward, f_kernel, lifted_point) == lifted_image
        lifted_dual = evaluate_with_kernel(dual, d_kernel, lifted_image)
        expected_dual = dual(image)
        assert lifted_dual == dual.codomain().change_ring(tower)([
            tower(expected_dual[0]), tower(expected_dual[1])])

    def kernel_points(curve, polynomial):
        """Construct both geometric points above each base-field root."""
        roots = sorted(polynomial.roots(multiplicities=False), key=encode)
        assert len(roots) == (ELL - 1)//2
        extended = curve.change_ring(tower)
        for x in roots:
            assert x != 0
            a1, a2, a3, a4, a6 = curve.ainvs()
            assert (a1, a2, a3) == (k(1), k(0), k(0))
            c = (x**3 + a4*x + a6)/(x*x)
            # Trace one rules out an F_(2^131)-rational kernel lift.
            assert c.trace() == 1
            q = halftrace(c + 1)
            assert q*q + q == c + 1
            y = tower(x)*(tower(q) + tower.gen())
            point = extended([tower(x), y])
            assert point != extended(0)
            assert point[0] == tower(x)
            assert -point != point
            yield point, -point

    def raw_exception_status(isogeny, point):
        try:
            image = isogeny._eval(point)
        except (ArithmeticError, ZeroDivisionError) as error:
            return type(error).__name__
        assert image.is_zero()
        return "maps_to_infinity"

    f_started = time.perf_counter()
    f_count = 0
    f_raw_status = None
    for points in kernel_points(source, f_kernel):
        for point in points:
            if f_raw_status is None:
                f_raw_status = raw_exception_status(forward, point)
            assert evaluate_with_kernel(forward, f_kernel, point).is_zero()
            f_count += 1
    assert f_count == ELL - 1
    f_seconds = time.perf_counter() - f_started
    print("forward kernel points checked", f_count, round(f_seconds, 3), flush=True)

    d_started = time.perf_counter()
    d_count = 0
    d_raw_status = None
    for points in kernel_points(target, d_kernel):
        for point in points:
            if d_raw_status is None:
                d_raw_status = raw_exception_status(dual, point)
            assert evaluate_with_kernel(dual, d_kernel, point).is_zero()
            d_count += 1
    assert d_count == ELL - 1
    d_seconds = time.perf_counter() - d_started
    print("dual kernel points checked", d_count, round(d_seconds, 3), flush=True)

    receipt = {
        "kind": "ecc2k130_degree263_exceptional_input_replay",
        "status": "verified",
        "candidate_id": None,
        "sage_version": sage_version,
        "field_degree": N,
        "map_degree": ELL,
        "source_infinity_to_target_infinity": True,
        "target_infinity_to_dual_infinity": True,
        "rational_order_two_composition": True,
        "ordinary_subgroup_wrapper_and_dual_composition": True,
        "ordinary_quadratic_extension_wrapper_agrees": True,
        "forward_kernel_roots": (ELL - 1)//2,
        "forward_nonzero_kernel_points_mapped_to_infinity": f_count,
        "raw_forward_kernel_sample_status": f_raw_status,
        "dual_kernel_roots": (ELL - 1)//2,
        "dual_nonzero_kernel_points_mapped_to_infinity": d_count,
        "raw_dual_kernel_sample_status": d_raw_status,
        "all_kernel_roots_have_no_base_field_y_lift": True,
        "construction_wall_seconds": construction_seconds,
        "forward_kernel_wall_seconds": f_seconds,
        "dual_kernel_wall_seconds": d_seconds,
        "total_wall_seconds": time.perf_counter() - started,
        "forward_report_sha256": sha256(FORWARD_REPORT),
        "dual_report_sha256": sha256(DUAL_REPORT),
        "source_sha256": sha256(Path(__file__)),
        "transport_source_sha256": sha256(TRANSPORT_SOURCE),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
