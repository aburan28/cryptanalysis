#!/usr/bin/env python3
"""Derive exact ONB-to-polynomial field maps for the frozen n53/n83 curves.

The implementation basis changes; the mathematical curve, subgroup,
generator, factor base, and public target do not. The bridge is an exact
F2-linear isomorphism with independently checked multiplication and group
law on deterministic controls.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector

from run_probe import HERE, curves, field, sha

MODULI = {
    53: (0, 1, 2, 6),
    83: (0, 2, 4, 7),
}
SEEDS = {53: 530327, 83: 830327}


def element_bits(element):
    return sum(int(value) << index
               for index, value in enumerate(element.polynomial().list()))


def xor_images(mask, images):
    result = 0
    while mask:
        bit = mask & -mask
        result ^= images[bit.bit_length() - 1]
        mask ^= bit
    return result


def poly_element(poly_field, integer):
    return sum((poly_field.gen() ** index)
               for index in range(poly_field.degree())
               if integer >> index & 1)


def basis_bridge(n):
    onb = field.Onb(n)
    degree = onb.m
    assert degree == n
    f2 = GF(2)
    ring = PolynomialRing(f2, "z")
    z = ring.gen()
    modulus = z ** n + sum(z ** degree for degree in MODULI[n])
    assert modulus.is_irreducible()
    poly_field = GF(2 ** n, f"u{n}", modulus=modulus)

    gamma = onb.fromCoords(1)
    powers = [onb.one()]
    for _ in range(n):
        powers.append(onb.mul(powers[-1], gamma))
    coords = [onb.toCoords(value) for value in powers]
    power_matrix = matrix(f2, n, n,
                          lambda row, col: (coords[col] >> row) & 1)
    assert power_matrix.rank() == n
    right = vector(f2, [(coords[n] >> row) & 1 for row in range(n)])
    coeffs = power_matrix.solve_right(right)
    minpoly = z ** n + sum(int(coeffs[index]) * z ** index
                          for index in range(n))
    assert minpoly.is_irreducible()
    roots = minpoly.change_ring(poly_field).roots()
    assert len(roots) == n and all(multiplicity == 1
                                   for _, multiplicity in roots)
    root = min((candidate for candidate, _ in roots), key=element_bits)
    root_bits = element_bits(root)

    positions = []
    current_onb = gamma
    current_poly = root
    onb_to_poly = [None] * n
    for _ in range(n):
        coords_mask = onb.toCoords(current_onb)
        assert coords_mask.bit_count() == 1
        position = coords_mask.bit_length() - 1
        assert position not in positions
        positions.append(position)
        onb_to_poly[position] = element_bits(current_poly)
        current_onb = onb.sqr(current_onb)
        current_poly = current_poly ** 2
    assert current_onb == gamma and current_poly == root
    assert sorted(positions) == list(range(n))
    assert all(value is not None for value in onb_to_poly)
    bridge_matrix = matrix(f2, n, n, lambda row, col:
                           (onb_to_poly[col] >> row) & 1)
    assert bridge_matrix.rank() == n
    inverse_matrix = bridge_matrix.inverse()
    poly_to_onb = [sum(int(inverse_matrix[row, col]) << row
                       for row in range(n)) for col in range(n)]
    assert all(xor_images(onb_to_poly[index], poly_to_onb) == (1 << index)
               for index in range(n))
    assert all(xor_images(poly_to_onb[index], onb_to_poly) == (1 << index)
               for index in range(n))
    assert xor_images(onb.toCoords(onb.one()), onb_to_poly) == 1

    rng = random.Random(SEEDS[n])
    multiplication_controls = 128
    for _ in range(multiplication_controls):
        left_coords = rng.getrandbits(n)
        right_coords = rng.getrandbits(n)
        left = onb.fromCoords(left_coords)
        right = onb.fromCoords(right_coords)
        left_poly = poly_element(poly_field,
                                 xor_images(left_coords, onb_to_poly))
        right_poly = poly_element(poly_field,
                                  xor_images(right_coords, onb_to_poly))
        assert xor_images(onb.toCoords(onb.mul(left, right)),
                          onb_to_poly) == element_bits(left_poly * right_poly)
        assert xor_images(onb.toCoords(onb.sqr(left)),
                          onb_to_poly) == element_bits(left_poly ** 2)
        if right_coords:
            assert xor_images(onb.toCoords(onb.inv(right)),
                              onb_to_poly) == element_bits(right_poly ** -1)

    baseline_path = HERE / "runs" / f"n{n}_ordinary_frozen.json"
    baseline = json.loads(baseline_path.read_text())
    curve = curves.Curve(onb)
    curve_poly = EllipticCurve(poly_field, [1, 0, 0, 0, 1])
    target = tuple(map(int, baseline["public_subgroup_target"]))
    assert curve.onCurve(target)
    archive_path = HERE / "bases" / (
        f"n{n}_weight{3 if n == 53 else 4}_orbits.json.gz")
    with gzip.open(archive_path, "rt") as stream:
        archive = json.load(stream)
    order = int(archive["curve"]["subgroup_order"])
    assert baseline["curve_id"] == archive["curve"]["curve_id"]
    assert baseline["factor_base_archive_sha256"] == sha(archive_path)
    assert curve.mul(target, order) is None

    def mapped_point(point):
        return curve_poly(
            poly_element(poly_field, xor_images(
                onb.toCoords(point[0]), onb_to_poly)),
            poly_element(poly_field, xor_images(
                onb.toCoords(point[1]), onb_to_poly)))

    mapped_target = mapped_point(target)
    assert order * mapped_target == curve_poly(0)
    group_controls = 0
    points = [target, tuple(map(int, archive["curve"]["generator"]))]
    for _ in range(16):
        while True:
            x = onb.fromCoords(rng.getrandbits(n))
            point = curve.pointFromX(x)
            if point is not None:
                points.append(point)
                break
    for left, right in zip(points[::2], points[1::2]):
        source_sum = curve.add(left, right)
        target_sum = mapped_point(left) + mapped_point(right)
        assert target_sum == (mapped_point(source_sum)
                              if source_sum is not None else curve_poly(0))
        group_controls += 1

    runtime_path = HERE / "bridge_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    mapped_generator = mapped_point(points[1])
    return {
        "kind": "exact_type_ii_onb_to_polynomial_field_bridge",
        "field_degree": n,
        "curve_id": baseline["curve_id"],
        "isogeny": "none",
        "changes_curve_identity": False,
        "source_basis": archive["field"],
        "target_implementation_basis": {
            "name": "polynomial_basis_for_fast_root_arithmetic",
            "defining_modulus": str(modulus),
            "low_terms": list(MODULI[n]),
            "element_encoding": "unsigned integer with bit i the z^i coefficient",
        },
        "onb_gamma_minpoly": str(minpoly),
        "chosen_gamma_image_poly_bits": root_bits,
        "onb_gamma_frobenius_coordinate_cycle": positions,
        "onb_to_poly_basis_images": onb_to_poly,
        "poly_to_onb_basis_images": poly_to_onb,
        "subgroup_order": order,
        "mapped_public_target_poly": [element_bits(mapped_target[0]),
                                      element_bits(mapped_target[1])],
        "mapped_generator_poly": [element_bits(mapped_generator[0]),
                                  element_bits(mapped_generator[1])],
        "multiplication_square_inverse_controls": multiplication_controls,
        "group_addition_controls": group_controls,
        "deterministic_control_seed": SEEDS[n],
        "status": "PASS",
        "baseline_receipt_sha256": sha(baseline_path),
        "base_archive_sha256": sha(archive_path),
        "runtime_info_sha256": sha(runtime_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = HERE / "field_bridges" / f"n{args.n}_onb_poly.json"
    report = basis_bridge(args.n)
    content = json.dumps(report, indent=2) + "\n"
    if args.check:
        assert output.read_text() == content
    else:
        assert not output.exists()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
    print(json.dumps({"n": args.n, "curve_id": report["curve_id"],
                      "status": report["status"],
                      "gamma_image": report[
                          "chosen_gamma_image_poly_bits"]}))


if __name__ == "__main__":
    main()
