"""Polynomial semantics and budget/shape rejection for proof substitution."""
import copy
import random
import unittest

from compose import compose


def proof(n, nodes, outputs):
    return dict(version=1, nvars=n, order='grevlex-x0-first', nodes=nodes, outputs=outputs)


def evaluate(p, equations):
    values = []
    for node in p['nodes']:
        if node[0] == 'input':
            value = set(equations[node[1]])
        elif node[0] == 'xor':
            value = values[node[1]] ^ values[node[2]]
        else:
            value = set()
            for term in values[node[1]]:
                value.symmetric_difference_update((term | node[2],))
        values.append(value)
    return [values[i] for i in p['outputs']]


class CompositionTests(unittest.TestCase):
    def test_random_nested_multiplication_and_original_substitution(self):
        rng = random.Random(1090001)
        for _ in range(100):
            originals = [{rng.randrange(32) for _ in range(10)} for _ in range(4)]
            def graph(inputs):
                nodes = [['input', i] for i in range(inputs)]
                for _ in range(25):
                    nodes.append(['mul', rng.randrange(len(nodes)), rng.randrange(32)]
                        if rng.randrange(2) else ['xor', rng.randrange(len(nodes)), rng.randrange(len(nodes))])
                return proof(5, nodes, [rng.randrange(len(nodes)) for _ in range(3)])
            seed = graph(4)
            derived = evaluate(seed, originals)
            continuation = graph(7)
            result = compose(seed, continuation, 4, max_work=100000, max_nodes=1000)
            self.assertEqual(result['status'], 'composed-unverified')
            self.assertEqual(evaluate(result['proof'], originals),
                             evaluate(continuation, derived+originals))
            self.assertTrue(all(node[1] < 4 for node in result['proof']['nodes'] if node[0] == 'input'))

    def test_every_small_work_and_node_budget(self):
        seed = proof(2, [['input', 0], ['mul', 0, 2]], [1])
        continuation = proof(2, [['input', 0], ['input', 1], ['xor', 0, 1]], [2])
        full = compose(seed, continuation, 1, max_work=1000, max_nodes=100)
        self.assertEqual(full['status'], 'composed-unverified')
        for cap in range(full['stats']['work']+2):
            r = compose(seed, continuation, 1, max_work=cap, max_nodes=100)
            self.assertLessEqual(r['stats']['work'], cap)
            if cap < full['stats']['work']:
                self.assertEqual(r['status'], 'inconclusive')
                self.assertIsNone(r['proof'])
            else:
                self.assertEqual(r, full)
        for cap in range(full['stats']['combined_nodes']+2):
            r = compose(seed, continuation, 1, max_work=1000, max_nodes=cap)
            self.assertLessEqual(r['stats']['combined_nodes'], cap)
            self.assertEqual(r['status'] == 'composed-unverified', cap >= full['stats']['combined_nodes'])

    def test_malformed_unused_nodes_and_input_mapping_rejected(self):
        seed = proof(2, [['input', 0]], [0])
        continuation = proof(2, [['input', 0]], [0])
        for side in ('seed', 'continuation'):
            for bad in (['input', 999], ['xor', 99, 0], ['mul', 0, 4], ['bogus', 0], ['input', True]):
                a, b = copy.deepcopy(seed), copy.deepcopy(continuation)
                (a if side == 'seed' else b)['nodes'].append(bad)
                r = compose(a, b, 1, max_work=1000, max_nodes=100)
                self.assertEqual(r['status'], 'invalid')
                self.assertIsNone(r['proof'])

    def test_empty_basis_and_repeated_outputs(self):
        empty = proof(2, [], [])
        r = compose(empty, empty, 0, max_work=100, max_nodes=10)
        self.assertEqual(r['proof'], empty)
        seed = proof(2, [['input', 0]], [0, 0])
        continuation = proof(2, [['input', 1], ['mul', 0, 1]], [1, 1])
        r = compose(seed, continuation, 1, max_work=1000, max_nodes=100)
        self.assertEqual(evaluate(r['proof'], [{0, 2}]), [{1, 3}, {1, 3}])


if __name__ == '__main__':
    unittest.main()
