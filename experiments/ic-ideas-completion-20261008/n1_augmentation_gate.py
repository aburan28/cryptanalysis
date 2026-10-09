#!/usr/bin/env python3
"""Exact augmentation obstruction for sparse group-algebra S3 lifts.

The augmentation map R=F2[Z/q] -> F2 sends a support set to its parity.
For S3(a,b,c)=(ab+ac+bc)^2+abc+1, two even-weight leaves map to
S3(0,0,c)=1 for every c.  The script checks this on valid field identities
and enumerates the minimum odd-weight kernel adjustment at q=47.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

from sage.all import GF, Matrix, PolynomialRing, set_random_seed, vector

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-20261007"
sys.path.insert(0, str(PRIOR))
from sage_probes import bits, curve, field, ring_s3  # noqa: E402


def min_odd_kernel_weight(selected_factor: int, q: int):
    """Enumerate the 2^(q-degree(f)) words of the projection kernel."""
    degree = selected_factor.bit_length()-1
    dimension = q-degree
    mask = (1 << q)-1
    basis = []
    for i in range(dimension):
        rotated = ((selected_factor << i) | (selected_factor >> (q-i))) & mask
        basis.append(rotated)
    word = 0
    min_odd = q+1
    min_even_nonzero = q+1
    odd_count = 0
    odd_min_witness = None
    for gray_step in range(1, 1 << dimension):
        variable = (gray_step & -gray_step).bit_length()-1
        word ^= basis[variable]
        weight = word.bit_count()
        if weight & 1:
            odd_count += 1
            if weight < min_odd:
                min_odd = weight
                odd_min_witness = word
        elif weight < min_even_nonzero:
            min_even_nonzero = weight
    assert odd_count == 1 << (dimension-1)
    return {"kernel_dimension": dimension,
            "enumerated_nonzero_kernel_words": (1 << dimension)-1,
            "minimum_odd_kernel_weight": min_odd,
            "odd_minimum_witness_bits": odd_min_witness,
            "minimum_even_nonzero_kernel_weight": min_even_nonzero}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=256)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    set_random_seed(20261008)
    rng = random.Random(20261008)
    n, q = 23, 47
    K, modulus = field(n)
    E = curve(K)
    gamma = K.multiplicative_generator()**((2**n-1)//q)
    assert gamma.multiplicative_order() == q
    R = PolynomialRing(GF(2), "z")
    z = R.gen()
    factors = list((z**q+1).factor())
    factor_degrees = sorted(int(f.degree()) for f, _ in factors)
    assert factor_degrees == [1, 23, 23]
    selected = R(gamma.minpoly().list())
    selected_bits = sum(int(c) << i for i, c in enumerate(selected.list()))
    kernel = min_odd_kernel_weight(selected_bits, q)
    gamma_basis = [gamma**i for i in range(n)]
    gamma_change = Matrix(GF(2), n, n,
                          lambda i, j: (bits(gamma_basis[j]) >> i) & 1).inverse()
    def section(value):
        coordinates = gamma_change*vector(GF(2),
            [(bits(value) >> i) & 1 for i in range(n)])
        return sum(int(coordinates[i]) << i for i in range(n))
    sparse_points = []
    sparse_values = {}
    for i in range(q):
        for j in range(i+1, q):
            x = gamma**i + gamma**j
            leaf_section = (1 << i) | (1 << j)
            assert leaf_section.bit_count() == 2
            sparse_values[bits(x)] = leaf_section
            for P in E.lift_x(x, all=True):
                sparse_points.append((P, leaf_section))
    assert len(sparse_values) == q*(q-1)//2
    assert sparse_points
    valid = 0
    projected = 0
    impossible_for_every_third_lift = 0
    checked_examples = []
    while valid < args.samples:
        P, a = rng.choice(sparse_points)
        Q, b = rng.choice(sparse_points)
        T = P+Q
        if T.is_zero():
            continue
        valid += 1
        assert a.bit_count() % 2 == b.bit_count() % 2 == 0
        # Any section for the target's x-coordinate has the same field image;
        # parity of the target section cannot repair S3(0,0,c)=1.
        c = section(T[0])
        def project(word):
            value = K(0)
            for power in range(q):
                if word >> power & 1:
                    value += gamma**power
            return value
        assert project(a) == P[0] and project(b) == Q[0]
        assert project(ring_s3(a, b, c, q)) == 0
        projected += 1
        assert ring_s3(a, b, c, q).bit_count() % 2 == 1
        impossible_for_every_third_lift += 1
        if len(checked_examples) < 4:
            checked_examples.append({"leaf_a": a, "leaf_b": b,
                                     "target_x": bits(T[0]),
                                     "ring_s3_augmentation": 1})
    result = {"schema_version": 1, "proposal_id": "N1",
              "candidate_id": None, "run_id": None,
              "field_degree": n, "group_algebra_length": q,
              "field_modulus_bits": modulus,
              "cyclotomic_factor_degrees": factor_degrees,
              "selected_factor_bits": selected_bits,
              "selected_factor_weight": selected_bits.bit_count(),
              "sparse_weight_two_x_values": len(sparse_values),
              "sparse_weight_two_curve_points": len(sparse_points),
              "sampled_valid_field_identities": valid,
              "projected_s3_identites": projected,
              "impossible_exact_lifts_with_fixed_even_leaves":
                  impossible_for_every_third_lift,
              "examples": checked_examples,
              "kernel_parity_repair": kernel,
              "algebraic_rule": "augmentation(S3(0,0,c))=1 for all c",
              "scope": "fixed sparse weight-two leaf sections; changing a leaf by a kernel word is a separate representation",
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "prior_source_sha256": hashlib.sha256(
                  (PRIOR / "sage_probes.py").read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"valid": valid,
                      "impossible": impossible_for_every_third_lift,
                      "min_odd_kernel_weight": kernel["minimum_odd_kernel_weight"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
