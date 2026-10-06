"""Independent polynomial and witness controls for the W24 oracle."""

import hashlib
import unittest

from orbit_seed import (DEGREE, FIELD_MASK, MODULUS, OrbitClosedW24,
                        frobenius, seed_from_mask, square)


def square_by_monomials(word: int) -> int:
    raw = 0
    for bit in range(DEGREE):
        if word & (1 << bit):
            raw ^= 1 << (2 * bit)
    for bit in range(2 * DEGREE - 2, DEGREE - 1, -1):
        if raw & (1 << bit):
            raw ^= MODULUS << (bit - DEGREE)
    return raw


class OrbitSeedTests(unittest.TestCase):
    def test_square_matches_monomial_reference_and_frobenius_period(self) -> None:
        for index in range(16):
            word = int.from_bytes(hashlib.sha256(f"square:{index}".encode()).digest(),
                                  "big") & FIELD_MASK
            self.assertEqual(square(word), square_by_monomials(word))
            self.assertEqual(square(frobenius(word, 130)), word)

    def test_seed_witnesses_reconstruct_across_conjugate_spaces(self) -> None:
        oracle = OrbitClosedW24()
        self.assertEqual(len(oracle.spaces), DEGREE)
        self.assertEqual(oracle.witnesses(0), ([], 0))
        for mask, exponent in ((1, 0), (3, 1), (0x13579b, 7),
                               (0x81abcd, 65), ((1 << 24) - 1, 130)):
            word = frobenius(seed_from_mask(mask, oracle.basis), exponent)
            witnesses, reductions = oracle.witnesses(word)
            self.assertIn({"mask": mask, "exponent": exponent}, witnesses)
            self.assertGreaterEqual(reductions, 0)
            for witness in witnesses:
                rebuilt = frobenius(seed_from_mask(witness["mask"], oracle.basis),
                                    witness["exponent"])
                self.assertEqual(rebuilt, word)


if __name__ == "__main__":
    unittest.main()
