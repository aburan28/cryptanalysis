#!/usr/bin/env python3
"""Independent checked-Sage replay of the frozen N53 PDP stage receipts."""

from __future__ import annotations

import hashlib
import gzip
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, is_prime, matrix

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/n53_scale_v1"
N = 53
R = 21044858204113
COFACTOR = 428


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xcnf_sha(folder):
    raw = folder / "system.xcnf"
    archive = folder / "system.xcnf.gz"
    digest = hashlib.sha256()
    opener = raw.open if raw.exists() else lambda mode: gzip.open(archive, mode)
    with opener("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    runtime = RUN / "sage_runtime_info.json"
    if not runtime.is_file():
        raise FileNotFoundError("save checked launcher runtime info before Sage replay")
    binary = GF(2)
    polynomials = PolynomialRing(binary, "u")
    u = polynomials.gen()
    field = GF(2**N, "z", modulus=u**N + u**6 + u**2 + u + 1)
    z = field.gen()
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def element(bits):
        value = field(0)
        for i in range(N):
            if bits >> i & 1:
                value += z**i
        return value

    def point(pair):
        return curve(element(pair[0]), element(pair[1]))

    generator = point((198217578752339, 7929897206038174))
    ordinary = point((7764671419819752, 2542564920656034))
    assert is_prime(R)
    assert generator != curve(0) and R * generator == curve(0)
    assert ordinary != curve(0) and R * ordinary == curve(0)
    assert 596471236405 * generator == ordinary
    alpha = element(3)
    conjugates = [alpha]
    for _ in range(N - 1):
        conjugates.append(conjugates[-1] ** 2)
    assert conjugates[-1] ** 2 == alpha
    coordinates = []
    for value in conjugates:
        coeff = list(value.polynomial().list())
        coordinates.append(coeff + [0] * (N - len(coeff)))
    assert matrix(binary, coordinates).rank() == N
    weight_two_x = {conjugates[i] + conjugates[j]
                    for i, j in itertools.combinations(range(N), 2)}
    assert len(weight_two_x) == 1378
    receipts = {name: json.loads((RUN / name / "receipt.json").read_text())
                for name in ("fc", "unary", "fc_planted", "unary_planted")}
    digest_set = {receipt["factor_base"]["projected_set_sha256"]
                  for receipt in receipts.values()}
    assert len(digest_set) == 1
    for name, receipt in receipts.items():
        assert receipt["status"] == "EXTERNAL_WATCHDOG"
        assert receipt["candidate_id"] is None
        assert receipt["group_lift"] is None
        assert xcnf_sha(RUN / name) == receipt["xcnf_sha256"]
        if "planted" not in name:
            assert point(receipt["target"]) == ordinary
            continue
        fixture = receipt["fixture"]
        points = [point(pair) for pair in fixture["points"]]
        assert len(points) == 5 and all(p[0] in weight_two_x for p in points)
        target = point(fixture["target"])
        assert sum(points, curve(0)) == target
        assert [int(p[0] in weight_two_x) for p in points] == [1] * 5
        assert all(COFACTOR * p != curve(0) and R * (COFACTOR * p) == curve(0)
                   for p in points)
        xs = [p[0] for p in points]
        prefix = []
        running = curve(0)
        for p in points:
            running += p
            prefix.append(running)
        mids = [p[0] for p in prefix[1:4]]
        assert all(p != curve(0) and p[0] != 0 for p in prefix[1:4])
        assert [element(value) for value in fixture["intermediate_x"]] == mids
        for a, b, c in ((xs[0], xs[1], mids[0]),
                        (mids[0], xs[2], mids[1]),
                        (mids[1], xs[3], mids[2]),
                        (mids[2], xs[4], target[0])):
            e2 = a*b + a*c + b*c
            e3 = a*b*c
            assert e2**2 + e3 + 1 == 0
    assert receipts["fc"]["target"] == receipts["unary"]["target"]
    assert receipts["fc_planted"]["target"] == receipts["unary_planted"]["target"]
    result = {
        "status": "PASS", "curve": "N53_kb1_polynomial_0x20000000000047",
        "normal_basis_rank": N, "weight_two_x_count": len(weight_two_x),
        "usable_base_points": 1696, "signed_frobenius_columns": 16,
        "ordinary_target_subgroup_verified": True,
        "ordinary_published_scalar_replayed": True,
        "planted_five_point_group_witness_replayed": True,
        "planted_four_s3_equations_verified": True,
        "statuses": {name: receipt["status"] for name, receipt in receipts.items()},
        "projected_set_sha256": next(iter(digest_set)),
        "runtime_info_sha256": sha(runtime),
        "source_sha256": sha(Path(__file__)),
    }
    (RUN / "sage_replay.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
