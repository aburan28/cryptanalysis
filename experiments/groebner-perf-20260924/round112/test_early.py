"""Exact native/model prefix checks and strict ordinary-retained size controls."""
import ctypes as C
import importlib.util
from pathlib import Path
import random
import unittest

from early_query import Query, HERE, abi
# Explicitly load this model: legacy query imports may prepend round108.
spec = importlib.util.spec_from_file_location('early_matrix_model', HERE/'matrix_model.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
from early_model import rewrite


def counters(value):
    return {k: v for k, v in value.items() if not k.endswith('seconds')}


class EarlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = {(sanitized, mode): Query(sanitizer=sanitized, early_mode=mode)
                       for sanitized in (False, True) for mode in (0, 1)}

    def raw(self, q, n, rows, degree, multiplier, **limits):
        original = abi.InputOwner(n, len(rows), abi.anf_from_equations(rows))
        with q.layout(n, len(rows), degree, multiplier) as layout:
            self.assertIsNone(layout.reason)
            stats = q.lib.macaulay_apply.argtypes[-1]._type_()
            handle = q.lib.macaulay_apply(layout._handle, C.byref(original.view),
                limits.get('max_work', 20000000), limits.get('max_nodes', 2000000),
                limits.get('max_rows', 4096), C.byref(stats))
            try:
                basis, proof = abi.export(q.lib.macaulay_view(handle).contents) if handle else (None, None)
                return dict(stats=counters(abi.fields(stats)), basis=basis, proof=proof,
                    reason=None if handle else q.lib.macaulay_error().decode(),
                    parity=counters(q._parity_local.stats), block=q._block_local.stats,
                    early=q._early_local.stats)
            finally:
                if handle: q.lib.macaulay_result_destroy(handle)

    def exact(self, q, n, rows, degree, multiplier, **limits):
        actual = self.raw(q, n, rows, degree, multiplier, **limits)
        expected = oracle.model(n, rows, degree, multiplier, early_mode=q.early_mode,
            parity_mode=q.parity_mode, parity_bytes=q.parity_bytes, block_bits=q.block_bits,
            table_bytes=q.table_bytes, **limits)
        self.assertEqual(actual, expected)
        return actual

    def test_random_matrices_and_independent_proof_checks(self):
        rng = random.Random(1120001)
        selections = 0
        for sanitized in (False, True):
            for n in range(1, 8):
                for _ in range(10):
                    rows = [sorted({rng.randrange(1 << n) for _ in range(rng.randrange(12))})
                            for _ in range(rng.randrange(n+3))]
                    old = self.exact(self.queries[sanitized, 0], n, rows, n, min(n, 2))
                    new = self.exact(self.queries[sanitized, 1], n, rows, n, min(n, 2))
                    self.assertEqual(new['basis'], old['basis'])
                    for result in (old, new):
                        if result['proof'] is not None:
                            checked = abi.python_verify(n, rows, result['basis'], result['proof'],
                                max_work=10000000, max_retained_terms=10000000)
                            self.assertNotEqual(checked['status'], 'checker-failure')
                    if new['early']['bound_selected']:
                        selections += 1
                        raw = oracle.raw_model(n, rows, n, min(n, 2), minimal=True, block=True)
                        self.assertLess(len(new['proof']['nodes']), len(raw['proof']['nodes']))
                        self.assertLessEqual(new['early']['active_nodes'], len(raw['proof']['nodes']))
                        self.assertEqual(new['early']['prune_visits'], 0)
        self.assertGreater(selections, 0)

    def test_every_small_budget_prefix(self):
        rows = [[0, 1, 3], [2, 3]]
        for q in self.queries.values():
            full = self.exact(q, 2, rows, 2, 1)
            for cap in range(full['stats']['work']+2):
                value = self.exact(q, 2, rows, 2, 1, max_work=cap)
                self.assertEqual(value['stats']['status'] == 0, cap >= full['stats']['work'])
            for cap in range(1, full['stats']['nodes']+2):
                self.exact(q, 2, rows, 2, 1, max_nodes=cap)
            for cap in range(1, full['stats']['rows']+2):
                self.exact(q, 2, rows, 2, 1, max_rows=cap)

    def test_byte_and_shape_fallbacks(self):
        for sanitized in (False, True):
            for cap in (0, 1, 31, 32, 64, 10000):
                q = Query(sanitizer=sanitized, parity_bytes=cap)
                for rows in ([], [[]], [[0]], [[1]]*65, [[0, 1], [2]]):
                    self.exact(q, 2, rows, 2, 1)
            q = Query(sanitizer=sanitized, parity_mode=0)
            self.exact(q, 2, [[1], [2]], 2, 1)
            for n in (32, 63, 64):
                self.exact(self.queries[sanitized, 1], n, [[1 << (n-1)], [0, 1]], 1, 1)

    def test_lower_bound_rejects_raw_graph_size_shortcut(self):
        # The raw graph has unused nodes, but ordinary pruning retains one.
        # A one-node "compression" is not a strict improvement.
        proof = dict(version=1, nvars=2, order='grevlex-x0-first',
            nodes=[['input', 0], ['input', 1], ['xor', 0, 1]], outputs=[0])
        early = dict.fromkeys(oracle.EARLY_FIELDS, 0)
        early.update(mode=1, attempted=1)
        result = rewrite(proof, 2, early_stats=early)
        self.assertEqual(early['active_nodes'], 1)
        self.assertEqual(early['bound_fallback'], 1)
        self.assertEqual(result['stats']['selected'], 0)
        self.assertIs(result['proof'], proof)

    def test_leased_query_requires_original_input_certification(self):
        from proof_reader import decode
        for q in self.queries.values():
            rows = [[1, 6], [2, 5]]
            mapping = abi.anf_from_equations(rows)
            with q.layout(3, 2, 2, 0) as layout:
                with q.workspace(3, 2, list(mapping)).borrow_mapping(mapping) as packed:
                    result = q.compute(packed, layout=layout, export_proof=True)
            self.assertTrue(result['verified'])
            self.assertEqual(len(result['attempts']), 2)
            self.assertTrue(abi.python_verify(3, rows, result['basis'], decode(result['proof'].serialized()))['verified'])
            self.assertEqual(result['work'], sum(a['stats']['work'] for a in result['attempts']))


if __name__ == '__main__':
    unittest.main()
