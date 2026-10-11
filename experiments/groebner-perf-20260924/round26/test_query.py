"""Complete recovery and matched-rho parity with per-instance arithmetic."""
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from replay_query import PreparedIC, ARMS, CHECKERS, Point, GF2n, EuclidField, reference
from replay_identity import fixture, candidate, source_snapshot, receipt

def semantics(answer):
    return [{k: a[k] for k in ('target', 'status', 'relations', 'roots_checked',
        'lift_rejections', 'membership_rejections', 'k', 'novel_rows', 'rank',
        'root_checks', 'target_root_policy') if k in a} for a in answer]


class QueryTests(unittest.TestCase):
    def test_complete_recovery_and_both_rho_checks_match_frozen_pipeline(self):
        count = 0
        for ell in (3, 6):
            for seed in (401, 701, 702, 703):
                compared = []
                for arm in ('reference', *ARMS):
                    context = (reference.PreparedIC(ell=ell, arm=CHECKERS[ell]) if arm == 'reference'
                               else PreparedIC(ell=ell, arm=arm, verifier=CHECKERS[ell]))
                    with context as q:
                        wid, w, expected = fixture(q, seed)
                        result = q.recover(Point(**w['target']), w['rerandomization_seed'])
                        rho = q.rho(Point(**w['target']))
                        self.assertTrue(result['verified'])
                        self.assertTrue(rho['verified'])
                        self.assertEqual(result['scalar'], expected)
                        self.assertEqual(rho['scalar'], expected)
                        self.assertEqual(sum(result['phase_wall_ns'].values()), result['online_wall_ns'])
                        self.assertEqual(sum(q.preparation['phase_wall_ns'].values()), q.preparation['wall_ns'])
                        compared.append((semantics(q.preparation['attempts']), semantics(result['attempts']), q.preparation['column_logs']))
                        if arm != 'reference':
                            self.assertIs(type(q.oracle.F), EuclidField if arm == 'euclid' else GF2n)
                            self.assertEqual(result['independent_arithmetic'], rho['reference_policy']['independent_arithmetic'])
                            self.assertEqual(rho['reference_policy'], w['rho_reference']['policies'][arm])
                            cid, record = candidate(q, source_snapshot())
                            row = receipt(q, cid, record, wid, w, result, rho, 1, q.preparation['wall_ns']+result['online_wall_ns'])
                            self.assertEqual(row['resource_envelope']['independent_arithmetic'], result['independent_arithmetic'])
                            other = 'power' if arm == 'euclid' else 'euclid'
                            mismatch = {**rho, 'reference_policy': w['rho_reference']['policies'][other]}
                            with self.assertRaisesRegex(ValueError, 'same independent checker'):
                                receipt(q, cid, record, wid, w, result, mismatch, 1, row['wall_ns'])
                        count += 1
                self.assertEqual(compared[0], compared[1])
                self.assertEqual(compared[0], compared[2])
        print('Complete IC and same-point rho parity controls:', count)

    def test_invalid_targets_and_corrupted_scalar_check_reject(self):
        for Q in (Point(-1, 1), Point(1 << 13, 1), Point(True, 1), Point(0, 1), Point(0, 0, True)):
            with PreparedIC(arm='euclid') as q:
                result = q.recover(Q, 'invalid-target')
                self.assertFalse(result['verified'])
                self.assertEqual(result['status'], 'error')
                self.assertFalse(result['attempts'])
                self.assertEqual(sum(result['phase_wall_ns'].values()), result['online_wall_ns'])
                with self.assertRaises(ValueError): q.rho(Q)
        with PreparedIC(ell=6, arm='euclid', verifier='sparse') as q:
            _, w, _ = fixture(q, 701)
            original = q.oracle.add
            # Public-point validation must pass before corrupting only the final
            # replay, so this checks the independent recovery gate itself.
            validate = q.validate_public
            def validate_then_corrupt(target):
                validate(target)
                q.oracle.add = lambda *args: Point(0, 0, True)
            with patch.object(q, 'validate_public', side_effect=validate_then_corrupt):
                result = q.recover(Point(**w['target']), w['rerandomization_seed'])
            q.oracle.add = original
            self.assertFalse(result['verified'])
            self.assertEqual(result['status'], 'error')
            self.assertTrue(result['attempts'])

    def test_parallel_workspaces_keep_independent_arithmetic(self):
        original = GF2n.inv
        def solve(arm):
            with PreparedIC(arm=arm) as q:
                _, w, expected = fixture(q, 401)
                result = q.recover(Point(**w['target']), w['rerandomization_seed'])
                self.assertEqual(result['scalar'], expected)
                return type(q.oracle.F), result['verified']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(solve, ARMS))
        self.assertEqual(results, [(GF2n, True), (EuclidField, True)])
        self.assertIs(GF2n.inv, original)
        with self.assertRaises(ValueError): PreparedIC(arm='unknown')

    def test_setup_failure_and_single_use_context(self):
        with patch.object(EuclidField, 'inv', return_value=1):
            with self.assertRaises(RuntimeError): PreparedIC(arm='euclid')
        with PreparedIC(arm='euclid') as q:
            _, w, _ = fixture(q, 401)
            q.recover(Point(**w['target']), w['rerandomization_seed'])
            with self.assertRaises(RuntimeError): q.recover(Point(**w['target']), w['rerandomization_seed'])
        with self.assertRaises(RuntimeError): q.rho(Point(**w['target']))


if __name__ == '__main__':
    unittest.main()
