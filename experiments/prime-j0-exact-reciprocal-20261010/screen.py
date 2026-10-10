#!/usr/bin/env python3
"""Exact reciprocal lattice-cell audit with independent point replay."""

import argparse
import hashlib
import json
from math import gcd
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = ROOT / "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed.rs"
FROZEN = ROOT / "experiments/prime-j0-radix943-word-20261009/inputs.json"
FRESH = HERE / "fresh-inputs.json"
RESULT = HERE / "screen-result.json"
N = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
P = 2**256 - 2**32 - 977
GX = int("79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798", 16)
GY = int("483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8", 16)
LAMBDA_TAU = int("ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0", 16)
U0 = 193508920647619669885755136084601127231
U1 = 238911465918039986966665730306072050094
V0 = -U1
V1 = 303414439467246543595250775667605759171
W0 = U0 - 2 * V0
W1 = U1 - 2 * V1
BIT_SHIFT = 512
SEED = 20261010163
FRESH_COUNT = 4096


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar_digest(values):
    return hashlib.sha256(b"".join(k.to_bytes(32, "big") for k in values)).hexdigest()


def check_source_constants():
    source = SOURCE.read_text()
    for decimal in (str(U0), str(U1), str(V1)):
        assert f'b"{decimal}"' in source, decimal
    for hexadecimal in (f"{N:064x}", f"{LAMBDA_TAU:064x}",
                        f"{GX:064x}", f"{GY:064x}"):
        assert hexadecimal in source, hexadecimal
    assert U0 * V1 - U1 * V0 == N
    assert 0 < V1 < N and 0 < -W1 < N
    assert gcd(V1, N) == gcd(-W1, N) == 1
    assert (U0 + U1 * LAMBDA_TAU) % N == 0
    assert (V0 + V1 * LAMBDA_TAU) % N == 0


def corners(k, fw, fv):
    entries = []
    for dw in (0, 1):
        for dv in (0, 1):
            a = k - (fw + dw) * W0 - (fv + dv) * V0
            b = -(fw + dw) * W1 - (fv + dv) * V1
            norm = a * a + 3 * a * b + 3 * b * b
            entries.append((norm, max(abs(a), abs(b)), a, b))
    return sorted(entries)


def reciprocal(c, n=N, bits=BIT_SHIFT):
    assert 0 < c < n and gcd(c, n) == 1
    return (1 << bits) * c // n


def exact_floor(k, c, r, bits=BIT_SHIFT):
    return k * r >> bits


def small_prime_controls():
    checked = 0
    for n in range(3, 252):
        if any(n % p == 0 for p in range(2, int(n**0.5) + 1)):
            continue
        bits = 2 * n.bit_length()
        for c in range(1, n):
            r = reciprocal(c, n, bits)
            for k in range(n):
                assert exact_floor(k, c, r, bits) == k * c // n, (n, c, k)
                checked += 1
    return checked


def add(p, q):
    if p is None:
        return q
    if q is None:
        return p
    x1, y1 = p
    x2, y2 = q
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if x1 == x2:
        m = 3 * x1 * x1 * pow(2 * y1, -1, P) % P
    else:
        m = (y2 - y1) * pow(x2 - x1, -1, P) % P
    x3 = (m * m - x1 - x2) % P
    return x3, (m * (x1 - x3) - y1) % P


def multiply(k, point):
    if k < 0:
        return multiply(-k, (point[0], -point[1] % P))
    out = None
    while k:
        if k & 1:
            out = add(out, point)
        point = add(point, point)
        k >>= 1
    return out


def generate():
    if FRESH.exists():
        raise SystemExit("fresh input file already exists")
    check_source_constants()
    frozen = json.loads(FROZEN.read_text())
    old = {int(value, 16) for value in frozen["scalars_hex"]}
    rng = random.Random(SEED)
    values = []
    seen = set(old)
    while len(values) < FRESH_COUNT:
        k = rng.randrange(N)
        if k not in seen:
            values.append(k)
            seen.add(k)
    record = {"schema": 1, "seed": SEED, "count": len(values),
              "frozen_source_sha256": sha(FROZEN),
              "scalar_sha256": scalar_digest(values),
              "scalars_hex": [f"{k:064x}" for k in values]}
    FRESH.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"count": len(values), "scalar_sha256": record["scalar_sha256"]}))


def audit():
    if RESULT.exists():
        raise SystemExit("screen result already exists")
    check_source_constants()
    frozen = json.loads(FROZEN.read_text())
    fresh = json.loads(FRESH.read_text())
    frozen_values = [int(value, 16) for value in frozen["scalars_hex"]]
    fresh_values = [int(value, 16) for value in fresh["scalars_hex"]]
    assert len(frozen_values) == 519 and len(fresh_values) == FRESH_COUNT
    assert scalar_digest(frozen_values) == frozen["scalar_sha256"]
    assert scalar_digest(fresh_values) == fresh["scalar_sha256"]
    assert fresh["frozen_source_sha256"] == sha(FROZEN)
    assert not set(frozen_values) & set(fresh_values)
    r_w = reciprocal(V1)
    r_v = reciprocal(-W1)
    assert r_w.bit_length() <= 385 and r_v.bit_length() <= 386
    point = (GX, GY)
    tau_point = multiply(LAMBDA_TAU, point)
    checked = 0
    point_replays = 0
    max_coordinate_bits = 0
    for k in [0, N - 1] + frozen_values + fresh_values:
        assert 0 <= k < N
        fw = exact_floor(k, V1, r_w)
        fv = exact_floor(k, -W1, r_v)
        assert fw == k * V1 // N and fv == k * (-W1) // N
        candidate = corners(k, fw, fv)
        reference = corners(k, k * V1 // N, k * (-W1) // N)
        assert candidate == reference
        a, b = candidate[0][2:]
        assert (a + b * LAMBDA_TAU - k) % N == 0
        max_coordinate_bits = max(max_coordinate_bits, abs(a).bit_length(), abs(b).bit_length())
        if checked >= 2 + len(frozen_values) and point_replays < 128:
            assert add(multiply(a, point), multiply(b, tau_point)) == multiply(k, point)
            point_replays += 1
        checked += 1
    result = {"schema": 1, "status": "passed", "quotients_and_corner_lists_checked": checked,
              "small_prime_quotients_checked": small_prime_controls(),
              "independent_fresh_point_replays": point_replays,
              "maximum_chosen_coordinate_bits": max_coordinate_bits,
              "reciprocals_hex": {"v1": hex(r_w), "minus_w1": hex(r_v)},
              "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in
                                (SOURCE, FROZEN, FRESH, HERE / "PROTOCOL.md", Path(__file__))},
              "fresh_scalar_sha256": fresh["scalar_sha256"]}
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "quotients_and_corner_lists_checked",
                                         "small_prime_quotients_checked",
                                         "independent_fresh_point_replays")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "audit"))
    args = parser.parse_args()
    {"generate": generate, "audit": audit}[args.command]()
