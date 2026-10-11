import unittest

from boolean_basis import canonical_terms, certify_boolean_basis


class BooleanCertificateTests(unittest.TestCase):
    def test_boolean_field_pairs_are_required(self):
        self.assertFalse(certify_boolean_basis(2, [[0, 3]], [[0, 3]])["verified"])
        result = certify_boolean_basis(2, [[0, 3]], [[0, 1], [0, 2]])
        self.assertTrue(result["verified"])
        self.assertEqual(result["root_count"], 1)
        self.assertEqual(result["solutions"], [3])

    def test_rejects_wrong_ideal_even_when_generators_reduce_to_zero(self):
        # [1] is a GB and all inputs reduce to zero, but it discards real roots.
        self.assertFalse(certify_boolean_basis(2, [[1]], [[0]])["verified"])

    def test_rejects_nonreduced_basis(self):
        self.assertFalse(certify_boolean_basis(2, [[1], [2]], [[1, 2], [2]])["verified"])
        self.assertFalse(certify_boolean_basis(2, [[1]], [[1], [1, 3]])["verified"])

    def test_zero_and_unit_ideals_and_term_cancellation(self):
        self.assertEqual(canonical_terms([1, 1, 2]), [2])
        self.assertTrue(certify_boolean_basis(2, [], [])["verified"])
        self.assertTrue(certify_boolean_basis(2, [[1, 1]], [])["verified"])
        self.assertTrue(certify_boolean_basis(2, [[1], [0, 1]], [[0]])["verified"])
        self.assertFalse(certify_boolean_basis(2, [], [[1, 1]])["verified"])

    def test_bounds(self):
        with self.assertRaises(ValueError):
            certify_boolean_basis(13, [], [])
        with self.assertRaises(ValueError):
            certify_boolean_basis(2, [[4]], [])

    def test_uncached_certificate_above_small_table_bound(self):
        equations = [[1 << v] for v in range(13)]
        result = certify_boolean_basis(13, equations, equations, monomial_cache=False)
        self.assertTrue(result["verified"])
        self.assertEqual(result["root_count"], 1)
        self.assertEqual(result["solutions"], [0])
        self.assertFalse(certify_boolean_basis(13, equations, equations[:-1],
                                             monomial_cache=False)["verified"])


if __name__ == "__main__":
    unittest.main()
