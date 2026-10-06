#!/usr/bin/env python3
"""Independent Sage geometry and Newton-identity replay of raw support bound."""

from __future__ import annotations

from collections import Counter
import hashlib
import itertools
import json
from math import comb
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, is_prime

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/n53_raw_coverage_v1"
N, R, COFACTOR, M = 53, 21044858204113, 428, 5


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def newton_multisets(counts):
    """Independent complete-homogeneous recurrence in Z[C_428]."""
    powers = [[0] * COFACTOR for _ in range(M + 1)]
    for degree in range(1, M + 1):
        for residue, count in counts.items():
            powers[degree][degree * residue % COFACTOR] += count
    h = [[0] * COFACTOR for _ in range(M + 1)]
    h[0][0] = 1
    for degree in range(1, M + 1):
        accum = [0] * COFACTOR
        for j in range(1, degree + 1):
            for left_residue, left_ways in enumerate(h[degree - j]):
                if not left_ways:
                    continue
                for right_residue, right_ways in enumerate(powers[j]):
                    if right_ways:
                        accum[(left_residue + right_residue) % COFACTOR] \
                            += left_ways * right_ways
        assert all(value % degree == 0 for value in accum)
        h[degree] = [value // degree for value in accum]
    return h[M]


def main():
    runtime = RUN / "sage_runtime_info.json"
    if not runtime.is_file():
        raise FileNotFoundError("save checked Sage runtime info before replay")
    audited = json.loads((RUN / "receipt.json").read_text())
    binary = GF(2)
    ring = PolynomialRing(binary, "u")
    u = ring.gen()
    field = GF(2**N, "z", modulus=u**N + u**6 + u**2 + u + 1)
    z = field.gen()
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    assert is_prime(R) and curve.cardinality() == COFACTOR * R

    def element(bits):
        return sum((z**i for i in range(N) if bits >> i & 1), field(0))

    source = audited["torsion_generator_source_point"]
    generator = R * curve(element(source[0]), element(source[1]))
    zero = curve(0)
    assert COFACTOR * generator == zero
    assert (COFACTOR // 2) * generator != zero
    assert (COFACTOR // 107) * generator != zero
    lookup = {i * generator: i for i in range(COFACTOR)}
    assert len(lookup) == COFACTOR
    alpha = element(3)
    conjugates = [alpha]
    for _ in range(N - 1):
        conjugates.append(conjugates[-1] ** 2)
    assert conjugates[-1] ** 2 == alpha
    counts = Counter()
    raw = 0
    for i, j in itertools.combinations(range(N), 2):
        for point in curve.lift_x(conjugates[i] + conjugates[j], all=True):
            counts[lookup[R * point]] += 1
            raw += 1
    assert raw == audited["raw_base_points"]
    digest = hashlib.sha256(json.dumps([counts.get(i, 0) for i in range(COFACTOR)],
                                separators=(",", ":")).encode()).hexdigest()
    assert digest == audited["torsion_class_counts_sha256"]
    final = newton_multisets(counts)
    assert sum(final) == comb(raw + M - 1, M)
    assert final[0] == audited["multisets_whose_sum_is_in_subgroup"]
    report = {"status": "PASS", "kind": "n53_raw_coverage_sage_replay",
              "curve_cardinality": COFACTOR * R,
              "raw_base_points": raw, "occupied_torsion_classes": len(counts),
              "multisets_whose_sum_is_in_subgroup": final[0],
              "all_unordered_multisets_with_repetition": sum(final),
              "torsion_class_counts_sha256": digest,
              "counting_method": "Newton identities in the cyclic group ring",
              "runtime_info_sha256": sha(runtime),
              "source_coverage_receipt_sha256": sha(RUN / "receipt.json"),
              "source_sha256": sha(Path(__file__))}
    (RUN / "sage_replay.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
