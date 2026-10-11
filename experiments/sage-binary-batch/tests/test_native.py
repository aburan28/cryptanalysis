"""Regression coverage for native arithmetic and NTL modulus isolation."""
import importlib.util
from pathlib import Path
import sys
import unittest

from sage.all import EllipticCurve, GF, PolynomialRing, set_random_seed
from sage.schemes.elliptic_curves import binary_batch, binary_batch_ntl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from public_points import generate
from test_binary_batch import BinaryBatchTests
import test_binary_batch

# Run the complete existing suite against normal installed imports.
test_binary_batch.candidate = binary_batch
test_binary_batch.add_pairs = binary_batch.add_pairs


class NativeTests(unittest.TestCase):
    def test_installed_native_is_selected(self):
        self.assertIs(binary_batch._native, binary_batch_ntl)
        self.assertTrue(binary_batch_ntl.supports(GF(2**19, 'z')))
        self.assertFalse(binary_batch_ntl.supports(GF(2**3, 'z')))

    def test_exhaustive_ntl_and_alternate_moduli(self):
        ring = PolynomialRing(GF(2), 't')
        t = ring.gen()
        for modulus in (t**3+t+1, t**3+t**2+1, t**4+t+1):
            field = GF(2**modulus.degree(), 'z', modulus=modulus, impl='ntl')
            for a, b in ((field(0), field(1)), (field(1), field(1)),
                         (field.gen(), field.gen())):
                curve = EllipticCurve(field, [1, a, 0, 0, b])
                points = list(curve)
                expected = [P+Q for P in points for Q in points]
                self.assertEqual(binary_batch.add_pairs(curve,
                    ((P,Q) for P in points for Q in points)), expected)
                for block in (1, 3, 17, 1024):
                    self.assertEqual(binary_batch.add_cartesian(
                        curve, iter(points), iter(points), block), expected)

    def test_generator_modulus_switch_and_exception(self):
        set_random_seed(2026092431)
        field = GF(2**19, 'z')
        other = GF(2**31, 'w')
        curve = EllipticCurve(field, [1, field.gen(), 0, 0, field.gen()])
        points, _ = generate(curve, 12, 43)
        expected = [P+Q for P,Q in zip(points, reversed(points))]

        def pairs():
            for P,Q in zip(points, reversed(points)):
                other.gen() ** 12345  # Changes the active NTL modulus.
                yield P,Q

        self.assertEqual(binary_batch.add_pairs(curve, pairs()), expected)

        def broken():
            yield points[0], points[1]
            raise RuntimeError('fixture error')

        with self.assertRaisesRegex(RuntimeError, 'fixture error'):
            binary_batch.add_pairs(curve, broken())
        self.assertEqual(binary_batch.add_pairs(curve, pairs()), expected)

    def test_native_word_boundaries(self):
        set_random_seed(2026092432)
        for degree in (17, 63, 65, 127, 129, 163, 257):
            field = GF(2**degree, 'z', impl='ntl')
            curve = EllipticCurve(field, [1, field.gen(), 0, 0, field.gen()])
            points, _ = generate(curve, 12, degree)
            points += [curve(0), curve(0, field.gen().sqrt())]
            pairs = [(P,Q) for P,Q in zip(points, reversed(points))]
            pairs += [(P,P) for P in points] + [(P,-P) for P in points]
            self.assertEqual(binary_batch.add_pairs(curve, pairs),
                             [P+Q for P,Q in pairs])

    def test_fallback_matches_native(self):
        spec = importlib.util.spec_from_file_location('incumbent', HERE/'baseline/binary_batch.py')
        incumbent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(incumbent)
        field = GF(2**19, 'z')
        curve = EllipticCurve(field, [1, 1, 0, 0, 1])
        points, _ = generate(curve, 20, 23)
        expected = incumbent.add_cartesian(curve, points, points)
        native = binary_batch._native
        try:
            binary_batch._native = None
            self.assertEqual(binary_batch.add_cartesian(curve, points, points), expected)
        finally:
            binary_batch._native = native
        self.assertEqual(binary_batch.add_cartesian(curve, points, points), expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
