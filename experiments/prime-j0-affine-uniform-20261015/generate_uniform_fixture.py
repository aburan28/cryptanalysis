#!/usr/bin/env python3
"""Freeze 12,288 unique SHAKE256-derived secp256k1 scalar/point pairs."""

from hashlib import sha256, shake_256
import json
from pathlib import Path
import sys

P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)
DOMAIN = b"prime-j0-uniform-scalar-v1\0"


def add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    x1, y1 = a
    x2, y2 = b
    if x1 == x2:
        if (y1 + y2) % P == 0:
            return None
        slope = (3*x1*x1*pow(2*y1, -1, P)) % P
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


def on_curve(point):
    if point is None:
        return True
    x, y = point
    return 0 <= x < P and 0 <= y < P and (y*y-x*x*x-7) % P == 0


def encode(point):
    return "identity" if point is None else f"{point[0]:064x}:{point[1]:064x}"


def main(base_fixture, output):
    base_bytes = base_fixture.read_bytes()
    base_sha = sha256(base_bytes).hexdigest()
    base = json.loads(base_bytes)["cases"]
    assert len(base) == 128 and on_curve(G) and multiply(N, G) is None
    # Check the reference fixture before using its digest to select the seed.
    for case in base:
        scalar = int(case["scalar_hex"], 16)
        assert 0 < scalar < N
        assert encode(multiply(scalar, G)) == case["point_hex"]
    seed = sha256(DOMAIN + bytes.fromhex(base_sha)).digest()
    seen = set()
    cases = []
    counter = 0
    while len(cases) < 128*96:
        candidate = int.from_bytes(shake_256(
            DOMAIN + seed + counter.to_bytes(8, "big")
        ).digest(32), "big")
        counter += 1
        if not 0 < candidate < N or candidate in seen:
            continue
        point = multiply(candidate, G)
        assert point is not None and on_curve(point)
        seen.add(candidate)
        cases.append({"scalar_hex": f"{candidate:064x}",
                      "point_hex": encode(point)})
    record = {
        "schema": 1,
        "base_fixture_sha256": base_sha,
        "derivation": "SHAKE256(domain || seed || counter_be64), 32 bytes, rejection to 1..n-1 and unique",
        "domain_hex": DOMAIN.hex(),
        "seed_hex": seed.hex(),
        "counters_used": counter,
        "cases": cases,
    }
    output.write_text(json.dumps(record, sort_keys=True, separators=(",", ":"))+"\n")
    print(f"cases={len(cases)} counters={counter} sha256={sha256(output.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
