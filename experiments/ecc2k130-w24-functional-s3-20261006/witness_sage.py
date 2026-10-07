#!/usr/bin/env sage -python
"""Independently replay the constructed planted XCNF witness in Sage."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ

HERE = Path(__file__).resolve().parent
WITNESS = HERE / "runs" / "witness"
BASE = HERE.parent / "ecc2k130-263-equal-w24-workload-20261005"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    started = time.perf_counter()
    report = json.loads((WITNESS / "receipt.json").read_text())
    verified = json.loads((WITNESS / "verification.json").read_text())
    config = json.loads((HERE / "CONFIG.json").read_text())
    base = json.loads((BASE / "base_selection.json").read_text())
    workload = json.loads((BASE / "primary_workload.json").read_text())
    assert report["status"] == "constructed_unverified"
    assert verified["status"] == "PASS_XCNF_WITNESS"
    assert verified["witness_receipt_sha256"] == digest(WITNESS / "receipt.json")
    assert report["sage_runtime_info_sha256"] == digest(
        WITNESS / "runtime-info.json")
    assert config["parent_base_selection_sha256"] == digest(
        BASE / "base_selection.json")
    assert config["parent_primary_workload_sha256"] == digest(
        BASE / "primary_workload.json")
    for name, expected in report["source_sha256"].items():
        assert digest(HERE / name) == expected

    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    modulus = t**131 + t**13 + t**2 + t + 1
    assert modulus.is_irreducible()
    field = GF(2**131, "t", modulus=modulus)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    r = ZZ(workload["subgroup_order"])

    def decode(value):
        value = int(value)
        return field(sum(t**j for j in range(value.bit_length())
                         if (value >> j) & 1))

    def encode(value):
        return sum(int(bit) << j for j, bit in
                   enumerate(value.polynomial().list()))

    def point_words(point):
        return [encode(point[0]), encode(point[1])]

    def halftrace(value):
        total = field.zero()
        term = value
        for _ in range(66):
            total += term
            term = term**4
        assert total**2 + total == value + field(value.trace())
        return total

    basis = [field.gen()**j + (field.gen()**j).trace()
             for j in range(1, 25)]
    masks = base["source"]["control_masks_selection_order"][:6]
    assert report["planted_masks"] == masks
    raw_points, us = [], []
    for mask in masks:
        assert 0 < mask <= config["source_last_selected_mask"]
        w = sum((basis[j] for j in range(24) if mask & (1 << j)),
                field.zero())
        assert w != 0 and w.trace() == 0 and (1/w).trace() == 0
        u = halftrace(w)
        assert u not in (0, 1)
        x = 1 + 1/u
        rhs = x + 1/(x*x)
        assert rhs.trace() == 0
        first = curve([x, x*halftrace(rhs)])
        second = -first
        chosen = min((first, second), key=lambda p: encode(p[1]))
        assert 4*chosen != curve(0) and r*(4*chosen) == curve(0)
        raw_points.append(chosen)
        us.append(u)
    assert report["planted_raw_points"] == [point_words(p) for p in raw_points]
    total = sum(raw_points, curve(0))
    q = 4*total
    assert point_words(q) == report["public_q"] and r*q == curve(0)
    torsion = (curve(0), curve([0, 1]), curve([1, 0]), curve([1, 1]))
    base_lift = ZZ(4).inverse_mod(r)*q
    fibers = tuple(base_lift + point for point in torsion)
    assert [point_words(point) for point in fibers] == report["raw_fibers"]
    assert fibers[report["planted_fiber_index"]] == total
    assert all(4*point == q for point in fibers)

    root_bits = report["root_choice_bits"]
    assert len(root_bits) == 4
    branch_classes = []
    prefix = raw_points[0]
    for slot in range(1, 5):
        next_prefix = prefix + raw_points[slot]
        assert not prefix.is_zero() and not next_prefix.is_zero()
        u1 = 1/(prefix[0]+1)
        u2 = us[slot]
        z = 1/(next_prefix[0]+1)
        assert encode(z) == report["partial_sum_us"][slot-1]
        b = (u1**2+u1)*(u2**2+u2)
        aa = b + 1
        cc = (u1+u2)**2
        if b == 0:
            expected = u1+u2
            branch_classes.append("B0")
        elif aa == 0:
            expected = cc
            branch_classes.append("B1")
        else:
            s = cc*aa/(b*b)
            assert s.trace() == 0
            expected = (b/aa)*(halftrace(s)+field(root_bits[slot-1]))
            branch_classes.append("regular")
        assert z == expected
        assert (aa*z*z+b*z+cc) == 0
        prefix = next_prefix
    assert branch_classes == report["root_branch_classes"]
    result = {
        "schema": "ecc2k130-w24-functional-s3-sage-witness-v1",
        "status": "PASS_PLANTED_GROUP_WITNESS",
        "curve_id": config["curve_id"],
        "source_usable_points_B": config["source_usable_points_B"],
        "public_q": point_words(q),
        "selected_fiber_index": report["planted_fiber_index"],
        "root_branch_classes": branch_classes,
        "witness_receipt_sha256": digest(WITNESS / "receipt.json"),
        "xcnf_verification_sha256": digest(WITNESS / "verification.json"),
        "sage_runtime_info_sha256": digest(WITNESS / "runtime-info.json"),
        "source_sha256": digest(Path(__file__)),
        "replay_seconds": time.perf_counter()-started,
        "candidate_id": None,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    with (WITNESS / "sage_group_replay.json").open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "root_branch_classes": branch_classes}, sort_keys=True))


if __name__ == "__main__":
    main()
