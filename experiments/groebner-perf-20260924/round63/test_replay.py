"""Exact differential controls and adversarial certificate mutations."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import ctypes as C
import random
import unittest
from curve_replay import PublicQuery, PublicReplay, NativeReplay, Point, INF, point_record, _Result
from gf2n import modulus


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.reference = PublicReplay(5, modulus(5), 1)
        self.native = [NativeReplay(self.reference, u) for u in (False, True)]

    def tearDown(self):
        for native in self.native:
            native.close()

    def fixture(self, xs=(0, 1, 2), signs=0):
        E = self.reference.E
        points = [E.lift_x(x) for x in xs]
        self.assertNotIn(None, points)
        target = E.sum([E.neg(p) if signs >> i & 1 else p for i, p in enumerate(points)])
        self.assertFalse(target.inf)
        assignment = sum(x << (i * 5) for i, x in enumerate(xs))
        return PublicQuery(5, modulus(5), 1, len(xs), 5, target, {}), assignment

    def compare(self, query, assignment, budget=256, reference=None, natives=None):
        reference = reference or self.reference
        expected = reference.find(query, assignment, budget)
        for native in natives or self.native:
            self.assertEqual(native.find(query, assignment, budget), expected)
        if expected['status'] == 'match':
            self.assertTrue(reference.verify(query, assignment, expected['witness']))
        return expected

    def test_random_fields_and_full_width(self):
        rng = random.Random(202610036301)
        for n in (3, 5, 9, 31, 63):
            ref = PublicReplay(n, modulus(n), 1 if n < 31 else 7)
            native = [NativeReplay(ref, u) for u in (False, True)]
            try:
                for _ in range(20):
                    ell = min(n, 21)
                    points = [ref.E.random_factor_base_point(ell, rng) for _ in range(3)]
                    target = ref.E.sum(points)
                    if target.inf:
                        continue
                    assignment = sum(p.x << (i * ell) for i, p in enumerate(points))
                    query = PublicQuery(n, ref.F.mod, ref.E.b, 3, ell, target, {})
                    for budget in (0, 1, 7, 8, 256):
                        self.compare(query, assignment, budget, ref, native)
                # 64 Boolean variables, with an input reaching bit 63.
                if n == 63:
                    points = [ref.E.random_factor_base_point(8, rng) for _ in range(8)]
                    while points[-1].x < 128 or ref.E.sum(points).inf:
                        points[-1] = ref.E.random_factor_base_point(8, rng)
                    query = PublicQuery(n, ref.F.mod, ref.E.b, 8, 8, ref.E.sum(points), {})
                    assignment = sum(p.x << (i * 8) for i, p in enumerate(points))
                    self.compare(query, assignment, 256, ref, native)
            finally:
                for item in native:
                    item.close()

    def test_exceptional_group_law_paths(self):
        # A finite factor can follow an intermediate infinity. x=0 has order 2.
        for xs, signs in (((0, 0, 1), 0), ((1, 1, 0), 1), ((1, 1, 1), 0)):
            query, assignment = self.fixture(xs, signs)
            self.compare(query, assignment)

    def test_no_lift_no_match_and_budget(self):
        query, assignment = self.fixture((0, 0, 1), 4)
        self.assertEqual(self.compare(query, assignment, 0)['status'], 'budget')
        self.assertEqual(self.compare(query, assignment, 1)['status'], 'budget')
        self.assertEqual(self.compare(query, assignment, 8)['status'], 'match')
        x = next(x for x in range(32) if self.reference.E.lift_x(x) is None)
        missing = replace(query, m=1)
        self.assertEqual(self.compare(missing, x)['status'], 'no-match')
        mismatched = replace(query, target=self.reference.E.lift_x(0), m=1)
        self.assertEqual(self.compare(mismatched, 1)['status'], 'no-match')

    def test_mutations_and_independence(self):
        query, assignment = self.fixture((1, 1, 1), 0)
        witness = self.compare(query, assignment)['witness']
        mutations = []
        for key in ('ring', 'target', 'assignment', 'points', 'steps', 'slopes'):
            w = deepcopy(witness)
            if key == 'ring': w[key][2] ^= 2
            elif key == 'target': w[key][1] ^= 1
            elif key == 'assignment': w[key] ^= 1
            elif key in ('points', 'steps'): w[key][0][1] ^= 1
            else: w[key][1] ^= 1
            mutations.append(w)
        for value in (None, {}, [], {'extra': 1}): mutations.append(value)
        for bad in mutations:
            self.assertFalse(self.reference.verify(query, assignment, bad))
        self.assertFalse(self.reference.verify(replace(query, anf={0: 1}), assignment, witness))
        self.assertFalse(self.reference.verify(replace(query, target=self.reference.E.neg(query.target)), assignment, witness))
        for bad in (-1, 1 << query.nvars, True):
            self.assertFalse(self.reference.verify(query, bad, witness))
        bad = deepcopy(witness); bad['steps'][0] = [1, 0, 1]
        self.assertFalse(self.reference.verify(query, assignment, bad))
        # The independent checker must not call inversion, lifting, or addition.
        def forbidden(*args): raise RuntimeError('producer operation in verifier')
        self.reference.F.inv = forbidden
        self.reference.E.lift_x = forbidden
        self.reference.E.add = forbidden
        self.assertTrue(self.reference.verify(query, assignment, witness))
        self.assertFalse(hasattr(query, 'planted'))
        self.assertFalse(hasattr(query, 'points'))

    def test_reject_invalid_inputs_and_native_field(self):
        query, assignment = self.fixture((0, 0, 1))
        for ring in ((5, -37, 1), (5, 33, 1), (5, 37, True), (4, 19, 1)):
            with self.assertRaises(ValueError): PublicReplay(*ring)
        for native in self.native:
            for ring in ((0, 0, 1), (64, (1 << 63) + 1, 1), (5, 33, 1), (5, 37, 0)):
                self.assertFalse(native.lib.replay_create(*ring))
            for changed in (replace(query, m=0), replace(query, l=0), replace(query, target=INF),
                            replace(query, m=8, l=9), replace(query, b=2), replace(query, b=True),
                            replace(query, target=Point(query.target.x, query.target.y, '0'))):
                with self.assertRaises(ValueError): native.find(changed, assignment)
            for budget in (-1, 257, True):
                with self.assertRaises(ValueError): native.find(query, assignment, budget)
            raw = _Result()
            native.lib.replay_find(native._context, 3, 5, 1 << 15, query.target.x, query.target.y, 8, C.byref(raw))
            self.assertEqual(raw.status, 3)
            native.lib.replay_find(None, 3, 5, assignment, query.target.x, query.target.y, 8, C.byref(raw))
            self.assertEqual(raw.status, 3)

    def test_thread_ownership_and_close(self):
        query, assignment = self.fixture((0, 0, 1))
        expected = self.reference.find(query, assignment)
        for native in self.native:
            with ThreadPoolExecutor(max_workers=4) as pool:
                values = list(pool.map(lambda _: native.find(query, assignment), range(20)))
            self.assertTrue(all(value == expected for value in values))
            native.close(); native.close()
            with self.assertRaises(RuntimeError): native.find(query, assignment)


if __name__ == '__main__':
    unittest.main()
