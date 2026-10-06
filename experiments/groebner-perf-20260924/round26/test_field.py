"""Compare independent inversion with exponentiation and exact curve arithmetic."""
import random
import unittest
from unittest.mock import patch

from reference_field import EuclidField, GF2n
from replay_query import ToyCurve, Curve, Point, point, scalar_replay, IDENTITY


class FieldTests(unittest.TestCase):
    def test_exhaustive_inverses_in_small_and_complete_13_bit_fields(self):
        count = 0
        for n, mod in ((3, None), (5, None), (8, 0x11b), (8, 0x11d), (11, None), (13, None)):
            oracle = GF2n(n, mod)
            fast = EuclidField(n, oracle.mod)
            for a in range(1, 1 << n):
                actual = fast.inv(a)
                self.assertEqual(actual, oracle.inv(a))
                self.assertEqual(oracle.mul(a, actual), 1)
                self.assertTrue(0 < actual < 1 << n)
                count += 1
        print('Exhaustive nonzero inverse comparisons:', count)

    def test_larger_fields_against_exponentiation(self):
        rng, count = random.Random(2026092901), 0
        fields = [(17, None), (19, None), (31, (1 << 31) | 9),
                  (64, (1 << 64) | 27), (128, (1 << 128) | 135)]
        for n, mod in fields:
            oracle = GF2n(n, mod)
            fast = EuclidField(n, oracle.mod)
            for a in [1, 1 << (n-1), (1 << n)-1] + [rng.randrange(1, 1 << n) for _ in range(128)]:
                inverse = fast.inv(a)
                self.assertEqual(inverse, oracle.inv(a))
                self.assertEqual(oracle.mul(a, inverse), 1)
                count += 1
        print('Random/boundary inverse controls through 128 bits:', count)

    def test_invalid_elements_and_nonunits_terminate(self):
        field = EuclidField(8, 0x11b)
        with self.assertRaises(ZeroDivisionError): field.inv(0)
        for a in (-1, 256, True, False, 1.0, '1', None):
            with self.subTest(a=a), self.assertRaises(ValueError): field.inv(a)
        # The public constructor validates irreducibility. Even corrupted
        # internal state must terminate if the element is not a unit.
        field.mod = 0x101
        with self.assertRaises(ZeroDivisionError): field.inv(3)

    def test_no_exponentiation_or_native_dependency_in_inverse(self):
        field = EuclidField(13)
        expected = GF2n(13, field.mod).inv(173)
        with patch.object(GF2n, 'pow', side_effect=AssertionError('power oracle called')):
            self.assertEqual(field.inv(173), expected)
        self.assertIs(EuclidField.mul, GF2n.mul)
        self.assertIs(EuclidField.sqr, GF2n.sqr)

    def test_all_toy_subgroup_points_and_exceptional_curve_cases(self):
        c = ToyCurve(13)
        old = Curve(GF2n(c.n, c.mod), c.b)
        fast = Curve(EuclidField(c.n, c.mod), c.b)
        G = point(c.G)
        for k in range(c.r):
            expected = scalar_replay(old, G, k)
            self.assertEqual(scalar_replay(fast, G, k), expected)
            self.assertTrue(fast.on_curve(expected))
            self.assertEqual(fast.add(expected, G), old.add(expected, G))
            self.assertEqual(fast.add(expected, expected), old.add(expected, expected))
            self.assertEqual(fast.add(expected, fast.neg(expected)), IDENTITY)
            self.assertEqual(fast.add(expected, IDENTITY), expected)
        torsion = Point(0, 1)
        self.assertTrue(fast.on_curve(torsion))
        self.assertEqual(fast.add(torsion, torsion), IDENTITY)
        self.assertEqual(scalar_replay(fast, torsion, c.r), torsion)
        print('Full subgroup scalar/curve controls:', c.r)


if __name__ == '__main__':
    unittest.main()
