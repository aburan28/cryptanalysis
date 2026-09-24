"""Native singleton correctness across NTL contexts and point boundaries."""
import copy
import unittest

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl
from sage.schemes.elliptic_curves.ell_point import EllipticCurvePoint_finite_field


class NativeSingletonTests(unittest.TestCase):
    def test_context_switches_and_special_points(self):
        curves = []
        for degree, a in ((19, 1), (131, 0), (67, 1), (163, 1)):
            field = GF(2**degree, 'z', impl='ntl')
            curve = EllipticCurve(field, [1, a, 0, 0, 1])
            curves.append((curve, 1 if degree == 19 else min(65, degree-1)))
        for _ in range(4):
            for curve, power in curves:
                point = curve.random_point()
                unnormalized = copy.copy(point)
                scale = curve.base_ring().gen()
                unnormalized._coords = tuple(c*scale for c in point)
                unnormalized._normalized = False
                for P in (curve(0), curve(0, 1), point, -point, unnormalized):
                    actual = binary_batch_ntl._frobenius_one(curve, P, power)
                    expected = binary_batch.frobenius_points(curve, [P], power)[0]
                    self.assertEqual(actual, expected)
                    self.assertIs(type(actual), EllipticCurvePoint_finite_field)
                    self.assertIs(actual.curve(), curve)

    def test_bad_inputs_rejected(self):
        field = GF(2**19, 'z', impl='ntl')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        point = curve.random_point()
        with self.assertRaises(ValueError):
            binary_batch_ntl._frobenius_one(curve, point, 0)
        with self.assertRaises(ValueError):
            binary_batch_ntl._frobenius_one(curve, point, 19)
        other = EllipticCurve(field, [1, 0, 0, 0, 1])
        with self.assertRaises(ValueError):
            binary_batch_ntl._frobenius_one(other, point, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
