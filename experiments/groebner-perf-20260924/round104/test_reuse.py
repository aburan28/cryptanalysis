"""Exact semantics, physical ownership, budget boundaries and portable fallback."""
from concurrent.futures import ThreadPoolExecutor
import copy
import ctypes as C
import random
import subprocess
import sys
import unittest

from query import Query, HERE, abi, LiveStats, DenseStats, ReuseStats
from proof_reader import decode
from capture import OwnedProof
from ownership import ownership
from audit import trace


class ReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = [Query(sanitizer=s, arm='matrix-packed') for s in (False, True)]

    def produce(self, q, n, rows):
        owner = abi.InputOwner(n, len(rows), abi.anf_from_equations(rows))
        with q.workspace(n, len(rows), list(owner.anf)).borrow_mapping(owner.anf) as lease:
            result = q.compute(lease, max_work=10000000, max_check_work=10000000, export_proof=True)
        self.assertTrue(result['verified'], result)
        proof = result['proof']
        if isinstance(proof, OwnedProof): proof = decode(proof.serialized())
        return owner, result['basis'], proof

    def check(self, q, original, basis, proof, *, enabled=1, old=False, work=10000000,
              terms=10000000, byte_limit=134217728, policy=2, mode=1, schedule=1):
        owner = abi.ProofOwner(original.view.nvars, basis, proof)
        stats, live, dense, reuse = abi.CheckStats(), LiveStats(), DenseStats(), ReuseStats()
        args = [C.byref(original.view), C.byref(owner.view), work, terms, schedule,
                policy, mode, byte_limit]
        if old:
            code = q.dense.check_packed_dense(*args, C.byref(stats), C.byref(live), C.byref(dense))
        else:
            code = q.reuse.check_packed_reuse(*args, enabled, C.byref(stats), C.byref(live),
                                            C.byref(dense), C.byref(reuse))
        return code, abi.fields(stats), abi.fields(live), abi.fields(dense), abi.fields(reuse)

    def equality(self, q, original, basis, proof, **options):
        old = self.check(q, original, basis, proof, old=True, **options)
        disabled = self.check(q, original, basis, proof, enabled=0, **options)
        current = self.check(q, original, basis, proof, **options)
        self.assertEqual(trace(old[:4]), trace(disabled[:4]))
        self.assertEqual(trace(old[:3]), trace(current[:3]))
        self.assertEqual(old[0], 0)
        self.assertTrue(abi.python_verify(original.view.nvars,
            original.equations(), basis, proof,
            max_work=10000000, max_retained_terms=10000000)['verified'])
        for flag, result in ((False, disabled), (True, current)):
            dense, stats = result[3:]
            if not dense['selected']:
                self.assertEqual(stats, dict(enabled=int(flag), checks=0, transfers=0,
                    left_transfers=0, right_transfers=0, payload_allocations=0, payload_releases=0))
                continue
            predicted = ownership(proof, enabled=flag, policy=options.get('policy', 2))
            peak = predicted.pop('peak_buffers')
            self.assertEqual(stats, predicted)
            self.assertEqual(dense['peak_bytes'], dense['metadata_bytes']+peak*dense['words_per_value']*8)
            self.assertEqual(dense['created_values'], stats['payload_allocations']+stats['transfers'])
            self.assertEqual(dense['live_bytes'], 0)
        self.assertLessEqual(current[3]['peak_bytes'], old[3]['peak_bytes'])
        return current

    def test_random_exact_ideals_all_retention_policies_and_schedules(self):
        rng = random.Random(1040001)
        for q in self.queries:
            for n in range(1, 7):
                for _ in range(5):
                    rows = [sorted(set(rng.randrange(1 << n) for _ in range(rng.randrange(7))))
                            for _ in range(rng.randrange(n+2))]
                    original, basis, proof = self.produce(q, n, rows)
                    for policy in (0, 1, 2):
                        for schedule in (0, 1):
                            self.equality(q, original, basis, proof, policy=policy, schedule=schedule)

    def test_left_right_transfer_output_pins_aliases_and_boolean_cancellation(self):
        for q in self.queries:
            rows = [[1], [2], [0, 1], []]
            # The contradictory pair x and 1+x gives the reduced basis {1}.
            original, basis, proof = self.produce(q, 2, rows)
            for kind in ('left', 'right', 'alias', 'zero-multiply', 'empty-input'):
                extended = copy.deepcopy(proof); i = len(extended['nodes'])
                if kind == 'left':
                    extended['nodes'] += [['input', 0], ['input', 1], ['xor', i, i+1]]
                elif kind == 'right':
                    pinned = extended['outputs'][0]
                    extended['nodes'] += [['input', 1], ['xor', pinned, i]]
                elif kind == 'alias':
                    extended['nodes'] += [['input', 0], ['xor', i, i]]
                elif kind == 'zero-multiply':
                    extended['nodes'] += [['input', 2], ['mul', i, 1], ['input', 1], ['xor', i+1, i+2]]
                else:
                    extended['nodes'] += [['input', 3], ['input', 1], ['xor', i, i+1]]
                result = self.equality(q, original, basis, extended)
                if kind == 'left': self.assertGreater(result[4]['left_transfers'], 0)
                if kind == 'right': self.assertGreater(result[4]['right_transfers'], 0)
            # Multiple output pins affect ownership even though repeated basis
            # rows would be rejected by the mathematical checker.
            planned = ownership(dict(nodes=[['input', 0], ['input', 1], ['xor', 0, 1]], outputs=[0, 0, 2]))
            self.assertEqual((planned['left_transfers'], planned['right_transfers']), (0, 1))

    def test_every_small_work_and_term_budget_preserves_reference_outcomes(self):
        for q in self.queries:
            original, basis, proof = self.produce(q, 2, [[1], [2]])
            i = len(proof['nodes'])
            proof['nodes'] += [['input', 0], ['input', 1], ['xor', i, i+1]]
            full = self.check(q, original, basis, proof)
            self.assertEqual(full[0], 0)
            for budget in range(full[1]['work']+2):
                old = self.check(q, original, basis, proof, old=True, work=budget)
                new = self.check(q, original, basis, proof, work=budget)
                self.assertEqual(trace(old[:3]), trace(new[:3]))
                self.assertLessEqual(new[1]['work'], budget)
                self.assertEqual(new[0] == 0, budget >= full[1]['work'])
            for policy in (0, 1, 2):
                for budget in range(full[1]['retained_terms']+2):
                    old = self.check(q, original, basis, proof, old=True, terms=budget, policy=policy)
                    new = self.check(q, original, basis, proof, terms=budget, policy=policy)
                    self.assertEqual(trace(old[:3]), trace(new[:3]))
            self.equality(q, original, basis, proof)

    def test_exact_physical_byte_boundary_and_recovery(self):
        for q in self.queries:
            original = abi.InputOwner(2, 2, abi.anf_from_equations([[1], [2]]))
            proof = dict(version=1, nvars=2, order='grevlex-x0-first',
                nodes=[['input', 0], ['input', 1], ['input', 0], ['input', 1], ['xor', 2, 3]], outputs=[0, 1])
            basis = [[1], [2]]
            full = self.equality(q, original, basis, proof)
            old = self.check(q, original, basis, proof, old=True)
            peak = full[3]['peak_bytes']
            self.assertLess(peak, old[3]['peak_bytes'])
            for limit in (0, 1, full[3]['metadata_bytes']-1, peak-1, peak, old[3]['peak_bytes']-1, old[3]['peak_bytes']):
                result = self.check(q, original, basis, proof, byte_limit=limit)
                self.assertLessEqual(result[3]['peak_bytes'], limit)
                self.assertEqual(result[0] == 0, limit >= peak)
                self.equality(q, original, basis, proof)

    def test_malformed_nodes_outputs_basis_and_modes_rejected(self):
        for q in self.queries:
            original, output, source = self.produce(q, 2, [[1]])
            for kind in ('input', 'mul-forward', 'mul-mask', 'xor-forward', 'output', 'basis'):
                proof, basis = copy.deepcopy(source), copy.deepcopy(output)
                i = len(proof['nodes'])
                if kind == 'input': proof['nodes'].append(['input', 1])
                elif kind == 'mul-forward': proof['nodes'].append(['mul', i, 0])
                elif kind == 'mul-mask': proof['nodes'].append(['mul', 0, 4])
                elif kind == 'xor-forward': proof['nodes'].append(['xor', 0, i])
                elif kind == 'output': proof['outputs'][0] = i
                else: basis[0].append(0)
                self.assertEqual(self.check(q, original, basis, proof)[0], 1, kind)
            for options in ({'enabled': 2}, {'mode': 2}, {'policy': 3}, {'schedule': 2}):
                self.assertEqual(self.check(q, original, output, source, **options)[0], 1)
            self.equality(q, original, output, source)

    def test_word_boundaries_large_ring_fallback_and_equation_limbs(self):
        for q in self.queries:
            for n, rows in ((6, [[32, 0]]), (7, [[64, 0]]), (12, [[2048, 0]]),
                    (13, [[4096, 0]]), (32, [[1 << 31, 0]]), (64, [[1 << 63, 0]]),
                    (2, [[1]]*65), (2, [[2, 0]]*128), (2, []), (2, [[]])):
                original, basis, proof = self.produce(q, n, rows)
                self.equality(q, original, basis, proof)
                self.equality(q, original, basis, proof, mode=0)

    def test_changed_coefficients_concurrent_calls_and_owned_proof_lifetime(self):
        for sanitizer in (False, True):
            q = Query(sanitizer=sanitizer, arm='matrix-reuse')
            with q.layout(4, 2, 2, 1) as layout:
                def call(i):
                    rows = [[3]+([0] if i & 1 else []), [12]+([0] if i & 2 else [])]
                    anf = abi.anf_from_equations(rows)
                    with q.workspace(4, 2, layout.support).borrow_mapping(anf) as lease:
                        result = q.compute(lease, layout=layout, max_work=10000000,
                                           max_check_work=10000000, export_proof=True)
                    self.assertTrue(result['verified'], result)
                    proof = decode(result['proof'].serialized())
                    self.assertTrue(abi.python_verify(4, rows, result['basis'], proof,
                        max_work=10000000, max_retained_terms=10000000)['verified'])
                    expected = ownership(proof); expected.pop('peak_buffers')
                    self.assertEqual(result['certificate']['reuse'], expected)
                    return result['proof'].serialized(), trace(result['certificate'])
                reference = [call(i) for i in range(8)]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    self.assertEqual(list(pool.map(call, range(8))), reference)
            self.assertTrue(decode(reference[0][0]))

    def test_import_scope(self):
        for order in ('query,audit', 'audit,query'):
            script = f'''import sys, pathlib, importlib.util
sys.path.insert(0,{str(HERE)!r})
before=sys.path[:]
import {order}
assert sys.path==before
for name in ('common','panel','worker','capture','proof_reader','ownership'):
    assert pathlib.Path(importlib.util.find_spec(name).origin).parent==pathlib.Path({str(HERE)!r})
'''
            subprocess.run([sys.executable, '-c', script], check=True)


if __name__ == '__main__':
    unittest.main()
