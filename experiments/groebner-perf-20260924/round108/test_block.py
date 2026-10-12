"""Exact RREF outputs, derivations, charged prefixes and native ownership."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as C
import random
import subprocess
import sys
import unittest

from query import Query, HERE, abi
from matrix_model import model
from audit import trace
from capture import OwnedProof
from proof_reader import decode


class BlockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = {(s, m): Query(sanitizer=s,
            arm='matrix-block4' if m else 'matrix-parity')
            for s in (False, True) for m in (False, True)}

    def raw(self, q, n, rows, degree, multiplier, *, work=20000000,
            nodes=2000000, max_rows=4096, layout=None, masks=None):
        original = abi.InputOwner(n, len(rows), abi.anf_from_equations(rows))
        if masks is not None:
            original = abi.InputOwner(n, len(rows), {m: original.anf.get(m, 0) for m in masks})
        own = layout is None
        layout = layout or q.layout(n, len(rows), degree, multiplier)
        self.assertIsNone(layout.reason)
        stats_type = q.lib.macaulay_apply.argtypes[-1]._type_
        stats = stats_type()
        handle = q.lib.macaulay_apply(layout._handle, C.byref(original.view), work,
                                      nodes, max_rows, C.byref(stats))
        try:
            if handle:
                view = q.lib.macaulay_view(handle).contents
                basis, proof = abi.export(view)
                reason = None
            else:
                basis, proof = None, None
                reason = q.lib.macaulay_error().decode()
            result=dict(stats=trace(abi.fields(stats)), basis=basis, proof=proof, reason=reason)
            result['parity']=trace(q._parity_local.stats)
            if q.block_arm=='matrix-block4':result['block']=trace(q._block_local.stats)
            return result
        finally:
            if handle:
                q.lib.macaulay_result_destroy(handle)
            if own:
                layout.close()

    def exact(self, s, m, n, rows, degree, multiplier, **kwargs):
        actual = self.raw(self.queries[s, m], n, rows, degree, multiplier, **kwargs)
        options = dict(minimal=True, parity=True, block=m, max_work=kwargs.get('work', 20000000),
            max_nodes=kwargs.get('nodes', 2000000), max_rows=kwargs.get('max_rows', 4096),
            packed_masks=kwargs.get('masks'))
        expected = model(n, rows, degree, multiplier, **options)
        self.assertEqual(actual, expected)
        return actual

    def test_random_echelon_outputs_and_exact_derivation_graphs(self):
        rng = random.Random(1080001)
        for s in (False, True):
            for n in range(1, 8):
                for _ in range(10):
                    rows = [sorted({rng.randrange(1 << n) for _ in range(rng.randrange(12))})
                            for _ in range(rng.randrange(n+3))]
                    old = self.exact(s, False, n, rows, n, min(2, n))
                    new = self.exact(s, True, n, rows, n, min(2, n))
                    self.assertEqual(old['basis'], new['basis'])
                    self.assertEqual(old['stats']['pivots'], new['stats']['pivots'])
                    for result in (old, new):
                        cert = abi.python_verify(n, rows, result['basis'], result['proof'],
                            max_work=10000000, max_retained_terms=10000000)
                        # A bounded matrix need not be complete. Neither arm may
                        # claim completion based on row reduction alone.
                        self.assertNotEqual(cert['status'], 'checker-failure')
                    self.assertEqual(abi.python_verify(n, rows, old['basis'], old['proof'])['verified'],
                                     abi.python_verify(n, rows, new['basis'], new['proof'])['verified'])

    def test_every_small_work_node_and_row_budget_prefix(self):
        rows = [[0, 1, 3], [2, 3]]
        for s in (False, True):
            for m in (False, True):
                full = self.exact(s, m, 2, rows, 2, 1)
                for limit in range(full['stats']['work']+2):
                    r = self.exact(s, m, 2, rows, 2, 1, work=limit)
                    self.assertEqual(r['stats']['status'] == 0, limit >= full['stats']['work'])
                for limit in range(1, full['stats']['nodes']+2):
                    self.exact(s, m, 2, rows, 2, 1, nodes=limit)
                for limit in range(1, full['stats']['rows']+2):
                    self.exact(s, m, 2, rows, 2, 1, max_rows=limit)

    def test_empty_constant_repeated_and_multiple_coefficient_limbs(self):
        for s in (False, True):
            for m in (False, True):
                for rows in ([], [[]], [[0]], [[0, 1], [1]], [[1, 1, 2]],
                             [[1]]*65, [[0, 2]]*128):
                    self.exact(s, m, 2, rows, 2, 1)
                self.exact(s, m, 3, [[1], [2]], 2, 1, masks=list(range(7)))

    def test_large_variable_masks_and_word_boundaries(self):
        for s in (False, True):
            for m in (False, True):
                for n in (6, 7, 12, 32, 63, 64):
                    self.exact(s, m, n, [[0, 1 << (n-1)], [1]], 1, 1)

    def test_layout_ownership_and_closed_handles(self):
        for s in (False, True):
            old, new = self.queries[s, False], self.queries[s, True]
            with old.layout(2, 1, 1, 1) as layout:
                anf = abi.anf_from_equations([[1]])
                with new.workspace(2, 1, list(anf)).borrow_mapping(anf) as lease:
                    with self.assertRaises(ValueError):
                        new.compute(lease, layout=layout)
            with old.workspace(2, 1, list(anf)).borrow_mapping(anf) as lease:
                with self.assertRaises(RuntimeError):
                    old.compute(lease, layout=layout)

    def test_fresh_coefficients_fallback_and_owned_proof_lifetime(self):
        for s in (False, True):
            q = self.queries[s, True]
            with q.layout(4, 4, 1, 1) as layout:
                def call(seed):
                    rows = [[1 << bit]+([0] if seed >> bit & 1 else []) for bit in range(4)]
                    anf = abi.anf_from_equations(rows)
                    with q.workspace(4, 4, layout.support).borrow_mapping(anf) as lease:
                        result = q.compute(lease, layout=layout, max_work=10000000,
                            max_check_work=10000000, export_proof=True)
                    self.assertTrue(result['verified'], result)
                    self.assertEqual(len(result['attempts']), 1)
                    self.assertIsInstance(result['proof'], OwnedProof)
                    proof = decode(result['proof'].serialized())
                    self.assertTrue(abi.python_verify(4, rows, result['basis'], proof)['verified'])
                    return result['proof'].serialized(), trace(result['certificate'])
                expected = [call(i) for i in range(8)]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    self.assertEqual(list(pool.map(call, range(8))), expected)
                anf = abi.anf_from_equations([[1], [2], [4], [8]])
                with q.workspace(4, 4, layout.support).borrow_mapping(anf) as lease:
                    fallback = q.compute(lease, layout=layout, matrix_cap=1,
                                         max_work=1000000, export_proof=True)
                self.assertTrue(fallback['verified'], fallback)
                self.assertEqual(len(fallback['attempts']), 2)
                self.assertEqual(fallback['work'], sum(a['stats']['work'] for a in fallback['attempts']))
            self.assertTrue(decode(expected[0][0]))

    def test_incomplete_candidate_cannot_bypass_checker(self):
        for s in (False, True):
            q = self.queries[s, True]
            # No monomial multiples: ordinary echelon form is insufficient.
            rows = [[1, 3], [4, 5]]
            anf = abi.anf_from_equations(rows)
            with q.layout(3, 2, 2, 0) as layout:
                with q.workspace(3, 2, list(anf)).borrow_mapping(anf) as lease:
                    r = q.compute(lease, layout=layout, fallback=False, export_proof=True)
            self.assertFalse(r['verified'])
            self.assertNotIn('basis', r)

    def test_forged_compressed_proofs_remain_rejected(self):
        import copy
        for sanitized in (False,True):
            q=self.queries[sanitized,True]
            rows=[[0,1,3],[2,3]]
            result=self.raw(q,2,rows,2,2)
            original=abi.InputOwner(2,len(rows),abi.anf_from_equations(rows))
            for kind in ('basis','input','output','forward-xor'):
                basis,proof=copy.deepcopy(result['basis']),copy.deepcopy(result['proof'])
                if kind=='basis':basis[0]=[0]
                elif kind=='input':proof['nodes'].append(['input',len(rows)])
                elif kind=='output':proof['outputs'][0]=len(proof['nodes'])
                else:proof['nodes'].append(['xor',len(proof['nodes']),0])
                owner=abi.ProofOwner(2,basis,proof)
                checked=q._check(original.view,owner.view,10000000,10000000)
                self.assertFalse(checked['verified'],(kind,checked))

    def test_table_budget_prefixes_and_byte_cap_boundaries(self):
        rows = [[0], [1], [2], [3], [0, 1, 2, 3]]
        for sanitized in (False, True):
            full = self.exact(sanitized, True, 2, rows, 2, 0)
            self.assertEqual(full['block']['builds'], 1)
            self.assertEqual(full['block']['combinations'], 15)
            self.assertEqual(full['block']['peak_payload_bytes'], 205)
            for limit in range(full['stats']['work']+2):
                self.exact(sanitized, True, 2, rows, 2, 0, work=limit)
            for limit in range(1, full['stats']['nodes']+2):
                self.exact(sanitized, True, 2, rows, 2, 0, nodes=limit)
            baseline = self.raw(self.queries[sanitized, False], 2, rows, 2, 0)
            for bits in (0, 4):
                for cap in (0, 4, 5, 204, 205, 206):
                    q = Query(sanitizer=sanitized, block_bits=bits, table_bytes=cap)
                    actual = self.raw(q, 2, rows, 2, 0)
                    expected = model(2, rows, 2, 0, minimal=True, parity=True,
                                     block=True, block_bits=bits, table_bytes=cap)
                    self.assertEqual(actual, expected)
                    self.assertEqual(actual['basis'], baseline['basis'])
                    self.assertLessEqual(actual['block']['peak_payload_bytes'], cap)
                    if not bits:
                        self.assertEqual(actual['stats'], baseline['stats'])
                        self.assertEqual(actual['proof'], baseline['proof'])
            for bad in (-1, 1, 3, 5, True):
                with self.assertRaises(ValueError):
                    Query(block_bits=bad)

    def test_upper_triangular_signatures_and_word_boundaries(self):
        # Nonidentity unit-triangular pivot submatrices require a lookup from
        # coefficient signature to combination; signature != combination.
        for sanitized in (False, True):
            for n, degree in ((2, 2), (6, 6), (7, 7)):
                from scalar_model import monomials
                columns = sorted(monomials(n, degree), key=lambda m: (-m.bit_count(), m))
                rows = [[c]+(columns[i+1:i+3] if i % 2 else [])
                        for i, c in enumerate(columns)]
                rows += [columns[::3], columns[1::2], columns]
                old = self.exact(sanitized, False, n, rows, degree, 0)
                new = self.exact(sanitized, True, n, rows, degree, 0)
                self.assertEqual(old['basis'], new['basis'])
                self.assertGreater(new['block']['builds'], 0)
                self.assertTrue(abi.python_verify(n, rows, new['basis'], new['proof'])['verified'])
            # Five columns leave a partial final group and missing pivot slots.
            self.exact(sanitized, True, 4, [[1], [2], [1, 2], [8]], 1, 0)

    def test_import_scope(self):
        for order in ('query,audit', 'audit,query'):
            code = f'''import sys,pathlib,importlib.util
sys.path.insert(0,{str(HERE)!r})
before=sys.path[:]
import {order}
assert sys.path==before
for name in ('common','panel','worker','capture','proof_reader','ownership','normal_model','matrix_model','parity_model','scalar_model','block_model'):
    assert pathlib.Path(importlib.util.find_spec(name).origin).parent==pathlib.Path({str(HERE)!r})
'''
            subprocess.run([sys.executable, '-c', code], check=True)


if __name__ == '__main__':
    unittest.main()
