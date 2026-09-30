"""Differential exact proof, invalid certificates, fallback and complete queries."""
import ctypes as ct
import importlib.util
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from sparse_checker import (HERE, SparseChecker, SparseQuery, PackedChecker, Result,
                            ProofStats, U32, U64, ARMS, query, _pack, PackedANF,
                            Curve, GF2n, Point)

spec = importlib.util.spec_from_file_location('frozen_truth_tests', HERE.parent / 'round18/test_truth.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
packed = legacy.packed


def semantic(answer):
    return {k: v for k, v in answer.items()
            if k not in ('backend', 'evaluation_counts', 'scratch_bytes', 'proof_stats')}


class LegacyContractTests(legacy.TruthTests):
    """Run the frozen contract against the new checker and all three query arms."""
    def setUp(self):
        self.patched = patch.multiple(legacy, PackedChecker=SparseChecker, Result=Result,
                                      semantic=semantic, TruthQuery=SparseQuery, ARMS=ARMS)
        self.patched.start()
        self.addCleanup(self.patched.stop)

    def test_complete_queries_independent_replay_and_no_dictionary(self):
        solved = 0
        for n, ell in ((11, 2), (31, 6), (83, 2)):
            original = legacy.make_instance(n, 3, ell, seed=101)
            changed = legacy.make_instance(n, 3, ell, seed=102)
            curve = Curve(GF2n(n, original.mod), original.b)
            target, other = curve.sum(original.points), curve.sum(changed.points)
            expected = {}
            for arm in ARMS:
                for sanitizer in (False, True):
                    with SparseQuery(n, original.mod, original.b, 3, ell, arm,
                                     sanitizer=sanitizer) as current:
                        for index, (point, fixture) in enumerate(((target, original),
                                (curve.neg(target), original), (other, changed), (target, original))):
                            with patch.object(PackedANF, 'to_dict', side_effect=AssertionError('unpacking forbidden')):
                                answer = current.solve(point)
                            self.assertTrue(answer['verified'])
                            self.assertEqual(answer['query_arm'], arm)
                            self.assertEqual(fixture.evaluate(answer['assignment']), 0)
                            points = [Point(**p) for p in answer['curve_witness']['points']]
                            self.assertTrue(all(curve.on_curve(p) for p in points))
                            self.assertEqual(curve.sum(points), point)
                            self.assertEqual(answer['complete_query_ns'], sum(answer['phases_ns'].values()))
                            value = (answer['basis_sha256'], semantic(answer['basis_certificate']),
                                     answer['assignment'], answer['curve_witness'])
                            if index in expected:
                                self.assertEqual(value, expected[index])
                            expected[index] = value
                            solved += 1
                        with self.assertRaises(ValueError):
                            current.solve(Point(0, 0))
                        self.assertTrue(current.solve(target)['verified'])
                    with self.assertRaises(RuntimeError):
                        current.solve(target)
        print('Complete-query comparisons:', solved, 'across three arms, both builds, three fields and fresh targets')


class SparseProofTests(unittest.TestCase):
    def test_every_three_variable_polynomial_and_corrupted_bases(self):
        comparisons = 0
        with query(3, 1, 'ordered') as producer, PackedChecker(3, 1) as frozen:
            checks = [SparseChecker(3, 1, mode=mode, sanitizer=sanitizer)
                      for mode in (0, 1, 2) for sanitizer in (False, True)]
            try:
                for coefficient_mask in range(256):
                    pairs = [(m, 1) for m in range(8) if coefficient_mask >> m & 1]
                    anf = packed(3, 1, pairs)
                    basis = producer.compute(dict(pairs))['basis_terms']
                    roots = [a for a in range(8) if sum((m & a) == m for m, _ in pairs) % 2 == 0]
                    expected = frozen.certify(anf, basis)
                    self.assertTrue(expected['verified'])
                    self.assertEqual(expected['solutions'], roots)
                    variants = [basis, [], [[0]], list(reversed(basis))]
                    if basis:
                        variants += [basis + [basis[0]], basis[1:],
                                     [sorted(set(basis[0]) ^ {0})] + basis[1:]]
                    for variant in variants:
                        expected = semantic(frozen.certify(anf, variant))
                        for check in checks:
                            result = check.certify(anf, variant)
                            self.assertEqual(semantic(result), expected,
                                             (coefficient_mask, variant, check.mode))
                            comparisons += 1
            finally:
                for check in checks:
                    check.close()
        print('Exhaustive 3-variable valid/invalid certificate comparisons:', comparisons)

    def test_exact_256_boundary_all_fallbacks_and_reuse(self):
        for sanitizer in (False, True):
            for n in (9, 18, 20):
                with SparseChecker(n, 128, sanitizer=sanitizer) as sparse, PackedChecker(n, 128) as frozen:
                    # Exactly 256 independent roots: sparse enumeration fills
                    # the workspace and must still prove completion exactly.
                    pairs = [(1 << i, 1 << (64+i)) for i in range(8, n)]
                    anf = packed(n, 128, pairs)
                    basis = [[1 << i] for i in range(8, n)]
                    result = sparse.certify(anf, basis)
                    self.assertEqual(semantic(result), semantic(frozen.certify(anf, basis)))
                    self.assertEqual(result['solutions'], list(range(256)))
                    self.assertEqual(result['proof_stats']['standard_visited'], 256)
                    self.assertEqual(result['proof_stats']['staircase_used'], 1)
                    self.assertEqual(result['proof_stats']['dense_table_bytes'], 0)
                    # Bad empty basis has >256 standard monomials. Retain the
                    # exact dense dimension, not just the 256-element prefix.
                    result = sparse.certify(anf, [])
                    self.assertEqual(semantic(result), semantic(frozen.certify(anf, [])))
                    self.assertEqual(result['standard_monomials'], 1 << n)
                    self.assertEqual(result['proof_stats']['fallback_reason'], 2)
                    # A large zero set bypasses sparse root storage entirely.
                    zero = packed(n, 128, [])
                    result = sparse.certify(zero, [])
                    self.assertEqual(semantic(result), semantic(frozen.certify(zero, [])))
                    self.assertEqual(result['proof_stats']['fallback_reason'], 1)
                    self.assertEqual(result['proof_stats']['root_list_used'], 0)
                    # Reuse after both fallbacks cannot retain old roots/counts.
                    one = packed(n, 128, [(0, 1 << 127)])
                    result = sparse.certify(one, [[0]])
                    self.assertTrue(result['verified'])
                    self.assertEqual(result['solutions'], [])
                    self.assertEqual(result['proof_stats']['fallback_reason'], 0)
                    self.assertEqual(semantic(sparse.certify(anf, basis)), semantic(frozen.certify(anf, basis)))
        with SparseChecker(9, 9, budget_test=True) as sparse, PackedChecker(9, 9) as frozen:
            anf = packed(9, 9, [(1 << i, 1 << i) for i in range(9)])
            basis = [[1 << i] for i in range(9)]
            for variant in (basis, basis[1:], basis + [[1]], [[1, 2]] + basis[1:]):
                result = sparse.certify(anf, variant)
                self.assertEqual(semantic(result), semantic(frozen.certify(anf, variant)))
                self.assertEqual(result['proof_stats']['fallback_reason'], 3)
                self.assertEqual(result['proof_stats']['budget_limit'], 8)
                self.assertLessEqual(result['proof_stats']['divisibility_tests'], 8)

    def test_mask_order_and_random_nonzero_large_rings(self):
        rng = random.Random(2026092801)
        for n in (6, 12, 18, 20):
            # Triangular affine ideals have known nonzero solutions, sparse
            # quotients and grevlex tails that exercise more than pure powers.
            root = rng.randrange(1 << n)
            basis = []
            pairs = []
            for i in range(n):
                terms = [1 << i]
                if root >> i & 1:
                    terms.append(0)
                basis.append(sorted(terms))
                pairs.extend((term, 1 << i) for term in terms)
            rng.shuffle(basis)
            pairs += pairs[:3] * 2
            rng.shuffle(pairs)
            anf = packed(n, n, pairs)
            with SparseChecker(n, n) as sparse, PackedChecker(n, n) as frozen:
                result = sparse.certify(anf, basis)
                self.assertEqual(semantic(result), semantic(frozen.certify(anf, basis)))
                self.assertEqual(result['solutions'], [root])
                self.assertEqual(result['proof_stats']['staircase_used'], 1)
                self.assertEqual(result['proof_stats']['dense_table_bytes'], 0)

    def test_creation_modes_and_deterministic_abi(self):
        for mode in (-1, 3, True, 2.0):
            with self.assertRaises(ValueError):
                SparseChecker(3, 1, mode=mode)
        with SparseChecker(3, 1) as check:
            self.assertFalse(check.lib.truth_create_mode(3, 1, 3))
            anf = packed(3, 1, [(1, 1)])
            terms, offsets = _pack([[1]], 3)
            result = Result()
            ct.memset(ct.byref(result), 0x77, ct.sizeof(result))
            self.assertEqual(check.lib.truth_certify(None, anf.masks, anf.coefficients,
                len(anf.masks), terms, len(terms), offsets, 1, ct.byref(result)), 6)
            self.assertEqual(result.certificate.code, 6)
            self.assertEqual(bytes(result.proof), bytes(ct.sizeof(ProofStats)))


if __name__ == '__main__':
    unittest.main()
