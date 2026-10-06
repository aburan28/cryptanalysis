"""Trace parity is stronger than basis parity for these representation changes."""
from concurrent.futures import ThreadPoolExecutor
import random
import sys
import unittest

from query import HERE, load, anf_from_equations
sys.path.insert(0, str(HERE.parent / 'round5'))
from algebraic_certificate import verify
sys.path.insert(0, str(HERE.parent.parent / 'pdp-scaling'))
from boolean_basis import certify_boolean_basis


def signature(result):
    return {key: result.get(key) for key in ('status', 'verified', 'reason', 'basis', 'proof')} | {
        'counters': {k: v for k, v in result['producer_stats'].items() if not k.endswith('_seconds')}}


class ReductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queries = {(variant, sanitized): load(variant, sanitizer=sanitized)
                       for variant in ('baseline', 'pivots', 'ordered', 'combined')
                       for sanitized in (False, True)}

    def compare(self, n, equations, **options):
        anf = anf_from_equations(equations)
        expected = None
        for label, query in self.queries.items():
            result = query.compute(n, len(equations), anf, export_proof=True, **options)
            if expected is None:
                expected = result
                if result['verified']:
                    self.assertTrue(verify(n, equations, result['basis'], result['proof'])['verified'])
                    if n <= 10:
                        self.assertTrue(certify_boolean_basis(n, equations, result['basis'])['verified'])
            else:
                self.assertEqual(signature(result), signature(expected), label)
        return expected

    def test_random_traces_and_independent_oracles(self):
        rng = random.Random(2026092516)
        counts = {'verified': 0, 'inconclusive': 0}
        for n in range(1, 9):
            for _ in range(12):
                equations = [[rng.randrange(1 << n) for _ in range(rng.randrange(1, 9))]
                             for _ in range(rng.randrange(1, n + 2))]
                result = self.compare(n, equations)
                self.assertIn(result['status'], ('gb', 'inconclusive'))
                counts['verified' if result['verified'] else 'inconclusive'] += 1
        print('random trace controls:', counts)

    def test_boolean_cancellation_zero_unit_and_wide_masks(self):
        for n in (3, 21, 32, 63, 64):
            high = 1 << (n - 1)
            for equations in ([], [[]], [[0]], [[3, 0]], [[3, 1], [6, 2]],
                              [[high | 1, high, 1, 0], [high, 0]],
                              [[3, 3, 1, 0], [1, 0]],
                              [[3 << i, 0] for i in range(0, n - 1, 2)]):
                self.assertTrue(self.compare(n, equations)['verified'])

    def test_budget_boundaries_and_reuse(self):
        equations = [[3, 4, 0], [5, 8, 0], [10, 1], [12, 2]]
        for work in (0, 1, 10, 50, 100, 200, 1000, 10000):
            self.compare(4, equations, max_work=work)
        for nodes in (1, 2, 5, 10, 30):
            self.compare(4, equations, max_nodes=nodes)
        for rows in (1, 2, 3, 8):
            self.compare(4, equations, max_rows=rows, batch=1)
        for batch in (1, 2, 5, 64):
            self.compare(4, equations, batch=batch)
        self.assertTrue(self.compare(4, equations)['verified'])

    def test_call_local_numeric_state(self):
        def task(i):
            query = self.queries[list(self.queries)[i % len(self.queries)]]
            n = (5, 21, 32, 64)[i % 4]
            equations = [[3, i & 1], [1 << (n - 1), (i >> 1) & 1]]
            # The repeated constant entries deliberately use parity semantics.
            anf = anf_from_equations(equations)
            first = query.compute(n, 2, anf, export_proof=True)
            self.assertTrue(first['verified'], first)
            query.compute(n, 2, anf, max_work=0)
            second = query.compute(n, 2, anf, export_proof=True)
            self.assertEqual(signature(first), signature(second))
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(task, range(32)))


if __name__ == '__main__':
    unittest.main()
