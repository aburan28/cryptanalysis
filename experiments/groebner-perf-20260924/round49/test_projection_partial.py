"""Tagged certificate semantics, complete-basis boundaries and charged failures."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
import importlib.util
import os
from pathlib import Path
import sys
import unittest

from adapter import producer as candidate
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'round44'))
from tagged_reference import TAG, certify_roots

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('accepted_normalized44', HERE.parent / 'round44/normalized.py')
accepted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accepted)
sys.path.insert(0, str(HERE.parent / 'round37'))
from test_fixed_width import truth
from quadratic_reference import verify_basis
from multipliers import Checker as OldChecker


def integers(stats):
    return {k: v for k, v in stats.items() if type(v) is int}


class PartialTests(unittest.TestCase):
    def modes(self):
        return [('cpu', False), ('cpu', True)] + ([('metal', False)] if os.environ.get('QUADRATIC_TEST_METAL') == '1' else [])

    def verify(self, x, y, equations, terms, producer, checker):
        packed = candidate.Packed(x + y, equations, terms)
        result = producer.produce(packed, checker=checker)
        expected = truth(x + y, terms)
        self.assertEqual(result['roots'], expected)
        self.assertTrue(result['certificate']['verified'], result['certificate'])
        self.assertTrue(verify_basis(x + y, terms, expected, result['basis'], len(expected)))
        roots, constants, extended, partials, assignments = certify_roots(
            x, y, equations, tuple(tuple(v) for v in terms), result['proof_bytes'], sys.byteorder)
        self.assertEqual(list(roots), expected)
        check = result['certificate']
        self.assertEqual(check['stats']['assignments'], assignments)
        self.assertEqual(check['stats']['contradictions'], constants + len(extended) + sum(v[2] for v in partials))
        self.assertEqual(check['stats']['extended_contradictions'], len(extended))
        self.assertEqual(check['partial_stats']['records'], len(partials))
        self.assertEqual(check['partial_stats']['rank_sum'], sum(v[1] for v in partials))
        self.assertEqual(check['partial_stats']['assignments'], sum(v[3] for v in partials))
        self.assertEqual(result['partial_stats']['handled_branches'] + result['partial_stats']['copied_records'], len(partials))
        self.assertEqual(result['multiplier_stats']['certified_branches'] + result['symmetry_stats']['affine_copies'] - result['partial_stats']['copied_records'], len(extended))
        self.assertEqual(result['multiplier_stats']['attempts'], result['multiplier_stats']['certified_branches'] + result['multiplier_stats']['failed_branches'])
        self.assertEqual(result['symmetry_stats']['representatives'] + result['symmetry_stats']['aliases'], 1 << x)
        self.assertEqual(result['multiplier_stats']['proof_words'] * 8, len(result['proof_bytes']))
        return result

    def test_forced_partial_roots_both_limbs_and_sanitizer(self):
        for backend, sanitizer in self.modes():
            for y in (3, 7, 10):
                rank = y - 3 if y > 3 else 1
                for equations in (max(3, rank + 1), 31, 32, 63, 64, 65, 127, 128):
                    terms = [(1 << (2 + j), 1 << j) for j in range(rank)]
                    high = 1 << (equations - 1)
                    terms += [(((1 << (y - 2)) | (1 << (y - 1))) << 2, high), (0, high)]
                    with candidate.Producer(2, y, equations, backend=backend, sanitizer=sanitizer) as p, candidate.Checker(2, y, equations, sanitizer=sanitizer) as c:
                        a = self.verify(2, y, equations, terms, p, c)
                        self.assertEqual(a['partial_stats']['handled_branches'], 3)
                        self.assertEqual(a['partial_stats']['copied_records'], 1)
                        self.assertEqual(a['certificate']['partial_stats']['rank_sum'], 4 * rank)
                        self.assertEqual(a['certificate']['partial_stats']['assignments'], 4 * (1 << (y - rank)))
                        self.assertEqual(bool(a['stats']['gpu_used']), backend == 'metal' and equations <= 32)

    def test_enabled_disabled_and_fresh_asymmetric_inputs(self):
        systems = [[(4, 1), (24, 2), (0, 2)],
                   [(4, 1), (24, 2), (0, 2), (1, 1)],
                   [(4, 1), (24, 2), (0, 6), (8, 4), (16, 4)],
                   [(24, 2), (0, 2)],
                   [(4, 1), (8, 2), (16, 4), (0, 6)]]
        for backend, sanitizer in self.modes():
            with candidate.Producer(2, 3, 3, backend=backend, sanitizer=sanitizer) as p, candidate.Checker(2, 3, 3, sanitizer=sanitizer) as c, accepted.Producer(2, 3, 3, backend=backend, sanitizer=sanitizer) as old:
                for terms in systems:
                    p.configure_partial(False)
                    a = self.verify(2, 3, 3, terms, p, c)
                    old.configure_partial(False)
                    b = old.produce(candidate.Packed(5, 3, terms))
                    if backend != 'metal':
                        self.assertEqual(a['proof_bytes'], b['proof_bytes'])
                    self.assertEqual(a['roots'], b['roots'])
                    self.assertEqual(a['basis'], b['basis'])
                    p.configure_partial(True)
                    new = self.verify(2, 3, 3, terms, p, c)
                    self.assertEqual(new['roots'], b['roots'])
                    self.assertEqual(new['basis'], b['basis'])
                self.assertEqual(self.verify(2, 3, 3, systems[0], p, c)['partial_stats']['handled_branches'], 3)

    def test_malformed_tagged_records_and_global_basis_checks(self):
        terms = [(4, 1), (24, 2), (0, 2)]
        packed = candidate.Packed(5, 3, terms)
        for sanitizer in (False, True):
            with candidate.Producer(2, 3, 3, sanitizer=sanitizer) as p, candidate.Checker(2, 3, 3, sanitizer=sanitizer) as c:
                a = p.produce(packed, checker=c)
                words = list((candidate.U64 * (len(a['proof_bytes']) // 8)).from_buffer_copy(a['proof_bytes']))
                for kind in ('unknown-tag', 'padding', 'duplicate', 'reorder', 'overlap', 'extent'):
                    bad = words[:]
                    if kind == 'unknown-tag': bad[4] |= 1 << 62
                    elif kind == 'padding': bad[5] |= 8
                    elif kind == 'duplicate': bad[9] = bad[4]
                    elif kind == 'reorder': bad[4:9], bad[9:14] = bad[9:14], bad[4:9]
                    elif kind == 'overlap': bad[0] = 1
                    else: bad.pop()
                    with self.subTest(kind=kind), self.assertRaises(ValueError):
                        c.certify(packed, a['roots'], a['basis'], (candidate.U64 * len(bad))(*bad))
                for kind in ('nonlinear', 'wrong-kind'):
                    bad = words[:]
                    if kind == 'nonlinear': bad[5] = 2
                    else: bad[4] &= ~TAG
                    self.assertEqual(c.certify(packed, a['roots'], a['basis'], (candidate.U64 * len(bad))(*bad))['code'], 9)
                self.assertEqual(c.certify(packed, a['roots'][:-1], a['basis'], a['proof_bytes'])['code'], 3)
                self.assertEqual(c.certify(packed, a['roots'], [], a['proof_bytes'])['code'], 4)
                changed = candidate.Packed(5, 3, terms[:-1])
                self.assertFalse(c.certify(changed, a['roots'], a['basis'], a['proof_bytes'])['verified'])

    def test_zero_dependent_reordered_and_missing_witnesses(self):
        terms = [(4, 1), (24, 2), (0, 2)]
        packed = candidate.Packed(5, 3, terms)
        with candidate.Producer(2, 3, 3) as p, candidate.Checker(2, 3, 3) as c:
            a = p.produce(packed, checker=c)
            words = list((candidate.U64 * (len(a['proof_bytes']) // 8)).from_buffer_copy(a['proof_bytes']))
            for kind in ('zero', 'dependent', 'reorder', 'missing-one', 'missing-all'):
                bad = words[:]
                if kind in ('zero', 'dependent', 'reorder'):
                    for offset in range(4, len(bad), 5):
                        if kind == 'zero': bad[offset + 1:offset + 5] = [0] * 4
                        elif kind == 'dependent': bad[offset + 2] = bad[offset + 1]
                        else: bad[offset + 1:offset + 5] = reversed(bad[offset + 1:offset + 5])
                elif kind == 'missing-one': del bad[4:9]
                else: bad = bad[:4]
                result = c.certify(packed, a['roots'], a['basis'], (candidate.U64 * len(bad))(*bad))
                self.assertTrue(result['verified'], kind)
                self.assertEqual(result['root_count'], 4)
                if kind in ('zero', 'missing-all'):
                    self.assertEqual(result['stats']['assignments'], 32)

    def test_old_checker_rejects_new_tag(self):
        packed = candidate.Packed(5, 3, [(4, 1), (24, 2), (0, 2)])
        with candidate.Producer(2, 3, 3) as p, OldChecker(2, 3, 3) as old:
            a = p.produce(packed)
            with self.assertRaises(ValueError): old.certify(packed, a['roots'], a['basis'], a['proof_bytes'])

    def test_copy_budget_and_partial_commit_rollback(self):
        terms = [(4, 1), (24, 2), (0, 2)]
        with candidate.Checker(2, 3, 3) as c:
            with candidate.Producer(2, 3, 3, copy_budget_test=True) as p:
                a = self.verify(2, 3, 3, terms, p, c)
                self.assertEqual(a['partial_stats']['handled_branches'], 3)
                self.assertEqual(a['partial_stats']['copied_records'], 0)
                self.assertEqual(a['certificate']['partial_stats']['records'], 3)
                self.assertEqual(a['certificate']['stats']['assignments'], 20)
            with candidate.Producer(2, 3, 3, partial_commit_budget_test=True) as p:
                a = self.verify(2, 3, 3, terms, p, c)
                self.assertGreater(a['partial_stats']['roots_found'], 0)
                self.assertEqual(a['partial_stats']['handled_branches'], 0)
                self.assertGreater(a['partial_stats']['budget_skips'], 0)
                self.assertEqual(a['partial_stats']['assignments'], 12)
                self.assertEqual(a['stats']['fallback_assignments'], 24)

    def test_global_assignment_and_checker_work_budgets(self):
        packed = candidate.Packed(5, 3, [(4, 1), (24, 2), (0, 2)])
        with candidate.Producer(2, 3, 3, enumeration_budget_test=True) as p:
            with self.assertRaises(candidate.Inconclusive) as failure: p.produce(packed)
            self.assertEqual(failure.exception.partial_stats['assignments'], 8)
        with candidate.Producer(2, 3, 3) as p:
            a = p.produce(packed)
            for flag in ('budget_test', 'partial_budget_test'):
                with candidate.Checker(2, 3, 3, **{flag: True}) as c:
                    check = c.certify(packed, a['roots'], a['basis'], a['proof_bytes'])
                    self.assertEqual(check['code'], 5)
                    self.assertFalse(check['verified'])
                    self.assertIsNone(check['root_count'])

    def test_configuration_lifecycle_and_concurrent_reuse(self):
        packed = candidate.Packed(5, 3, [(4, 1), (24, 2), (0, 2)])
        with candidate.Producer(2, 3, 3) as p, candidate.Checker(2, 3, 3) as c:
            for bad in (0, 1, None, 'yes'):
                with self.assertRaises(ValueError): p.configure_partial(bad)
            self.assertEqual(p.lib.branch_partial_configure(p._handle, 2), -1)
            expected = p.produce(packed, checker=c)
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: p.produce(packed, checker=c), range(12)))
            for answer in results:
                self.assertEqual(answer['roots'], expected['roots'])
                self.assertEqual(answer['basis'], expected['basis'])
                self.assertEqual(answer['proof_bytes'], expected['proof_bytes'])
                self.assertEqual(integers(answer['partial_stats']), integers(expected['partial_stats']))
        with self.assertRaises(RuntimeError): p.produce(packed)
        with self.assertRaises(RuntimeError): c.certify(packed, expected['roots'], expected['basis'], expected['proof_bytes'])


if __name__ == '__main__':
    unittest.main()
