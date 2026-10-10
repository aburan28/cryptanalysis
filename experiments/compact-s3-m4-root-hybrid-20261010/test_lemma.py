#!/usr/bin/env python3
"""Exhaustively verify exact S3 roots and conditional clauses over GF(2^5)."""

from hybrid import (MeteredField, check_clauses, exact_roots, field,
                    root_lemma)
from s3_root_oracle import s3_roots
from chain_s3 import evaluate_s3


def assignment(a, b, c, branch):
    result = {}
    for offset, value in ((1, a), (6, b), (11, c)):
        for i in range(5):
            result[offset + i] = bool(value >> i & 1)
    result[16] = branch
    return result


def main():
    onb = field.Onb(5)
    metered = MeteredField(onb)
    left, right, mid = list(range(1, 6)), list(range(6, 11)), list(range(11, 16))
    counts = {0: 0, 1: 0, 2: 0}
    for a in range(1, 32):
        for b in range(1, 32):
            roots = exact_roots(metered, a, b)
            direct = tuple(c for c in range(32)
                           if evaluate_s3(onb, onb.fromCoords(a),
                                          onb.fromCoords(b), onb.fromCoords(c)) == 0)
            assert roots == direct
            counts[len(roots)] += 1
            branch = 16 if len(roots) == 2 else None
            clauses = root_lemma(left, right, mid, a, b, roots, branch)
            for c in range(32):
                allowed = any(check_clauses(clauses, assignment(a, b, c, z))
                              for z in (False, True))
                assert allowed == (c in roots), (a, b, c, roots)
                # An unrelated leaf pair must never be constrained by this lemma.
                other = assignment(a ^ 1, b, c, False)
                assert check_clauses(clauses, other)
    assert sum(counts.values()) == 31 * 31
    print({"status": "PASS", "field_degree": 5,
           "exhaustive_nonzero_leaf_pairs": 961, "root_counts": counts})


if __name__ == "__main__":
    main()
