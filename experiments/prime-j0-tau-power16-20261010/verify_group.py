#!/usr/bin/env python3
"""Independent affine-curve replay of the mixed-width two-bucket identity."""

from hashlib import sha256
import json
from pathlib import Path
import struct

from screen import ORDER, WIDTHS, LIMITS, norm, representative

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
BETA = 0x7AE96A2B657C07106E64479EAC3434E99CF0497512F58995C1396C28719501EE
LAMBDA_TAU = 0xAC9C52B33FA3CF1F5AD9E3FD77ED9BA4A880B9FC8EC739C2E0CFC810B51283D0
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)
PANELS = ("prime-j0-cache-window-20261010", "prime-j0-tau384-matching-20261010")


def negate(point):
    return None if point is None else (point[0], (-point[1]) % P)


def add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2:
        if (y1 + y2) % P == 0:
            return None
        slope = (3 * x1 * x1 * pow(2 * y1, -1, P)) % P
    else:
        slope = ((y2 - y1) * pow((x2 - x1) % P, -1, P)) % P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def multiply(integer, point):
    if integer < 0:
        return multiply(-integer, negate(point))
    result = None
    while integer:
        if integer & 1:
            result = add(result, point)
        point = add(point, point)
        integer >>= 1
    return result


def omega_point(point):
    return None if point is None else (BETA * point[0] % P, point[1])


def tau_point(point):
    return add(point, negate(omega_point(point)))


def unit_point(point, code):
    assert 0 <= code < 6
    for _ in range(code // 2):
        point = omega_point(point)
    return negate(point) if code & 1 else point


def coord_tau(pair):
    a, b = pair
    return -3 * b, a + 3 * b


def coord_unit(pair, code):
    for _ in range(code // 2):
        a, b = pair
        pair = (a + 3 * b, -a - 2 * b)
    return tuple(-part for part in pair) if code & 1 else pair


class Atlas:
    def __init__(self, width):
        raw = (HERE / f"atlas-w{width}.bin").read_bytes()
        assert raw[:4] == b"T2B" + bytes([ord(str(width))])
        self.radix = 1 << width
        self.count = struct.unpack_from("<I", raw, 4)[0]
        expected = 8 + 4 * self.radix * self.radix + 4 * self.count
        assert len(raw) == expected
        self.codes = memoryview(raw)[8:8 + 4 * self.radix * self.radix]
        self.seeds = memoryview(raw)[8 + 4 * self.radix * self.radix:]
        assert self.seed(0) == (0, 0)
        self.sha256 = sha256(raw).hexdigest()

    def seed(self, index):
        assert 0 <= index < self.count
        return struct.unpack_from("<hh", self.seeds, 4 * index)

    def decode(self, a, b):
        residue = (a % self.radix) * self.radix + b % self.radix
        code = struct.unpack_from("<I", self.codes, 4 * residue)[0]
        seed_id, exponent, unit = code >> 4, (code >> 3) & 1, code & 7
        assert seed_id < self.count and unit < 6
        seed = self.seed(seed_id)
        digit = coord_unit(coord_tau(seed) if exponent else seed, unit)
        assert digit[0] % self.radix == a % self.radix
        assert digit[1] % self.radix == b % self.radix
        return digit, seed_id, exponent, unit


def check_panel(name, atlases, bases):
    path = ROOT / "experiments" / name / "fresh-inputs.json"
    raw = path.read_bytes()
    panel = json.loads(raw)
    scalars = [int(value, 16) for value in panel["scalars_hex"]]
    assert len(scalars) == panel["count"] == 4096
    cache = {}
    bucket_counts = [0, 0]
    for case, scalar in enumerate(scalars):
        a, b = representative(scalar % ORDER)
        assert (a + b * LAMBDA_TAU - scalar) % ORDER == 0
        buckets = [None, None]
        for row, (width, (base, tau_base)) in enumerate(zip(WIDTHS, bases)):
            atlas = atlases[width]
            digit, seed_id, exponent, unit = atlas.decode(a, b)
            assert norm(digit) <= LIMITS[width] ** 2
            if seed_id:
                key = (row, seed_id)
                if key not in cache:
                    sa, sb = atlas.seed(seed_id)
                    cache[key] = add(multiply(sa, base), multiply(sb, tau_base))
                buckets[exponent] = add(buckets[exponent], unit_point(cache[key], unit))
                bucket_counts[exponent] += 1
            radix = 1 << width
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0), (name, case)
        actual = add(buckets[0], tau_point(buckets[1]))
        expected = multiply(scalar % ORDER, G)
        assert actual == expected, (name, case)
    return {"cases": len(scalars), "panel_sha256": sha256(raw).hexdigest(),
            "bucket_terms": bucket_counts, "cached_seed_points": len(cache)}


def main():
    assert BETA != 1 and pow(BETA, 3, P) == 1
    assert (G[1] * G[1] - G[0] ** 3 - 7) % P == 0
    assert omega_point(G) == multiply((1 - LAMBDA_TAU) % ORDER, G)
    assert tau_point(G) == multiply(LAMBDA_TAU, G)
    atlases = {width: Atlas(width) for width in (8, 9)}
    bases = []
    base = G
    for width in WIDTHS:
        bases.append((base, tau_point(base)))
        base = multiply(1 << width, base)
    result = {"schema": "prime-j0-tau-power16-group-check-v1",
              "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "atlas_sha256": {str(w): atlas.sha256 for w, atlas in atlases.items()},
              "panels": {name: check_panel(name, atlases, bases) for name in PANELS}}
    (HERE / "group-check.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
