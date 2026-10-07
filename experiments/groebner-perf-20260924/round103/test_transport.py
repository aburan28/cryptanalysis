"""Native ownership, exact proof equality, decoder rejection and call isolation."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as C
from dataclasses import FrozenInstanceError, replace
import gc
import random
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch

import query
from query import Query, HERE, abi
from capture import OwnedProof, capture
from proof_reader import decode
from audit import trace


def encoding(n, graph, outputs, endian=0):
    """Independent test encoder; does not use capture or OwnedProof."""
    prefix = '<' if endian == 0 else '>'
    return (struct.pack('<8sBBBBIQQ', b'GBPROOF1', 1, endian, 1, 0, n, len(graph), len(outputs))
            + b''.join(struct.pack(prefix+'IIQ', *node) for node in graph)
            + b''.join(struct.pack(prefix+'I', ref) for ref in outputs))


class FormatTests(unittest.TestCase):
    def test_endianness_and_64_bit_masks(self):
        nodes = [(0, 65, 0), (1, 0, 1 << 63), (2, 0, 1)]
        expected = dict(version=1, nvars=64, order='grevlex-x0-first',
                        nodes=[['input', 65], ['mul', 0, 1 << 63], ['xor', 0, 1]], outputs=[2, 1])
        for endian in (0, 1):
            self.assertEqual(decode(encoding(64, nodes, [2, 1], endian)), expected)
            self.assertEqual(decode(encoding(1, [], [], endian))['nodes'], [])

    def test_reject_malformed_and_oversized_format(self):
        valid = encoding(2, [(0, 0, 0), (1, 0, 3), (2, 0, 1)], [2])
        bad = [valid[:n] for n in range(len(valid))] + [valid+b'\0', bytearray(valid)]
        for offset, value in ((0, 0), (8, 2), (9, 2), (10, 0), (11, 1)):
            altered = bytearray(valid); altered[offset] = value; bad.append(bytes(altered))
        for fmt, offset, value in (('I', 12, 0), ('I', 12, 65),
                                   ('Q', 16, 10000001), ('Q', 24, 1000001)):
            altered = bytearray(valid); struct.pack_into('<'+fmt, altered, offset, value)
            bad.append(bytes(altered))
        for graph, outputs in (([(0, 0, 1)], []), ([(3, 0, 0)], []),
                ([(1, 0, 0)], []), ([(0, 0, 0), (1, 1, 0)], []),
                ([(0, 0, 0), (1, 0, 4)], []), ([(0, 0, 0), (2, 0, 1)], []),
                ([(0, 0, 0), (2, 1, 0)], []), ([(0, 0, 0)], [1]), ([], [0])):
            for endian in (0, 1): bad.append(encoding(2, graph, outputs, endian))
        for data in bad:
            with self.subTest(length=len(data)):
                with self.assertRaises(ValueError): decode(data)

    def test_owned_envelope_and_raw_copy_independence(self):
        owner = abi.ProofOwner(2, [[1]], dict(version=1, nvars=2,
            order='grevlex-x0-first', nodes=[['input', 0]], outputs=[0]))
        value = capture(owner.view, abi.Node)
        saved = value.serialized()
        owner.view.graph[0].a = 99
        owner.view.outputs[0] = 99
        self.assertEqual(value.serialized(), saved)
        with self.assertRaises(FrozenInstanceError): value.graph = b''
        for change in (dict(byteorder='mixed'), dict(nvars=0), dict(nvars=True),
                dict(nodes=-1), dict(nodes=10000001), dict(outputs=1000001),
                dict(graph=b''), dict(graph=bytearray(value.graph)), dict(references=b'')):
            with self.assertRaises(ValueError): replace(value, **change).serialized()
        for field, value in (('version', 2), ('order', 0), ('reserved', 1),
                             ('nvars', 0), ('nvars', 65), ('nodes', 10000001), ('rows', 1000001)):
            view = abi.ProofView.from_buffer_copy(owner.view)
            setattr(view, field, value)
            with self.assertRaises(ValueError): capture(view, abi.Node)
        class Wrong(C.Structure):
            _fields_ = [('op', C.c_uint32), ('a', C.c_uint64), ('b', C.c_uint64)]
        with self.assertRaises(ValueError): capture(owner.view, Wrong)
        for field in ('graph', 'outputs'):
            view = abi.ProofView.from_buffer_copy(owner.view)
            setattr(view, field, type(getattr(view, field))())
            with self.assertRaises(ValueError): capture(view, abi.Node)


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pairs = [(Query(sanitizer=s, arm='matrix-list'),
                      Query(sanitizer=s, arm='matrix-packed')) for s in (False, True)]

    def call(self, q, n, rows, *, layout=None, export=True, **options):
        mapping = abi.anf_from_equations(rows)
        with q.workspace(n, len(rows), layout.support if layout and rows else list(mapping)).borrow_mapping(mapping) as lease:
            result = q.compute(lease, layout=layout, export_proof=export,
                               max_work=20000000, max_check_work=20000000, **options)
        return result

    def checked(self, n, rows, result):
        self.assertTrue(result['verified'], result)
        proof = result['proof']
        if isinstance(proof, OwnedProof): proof = decode(proof.serialized())
        self.assertTrue(abi.python_verify(n, rows, result['basis'], proof,
            max_work=20000000, max_retained_terms=20000000)['verified'])
        profile = result['materialization']
        self.assertEqual(profile['calls'], 1)
        self.assertEqual(profile['nodes'], len(proof['nodes']))
        self.assertEqual(profile['outputs'], len(proof['outputs']))
        self.assertEqual(profile['total_ns'], profile['basis_ns']+profile['proof_ns'])
        return proof

    def test_exact_random_matrix_proofs_and_independent_math(self):
        rng = random.Random(1030001)
        for n in range(1, 6):
            for _ in range(5):
                rows = [sorted(set(rng.randrange(1 << n) for _ in range(rng.randrange(7))))
                        for _ in range(rng.randrange(n+2))]
                degree = max((m.bit_count() for row in rows for m in row), default=0)
                for left, right in self.pairs:
                    values = []
                    for q in (left, right):
                        with q.layout(n, len(rows), degree, n) as layout:
                            result = self.call(q, n, rows, layout=layout, fallback=False)
                        values.append((result['basis'], self.checked(n, rows, result), trace(result['attempts'])))
                    self.assertEqual(*values)

    def test_lifetime_fresh_coefficients_fallback_and_boundaries(self):
        for left, right in self.pairs:
            for n, rows in ((2, []), (2, [[]]), (2, [[0]]), (2, [[1]]*65),
                    (7, [[64, 0]]), (12, [[2048, 0]]), (13, [[4096, 0]]),
                    (32, [[1 << 31, 0]]), (64, [[1 << 63, 0]])):
                values = []
                for q in (left, right):
                    with q.layout(n, len(rows), 1, 0) as layout:
                        result = self.call(q, n, rows, layout=layout, fallback=False)
                    gc.collect()
                    values.append((result['basis'], self.checked(n, rows, result)))
                self.assertEqual(*values)
            with right.layout(2, 1, 2, 0) as layout:
                result = self.call(right, 2, [[3, 0]], layout=layout)
                self.checked(2, [[3, 0]], result)
                self.assertEqual([a['kind'] for a in result['attempts']], ['macaulay', 'fresh-f4'])
                before = result['proof'].serialized()
                fresh = self.call(right, 2, [[1]], layout=layout)
                self.checked(2, [[1]], fresh)
                repeated = self.call(right, 2, [[3, 0]], layout=layout)
                self.assertEqual(repeated['proof'].serialized(), before)
                self.assertNotEqual(fresh['proof'].serialized(), before)

    def test_budget_failure_does_not_export_and_optional_export(self):
        for _, q in self.pairs:
            result = self.call(q, 2, [[1]], export=False)
            self.assertTrue(result['verified'])
            self.assertNotIn('proof', result)
            self.assertEqual(result['materialization']['nodes'], 0)
            with q.workspace(2, 1, [1]).borrow_mapping({1: 1}) as lease:
                with patch.object(query, 'capture', side_effect=AssertionError('must not export')):
                    result = q.compute(lease, max_work=0, export_proof=True)
            self.assertFalse(result['verified'])
            self.assertNotIn('proof', result)
            self.assertFalse(any(result['materialization'].values()))
            self.assertIsNone(query._materialization.get())

    def test_exception_frees_result_and_resets_call_state(self):
        for _, q in self.pairs:
            for matrix in (False, True):
                with q.layout(2, 1, 1, 0) as layout:
                    library = q.lib if matrix else q.base.producer
                    name = 'macaulay_result_destroy' if matrix else 'producer_destroy'
                    original = getattr(library, name)
                    freed = []
                    def release(handle):
                        freed.append(handle); original(handle)
                    with patch.object(library, name, side_effect=release):
                        with patch.object(query, 'capture', side_effect=RuntimeError('injected capture failure')):
                            with self.assertRaisesRegex(RuntimeError, 'injected capture failure'):
                                self.call(q, 2, [[1]], layout=layout if matrix else None)
                    self.assertEqual(len(freed), 1)
                    self.assertIsNone(query._materialization.get())
                    self.checked(2, [[1]], self.call(q, 2, [[1]], layout=layout if matrix else None))

    def test_concurrent_and_nested_calls_keep_separate_profiles(self):
        for _, q in self.pairs:
            def run(i):
                rows = [[1]+([0] if i & 1 else []), [2]+([0] if i & 2 else [])]
                result = self.call(q, 2, rows)
                proof = self.checked(2, rows, result)
                return result['basis'], proof, trace(result['materialization'])
            expected = [run(i) for i in range(8)]
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(list(pool.map(run, range(8))), expected)
            active = False
            inner = []
            def nested(view, node_type):
                nonlocal active
                if not active:
                    active = True
                    try: inner.append(self.call(q, 2, [[1], [2]]))
                    finally: active = False
                return capture(view, node_type)
            with patch.object(query, 'capture', side_effect=nested):
                outer = self.call(q, 2, [[1]])
            self.checked(2, [[1]], outer)
            self.assertEqual(len(inner), 1)
            self.checked(2, [[1], [2]], inner[0])
            self.assertIsNone(query._materialization.get())

    def test_import_scope(self):
        for order in ('query,audit', 'audit,query'):
            script = f'''import sys, pathlib, importlib.util
sys.path.insert(0,{str(HERE)!r})
before=sys.path[:]
import {order}
assert sys.path==before
for name in ('common','panel','worker','capture','proof_reader'):
    assert pathlib.Path(importlib.util.find_spec(name).origin).parent==pathlib.Path({str(HERE)!r})
'''
            subprocess.run([sys.executable, '-c', script], check=True)


if __name__ == '__main__':
    unittest.main()
