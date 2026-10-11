"""Signed-orbit and independently replayed four-point x-only controls."""

import unittest

import curves
from compare_x_only import build_index, query_prefix
from perf_probe import base_prefix
from x_only_cycle import XOnlyCycle


class XOnlyCycleTest(unittest.TestCase):
    def test_signed_frobenius_key_and_positive_witness(self):
        for degree, cofactor in ((53, 428), (83, 4)):
            order = curves.curveOrder(degree) // cofactor
            onb, curve, base, reps, _ = base_prefix(
                degree, cofactor, order, 2)
            canonicalize = XOnlyCycle(onb)
            self.assertEqual(canonicalize.key_and_shift(curve, None), (-1, 0))
            for point in [(onb.one(), 0), (0, onb.one())] + base[:12]:
                with self.subTest(degree=degree, point=point):
                    key, shift = canonicalize.key_and_shift(curve, point)
                    self.assertEqual(canonicalize.key_and_shift(
                        curve, curve.frob(point, shift)), (key, 0))
                    self.assertEqual(canonicalize.key_and_shift(
                        curve, curve.neg(point))[0], key)
                    self.assertEqual(canonicalize.key_and_shift(
                        curve, curve.frob(point, 7))[0], key)
            index, build = build_index(curve, base, reps, degree, canonicalize)
            self.assertEqual(build["keys"], len(index))
            representatives = [value[0] for value in index.values()]
            target = curve.add(representatives[0], representatives[1])
            self.assertIsNotNone(target)
            result = query_prefix(curve, index, target, degree, canonicalize, 2)
            self.assertGreaterEqual(len(result["verified_hit_positions"]), 1)


if __name__ == "__main__":
    unittest.main()
