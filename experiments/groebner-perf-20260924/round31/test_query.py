"""Complete public queries preserve packed transport and independent checks."""
import os
import unittest
from unittest.mock import patch

from quadratic import Basis, BaselineQuery, QuadraticQuery, SparseChecker
from sparse_checker import Curve, GF2n, Point, PackedANF
from descend import make_instance
from quadratic_reference import truth_roots, branch_counts
from test_quadratic import roots


class QueryTests(unittest.TestCase):
    def test_complete_queries_and_fresh_packed_inputs(self):
        builds = [('cpu', False), ('cpu', True)]
        if os.environ.get('QUADRATIC_TEST_METAL') == '1':
            builds.append(('metal', False))
        for backend, sanitizer in builds:
            for n, ell, seeds in ((31, 6, (101, 102, 105)), (11, 3, (101, 102)), (83, 2, (101,))):
                f = make_instance(n, 3, ell, seed=seeds[0])
                shape = (n, f.mod, f.b, 3, ell)
                oracle = Curve(GF2n(n, f.mod), f.b)
                with BaselineQuery(*shape, arm='sparse', sanitizer=sanitizer) as baseline, \
                     QuadraticQuery(*shape, sanitizer=sanitizer, backend=backend) as candidate:
                    for seed in seeds:
                        f = make_instance(n, 3, ell, seed=seed)
                        target = oracle.sum(f.points)
                        with patch.object(PackedANF, 'items', side_effect=AssertionError('ANF expanded')), \
                             patch.object(PackedANF, 'to_dict', side_effect=AssertionError('ANF materialized')):
                            left, right = baseline.solve(target), candidate.solve(target)
                        self.assertTrue(right['verified'])
                        for key in ('status', 'basis_terms', 'assignment', 'curve_witness'):
                            self.assertEqual(left[key], right[key])
                        self.assertEqual(right['complete_query_ns'], sum(right['phases_ns'].values()))
                        self.assertTrue(all(f.evaluate(r) == 0 for r in right['basis_certificate']['solutions']))
                        points = [Point(**p) for p in right['curve_witness']['points']]
                        self.assertTrue(all(oracle.on_curve(p) for p in points))
                        self.assertEqual(oracle.sum(points), target)
                        if (n, ell, seed) == (31, 6, 105):
                            self.assertEqual(right['metrics']['fallback_branches'], 4)
                            self.assertEqual(right['metrics']['fallback_assignments'], 256)

    def test_dimensions_checker_ownership_and_closed_workspace(self):
        with self.assertRaises(ValueError):
            Basis(14, 7, 31)  # Exact exhaustive certificate is still limited to 20.
        with SparseChecker(5, 2) as checker:
            with self.assertRaises(ValueError):
                Basis(2, 2, 2, checker=checker)
            with Basis(2, 3, 2, checker=checker) as basis:
                basis.close()
                with self.assertRaises(RuntimeError):
                    basis.compute(None)
            self.assertTrue(checker._handle)  # Shared checker remains owned by caller.
        f = make_instance(11, 3, 2, seed=5)
        with self.assertRaises(ValueError):
            QuadraticQuery(11, f.mod, f.b, 2, 2)
        with QuadraticQuery(11, f.mod, f.b, 3, 2) as query:
            with self.assertRaises(ValueError):
                query.solve(Point(0, 0, True))
            query.close()
            with self.assertRaises(RuntimeError):
                query.solve(f.points[0])

    def test_independent_truth_bitmap_oracle(self):
        for bits in range(256):
            items = [(m, 1) for m in range(8) if bits>>m&1]
            self.assertEqual(truth_roots(3, 1, items), roots(3, items))
        items = [(1, 1<<127), (2, 1), (0, 1), (3, 1<<64), (3, 1<<64)]
        self.assertEqual(truth_roots(5, 128, items), roots(5, items))
        counts = branch_counts(1, 2, 3, [(2, 1), (4, 2), (6, 4), (0, 4)])
        self.assertEqual(counts['consistent'], 2)
        self.assertEqual(counts['lifted_candidates'], 2)


if __name__ == '__main__':
    unittest.main()
