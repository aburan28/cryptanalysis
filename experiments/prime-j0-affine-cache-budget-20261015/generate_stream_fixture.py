#!/usr/bin/env python3
"""Derive 96 distinct-scalar batches from the frozen 128-point fixture."""

from hashlib import sha256
import json
from pathlib import Path
import sys

P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def on_curve(point):
    if point is None:
        return True
    x, y = point
    return 0 <= x < P and 0 <= y < P and (y*y-x*x*x-7) % P == 0


def add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    x1, y1 = a
    x2, y2 = b
    if x1 == x2:
        if (y1+y2) % P == 0:
            return None
        slope = (3*x1*x1 * pow(2*y1, -1, P)) % P
    else:
        slope = ((y2-y1)*pow(x2-x1, -1, P)) % P
    x3 = (slope*slope-x1-x2) % P
    y3 = (slope*(x1-x3)-y1) % P
    return x3, y3


def multiply(k, point):
    total = None
    while k:
        if k & 1:
            total = add(total, point)
        point = add(point, point)
        k >>= 1
    return total


def encode(point):
    return "identity" if point is None else f"{point[0]:064x}:{point[1]:064x}"


def main(source, output):
    source_bytes = source.read_bytes()
    fixture_sha = sha256(source_bytes).hexdigest()
    base = json.loads(source_bytes)["cases"]
    assert len(base) == 128 and on_curve(G) and multiply(N, G) is None
    base_points = []
    for case in base:
        scalar = int(case["scalar_hex"], 16)
        text = case["point_hex"]
        x, y = (int(part, 16) for part in text.split(":"))
        point = x, y
        assert 0 < scalar < N and on_curve(point)
        assert encode(multiply(scalar, G)) == text
        base_points.append((scalar, point))
    step = int.from_bytes(sha256(
        b"prime-j0-affine-stream-v1\0" + bytes.fromhex(fixture_sha)
    ).digest(), "big") % N
    assert step != 0
    delta = multiply(step, G)
    assert delta is not None and on_curve(delta)
    cases = []
    offset_point = None
    seen = set()
    for repeat in range(96):
        for scalar, point in base_points:
            shifted_scalar = (scalar + repeat*step) % N
            shifted_point = add(point, offset_point)
            assert shifted_scalar not in seen and on_curve(shifted_point)
            seen.add(shifted_scalar)
            cases.append({"scalar_hex": f"{shifted_scalar:064x}",
                          "point_hex": encode(shifted_point)})
        offset_point = add(offset_point, delta)
    assert len(cases) == 12288
    record = {
        "schema": 1,
        "base_fixture_sha256": fixture_sha,
        "step_scalar_hex": f"{step:064x}",
        "step_point_hex": encode(delta),
        "input_law": "128 frozen scalars plus j*step modulo subgroup order, j=0..95",
        "cases": cases,
    }
    output.write_text(json.dumps(record, sort_keys=True, separators=(",", ":"))+"\n")
    print(f"cases={len(cases)} sha256={sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
