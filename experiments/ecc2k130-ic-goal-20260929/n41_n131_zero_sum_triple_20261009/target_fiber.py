#!/usr/bin/env python3
"""Enumerate the exact raw four-division target fiber for the N41 public row."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ORDER = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = HERE / "target_fiber_result.json"
    if output.exists():
        raise FileExistsError(output)
    runtime = json.loads((HERE / "signature_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def decode(value):
        return field(ring([(int(value) >> i) & 1 for i in range(41)]))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def encoded_point(point):
        return None if point == curve(0) else [encode(point[0]), encode(point[1])]

    def half_trace(value):
        result = field.zero()
        for _ in range(21):
            result += value
            value = value**4
        return result

    lines = (HERE / "input_public.txt").read_text().splitlines()
    qx, qy, subgroup_order, block_count = map(int, lines[0].split())
    assert subgroup_order == ORDER and block_count == 4
    target = curve(decode(qx), decode(qy))
    assert ORDER*target == curve(0)
    row = json.loads((HERE / "public/result.json").read_text())["row"]
    assert len(row) == 12

    raw_members = []
    for leaf in row:
        mask = leaf["mask"]
        w = sum((field(t**(i + 1)) for i in range(7) if mask >> i & 1),
                field.zero())
        u = half_trace(w)**(2**leaf["rotation"])
        possible = curve.lift_x(1 + 1/u, all=True)
        projected = curve(*map(decode, leaf["point"]))
        matching = [point for point in possible if 4*point == projected]
        assert len(matching) == 1
        raw_members.append(matching[0])
    raw_sum = sum(raw_members, curve(0))
    assert 4*raw_sum == target

    torsion = next((ORDER*point for point in raw_members
                    if 4*(ORDER*point) == curve(0) and
                    2*(ORDER*point) != curve(0)), None)
    assert torsion is not None
    subgroup_preimage = pow(4, -1, ORDER)*target
    assert 4*subgroup_preimage == target
    fiber = [subgroup_preimage + i*torsion for i in range(4)]
    assert len(set(fiber)) == 4 and all(4*point == target for point in fiber)
    row_index = fiber.index(raw_sum)

    result = {
        "status": "PASS_RAW_TARGET_FIBER",
        "proposal_id": "Q20261009195000",
        "raw_target_fiber": [encoded_point(point) for point in fiber],
        "order_four_torsion_generator": encoded_point(torsion),
        "subgroup_preimage": encoded_point(subgroup_preimage),
        "public_row_raw_sum": encoded_point(raw_sum),
        "public_row_fiber_index": row_index,
        "scope": "all rational raw sums whose fourfold projection is the frozen N41 public point",
        "sha256": {"source": sha(__file__),
                   "public_input": sha(HERE / "input_public.txt"),
                   "public_result": sha(HERE / "public/result.json"),
                   "runtime": sha(HERE / "signature_runtime_info.json")},
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
