import random
import unittest

import curves
import field
import indexcalc_e2e as e


class CandidateTests(unittest.TestCase):
    def test_wide_inverse_and_trace_match_original_reference(self):
        for m in (5, 9, 131):
            ref = field.Onb(m)
            audit = e.AuditField(m, e.Ledger())
            rng = random.Random(3100 + m)
            for _ in range(8):
                value = ref.fromCoords(rng.randrange(1, 1 << m))
                self.assertEqual(audit.inv(value), ref.inv(value))
                self.assertEqual(audit.mul(value, audit.inv(value)), audit.one())
                self.assertEqual(audit.trace(value), ref.trace(value))
                self.assertTrue(audit.isSymmetric(audit.inv(value)))

    def test_subgroup_and_frobenius_coefficients(self):
        for m, weight in ((5, 4), (9, 2)):
            meter = e.Ledger()
            onb, curve, ell, generator, eigen, reps, lookup, _, _ = e.setup(m, weight, 3, meter)
            for point, (column, coeff) in lookup.items():
                self.assertIsNone(curve.mul(point, ell))
                self.assertLessEqual(onb.toCoords(point[0]).bit_count(), weight)
                self.assertEqual(curve.mul(reps[column], coeff), point)
                self.assertIn(curve.frob(point), lookup)
            # Compare orbit construction with an exhaustive coordinate sweep.
            for coordinate in range(1, 1 << m):
                if coordinate.bit_count() > weight:
                    continue
                point = curve.pointFromX(onb.fromCoords(coordinate))
                if point is not None and curve.mul(point, ell) is None:
                    self.assertIn(point, lookup)

    def test_matrix_dependence_and_recovery(self):
        matrix = e.RelationMatrix(2, 11, e.Ledger())
        self.assertTrue(matrix.push([1, 2], 8))
        self.assertFalse(matrix.push([2, 4], 5))
        self.assertTrue(matrix.push([3, 1], 9))
        x, y = matrix.solution()
        self.assertEqual((x + 2*y) % 11, 8)
        self.assertEqual((3*x + y) % 11, 9)
        with self.assertRaises(AssertionError):
            matrix.push([0, 0], 1)

    def test_decomposition_matches_exhaustive_oracle(self):
        for variant in ('reference', 'candidate'):
            meter = e.Ledger()
            context = e.setup(5, 4, 3, meter)
            onb, curve, ell, generator, _, _, lookup, _, _ = context
            verified = 0
            for scalar in range(1, ell):
                target = curve.mul(generator, scalar)
                row, details = e.decompose(context, target, 3, 4, variant, meter, budget=2)
                expected = e.oracle(curve, lookup, target, 3)
                if details['status'] not in ('budget', 'external_timeout'):
                    self.assertEqual(row is not None, expected)
                verified += row is not None
            # The reference may exhaust its 16-model bound on every query.
            # A bounded unknown is not an unsatisfiability certificate.
            if variant == 'candidate':
                self.assertGreater(verified, 0)


if __name__ == '__main__':
    unittest.main()
