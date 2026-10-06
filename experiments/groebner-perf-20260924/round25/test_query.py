"""Complete recovery, preparation parity, exact fallback and workspace isolation."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import random
import unittest
from unittest.mock import patch

from sparse_ic import PreparedIC, ARMS, Point, Ledger, ONLINE, scalar_replay, point, first, reference
from ic_identity import fixture, candidate, source_snapshot
from relations import Oracle


def semantic_certificate(value):
    return {k: v for k, v in value.items() if k not in ('backend', 'evaluation_counts', 'scratch_bytes', 'proof_stats')}


def semantics(attempt):
    answer = {k: attempt[k] for k in ('target', 'status', 'relations', 'roots_checked',
        'lift_rejections', 'membership_rejections') if k in attempt}
    basis = attempt.get('basis')
    if basis:
        answer['basis_sha256'] = basis['basis_sha256']
        answer['certificate'] = semantic_certificate(basis['basis_certificate'])
    for key in ('k', 'novel_rows', 'rank', 'root_checks', 'target_root_policy'):
        if key in attempt:
            answer[key] = attempt[key]
    return answer


class QueryTests(unittest.TestCase):
    def test_complete_recovery_and_frozen_pipeline_parity(self):
        compared = 0
        for ell in (3, 6):
            for seed in (401, 701):
                results = []
                for arm in ('reference', *ARMS):
                    query = first.PreparedIC(ell=ell) if arm == 'reference' else PreparedIC(ell=ell, arm=arm)
                    with query as q:
                        _, w, expected = fixture(q, seed)
                        result = q.recover(Point(**w['target']), w['rerandomization_seed'])
                        self.assertTrue(result['verified'], result)
                        self.assertEqual(result['scalar'], expected)
                        self.assertEqual(sum(result['phase_wall_ns'].values()), result['online_wall_ns'])
                        self.assertEqual(sum(q.preparation['phase_wall_ns'].values()), q.preparation['wall_ns'])
                        self.assertEqual(q.oracle.sum([scalar_replay(q.oracle, q.G, expected)]), Point(**w['target']))
                        results.append(([semantics(a) for a in q.preparation['attempts']],
                            [semantics(a) for a in result['attempts']], q.preparation['column_logs']))
                        if arm != 'reference':
                            expected_backend = 'independent-packed-sparse-proof' if arm == 'sparse' else 'independent-packed-bitslice-zeta'
                            for a in q.preparation['attempts'] + result['attempts']:
                                if a.get('basis', {}).get('status') == 'gb':
                                    self.assertEqual(a['basis']['basis_certificate']['backend'], expected_backend)
                            rho = q.rho(Point(**w['target']))
                            self.assertTrue(rho['verified'])
                            self.assertEqual(rho['scalar'], expected)
                            self.assertEqual(rho['reference_policy'], w['rho_reference'])
                        with self.assertRaises(RuntimeError):
                            q.recover(Point(**w['target']), w['rerandomization_seed'])
                    compared += 1
                self.assertEqual(results[0], results[1])
                self.assertEqual(results[0], results[2])
        print('Complete recovery comparisons with the frozen pipeline:', compared)

    def test_exhaustive_small_subgroup_and_ordinary_larger_controls(self):
        counts = Counter()
        for ell in (3, 6):
            with PreparedIC(ell=ell, arm='sparse') as sparse, PreparedIC(ell=ell) as packed:
                oracle = Oracle(sparse.fb, 3)
                scalars = range(1, sparse.curve.r) if ell == 3 else random.Random(20260929).sample(range(1, sparse.curve.r), 32)
                for k in scalars:
                    target = sparse.curve.K.smul(sparse.curve.G, k)
                    left = packed.backend.decompose(target, Ledger(ONLINE), target=True)
                    right = sparse.backend.decompose(target, Ledger(ONLINE), target=True)
                    self.assertEqual(semantics(left), semantics(right))
                    self.assertEqual(bool(right['relations']), oracle.ordered_count(target) > 0)
                    for rel in right['relations']:
                        points = [Point(**p) for p in rel['witness']['points']]
                        self.assertEqual(sparse.oracle.sum(points), point(target))
                        self.assertEqual(sum(c*sparse.logs[j] for j, c in rel['row']) % sparse.curve.r, k)
                    counts[ell, right['status']] += 1
        print('Exhaustive 9-variable and 32 ordinary 18-variable comparisons:', dict(counts))

    def test_forced_exact_fallback_and_sanitized_recovery(self):
        for budget, sanitized in ((True, False), (False, True)):
            with PreparedIC(ell=6, arm='sparse', budget_test=budget, sanitizer=sanitized) as q:
                _, w, expected = fixture(q, 701)
                result = q.recover(Point(**w['target']), w['rerandomization_seed'])
                self.assertTrue(result['verified'])
                self.assertEqual(result['scalar'], expected)
                self.assertEqual(sum(result['phase_wall_ns'].values()), result['online_wall_ns'])
                proofs = [a['basis']['basis_certificate']['proof_stats'] for a in q.preparation['attempts'] + result['attempts'] if a.get('basis', {}).get('status') == 'gb']
                self.assertTrue(proofs)
                self.assertTrue(all(p['budget_limit'] == (8 if budget else 65536) for p in proofs))
                if budget:
                    self.assertTrue(any(p['fallback_reason'] == 3 for p in proofs))
                _, manifest = candidate(q, source_snapshot())
                self.assertEqual(manifest['point_decomposition']['certificate_policy']['test_only_budget_build'], budget)

    def test_failures_reject_certificates_and_charge_attempts(self):
        for status in ('inconclusive', 'error'):
            with PreparedIC(arm='sparse', max_target=1) as q:
                _, w, _ = fixture(q, 401)
                with patch.object(q.backend.query.basis, 'compute', return_value={'status': status}):
                    result = q.recover(Point(**w['target']), w['rerandomization_seed'])
                self.assertFalse(result['verified'])
                self.assertEqual(result['status'], 'budget' if status == 'inconclusive' else 'error')
                self.assertEqual(len(result['attempts']), 1)
                self.assertEqual(sum(result['phase_wall_ns'].values()), result['online_wall_ns'])
                self.assertGreater(result['phase_wall_ns']['target_pdp'], 0)
        with PreparedIC(arm='sparse') as q:
            _, w, _ = fixture(q, 401)
            with patch.object(q.backend.query.basis, '_certify', return_value={'verified': False}):
                result = q.recover(Point(**w['target']), w['rerandomization_seed'])
            self.assertEqual(result['status'], 'error')
            self.assertFalse(result['verified'])
            self.assertFalse(result['attempts'][0]['relations'])

    def test_install_failure_closes_workspace_and_does_not_change_globals(self):
        factory = reference.PDP
        original_close, closed = reference.PDP.close, []
        def close(value):
            original_close(value)
            closed.append(value.query._closed)
        with patch.object(reference.PDP, 'close', new=close), patch('sparse_ic.SparseChecker', side_effect=RuntimeError('injected checker construction failure')):
            with self.assertRaisesRegex(RuntimeError, 'injected checker'):
                PreparedIC(arm='sparse')
        self.assertEqual(closed, [True])
        self.assertIs(reference.PDP, factory)

    def test_parallel_contexts_keep_distinct_checkers_and_invalid_targets_reject(self):
        def solve(arm):
            with PreparedIC(arm=arm) as q:
                _, w, expected = fixture(q, 401)
                answer = q.recover(Point(**w['target']), w['rerandomization_seed'])
                self.assertEqual(answer['scalar'], expected)
                return q.backend.query.checker.path.name, answer['verified']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(solve, ARMS))
        self.assertTrue(all(v for _, v in results))
        self.assertNotEqual(results[0][0], results[1][0])
        with PreparedIC(arm='sparse') as q:
            answer = q.recover(q.G, 'already-seen')
            self.assertEqual(answer['status'], 'error')
            self.assertFalse(answer['attempts'])
            self.assertEqual(sum(answer['phase_wall_ns'].values()), answer['online_wall_ns'])
        for kwargs in ({'arm': 'unknown'}, {'arm': 'packed', 'budget_test': True}, {'arm': 'sparse', 'budget_test': 1}):
            with self.assertRaises(ValueError): PreparedIC(**kwargs)


if __name__ == '__main__':
    unittest.main()
