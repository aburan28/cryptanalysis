#!/usr/bin/env python3
"""Exact power-of-two Montgomery reduction in Z[omega]/(pi)."""
from hashlib import sha256
import json

from eisenstein_residue import P, PI, BETA, from_field, reduce_pair, to_field

RADIX = 1 << 128
INV_P_MOD_RADIX = pow(P, -1, RADIX)
INV_RADIX_MOD_P = pow(RADIX, -1, P)
assert P * INV_P_MOD_RADIX % RADIX == 1


def center(value):
    value %= RADIX
    return value - RADIX if value >= RADIX//2 else value


def ring_mul(left, right):
    u, v = left
    s, t = right
    a = u*s
    b = v*t
    c = (u+v)*(s+t)
    return a-b, c-a-2*b


def montgomery_reduce(raw):
    """Return raw/R modulo pi, with canonical 33-byte coordinates."""
    x, y = raw
    a, b = PI
    q1 = center(-((a-b)*x+b*y)*INV_P_MOD_RADIX)
    q2 = center(-(-b*x+a*y)*INV_P_MOD_RADIX)
    numerator_x = x+q1*a-q2*b
    numerator_y = y+q1*b+q2*(a-b)
    assert numerator_x % RADIX == numerator_y % RADIX == 0
    intermediate = numerator_x//RADIX, numerator_y//RADIX
    return reduce_pair(intermediate), intermediate, (q1,q2)


def encode(value):
    assert 0 <= value < P
    return from_field(value*RADIX % P)


def decode(pair):
    return to_field(pair)*INV_RADIX_MOD_P % P


def multiply(left, right):
    return montgomery_reduce(ring_mul(left,right))[0]


def rotate(left):
    u, v = left
    return reduce_pair((-v,u-v))


def self_check(count=10000):
    assert count > 0
    max_intermediate_bits = [0,0]
    max_quotient_bits = [0,0]
    max_post_quotient_bits = [0,0]
    canonical_corrections = 0
    for index in range(count):
        x = int.from_bytes(sha256(b"montgomery-x"+index.to_bytes(8,"big")).digest(),"big") % P
        y = int.from_bytes(sha256(b"montgomery-y"+index.to_bytes(8,"big")).digest(),"big") % P
        left,right = encode(x),encode(y)
        assert decode(left) == x and decode(right) == y
        raw = ring_mul(left,right)
        product,intermediate,q = montgomery_reduce(raw)
        assert decode(product) == x*y % P
        assert product == multiply(left,right)
        assert decode(rotate(left)) == BETA*x % P
        assert all(abs(coord) < 1 << 128 for coord in product)
        canonical_corrections += int(product != intermediate)
        for axis in range(2):
            max_intermediate_bits[axis] = max(max_intermediate_bits[axis],
                                              abs(intermediate[axis]).bit_length())
            max_quotient_bits[axis] = max(max_quotient_bits[axis],abs(q[axis]).bit_length())
            a,b = PI
            numerator = ((a-b)*intermediate[0]+b*intermediate[1]
                         if axis == 0 else -b*intermediate[0]+a*intermediate[1])
            nearest = (numerator + P//2)//P
            max_post_quotient_bits[axis] = max(max_post_quotient_bits[axis],
                                               abs(nearest).bit_length())
    return {
        'schema':1,'checked_pairs':count,'prime_hex':f'{P:064x}',
        'radix_bits':128,'inverse_prime_mod_radix_hex':f'{INV_P_MOD_RADIX:032x}',
        'inverse_radix_mod_prime_hex':f'{INV_RADIX_MOD_P:064x}',
        'max_intermediate_coordinate_bits':max_intermediate_bits,
        'max_montgomery_quotient_bits':max_quotient_bits,
        'max_canonical_quotient_bits':max_post_quotient_bits,
        'products_requiring_canonical_correction':canonical_corrections,
        'checked_conversion_rotation_product_and_divisibility':count,
        'native_cost_status':'unmeasured',
    }


if __name__ == '__main__':
    print(json.dumps(self_check(),sort_keys=True,indent=2))
