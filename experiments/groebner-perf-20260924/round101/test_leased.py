"""Independent dense oracle, malformed C inputs, leases, budgets and freshness."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as C
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from query import Query, ARMS, HERE, P, abi, DenseInput, MatrixStats, LayoutStats
from audit import trace, proof_bytes
from common import Context
from panel import run_command
from worker import run
sys.path.insert(0, str(P.parent/'pdp-scaling'))
from boolean_basis import certify_boolean_basis


class LeasedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = [Query(), Query(sanitizer=True)]

    def checked(self, n, rows, result):
        self.assertTrue(result['verified'], result)
        self.assertTrue(abi.python_verify(n, rows, result['basis'], result['proof'],
            max_work=100000000, max_retained_terms=10000000)['verified'])
        if n <= 8:
            self.assertTrue(certify_boolean_basis(n, rows, result['basis'])['verified'])

    def call(self, q, layout, rows, **options):
        mapping = abi.anf_from_equations(rows)
        with q.workspace(layout.shape[0], len(rows), layout.support if rows else ()).borrow_mapping(mapping) as original:
            return q.compute(original, layout=layout, export_proof=True, **options)

    def dense(self, q, shape, rows):
        lib = q.dense_lib
        stats = LayoutStats()
        layout = lib.macaulay_layout_create(*shape, 67108864, C.byref(stats))
        self.assertTrue(layout)
        try:
            support = tuple(lib.macaulay_layout_support(layout)[:stats.support])
            original = DenseInput(shape[0], rows, support)
            matrix = MatrixStats()
            handle = lib.macaulay_apply(layout, C.byref(original.view), 20000000,
                                       1000000, 10000, C.byref(matrix))
            self.assertTrue(handle, lib.macaulay_error())
            try:
                view = lib.macaulay_view(handle).contents
                cert = q.base._check(original.view, view, 100000000, 10000000)
                return q._answer(view, cert, True)
            finally:
                lib.macaulay_result_destroy(handle)
        finally:
            lib.macaulay_layout_destroy(layout)

    def test_dense_oracle_random_ideals_and_permutations(self):
        rng = random.Random(1010006)
        for n in range(1, 7):
            for _ in range(6):
                rows = [[rng.randrange(1 << n) for _ in range(rng.randrange(7))]
                        for _ in range(rng.randrange(n+2))]
                degree = max((m.bit_count() for row in rows for m in row), default=0)
                shape = n, len(rows), degree, n
                for q in self.queries:
                    expected = self.dense(q, shape, rows)
                    with q.layout(*shape) as layout:
                        mapping = abi.anf_from_equations(rows)
                        items = list(mapping.items())
                        rng.shuffle(items)
                        for ordered in (mapping, dict(items)):
                            with q.workspace(n, len(rows), layout.support if rows else ()).borrow_mapping(ordered) as original:
                                result = q.compute(original, layout=layout, fallback=False,
                                    max_work=20000000, matrix_cap=20000000, export_proof=True)
                            self.checked(n, rows, result)
                            self.assertEqual(result['basis'], expected['basis'])
                            self.assertEqual(result['proof'], expected['proof'])

    def test_high_variables_zero_equations_and_limbs(self):
        for q in self.queries:
            for n, rows in ((2, []), (2, [[]]), (2, [[0]]), (2, [[1]]*65),
                            (2, [[2, 0]]*128), (32, [[1 << 31, 1], [1, 0]]),
                            (64, [[1 << 63, 1], [1, 0]])):
                with q.layout(n, len(rows), 1, 0) as layout:
                    self.checked(n, rows, self.call(q, layout, rows, fallback=False))

    def test_raw_malformed_input_and_recovery(self):
        for q in self.queries:
            with q.layout(2, 1, 1, 0) as layout:
                for mutation in ('duplicate', 'outside', 'padding', 'count', 'null', 'equations'):
                    original = DenseInput(2, [[1]], layout.support)
                    if mutation == 'duplicate': original.masks[1] = original.masks[0]
                    if mutation == 'outside': original.masks[0] = 3
                    if mutation == 'padding': original.coefficients[0] = 2
                    if mutation == 'count': original.view.terms = 4
                    if mutation == 'null': original.view.masks = abi.P64()
                    if mutation == 'equations': original.view.equations = 0
                    stats = MatrixStats()
                    handle = q.lib.macaulay_apply(layout._handle, C.byref(original.view),
                                                  100000, 10000, 10000, C.byref(stats))
                    self.assertFalse(handle, mutation)
                    self.assertEqual(stats.status, 1, mutation)
                    self.checked(2, [[1]], self.call(q, layout, [[1]], fallback=False))

    def test_every_small_budget_and_failed_candidate_fallback(self):
        for q in self.queries:
            with q.layout(2, 1, 2, 1) as layout:
                full = self.call(q, layout, [[3, 0]], fallback=False)
                self.checked(2, [[3, 0]], full)
                for key, maximum in (('max_work', full['work']), ('max_check_work', full['check_work'])):
                    for limit in range(maximum+2):
                        result = self.call(q, layout, [[3, 0]], **{key: limit})
                        self.assertLessEqual(result['work' if key == 'max_work' else 'check_work'], limit)
                        if result['verified']: self.checked(2, [[3, 0]], result)
                for cap in (0, 1, 2, 4, 8, 32):
                    result = self.call(q, layout, [[3, 0]], matrix_cap=cap)
                    self.assertLessEqual(result['attempts'][0]['stats']['work'], cap)
                    self.assertEqual(result['work'], sum(a['stats']['work'] for a in result['attempts']))
                    if result['verified']: self.checked(2, [[3, 0]], result)
            with q.layout(2, 1, 2, 0) as layout:
                failed = self.call(q, layout, [[3, 0]], fallback=False)
                self.assertFalse(failed['verified'])
                self.assertIn('field pair', failed['attempts'][0]['certificate']['reason'])
                result = self.call(q, layout, [[3, 0]])
                self.checked(2, [[3, 0]], result)
                self.assertEqual([a['kind'] for a in result['attempts']], ['macaulay', 'fresh-f4'])
                self.assertEqual(result['check_work'], sum(a.get('certificate', {}).get('stats', {}).get('work', 0) for a in result['attempts']))

    def test_lease_ownership_and_result_lifetime(self):
        for q in self.queries:
            with q.layout(2, 1, 1, 0) as layout:
                workspace = q.workspace(2, 1, layout.support)
                with workspace.borrow_mapping({1: 1}) as original:
                    result = q.compute(original, layout=layout, export_proof=True)
                    with self.assertRaises(ValueError):
                        q.compute(DenseInput(2, [[1]], layout.support), layout=layout)
                with self.assertRaises(RuntimeError): q.compute(original, layout=layout)
                layout.close()
                self.checked(2, [[1]], result)

    def test_changed_target_fresh_and_reused_trace(self):
        for sanitized in (False, True):
            ctx = Context(sanitizer=sanitized)
            before = None
            for name in ('pdp-6-seed-1', 'pdp-6-seed-3', 'pdp-6-seed-1'):
                values = {a: ctx.run(name, a, limits={'max_work': 80000000})['result'] for a in ARMS}
                self.assertEqual(trace(values['fresh2']), trace(values['reused2']))
                for value in values.values(): self.assertTrue(value['reference_equations_and_curve_replay'])
                if name == 'pdp-6-seed-1':
                    if before is not None: self.assertEqual(before, trace(values['reused2']))
                    before = trace(values['reused2'])

    def test_concurrent_numeric_calls(self):
        for q in self.queries:
            with q.layout(4, 2, 2, 1) as layout:
                def call(i):
                    rows = [[3]+([0] if i & 1 else []), [12]+([0] if i & 2 else [])]
                    result = self.call(q, layout, rows)
                    self.checked(4, rows, result)
                    return trace(result)
                expected = [call(i) for i in range(16)]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    self.assertEqual(expected, list(pool.map(call, range(16))))

    def test_proof_storage_and_process_failure_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'cells').mkdir()
            for i, arm in enumerate(('fresh2', 'reused2')):
                run('pdp-6-seed-1', arm, 80000000, output=root/'cells'/f'{i}.json')
            rows = [json.loads((root/'cells'/f'{i}.json').read_text()) for i in range(2)]
            self.assertEqual(rows[0]['result']['proof_sha256'], rows[1]['result']['proof_sha256'])
            self.assertEqual(len(list((root/'proofs').glob('*.json'))), 1)
            self.assertTrue(proof_bytes(root, rows[0]['result']['proof_sha256']))
            for row in rows: self.assertEqual(row['wall_ns'], sum(row['phases'].values()))
            failed = run_command([sys.executable, '-c', 'raise SystemExit(7)'], root/'failed.log', 5)
            self.assertEqual((failed['execution'], failed['exit_code']), ('process-failure', 7))
            timed = run_command([sys.executable, '-c', 'import time; time.sleep(60)'], root/'timed.log', .05)
            self.assertEqual(timed['execution'], 'timeout')
            self.assertGreaterEqual(timed['process_elapsed_ns'], 50000000)
            self.assertLess(timed['process_elapsed_ns'], 5000000000)


if __name__ == '__main__':
    unittest.main(verbosity=2)
