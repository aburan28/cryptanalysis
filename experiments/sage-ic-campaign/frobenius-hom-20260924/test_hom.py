"""Exactness and fallback contracts for the public Frobenius isogeny."""
import copy
import importlib.util
import unittest
from pathlib import Path

from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves.ell_point import EllipticCurvePoint_finite_field
from sage.schemes.elliptic_curves import hom_frobenius

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'old_hom_frobenius', HERE / 'baseline/hom_frobenius.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
original = old.EllipticCurveHom_frobenius._call_


class HomTests(unittest.TestCase):
    def compare(self, curve, powers):
        point = curve.random_point()
        special = [curve(0), curve(0, curve.a6().sqrt()), point, -point, 2*point]
        if point:
            unnormalized = copy.copy(point)
            factor = curve.base_ring().gen()
            unnormalized._coords = tuple(c*factor for c in point)
            unnormalized._normalized = False
            special.append(unnormalized)
        for power in powers:
            phi = curve.frobenius_isogeny(power)
            for P in special:
                with self.subTest(degree=curve.base_ring().degree(), power=power, point=P):
                    actual = phi(P)
                    expected = original(phi, P)
                    self.assertEqual(actual, expected)
                    self.assertIs(type(actual), type(expected))
                    self.assertIs(actual.curve(), expected.curve())

    def test_koblitz_powers_and_boundary_fields(self):
        for degree in (5, 19, 31, 67, 131, 163):
            field = GF(2**degree, 'z', impl='ntl')
            curve = EllipticCurve(field, [1, 1, 0, 0, 1])
            self.compare(curve, (0, 1, min(7, degree-1), degree-1,
                                 degree, degree+1))

    def test_alternate_modulus_and_a_zero(self):
        standard = GF(2**131, 'z', impl='ntl')
        alternate = GF(2**131, 'w', modulus=standard.modulus().reverse(), impl='ntl')
        curve = EllipticCurve(alternate, [1, 0, 0, 0, 1])
        self.compare(curve, (1, 7, 65, 131))

    def test_general_curves_keep_original_path(self):
        binary = GF(2**19, 'z', impl='ntl')
        curves = [EllipticCurve(binary, [1, binary.gen(), 0, 0, 1]),
                  EllipticCurve(binary, [1, 1, 0, 0, binary.gen()]),
                  EllipticCurve(GF(5**2, 'z'), [1, 1])]
        for curve in curves:
            phi = curve.frobenius_isogeny(1)
            point = curve.random_point()
            self.assertEqual(phi(point), original(phi, point))
            self.assertIsNone(phi._binary_batch_map)

    def test_custom_point_class_and_cached_guard(self):
        field = GF(2**19, 'z', impl='ntl')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        phi = curve.frobenius_isogeny(7)
        standard = curve.random_point()
        self.assertEqual(phi(standard), original(phi, standard))
        calls = {'initialize': 0}

        class CustomPoint(EllipticCurvePoint_finite_field):
            def __init__(self, *args, **kwargs):
                calls['initialize'] += 1
                super().__init__(*args, **kwargs)
                self.marker = 'constructed'

        prior = curve._point
        try:
            curve._point = CustomPoint
            custom = CustomPoint(curve, list(standard), check=False)
            candidate = hom_frobenius.EllipticCurveHom_frobenius._call_
            try:
                hom_frobenius.EllipticCurveHom_frobenius._call_ = original
                before = calls['initialize']
                expected = phi(custom)
                incumbent_initializations = calls['initialize'] - before
            finally:
                hom_frobenius.EllipticCurveHom_frobenius._call_ = candidate
            before = calls['initialize']
            actual = phi(custom)
            self.assertEqual(actual, expected)
            self.assertIs(type(actual), CustomPoint)
            self.assertEqual(actual.marker, 'constructed')
            self.assertEqual(calls['initialize'] - before, incumbent_initializations)
        finally:
            curve._point = prior


if __name__ == '__main__':
    unittest.main(verbosity=2)
