"""Exact Python/native composition, budgets, raw ABI rejection and lifetimes."""
import copy
import ctypes as C
from concurrent.futures import ThreadPoolExecutor
import random
import sys
import unittest

from native import HERE, Native, SeededStats, abi
sys.path.insert(0, str(HERE.parent/'round109'))
from compose import compose
from test_compose import proof, evaluate


def owner(p, equations):
    return abi.ProofOwner(p['nvars'], [sorted(row) for row in evaluate(p, equations)], p)


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.natives = [Native(False), Native(True)]

    def compare(self, seed, continuation, originals, max_work=100000, max_nodes=1000):
        a = owner(seed, originals)
        b = owner(continuation, evaluate(seed, originals)+originals)
        expected = compose(seed, continuation, len(originals), max_work=max_work, max_nodes=max_nodes)
        for native in self.natives:
            result = native.compose(a, b, len(originals), max_work, max_nodes)
            self.assertEqual(result, expected)
        return expected

    def test_random_nested_graphs(self):
        rng = random.Random(1100001)
        for _ in range(100):
            originals = [{rng.randrange(32) for _ in range(10)} for _ in range(4)]
            def graph(inputs):
                nodes = [['input', i] for i in range(inputs)]
                for _ in range(25):
                    nodes.append(['mul', rng.randrange(len(nodes)), rng.randrange(32)] if rng.randrange(2)
                        else ['xor', rng.randrange(len(nodes)), rng.randrange(len(nodes))])
                return proof(5, nodes, [rng.randrange(len(nodes)) for _ in range(3)])
            self.compare(graph(4), graph(7), originals)

    def test_every_small_composition_budget(self):
        seed = proof(2, [['input', 0], ['mul', 0, 2]], [1])
        cont = proof(2, [['input', 0], ['input', 1], ['xor', 0, 1]], [2])
        full = self.compare(seed, cont, [{0, 1}])
        for cap in range(full['stats']['work']+2):
            self.compare(seed, cont, [{0, 1}], max_work=cap)
        for cap in range(full['stats']['combined_nodes']+2):
            self.compare(seed, cont, [{0, 1}], max_nodes=cap)

    def test_empty_repeated_and_64_bit(self):
        self.compare(proof(2, [], []), proof(2, [], []), [])
        self.compare(proof(2, [['input', 0]], [0, 0]), proof(2, [['input', 1], ['mul', 0, 1]], [1, 1]), [{0, 2}])
        self.compare(proof(64, [['input', 0], ['mul', 0, 1 << 63]], [1]),
            proof(64, [['input', 0], ['mul', 0, (1 << 64)-1]], [1]), [{0, 1}])

    def test_malformed_unused_nodes_and_raw_headers(self):
        seed = proof(2, [['input', 0]], [0])
        cont = proof(2, [['input', 0]], [0])
        for native in self.natives:
            for side in (0, 1):
                for bad in (['input', 999], ['xor', 99, 0], ['mul', 0, 4]):
                    graphs = [copy.deepcopy(seed), copy.deepcopy(cont)]
                    graphs[side]['nodes'].append(bad)
                    owners = [abi.ProofOwner(2, [[0]], p) for p in graphs]
                    r = native.compose(*owners, 1)
                    self.assertEqual(r['status'], 'invalid')
                    self.assertIsNone(r['proof'])
            for field, value in [('version', 0), ('order', 0), ('reserved', 1), ('rows', 4097), ('nodes', 10000001)]:
                a, b = owner(seed, [{0}]), owner(cont, [{0}, {0}])
                setattr(a.view, field, value)
                self.assertEqual(native.compose(a, b, 1)['status'], 'invalid')
            a, b = owner(seed, [{0}]), owner(cont, [{0}, {0}])
            a.offsets[1] = 999
            self.assertEqual(native.compose(a, b, 1)['status'], 'invalid')

    def test_seeded_budgets_ownership_and_capture(self):
        equations = [[0, 1], [2, 3]]
        original = abi.InputOwner(2, 2, abi.anf_from_equations(equations))
        seed = owner(proof(2, [['input', 0], ['input', 1], ['xor', 0, 1]], [2]), list(map(set, equations)))
        for native in self.natives:
            def run(work, nodes, capture=1):
                stats = SeededStats()
                handle = native.lib.seeded_produce(C.byref(original.view), C.byref(seed.view), work, nodes, 100, 8, capture, C.byref(stats))
                try:
                    self.assertLessEqual(stats.work, work)
                    self.assertEqual(stats.work, stats.bridge_work+stats.scan_work+stats.producer.work+stats.composition.work)
                    if handle:
                        basis, p = abi.export(native.lib.seeded_view(handle).contents)
                        cont = native.lib.seeded_continuation_view(handle)
                        self.assertEqual(bool(cont), bool(capture))
                        self.assertEqual(evaluate(p, list(map(set, equations))), list(map(set, basis)))
                        if cont:
                            cb, cp = abi.export(cont.contents)
                            self.assertEqual(compose(seed=abi.export(seed.view)[1], continuation=cp, originals=2,
                                max_work=work, max_nodes=nodes)['proof'], p)
                        return stats, basis, p
                    self.assertIn(stats.status, (1, 2))
                    return stats, None, None
                finally:
                    if handle: native.lib.seeded_destroy(handle)
            full = run(100000, 1000)
            self.assertEqual(full[0].status, 0)
            for cap in range(full[0].work+2):
                result = run(cap, 1000)
                self.assertEqual(result[0].status == 0, cap >= full[0].work)
            for nodes in range(1, 40):
                run(100000, nodes)
            self.assertEqual(run(100000, 1000, 0)[1:], full[1:])
            with ThreadPoolExecutor(max_workers=4) as pool:
                for result in pool.map(lambda _: run(100000, 1000), range(16)):
                    self.assertEqual(result[1:], full[1:])


if __name__ == '__main__':
    unittest.main()
