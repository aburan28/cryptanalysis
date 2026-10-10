#!/usr/bin/env sage -python
"""Reconstruct four raw query lifts from the exact source group law."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

import build_four_lift as gate


ORDER = ZZ("680564733841876926932320129493409985129")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite Sage replay receipt")
    started = time.perf_counter()
    runtime = json.loads(args.runtime_info.read_text())
    if runtime.get("status") != "verified":
        raise ValueError("checked Sage runtime did not verify")
    parent = json.loads(gate.LIFTS.read_text())
    public = json.loads(gate.PUBLIC.read_text())
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

    qpair = public["first_16_public_queries"][0]["source"]
    query = curve([decode(qpair[0]), decode(qpair[1])])
    torsion = curve([field.one(), field.one()])
    if (ORDER * query != curve(0) or 4*torsion != curve(0)
            or 2*torsion != curve([field.zero(), field.one()])):
        raise ArithmeticError("subgroup or torsion certificate failed")
    lifts = [query + index*torsion for index in range(4)]
    words = [[encode(point[0]), encode(point[1])] for point in lifts]
    expected = [row["point"] for row in parent["raw_target_lifts"]]
    if (words != expected or len({row[0] for row in words}) != 4
            or any(4*point != 4*query for point in lifts)
            or [row[0] for row in words] != gate.target_lifts()):
        raise ArithmeticError("four-lift point or x replay failed")
    result = {
        "schema": "ecc2k130-equalb-four-lift-sage-replay-v1",
        "status": "PASS_INDEPENDENT_FOUR_RAW_LIFTS",
        "query_index": 0,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "query": qpair,
        "torsion": [encode(torsion[0]), encode(torsion[1])],
        "raw_lift_points": words,
        "all_project_to_four_times_query": True,
        "runtime_info_sha256": gate.ref.sha(args.runtime_info),
        "public_points_sha256": gate.ref.sha(gate.PUBLIC),
        "parent_lift_receipt_sha256": gate.ref.sha(gate.LIFTS),
        "source_sha256": gate.ref.sha(Path(__file__)),
        "wall_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "wall_seconds": result["wall_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
