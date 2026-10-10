#!/usr/bin/env python3
"""Checked-Sage reconstruction of N41 collision prefixes and sampled ranks."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing, EllipticCurve, matrix

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lift(F, value):
    t = F.gen()
    out = F.zero()
    while value:
        bit = value.bit_length() - 1
        out += t**bit
        value ^= 1 << bit
    return out


def coordinates(value):
    return list(value.polynomial())


def encoded(value):
    return sum(int(c) << i for i, c in enumerate(coordinates(value)))


def rank(values):
    rows = []
    for value in values:
        coeffs = coordinates(value)
        rows.append([int(coeffs[i]) if i < len(coeffs) else 0 for i in range(41)])
    return matrix(GF(2), rows).rank()


def main():
    output = HERE / "sage_collision_audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "sage_collision_protocol.json").read_text())
    source = Path(__file__)
    receipt = HERE / "collision_rank_result.json"
    geometry_path = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
    for key, path in [("source", source), ("collision_result", receipt),
                      ("geometry", geometry_path), ("runtime", HERE / "sage_runtime_info.json")]:
        if protocol["sha256"][key] != sha(path):
            raise ValueError("frozen digest mismatch: " + key)
    P = PolynomialRing(GF(2), "t")
    t = P.gen()
    F = GF(2**41, "t", modulus=t**41 + t**3 + 1)
    t = F.gen()
    E = EllipticCurve(F, [1, 0, 0, 0, 1])
    target = lift(F, protocol["residual_x"])
    k = protocol["free_low_bits"]
    cross = [t**(2*h) + target*t**h for h in range(2*k - 1)]
    if rank(cross) != 40:
        raise AssertionError("cross-term rank mismatch")
    raw = json.loads(geometry_path.read_text())["n41"]
    expected = json.loads(receipt.read_text())
    checked = []
    for rotation, domain_receipt in zip([20, 30], expected["domains"]):
        rows = raw["point_rows_by_unique_rotation"][str(rotation)]
        source_points = [E(lift(F, row[0]), lift(F, row[1])) for row in rows]
        xs = set()
        for i, left in enumerate(rows):
            for j in range(i + 1, len(rows)):
                if left[2] != rows[j][2]:
                    xs.add(encoded((source_points[i] + source_points[j])[0]))
        if len(xs) != 978:
            raise AssertionError("independent pair-output count mismatch")
        prefixes = sorted({x & ~((1 << k) - 1) for x in xs})
        if len(prefixes) != 977:
            raise AssertionError("independent prefix count mismatch")
        counts = {p: sum((x & ~((1 << k) - 1)) == p for x in xs)
                  for p in prefixes}
        collision = [p for p, count in counts.items() if count == 2]
        if collision != [domain_receipt["first_collision_prefix"]]:
            raise AssertionError("independent first collision mismatch")
        selected = sorted({prefixes[0], prefixes[1], prefixes[2], prefixes[len(prefixes)//2],
                           prefixes[-3], prefixes[-2], prefixes[-1], collision[0]})
        for value in selected:
            a = lift(F, value)
            side = [((a + target)*t**i)**2 + target*a*t**i for i in range(k)]
            if rank(cross + side) != 41:
                raise AssertionError("sampled prefix rank mismatch")
        checked.append({"rotation": rotation, "pair_output_x_count": len(xs),
                        "prefix_count": len(prefixes), "collision_prefix": collision[0],
                        "sampled_prefix_rank_checks": len(selected)})
    result = {"status": "PASS", "source_sha256": sha(source),
              "protocol_sha256": sha(HERE / "sage_collision_protocol.json"),
              "collision_result_sha256": sha(receipt), "cross_term_rank": 40,
              "domains": checked}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
