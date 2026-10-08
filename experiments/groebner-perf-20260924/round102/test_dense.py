"""Exact arithmetic, proof rejection, budget boundaries and portable fallback."""
import copy
import ctypes as C
import random
import subprocess
import sys
import unittest

from query import Query, HERE, abi, LiveStats, DenseStats
from audit import proof_cost, producer_trace


class DenseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = [Query(sanitizer=flag) for flag in (False, True)]

    def produce(self, q, n, rows):
        original = abi.InputOwner(n, len(rows), abi.anf_from_equations(rows))
        with q.workspace(n, len(rows), list(original.anf)).borrow_mapping(original.anf) as lease:
            result = q.compute(lease, max_work=10000000, max_check_work=10000000, export_proof=True)
        self.assertTrue(result['verified'], result)
        return original, result

    def check(self, q, original, basis, proof, *, work=10000000, terms=10000000,
              byte_limit=134217728, policy=2, mode=1, schedule=1):
        owner = abi.ProofOwner(original.view.nvars, basis, proof)
        stats, live, dense = abi.CheckStats(), LiveStats(), DenseStats()
        code = q.dense.check_packed_dense(C.byref(original.view), C.byref(owner.view),
            work, terms, schedule, policy, mode, byte_limit,
            C.byref(stats), C.byref(live), C.byref(dense))
        return code, abi.fields(stats), abi.fields(live), abi.fields(dense)

    def test_import_scope(self):
        for order in ('query,audit', 'audit,query'):
            script = f'''import sys, pathlib, importlib.util
sys.path.insert(0,{str(HERE)!r})
before=sys.path[:]
import {order}
assert sys.path==before
for name in ('common','panel','worker'):
    assert pathlib.Path(importlib.util.find_spec(name).origin).parent==pathlib.Path({str(HERE)!r})
'''
            subprocess.run([sys.executable, '-c', script], check=True)

    def test_random_ideals_against_independent_python_and_hash(self):
        rng = random.Random(102001)
        for q in self.queries:
            for n in range(1, 7):
                for _ in range(8):
                    rows = [sorted(set(rng.randrange(1 << n) for _ in range(rng.randrange(7))))
                            for _ in range(rng.randrange(n+2))]
                    original, result = self.produce(q, n, rows)
                    proof, basis = result['proof'], result['basis']
                    self.assertTrue(abi.python_verify(n, rows, basis, proof,
                        max_work=10000000, max_retained_terms=10000000)['verified'])
                    for policy in (0, 1, 2):
                        for schedule in (0, 1):
                            dense = self.check(q, original, basis, proof, policy=policy, schedule=schedule)
                            sparse = self.check(q, original, basis, proof, policy=policy, mode=0, schedule=schedule)
                            self.assertEqual(dense[0], 0)
                            self.assertEqual(sparse[0], 0)
                            self.assertEqual(dense[2], sparse[2])
                            expected = proof_cost(n, rows, basis, proof)
                            self.assertEqual(dense[1]['work']-sparse[1]['work'], expected['extra_work'])
                            self.assertEqual(dense[3]['word_work'], expected['word_work'])
                            if policy:
                                self.assertEqual(dense[3]['created_values'], dense[3]['released_values'])

    def test_boolean_multiplication_cancellation_and_shared_operands(self):
        # x*(1+x)=0 in the Boolean ring; unused nodes must still be checked.
        for q in self.queries:
            rows = [[0, 1]]
            original, result = self.produce(q, 2, rows)
            proof = copy.deepcopy(result['proof'])
            start = len(proof['nodes'])
            proof['nodes'] += [['input', 0], ['mul', start, 1], ['xor', start, start],
                               ['xor', start+1, start+2]]
            code, _, live, dense = self.check(q, original, result['basis'], proof)
            self.assertEqual(code, 0)
            self.assertEqual(live['live_terms'], 0)
            self.assertEqual(dense['created_values'], len(proof['nodes']))
            self.assertEqual(dense['released_values'], len(proof['nodes']))

    def test_every_small_work_budget_and_exact_memory_boundary(self):
        for q in self.queries:
            original, result = self.produce(q, 2, [[0, 1]])
            basis, proof = result['basis'], result['proof']
            full = self.check(q, original, basis, proof)
            self.assertEqual(full[0], 0)
            for budget in range(full[1]['work']+2):
                code, stats, _, _ = self.check(q, original, basis, proof, work=budget)
                self.assertLessEqual(stats['work'], budget)
                self.assertEqual(code == 0, budget >= full[1]['work'])
            peak = full[3]['peak_bytes']
            for limit in (0, 1, peak-1, peak, peak+1):
                code, _, _, dense = self.check(q, original, basis, proof, byte_limit=limit)
                self.assertLessEqual(dense['peak_bytes'], limit)
                self.assertEqual(code == 0, limit >= peak)
            peak_terms = full[2]['peak_terms']
            self.assertEqual(self.check(q, original, basis, proof, terms=peak_terms)[0], 0)
            self.assertEqual(self.check(q, original, basis, proof, terms=peak_terms-1)[0], 2)

    def test_malformed_nodes_outputs_and_basis_are_rejected(self):
        for q in self.queries:
            original, result = self.produce(q, 2, [[1]])
            for kind in ('input', 'mul-forward', 'mul-mask', 'xor-forward', 'output', 'basis'):
                proof, basis = copy.deepcopy(result['proof']), copy.deepcopy(result['basis'])
                i = len(proof['nodes'])
                if kind == 'input': proof['nodes'].append(['input', 1])
                elif kind == 'mul-forward': proof['nodes'].append(['mul', i, 0])
                elif kind == 'mul-mask': proof['nodes'].append(['mul', 0, 4])
                elif kind == 'xor-forward': proof['nodes'].append(['xor', 0, i])
                elif kind == 'output': proof['outputs'][0] = i
                elif kind == 'basis': basis[0].append(0)
                self.assertEqual(self.check(q, original, basis, proof)[0], 1, kind)
            for options in ({'mode': 2}, {'policy': 3}, {'schedule': 2}):
                self.assertEqual(self.check(q, original, result['basis'], result['proof'], **options)[0], 1)

    def test_large_ring_fallback_word_boundaries_and_equation_limbs(self):
        for q in self.queries:
            for n, rows in ((6, [[32, 0]]), (7, [[64, 0]]), (12, [[2048, 0]]),
                            (13, [[4096, 0]]), (32, [[1 << 31, 0]]),
                            (64, [[1 << 63, 0]]), (2, [[1]]*65), (2, []), (2, [[]])):
                original, result = self.produce(q, n, rows)
                dense = self.check(q, original, result['basis'], result['proof'])
                sparse = self.check(q, original, result['basis'], result['proof'], mode=0)
                self.assertEqual(dense[0], 0)
                self.assertEqual(dense[3]['selected'], int(n <= 12))
                self.assertEqual(dense[3]['fallback_large_ring'], int(n > 12))
                if n > 12:
                    self.assertEqual({k:v for k,v in dense[1].items() if not k.endswith('seconds')},
                                     {k:v for k,v in sparse[1].items() if not k.endswith('seconds')})
                    self.assertEqual(dense[2], sparse[2])


if __name__ == '__main__':
    unittest.main()
