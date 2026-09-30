"""Whole-query equivalence and fresh native transport at every frozen shape."""
from contextlib import ExitStack
import importlib.util
import os
import unittest
from unittest.mock import patch

from narrow import HERE
from narrow_query import NarrowQuery
from query import CertifiedQuery
from native_descent import PackedANF
from wide_descent import PackedANF as WidePacked
from descend import make_instance
from sparse_checker import Curve, GF2n, Point
from quadratic_reference import verify_basis

_spec = importlib.util.spec_from_file_location('narrow_truth_reference', HERE.parent/'round32/reference.py')
_reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_reference)


class NarrowQueryTests(unittest.TestCase):
    def test_frozen_small_and_wide_queries(self):
        backends = ('cpu', 'metal') if os.environ.get('QUADRATIC_TEST_METAL') == '1' else ('cpu',)
        shapes = [(31, 6, range(101, 107)), (31, 5, (101,)), (11, 3, (101,)),
                  (83, 2, (101,)), (31, 7, (201,)), (31, 8, (201,))]
        for n, ell, seeds in shapes:
            original = make_instance(n, 3, ell, seed=seeds[0])
            curve = Curve(GF2n(n, original.mod), original.b)
            with ExitStack() as stack:
                queries = [(stack.enter_context(CertifiedQuery(n, original.mod, original.b, 3, ell, backend=backend)),
                            stack.enter_context(NarrowQuery(n, original.mod, original.b, 3, ell, backend=backend)))
                           for backend in backends]
                for seed in seeds:
                    original = make_instance(n, 3, ell, seed=seed)
                    items = sorted(original.anf.items())
                    expected = _reference.chunked_roots(3*ell, n, items)
                    target = curve.sum(original.points)
                    for backend, (old, new) in zip(backends, queries):
                        with self.subTest(n=n, ell=ell, seed=seed, backend=backend), \
                             patch.object(PackedANF, 'items', side_effect=AssertionError('expanded ANF')), \
                             patch.object(PackedANF, 'to_dict', side_effect=AssertionError('copied ANF')), \
                             patch.object(WidePacked, 'items', side_effect=AssertionError('expanded wide ANF')), \
                             patch.object(WidePacked, 'to_dict', side_effect=AssertionError('copied wide ANF')):
                            a, b = old.solve(target), new.solve(target)
                        self.assertTrue(a['verified'], a)
                        self.assertTrue(b['verified'], b)
                        for key in ('basis_terms', 'basis_sha256', 'assignment', 'curve_witness', 'proof_bytes', 'proof_sha256'):
                            self.assertEqual(a[key], b[key], key)
                        self.assertEqual(b['basis_certificate']['solutions'], expected)
                        self.assertTrue(verify_basis(3*ell, items, expected, b['basis_terms'], len(expected)))
                        points = [Point(**p) for p in b['curve_witness']['points']]
                        self.assertTrue(all(curve.on_curve(p) for p in points))
                        self.assertEqual(curve.sum(points), target)
                        self.assertEqual(original.evaluate(b['assignment']), 0)
                        self.assertEqual(b['complete_query_ns'], sum(b['phases_ns'].values()))
                        self.assertEqual(b['producer_coefficient_word_bits'], 32 if n<=32 else 64 if n<=64 else 128)
                        packed = new.descent.descend_packed(target.x)
                        self.assertTrue(new.checker.certify(packed, expected, a['basis_terms'], a['proof_bytes'])['verified'])
                        self.assertTrue(old.checker.certify(packed, expected, b['basis_terms'], b['proof_bytes'])['verified'])


if __name__ == '__main__':
    unittest.main()
