"""Installed scalar/batch regressions without archived platform binaries.

The oracle uses affine Weierstrass formulas on field elements. It does not
call Sage point addition, scalar multiplication, or the optimized modules.
"""
import pickle
import unittest

from sage.all import EllipticCurve, GF, ZZ, set_random_seed
from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl


def affine_add(curve, left, right):
    if left is None:
        return right
    if right is None:
        return left
    a1, a2, a3, a4, _ = curve.ainvs()
    x1, y1 = left
    x2, y2 = right
    if x1 == x2:
        if y1 + y2 + a1*x1 + a3 == 0:
            return None
        slope = (3*x1*x1 + 2*a2*x1 + a4 - a1*y1)/(2*y1 + a1*x1 + a3)
    else:
        slope = (y2-y1)/(x2-x1)
    intercept = y1 - slope*x1
    x3 = slope*slope + a1*slope - a2 - x1 - x2
    return x3, -(slope+a1)*x3 - intercept - a3


def reference(point, scalar):
    curve = point.curve()
    coords = point.xy() if point else None
    scalar = int(scalar)
    if scalar < 0:
        if coords is not None:
            x, y = coords
            coords = x, -y-curve.a1()*x-curve.a3()
        scalar = -scalar
    result = None
    while scalar:
        if scalar & 1:
            result = affine_add(curve, result, coords)
        coords = affine_add(curve, coords, coords)
        scalar >>= 1
    return curve(0) if result is None else curve(result)


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        set_random_seed(2026092801)

    def assert_point(self, actual, expected):
        self.assertEqual(actual, expected)
        self.assertIs(type(actual), type(expected))
        self.assertIs(actual.parent(), expected.parent())
        self.assertIs(actual.curve(), expected.curve())
        self.assertEqual(hash(actual), hash(expected))
        self.assertEqual(pickle.loads(pickle.dumps(actual)), expected)
        self.assertTrue(not actual or actual.curve().is_on_curve(*actual.xy()))

    def test_native_dispatch(self):
        self.assertIs(binary_batch._native, binary_batch_ntl)
        calls = dict.fromkeys(('_pari_point', '_add_pairs', '_from_pari_point'), 0)
        originals = {name: getattr(binary_batch_ntl, name) for name in calls}
        def wrap(name):
            def counted(*args, **kwargs):
                calls[name] += 1
                return originals[name](*args, **kwargs)
            return counted
        try:
            for name in calls:
                setattr(binary_batch_ntl, name, wrap(name))
            E = EllipticCurve(GF(2**131, 'z', impl='ntl'), [1, 1, 0, 0, 1])
            P, Q = E.random_point(), E.random_point()
            self.assert_point(17*P, reference(P, 17))
            expected = affine_add(E, P.xy(), Q.xy())
            self.assertEqual(binary_batch.add_pairs(E, [(P, Q)]),
                             [E(0) if expected is None else E(expected)])
        finally:
            for name, function in originals.items():
                setattr(binary_batch_ntl, name, function)
        for name, count in calls.items():
            self.assertGreater(count, 0, name)

    def test_exhaustive_small_scalar(self):
        for degree in (2, 3, 4):
            F = GF(2**degree, 'z', impl='ntl')
            for a in (0, 1, F.gen()):
                E = EllipticCurve(F, [1, a, 0, 0, 1])
                for P in E:
                    for k in (-17, -2, -1, 0, 1, 2, 17):
                        self.assert_point(ZZ(k)*P, reference(P, k))

    def test_scalar_word_boundaries_and_modulus_switch(self):
        for degree in (19, 31, 32, 33, 63, 64, 65, 127, 128, 129, 131, 163, 255, 256, 257):
            F = GF(2**degree, 'z', impl='ntl')
            for a in (F(1), F.gen()):
                E = EllipticCurve(F, [1, a, 0, 0, 1])
                P = E.random_point()
                for k in (-17, 0, 17, 2**(degree-1)+12345):
                    with self.subTest(degree=degree, scalar=k, coefficient=str(a)):
                        expected = reference(P, k)
                        other = GF(2**7, 'other', impl='ntl')
                        other.gen()**19  # Switch the active NTL modulus.
                        self.assert_point(ZZ(k)*P, expected)

    def test_generic_fields_and_custom_constructor(self):
        fields = (GF(101), GF(65537), GF(2**19, 'p', impl='pari_ffelt'),
                  GF(2**8, 'g', impl='givaro'), GF(5**3, 'a'))
        for F in fields:
            E = EllipticCurve(F, [1, 1, 0, 0, 1])
            P = E.random_point()
            for k in (-17, 0, 2, 17, 1234567):
                self.assert_point(ZZ(k)*P, reference(P, k))
        E = EllipticCurve(GF(2**19, 'z', impl='ntl'), [1, 1, 0, 0, 1])
        P = E.random_point()
        expected = reference(P, 17)
        constructor = E._point
        class CustomPoint(constructor):
            pass
        E._point = CustomPoint
        try:
            native = binary_batch._native
            try:
                binary_batch._native = None
                fallback = 17*P
            finally:
                binary_batch._native = native
            # Sage can retain the input point class when the curve's
            # constructor is replaced. Match the existing fallback contract.
            self.assert_point(17*P, fallback)
            self.assertEqual(fallback, expected)
        finally:
            E._point = constructor

    def test_optional_native_fallback(self):
        E = EllipticCurve(GF(2**19, 'z', impl='ntl'), [1, 1, 0, 0, 1])
        P = E.random_point()
        expected = reference(P, 17)
        native = binary_batch._native
        try:
            binary_batch._native = None
            self.assert_point(17*P, expected)
            self.assertEqual(binary_batch.add_pairs(E, [(P, -P), (P, P)]),
                             [E(0), reference(P, 2)])
        finally:
            binary_batch._native = native

    def test_fused_and_cartesian(self):
        E = EllipticCurve(GF(2**4, 'z', impl='ntl'), [1, 1, 0, 0, 1])
        points = list(E)
        pairs = [(P, Q) for P in points for Q in points]
        for power in (-1, 0, 1, 7):
            expected = []
            for P, Q in pairs:
                left = tuple(v.frobenius(power % 4) for v in P.xy()) if P else None
                right = Q.xy() if Q else None
                coords = affine_add(E, left, right)
                expected.append(E(0) if coords is None else E(coords))
            self.assertEqual(binary_batch.frobenius_add_pairs(E, iter(pairs), power), expected)
            if power == 0:
                for size in (1, 3, 17):
                    self.assertEqual(binary_batch.add_cartesian(E, iter(points), iter(points),
                                                               block_size=size), expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
