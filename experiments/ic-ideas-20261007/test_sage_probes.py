"""Small Sage-backed invariants used by the algebraic gates."""

import random
import unittest

from sage_probes import (bits, field, from_bits, multiplier_orbit,
                         norm_multipliers, order_two_mod, ring_mul)


class SageProbeTest(unittest.TestCase):
    def test_bit_encoding_roundtrip(self):
        K, _ = field(19)
        for value in (0, 1, 2, 7, (1 << 19)-1, 0x12345):
            self.assertEqual(bits(from_bits(K, value)), value)

    def test_n53_multiplier_classes(self):
        r = 21044858204113
        lam = 10244141222326
        self.assertEqual((lam*lam+lam+2) % r, 0)
        self.assertEqual(pow(lam, 53, r), 1)
        multipliers = norm_multipliers(16)
        self.assertEqual(len(multipliers), 21)
        classes = {multiplier_orbit(a+b*lam, lam, 53, r)
                   for a, b, _ in multipliers}
        self.assertEqual(len(classes), 10)

    def test_group_algebra_projection_is_multiplicative(self):
        K, _ = field(5)
        gamma = K.gen()
        self.assertEqual(gamma.multiplicative_order(), 31)
        def project(mask):
            return sum((gamma**i for i in range(31) if mask >> i & 1), K(0))
        rng = random.Random(20261007)
        for _ in range(32):
            a, b = rng.getrandbits(31), rng.getrandbits(31)
            self.assertEqual(project(ring_mul(a, b, 31)), project(a)*project(b))

    def test_rational_character_orbits(self):
        self.assertEqual([order_two_mod(n) for n in (19, 23, 131)],
                         [18, 11, 130])


if __name__ == "__main__":
    unittest.main()
