#!/usr/bin/env sage -python
"""Certify all four raw target lifts of a cofactor-four source relation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

import field as ref


HERE = Path(__file__).resolve().parent
PUBLIC = ref.EQUAL / "runs/R1/point16/public_points.json"
ORDER = ZZ("680564733841876926932320129493409985129")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite torsion-lift receipt")
    started = time.perf_counter()
    runtime = json.loads(args.runtime_info.read_text())
    if runtime.get("status") != "verified":
        raise ValueError("checked Sage runtime did not verify")
    public = json.loads(PUBLIC.read_text())
    f2 = GF(2)
    ring = PolynomialRing(f2, "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
    powers = [field.gen()**index for index in range(131)]
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def from_int(value):
        value = int(value)
        return sum((powers[index] for index in range(value.bit_length())
                    if value & (1 << index)), field.zero())

    def to_int(value):
        return sum(int(bit) << index for index, bit in
                   enumerate(value.polynomial().list()))

    def halftrace(value):
        result = field.zero()
        for _ in range(66):
            result += value
            value = value**4
        return result

    qwords = public["first_16_public_queries"][0]["source"]
    query = curve([from_int(qwords[0]), from_int(qwords[1])])
    if ORDER*query != curve(0):
        raise ArithmeticError("ordinary public query left prime subgroup")
    basis = ref.words("w24_source")
    torsion = None
    witness_mask = None
    for row in public["point_controls"]["w24_source"]:
        mask = int(row["mask"])
        w = from_int(ref.parameter(basis, mask))
        u = halftrace(w)
        x = 1 + 1/u
        y = x*halftrace(x+1/(x*x))
        point = curve([x, y])
        candidate = ORDER*point
        if candidate != curve(0) and 2*candidate != curve(0) and 4*candidate == curve(0):
            torsion = candidate
            witness_mask = mask
            break
    if torsion is None:
        raise ArithmeticError("control stream lacks an order-four torsion witness")
    lifts = [query + index*torsion for index in range(4)]
    if len(set(lifts)) != 4 or len({to_int(point[0]) for point in lifts}) != 4:
        raise ArithmeticError("target torsion lifts or x values repeat")
    if any(4*point != 4*query for point in lifts):
        raise ArithmeticError("cofactor-four projection changed across lifts")
    if 2*torsion != curve([field.zero(), field.one()]):
        raise ArithmeticError("order-four witness has wrong 2-torsion")
    receipt = {
        "schema": "ecc2k130-equalb-m6-four-torsion-lifts-v1",
        "status": "PASS_FOUR_EXACT_RAW_TARGET_LIFTS",
        "candidate_id": None,
        "source_curve_id": "EC1N131Ckb1h136f03e58c98",
        "subgroup_order": str(ORDER),
        "cofactor": 4,
        "query_index": 0,
        "query": qwords,
        "torsion_witness_base_mask": witness_mask,
        "torsion_order": 4,
        "torsion_point": [to_int(torsion[0]), to_int(torsion[1])],
        "torsion_double": [to_int((2*torsion)[0]),
                           to_int((2*torsion)[1])],
        "raw_target_lifts": [
            {"torsion_shift": index,
             "point": [to_int(point[0]), to_int(point[1])]}
            for index, point in enumerate(lifts)],
        "distinct_x_coordinates": 4,
        "all_project_to_four_times_query": True,
        "runtime_info_sha256": ref.sha(args.runtime_info),
        "public_input_sha256": ref.sha(PUBLIC),
        "source_sha256": ref.sha(Path(__file__)),
        "wall_seconds": time.perf_counter() - started,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": receipt["status"],
                      "distinct_x_coordinates": 4,
                      "wall_seconds": receipt["wall_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
