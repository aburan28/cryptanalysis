"""Complete point queries, wider descent and a separate exhaustive root oracle."""
import importlib.util
import os
import unittest
from unittest.mock import patch

from certified import HERE
from query import CertifiedQuery, BaselineQuery, QuadraticQuery
from sparse_checker import Curve, GF2n, Point
from descend import make_instance
from wide_descent import NativeDescent as WideDescent, PackedANF as WidePacked
from native_descent import PackedANF
from quadratic_reference import verify_basis

spec = importlib.util.spec_from_file_location('branch_certificate_reference', HERE/'reference.py')
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class QueryTests(unittest.TestCase):
    def test_paired_eighteen_variable_queries_and_packed_transport(self):
        backends = ['cpu', 'metal'] if os.environ.get('QUADRATIC_TEST_METAL') == '1' else ['cpu']
        for backend in backends:
            f = make_instance(31, 3, 6, seed=101)
            shape = 31, f.mod, f.b, 3, 6
            curve = Curve(GF2n(31, f.mod), f.b)
            with BaselineQuery(*shape, arm='sparse') as baseline, CertifiedQuery(*shape, backend=backend) as candidate:
                for seed in (101, 102, 105):
                    f = make_instance(31, 3, 6, seed=seed)
                    target = curve.sum(f.points)
                    with patch.object(PackedANF, 'items', side_effect=AssertionError('expanded ANF')), \
                         patch.object(PackedANF, 'to_dict', side_effect=AssertionError('copied ANF')):
                        left, right = baseline.solve(target), candidate.solve(target)
                    self.assertTrue(right['verified'], right['basis_certificate'])
                    for key in ('basis_terms', 'assignment', 'curve_witness'):
                        self.assertEqual(left[key], right[key])
                    self.assertGreater(right['basis_certificate']['stats']['contradictions'], 4000)
                    self.assertLess(right['basis_certificate']['stats']['assignments'], 1024)
                    self.assertEqual(right['complete_query_ns'], sum(right['phases_ns'].values()))

    def test_complete_twenty_one_and_twenty_four_variable_queries(self):
        backends = ['cpu', 'metal'] if os.environ.get('QUADRATIC_TEST_METAL') == '1' else ['cpu']
        for ell in (7, 8):
            f = make_instance(31, 3, ell, seed=101)
            curve = Curve(GF2n(31, f.mod), f.b)
            expected = reference.chunked_roots(3*ell, 31, sorted(f.anf.items()))
            for backend in backends:
                with CertifiedQuery(31, f.mod, f.b, 3, ell, backend=backend) as candidate:
                    target = curve.sum(f.points)
                    with patch.object(WidePacked, 'items', side_effect=AssertionError('expanded ANF')), \
                         patch.object(WidePacked, 'to_dict', side_effect=AssertionError('copied ANF')):
                        result = candidate.solve(target)
                    self.assertTrue(result['verified'], result['basis_certificate'])
                    self.assertEqual(result['basis_certificate']['solutions'], expected)
                    self.assertTrue(verify_basis(3*ell, sorted(f.anf.items()), expected, result['basis_terms'], len(expected)))
                    points = [Point(**p) for p in result['curve_witness']['points']]
                    self.assertTrue(all(curve.on_curve(p) for p in points))
                    self.assertEqual(curve.sum(points), target)
                    self.assertEqual(result['metrics']['gpu_used'], int(backend == 'metal' and ell == 7))
                    self.assertEqual(result['metrics']['gpu_shape_fallback'], int(backend == 'metal' and ell == 8))

    def test_wide_descent_matches_untouched_equations_and_resets(self):
        for sanitizer in (False, True):
            for ell in (6, 7, 8):
                f = make_instance(31, 3, ell, seed=101)
                curve = Curve(GF2n(31, f.mod), f.b)
                with WideDescent(31, f.mod, f.b, 3, ell, sanitizer=sanitizer) as descent:
                    for seed in (101, 102):
                        original = make_instance(31, 3, ell, seed=seed)
                        target = curve.sum(original.points)
                        self.assertEqual(descent.descend_packed(target.x).to_dict(), original.anf)

    def test_fallback_and_invalid_targets(self):
        f = make_instance(83, 3, 2, seed=101)
        curve = Curve(GF2n(83, f.mod), f.b)
        with CertifiedQuery(83, f.mod, f.b, 3, 2) as query:
            result = query.solve(curve.sum(f.points))
            self.assertTrue(result['verified'])
            self.assertEqual(result['replay_backend'], 'python-public-point-wide-field-fallback')
            with self.assertRaises(ValueError):
                query.solve(Point(0, 0, True))
            query.close()
            with self.assertRaises(RuntimeError):
                query.solve(f.points[0])

    def test_chunked_reference_against_small_truth_functions(self):
        for bits in range(256):
            items = [(m, 1) for m in range(8) if bits>>m&1]
            expected = [a for a in range(8) if sum(a&m == m for m, _ in items)%2 == 0]
            for chunk_bits in (1, 2, 3):
                self.assertEqual(reference.chunked_roots(3, 1, items, chunk_bits=chunk_bits), expected)


if __name__ == '__main__':
    unittest.main()
