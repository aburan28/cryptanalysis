import unittest
from collections import Counter

import audit


class CyclicGroup:
    def __init__(self, prime):
        self.prime = prime

    def add(self, first, second):
        value = ((first or 0) + (second or 0)) % self.prime
        return value or None


class SumsetTests(unittest.TestCase):
    def test_signed_single_generator_closed_form(self):
        group = CyclicGroup(11)
        actual = audit.histogram(group, [[1, 10]] * 3, True)
        self.assertEqual(actual, Counter({3: 1, 1: 1, 10: 1, 8: 1}))

    def test_disjoint_binary_weights(self):
        group = CyclicGroup(17)
        actual = audit.histogram(group, [[1, 16], [2, 15], [4, 13]], False)
        self.assertEqual(actual, Counter({v % 17: 1 for v in (-7, -5, -3, -1, 1, 3, 5, 7)}))

    def test_identity_is_retained_in_histogram(self):
        self.assertEqual(audit.histogram(CyclicGroup(11), [[1, 10]] * 2, True),
                         Counter({2: 1, None: 1, 9: 1}))

    def test_invariant_base_has_no_extra_support(self):
        base = [1, 2, 4]  # Invariant under multiplication by 2 modulo 7.
        shifted = [[pow(2, i, 7) * p % 7 for p in base] for i in range(3)]
        same = audit.histogram(CyclicGroup(7), [base] * 3, True)
        changed = audit.histogram(CyclicGroup(7), shifted, False)
        self.assertEqual(set(same), set(changed))
        self.assertNotEqual(sum(same.values()), sum(changed.values()))

    def test_empty_base(self):
        self.assertEqual(audit.histogram(CyclicGroup(11), [[]] * 3, False), {})

    def test_limits(self):
        with self.assertRaises(ValueError):
            audit.cell(131, 21, 6, audit.SEEDS[0])
        with self.assertRaises(ValueError):
            audit.histogram(CyclicGroup(101), [list(range(1, 11))] * 6, False)

    def test_binary_rank_dependencies(self):
        self.assertEqual(audit.binary_rank([0, 3, 5, 6, 3]), 2)
        self.assertEqual(audit.binary_rank([1, 2, 4, 8]), 4)

    def test_degree131_invariant_subspace_obstruction(self):
        self.assertEqual(pow(2, 130, 131), 1)
        for prime_divisor in (2, 5, 13):
            self.assertNotEqual(pow(2, 130 // prime_divisor, 131), 1)


if __name__ == "__main__":
    unittest.main()
