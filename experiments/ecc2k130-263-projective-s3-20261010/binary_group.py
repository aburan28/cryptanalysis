"""Independent polynomial-basis group law and projective S3 reference."""

from __future__ import annotations

from pathlib import Path
import sys


PARENT = Path(__file__).resolve().parents[1] / "ecc2k130-263-native-w24-m6-20261010"
sys.path.insert(0, str(PARENT))
import field as f  # noqa: E402


def on_curve(point, b):
    if point is None:
        return True
    x, y = point
    return f.square(y) ^ f.multiply(x, y) == f.multiply(f.square(x), x) ^ b


def negate(point):
    return None if point is None else (point[0], point[0] ^ point[1])


def add(left, right, b):
    if left is None:
        return right
    if right is None:
        return left
    if not on_curve(left, b) or not on_curve(right, b):
        raise ValueError("input point is off curve")
    x1, y1 = left
    x2, y2 = right
    if x1 == x2:
        if y1 ^ y2 == x1:
            return None
        if y1 != y2:
            raise ArithmeticError("same x has neither equal nor opposite y")
        if x1 == 0:
            return None
        slope = x1 ^ f.multiply(y1, f.inverse(x1))
        x3 = f.square(slope) ^ slope
        y3 = f.square(x1) ^ f.multiply(slope ^ 1, x3)
    else:
        slope = f.multiply(y1 ^ y2, f.inverse(x1 ^ x2))
        x3 = f.square(slope) ^ slope ^ x1 ^ x2
        y3 = f.multiply(slope, x1 ^ x3) ^ x3 ^ y1
    result = (x3, y3)
    if not on_curve(result, b):
        raise ArithmeticError("group sum left the curve")
    return result


def times(point, count, b):
    result = None
    while count:
        if count & 1:
            result = add(result, point, b)
        point = add(point, point, b)
        count >>= 1
    return result


def projective_x(point):
    return (1, 0) if point is None else (point[0], 1)


def s3_projective(left, middle, right, b):
    x1, z1 = left
    x2, z2 = middle
    x3, z3 = right
    if any(z not in (0, 1) for z in (z1, z2, z3)):
        raise ValueError("Z must be Boolean")
    if any(x != 1 for x, z in (left, middle, right) if z == 0):
        raise ValueError("infinity must be canonical")
    pair = (f.multiply(x1, x2) if z3 else 0)
    pair ^= f.multiply(x2, x3) if z1 else 0
    pair ^= f.multiply(x3, x1) if z2 else 0
    product_z = z1 & z2 & z3
    triple = f.multiply(f.multiply(x1, x2), x3) if product_z else 0
    return f.square(pair) ^ triple ^ (b if product_z else 0)
