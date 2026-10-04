#!/usr/bin/env sage -python
"""Rebuild and independently verify the saved ECC2K-130 degree-263 map."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ
from sage.version import version as sage_version


HERE = Path(__file__).resolve().parent
REPORT = HERE / "ecc2k130_degree263_isogeny_control.json"
DUAL_REPORT = HERE / "ecc2k130_degree263_dual_control.json"
SOURCE = HERE / "sage_construct_ecc2k130_263_isogeny.py"


def main():
    started = time.perf_counter()
    report = json.loads(REPORT.read_text())
    assert report["source_sha256"] == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    f2ring = PolynomialRing(GF(2), "t")
    t = f2ring.gen()
    modulus = t**131 + t**13 + t**2 + t + 1
    assert modulus.is_irreducible()
    field = GF(2**131, "t", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(sum(t**index for index in range(value.bit_length())
                         if value & (1 << index)))

    def encode(value):
        return sum(int(bit) << index
                   for index, bit in enumerate(value.polynomial().list()))

    def source_point(pair):
        return curve([decode(pair[0]), decode(pair[1])])

    polyring = PolynomialRing(field, "X")
    coefficients = report["kernel_polynomial_coefficients"]
    assert len(coefficients) == 132 and coefficients[-1] == 1
    assert hashlib.sha256(json.dumps(coefficients, separators=(",", ":")).encode()
                          ).hexdigest() == report["kernel_polynomial_sha256"]
    kernel = polyring([decode(value) for value in coefficients])
    print("reconstructed kernel", round(time.perf_counter() - started, 3), flush=True)

    # check=True tests the division-polynomial identity and cyclic subgroup
    # stability independently of the torsion point used to generate the input.
    isogeny = curve.isogeny(kernel, check=True)
    codomain = isogeny.codomain()
    assert isogeny.degree() == 263
    assert isogeny.kernel_polynomial().monic().list() == kernel.monic().list()
    assert codomain.j_invariant() != curve.j_invariant()
    assert [encode(value) for value in codomain.ainvs()] == report["codomain_ainvs"]
    assert encode(codomain.j_invariant()) == report["codomain_j"]
    print("independent cyclic-kernel check passed",
          round(time.perf_counter() - started, 3), flush=True)

    g = source_point(report["source_generator"])
    public = source_point(report["source_public_fixture"])
    scalar = ZZ(report["fixture_scalar"])
    subgroup_order = ZZ(report["subgroup_order"])
    assert not g.is_zero() and subgroup_order * g == curve(0)
    assert public == scalar * g
    transported = isogeny(g)
    mapped_public = isogeny(public)
    assert [encode(transported[0]), encode(transported[1])] == report[
        "transported_generator"]
    assert [encode(mapped_public[0]), encode(mapped_public[1])] == report[
        "transported_public_fixture"]
    assert mapped_public == scalar * transported
    assert not transported.is_zero() and subgroup_order * transported == codomain(0)
    assert isogeny(7 * g) == 7 * transported

    dual_report = json.loads(DUAL_REPORT.read_text())
    assert dual_report["forward_kernel_sha256"] == report[
        "kernel_polynomial_sha256"]
    dual_kernel = polyring([decode(value) for value in dual_report[
        "dual_kernel_polynomial_coefficients"]])
    dual_raw = codomain.isogeny(dual_kernel, check=True)
    assert dual_raw.degree() == 263
    assert [encode(value) for value in dual_raw.codomain().ainvs()] == dual_report[
        "dual_raw_codomain_ainvs"]
    iso = dual_raw.codomain().isomorphism_to(curve)
    assert [encode(value) for value in iso.tuple()] == dual_report[
        "isomorphism_tuple_to_source"]
    sign = ZZ(dual_report["composition_sign_for_chosen_isomorphism"])
    assert sign in (-1, 1)
    assert sign * iso(dual_raw(transported)) == 263 * g
    assert sign * iso(dual_raw(mapped_public)) == 263 * public
    print("independent dual composition check passed",
          round(time.perf_counter() - started, 3), flush=True)

    result = {
        "kind": "independent_sage_ecc2k130_degree263_isogeny_replay",
        "candidate_id": None,
        "sage_version": sage_version,
        "cyclic_kernel_check": True,
        "map_degree": 263,
        "codomain_j_differs": True,
        "source_and_target_subgroup_checks": True,
        "fixture_scalar_replay": True,
        "dual_composition_on_two_points": True,
        "dual_status": "explicit_dual_kernel_replayed",
        "replay_wall_seconds": time.perf_counter() - started,
        "input_report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        "dual_report_sha256": hashlib.sha256(DUAL_REPORT.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (HERE / "ecc2k130_degree263_isogeny_sage_replay.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ("source_sha256", "input_report_sha256",
                                     "dual_report_sha256")},
                     indent=2))


if __name__ == "__main__":
    main()
