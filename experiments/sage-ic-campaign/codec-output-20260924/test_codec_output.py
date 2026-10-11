"""Point-object contract for the accelerated NTL coordinate decoder."""
import copy
import pickle
import sys
import unittest
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_hardware_codec as codec
from sage.schemes.elliptic_curves.ell_point import EllipticCurvePoint_finite_field

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/sage-binary-hardware'))
from public_points import generate
sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark import incumbent_hardware


class CodecOutputTests(unittest.TestCase):
    def fixture(self, degree):
        field = GF(2**degree, 'z', impl='ntl')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        points, _ = generate(curve, 12, 2026092781 + degree)
        points += [curve(0)]
        return field, curve, points

    def test_state_and_interoperability(self):
        for degree in (5, 19, 67, 131, 163):
            field, curve, points = self.fixture(degree)
            words = (degree + 31) // 32
            data, flags = codec.pack_points(curve, iter(points), words)
            other = GF(2**31, 'w', impl='ntl')
            other.gen() ** 17  # Decoder must restore the original NTL context.
            actual = codec.unpack_points(curve, data, flags, words)
            self.assertEqual(actual, points)
            for i, point in enumerate(actual[:-1]):
                fresh = curve._point(curve, list(points[i]), check=False)
                self.assertIs(type(point), type(fresh))
                self.assertIs(point.parent(), fresh.parent())
                self.assertTrue(point._normalized)
                self.assertEqual(point.__dict__, fresh.__dict__)
                self.assertIs(point.codomain(), curve)
                self.assertEqual(point[2], field.one())
                self.assertEqual(hash(point), hash(fresh))
                self.assertEqual(copy.copy(point), fresh)
                self.assertEqual(pickle.loads(pickle.dumps(point)), fresh)
                self.assertEqual(point + points[0], fresh + points[0])

    def test_custom_constructor_and_infinity(self):
        _, curve, points = self.fixture(19)
        words = 1
        data, flags = codec.pack_points(curve, points, words)
        calls = {'new': 0, 'init': 0}

        class CustomPoint(EllipticCurvePoint_finite_field):
            def __new__(cls, *args, **kwargs):
                calls['new'] += 1
                return super().__new__(cls)

            def __init__(self, *args, **kwargs):
                calls['init'] += 1
                super().__init__(*args, **kwargs)

        old = curve._point
        try:
            curve._point = CustomPoint
            baseline = incumbent_hardware()._codec.unpack_points(curve, data, flags, words)
            baseline_calls = dict(calls)
            calls.update(new=0, init=0)
            actual = codec.unpack_points(curve, data, flags, words)
            self.assertEqual(actual, baseline)
            self.assertEqual(calls, baseline_calls)
            self.assertTrue(all(type(point) is CustomPoint for point in actual[:-1]))
            self.assertEqual(actual[-1], curve(0))
        finally:
            curve._point = old


if __name__ == '__main__':
    unittest.main(verbosity=2)
