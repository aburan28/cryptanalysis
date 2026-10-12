#!/usr/bin/env python3
"""Build an independent, deterministic secp256k1 scalar-point holdout."""

from hashlib import sha256
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
OUTPUT = HERE / "holdout.json"
SEED = 20261012416
CASES = 512
PRIOR_PANELS = (
    EXP / "prime-j0-sector-digit-20261010/fresh-inputs.json",
    EXP / "prime-j0-radix929-topball-20261012/holdout.json",
    EXP / "prime-j0-split-top-20261012/holdout.json",
    EXP / "prime-j0-radix569-topball-20261012/holdout.json",
)
P = (1 << 256) - (1 << 32) - 977
ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
GX = int("79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798", 16)
GY = int("483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8", 16)


def double(point):
    x, y, z = point
    if z == 0 or y == 0:
        return 0, 1, 0
    yy = y * y % P
    s = 4 * x * yy % P
    m = 3 * x * x % P
    rx = (m * m - 2 * s) % P
    ry = (m * (s - rx) - 8 * yy * yy) % P
    return rx, ry, 2 * y * z % P


def add_generator(point):
    x, y, z = point
    if z == 0:
        return GX, GY, 1
    zz = z * z % P
    u = GX * zz % P
    s = GY * zz * z % P
    h = (u - x) % P
    r = (s - y) % P
    if h == 0:
        return double(point) if r == 0 else (0, 1, 0)
    hh = h * h % P
    hhh = h * hh % P
    v = x * hh % P
    rx = (r * r - hhh - 2 * v) % P
    ry = (r * (v - rx) - y * hhh) % P
    return rx, ry, z * h % P


def multiply(scalar):
    point = (0, 1, 0)
    for bit in range(scalar.bit_length() - 1, -1, -1):
        point = double(point)
        if scalar >> bit & 1:
            point = add_generator(point)
    x, y, z = point
    if z == 0:
        return None
    inv = pow(z, P - 2, P)
    xx = x * inv * inv % P
    yy = y * inv * inv * inv % P
    assert yy * yy % P == (xx * xx * xx + 7) % P
    return xx, yy


def main():
    rng = random.Random(SEED)
    scalars = [rng.getrandbits(256) % ORDER for _ in range(CASES)]
    assert len(set(scalars)) == CASES
    prior_hashes = {}
    for path in PRIOR_PANELS:
        raw = path.read_bytes()
        previous = json.loads(raw)
        values = previous.get("scalars_hex")
        if values is None:
            values = [case["scalar_hex"] for case in previous["cases"]]
        assert set(scalars).isdisjoint(int(value, 16) % ORDER for value in values)
        prior_hashes[str(path.relative_to(EXP))] = sha256(raw).hexdigest()
    cases = []
    for index, scalar in enumerate(scalars):
        point = multiply(scalar)
        cases.append({
            "index": index, "scalar_hex": f"{scalar:064x}",
            "base_x_hex": f"{GX:064x}", "base_y_hex": f"{GY:064x}",
            "expected_identity": point is None,
            "expected_x_hex": None if point is None else f"{point[0]:064x}",
            "expected_y_hex": None if point is None else f"{point[1]:064x}",
        })
    scalar_bytes = b"".join(value.to_bytes(32, "big") for value in scalars)
    fixture = {
        "schema": 1, "curve": "secp256k1", "seed": SEED,
        "input_law": "512 distinct random.Random(seed).getrandbits(256) % subgroup_order scalars",
        "scalar_sha256": sha256(scalar_bytes).hexdigest(),
        "disjoint_prior_panels_sha256": prior_hashes,
        "generator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": cases,
    }
    data = (json.dumps(fixture, indent=2, sort_keys=True) + "\n").encode()
    if "--check" in sys.argv:
        assert OUTPUT.read_bytes() == data
    else:
        if OUTPUT.exists():
            raise SystemExit("holdout already exists; use --check")
        OUTPUT.write_bytes(data)
    print(f"cases={CASES} scalar_sha256={fixture['scalar_sha256']}")


if __name__ == "__main__":
    main()
