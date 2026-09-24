"""Correctness and lifecycle contract for conservative CPU auto routing."""
import sys
import unittest
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves.binary_hardware import FrobeniusPlan

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate


class AutoRoutingTests(unittest.TestCase):
    def points(self, degree, count, power, a=1):
        field = GF(2**degree, 'z', impl='ntl')
        curve = EllipticCurve(field, [1, a, 0, 0, 1])
        base, _ = generate(curve, min(count, 128), 2026094301 + degree + power)
        points = [base[i % len(base)] for i in range(count)]
        points[0], points[1] = curve(0), curve(0, 1)
        phi = curve.frobenius_isogeny(power % degree)
        return curve, points, [phi(point) for point in points]

    def test_routed_and_lifecycle(self):
        for degree in (67, 131):
            curve, points, expected = self.points(degree, 4096, 65)
            with FrobeniusPlan(curve, 65, backend='auto') as plan:
                self.assertIsNone(plan._auto_plan)
                self.assertEqual(plan.apply(points), expected)
                self.assertEqual(plan.last_backend, 'cpu')
                self.assertIsNotNone(plan._auto_plan)
                self.assertGreater(plan.table_seconds, 0)
                self.assertEqual(plan.apply(tuple(points)), expected)
                self.assertEqual(plan.last_backend, 'cpu')
            self.assertIsNone(plan._auto_plan)
            with self.assertRaises(RuntimeError):
                plan.apply(points)

    def test_nonrouted_and_iterators(self):
        for degree, count, power in ((131, 1024, 65), (131, 4096, 1),
                                     (19, 4096, 1), (163, 4096, 65)):
            curve, points, expected = self.points(degree, count, power)
            with FrobeniusPlan(curve, power, backend='auto') as plan:
                self.assertEqual(plan.apply(points), expected)
                self.assertEqual(plan.last_backend, 'sage')
                self.assertIsNone(plan._auto_plan)
                with self.assertRaises(ValueError):
                    plan.apply_words(None)
        curve, points, expected = self.points(131, 4096, 65)
        with FrobeniusPlan(curve, 65, backend='auto') as plan:
            self.assertEqual(plan.apply(iter(points)), expected)
            self.assertEqual(plan.last_backend, 'sage')
            self.assertIsNone(plan._auto_plan)

    def test_missing_optional_native_falls_back(self):
        curve, points, expected = self.points(131, 4096, 65, a=0)
        with FrobeniusPlan(curve, 65, backend='auto',
                           native_library='/nonexistent/sage-binary-native.so') as plan:
            self.assertEqual(plan.apply(points), expected)
            self.assertEqual(plan.last_backend, 'sage')
            self.assertTrue(plan._auto_disabled)
            self.assertEqual(plan.apply(points), expected)
            self.assertIsNone(plan._auto_plan)


if __name__ == '__main__':
    unittest.main(verbosity=2)
