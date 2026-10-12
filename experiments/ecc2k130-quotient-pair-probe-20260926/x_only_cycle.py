"""Signed-Frobenius quotient key from x alone on a binary elliptic curve.

For x != 0, y^2 + x*y = x^3 + 1 has exactly two rational roots whenever
it has one, and they differ by x.  They are negatives on the curve.  Thus
the least Frobenius rotation of x identifies the full signed orbit.  The y
coordinate and sign are needed only when a lookup actually hits.
"""

from cycle_canonical import CycleCanonical


class XOnlyCycle(CycleCanonical):
    def key_and_shift(self, curve, point, counts=None):
        if point is None:
            return -1, 0
        onb = getattr(curve, "curve", curve).f
        if onb.m != self.degree:
            raise ValueError("field degree differs from cycle map")
        word = self.cycle_word(onb, point[0])
        best, best_shift = word, 0
        for shift in range(1, self.degree):
            word = ((word << 1) | (word >> (self.degree - 1))) & self.mask
            if word < best:
                best, best_shift = word, shift
        if counts is not None:
            counts["coordinate_permutations"] = counts.get("coordinate_permutations", 0) + 1
            counts["word_rotations"] = counts.get("word_rotations", 0) + self.degree - 1
        return best, best_shift
