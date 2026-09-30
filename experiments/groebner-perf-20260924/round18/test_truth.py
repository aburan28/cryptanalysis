"""Independent roots/basis checks, direct packed equations and complete replay."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import random
import sys
import unittest
from unittest.mock import patch

from packed_checker import (PackedChecker, PackedANF, Result, Certificate, U32, U64,
                            Curve, GF2n, Point, query, _pack)
from truth_query import ARMS, TruthQuery
from descend import make_instance


def packed(n, e, pairs):
    limbs = (e+63)//64
    masks = (U32*len(pairs))(*(m for m, _ in pairs))
    values = (U64*(len(pairs)*limbs))(*(c>>(64*j)&((1<<64)-1)
                                        for _, c in pairs for j in range(limbs)))
    return PackedANF(n, e, masks, values, len(pairs))


def semantic(certificate):
    return {k: v for k, v in certificate.items()
            if k not in ('backend', 'evaluation_counts', 'scratch_bytes')}


class TruthTests(unittest.TestCase):
    def test_random_parity_roots_and_equations(self):
        rng = random.Random(2026092704)
        comparisons = evaluations = 0
        for e in (1, 2, 31, 63, 64, 65, 127, 128):
            # Keep the producer-generated cases within its declared 256-root
            # cap; the checker-only boundary tests below cover larger zero sets.
            for n in (1, 3, 6, 7, 8):
                pairs = [(rng.randrange(1<<n), rng.getrandbits(e)) for _ in range(25)]
                pairs += pairs[:4] + pairs[:3]
                planted, value = rng.randrange(1<<n), 0
                for mask, coefficient in pairs:
                    if mask & ~planted == 0: value ^= coefficient
                pairs.append((0, value))
                merged = {}
                for mask, coefficient in pairs:
                    merged[mask] = merged.get(mask, 0) ^ coefficient
                with query(n, e, 'ordered') as reference:
                    answer = reference.compute(merged)
                self.assertTrue(answer.get('groebner_verified'), answer)
                basis = answer['basis_terms']
                roots = [p for p in range(1<<n) if not self.scalar(pairs, p)]
                self.assertEqual(answer['basis_certificate']['solutions'], roots)
                for sanitizer in (False, True):
                    with PackedChecker(n, e, sanitizer=sanitizer) as checker:
                        for variant in (pairs, sorted(pairs), list(reversed(pairs))):
                            anf = packed(n, e, variant)
                            self.assertEqual(semantic(checker.certify(anf, basis)),
                                             semantic(answer['basis_certificate']))
                            comparisons += 1
                        for point in range(1<<n):
                            self.assertEqual(checker.evaluate(anf, point), self.scalar(pairs, point))
                            evaluations += 1
                        damaged = [row[:] for row in basis]
                        if damaged:
                            damaged[0] += damaged[0][:1]
                            self.assertFalse(checker.certify(anf, damaged)['verified'])
        print('Random packed certificates:', comparisons, 'direct evaluations:', evaluations)

    @staticmethod
    def scalar(pairs, point):
        value = 0
        for mask, coefficient in pairs:
            if mask & ~point == 0: value ^= coefficient
        return value

    def test_zero_many_roots_boundary_and_freshness(self):
        with query(9, 1, 'ordered') as producer:
            capped = producer.compute({})
            self.assertEqual(capped['status'], 'inconclusive')
            self.assertFalse(capped['complete'])
        for n in (1, 6, 20):
            for sanitizer in (False, True):
                with PackedChecker(n, 128, sanitizer=sanitizer) as checker:
                    zero = packed(n, 128, [])
                    empty = checker.certify(zero, [])
                    self.assertTrue(empty['verified'])
                    self.assertEqual(empty['root_count'], 1<<n)
                    self.assertEqual(empty['solutions'], list(range(1<<n)) if n <= 8 else None)
                    one = checker.certify(packed(n, 128, [(0, 1<<127)]), [[0]])
                    self.assertTrue(one['verified'])
                    self.assertEqual(one['solutions'], [])
                    pairs = [(1<<i, 1<<(64+i)) for i in range(n)]
                    fixed = checker.certify(packed(n, 128, pairs), [[1<<i] for i in range(n)])
                    self.assertTrue(fixed['verified'])
                    self.assertEqual(fixed['solutions'], [0])
                    self.assertEqual(semantic(checker.certify(zero, [])), semantic(empty))
                    self.assertTrue(checker.certify(packed(n, 128, [(0, 1), (0, 1)]), [])['verified'])

    def test_all_basis_rejections_and_invalid_abi(self):
        for sanitizer in (False, True):
            with PackedChecker(2, 2, sanitizer=sanitizer) as checker:
                anf = packed(2, 2, [(1, 1)])
                for bad, code in (([[]], 1), ([[1, 1]], 1), ([[1, 0]], 2),
                                  ([], 3), ([[1], [1]], 4)):
                    self.assertFalse(checker.certify(anf, bad)['verified'])
                    terms, starts = _pack(bad, 2)
                    out = Result()
                    self.assertEqual(checker.lib.truth_certify(checker._handle, anf.masks,
                        anf.coefficients, len(anf.masks), terms, len(terms), starts, len(bad), ct.byref(out)), code)
                self.assertEqual(checker.certify(packed(2, 2, [(1, 1), (2, 2)]),
                    [[1, 2], [2]])['reason'], 'nonstandard tail monomial')
                terms, starts = _pack([[1]], 2)
                args = [checker._handle, anf.masks, anf.coefficients, 1,
                        terms, len(terms), starts, 1]
                for changes in ({0: None}, {1: None}, {2: None}, {1: (U32*1)(4)},
                                {2: (U64*1)(4)}, {4: None}, {6: None},
                                {4: (U32*1)(4)}, {6: (U32*2)(1, 1)},
                                {6: (U32*2)(0, 0)}, {6: (U32*3)(0, 3, 2), 7: 2, 5: 2, 4: (U32*2)(1, 0)}):
                    bad = args[:]
                    for i, value in changes.items(): bad[i] = value
                    out = Result()
                    ct.memset(ct.byref(out), 0x7f, ct.sizeof(out))
                    self.assertEqual(checker.lib.truth_certify(*bad, ct.byref(out)), 6)
                    self.assertEqual(out.certificate.code, 6)
                    self.assertEqual(out.certificate.solution_count, 0)
                self.assertEqual(checker.lib.truth_certify(*args, None), 6)
                for bad in ((None, anf.masks, anf.coefficients, 1, 0),
                            (checker._handle, None, anf.coefficients, 1, 0),
                            (checker._handle, anf.masks, None, 1, 0),
                            (checker._handle, anf.masks, anf.coefficients, 1, 4)):
                    out = (U64*2)(99, 99)
                    self.assertEqual(checker.lib.truth_evaluate(*bad, out), 6)
                    self.assertEqual(list(out), [0, 0])
                for n, e in ((0, 1), (21, 1), (1, 0), (1, 129)):
                    self.assertFalse(checker.lib.truth_create(n, e))
            for e in (63, 65, 127):
                with PackedChecker(2, e, sanitizer=sanitizer) as checker:
                    bad = packed(2, e, [(1, 1<<e)])
                    with self.assertRaises(ValueError): checker.certify(bad, [[1]])
                    with self.assertRaises(ValueError): checker.evaluate(bad, 0)
        for n, e in ((True, 1), (21, 1), (1, False), (1, 129)):
            with self.assertRaises(ValueError): PackedChecker(n, e)

    def test_concurrent_mutation_extents_and_close(self):
        checker = PackedChecker(3, 65)
        anf = packed(3, 65, [(1, 1<<64)])
        other = packed(3, 65, [(0, 1<<64), (1, 1<<64)])
        def check(value): return checker.certify(value, [[1]])['verified']
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(check, [anf, other]*12)), [True, False]*12)
        anf.coefficients[1] = 0
        self.assertFalse(check(anf))
        anf.coefficients[1] = 1
        self.assertTrue(check(anf))
        for value in (-1, 8, True, 1.0):
            with self.assertRaises(ValueError): checker.evaluate(anf, value)
        with self.assertRaises(ValueError): checker.evaluate(packed(3, 64, [(1, 1)]), 0)
        with self.assertRaises(ValueError): checker.certify_views((U32*1)(1), (U64*1)(1), [[1]])
        checker.close()
        checker.close()
        with self.assertRaises(RuntimeError): checker.certify(anf, [[1]])
        with self.assertRaises(RuntimeError): checker.evaluate(anf, 0)

    def test_complete_queries_independent_replay_and_no_dictionary(self):
        for n, ell in ((11, 2), (31, 6), (83, 2)):
            original = make_instance(n, 3, ell, seed=101)
            curve = Curve(GF2n(n, original.mod), original.b)
            target = curve.sum(original.points)
            expected = None
            path = sys.path[:]
            for arm in ARMS:
                for sanitizer in (False, True):
                    with TruthQuery(n, original.mod, original.b, 3, ell, arm,
                                    sanitizer=sanitizer) as current:
                        self.assertEqual(sys.path, path)
                        if arm in ('packed-replay', 'combined'):
                            with patch.object(PackedANF, 'to_dict', side_effect=AssertionError('unpacking forbidden')):
                                answer = current.solve(target)
                        else:
                            answer = current.solve(target)
                        self.assertTrue(answer['verified'])
                        self.assertEqual(original.evaluate(answer['assignment']), 0)
                        points = [Point(**p) for p in answer['curve_witness']['points']]
                        self.assertTrue(all(curve.on_curve(p) for p in points))
                        self.assertEqual(curve.sum(points), target)
                        self.assertEqual(answer['complete_query_ns'], sum(answer['phases_ns'].values()))
                        got = (answer['basis_sha256'], semantic(answer['basis_certificate']),
                               answer['assignment'], answer['curve_witness'])
                        if expected is None: expected = got
                        self.assertEqual(got, expected)
                        # A different full target with the same x changes only sign replay.
                        negative = current.solve(curve.neg(target))
                        self.assertTrue(negative['verified'])
                        self.assertEqual(curve.sum([Point(**p) for p in negative['curve_witness']['points']]), curve.neg(target))
                        if n == 31 and arm == 'combined':
                            changed = make_instance(n, 3, ell, seed=102)
                            other_target = curve.sum(changed.points)
                            self.assertNotEqual(other_target.x, target.x)
                            fresh = current.solve(other_target)
                            self.assertTrue(fresh['verified'])
                            self.assertEqual(changed.evaluate(fresh['assignment']), 0)
                            self.assertEqual(curve.sum([Point(**p) for p in fresh['curve_witness']['points']]), other_target)
                        with self.assertRaises(ValueError): current.solve(Point(0, 0))
                        self.assertTrue(current.solve(target)['verified'])
                    with self.assertRaises(RuntimeError): current.solve(target)
        print('Complete-query comparisons cover all four arms, both checker builds and three field sizes')


if __name__ == '__main__': unittest.main()
