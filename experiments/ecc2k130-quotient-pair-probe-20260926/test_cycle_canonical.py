"""Independent orbit-scan controls for the ONB cycle quotient key."""

import unittest

import curves
from cycle_canonical import CycleCanonical
from perf_probe import base_prefix
from quotient_pair_probe import transform


class CycleCanonicalTest(unittest.TestCase):
    def test_orbit_key_and_witness(self):
        for degree, cofactor in ((53, 428), (83, 4)):
            order = curves.curveOrder(degree) // cofactor
            onb, curve, base, _, _ = base_prefix(degree, cofactor, order, 2)
            cycle = CycleCanonical(onb)
            points = [None, (onb.one(), 0), (0, onb.one())] + base[:8]
            points += [curve.add(base[i], base[-i - 1]) for i in range(8)]
            points += [curve.frob(p, 7) for p in base[:4]]
            for point in points:
                with self.subTest(degree=degree, point=point):
                    key, shift, sign = cycle.canonical(curve, point)
                    self.assertEqual(transform(curve, point, shift, sign),
                                     None if key == (-1, -1) else key)
                    if point is None:
                        continue
                    expected = min(
                        (cycle.cycle_word(onb, shifted[0]), signed[1], signed)
                        for j in range(degree)
                        for shifted in (curve.frob(point, j),)
                        for signed in (shifted, curve.neg(shifted)))
                    self.assertEqual((cycle.cycle_word(onb, key[0]), key[1], key),
                                     expected)
                    self.assertEqual(cycle.canonical(curve, curve.frob(point, 3))[0], key)
                    self.assertEqual(cycle.canonical(curve, curve.neg(point))[0], key)


if __name__ == "__main__":
    unittest.main()
