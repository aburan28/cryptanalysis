#!/usr/bin/env python3
"""Checked-Sage replay of the paired N53 W3/S4 planted SAT control."""

from __future__ import annotations

import gzip
import hashlib
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, is_prime

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/n53_w3_s4_planted_v1"
N, R, COFACTOR = 53, 21044858204113, 428


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_sha(archive):
    return hashlib.sha256(gzip.decompress(archive.read_bytes())).hexdigest()


def model_from_archive(archive):
    text = gzip.decompress(archive.read_bytes()).decode()
    assert "s SATISFIABLE" in text
    return {abs(int(word)): int(word) > 0
            for line in text.splitlines() if line.startswith("v ")
            for word in line[2:].split() if word != "0"}


def verify_formula(archive, model):
    clauses = xors = 0
    for line in gzip.decompress(archive.read_bytes()).decode().splitlines():
        if line.startswith("p "):
            nvars = int(line.split()[2])
            assert len(model) == nvars and set(model) == set(range(1, nvars + 1))
            continue
        words = line.split()
        if not words:
            continue
        assert words[-1] == "0"
        xor = words[0] == "x"
        values = [model[abs(int(word))] == (int(word) > 0)
                  for word in words[1 if xor else 0:-1]]
        if xor:
            assert sum(values) % 2 == 1
            xors += 1
        else:
            assert any(values)
            clauses += 1
    return clauses, xors


def main():
    runtime = RUN / "sage_runtime_info.json"
    if not runtime.is_file():
        raise FileNotFoundError("checked Sage runtime receipt is required")
    binary = GF(2)
    ring = PolynomialRing(binary, "u")
    u = ring.gen()
    field = GF(2**N, "z", modulus=u**N + u**6 + u**2 + u + 1)
    z = field.gen()
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert is_prime(R) and curve.cardinality() == R * COFACTOR

    def element(bits):
        return sum((z**i for i in range(N) if bits >> i & 1), field(0))

    def point(pair):
        return curve(element(pair[0]), element(pair[1]))

    alpha = element(3)
    basis = [alpha]
    for _ in range(N - 1):
        basis.append(basis[-1] ** 2)
    assert basis[-1] ** 2 == alpha
    weight3 = {basis[i] + basis[j] + basis[k]
               for i, j, k in itertools.combinations(range(N), 3)}
    assert len(weight3) == 23426
    receipts = {name: json.loads((RUN / name / "receipt.json").read_text())
                for name in ("fc", "unary")}
    assert receipts["fc"]["fixture"] == receipts["unary"]["fixture"]
    fixture = receipts["fc"]["fixture"]
    points = [point(pair) for pair in fixture["points"]]
    target = point(fixture["target"])
    assert len(points) == 4 and sum(points, curve(0)) == target
    assert all(p[0] in weight3 for p in points)
    assert all(COFACTOR * p != curve(0) and R * (COFACTOR * p) == curve(0)
               for p in points)
    xs = [p[0] for p in points]
    first = points[0] + points[1]
    second = first + points[2]
    mids = [first[0], second[0]]
    assert [element(value) for value in fixture["intermediate_x"]] == mids
    for a, b, c in ((xs[0], xs[1], mids[0]),
                    (mids[0], xs[2], mids[1]),
                    (mids[1], xs[3], target[0])):
        e2 = a*b + a*c + b*c
        assert e2**2 + a*b*c + 1 == 0
    checked = {}
    for name, receipt in receipts.items():
        assert receipt["pinned_model_verified"] is True
        assert receipt["status"] == "INDETERMINATE"
        assert receipt["search_attempt"]["status_lines"] == ["s INDETERMINATE"]
        arm = RUN / name
        for phase in ("pinned", "search"):
            for artifact in ("system.xcnf", "solver.stdout.txt", "solver.stderr.txt"):
                path = arm / phase / (artifact + ".gz")
                hashes = receipt[f"{phase}_artifacts"][artifact]
                assert sha(path) == hashes["archive_sha256"]
                assert raw_sha(path) == hashes["raw_sha256"]
        model = model_from_archive(arm / "pinned/solver.stdout.txt.gz")
        checked[name] = verify_formula(arm / "pinned/system.xcnf.gz", model)
        assert receipt["model_xcnf_verified"] is False
    result = {"status": "PASS", "kind": "n53_w3_s4_planted_sage_replay",
              "curve_cardinality": R * COFACTOR,
              "weight_three_masks": len(weight3),
              "planted_group_sum_verified": True,
              "planted_s3_chain_verified": True,
              "pinned_xcnf_checked_rows": {name: {"cnf": counts[0], "xor": counts[1]}
                                           for name, counts in checked.items()},
              "search_statuses": {name: receipt["status"] for name, receipt in receipts.items()},
              "runtime_info_sha256": sha(runtime),
              "source_receipt_sha256": {name: sha(RUN / name / "receipt.json")
                                        for name in receipts},
              "source_sha256": sha(Path(__file__))}
    (RUN / "sage_replay.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
