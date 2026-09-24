"""Exact public P+Q behavior for native binary dispatch and fallbacks."""
import copy
import importlib.util
import unittest
from pathlib import Path

from sage.all import EllipticCurve, GF, QQ
from sage.schemes.elliptic_curves import binary_batch
from sage.schemes.elliptic_curves.ell_point import EllipticCurvePoint_finite_field

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('old_ell_point',
                                               HERE / 'baseline/ell_point.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
original = old.EllipticCurvePoint_field._add_


class AdditionTests(unittest.TestCase):
    def compare(self, curve):
        point = curve.random_point()
        other = curve.random_point()
        zero = curve(0)
        inputs = [zero, point, other, -point, 2*point]
        if (curve.base_ring().characteristic() == 2
                and curve.a1() == 1 and curve.a3() == 0):
            inputs.append(curve(0, curve.a6().sqrt()))
            if point:
                unnormalized = copy.copy(point)
                scale = curve.base_ring().gen()
                unnormalized._coords = tuple(c*scale for c in point)
                unnormalized._normalized = False
                inputs.append(unnormalized)
        for P in inputs:
            for Q in inputs:
                with self.subTest(curve=curve, P=P, Q=Q):
                    actual = P+Q
                    expected = original(P, Q)
                    self.assertEqual(actual, expected)
                    self.assertIs(type(actual), type(expected))
                    self.assertIs(actual.curve(), curve)
                    self.assertIs(actual.parent(), expected.parent())

    def test_binary_context_switches(self):
        curves = []
        for degree, a in ((19, 1), (67, 0), (131, 1), (163, 1)):
            field = GF(2**degree, 'z', impl='ntl')
            curves.append(EllipticCurve(field, [1, a, 0, 0, 1]))
        standard = GF(2**131, 'z', impl='ntl')
        alternate = GF(2**131, 'w',
                       modulus=standard.modulus().reverse(), impl='ntl')
        curves.append(EllipticCurve(alternate, [1, 0, 0, 0, 1]))
        for _ in range(2):
            for curve in curves:
                self.compare(curve)

    def test_unsupported_models_and_prime_fields(self):
        field = GF(2**19, 'z', impl='ntl')
        curves = [EllipticCurve(field, [1, 1, field.gen(), 0, 1]),
                  EllipticCurve(GF(101), [1, 1]),
                  EllipticCurve(GF(101), [1, 0, 0, 0, 1]),
                  EllipticCurve(GF(5**2, 'z'), [1, 1]),
                  EllipticCurve(GF(3**5, 'z'), [1, 1]),
                  EllipticCurve(GF(2**8, 'z', impl='givaro'), [1, 1, 0, 0, 1])]
        for curve in curves:
            self.compare(curve)
        rational = EllipticCurve(QQ, [1, 1])
        point = rational(0, 1)
        self.assertEqual(point + (-point), original(point, -point))

    def test_custom_point_class(self):
        field = GF(2**19, 'z', impl='ntl')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        P, Q = curve.random_point(), curve.random_point()
        calls = {'initialize': 0}

        class CustomPoint(EllipticCurvePoint_finite_field):
            def __init__(self, *args, **kwargs):
                calls['initialize'] += 1
                super().__init__(*args, **kwargs)
                self.marker = 'constructed'

        prior = curve._point
        try:
            curve._point = CustomPoint
            custom_P = CustomPoint(curve, list(P), check=False)
            custom_Q = CustomPoint(curve, list(Q), check=False)
            candidate = EllipticCurvePoint_finite_field._add_
            try:
                EllipticCurvePoint_finite_field._add_ = original
                before = calls['initialize']
                expected = custom_P + custom_Q
                incumbent_initializations = calls['initialize'] - before
            finally:
                EllipticCurvePoint_finite_field._add_ = candidate
            before = calls['initialize']
            actual = custom_P + custom_Q
            self.assertEqual(actual, expected)
            self.assertIs(type(actual), CustomPoint)
            self.assertEqual(actual.marker, 'constructed')
            self.assertEqual(calls['initialize'] - before, incumbent_initializations)
        finally:
            curve._point = prior

    def test_optional_native_extension_fallback(self):
        curves = [EllipticCurve(GF(2**19, 'z', impl='ntl'), [1, 1, 0, 0, 1]),
                  EllipticCurve(GF(101), [1, 1])]
        previous = binary_batch._native
        try:
            binary_batch._native = None
            for curve in curves:
                P, Q = curve.random_point(), curve.random_point()
                actual = P+Q
                expected = original(P, Q)
                self.assertEqual(actual, expected)
                self.assertIs(actual.parent(), expected.parent())
        finally:
            binary_batch._native = previous


if __name__ == '__main__':
    unittest.main(verbosity=2)
