"""Exact differential checks for the packed boundary and reusable workspace."""
import ctypes
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from packed_query import PackedQuery, Certificate, DualStats
from boolean_basis import certify_boolean_basis
from boolean_certificate_native import certify_boolean_basis_native
from solve_dual import compute_dual_basis, make_instance, solve_dual
from descent_plan import DescentPlan
from descend import descend, GF2n, Curve, sumpoly


def pack_rows(rows):
    anf = {}
    for index, row in enumerate(rows):
        for mask in row:
            anf[mask] = anf.get(mask, 0) ^ (1 << index)
    return anf


class PackedTests(unittest.TestCase):
    def test_target_independent_descent_plan(self):
        rng = random.Random(2026092505)
        for n, m, ell, b in ((5,2,2,1), (7,3,2,3), (11,3,3,1), (11,4,2,1), (31,3,6,1)):
            field = GF2n(n)
            plan = DescentPlan(n, field.mod, b, m, ell)
            targets = [0, (1 << n)-1, rng.randrange(1 << n), 0]
            for target in targets:
                expected = descend(sumpoly.load(m+1), field, Curve(field,b), m, ell, target)
                self.assertEqual(plan.descend(target), expected)
            with ThreadPoolExecutor(max_workers=4) as pool:
                answers = list(pool.map(plan.descend, targets))
            self.assertEqual(answers, [plan.descend(target) for target in targets])
            for target in (-1, 1 << n, 0.5):
                with self.assertRaises(ValueError):
                    plan.descend(target)

    def check_case(self, n, rows, basis=None):
        if basis is None:
            old = compute_dual_basis(n, rows, verifier='native')
            self.assertEqual(old['status'], 'gb')
            basis = old['basis_terms']
        # Small systems use the Python truth-table oracle. Larger frozen cases
        # compare against the unchanged row-based native verifier: the existing
        # CI suite separately checks that verifier against Python. Here the new
        # boundary under test is the independent packed coefficient decoder.
        oracle_check = ((lambda candidate: certify_boolean_basis(n, rows, candidate)) if n <= 12 else
                        (lambda candidate: certify_boolean_basis_native(n, rows, candidate)))
        expected = oracle_check(basis)
        mutations = [(wrong, oracle_check(wrong)) for wrong in
                     ([], [[0]], [[]], basis[:-1], basis+basis, [[0, 0]])]
        for sanitizer in (False, True):
            with PackedQuery(n, max(1, len(rows)), sanitizer=sanitizer) as query:
                actual = query.compute(pack_rows(rows))
                self.assertEqual(actual['status'], 'gb')
                self.assertEqual(actual['basis_terms'], basis)
                for key in ('root_count', 'standard_monomials', 'solutions'):
                    self.assertEqual(actual['basis_certificate'][key], expected[key])
                for wrong, oracle in mutations:
                    certificate = query.certify(pack_rows(rows), wrong)
                    self.assertEqual(certificate['verified'], oracle['verified'])
                    if not oracle['verified']:
                        self.assertEqual(certificate['reason'], oracle['reason'])

    def test_random_small_ideals(self):
        rng = random.Random(2026092504)
        for n in range(1, 8):
            for _ in range(12):
                rows = [[rng.randrange(1 << n) for _ in range(rng.randrange(12))]
                        for _ in range(rng.randrange(1, n+2))]
                self.check_case(n, rows)

    def test_frozen_inputs(self):
        for case in json.loads((HERE.parent/'round3/inputs.json').read_text())['cases']:
            data = case['input']
            self.check_case(data['nvars'], data['equations'], data['basis'])

    def test_coefficient_word_boundaries(self):
        for count in (1, 31, 63, 64, 65, 83, 128, 129, 4096):
            rows = [[1 << (i % 3)] + ([0] if i % 3 == 1 else []) for i in range(count)]
            self.check_case(3, rows)

    def test_workspace_reuse_and_failure_recovery(self):
        for sanitizer in (False, True):
            with PackedQuery(10, 10, sanitizer=sanitizer) as query:
                self.assertEqual(query.compute({})['status'], 'inconclusive')
                # A failure must not leave table/roots that contaminate the next input.
                for point in (0, 1023, 91, 0, 729):
                    anf = {1 << i: 1 << i for i in range(10)}
                    anf[0] = point
                    answer = query.compute(anf)
                    self.assertEqual(answer['basis_certificate']['solutions'], [point])
                    self.assertTrue(answer['groebner_verified'])
                    self.assertEqual(query.compute(dict(reversed(list(anf.items()))))['basis_sha256'],
                                     answer['basis_sha256'])
                self.assertEqual(query.compute({0: 1})['basis_terms'], [[0]])
                self.assertEqual(query.compute({})['status'], 'inconclusive')
            with self.assertRaises(RuntimeError):
                query.compute({0: 1})
            query.close()

    def test_concurrent_workspace(self):
        with PackedQuery(10, 10) as shared:
            def compute(point):
                anf = {1 << i: 1 << i for i in range(10)}
                anf[0] = point
                return shared.compute(anf)['basis_certificate']['solutions'] == [point]
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertTrue(all(pool.map(compute, range(128))))

    def test_invalid_inputs(self):
        for shape in ((0,1), (21,1), (1,0), (1,4097)):
            with self.assertRaises(ValueError):
                PackedQuery(*shape)
        for sanitizer in (False, True):
            with PackedQuery(3, 3, sanitizer=sanitizer) as query:
                for anf in ({-1: 1}, {8: 0}, {1: -1}, {1: 8}, {1: 1 << 64}, {1: 1.5}, {1.5: 1}):
                    with self.assertRaises(ValueError):
                        query.compute(anf)
                    with self.assertRaises(ValueError):
                        query.certify(anf, [])
            with PackedQuery(3, 65, sanitizer=sanitizer) as query:
                for anf in ({1: -1}, {1: 1 << 65}, {1: 1.5}):
                    with self.assertRaises(ValueError):
                        query.compute(anf)

    def test_native_boundary_and_duplicate_cancellation(self):
        for sanitizer in (False, True):
            with PackedQuery(3, 3, sanitizer=sanitizer) as query:
                masks = (ctypes.c_uint32*2)(1,1)
                coefficients = (ctypes.c_uint64*2)(1,1)
                starts = (ctypes.c_uint32*1)(0)
                stats, certificate = DualStats(), Certificate()
                handle = query._solver.packed_dual_compute(query._handle, masks, coefficients, 2, ctypes.byref(stats))
                self.assertTrue(handle)
                query._solver.dual_destroy(handle)
                self.assertEqual((stats.roots, stats.rows), (8, 0))
                self.assertEqual(query._verifier.packed_boolean_certificate(3, 3, masks, coefficients, 2,
                    None, 0, starts, 0, ctypes.byref(certificate)), 0)
                for bad_masks, bad_coefficients in ((None, coefficients), (masks, None),
                        ((ctypes.c_uint32*2)(8,1), coefficients), (masks, (ctypes.c_uint64*2)(8,1))):
                    self.assertFalse(query._solver.packed_dual_compute(query._handle, bad_masks, bad_coefficients, 2, ctypes.byref(stats)))
                    self.assertEqual(query._verifier.packed_boolean_certificate(3, 3, bad_masks, bad_coefficients, 2,
                        None, 0, starts, 0, ctypes.byref(certificate)), 6)

    def test_curve_replay_without_python_equation_expansion(self):
        for n, ell in ((11,2), (31,6)):
            instance = make_instance(n, 3, ell, seed=101)
            expected = solve_dual(instance, verifier='native')
            with PackedQuery(instance.nvars, instance.n) as query:
                with patch.object(instance, 'equations', side_effect=AssertionError('Python equation expansion')):
                    actual = query.solve(instance)
                self.assertTrue(actual['verified'])
                self.assertEqual(actual['assignment'], expected['assignment'])
                self.assertEqual(actual['basis_sha256'], expected['basis_sha256'])


if __name__ == '__main__':
    unittest.main()
