#!/usr/bin/env python3
"""Independently check the selected digit certificate and secp256k1 eigenvalue."""

from hashlib import sha256
import argparse
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
V = (-238911465918039986966665730306072050094,
     303414439467246543595250775667605759171)
LAMBDA = (-V[0] * pow(V[1], -1, N)) % N
RADIX = 1024
BOUND = 149


def digest(raw):
    return sha256(raw).hexdigest()


def group_add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if x1 == x2:
        slope = 3 * x1 * x1 * pow(2 * y1, -1, P)
    else:
        slope = (y2 - y1) * pow((x2 - x1) % P, -1, P)
    slope %= P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def group_mul(scalar, point):
    total = None
    while scalar:
        if scalar & 1:
            total = group_add(total, point)
        point = group_add(point, point)
        scalar >>= 1
    return total


def tau(pair):
    a, b = pair
    return -3 * b, a + 3 * b


def omega(pair):
    a, b = pair
    return a + 3 * b, -a - 2 * b


def rho(pair):
    a, b = pair
    return a - 3 * b, a + 4 * b


def norm(pair):
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def mapped(seed, map_id):
    assert 0 <= map_id <= 3
    pair = seed if map_id != 3 else rho(seed)
    for _ in range(map_id if map_id < 3 else 0):
        pair = tau(pair)
    return pair


def unit_image(pair, unit_code):
    assert 0 <= unit_code < 6
    for _ in range(unit_code // 2):
        pair = omega(pair)
    if unit_code & 1:
        pair = -pair[0], -pair[1]
    return pair


def verify_eigenvalue():
    generator = (GX, GY)
    assert (GY * GY - GX * GX * GX - 7) % P == 0
    assert (LAMBDA * LAMBDA - 3 * LAMBDA + 3) % N == 0
    # The lattice basis uses tau = 1 - omega, with omega^3 = 1.
    image = group_mul((1 - LAMBDA) % N, generator)
    assert image is not None and image[1] == GY
    beta = next(pow(base, (P - 1) // 3, P) for base in range(2, 100)
                if pow(base, (P - 1) // 3, P) != 1)
    assert pow(beta, 3, P) == 1
    assert image[0] in {(beta * GX) % P, (beta * beta * GX) % P}
    return image[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-panel", type=Path, required=True)
    args = parser.parse_args()
    input_raw = (HERE / "holdout-inputs.json").read_bytes()
    receipt = json.loads((HERE / "holdout-screen-width2.json").read_bytes())
    path_raw = (HERE / "holdout-paths-width2.jsonl").read_bytes()
    cover_raw = (ROOT / "prime-j0-dual-orbit-20261011" /
                 "cover-priority-rho0.bin").read_bytes()
    assert digest(input_raw) == receipt["input_sha256"]
    assert digest(path_raw) == receipt["certificate_sha256"]
    assert digest(cover_raw) == receipt["cover_sha256"]
    assert digest((HERE / "screen.py").read_bytes()) == receipt["source_sha256"]
    inputs = json.loads(input_raw)
    assert inputs["candidate_source_sha256"] == receipt["source_sha256"]
    assert inputs["candidate_beam_width"] == 2
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", cover_raw)
    assert (magic, radix, classes, count, mask) == (b"LP21", 1024, 174764, 67338, 15)
    seeds = list(struct.iter_unpack("<hh", cover_raw[20 + 4 * classes:]))
    assert len(seeds) == count
    scalars = [int(value, 16) for value in inputs["scalars_hex"]]
    reduced = {value % N for value in scalars}
    assert len(reduced) == len(scalars)
    for name, expected_hash in inputs["source_sha256"].items():
        source = args.direct_panel if name == \
            "prime-j0-direct-rho-20261011/fresh-inputs.json" else ROOT / name
        prior_raw = source.read_bytes()
        assert digest(prior_raw) == expected_hash, name
        prior_reduced = {int(value, 16) % N for value in
                         json.loads(prior_raw)["scalars_hex"]}
        assert reduced.isdisjoint(prior_reduced), name
    lines = path_raw.splitlines()
    assert len(lines) == len(scalars) == receipt["cases"] == 4096
    active = rho_terms = terms = 0
    terminal_max = 0
    verify_eigenvalue()
    for index, (scalar, line) in enumerate(zip(scalars, lines)):
        entry = json.loads(line)
        assert entry["index"] == index
        assert len(entry["digits"]) == 12
        a, b = map(int, entry["terminal"])
        terminal_norm = norm((a, b))
        assert terminal_norm < BOUND * BOUND
        terminal_max = max(terminal_max, terminal_norm)
        rho_this = 0
        for row in reversed(entry["digits"]):
            da, db, seed_id, map_id, unit_code = map(int, row)
            assert 0 <= seed_id < len(seeds)
            assert (da, db) == unit_image(mapped(seeds[seed_id], map_id), unit_code)
            assert norm((da, db)) <= RADIX * RADIX
            a, b = RADIX * a + da, RADIX * b + db
            terms += seed_id != 0
            rho_this += seed_id != 0 and map_id == 3
        assert (a + b * LAMBDA - scalar) % N == 0
        active += rho_this != 0
        rho_terms += rho_this
    expected = receipt["carry_aware"]
    assert (active, rho_terms, terms, terminal_max) == \
        (expected["active_rho_cases"], expected["rho_terms"],
         expected["nonzero_full_window_terms"],
         expected["max_terminal_norm"])
    result = {"schema": 1, "status": "passed", "cases": len(lines),
              "active_rho_cases": active, "rho_terms": rho_terms,
              "nonzero_full_window_terms": terms,
              "terminal_maximum_norm": terminal_max,
              "certificate_sha256": digest(path_raw),
              "verifier_sha256": digest(Path(__file__).read_bytes())}
    (HERE / "holdout-verify.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
