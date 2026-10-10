#!/usr/bin/env sage -python
"""Independently replay planted balanced-S3 point chains in checked Sage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

import build_balanced as balanced


HERE = Path(__file__).resolve().parent
PARENT_SAGE = balanced.gate.PARENT / "runs/R1/sage_verification.json"
ORDER = ZZ("680564733841876926932320129493409985129")


def bits(value: int, length: int) -> list[int]:
    return [(value >> index) & 1 for index in range(length)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite Sage control receipt")
    started = time.perf_counter()
    runtime = json.loads(args.runtime_info.read_text())
    parent = json.loads(PARENT_SAGE.read_text())
    if (runtime.get("status") != "verified"
            or parent["status"] != "PASS_SAGE_POINT_AND_BOOLEAN_REPLAY"):
        raise ValueError("checked Sage or planted source control changed")

    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    modulus = t**131 + t**13 + t**2 + t + 1
    if not modulus.is_irreducible():
        raise ArithmeticError("field modulus changed")
    field = GF(2**131, "t", modulus=modulus)
    powers = [field.gen()**index for index in range(131)]
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        value = int(value)
        return sum((powers[index] for index in range(value.bit_length())
                    if value & (1 << index)), field.zero())

    def encode(value):
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def halftrace(value):
        result = field.zero()
        for _ in range(66):
            result += value
            value = value**4
        return result

    controls = {}
    for policy in balanced.POLICIES:
        fixture = parent["planted"][policy]
        masks = [int(value) for value in fixture["selectors"]]
        basis = balanced.ref.words(policy)
        if masks != sorted(masks) or len(masks) != 6:
            raise ArithmeticError("planted selector order changed")
        points = []
        inverses = []
        for index, mask in enumerate(masks):
            if (policy == "normal4_source" and mask.bit_count() != 4
                    or policy == "w24_source" and mask > 11740931):
                raise ArithmeticError("selected leaf outside frozen base")
            parameter = decode(balanced.ref.parameter(basis, mask))
            if not parameter or parameter.trace() != 0:
                raise ArithmeticError("invalid planted parameter")
            u = halftrace(parameter)
            if u*u + u != parameter or (1/parameter).trace() != 0:
                raise ArithmeticError("planted leaf equation failed")
            x = 1 + 1/u
            y = x*halftrace(x + 1/(x*x))
            point = curve([x, y])
            if (encode(x) != fixture["raw_leaf_x"][index]
                    or ORDER*(4*point) != curve(0)):
                raise ArithmeticError("independent planted point mismatch")
            points.append(point)
            inverses.append(encode(1/parameter))
        query = sum(points, curve(0))
        if [encode(query[0]), encode(query[1])] != fixture["source_query"]:
            raise ArithmeticError("planted source query changed")
        nodes = [points[0]+points[1], points[2]+points[3],
                 points[4]+points[5]]
        nodes.append(nodes[0]+nodes[1])
        if any(node.is_zero() for node in nodes) or nodes[3]+nodes[2] != query:
            raise ArithmeticError("balanced point chain has an exceptional node")
        node_x = [encode(node[0]) for node in nodes]
        prog, roots, leaves, chain = balanced.build_ir(policy)
        assignments = {("one", 0): 1}
        for bit, value in enumerate(bits(encode(query[0]), 131)):
            assignments[("target", bit)] = value
        for index, (mask, point, inverse) in enumerate(
                zip(masks, points, inverses)):
            for name, value, width in (
                    ("s", mask, len(basis)), ("x", encode(point[0]), 131),
                    ("z", inverse, 131)):
                for bit, bit_value in enumerate(bits(value, width)):
                    assignments[("%s%d" % (name, index), bit)] = bit_value
        for index, value in enumerate(node_x):
            for bit, bit_value in enumerate(bits(value, 131)):
                assignments[("t%d" % index, bit)] = bit_value
        if any(prog.evaluate(assignments, roots)):
            raise ArithmeticError("balanced Boolean circuit rejected group chain")
        altered = dict(assignments)
        altered[("target", 0)] ^= 1
        if not any(prog.evaluate(altered, roots)):
            raise ArithmeticError("balanced circuit accepted mutated target x")
        controls[policy] = {
            "selectors": [str(mask) for mask in masks],
            "leaf_x": [encode(point[0]) for point in points],
            "balanced_intermediate_x": node_x,
            "source_query": fixture["source_query"],
            "positive_boolean_replay": True,
            "negative_target_x_bit0_rejected": True,
            "finite_intermediate_count": len(nodes),
        }
    result = {
        "schema": "ecc2k130-equalb-balanced-s3-sage-control-v1",
        "status": "PASS_INDEPENDENT_BALANCED_POINT_AND_BOOLEAN_REPLAY",
        "candidate_id": None,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "controls": controls,
        "runtime_info_sha256": balanced.ref.sha(args.runtime_info),
        "parent_sage_receipt_sha256": balanced.ref.sha(PARENT_SAGE),
        "builder_sha256": balanced.ref.sha(HERE / "build_balanced.py"),
        "source_sha256": balanced.ref.sha(Path(__file__)),
        "wall_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "wall_seconds": result["wall_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
