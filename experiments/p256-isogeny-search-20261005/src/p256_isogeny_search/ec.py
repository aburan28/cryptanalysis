"""Small, auditable short-Weierstrass arithmetic for experiment control code.

This is not constant-time and must not be used for secret-key operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


AffinePoint = Optional[tuple[int, int]]


@dataclass(frozen=True, slots=True)
class JacobianPoint:
    x: int
    y: int
    z: int

    @property
    def is_infinity(self) -> bool:
        return self.z == 0


@dataclass(frozen=True, slots=True)
class ShortWeierstrassCurve:
    p: int
    a: int
    b: int

    @property
    def infinity(self) -> JacobianPoint:
        return JacobianPoint(1, 1, 0)

    def is_on_curve(self, point: AffinePoint) -> bool:
        if point is None:
            return True
        x, y = point
        return (y * y - (x * x * x + self.a * x + self.b)) % self.p == 0

    def from_affine(self, point: AffinePoint) -> JacobianPoint:
        if point is None:
            return self.infinity
        if not self.is_on_curve(point):
            raise ValueError("point is not on the curve")
        x, y = point
        return JacobianPoint(x % self.p, y % self.p, 1)

    def to_affine(self, point: JacobianPoint) -> AffinePoint:
        if point.is_infinity:
            return None
        p = self.p
        z_inv = pow(point.z, -1, p)
        z2 = z_inv * z_inv % p
        return point.x * z2 % p, point.y * z2 * z_inv % p

    def normalize(self, point: JacobianPoint) -> JacobianPoint:
        """Return the unique Z=1 representative (or conventional infinity)."""
        return self.from_affine(self.to_affine(point))

    def batch_normalize(self, points: list[JacobianPoint]) -> list[JacobianPoint]:
        """Normalize many points with one field inversion (Montgomery's trick)."""
        p = self.p
        nonzero_indices = [
            index for index, point in enumerate(points) if not point.is_infinity
        ]
        if not nonzero_indices:
            return [self.infinity for _ in points]

        prefixes: list[int] = []
        accumulator = 1
        for index in nonzero_indices:
            prefixes.append(accumulator)
            accumulator = accumulator * points[index].z % p
        inverse = pow(accumulator, -1, p)
        z_inverses = [0] * len(points)
        for position in range(len(nonzero_indices) - 1, -1, -1):
            index = nonzero_indices[position]
            z_inverses[index] = inverse * prefixes[position] % p
            inverse = inverse * points[index].z % p

        normalized: list[JacobianPoint] = []
        for index, point in enumerate(points):
            if point.is_infinity:
                normalized.append(self.infinity)
                continue
            z_inv = z_inverses[index]
            z2 = z_inv * z_inv % p
            normalized.append(
                JacobianPoint(point.x * z2 % p, point.y * z2 * z_inv % p, 1)
            )
        return normalized

    def negate(self, point: JacobianPoint) -> JacobianPoint:
        if point.is_infinity:
            return point
        return JacobianPoint(point.x, (-point.y) % self.p, point.z)

    def double(self, point: JacobianPoint) -> JacobianPoint:
        if point.is_infinity or point.y == 0:
            return self.infinity
        p = self.p
        x1, y1, z1 = point.x, point.y, point.z
        xx = x1 * x1 % p
        yy = y1 * y1 % p
        yyyy = yy * yy % p
        zz = z1 * z1 % p
        s = 2 * ((x1 + yy) * (x1 + yy) - xx - yyyy) % p
        m = (3 * xx + self.a * zz * zz) % p
        x3 = (m * m - 2 * s) % p
        y3 = (m * (s - x3) - 8 * yyyy) % p
        z3 = ((y1 + z1) * (y1 + z1) - yy - zz) % p
        return JacobianPoint(x3, y3, z3)

    def add(self, left: JacobianPoint, right: JacobianPoint) -> JacobianPoint:
        if left.is_infinity:
            return right
        if right.is_infinity:
            return left

        p = self.p
        x1, y1, z1 = left.x, left.y, left.z
        x2, y2, z2 = right.x, right.y, right.z
        z1z1 = z1 * z1 % p
        z2z2 = z2 * z2 % p
        u1 = x1 * z2z2 % p
        u2 = x2 * z1z1 % p
        s1 = y1 * z2 * z2z2 % p
        s2 = y2 * z1 * z1z1 % p
        if u1 == u2:
            return self.double(left) if s1 == s2 else self.infinity

        h = (u2 - u1) % p
        i = (2 * h) * (2 * h) % p
        j = h * i % p
        r = 2 * (s2 - s1) % p
        v = u1 * i % p
        x3 = (r * r - j - 2 * v) % p
        y3 = (r * (v - x3) - 2 * s1 * j) % p
        z3 = ((z1 + z2) * (z1 + z2) - z1z1 - z2z2) * h % p
        return JacobianPoint(x3, y3, z3)

    def scalar_mul(self, scalar: int, point: JacobianPoint) -> JacobianPoint:
        if scalar < 0:
            return self.scalar_mul(-scalar, self.negate(point))
        result = self.infinity
        addend = point
        while scalar:
            if scalar & 1:
                result = self.add(result, addend)
            addend = self.double(addend)
            scalar >>= 1
        return result

    def equal(self, left: JacobianPoint, right: JacobianPoint) -> bool:
        if left.is_infinity or right.is_infinity:
            return left.is_infinity and right.is_infinity
        p = self.p
        z1z1 = left.z * left.z % p
        z2z2 = right.z * right.z % p
        if left.x * z2z2 % p != right.x * z1z1 % p:
            return False
        return (
            left.y * right.z * z2z2 - right.y * left.z * z1z1
        ) % p == 0

    def j_invariant(self) -> int:
        p = self.p
        a3 = self.a * self.a * self.a % p
        denominator = (4 * a3 + 27 * self.b * self.b) % p
        if denominator == 0:
            raise ValueError("singular curve")
        return 1728 * 4 * a3 * pow(denominator, -1, p) % p
