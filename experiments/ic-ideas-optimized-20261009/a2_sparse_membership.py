#!/usr/bin/env python3
"""Exact indexed membership and support recovery for N23 sparse sums."""
from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007/results/a2_final.json"
N = 23
ROOT_ORDER = 47
MASK = (1 << N) - 1


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mul(a: int, b: int, modulus: int) -> int:
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a & (1 << N):
            a ^= modulus
    return result & MASK


def square(a: int, modulus: int) -> int:
    return mul(a, a, modulus)


class SparseMembership:
    def __init__(self, gamma: int, modulus: int):
        assert modulus.bit_length() == N + 1
        self.modulus = modulus
        powers = [1]
        for _ in range(1, ROOT_ORDER):
            powers.append(mul(powers[-1], gamma, modulus))
        assert mul(powers[-1], gamma, modulus) == 1
        assert len(set(powers)) == ROOT_ORDER
        self.powers = powers
        self.bits = bytearray(1 << (N - 3))
        self.supports: dict[int, tuple[int, ...]] = {}
        for weight in (2, 3):
            for support in itertools.combinations(range(ROOT_ORDER), weight):
                value = 0
                for exponent in support:
                    value ^= powers[exponent]
                if value in self.supports:
                    raise AssertionError("sparse sum has two support encodings")
                self.supports[value] = support
                self.bits[value >> 3] |= 1 << (value & 7)
        assert len(self.supports) == 17_296

    def contains(self, x: int) -> bool:
        return 0 <= x <= MASK and bool(self.bits[x >> 3] & (1 << (x & 7)))

    def support(self, x: int) -> tuple[int, ...] | None:
        if not self.contains(x):
            return None
        return self.supports[x]


def main() -> None:
    output = HERE / "a2_sparse_membership.json"
    bits_path = HERE / "a2_sparse_membership.bits.gz"
    support_path = HERE / "a2_sparse_membership.supports.gz"
    if any(path.exists() for path in (output, bits_path, support_path)):
        raise FileExistsError("preserve prior indexed membership artifacts")
    prior = json.loads(PRIOR.read_text())
    gamma, modulus = prior["gamma_bits"], prior["field_modulus_bits"]
    index = SparseMembership(gamma, modulus)
    frobenius_matches = 0
    for value, support in index.supports.items():
        conjugate = square(value, modulus)
        expected = tuple(sorted((2 * exponent) % ROOT_ORDER for exponent in support))
        assert index.support(conjugate) == expected
        frobenius_matches += 1
    exact_domain_matches = 0
    for value in range(1 << N):
        exact_domain_matches += index.contains(value) == (value in index.supports)
    assert exact_domain_matches == 1 << N
    encoded_supports = b"".join(struct.pack("<IBBB", value, *(
        *support, *(255 for _ in range(3 - len(support)))))
        for value, support in sorted(index.supports.items()))
    bits_path.write_bytes(gzip.compress(index.bits, compresslevel=9, mtime=0))
    support_path.write_bytes(gzip.compress(encoded_supports, compresslevel=9, mtime=0))
    answer = {"schema_version": 1, "proposal_id": "A2",
              "candidate_id": None, "run_id": None,
              "field_degree": N, "root_order": ROOT_ORDER,
              "field_modulus_bits": modulus, "gamma_bits": gamma,
              "sparse_sum_count": len(index.supports),
              "weight_two_count": ROOT_ORDER * (ROOT_ORDER-1)//2,
              "weight_three_count": ROOT_ORDER * (ROOT_ORDER-1)*(ROOT_ORDER-2)//6,
              "exact_domain_matches": exact_domain_matches,
              "frobenius_support_matches": frobenius_matches,
              "bitset_bytes": len(index.bits),
              "bitset_gzip_bytes": bits_path.stat().st_size,
              "support_map_gzip_bytes": support_path.stat().st_size,
              "bitset_sha256": sha(bits_path),
              "support_map_sha256": sha(support_path),
              "prior_receipt_sha256": sha(PRIOR),
              "source_sha256": sha(Path(__file__))}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"sparse_sum_count": answer["sparse_sum_count"],
                      "bitset_gzip_bytes": answer["bitset_gzip_bytes"],
                      "support_map_gzip_bytes": answer["support_map_gzip_bytes"]}))


if __name__ == "__main__":
    main()
