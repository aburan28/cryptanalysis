"""Exact packing contract for the guarded standard-point fast path."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

import numpy as np
from sage.all import EllipticCurve, GF
from sage.schemes.elliptic_curves import binary_hardware_codec as candidate
from sage.schemes.elliptic_curves.ell_point import EllipticCurvePoint_finite_field

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'sage-binary-hardware'))
from public_points import generate

old_so = next((HERE / 'baseline').glob('binary_hardware_codec*.so'))
package = types.ModuleType('_pack_incumbent')
package.__path__ = []
sys.modules[package.__name__] = package
name = package.__name__ + '.binary_hardware_codec'
spec = importlib.util.spec_from_file_location(name, old_so)
incumbent = importlib.util.module_from_spec(spec)
sys.modules[name] = incumbent
spec.loader.exec_module(incumbent)


class PackTests(unittest.TestCase):
    def compare(self, curve, points):
        words = (curve.base_ring().degree() + 31) // 32
        items = list(points)
        original = incumbent.pack_points(curve, iter(items), words)
        improved = candidate.pack_points(curve, iter(items), words)
        for left, right in zip(original, improved):
            np.testing.assert_array_equal(left, right)

    def test_standard_and_exceptional_inputs(self):
        for degree in (5, 19, 31, 67, 131, 163):
            field = GF(2**degree, 'z', impl='ntl')
            curve = EllipticCurve(field, [1, 1, 0, 0, 1])
            base, _ = generate(curve, 12, 2026093401 + degree)
            self.compare(curve, base + [-base[0], base[0], curve(0), curve(0, 1)])
            self.compare(curve, iter(base))

    def test_non_normalized_standard_point(self):
        field = GF(2**19, 'z', impl='ntl')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        base, _ = generate(curve, 1, 2026093481)
        point = curve._point(curve, list(base[0]), check=False)
        z = field.gen() + 1
        x, y = point.xy()
        point._coords = (x*z, y*z, z)
        self.assertEqual(point.xy(), (x, y))
        self.compare(curve, [point])

    def test_custom_xy_hook_and_wrong_curve(self):
        field = GF(2**19, 'z', impl='ntl')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        base, _ = generate(curve, 1, 2026093482)
        calls = []

        class CustomPoint(EllipticCurvePoint_finite_field):
            def xy(self):
                calls.append('xy')
                return super().xy()

        custom = CustomPoint(curve, list(base[0]), check=False)
        words = 1
        incumbent.pack_points(curve, [custom], words)
        self.assertEqual(calls, ['xy'])
        candidate.pack_points(curve, [custom], words)
        self.assertEqual(calls, ['xy', 'xy'])
        other = EllipticCurve(field, [1, 0, 0, 0, 1])
        for codec in (incumbent, candidate):
            with self.assertRaises(ValueError):
                codec.pack_points(curve, [other(0)], words)
            with self.assertRaises(ValueError):
                codec.pack_points(curve, [0], words)


if __name__ == '__main__':
    unittest.main(verbosity=2)
