"""Support-only symmetry proof across equation limbs and canceled coefficients."""
import unittest
from test_symmetry import candidate, producer, accepted_checker, truth

class SparseGuardTests(unittest.TestCase):
    def test_each_equation_boundary_and_fresh_cancellations(self):
        for sanitizer in (False, True):
            for equations in (31, 32, 63, 64, 65, 127, 128):
                high = 1 << (equations - 1)
                base = [(4, 1), (24, 2), (0, 2)]
                systems = [(base + [(1, high), (2, high)], True),
                           (base + [(1, high)], False),
                           (base + [(2, high)], False),
                           (base + [(1, high), (1, high)], True),
                           (base + [(2, high), (1, high), (1, high), (2, high)], True)]
                with producer.Producer(2, 3, equations, sanitizer=sanitizer) as p, candidate.Checker(2, 3, equations, sanitizer=sanitizer) as c, accepted_checker.Checker(2, 3, equations, sanitizer=sanitizer) as old:
                    for terms, symmetric in systems:
                        packed = producer.Packed(5, equations, terms)
                        answer = p.produce(packed)
                        check = c.certify(packed, answer['roots'], answer['basis'], answer['proof_bytes'])
                        baseline = old.certify(packed, answer['roots'], answer['basis'], answer['proof_bytes'])
                        self.assertTrue(check['verified'])
                        self.assertTrue(baseline['verified'])
                        self.assertEqual(answer['roots'], truth(5, terms))
                        self.assertEqual(check['symmetry_check_stats']['enabled'], int(symmetric))
                        self.assertEqual(check['symmetry_check_stats']['asymmetric_fallback'], int(not symmetric))
                        self.assertGreater(check['symmetry_check_stats']['guard_coefficients'], 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
