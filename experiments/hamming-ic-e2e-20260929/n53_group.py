"""Pure-Python reference arithmetic for the fixed N53 Koblitz stage probe."""

from __future__ import annotations


N = 53
LOW_TERMS = (0, 1, 2, 6)
MODULUS = (1 << N) | sum(1 << i for i in LOW_TERMS)
R = 21044858204113
COFACTOR = 428
GENERATOR = (198217578752339, 7929897206038174)
TARGET = (7764671419819752, 2542564920656034)


class Field:
    def __init__(self):
        self.n = N
        self.modulus = MODULUS
        self.mask = (1 << N) - 1

    def mul(self, a: int, b: int) -> int:
        result = 0
        while b:
            if b & 1:
                result ^= a
            b >>= 1
            a <<= 1
            if a >> N:
                a ^= MODULUS
        return result

    def square(self, a: int) -> int:
        return self.mul(a, a)

    def inv(self, a: int) -> int:
        if a == 0:
            raise ZeroDivisionError
        u, v, left, right = a, MODULUS, 1, 0
        while u != 1:
            if u == 0:
                raise ValueError("reducible modulus")
            shift = u.bit_length() - v.bit_length()
            if shift < 0:
                u, v, left, right = v, u, right, left
                shift = -shift
            u ^= v << shift
            left ^= right << shift
        while left.bit_length() > N:
            left ^= MODULUS << (left.bit_length() - N - 1)
        return left

    def trace(self, a: int) -> int:
        value, total = a, a
        for _ in range(N - 1):
            value = self.square(value)
            total ^= value
        if total not in (0, 1):
            raise AssertionError("trace outside prime field")
        return total

    def half_trace(self, a: int) -> int:
        value, total = a, a
        for _ in range((N - 1) // 2):
            value = self.square(self.square(value))
            total ^= value
        return total


class Curve:
    """y^2 + xy = x^3 + 1; None is the identity."""

    def __init__(self, field: Field):
        self.f = field

    def on_curve(self, point):
        if point is None:
            return True
        x, y = point
        f = self.f
        if not (0 <= x <= f.mask and 0 <= y <= f.mask):
            return False
        return f.square(y) ^ f.mul(x, y) == f.mul(f.square(x), x) ^ 1

    @staticmethod
    def neg(point):
        return None if point is None else (point[0], point[0] ^ point[1])

    def add(self, first, second):
        if first is None:
            return second
        if second is None:
            return first
        f = self.f
        x, y = first
        u, v = second
        if x == u:
            if y != v or x == 0:
                return None
            slope = x ^ f.mul(y, f.inv(x))
            out_x = f.square(slope) ^ slope
            out_y = f.square(x) ^ f.mul(slope ^ 1, out_x)
        else:
            slope = f.mul(y ^ v, f.inv(x ^ u))
            out_x = f.square(slope) ^ slope ^ x ^ u
            out_y = f.mul(slope, x ^ out_x) ^ out_x ^ y
        return out_x, out_y

    def mul(self, point, scalar: int):
        if scalar < 0:
            return self.mul(self.neg(point), -scalar)
        result = None
        while scalar:
            if scalar & 1:
                result = self.add(result, point)
            scalar >>= 1
            if scalar:
                point = self.add(point, point)
        return result

    def lift(self, x: int):
        f = self.f
        if x == 0:
            return [(0, 1)]
        rhs = x ^ f.inv(f.square(x))
        if f.trace(rhs):
            return []
        z = f.half_trace(rhs)
        if f.square(z) ^ z != rhs:
            raise AssertionError("invalid half trace")
        y = f.mul(x, z)
        return sorted(((x, y), (x, x ^ y)))


def normal_basis(field: Field):
    alpha = 3
    values = [alpha]
    for _ in range(N - 1):
        values.append(field.square(values[-1]))
    assert field.square(values[-1]) == alpha
    pivots = {}
    for value in values:
        while value:
            bit = value.bit_length() - 1
            if bit not in pivots:
                pivots[bit] = value
                break
            value ^= pivots[bit]
    assert len(pivots) == N
    return alpha, values
