"""Exact controls on both sides of the lifted-enumeration branch condition."""
import os
import sys
import unittest

from adapter import HERE, Checker, load, producer

prior = load('lazy51_boundary_prior49', HERE.parent / 'round49/adapter.py')
sys.path.insert(0, str(HERE))

CASES = (
    ('above', 2, [(12, 1), (20, 2)], 4, 20),
    ('equal', 3, [(12, 1), (20, 2), (24, 4)], 3, 16),
    ('below', 4, [(12, 1), (20, 2), (24, 4), (4, 8)], 2, 12),
    ('full-rank', 6, [(12, 1), (20, 2), (24, 4), (4, 8), (8, 16), (16, 32)], 0, 4),
    ('inconsistent', 4, [(12, 1), (20, 2), (24, 4), (0, 8)], 3, 0),
)


def truth(terms):
    roots = []
    for assignment in range(32):
        value = 0
        for monomial, coefficient in terms:
            if assignment & monomial == monomial:
                value ^= coefficient
        if not value:
            roots.append(assignment)
    return roots


class NullspaceBoundaryTests(unittest.TestCase):
    def test_exact_branch_boundary_and_unchanged_proofs(self):
        modes = [('cpu', False), ('cpu', True)]
        if os.environ.get('QUADRATIC_TEST_METAL') == '1':
            modes.append(('metal', False))
        for backend, sanitizer in modes:
            for name, equations, terms, nullity, count in CASES:
                expected = truth(terms)
                self.assertEqual(len(expected), count)
                packed = producer.Packed(5, equations, terms)
                with producer.Producer(2, 3, equations, backend=backend, sanitizer=sanitizer) as candidate, \
                        prior.producer.Producer(2, 3, equations, backend=backend, sanitizer=sanitizer) as accepted, \
                        Checker(2, 3, equations, sanitizer=sanitizer, identity='factored_local') as checker:
                    for partial, projection in ((False, False), (False, True), (True, False), (True, True)):
                        for p in (candidate, accepted):
                            p.configure_partial(partial)
                            p.configure_gpu_projection(projection)
                        actual = candidate.produce(packed, checker=checker)
                        baseline = accepted.produce(packed, checker=checker)
                        with self.subTest(backend=backend, sanitizer=sanitizer, case=name,
                                          partial=partial, projection=projection):
                            self.assertEqual(actual['roots'], expected)
                            for field in ('roots', 'basis', 'proof_bytes', 'gpu_projection_stats'):
                                self.assertEqual(actual[field], baseline[field])
                            self.assertTrue(actual['certificate']['verified'])
                            self.assertEqual(actual['stats']['max_nullity'], nullity)
                            for field in ('stats', 'partial_stats', 'projection_stats',
                                          'normalization_stats', 'multiplier_stats',
                                          'deferred_stats', 'symmetry_stats'):
                                for key, value in actual[field].items():
                                    if type(value) in (int, bool):
                                        self.assertEqual(value, baseline[field][key], (field, key))
                            if name != 'inconsistent':
                                self.assertEqual(actual['stats']['lifted_candidates'] > 0, nullity < 3)


if __name__ == '__main__':
    unittest.main()
