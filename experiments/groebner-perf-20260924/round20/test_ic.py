"""Complete toy recovery, exhaustive relation presence and failure controls."""
from collections import Counter
import random
import unittest
from unittest.mock import patch

from ic_query import ARMS, PreparedIC, Ledger, PHASES, ONLINE, Point, PackedANF, point, scalar_replay
from identity import candidate, fixture, no_floats, source_snapshot
from relations import Oracle


class ICTests(unittest.TestCase):
    def test_exhaustive_subgroup_relation_presence(self):
        totals = {}
        for arm in ARMS:
            with PreparedIC(13, 3, arm) as q:
                oracle = Oracle(q.fb, 3)
                counts = Counter()
                for k in range(1, q.curve.r):
                    R = q.curve.K.smul(q.curve.G, k)
                    answer = q.backend.decompose(R, Ledger(PHASES))
                    self.assertEqual(bool(answer['relations']), oracle.ordered_count(R) > 0, (arm, k))
                    self.assertEqual(answer['roots_checked'], answer['basis']['basis_certificate']['root_count'])
                    counts[answer['status']] += 1
                    for relation in answer['relations']:
                        points = [Point(**p) for p in relation['witness']['points']]
                        self.assertTrue(all(q.oracle.on_curve(p) for p in points))
                        self.assertEqual(q.oracle.sum(points), point(R))
                        value = sum(c*q.logs[j] for j, c in relation['row']) % q.curve.r
                        self.assertEqual(value, k)
                totals[arm] = dict(counts)
        self.assertEqual(totals['baseline'], totals['packed'])
        print('Exhaustive subgroup PDP comparisons:', 2*2002, totals)

    def test_complete_fresh_targets_and_no_dictionary_boundary(self):
        results = {}
        for seed in (401, 402, 403):
            for arm in ARMS:
                with PreparedIC(13, 3, arm) as q:
                    wid, frozen, expected = fixture(q, seed)
                    Q = Point(**frozen['target'])
                    self.assertNotIn(Q, q.seen_points)
                    if arm == 'packed':
                        with patch.object(PackedANF, 'to_dict', side_effect=AssertionError('dictionary conversion')):
                            answer = q.recover(Q, frozen['rerandomization_seed'])
                    else:
                        answer = q.recover(Q, frozen['rerandomization_seed'])
                    rho = q.rho(Q)
                    self.assertTrue(answer['verified'], answer)
                    self.assertTrue(rho['verified'], rho)
                    self.assertEqual(answer['scalar'], expected)
                    self.assertEqual(rho['scalar'], expected)
                    self.assertEqual(sum(answer['phase_wall_ns'].values()), answer['online_wall_ns'])
                    self.assertEqual(set(answer['phase_wall_ns']), set(ONLINE))
                    self.assertEqual(sum(q.preparation['phase_wall_ns'].values()), q.preparation['wall_ns'])
                    self.assertEqual(sum(a['novel_rows'] for a in q.preparation['attempts']), q.fb.effective_columns)
                    with self.assertRaises(RuntimeError):
                        q.recover(Q, frozen['rerandomization_seed'])
                    results[seed, arm] = (wid, expected, [a['status'] for a in answer['attempts']],
                                          [a['target'] for a in answer['attempts']])
            self.assertEqual(results[seed, 'baseline'], results[seed, 'packed'])
        print('Full independently replayed DLP comparisons:', 6)

    def test_budget_invalid_known_point_and_closed_context(self):
        with PreparedIC(13, 3, 'packed', max_collection=1) as q:
            self.assertEqual(q.preparation['status'], 'insufficient_relations')
            _, frozen, _ = fixture(q, 501)
            answer = q.recover(Point(**frozen['target']), frozen['rerandomization_seed'])
            self.assertEqual(answer['status'], 'insufficient_relations')
            self.assertIsNone(answer['online_wall_ns'])
        for Q in (Point(0, 0), Point(0, 0, True), Point(1 << 13, 1), Point(0, 1)):
            with PreparedIC(13, 3, 'packed') as q:
                answer = q.recover(Q, 'invalid-control')
                self.assertEqual(answer['status'], 'error')
                self.assertFalse(answer['verified'])
                self.assertEqual(answer['attempts'], [])
        with PreparedIC(13, 3, 'packed') as q:
            self.assertEqual(q.recover(q.G, 'known-target')['status'], 'error')
        with self.assertRaises(RuntimeError):
            q.rho(q.G)
        q.close()
        with self.assertRaises(RuntimeError):
            q.recover(q.G, 'closed')

    def test_target_budget_and_corrupt_logs(self):
        with PreparedIC(13, 3, 'packed', max_target=1) as q:
            _, frozen, _ = fixture(q, 401)
            Q = Point(**frozen['target'])
            with patch.object(q.backend, 'decompose', return_value={
                    'status': 'budget', 'relations': [], 'target': [1, 1]}):
                answer = q.recover(Q, frozen['rerandomization_seed'])
            self.assertEqual(answer['status'], 'budget')
            self.assertFalse(answer['verified'])
            self.assertEqual(len(answer['attempts']), 1)
        with PreparedIC(13, 3, 'packed') as q:
            _, frozen, _ = fixture(q, 401)
            q.logs = {j: (value+1) % q.curve.r for j, value in q.logs.items()}
            answer = q.recover(Point(**frozen['target']), frozen['rerandomization_seed'])
            self.assertEqual(answer['status'], 'error')
            self.assertFalse(answer['verified'])

    def test_identity_relation_and_membership_continuation(self):
        with PreparedIC(13, 3, 'packed') as q:
            for seed in range(1000):
                rng = random.Random(seed)
                a = rng.randrange(1, q.curve.r)
                Q = point(q.curve.K.smul(q.curve.G, (-a) % q.curve.r))
                if Q not in q.seen_points:
                    break
            with patch.object(q.backend, 'decompose', side_effect=AssertionError('identity does not need PDP')):
                answer = q.recover(Q, seed)
            self.assertTrue(answer['verified'])
            self.assertEqual(answer['attempts'][0]['status'], 'identity_relation')
            self.assertEqual(answer['scalar'], (-a) % q.curve.r)
        with PreparedIC(13, 3, 'packed') as q:
            positive = next(a for a in q.preparation['attempts'] if a['relations'])
            q.backend.mapping = {}
            rejected = q.backend.decompose(tuple(positive['target']), Ledger(PHASES))
            self.assertFalse(rejected['relations'])
            self.assertGreater(rejected['membership_rejections'], 0)
            self.assertEqual(rejected['roots_checked'], rejected['basis']['basis_certificate']['root_count'])

    def test_exact_identity_and_limits(self):
        snapshot = source_snapshot()
        ids = []
        for arm in ARMS:
            with PreparedIC(13, 3, arm) as q:
                cid, manifest = candidate(q, snapshot)
                no_floats(manifest)
                self.assertIn('fb8PDP3evalRCsampleLAgaussTDpdpISO0h', cid)
                self.assertEqual(manifest['factor_base']['actual_usable_point_count'], 8)
                self.assertEqual(manifest['curve']['subgroup_order'], 2003)
                ids.append(cid)
        self.assertNotEqual(*ids)
        for args in ((13, 0), (13, 7), (31, 3)):
            with self.assertRaises(ValueError): PreparedIC(*args)
        with self.assertRaises(ValueError): no_floats({'bad': 0.1})
        with self.assertRaises(ValueError): scalar_replay(None, None, -1)


if __name__ == '__main__':
    unittest.main()
