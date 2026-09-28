"""Frozen toy arithmetic adapted from ../nonfrobenius-ic/index_calculus.py.

Only four fixed fields, with prime subgroup orders at most 2003, are accepted.
No external target, cryptographic-size parameter, or logarithm extraction API.
"""
from collections import Counter, defaultdict
from contextlib import contextmanager
import time

PROFILES = {5: (0x25, 11), 7: (0x83, 29), 9: (0x211, 127), 13: (0x201b, 2003)}

def require(condition, message):
    if not condition:
        raise ValueError(message)


class Ledger:
    def __init__(self):
        self.current = "unscoped"
        self.counts = defaultdict(Counter)
        self.seconds = defaultdict(float)

    def tick(self, name, count=1):
        self.counts[self.current][name] += count

    @contextmanager
    def phase(self, name):
        previous = self.current
        self.current = name
        start = time.perf_counter()
        try:
            yield
        finally:
            self.seconds[name] += time.perf_counter() - start
            self.current = previous

    def report(self):
        return {name: {"seconds": self.seconds[name],
                       "operations": dict(sorted(self.counts[name].items()))}
                for name in sorted(set(self.seconds) | set(self.counts))}


def polynomial_remainder(value, modulus):
    while value.bit_length() >= modulus.bit_length():
        value ^= modulus << (value.bit_length() - modulus.bit_length())
    return value


def polynomial_gcd(a, b):
    while b:
        a, b = b, polynomial_remainder(a, b)
    return a


class BinaryField:
    """Polynomial coordinates; square is ordinary field arithmetic, not a point map."""

    def __init__(self, degree, modulus, ledger):
        require((degree, modulus) in {(5, 0x25), (7, 0x83), (9, 0x211), (13, 0x201b)}, "only fixed toy fields of degree 5, 7, 9, or 13 are supported")
        require(modulus.bit_length() == degree + 1 and modulus & 1,
                "invalid modulus degree or constant term")
        self.degree, self.modulus, self.ledger = degree, modulus, ledger
        self.limit = 1 << degree

    def _multiply(self, a, b):
        result = 0
        while b:
            if b & 1:
                result ^= a
            b >>= 1
            a <<= 1
            if a & self.limit:
                a ^= self.modulus
        return result

    def mul(self, a, b):
        self.ledger.tick("field_multiplications")
        return self._multiply(a, b)

    def square(self, a):
        self.ledger.tick("field_squarings")
        return self._multiply(a, a)

    def inv(self, a):
        self.ledger.tick("field_inversions")
        if a == 0:
            raise ZeroDivisionError("zero has no inverse")
        u, v, left, right = a, self.modulus, 1, 0
        while u != 1:
            require(u != 0, "modulus is reducible or element is invalid")
            shift = u.bit_length() - v.bit_length()
            if shift < 0:
                u, v, left, right = v, u, right, left
                shift = -shift
            u ^= v << shift
            left ^= right << shift
        return polynomial_remainder(left, self.modulus)

    def irreducible(self):
        # Rabin's criterion, including each prime divisor of the field degree.
        remaining, prime_divisors, divisor = self.degree, set(), 2
        while divisor * divisor <= remaining:
            if remaining % divisor == 0:
                prime_divisors.add(divisor)
                while remaining % divisor == 0:
                    remaining //= divisor
            divisor += 1
        if remaining > 1:
            prime_divisors.add(remaining)
        checkpoints = {self.degree // p for p in prime_divisors}
        power = 2
        for step in range(1, self.degree + 1):
            power = self.square(power)
            if step in checkpoints and polynomial_gcd(power ^ 2, self.modulus) != 1:
                return False
        return power == 2


class BinaryCurve:
    """E: y^2 + xy = x^3 + 1. No curve endomorphism or orbit methods."""

    def __init__(self, field):
        self.f, self.ledger = field, field.ledger

    def on_curve(self, point):
        if point is None:
            return True
        x, y = point
        if not (0 <= x < self.f.limit and 0 <= y < self.f.limit):
            return False
        f = self.f
        return f.square(y) ^ f.mul(x, y) == f.mul(f.square(x), x) ^ 1

    def neg(self, point):
        self.ledger.tick("point_negations")
        return None if point is None else (point[0], point[0] ^ point[1])

    def add(self, first, second):
        self.ledger.tick("point_additions_including_special_cases")
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
            self.ledger.tick("point_doublings_subset")
            slope = x ^ f.mul(y, f.inv(x))
            out_x = f.square(slope) ^ slope
            out_y = f.square(x) ^ f.mul(slope ^ 1, out_x)
        else:
            slope = f.mul(y ^ v, f.inv(x ^ u))
            out_x = f.square(slope) ^ slope ^ x ^ u
            out_y = f.mul(slope, x ^ out_x) ^ out_x ^ y
        return out_x, out_y

    def mul(self, point, scalar):
        require(type(scalar) is int and scalar >= 0, "expected nonnegative scalar")
        self.ledger.tick("scalar_multiplications")
        result = None
        while scalar:
            if scalar & 1:
                result = self.add(result, point)
            scalar >>= 1
            if scalar:
                point = self.add(point, point)
        return result

    def lift(self, x):
        """Return both actual points above x, including the order-two exception."""
        require(type(x) is int and 0 <= x < self.f.limit, "x outside field")
        if x == 0:
            return [(0, 1)]
        f = self.f
        rhs = x ^ f.inv(f.square(x))
        term, half_trace = rhs, rhs
        for _ in range((f.degree - 1) // 2):
            term = f.square(f.square(term))
            half_trace ^= term
        if f.square(half_trace) ^ half_trace != rhs:
            return []
        y = f.mul(x, half_trace)
        return sorted([(x, y), (x, x ^ y)])


