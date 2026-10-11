"""Batch group arithmetic and quotient-witness equivalence controls."""

import unittest

import curves
from batch_x_only import batch_add_fixed_left, query_prefix_batch
from compare_x_only import build_index, query_prefix
from perf_probe import base_prefix
from x_only_cycle import XOnlyCycle


class BatchXOnlyTest(unittest.TestCase):
    def test_add_and_queries(self):
        for degree, cofactor in ((53, 428), (83, 4)):
            order = curves.curveOrder(degree) // cofactor
            onb, curve, base, reps, _ = base_prefix(
                degree, cofactor, order, 2)
            left = base[0]
            rights = [None, left, curve.neg(left)] + base[:30]
            self.assertEqual(batch_add_fixed_left(curve, left, rights),
                             [curve.add(left, right) for right in rights])
            canonicalize = XOnlyCycle(onb)
            index, _ = build_index(curve, base, reps, degree, canonicalize)
            representatives = [value[0] for value in index.values()]
            positive_target = curve.add(representatives[0], representatives[1])
            self.assertIsNotNone(positive_target)
            for target, limit, expected_positive in (
                    (positive_target, 2, True),
                    (curve.mul(left, 1234567), 2048, False)):
                with self.subTest(degree=degree, limit=limit):
                    direct = query_prefix(curve, index, target, degree,
                                          canonicalize, limit)
                    batched = query_prefix_batch(curve, index, target, degree,
                                                 canonicalize, limit)
                    self.assertEqual(direct["verified_hit_positions"],
                                     batched["verified_hit_positions"])
                    if expected_positive:
                        self.assertTrue(batched["verified_hit_positions"])
                    self.assertEqual(direct["lookups"], batched["lookups"])


if __name__ == "__main__":
    unittest.main()
