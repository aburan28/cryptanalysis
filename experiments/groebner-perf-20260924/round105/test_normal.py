"""Exact membership, incomplete bases, resource boundaries and fresh-query scope."""
from concurrent.futures import ThreadPoolExecutor
import copy
import ctypes as C
import random
import subprocess
import sys
import unittest

from query import Query, HERE, abi, LiveStats, DenseStats, ReuseStats, NormalStats
from capture import OwnedProof
from proof_reader import decode
from normal_model import model, reference
from audit import trace


class NormalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = [Query(sanitizer=s, arm='f4-reuse') for s in (False, True)]

    def produce(self, q, n, rows):
        original = abi.InputOwner(n, len(rows), abi.anf_from_equations(rows))
        with q.workspace(n, len(rows), list(original.anf)).borrow_mapping(original.anf) as lease:
            result = q.compute(lease, max_work=10000000, max_check_work=10000000, export_proof=True)
        self.assertTrue(result['verified'], result)
        proof = result['proof']
        if isinstance(proof, OwnedProof):
            proof = decode(proof.serialized())
        return original, result['basis'], proof

    def check(self, q, original, basis, proof, *, mode=2, old=False, work=10000000,
              terms=10000000, map_bytes=1048576, policy=2, schedule=1):
        owner = abi.ProofOwner(original.view.nvars, basis, proof)
        stats, live, dense, reuse = abi.CheckStats(), LiveStats(), DenseStats(), ReuseStats()
        normal = NormalStats()
        args = [C.byref(original.view), C.byref(owner.view), work, terms, schedule,
                policy, 1, 134217728, 1]
        if old:
            code = q.reuse.check_packed_reuse(*args, C.byref(stats), C.byref(live),
                                             C.byref(dense), C.byref(reuse))
        else:
            code = q.normal.check_packed_normal(*args, mode, map_bytes, C.byref(normal),
                C.byref(stats), C.byref(live), C.byref(dense), C.byref(reuse))
        return code, abi.fields(stats), abi.fields(live), abi.fields(dense), abi.fields(reuse), abi.fields(normal)

    def equality(self, q, original, basis, proof, **options):
        old = self.check(q, original, basis, proof, old=True, **options)
        disabled = self.check(q, original, basis, proof, **{**options, 'mode': 0})
        current = self.check(q, original, basis, proof, **options)
        self.assertEqual(trace(old[:5]), trace(disabled[:5]))
        self.assertEqual((old[0], current[0]), (0, 0))
        self.assertEqual(old[2:5], current[2:5])
        expected, values = model(original.view.nvars, original.equations(), basis,
                                mode=options.get('mode', 2), byte_limit=options.get('map_bytes', 1048576))
        self.assertEqual(current[5], expected)
        if values is not None:
            self.assertFalse(any(values))
        direct = reference(original.view.nvars, original.equations(), basis)
        self.assertFalse(any(direct['results']))
        selected = expected['selected']
        self.assertEqual(current[1]['work'], old[1]['work']+expected['work']-selected*direct['work'])
        self.assertEqual(current[1]['reduction_steps'], old[1]['reduction_steps']-selected*direct['reduction_steps'])
        self.assertTrue(abi.python_verify(original.view.nvars, original.equations(), basis, proof,
            max_work=10000000, max_retained_terms=10000000)['verified'])
        return current

    def test_random_exact_ideals_policies_and_phase_schedules(self):
        rng = random.Random(1050001)
        for q in self.queries:
            for n in range(1, 7):
                for _ in range(5):
                    rows = [sorted(set(rng.randrange(1 << n) for _ in range(rng.randrange(7))))
                            for _ in range(rng.randrange(n+2))]
                    original, basis, proof = self.produce(q, n, rows)
                    for policy in (0, 1, 2):
                        for schedule in (0, 1):
                            self.equality(q, original, basis, proof, policy=policy, schedule=schedule)

    def test_automatic_density_guard_and_exact_map_byte_boundary(self):
        for q in self.queries:
            for rows, selected in (([[1], [2]], 0), ([[1], [2]]*4, 1)):
                original, basis, proof = self.produce(q, 2, rows)
                result = self.equality(q, original, basis, proof, mode=1)
                self.assertEqual(result[5]['selected'], selected)
                for cap in (0, 1, 31, 32, 33):
                    result = self.equality(q, original, basis, proof, mode=2, map_bytes=cap)
                    self.assertEqual(result[5]['selected'], int(cap >= 32))
                    self.assertEqual(result[5]['fallback_bytes'], int(cap < 32))
                    self.assertLessEqual(result[5]['peak_bytes'], cap)

    def test_dimension_word_boundary_and_large_ring_fallback(self):
        for q in self.queries:
            for n, rows, selected in ((6, [], 1), (7, [], 0), (7, [[64]], 1),
                    (8, [[128]], 0), (12, [[1 << i] for i in range(12)], 1),
                    (13, [[4096]], 0), (32, [[1 << 31, 0]], 0), (64, [[1 << 63, 0]], 0)):
                original, basis, proof = self.produce(q, n, rows)
                result = self.equality(q, original, basis, proof)
                self.assertEqual(result[5]['selected'], selected)
                self.assertEqual(result[5]['fallback_large_ring'], int(n > 12))
                if n in (7, 8) and not selected:
                    self.assertEqual(result[5]['dimension'], 65)
                    self.assertEqual(result[5]['fallback_dimension'], 1)

    def test_incomplete_basis_and_forged_derivations_still_rejected(self):
        for q in self.queries:
            # Both generators reduce to zero, but their S-pair does not.
            rows = [[1, 3], [4, 5]]
            original = abi.InputOwner(3, 2, abi.anf_from_equations(rows))
            proof = dict(version=1, nvars=3, order='grevlex-x0-first',
                         nodes=[['input', 0], ['input', 1]], outputs=[0, 1])
            for mode in (0, 1, 2):
                self.assertEqual(self.check(q, original, rows, proof, mode=mode)[0], 1)
            original, basis, proof = self.produce(q, 2, [[1]])
            for kind in ('wrong-basis', 'input', 'mul-forward', 'mul-mask', 'xor-forward', 'output'):
                bad, output = copy.deepcopy(proof), copy.deepcopy(basis)
                count = len(bad['nodes'])
                if kind == 'wrong-basis': output = [[0]]
                elif kind == 'input': bad['nodes'].append(['input', 1])
                elif kind == 'mul-forward': bad['nodes'].append(['mul', count, 0])
                elif kind == 'mul-mask': bad['nodes'].append(['mul', 0, 4])
                elif kind == 'xor-forward': bad['nodes'].append(['xor', 0, count])
                else: bad['outputs'][0] = count
                self.assertEqual(self.check(q, original, output, bad)[0], 1, kind)
            self.assertEqual(self.check(q, original, basis, proof, mode=3)[0], 1)
            self.equality(q, original, basis, proof)

    def test_every_small_work_budget_term_budget_and_recovery(self):
        for q in self.queries:
            original, basis, proof = self.produce(q, 2, [[1], [2]])
            full = self.check(q, original, basis, proof)
            for limit in range(full[1]['work']+2):
                result = self.check(q, original, basis, proof, work=limit)
                self.assertLessEqual(result[1]['work'], limit)
                self.assertLessEqual(result[5]['work'], result[1]['work'])
                self.assertEqual(result[0] == 0, limit >= full[1]['work'])
            for policy in (0, 1, 2):
                for limit in range(full[1]['retained_terms']+2):
                    old = self.check(q, original, basis, proof, old=True, terms=limit, policy=policy)
                    new = self.check(q, original, basis, proof, terms=limit, policy=policy)
                    self.assertEqual(old[0], new[0])
            self.equality(q, original, basis, proof)

    def test_empty_inconsistent_repeated_inputs_and_equation_limbs(self):
        for q in self.queries:
            for rows in ([], [[]], [[1], [0, 1]], [[1]]*65, [[0, 2]]*128,
                         [[0, 1, 2, 3]]*32):
                original, basis, proof = self.produce(q, 2, rows)
                self.equality(q, original, basis, proof)

    def test_changed_coefficients_concurrency_and_independent_proof_ownership(self):
        for sanitized in (False, True):
            q = Query(sanitizer=sanitized, arm='matrix-quotient')
            with q.layout(4, 32, 1, 1) as layout:
                def call(seed):
                    rows = [[1 << bit]+([0] if seed >> bit & 1 else []) for bit in range(4)]*8
                    anf = abi.anf_from_equations(rows)
                    with q.workspace(4, 32, layout.support).borrow_mapping(anf) as lease:
                        result = q.compute(lease, layout=layout, max_work=10000000,
                                           max_check_work=10000000, export_proof=True)
                    self.assertTrue(result['verified'], result)
                    self.assertEqual(result['certificate']['normal']['selected'], 1)
                    proof = decode(result['proof'].serialized())
                    self.assertTrue(abi.python_verify(4, rows, result['basis'], proof,
                        max_work=10000000, max_retained_terms=10000000)['verified'])
                    self.assertEqual(result['certificate']['normal'], model(4, rows, result['basis'])[0])
                    return result['proof'].serialized(), trace(result['certificate'])
                expected = [call(i) for i in range(8)]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    self.assertEqual(list(pool.map(call, range(8))), expected)
            self.assertTrue(decode(expected[0][0]))

    def test_import_scope(self):
        for order in ('query,audit', 'audit,query'):
            script = f'''import sys, pathlib, importlib.util
sys.path.insert(0,{str(HERE)!r})
before=sys.path[:]
import {order}
assert sys.path==before
for name in ('common','panel','worker','capture','proof_reader','ownership','normal_model'):
    assert pathlib.Path(importlib.util.find_spec(name).origin).parent==pathlib.Path({str(HERE)!r})
'''
            subprocess.run([sys.executable, '-c', script], check=True)


if __name__ == '__main__':
    unittest.main()
