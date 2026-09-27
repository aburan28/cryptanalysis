"""Independent public-point replay, native ABI and complete-query checks."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import random
import unittest

from public_replay import (Curve, GF2n, INF, NativeReplay, NativeResult, Point,
                           PythonReplay, U64, is_irreducible, replay)
from public_query import PublicQuery
from descend import make_instance, verify_solution


def witness_check(test, curve, xs, target, answer):
    if answer['verified']:
        points = [Point(**p) for p in answer['points']]
        test.assertEqual([p.x for p in points], list(xs))
        test.assertTrue(all(curve.on_curve(p) for p in points))
        test.assertEqual(curve.sum(points), target)
        test.assertEqual(answer['patterns'], answer['signs'] + 1)
    else:
        test.assertIsNone(answer['signs'])
        test.assertEqual(answer['points'], [])


class ReplayTests(unittest.TestCase):
    def test_exhaustive_small_curve_and_identity(self):
        field = GF2n(3)
        compared = 0
        for b in (1, 2):
            curve = Curve(field, b)
            targets = [INF] + [Point(x, y) for x in range(8) for y in range(8)
                               if curve.on_curve(Point(x, y))]
            with PythonReplay(3, field.mod, b) as oracle, \
                    NativeReplay(3, field.mod, b) as fast, \
                    NativeReplay(3, field.mod, b, sanitizer=True) as sanitized:
                for x in range(8):
                    for y in range(8):
                        for target in targets:
                            reference = oracle.match((x, y), target)
                            witness_check(self, curve, (x, y), target, reference)
                            for native in (fast, sanitized):
                                actual = native.match((x, y), target)
                                self.assertEqual(reference, actual)
                                compared += 1
        print('Exhaustive native/Python full-point comparisons:', compared)

    def test_random_fields_witnesses_and_unsatisfied_targets(self):
        rng = random.Random(2026092701)
        compared = 0
        for n in (5, 11, 31, 61, 63):
            field = GF2n(n)
            for b in (1, 2):
                curve = Curve(field, b)
                with PythonReplay(n, field.mod, b) as oracle, \
                        NativeReplay(n, field.mod, b) as fast, \
                        NativeReplay(n, field.mod, b, sanitizer=True) as sanitized:
                    for m in (1, 2, 3, 5):
                        for case in range(6):
                            points = [curve.random_point(rng) for _ in range(m)]
                            xs = [p.x for p in points]
                            target = curve.sum(points) if case % 2 else curve.random_point(rng)
                            reference = oracle.match(xs, target)
                            witness_check(self, curve, xs, target, reference)
                            for native in (fast, sanitized):
                                actual = native.match(xs, target)
                                self.assertEqual(actual, reference, (n, b, m, case))
                                witness_check(self, curve, xs, target, actual)
                                compared += 1
                    # x=0 doubles to infinity; maximal accepted sign dimension.
                    xs = [0] * 12
                    self.assertEqual(oracle.match(xs, INF), fast.match(xs, INF))
                    self.assertTrue(fast.match(xs, INF)['verified'])
        print('Random native/Python full-point comparisons:', compared)

    def test_invalid_fields_points_and_raw_abi(self):
        field = GF2n(3)
        for sanitizer in (False, True):
            with NativeReplay(3, field.mod, 1, sanitizer=sanitizer) as native:
                lib = native.lib
                for mod in range(8, 16):
                    handle = lib.replay_create(3, mod, 1)
                    self.assertEqual(bool(handle), is_irreducible(mod))
                    lib.replay_destroy(handle)
                for args in ((0, 1, 1), (2, 7, 1), (4, 19, 1), (64, 0, 1),
                             (3, field.mod, 0), (3, field.mod, 8), (3, 9, 1)):
                    self.assertFalse(lib.replay_create(*args), args)
                xs, out = (U64 * 13)(*([0] * 13)), NativeResult()
                cases = [(None, xs, 2, 0, 0, 1), (native._handle, None, 2, 0, 0, 1),
                         (native._handle, xs, 0, 0, 0, 1), (native._handle, xs, 13, 0, 0, 1),
                         (native._handle, xs, 2, 0, 0, 2), (native._handle, xs, 2, 1, 0, 1),
                         (native._handle, xs, 2, 0, 0, 0), (native._handle, xs, 2, 8, 0, 0)]
                for args in cases:
                    ct.memset(ct.byref(out), 0x7F, ct.sizeof(out))
                    self.assertEqual(lib.replay_match(*args, ct.byref(out)), 3)
                    self.assertEqual((out.code, out.signs, out.patterns), (3, (1 << 32)-1, 0))
                    self.assertTrue(all(y == 0 for y in out.ys))
                xs[0] = 8
                self.assertEqual(lib.replay_match(native._handle, xs, 2, 0, 0, 1, ct.byref(out)), 3)
                self.assertEqual(lib.replay_match(native._handle, xs, 2, 0, 0, 1, None), 3)
                self.assertTrue(native.match([0, 0], INF)['verified'])
        for cls in (PythonReplay, NativeReplay):
            for args in ((4, 19, 1), (3, 9, 1), (3, field.mod, 0), (3, field.mod, 8),
                         (True, field.mod, 1), (3, -1, 1)):
                with self.assertRaises(ValueError): cls(*args)
            with cls(3, field.mod, 1) as checker:
                for xs, target in (([], INF), ([0]*13, INF), ([-1], INF), ([8], INF),
                                   ([0], Point(0, 0)), ([0], Point(1, 0, True)),
                                   ([0], Point(0, 0, 1)), ([0], Point(True, 0))):
                    with self.assertRaises(ValueError): checker.match(xs, target)

    def test_concurrent_freshness_and_lifetime(self):
        field = GF2n(11)
        curve = Curve(field, 1)
        rng = random.Random(71)
        with PythonReplay(11, field.mod, 1) as oracle:
            cases = []
            for _ in range(24):
                points = [curve.random_point(rng) for _ in range(3)]
                xs = [p.x for p in points]
                target = curve.sum(points)
                cases.extend([(xs, target), (xs, INF)])
            expected = [oracle.match(*args) for args in cases]
        for cls in (PythonReplay, NativeReplay):
            checker = cls(11, field.mod, 1)
            with ThreadPoolExecutor(max_workers=8) as pool:
                actual = list(pool.map(lambda args: checker.match(*args), cases))
            self.assertEqual(actual, expected)
            checker.close()
            checker.close()
            with self.assertRaises(RuntimeError): checker.match([0, 0], INF)
            with self.assertRaises(RuntimeError): checker.validate_target(INF)

    def test_complete_public_queries_and_wide_fallback(self):
        for n, ell in ((11, 2), (31, 3), (83, 2)):
            original = make_instance(n, 3, ell, seed=101)
            curve = Curve(GF2n(n, original.mod), original.b)
            target = curve.sum(original.points)
            shape = (n, original.mod, original.b, 3, ell)
            with PublicQuery(*shape, arm='python') as python, \
                    PublicQuery(*shape, arm='native-or-python') as native:
                # Neither query receives fixture points or a planted assignment.
                for point in (target, curve.neg(target)):
                    left, right = python.solve(point), native.solve(point)
                    self.assertEqual(left['basis_sha256'], right['basis_sha256'])
                    self.assertEqual(left['basis_certificate'], right['basis_certificate'])
                    self.assertEqual(left['curve_witness'], right['curve_witness'])
                    self.assertEqual(left['assignment'], right['assignment'])
                    self.assertTrue(left['verified'] and right['verified'])
                    self.assertEqual(original.evaluate(right['assignment']), 0)
                    self.assertTrue(verify_solution(original, right['assignment']))
                    witness_check(self, curve, original.x_from_assignment(right['assignment']),
                                  point, right['curve_witness'])
                    for result in (left, right):
                        self.assertEqual(result['complete_query_ns'], sum(result['phases_ns'].values()))
                    if n > 63:
                        self.assertEqual(right['replay_backend'], 'python-public-point-wide-field-fallback')
                changed = make_instance(n, 3, ell, seed=102)
                other_target = curve.sum(changed.points)
                if n == 31:
                    self.assertNotEqual(other_target.x, target.x)
                alternate = native.solve(other_target)
                self.assertTrue(alternate['verified'])
                self.assertEqual(changed.evaluate(alternate['assignment']), 0)
                witness_check(self, curve, changed.x_from_assignment(alternate['assignment']),
                              other_target, alternate['curve_witness'])
                with self.assertRaises(ValueError): native.solve(INF)
                with self.assertRaises(ValueError): native.solve(Point(0, 0))
                self.assertTrue(native.solve(target)['verified'])
            with self.assertRaises(RuntimeError): native.solve(target)
        with self.assertRaises(ValueError): NativeReplay(83, GF2n(83).mod, 1)
        with replay(83, GF2n(83).mod, 1, 'native-or-python') as fallback:
            self.assertIn('fallback', fallback.backend)


if __name__ == '__main__':
    unittest.main()
