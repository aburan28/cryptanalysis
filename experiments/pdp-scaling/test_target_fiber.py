"""Cofactor-aware targets for algebraic equations on original base points."""

import json
from pathlib import Path
import unittest

from gf2n import Curve, GF2n, INF, Point
from target_fiber import KERNEL_4, projected_preimages, scalar_mul

HERE = Path(__file__).resolve().parent


class TargetFiberTests(unittest.TestCase):
    def test_four_preimages_and_replay(self):
        for n in (13, 31, 83):
            with self.subTest(n=n):
                if n == 31:
                    r, h = 1439393, 4 * 373
                    modulus = GF2n(n).mod
                else:
                    base = json.loads((HERE / "ordinary-evidence-20260928" / f"n{n}.json").read_text())["base"]
                    r, h, modulus = base["subgroup_order"], base["cofactor"], base["modulus"]
                curve = Curve(GF2n(n, modulus), 1)
                self.assertEqual(curve.add(Point(1, 0), Point(1, 0)), Point(0, 1))
                self.assertEqual(curve.add(Point(1, 1), Point(1, 1)), Point(0, 1))
                self.assertEqual(curve.add(Point(1, 0), Point(1, 1)), INF)
                self.assertEqual(len(set(KERNEL_4)), 4)
                target = INF
                for x in range(1, 20):
                    point = curve.lift_x(x)
                    if point is not None:
                        target = scalar_mul(curve, point, h)
                        if target != INF:
                            break
                self.assertNotEqual(target, INF)
                self.assertEqual(scalar_mul(curve, target, r), INF)
                options = projected_preimages(curve, target, r)
                self.assertEqual(len(set(options)), 4)
                for candidate in options:
                    self.assertEqual(scalar_mul(curve, candidate, 4), target)
                # The projected point itself is generally not a preimage.
                self.assertNotIn(target, options)

    def test_wrong_target_rejected(self):
        curve = Curve(GF2n(13), 1)
        with self.assertRaises(ValueError):
            projected_preimages(curve, Point(1, 0), 2003)


if __name__ == "__main__":
    unittest.main()
