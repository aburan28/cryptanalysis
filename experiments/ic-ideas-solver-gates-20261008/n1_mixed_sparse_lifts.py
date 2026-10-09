#!/usr/bin/env python3
"""Exact CRT and support test for mixed (2,3,3) cyclotomic S3 identities."""
from __future__ import annotations

import hashlib
import itertools
import json
import random
import sys
import time
from pathlib import Path

from sage.all import GF, Matrix, vector

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007"
sys.path.insert(0, str(PRIOR))
from sage_probes import bits, field, ring_s3  # noqa: E402

GATE = HERE.parent / "ic-ideas-completion-20261008/n1_gate.json"


def roots_s3(a, b, K):
    A, B, C = (a + b)**2, a*b, (a*b)**2 + K(1)
    if A == 0:
        return [] if B == 0 else [C/B]
    p, q = B/A, C/A
    if p == 0:
        return [q**(2**22)]
    w = q/(p*p)
    h, current = K(0), w
    for _ in range(12):
        h += current
        current = current**4
    if h*h + h != w:
        return []
    roots = [p*h, p*(h + 1)]
    assert all((a*b+a*c+b*c)**2+a*b*c+1 == 0 for c in roots)
    return roots


def project(word, powers, K):
    answer = K(0)
    while word:
        low = word & -word
        answer += powers[low.bit_length()-1]
        word ^= low
    return answer


def main():
    out = HERE / "n1_mixed_sparse_lifts.json"
    if out.exists():
        raise FileExistsError(out)
    started = time.perf_counter_ns()
    K, modulus = field(23)
    gamma = K.multiplicative_generator()**((2**23-1)//47)
    eta = gamma**5
    assert gamma.multiplicative_order() == eta.multiplicative_order() == 47
    assert gamma.minpoly() != eta.minpoly()
    first_powers = [gamma**i for i in range(47)]
    second_powers = [eta**i for i in range(47)]
    two = {}
    three = {}
    for i, j in itertools.combinations(range(47), 2):
        word = (1 << i) | (1 << j)
        two[bits(first_powers[i]+first_powers[j])] = word
    for i, j, k in itertools.combinations(range(47), 3):
        word = (1 << i) | (1 << j) | (1 << k)
        three[bits(first_powers[i]+first_powers[j]+first_powers[k])] = word
    assert len(two) == 1081 and len(three) == 16215
    gate = json.loads(GATE.read_text())
    factor = gate["selected_factor_bits"]
    assert sum(int(c) << i for i, c in enumerate(gamma.minpoly().list())) == factor
    mask = (1 << 47)-1
    kernel = [factor ^ (((factor << i) | (factor >> (47-i))) & mask)
              for i in range(1, 24)]
    assert all(word.bit_count() % 2 == 0 and project(word, first_powers, K) == 0
               for word in kernel)
    transport = Matrix(GF(2), 23, 23,
                       lambda row, col: (bits(project(kernel[col], second_powers, K))
                                         >> row) & 1)
    inverse = transport.inverse()
    def correction(delta):
        v = inverse*vector(GF(2), [(bits(delta) >> i) & 1 for i in range(23)])
        return xor_words(kernel[i] for i in range(23) if v[i])
    rng = random.Random(20261008)
    two_items = [(project(word, first_powers, K), word) for word in two.values()]
    three_items = [(project(word, first_powers, K), word) for word in three.values()]
    target_count, attempt_cap = 128, 100_000
    cells = []
    for attempt in range(attempt_cap):
        a, aword = rng.choice(two_items)
        b, bword = rng.choice(three_items)
        roots = roots_s3(a, b, K)
        for c in roots:
            cword = three.get(bits(c))
            if cword is None:
                continue
            raw = ring_s3(aword, bword, cword, 47)
            a2, b2 = project(aword, second_powers, K), project(bword, second_powers, K)
            other_roots = roots_s3(a2, b2, K)
            options = []
            for other_c in other_roots:
                delta = other_c + project(cword, second_powers, K)
                repaired = cword ^ correction(delta)
                assert project(repaired, first_powers, K) == c
                assert project(repaired, second_powers, K) == other_c
                assert repaired.bit_count() & 1
                assert ring_s3(aword, bword, repaired, 47) == 0
                options.append(repaired.bit_count())
            cells.append({"a_weight": aword.bit_count(),
                          "b_weight": bword.bit_count(),
                          "c_weight": cword.bit_count(),
                          "raw_exact_lift": raw == 0,
                          "other_component_root_count": len(other_roots),
                          "minimum_exact_c_support_with_fixed_a_b":
                              min(options) if options else None})
            if len(cells) == target_count:
                break
        if len(cells) == target_count:
            break
    answer = {"schema_version": 1, "proposal_id": "N1",
              "candidate_id": None, "run_id": None,
              "field_degree": 23, "field_modulus_bits": modulus,
              "group_algebra_length": 47,
              "input_law": "random weight-two and weight-three sparse x values; retain weight-three S3 roots",
              "pair_attempts": attempt+1, "attempt_cap": attempt_cap,
              "valid_field_s3_identities": len(cells),
              "raw_sparse_exact_lifts": sum(c["raw_exact_lift"] for c in cells),
              "fixed_a_b_exact_lift_exists": sum(c["other_component_root_count"] > 0
                                                 for c in cells),
              "repaired_c_supports": [c["minimum_exact_c_support_with_fixed_a_b"]
                                       for c in cells if c["minimum_exact_c_support_with_fixed_a_b"]
                                       is not None],
              "cells": cells,
              "stage_wall_ns_exploratory": time.perf_counter_ns()-started,
              "prior_gate_sha256": hashlib.sha256(GATE.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"identities": len(cells),
                      "raw_exact": answer["raw_sparse_exact_lifts"],
                      "fixed_a_b_lifts": answer["fixed_a_b_exact_lift_exists"]}))


def xor_words(words):
    answer = 0
    for word in words:
        answer ^= word
    return answer


if __name__ == "__main__":
    main()
