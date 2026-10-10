import math
import unittest

from p256_isogeny_search.analysis import (
    prove_prime,
    small_isogeny_degree_classes,
    structural_report,
    verified_discriminant_factors,
)
from p256_isogeny_search.constants import P256


class StructuralAnalysisTests(unittest.TestCase):
    def test_discriminant_factorization_is_proved_and_squarefree(self):
        factors = verified_discriminant_factors()
        self.assertEqual(math.prod(factors), abs(P256.frobenius_discriminant))
        self.assertEqual(len(factors), len(set(factors)))
        self.assertTrue(all(prove_prime(value) for value in factors))

    def test_report_classifies_a_single_maximal_order(self):
        report = structural_report(isogeny_prime_bound=47)
        self.assertTrue(report["frobenius"]["discriminant_is_fundamental"])
        self.assertTrue(report["frobenius"]["prime_factor_certificates_verified"])
        self.assertEqual(
            report["endomorphism_orders"][
                "frobenius_order_conductor_in_maximal_order"
            ],
            1,
        )
        self.assertEqual(len(report["endomorphism_orders"]["possible_orders"]), 1)

    def test_small_prime_splitting(self):
        classes = small_isogeny_degree_classes(P256.frobenius_discriminant, 13)
        self.assertEqual(classes["ramified"], [3, 5])
        self.assertEqual(classes["split"], [11, 13])
        self.assertEqual(classes["inert"], [2, 7])


if __name__ == "__main__":
    unittest.main()
