"""Lease, cleanup, budget and independently evaluated proof boundary tests."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import unittest

import seeded_query
from seeded_query import Query, abi
from capture import OwnedProof
from proof_reader import decode


def evaluate(proof, equations):
    values = []
    for node in proof['nodes']:
        if node[0] == 'input':
            value = set(equations[node[1]])
        elif node[0] == 'xor':
            value = values[node[1]] ^ values[node[2]]
        else:
            value = set()
            for mask in values[node[1]]:
                product = mask | node[2]
                value.symmetric_difference_update((product,))
        values.append(value)
    return [values[i] for i in proof['outputs']]


class QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = [Query(sanitizer=value) for value in (False, True)]

    def solve(self, q, equations=None, nvars=2, **options):
        equations = equations if equations is not None else [[3, 1], [2, 1]]
        mapping = abi.anf_from_equations(equations)
        workspace = q.workspace(nvars, len(equations), list(mapping))
        with workspace.borrow_mapping(mapping) as packed:
            before = list(packed.items())
            result = q.compute(packed, export_proof=True, **options)
            self.assertEqual(list(packed.items()), before)
        self.assertEqual(sum(result['phases'].values()), result['wall_ns'])
        self.assertTrue(all(v >= 0 for v in result['phases'].values()))
        self.assertEqual(sum(a['stats']['work'] for a in result['attempts']), result['work'])
        self.assertEqual(sum(a.get('certificate', {}).get('stats', {}).get('work', 0)
                             for a in result['attempts']), result['check_work'])
        self.assertLessEqual(result['work'], options.get('max_work', 2_000_000))
        self.assertLessEqual(result['check_work'], options.get('max_check_work', 20_000_000))
        if result['verified']:
            self.assertIsInstance(result['proof'], OwnedProof)
            proof = decode(result['proof'].serialized())
            self.assertEqual(evaluate(proof, equations), list(map(set, result['basis'])))
            for assignment in range(1 << nvars):
                zero = lambda rows: all(sum((m & assignment) == m for m in row) % 2 == 0 for row in rows)
                self.assertEqual(zero(equations), zero(result['basis']))
        else:
            self.assertNotIn('proof', result)
            self.assertNotIn('basis', result)
        return result

    def test_fresh_reused_and_owned_output_without_export(self):
        for q in self.queries:
            with patch.object(abi, 'export', side_effect=AssertionError('Python proof decoding in query')):
                fresh = self.solve(q)
                with q.layout(2, 2, 2, 2) as layout:
                    reused = self.solve(q, layout=layout)
                    again = self.solve(q, layout=layout)
                self.assertTrue(fresh['verified'] and reused['verified'])
                self.assertEqual(fresh['basis'], reused['basis'])
                self.assertEqual(reused['proof'], again['proof'])
                temporary = self.solve(q, fresh_shape=(2, 2, 2, 2))
                self.assertEqual(temporary['proof'], reused['proof'])

    def test_live_lease_and_layout_ownership(self):
        q = self.queries[0]
        workspace = q.workspace(2, 1, [1])
        with workspace.borrow_mapping({1: 1}) as packed:
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaises(RuntimeError):
                    pool.submit(q.compute, packed).result()
            with self.queries[1].layout(2, 1, 1, 1) as foreign:
                with self.assertRaises(ValueError): q.compute(packed, layout=foreign)
            layout = q.layout(2, 1, 1, 1)
            layout.close()
            with self.assertRaises(RuntimeError): q.compute(packed, layout=layout)
            with self.assertRaises(ValueError): q.compute(packed, layout=layout, fresh_shape=(2, 1, 1, 1))
        with self.assertRaises(RuntimeError): q.compute(packed)
        with self.assertRaises(ValueError): q.compute(abi.InputOwner(2, 1, {1: 1}))

    def test_all_small_work_and_checker_prefixes(self):
        for q in self.queries:
            full = self.solve(q)
            for work in range(full['work']+2):
                result = self.solve(q, max_work=work)
                self.assertEqual(result['verified'], work >= full['work'])
            for work in range(full['check_work']+2):
                result = self.solve(q, max_check_work=work)
                self.assertEqual(result['verified'], work >= full['check_work'])

    def test_no_fallback_and_matrix_failure(self):
        for q in self.queries:
            with q.layout(2, 2, 2, 0) as layout:
                stopped = self.solve(q, layout=layout, fallback=False, matrix_cap=0)
                self.assertEqual([a['kind'] for a in stopped['attempts']], ['macaulay'])
                self.assertFalse(stopped['verified'])
                fallback = self.solve(q, layout=layout, matrix_cap=0)
                self.assertEqual([a['kind'] for a in fallback['attempts']], ['macaulay', 'fresh-f4'])
                self.assertTrue(fallback['verified'])

    def test_seeded_continuation_shares_budgets_and_can_be_disabled(self):
        equations = [[1, 6], [2, 5]]
        for q in self.queries:
            with q.layout(3, 2, 2, 0) as layout:
                options = dict(equations=equations, nvars=3, layout=layout)
                full = self.solve(q, **options)
                self.assertEqual([a['kind'] for a in full['attempts']], ['macaulay', 'seeded-f4'])
                self.assertFalse(full['attempts'][0]['verified'])
                self.assertTrue(full['verified'])
                stopped = self.solve(q, **options, fallback=False)
                self.assertFalse(stopped['verified'])
                self.assertEqual(len(stopped['attempts']), 1)
                for cap in (0, 1, full['attempts'][0]['stats']['work'], full['work']-1, full['work']):
                    self.solve(q, **options, max_work=cap)
                for cap in (0, 1, full['check_work']-1, full['check_work']):
                    result = self.solve(q, **options, max_check_work=cap)
                    self.assertEqual(result['verified'], cap == full['check_work'])
                destroy_original = q.native.lib.seeded_destroy
                with patch.object(q.native.lib, 'seeded_destroy', wraps=destroy_original) as destroy, \
                        patch.object(seeded_query, 'capture', side_effect=RuntimeError('seed copy failed')):
                    with self.assertRaisesRegex(RuntimeError, 'seed copy failed'):
                        self.solve(q, **options)
                    self.assertEqual(destroy.call_count, 1)

    def test_exception_releases_result_and_temporary_layout(self):
        q = self.queries[0]
        original_destroy = q.lib.macaulay_result_destroy
        original_close = q.lib.macaulay_layout_destroy
        with patch.object(q.lib, 'macaulay_result_destroy', wraps=original_destroy) as destroy, \
                patch.object(q.lib, 'macaulay_layout_destroy', wraps=original_close) as close, \
                patch.object(seeded_query, 'capture', side_effect=RuntimeError('capture failed')):
            with self.assertRaisesRegex(RuntimeError, 'capture failed'):
                self.solve(q, fresh_shape=(2, 2, 2, 2))
            self.assertEqual(destroy.call_count, 1)
            self.assertEqual(close.call_count, 1)
        self.assertTrue(self.solve(q, fresh_shape=(2, 2, 2, 2))['verified'])

    def test_concurrent_calls_keep_per_call_counters(self):
        for q in self.queries:
            with q.layout(2, 2, 2, 2) as layout:
                expected = self.solve(q, layout=layout)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(lambda _: self.solve(q, layout=layout), range(12)))
                for result in results:
                    self.assertEqual(result['proof'], expected['proof'])
                    self.assertEqual(result['work'], expected['work'])
                    self.assertEqual(result['check_work'], expected['check_work'])


if __name__ == '__main__':
    unittest.main()
