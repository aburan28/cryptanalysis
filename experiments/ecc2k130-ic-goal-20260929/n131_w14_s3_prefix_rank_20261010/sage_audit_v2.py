#!/usr/bin/env python3
"""Independent checked-Sage replay of S3 prefix rank and group controls."""

import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing, EllipticCurve, matrix

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
RESULT = HERE / "result.json"
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
W14 = BASE / "n131_w14_polynomial_pair_inverse_20261010/inputs.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field(n, degrees):
    poly = PolynomialRing(GF(2), "t")
    t = poly.gen()
    return GF(2**n, "t", modulus=t**n + sum(t**d for d in degrees))


def lift(F, value):
    t = F.gen()
    result = F.zero()
    while value:
        bit = value.bit_length() - 1
        result += t**bit
        value ^= 1 << bit
    return result


def coords(value, n):
    coefficients = value.polynomial().list()
    return [int(coefficients[i]) if i < len(coefficients) else 0 for i in range(n)]


def rank_of_variations(F, n, a, b, target, k):
    t = F.gen()
    columns = []
    for i in range(k):
        e = t**i
        columns.append(((b + target)*e)**2 + target*b*e)
    for i in range(k):
        e = t**i
        columns.append(((a + target)*e)**2 + target*a*e)
    for h in range(2*k - 1):
        e = t**h
        columns.append(e**2 + target*e)
    return matrix(GF(2), [coords(x, n) for x in columns]).rank()


def point(E, F, encoded):
    return E(lift(F, encoded[0]), lift(F, encoded[1]))


def audit():
    record = json.loads(RESULT.read_text())
    geom = json.loads(GEOMETRY.read_text())["n41"]
    inp = json.loads(W14.read_text())
    out = {"status": "PASS", "result_sha256": sha(RESULT), "source_sha256": sha(Path(__file__)),
           "checks": {}}
    for n, terms, section, ks in [(41, [0, 3], "n41", [0, 4, 8, 10, 11, 12]),
                                  (131, [0, 1, 2, 13], "n131", [0, 16, 28, 32, 33, 34])]:
        F = field(n, terms)
        E = EllipticCurve(F, [1, 0, 0, 0, 1])
        checked = 0
        for item in record[section]["cases"][:2]:
            a, b, target = (lift(F, item[key]) for key in ("a", "b", "t"))
            s3 = (a*b + target*(a+b))**2 + target*a*b + 1
            if coords(s3, n) != coords(lift(F, item["s3_value"]), n):
                raise AssertionError("S3 value mismatch")
            for k in ks:
                if rank_of_variations(F, n, a, b, target, k) != item["ranks"][str(k)]:
                    raise AssertionError("prefix variation rank mismatch")
                checked += 1
        if n == 41:
            pair_points = []
            for rotation, witness in zip([20, 30], record["n41"]["positive_witness"]):
                rows = geom["point_rows_by_unique_rotation"][str(rotation)]
                i, j = witness["source_indices"]
                left, right = point(E, F, rows[i]), point(E, F, rows[j])
                total = left + right
                if total != point(E, F, witness["pair_sum"]):
                    raise AssertionError("N41 pair sum mismatch")
                pair_points.append(total)
            if pair_points[0] + pair_points[1] != point(E, F, record["n41"]["positive_residual"]):
                raise AssertionError("N41 residual mismatch")
            out["checks"]["n41_group_witness"] = True
        else:
            for row in inp["positives"][:2]:
                if point(E, F, row["raw_leaves"][0]) + point(E, F, row["raw_leaves"][1]) != point(E, F, row["raw_sum"]):
                    raise AssertionError("N131 pair sum mismatch")
            out["checks"]["n131_pair_controls"] = 2
        out["checks"][section + "_independent_ranks"] = checked
    with (HERE / "sage_audit.json").open("x") as stream:
        json.dump(out, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    audit()
