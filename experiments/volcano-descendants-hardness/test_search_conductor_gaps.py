import unittest

from search_conductor_gaps import (
    factor_with_certificate, koblitz_invariants, kronecker_minus7, search,
)


class SearchTests(unittest.TestCase):
    def test_independent_known_degrees(self):
        for m, conductor in [(19, 457), (83, 6473*53676929),
                             (131, 263*146505763881528721)]:
            inv = koblitz_invariants(m)
            self.assertEqual(inv['frobenius_conductor'], conductor)
        self.assertEqual(koblitz_invariants(19)['trace'], 797)
        self.assertEqual(koblitz_invariants(131)['trace'], -22283658519494248867)
        # Independent trace recurrence from X^2+X+2, rather than tau^m=a+b*tau.
        t_previous, t_current = 2, -1
        for m in range(2, 132):
            t_previous, t_current = t_current, -t_current-2*t_previous
            self.assertEqual(koblitz_invariants(m)['trace'], t_current)

    def test_m127_excluded_prime(self):
        result = search(127, 127, 60)
        self.assertEqual(result['counts']['complete_factorizations'], 1)
        hit = result['ranked_hits'][0]
        self.assertEqual(hit['prime'], '3293187233103900007')
        self.assertEqual(hit['prime_bits'], 62)
        self.assertEqual(hit['kronecker_minus7'], 1)
        self.assertEqual(hit['class_number_ratio_to_maximal'],
                         '3293187233103900006')
        self.assertIsNone(result['rows'][0]['destination_curve_id'])

    def test_factor_proposal_is_verified(self):
        factors, status, _ = factor_with_certificate(263*146505763881528721, 2)
        self.assertEqual(status, 'complete')
        self.assertEqual(factors, {263: 1, 146505763881528721: 1})
        self.assertEqual(kronecker_minus7(2), 1)
        self.assertEqual(kronecker_minus7(7), 0)


if __name__ == '__main__':
    unittest.main()
