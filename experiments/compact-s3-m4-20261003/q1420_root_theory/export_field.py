#!/usr/bin/env python3
"""Export the verified ONB-to-polynomial bridge for the Q1420 root oracle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def export(n: int) -> str:
    bridge = json.loads((PARENT / "field_bridges" /
                         f"n{n}_onb_poly.json").read_text())
    assert bridge["status"] == "PASS" and bridge["field_degree"] == n
    assert bridge["isogeny"] == "none"
    cycle = bridge["onb_gamma_frobenius_coordinate_cycle"]
    forward = [int(value) for value in bridge["onb_to_poly_basis_images"]]
    inverse = [int(value) for value in bridge["poly_to_onb_basis_images"]]
    low_terms = bridge["target_implementation_basis"]["low_terms"]
    assert len(cycle) == len(forward) == len(inverse) == n
    assert sorted(cycle) == list(range(n))
    modulus_low = sum(1 << exponent for exponent in low_terms)
    # Balanced-S3 leaf bits are Onb.toCoords() gamma_i coordinates, whereas
    # the archived native root index uses a separate Frobenius-cycle order.
    onb_to_poly = forward
    poly_to_onb = inverse
    for j in range(n):
        image = onb_to_poly[j]
        reconstructed = 0
        while image:
            bit = (image & -image).bit_length() - 1
            reconstructed ^= poly_to_onb[bit]
            image &= image - 1
        assert reconstructed == 1 << j
    lines = [f"Q1420FIELD1 {n} {modulus_low:x}"]
    lines.extend(f"{value:x}" for value in onb_to_poly)
    lines.extend(f"{value:x}" for value in poly_to_onb)
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = HERE / f"n{args.degree}_field.txt"
    content = export(args.degree)
    if args.check:
        assert output.read_text() == content
    else:
        assert not output.exists()
        output.write_text(content)
    print(output)


if __name__ == "__main__":
    main()
