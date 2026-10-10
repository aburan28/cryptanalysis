#!/usr/bin/env sage -python
"""Independently replay exact normal4 support and balanced group controls."""

from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

import build_selector as circuit


HERE = Path(__file__).resolve().parent
PUBLIC = circuit.ref.EQUAL / "runs/R1/point16/public_points.json"
PARENT_SAGE = circuit.BALANCED / "runs/R1/sage_balanced.json"
ORDER = ZZ("680564733841876926932320129493409985129")


def positions(mask: int) -> tuple[int, ...]:
    return tuple(bit for bit in range(131) if mask & (1 << bit))


def checked_mask(selected: tuple[int, ...]) -> int:
    if len(selected) != 4 or any(not 0 <= value <= 130 for value in selected):
        raise ValueError("support tuple outside width or range")
    if any(left >= right for left, right in zip(selected, selected[1:])):
        raise ValueError("support tuple not strictly increasing")
    return sum(1 << value for value in selected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite Sage receipt")
    started = time.perf_counter()
    runtime = json.loads(args.runtime_info.read_text())
    prior = json.loads(PARENT_SAGE.read_text())
    public = json.loads(PUBLIC.read_text())
    if (runtime.get("status") != "verified" or prior["status"]
            != "PASS_INDEPENDENT_BALANCED_POINT_AND_BOOLEAN_REPLAY"):
        raise ValueError("Sage runtime or parent control changed")

    small_width_counts = {}
    for width in range(4, 10):
        tuples = list(combinations(range(width), 4))
        masks = {sum(1 << bit for bit in selected) for selected in tuples}
        expected = {mask for mask in range(1 << width)
                    if mask.bit_count() == 4}
        if masks != expected or len(tuples) != len(expected):
            raise ArithmeticError("small-width selector bijection failed")
        small_width_counts[str(width)] = len(tuples)
    for invalid in ((0, 0, 2, 3), (1, 0, 2, 3), (0, 1, 2, 131)):
        try:
            checked_mask(invalid)
        except ValueError:
            pass
        else:
            raise ArithmeticError("invalid support tuple was accepted")

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    modulus = t**131 + t**13 + t**2 + t + 1
    if not modulus.is_irreducible():
        raise ArithmeticError("source field modulus changed")
    field = GF(2**131, "t", modulus=modulus)
    powers = [field.gen()**bit for bit in range(131)]
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    basis = circuit.ref.words("normal4_source")

    def decode(value):
        value = int(value)
        return sum((powers[bit] for bit in range(value.bit_length())
                    if value & (1 << bit)), field.zero())

    def encode(value):
        return sum(int(coefficient) << bit for bit, coefficient in
                   enumerate(value.polynomial().list()))

    def halftrace(value):
        result = field.zero()
        for _ in range(66):
            result += value
            value = value**4
        return result

    replayed = {}
    controls = public["point_controls"]["normal4_source"]
    for row in controls:
        mask = int(row["normal_mask_decimal"])
        selected = positions(mask)
        if checked_mask(selected) != mask:
            raise ArithmeticError("normal4 mask did not round-trip")
        w = decode(circuit.ref.parameter(basis, mask))
        if not w or w.trace() != 0 or (1/w).trace() != 0:
            raise ArithmeticError("sample normal4 parameter is not rational")
        u = halftrace(w)
        if u*u + u != w:
            raise ArithmeticError("sample halftrace equation failed")
        x = 1 + 1/u
        y = x*halftrace(x + 1/(x*x))
        raw = curve([x, y])
        point = 4*raw
        if ([encode(point[0]), encode(point[1])] != row["source"]
                or ORDER*point != curve(0)):
            raise ArithmeticError("sample source point changed")
        replayed[mask] = raw

    high_mask = sum(1 << bit for bit in (0, 1, 2, 130))
    if checked_mask(positions(high_mask)) != high_mask:
        raise ArithmeticError("high-position mask did not round-trip")
    high_w = decode(circuit.ref.parameter(basis, high_mask))
    if not high_w or high_w.trace() != 0 or (1/high_w).trace() != 0:
        raise ArithmeticError("high-position control is not rational")
    high_u = halftrace(high_w)
    if high_u*high_u + high_u != high_w:
        raise ArithmeticError("high-position halftrace equation failed")
    high_x = 1 + 1/high_u
    high_y = high_x*halftrace(high_x + 1/(high_x*high_x))
    high_raw = curve([high_x, high_y])
    if high_raw.is_zero() or ORDER*(4*high_raw) != curve(0):
        raise ArithmeticError("high-position projected point changed")

    fixture = prior["controls"]["normal4_source"]
    planted_masks = [int(mask) for mask in fixture["selectors"]]
    if planted_masks != sorted(planted_masks) or len(planted_masks) != 6:
        raise ArithmeticError("planted source selectors changed")
    points = [replayed[mask] for mask in planted_masks]
    query = sum(points, curve(0))
    nodes = [points[0]+points[1], points[2]+points[3],
             points[4]+points[5]]
    nodes.append(nodes[0]+nodes[1])
    if (any(point.is_zero() for point in nodes)
            or nodes[3]+nodes[2] != query
            or [encode(query[0]), encode(query[1])]
            != fixture["source_query"]
            or [encode(point[0]) for point in nodes]
            != fixture["balanced_intermediate_x"]):
        raise ArithmeticError("planted balanced point tree changed")
    receipt = {
        "schema": "ecc2k130-normal4-selector-sage-v1",
        "status": "PASS_128_POINTS_SUPPORT_BIJECTION_AND_BALANCED_TREE",
        "candidate_id": None,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "point_controls": len(controls),
        "high_position_control": {"mask": str(high_mask),
                                  "raw_x": str(encode(high_x)),
                                  "projected_x": str(encode((4*high_raw)[0]))},
        "small_width_counts": small_width_counts,
        "planted_selectors": [str(mask) for mask in planted_masks],
        "planted_query": fixture["source_query"],
        "runtime_info_sha256": circuit.ref.sha(args.runtime_info),
        "public_input_sha256": circuit.ref.sha(PUBLIC),
        "parent_sage_sha256": circuit.ref.sha(PARENT_SAGE),
        "source_sha256": circuit.ref.sha(Path(__file__)),
        "wall_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "point_controls", "wall_seconds")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
