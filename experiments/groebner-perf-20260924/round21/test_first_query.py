"""Independent complete recovery, root-stop, failure and collection controls."""
from collections import Counter
import random
import unittest
from unittest.mock import patch

from first_query import PreparedIC, ARMS, Point, Ledger, ONLINE, PHASES, point, scalar_replay, reference
from first_identity import fixture
from relations import Oracle


class FirstQueryTests(unittest.TestCase):
    def test_exhaustive_small_subgroup_and_eighteen_variable_controls(self):
        comparisons = Counter()
        for ell in (3,6):
            with PreparedIC(13,ell,'first-usable') as q:
                oracle = Oracle(q.fb,3)
                scalars = range(1,q.curve.r) if ell == 3 else random.Random(801).sample(range(1,q.curve.r),64)
                for k in scalars:
                    R = q.curve.K.smul(q.curve.G,k)
                    answer = q.backend.decompose(R,Ledger(ONLINE),target=True)
                    all_roots = q.backend.parent.decompose(R,Ledger(ONLINE),target=True)
                    self.assertEqual(bool(answer['relations']),oracle.ordered_count(R)>0)
                    self.assertEqual(answer['status'],all_roots['status'])
                    self.assertEqual(answer['basis']['basis_sha256'],all_roots['basis']['basis_sha256'])
                    self.assertEqual(answer['basis']['basis_certificate'],all_roots['basis']['basis_certificate'])
                    self.assertLessEqual(answer['roots_checked'],all_roots['roots_checked'])
                    self.assertEqual(answer['roots_checked'],len(answer['root_checks']))
                    for rel in answer['relations']:
                        pts = [Point(**p) for p in rel['witness']['points']]
                        self.assertEqual(q.oracle.sum(pts),point(R))
                        self.assertEqual(sum(c*q.logs[j] for j,c in rel['row']) % q.curve.r,k)
                    comparisons[ell,answer['status']] += 1
                self.assertTrue(all(a['roots_checked'] == a['basis']['basis_certificate']['root_count']
                                    for a in q.preparation['attempts']))
        print('Exhaustive 9-variable and 64 ordinary 18-variable controls:',dict(comparisons))

    def test_complete_target_parity_and_unchanged_collection(self):
        for ell in (3,6):
            for seed in (701,801):
                records = {}
                for arm in ARMS:
                    with PreparedIC(13,ell,arm) as q:
                        _,w,k = fixture(q,seed)
                        with patch.object(reference.PackedANF,'to_dict',side_effect=AssertionError('dictionary')):
                            answer = q.recover(Point(**w['target']),w['rerandomization_seed'])
                        self.assertTrue(answer['verified'])
                        self.assertEqual(answer['scalar'],k)
                        self.assertEqual(sum(answer['phase_wall_ns'].values()),answer['online_wall_ns'])
                        self.assertEqual(sum(q.preparation['phase_wall_ns'].values()),q.preparation['wall_ns'])
                        with self.assertRaises(RuntimeError): q.recover(Point(**w['target']),w['rerandomization_seed'])
                        records[arm] = ([(a['target'],a['basis']['basis_sha256'],a['relations'],a['rank'])
                                         for a in q.preparation['attempts']],
                                        [(a['target'],a['status']) for a in answer['attempts']])
                self.assertEqual(records['all-roots'],records['first-usable'])

    def test_skip_unusable_root_and_stop_at_first_valid_one(self):
        with PreparedIC(13,6) as q:
            positive = next(a for a in q.preparation['attempts'] if len(a['relations']) >= 2)
            R = tuple(positive['target'])
            first = q.backend.decompose(R,Ledger(ONLINE),target=True)
            bad = first['relations'][0]['witness']['points'][0]
            original = dict(q.backend.mapping)
            q.backend.mapping.pop((bad['x'],bad['y']))
            answer = q.backend.decompose(R,Ledger(ONLINE),target=True)
            self.assertGreater(answer['membership_rejections'],0)
            self.assertTrue(answer['relations'])
            self.assertEqual(len(answer['relations']),1)
            self.assertEqual(answer['root_checks'][-1]['status'],'accepted')
            self.assertEqual([c['status'] for c in answer['root_checks']].count('accepted'),1)
            q.backend.mapping.clear()
            none = q.backend.decompose(R,Ledger(ONLINE),target=True)
            self.assertEqual(none['status'],'lift_rejected')
            self.assertFalse(none['relations'])
            self.assertEqual(none['roots_checked'],none['basis']['basis_certificate']['root_count'])
            q.backend.mapping.update(original)

    def test_producer_budget_failure_and_invalid_certificate(self):
        with PreparedIC() as q:
            R = q.curve.K.smul(q.curve.G,17)
            for status,expected in (('inconclusive','budget'),('error','error')):
                with patch.object(q.backend.query.basis,'compute',return_value={'status':status}):
                    a = q.backend.decompose(R,Ledger(ONLINE),target=True)
                self.assertEqual(a['status'],expected)
                self.assertFalse(a['root_checks'])
            with patch.object(q.backend.query.basis,'compute',return_value={
                    'status':'gb','groebner_verified':False,'basis_certificate':{'verified':False}}):
                with self.assertRaises(RuntimeError): q.backend.decompose(R,Ledger(ONLINE),target=True)
        with self.assertRaises(ValueError): PreparedIC(arm='unknown')


if __name__ == '__main__': unittest.main()
