"""Slow replay arithmetic, separate from the measured relation engine.

Multiplication uses unreduced convolution and long division; inversion uses
exponentiation instead of extended Euclid. The associated verifier accepts only fixed toy fields of degree at most 13.
"""


def mul(a, b, modulus):
    value = 0
    for bit in range(b.bit_length()):
        if b >> bit & 1:
            value ^= a << bit
    for bit in range(value.bit_length() - 1, modulus.bit_length() - 2, -1):
        if value >> bit & 1:
            value ^= modulus << (bit - modulus.bit_length() + 1)
    return value


def inv(a, degree, modulus):
    if a == 0:
        raise ZeroDivisionError
    power, value, exponent = a, 1, (1 << degree) - 2
    while exponent:
        if exponent & 1:
            value = mul(value, power, modulus)
        power = mul(power, power, modulus)
        exponent >>= 1
    return value


def add(first, second, degree, modulus):
    if first is None:
        return second
    if second is None:
        return first
    x, y = first
    u, v = second
    if x == u and (y != v or x == 0):
        return None
    if first == second:
        slope = x ^ mul(y, inv(x, degree, modulus), modulus)
    else:
        slope = mul(y ^ v, inv(x ^ u, degree, modulus), modulus)
    intercept = y ^ mul(slope, x, modulus)
    out_x = mul(slope, slope, modulus) ^ slope ^ x ^ u
    return out_x, mul(slope ^ 1, out_x, modulus) ^ intercept


def scalar_mul(point, scalar, degree, modulus):
    result = None
    # Left-to-right, distinct from the engine's right-to-left membership check.
    for bit in bin(scalar)[2:]:
        result = add(result, result, degree, modulus)
        if bit == "1":
            result = add(result, point, degree, modulus)
    return result


def on_curve(point, degree, modulus):
    if point is None:
        return True
    x, y = point
    if not (0 <= x < 1 << degree and 0 <= y < 1 << degree):
        return False
    return mul(y, y, modulus) ^ mul(x, y, modulus) == mul(mul(x, x, modulus), x, modulus) ^ 1
