#!/usr/bin/env python3
"""Exact prototype of F_p as Z[omega]/(pi) for secp256k1's prime."""

from hashlib import sha256
import json

P = (1 << 256) - (1 << 32) - 977
PI = (-367917413016453100223835821029139468249,
      -64502973549206556628585045361533709078)


def norm(pair):
    a, b = pair
    return a*a-a*b+b*b


def beta_root():
    for generator in range(2, 100):
        beta = pow(generator, (P-1)//3, P)
        if beta != 1:
            assert (beta*beta+beta+1) % P == 0
            return beta
    raise AssertionError("nontrivial cube root missing")


BETA = beta_root()
assert norm(PI) == P
assert (PI[0]+BETA*PI[1]) % P == 0
assert abs(PI[0])+abs(PI[1]) < 1 << 129
assert abs(PI[1])+abs(PI[0]-PI[1]) < 1 << 129


def nearest_ratio(numerator, denominator):
    assert denominator > 0
    return (numerator + denominator//2)//denominator


def reduce_pair(pair):
    """Subtract the nearest coefficients of pi and omega*pi.

    The basis columns are (a,b) and (-b,a-b); their determinant is p.
    Rounding the inverse-basis coordinates gives a bounded representative.
    """
    x, y = pair
    a, b = PI
    q1 = nearest_ratio((a-b)*x+b*y, P)
    q2 = nearest_ratio(-b*x+a*y, P)
    return x-q1*a+q2*b, y-q1*b-q2*(a-b)


def from_field(value):
    assert 0 <= value < P
    return reduce_pair((value, 0))


def to_field(pair):
    return (pair[0]+BETA*pair[1]) % P


def pack33(pair):
    """Pack two signed 129-bit sign/magnitude coordinates into 33 bytes."""
    assert all(abs(value) < 1 << 128 for value in pair)
    words = [(int(value < 0) << 128) | abs(value) for value in pair]
    return (words[0] | (words[1] << 129)).to_bytes(33, "little")


def unpack33(payload):
    assert len(payload) == 33
    packed = int.from_bytes(payload, "little")
    assert packed < 1 << 258
    words = (packed & ((1 << 129)-1), packed >> 129)
    return tuple(-(word & ((1 << 128)-1)) if word >> 128 else word
                 for word in words)


def add(left, right):
    return reduce_pair((left[0]+right[0], left[1]+right[1]))


def rotate(left):
    # omega*(u+v*omega) = -v + (u-v)*omega.
    u, v = left
    return reduce_pair((-v, u-v))


def multiply(left, right):
    # Three half-size products via Karatsuba before ideal reduction.
    u, v = left
    s, t = right
    us = u*s
    vt = v*t
    cross = (u+v)*(s+t)-us-vt
    return reduce_pair((us-vt, cross-vt))


def self_check(count=1000):
    assert count > 0
    a, b = PI
    determinant = a*(a-b)+b*b
    assert determinant == P
    max_bits = [0, 0]
    over_signed_128 = 0
    for index in range(count):
        x = int.from_bytes(sha256(b"eisenstein-x"+index.to_bytes(8,"big")).digest(),"big") % P
        y = int.from_bytes(sha256(b"eisenstein-y"+index.to_bytes(8,"big")).digest(),"big") % P
        left, right = from_field(x), from_field(y)
        assert to_field(left) == x
        assert to_field(right) == y
        assert to_field(add(left, right)) == (x+y) % P
        assert to_field(rotate(left)) == (BETA*x) % P
        assert to_field(rotate(rotate(left))) == (BETA*BETA*x) % P
        assert to_field(multiply(left, right)) == (x*y) % P
        assert reduce_pair(left) == left
        assert unpack33(pack33(left)) == left
        assert unpack33(pack33(right)) == right
        for pair in (left, right):
            max_bits[0] = max(max_bits[0], abs(pair[0]).bit_length())
            max_bits[1] = max(max_bits[1], abs(pair[1]).bit_length())
            over_signed_128 += int(any(abs(value) >= 1 << 127 for value in pair))
    return {
        "schema": 1,
        "prime_hex": f"{P:064x}",
        "beta_hex": f"{BETA:064x}",
        "pi": list(PI),
        "pi_norm_equals_prime": norm(PI) == P,
        "ideal_basis_determinant_equals_prime": determinant == P,
        "checked_pairs": count,
        "checked_conversion_add_rotation_square_rotation_and_multiply": count,
        "max_absolute_coordinate_bits": max_bits,
        "pairs_exceeding_signed_128_range": over_signed_128,
        "provable_coordinate_abs_bound": "strictly below 2^128 after basis rounding",
        "packed_x_bytes": 33,
        "packed_affine_xy_bytes": 65,
        "native_cost_status": "unmeasured",
    }


if __name__ == "__main__":
    print(json.dumps(self_check(), sort_keys=True, indent=2))
