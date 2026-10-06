#!/usr/bin/env sage -python
"""Construct a characteristic-two dual from an independent torsion line."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ, set_random_seed
from sage.version import version as sage_version

from sage_construct_ecc2k130_263_isogeny import (
    ELL, N, curve_order_at_degree, field_integer, random_point_over_tower,
)


HERE = Path(__file__).resolve().parent
FORWARD_REPORT = HERE / "ecc2k130_degree263_isogeny_control.json"
SEED = 20260927


def main():
    started = time.perf_counter()
    record = json.loads(FORWARD_REPORT.read_text())
    f2ring = PolynomialRing(GF(2), "t")
    t = f2ring.gen()
    modulus = t**N + t**13 + t**2 + t + 1
    k = GF(2**N, "t", modulus=modulus)

    def decode(value):
        return k(sum(t**index for index in range(value.bit_length())
                     if value & (1 << index)))

    u_ring = PolynomialRing(k, "u")
    u = u_ring.gen()
    l = k.extension(u*u + u + 1, "u")
    source = EllipticCurve(k, [1, 0, 0, 0, 1])
    ring = PolynomialRing(k, "X")
    x = ring.gen()
    forward_kernel = ring([decode(value) for value in
                           record["kernel_polynomial_coefficients"]])
    forward = source.isogeny(forward_kernel, check=False)
    target = forward.codomain()
    assert [field_integer(c) for c in target.ainvs()] == record["codomain_ainvs"]
    print("forward map reconstructed", round(time.perf_counter() - started, 3),
          flush=True)

    set_random_seed(SEED)
    torsion_cofactor = curve_order_at_degree(2 * N) // (ELL * ELL)
    attempts = []
    complement = None
    for index in range(1, 20):
        candidate = torsion_cofactor * random_point_over_tower(
            source.change_ring(l), k, l)
        if candidate.is_zero():
            attempts.append({"attempt": index, "status": "zero"})
            continue
        assert ELL * candidate == source.change_ring(l)(0)
        if forward_kernel(candidate[0]) == 0:
            attempts.append({"attempt": index, "status": "forward_kernel"})
            continue
        complement = candidate
        attempts.append({"attempt": index, "status": "complementary_263_line"})
        break
    assert complement is not None
    image = forward._eval(complement)
    assert not image.is_zero() and ELL * image == image.curve()(0)
    assert image.curve()([image[0] ** (2**N), image[1] ** (2**N)]) == -image
    print("complementary torsion image ready",
          round(time.perf_counter() - started, 3), flush=True)

    dual_kernel = ring.one()
    root_encodings = set()
    multiple = image
    for _ in range((ELL - 1) // 2):
        xi = multiple[0]
        assert xi ** (2**N) == xi
        parts = xi.lift().list()
        assert not any(parts[1:])
        base_x = k(parts[0])
        encoded = field_integer(base_x)
        assert encoded not in root_encodings
        root_encodings.add(encoded)
        dual_kernel *= x - base_x
        multiple += image
    assert dual_kernel.degree() == (ELL - 1) // 2
    print("dual kernel ready", round(time.perf_counter() - started, 3),
          flush=True)

    dual_raw = target.isogeny(dual_kernel, check=True)
    assert dual_raw.degree() == ELL
    assert dual_raw.codomain().is_isomorphic(source)
    iso = dual_raw.codomain().isomorphism_to(source)

    def transported_back(point):
        return iso(dual_raw(point))

    g = source([decode(value) for value in record["source_generator"]])
    public = source([decode(value) for value in record["source_public_fixture"]])
    tg = forward(g)
    tq = forward(public)
    recovered = transported_back(tg)
    if recovered == ELL * g:
        sign = 1
    elif recovered == -ELL * g:
        sign = -1
    else:
        raise AssertionError("raw dual composition is not ±[263] on generator")
    assert transported_back(tq) == sign * ELL * public
    result = {
        "kind": "explicit_ecc2k130_degree263_dual_control",
        "candidate_id": None,
        "sage_version": sage_version,
        "forward_kernel_sha256": record["kernel_polynomial_sha256"],
        "dual_kernel_polynomial_coefficients": [field_integer(c) for c in
                                                 dual_kernel.list()],
        "dual_raw_codomain_ainvs": [field_integer(c) for c in
                                   dual_raw.codomain().ainvs()],
        "dual_raw_codomain_isomorphic_to_source": True,
        "isomorphism_tuple_to_source": [field_integer(c) for c in iso.tuple()],
        "composition_sign_for_chosen_isomorphism": sign,
        "dual_composition_generator": True,
        "dual_composition_public_fixture": True,
        "torsion_attempts": attempts,
        "setup_wall_seconds": time.perf_counter() - started,
        "forward_report_sha256": hashlib.sha256(FORWARD_REPORT.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (HERE / "ecc2k130_degree263_dual_control.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key in ("kind", "composition_sign_for_chosen_isomorphism",
                                 "dual_composition_generator",
                                 "dual_composition_public_fixture",
                                 "setup_wall_seconds")}, indent=2))


if __name__ == "__main__":
    main()
