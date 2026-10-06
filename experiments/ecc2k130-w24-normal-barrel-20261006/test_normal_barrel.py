"""Structural tests for the normal-basis Frobenius front end."""

import unittest

from normal_barrel import DEGREE, NormalBasis, barrel, square


class NormalBarrelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.basis = NormalBasis.first("ecc2k130-w24-normal-element-v1", 1023)

    def test_full_rank_round_trips_and_frobenius(self):
        self.assertEqual(len(self.basis.reducer.pivots), DEGREE)
        for bit in range(DEGREE):
            self.assertEqual(self.basis.to_polynomial(self.basis.to_normal(1 << bit)),
                             1 << bit)
        for word in (0, 1, 42, (1 << 130) | (1 << 31) | 1):
            code = self.basis.to_normal(word)
            self.assertEqual(self.basis.to_polynomial(code), word)
            power = word
            for exponent in range(DEGREE):
                if exponent in (0, 1, 2, 7, 31, 65, 127, 128, 129, 130):
                    self.assertEqual(self.basis.to_polynomial(barrel(code, exponent)), power)
                power = square(power)
            self.assertEqual(power, word)

    def test_seed_linear_map_and_gate_ledger(self):
        for mask in (1, 7, 0xabcdef, (1 << 24) - 1):
            code = self.basis.seed_code(mask)
            expected = 0
            for bit, word in enumerate(self.basis.w24_to_normal_columns):
                if (mask >> bit) & 1:
                    expected ^= word
            self.assertEqual(code, expected)
        counts = self.basis.gate_counts()
        self.assertEqual(counts["per_leaf_barrel_mux"], 8 * DEGREE)
        self.assertEqual(counts["five_leaf_barrel_mux"], 5 * 8 * DEGREE)
        self.assertGreater(counts["per_leaf_seed_map_xor"], 0)
        self.assertGreater(counts["per_leaf_output_map_xor"], 0)

    def test_wrong_rotation_and_out_of_range_are_detected(self):
        code = self.basis.to_normal((1 << 99) | (1 << 13) | 1)
        self.assertNotEqual(barrel(code, 1), barrel(code, 2))
        self.assertNotEqual(self.basis.to_polynomial(barrel(code, 2)), square(
            self.basis.to_polynomial(code)))
        for exponent in (-1, 131, 255):
            with self.assertRaises(ValueError):
                barrel(code, exponent)


if __name__ == "__main__":
    unittest.main()
