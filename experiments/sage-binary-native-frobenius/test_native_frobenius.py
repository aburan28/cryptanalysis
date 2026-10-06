"""Native Frobenius contract and regression coverage; run with local Sage."""
import copy
import pickle
import sys
import unittest
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl
from sage.schemes.elliptic_curves.ell_point import EllipticCurvePoint_finite_field

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'sage-binary-arithmetic'))
import test_binary_batch
sys.path.insert(0, str(HERE.parent / 'sage-binary-hardware'))
from public_points import generate

test_binary_batch.candidate = binary_batch
test_binary_batch.add_pairs = binary_batch.add_pairs


class NativeFrobeniusTests(unittest.TestCase):
    def fixture(self, degree=19):
        field = GF(2**degree, 'z', impl='ntl')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        points, _ = generate(curve, 12, 2026092471 + degree)
        return field, curve, points

    def test_native_exact_and_point_state(self):
        self.assertTrue(hasattr(binary_batch_ntl, '_frobenius_prepared'))
        for degree in (5, 19, 67, 131, 163):
            field, curve, points = self.fixture(degree)
            points += [curve(0)]
            for power in (1, 2, 7, -1, degree, degree + 1):
                actual = binary_batch.frobenius_points(curve, iter(points), power)
                k = power % degree
                expected = [curve.frobenius_isogeny(k)(P) if k else P for P in points]
                self.assertEqual(actual, expected)
                if k:
                    self.assertIs(actual[-1], points[-1])
                else:
                    self.assertTrue(all(a is b for a, b in zip(actual, points)))
                for i, point in enumerate(actual[:-1]):
                    self.assertIs(type(point), type(points[0]))
                    self.assertIs(point.parent(), curve.point_homset())
                    self.assertIs(point.curve(), curve)
                    self.assertEqual(point[2], field.one())
                    if k:
                        self.assertTrue(point._normalized)
                        self.assertEqual(pickle.loads(pickle.dumps(point)), point)
                        self.assertEqual(copy.copy(point), point)
                        self.assertEqual(point + points[0], expected[i] + points[0])

    def test_iterator_switches_ntl_context(self):
        _, curve, points = self.fixture(19)
        other = GF(2**31, 'w', impl='ntl')

        def source():
            for point in points:
                other.gen() ** 17
                yield point

        self.assertEqual(binary_batch.frobenius_points(curve, source(), 7),
                         [curve.frobenius_isogeny(7)(P) for P in points])

    def test_custom_constructor_and_fallback(self):
        _, curve, points = self.fixture()
        expected = [curve.frobenius_isogeny(1)(P) for P in points]
        calls = {'new': 0, 'init': 0}

        class CustomPoint(EllipticCurvePoint_finite_field):
            def __new__(cls, *args, **kwargs):
                calls['new'] += 1
                return super().__new__(cls)

            def __init__(self, *args, **kwargs):
                calls['init'] += 1
                super().__init__(*args, **kwargs)

        old_class = curve._point
        try:
            curve._point = CustomPoint
            actual = binary_batch.frobenius_points(curve, points)
            self.assertEqual(actual, expected)
            self.assertEqual(calls, {'new': len(points), 'init': len(points)})
            self.assertTrue(all(type(P) is CustomPoint for P in actual))
        finally:
            curve._point = old_class
        native = binary_batch._native
        try:
            binary_batch._native = None
            fallback = binary_batch.frobenius_points(curve, points, 7)
        finally:
            binary_batch._native = native
        self.assertEqual(binary_batch.frobenius_points(curve, points, 7), fallback)


if __name__ == '__main__':
    unittest.main(verbosity=2)
