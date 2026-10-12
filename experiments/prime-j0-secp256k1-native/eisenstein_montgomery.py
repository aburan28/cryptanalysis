#!/usr/bin/env python3
"""Exact reference for secp256k1 Fp as Z[omega]/(pi), with ring Montgomery reduction.

This is a correctness and representation-bounds prototype. Python big integers
do not model the cost of a fixed-width native field implementation.
"""

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path


P = 2**256 - 2**32 - 977
BETA = int("7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee", 16)
# Multiply the Euclidean-gcd generator by omega: the ideal is unchanged,
# while both modulus coefficients now fit in 128 bits.
PI = (64502973549206556628585045361533709078,
      -303414439467246543595250775667605759171)
R = 1 << 128
R_INVERSE_P = pow(R, -1, P)


def add(x, y):
    return x[0] + y[0], x[1] + y[1]


def sub(x, y):
    return x[0] - y[0], x[1] - y[1]


def times_small(k, x):
    return k * x[0], k * x[1]


def product(x, y):
    """(a+b omega)(c+d omega), using omega^2=-1-omega."""
    a, b = x
    c, d = y
    ac, bd = a * c, b * d
    cross = (a + b) * (c + d)
    return ac - bd, cross - ac - 2 * bd


def conjugate(x):
    a, b = x
    return a - b, -b


def norm(x):
    a, b = x
    return a * a - a * b + b * b


assert norm(PI) == P
assert (PI[0] + PI[1] * BETA) % P == 0
assert (BETA * BETA + BETA + 1) % P == 0
assert max(abs(x).bit_length() for x in PI) <= 128

PI_INVERSE_R = times_small(pow(P, -1, R), conjugate(PI))
PI_INVERSE_R = tuple(x % R for x in PI_INVERSE_R)
assert tuple(x % R for x in product(PI, PI_INVERSE_R)) == (1, 0)


def balance(x):
    """Nearest Eisenstein-lattice representative modulo pi, with exact ties."""
    numerator = product(x, conjugate(PI))
    center = numerator[0] // P, numerator[1] // P
    choices = ((u, v) for u in range(center[0] - 1, center[0] + 3)
               for v in range(center[1] - 1, center[1] + 3))
    quotient = min(choices, key=lambda q: (norm(sub(x, product(q, PI))), q))
    reduced = sub(x, product(quotient, PI))
    assert 3 * norm(reduced) <= P
    return reduced, quotient


def montgomery_reduce(x):
    """Return x/R modulo pi and the radix cancellation and balance quotients."""
    cancellation = tuple(-u % R for u in product(x, PI_INVERSE_R))
    numerator = add(x, product(cancellation, PI))
    assert all(u % R == 0 for u in numerator)
    quotient = tuple(u // R for u in numerator)
    reduced, correction = balance(quotient)
    return reduced, cancellation, correction, quotient


def encode(x):
    """Enter the Eisenstein Montgomery domain; conversion is outside hot loops."""
    assert 0 <= x < P
    return balance(((x * R) % P, 0))[0]


def decode(x):
    return ((x[0] + x[1] * BETA) * R_INVERSE_P) % P


def multiply(x, y):
    return montgomery_reduce(product(x, y))[0]


def omega(x):
    """The cube-root action needs only swaps, subtraction, and sign changes."""
    a, b = x
    return -b, a - b


def one_minus_omega(x):
    """The tau constant is a linear pair map; the result may need balancing."""
    return sub(x, omega(x))


def verify(count):
    rng = random.Random(20261008)
    edges = [0, 1, 2, 3, P - 1, P - 2, BETA, (P - BETA) % P,
             R - 1, R, R + 1, P // 2]
    values = [(x, y) for x in edges for y in edges]
    values.extend((rng.randrange(P), rng.randrange(P)) for _ in range(count))
    corrections = Counter()
    max_balanced_bits = max_unbalanced_bits = 0
    for x, y in values:
        left, right = encode(x), encode(y)
        assert decode(left) == x and decode(right) == y
        candidate, cancellation, correction, unbalanced = montgomery_reduce(
            product(left, right))
        assert decode(candidate) == x * y % P
        assert candidate == multiply(left, right)
        assert decode(balance(add(left, right))[0]) == (x + y) % P
        assert decode(balance(sub(left, right))[0]) == (x - y) % P
        rotation = omega(left)
        assert norm(rotation) == norm(left)
        assert decode(rotation) == BETA * x % P
        assert omega(omega(omega(left))) == left
        assert decode(one_minus_omega(left)) == (1 - BETA) * x % P
        max_balanced_bits = max(max_balanced_bits,
                                *(abs(u).bit_length() for u in (*left, *right, *candidate)))
        max_unbalanced_bits = max(max_unbalanced_bits,
                                  *(abs(u).bit_length() for u in unbalanced))
        corrections[correction] += 1
        assert all(0 <= u < R for u in cancellation)
    return {
        "schema": 1,
        "prime_hex": hex(P),
        "beta_hex": hex(BETA),
        "pi": PI,
        "pi_norm_matches_prime": True,
        "radix_bits": 128,
        "edge_pairs": len(edges) ** 2,
        "random_pairs": count,
        "checked_pairs": len(values),
        "balanced_coefficient_max_bits": max_balanced_bits,
        "post_montgomery_unbalanced_max_bits": max_unbalanced_bits,
        "balance_corrections": [
            {"quotient": list(q), "count": n}
            for q, n in sorted(corrections.items())
        ],
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--random-pairs", type=int, default=10_000)
    args = parser.parse_args()
    assert args.random_pairs >= 0
    print(json.dumps(verify(args.random_pairs), sort_keys=True))


if __name__ == "__main__":
    main()
