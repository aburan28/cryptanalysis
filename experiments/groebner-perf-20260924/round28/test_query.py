"""Complete recovery parity and exhaustive ordinary-query pair controls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import unittest
from unittest.mock import patch

from conditional_ic import ARMS, CHECKERS, PreparedIC, Point, Ledger, PHASES, point, IDENTITY
from conditional_ic import reference, scalar_replay
from conditional_identity import candidate, fixture, receipt, source_snapshot


def semantics(attempts):
    keys = ('target','status','relations','roots_checked','lift_rejections',
            'membership_rejections','k','novel_rows','rank','root_checks','target_root_policy')
    return [{k:a[k] for k in keys if k in a} for a in attempts]


class QueryTests(unittest.TestCase):
    def test_all_nonzero_subgroup_queries_match_independent_pair_oracle(self):
        count = 0
        for ell in (3,6):
            with ExitStack() as stack:
                prepared = [stack.enter_context(PreparedIC(ell=ell,arm=a))
                            for a in ('two-eval','two-conditional')]
                q = prepared[0]
                points = [point(p) for p in q.fb.point_index()]
                sums = {q.oracle.add(P,Q) for P in points for Q in points}
                R = IDENTITY
                for _ in range(1,q.curve.r):
                    R = q.oracle.add(R,q.G)
                    answers = []
                    for p in prepared:
                        result = p.backend.decompose((R.x,R.y),Ledger(PHASES))
                        self.assertEqual(bool(result['relations']),R in sums)
                        self.assertNotIn(result['status'],('error','budget'))
                        for rel in result['relations']:
                            self.assertEqual(q.oracle.sum([Point(**x) for x in rel['witness']['points']]),R)
                        answers.append(result)
                        count += 1
                    self.assertEqual(semantics(answers[:1]),semantics(answers[1:]))
                    self.assertEqual(answers[0]['basis']['basis_terms'],answers[1]['basis']['basis_terms'])
        print('Exhaustive independently checked ordinary subgroup queries:',count)

    def test_complete_recovery_rho_and_exact_identities(self):
        snapshot = source_snapshot()
        for ell in (3,6):
            for seed in (401,701,702,703):
                with ExitStack() as stack:
                    prepared = {a:stack.enter_context(PreparedIC(ell=ell,arm=a)) for a in ARMS}
                    wid,w,expected = fixture(prepared,seed)
                    Q = Point(**w['target'])
                    self.assertTrue(all(Q not in q.seen_points for q in prepared.values()))
                    rho = prepared[ARMS[0]].rho(Q)
                    self.assertTrue(rho['verified'])
                    self.assertEqual(rho['scalar'],expected)
                    answers,cids = {},[]
                    for arm,q in prepared.items():
                        result = q.recover(Q,w['rerandomization_seed'])
                        self.assertTrue(result['verified'],result)
                        self.assertEqual(result['scalar'],expected)
                        self.assertEqual(sum(result['phase_wall_ns'].values()),result['online_wall_ns'])
                        self.assertEqual(sum(q.preparation['phase_wall_ns'].values()),q.preparation['wall_ns'])
                        cid,manifest = candidate(q,snapshot)
                        self.assertEqual(manifest['point_decomposition']['summands'],q.summands)
                        self.assertEqual(q.backend.query.shape[-2:],(q.summands,ell))
                        row = receipt(q,cid,manifest,wid,w,result,rho,1,q.preparation['wall_ns']+result['online_wall_ns'])
                        self.assertEqual(row['target_result'],result)
                        self.assertEqual(row['rho_measured'],rho)
                        cids.append(cid)
                        answers[arm] = result
                    self.assertEqual(len(set(cids)),3)
                    left,right = prepared['two-eval'],prepared['two-conditional']
                    self.assertEqual(semantics(left.preparation['attempts']),semantics(right.preparation['attempts']))
                    self.assertEqual(left.preparation['column_logs'],right.preparation['column_logs'])
                    self.assertEqual(semantics(answers['two-eval']['attempts']),semantics(answers['two-conditional']['attempts']))

    def test_three_summand_arm_preserves_frozen_sparse_euclid_pipeline(self):
        for ell in (3,6):
            with PreparedIC(ell=ell) as q, reference.PreparedIC(ell=ell,arm='euclid',verifier=CHECKERS[ell]) as old:
                self.assertEqual(semantics(q.preparation['attempts']),semantics(old.preparation['attempts']))
                self.assertEqual(q.seen_points,old.seen_points)
                self.assertEqual(q.preparation['column_logs'],old.preparation['column_logs'])

    def test_failure_lifetime_and_workspace_isolation(self):
        for arm in ARMS:
            with PreparedIC(arm=arm,max_collection=1) as q:
                self.assertEqual(q.preparation['status'],'insufficient_relations')
                answer = q.recover(q.G,'unready')
                self.assertFalse(answer['verified'])
                self.assertIsNone(answer['online_wall_ns'])
            with PreparedIC(arm=arm) as q:
                answer = q.recover(Point(-1,1),'invalid')
                self.assertEqual(answer['status'],'error')
                self.assertFalse(answer['attempts'])
                with self.assertRaises(RuntimeError):q.recover(Point(-1,1),'again')
            with self.assertRaises(RuntimeError):q.rho(q.G)
        def run(arm):
            with PreparedIC(arm=arm) as q:
                return q.backend.query.shape[-2],q.preparation['status']
        with ThreadPoolExecutor(max_workers=3) as pool:
            self.assertEqual(list(pool.map(run,ARMS)),[(3,'ready'),(2,'ready'),(2,'ready')])
        with self.assertRaises(ValueError):PreparedIC(arm='invalid')

    def test_corrupted_final_scalar_replay_cannot_pass(self):
        with ExitStack() as stack:
            prepared = {a:stack.enter_context(PreparedIC(arm=a)) for a in ARMS}
            _,w,_ = fixture(prepared,401)
            q = prepared['two-conditional']
            validate,add = q.validate_public,q.oracle.add
            def corrupt_after_validation(Q):
                validate(Q)
                q.oracle.add = lambda *args:IDENTITY
            with patch.object(q,'validate_public',side_effect=corrupt_after_validation):
                answer = q.recover(Point(**w['target']),w['rerandomization_seed'])
            q.oracle.add = add
            self.assertEqual(answer['status'],'error')
            self.assertFalse(answer['verified'])
            self.assertTrue(answer['attempts'])

    def test_complete_query_with_rebuilt_ubsan_components(self):
        for sanitizer in (False,True):
            with ExitStack() as stack:
                prepared = {a:stack.enter_context(PreparedIC(ell=6,arm=a,sanitizer=sanitizer)) for a in ARMS}
                _,w,expected = fixture(prepared,401)
                for q in prepared.values():
                    answer = q.recover(Point(**w['target']),w['rerandomization_seed'])
                    self.assertTrue(answer['verified'])
                    self.assertEqual(answer['scalar'],expected)


if __name__ == '__main__':unittest.main()
