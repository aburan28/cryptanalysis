#!/usr/bin/env python3
"""Check quotient keys against independent curve Frobenius and negation."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFS = HERE.parent / "ecc2k130-quotient-pair-probe-20260926" / "runs"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey
from run_n23 import frozen


def verify():
    checked = []
    for n in (23, 53, 83):
        path = (HERE / "runs" / "n23_one_target.json") if n == 23 else (
            REFS / f"n{n}_perf_prefix.json")
        receipt = json.loads(path.read_text())
        identity = receipt["curve_identity_record"]
        curve_id = f"EC1N{n}Ckb1h" + hashlib.sha256(frozen(
            identity)).hexdigest()[:12]
        assert receipt["curve_id"] == curve_id
        onb = field.Onb(n)
        curve = curves.Curve(onb)
        orbit = OrbitKey(onb)
        generator = tuple(identity["curve"]["generator"])
        assert curve.mul(generator, identity["curve"]["subgroup_order"]) is None
        for scalar in (1, 2, 19):
            point = curve.mul(generator, scalar)
            key, exponent, sign = orbit.canonical(point)
            canonical_point = curve.frob(point, exponent)
            if sign < 0:
                canonical_point = curve.neg(canonical_point)
            assert orbit.point_from_key(key) == canonical_point
            for shift in (0, 1, n // 2, n - 1):
                shifted = curve.frob(point, shift)
                assert orbit.canonical(shifted)[0] == key
                assert orbit.canonical(curve.neg(shifted))[0] == key
        checked.append(curve_id)
    return {"verified_curve_ids": checked,
            "point_scalars_per_curve": 3,
            "frobenius_shifts_per_point": 4,
            "signs_per_shift": 2}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
