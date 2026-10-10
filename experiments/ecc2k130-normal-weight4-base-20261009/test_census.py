"""Small-degree exhaustive controls for orbit enumeration and inversion."""

from __future__ import annotations

import itertools
import math
import unittest

from census import canonical_mask, cyclic_gap_representatives, inverse_mod, multiply_mod


def rotate(mask: int, degree: int) -> int:
    limit = (1 << degree) - 1
    return ((mask << 1) & limit) | (mask >> (degree - 1))


def multiply_mod_reference(left: int, right: int, modulus: int, degree: int) -> int:
    product = 0
    while right:
        if right & 1:
            product ^= left
        left <<= 1
        right >>= 1
    while product.bit_length() > degree:
        product ^= modulus << (product.bit_length() - degree - 1)
    return product


class CensusControls(unittest.TestCase):
    def test_gap_orbits_partition_all_four_subsets(self) -> None:
        for degree in (7, 11, 13):
            representatives = list(cyclic_gap_representatives(degree))
            self.assertEqual(len(representatives), math.comb(degree, 4) // degree)
            expected = {
                sum(1 << index for index in indices)
                for indices in itertools.combinations(range(degree), 4)
            }
            observed: set[int] = set()
            for gaps, representative in representatives:
                self.assertEqual(sum(gaps), degree)
                self.assertEqual(representative.bit_count(), 4)
                word = representative
                for _ in range(degree):
                    self.assertNotIn(word, observed)
                    self.assertEqual(canonical_mask(word, degree), representative)
                    observed.add(word)
                    word = rotate(word, degree)
                self.assertEqual(word, representative)
            self.assertEqual(observed, expected)

    def test_binary_field_inverses_exhaustively(self) -> None:
        degree = 5
        modulus = (1 << 5) | (1 << 2) | 1
        for value in range(1, 1 << degree):
            inverse = inverse_mod(value, modulus, degree)
            self.assertEqual(multiply_mod(value, inverse, modulus, degree), 1)
            self.assertEqual(multiply_mod(value, inverse, modulus, degree),
                             multiply_mod_reference(value, inverse, modulus, degree))


if __name__ == "__main__":
    unittest.main()
