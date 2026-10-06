#!/usr/bin/env python3
"""Check batched additions against the complete affine curve law."""

import json
import random
import unittest
from pathlib import Path

import curves
import field
from dyadic_five_sum_batch import batch_add_pairs

HERE = Path(__file__).resolve().parent


class BatchPairAdditionTest(unittest.TestCase):
    def test_regular_and_exceptional_pairs(self):
        for n in (53, 83):
            with self.subTest(degree=n):
                reference = json.loads((HERE / "runs" / f"n{n}_perf_prefix.json").read_text())
                curve = curves.Curve(field.Onb(n))
                generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
                rng = random.Random(8023 + n)
                points = [curve.mul(generator, rng.randrange(1, 1000000))
                          for _ in range(64)]
                pairs = [(rng.choice(points), rng.choice(points)) for _ in range(64)]
                pairs += [(None, points[0]), (points[0], None),
                          (points[0], points[0]),
                          (points[0], curve.neg(points[0]))]
                self.assertEqual(batch_add_pairs(curve, pairs),
                                 [curve.add(a, b) for a, b in pairs])


if __name__ == "__main__":
    unittest.main()
