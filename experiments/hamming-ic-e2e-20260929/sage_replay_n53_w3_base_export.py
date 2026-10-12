#!/usr/bin/env python3
"""Independent checked-Sage replay of the exported W3 signed orbit base."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, is_prime

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/n53_w3_base_export_v1"
N, R, COFACTOR = 53, 21044858204113, 428


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def main():
    runtime = RUN / "sage_runtime_info.json"
    if not runtime.is_file():
        raise FileNotFoundError("save checked Sage runtime info first")
    exported = json.loads((RUN / "representatives.json").read_text())
    receipt = json.loads((RUN / "receipt.json").read_text())
    assert sha(RUN / "representatives.json") == receipt["representatives_sha256"]
    binary = GF(2)
    ring = PolynomialRing(binary, "u")
    u = ring.gen()
    field = GF(2**N, "z", modulus=u**N + u**6 + u**2 + u + 1)
    z = field.gen()
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert is_prime(R) and curve.cardinality() == R * COFACTOR

    def element(bits):
        return sum((z**i for i in range(N) if bits >> i & 1), field(0))

    def encode(value):
        return sum(int(coefficient) << i
                   for i, coefficient in enumerate(value.polynomial().list()))

    lam = exported["lambda_mod_r"]
    assert pow(lam, N, R) == 1
    representatives = exported["representatives"]
    assert len(representatives) == 221
    entries = []
    points = set()
    for column, pair in enumerate(representatives):
        point = curve(element(pair[0]), element(pair[1]))
        assert point != curve(0) and R * point == curve(0)
        assert lam * point == curve(point[0]**2, point[1]**2)
        coefficient = 1
        for _ in range(N):
            negative = -point
            first = [encode(point[0]), encode(point[1])]
            second = [encode(negative[0]), encode(negative[1])]
            entries.extend((first + [column, coefficient],
                            second + [column, (-coefficient) % R]))
            assert tuple(first) not in points and tuple(second) not in points
            points.add(tuple(first))
            points.add(tuple(second))
            point = curve(point[0]**2, point[1]**2)
            coefficient = coefficient * lam % R
        assert [encode(point[0]), encode(point[1])] == pair
        assert coefficient == 1
    assert len(points) == receipt["actual_usable_points"] == 23426
    assert digest([list(point) for point in sorted(points)]) == receipt["projected_set_sha256"]
    assert digest(entries) == receipt["ordered_labeled_entries_sha256"]
    result = {"status": "PASS", "kind": "n53_w3_base_export_sage_replay",
              "curve_cardinality": R * COFACTOR,
              "representatives": len(representatives), "points": len(points),
              "projected_set_sha256": receipt["projected_set_sha256"],
              "ordered_labeled_entries_sha256": digest(entries),
              "runtime_info_sha256": sha(runtime),
              "source_receipt_sha256": sha(RUN / "receipt.json"),
              "source_sha256": sha(Path(__file__))}
    (RUN / "sage_replay.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
