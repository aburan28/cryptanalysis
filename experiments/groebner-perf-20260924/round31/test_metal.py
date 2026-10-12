"""Requested Metal execution must succeed; absence never becomes a CPU pass."""
from concurrent.futures import ThreadPoolExecutor
import os
import random
import unittest

from quadratic import Producer, Inconclusive, Unsupported
from test_quadratic import packed, roots


@unittest.skipUnless(os.environ.get('QUADRATIC_TEST_METAL') == '1', 'Metal execution not requested')
class MetalTests(unittest.TestCase):
    def compare(self, x, y, equations, items):
        p = packed(x+y, equations, items)
        with Producer(x, y, equations, backend='metal') as gpu, Producer(x, y, equations) as cpu:
            actual, reference = gpu.produce(p), cpu.produce(p)
            self.assertEqual(actual['roots'], roots(x+y, items))
            self.assertEqual(actual['basis'], reference['basis'])
            for name, value in reference['stats'].items():
                if name not in ('specialization', 'evaluation', 'interpolation', 'gpu_wall', 'gpu_device',
                                'gpu_used', 'gpu_shape_fallback', 'workspace_bytes'):
                    self.assertEqual(actual['stats'][name], value, name)
            supported = equations <= 32 and y*(y+1)//2 <= 31
            self.assertEqual(actual['stats']['gpu_used'], int(supported))
            self.assertEqual(actual['stats']['gpu_shape_fallback'], int(not supported))
            if supported:
                self.assertGreater(actual['stats']['gpu_wall'], 0)
                self.assertFalse(gpu.device.startswith('cpu'))
            else:
                self.assertIn('shape fallback', gpu.device)

    def test_all_three_variable_functions_and_partial_threadgroups(self):
        with Producer(1, 2, 1, backend='metal') as gpu, Producer(1, 2, 1) as cpu:
            for bits in range(256):
                items = [(m, 1) for m in range(8) if bits>>m&1]
                p = packed(3, 1, items)
                actual = gpu.produce(p)
                self.assertEqual(actual['roots'], roots(3, items))
                self.assertEqual(actual['basis'], cpu.produce(p)['basis'])
                self.assertEqual(actual['stats']['gpu_used'], 1)

    def test_seeded_shapes_pivot_gaps_equation_limits(self):
        rng = random.Random(31092026)
        for x, y in ((1, 1), (1, 7), (2, 2), (3, 3), (2, 5), (2, 6)):
            for equations in (1, 2, 7, 31, 32, 33, 64, 65, 128):
                # Avoid >256 roots on the one-equation eight-variable boundary.
                items = [(m, rng.getrandbits(equations)) for m in range(1<<(x+y))
                         if (m>>x).bit_count() <= 2 and rng.randrange(3) == 0]
                items += [(0, 1), (0, 1), (1, 0)]
                self.compare(x, y, equations, items)
        self.compare(1, 8, 32, [(0, 1)])  # Feature-count fallback; inconsistent.
        for items in ([], [(0, 1)], [(4, 1<<31)], [(1, 1), (4, 2), (0, 1)],
                      [(4, 1), (8, 2), (12, 4), (0, 4)]):
            self.compare(2, 2, 32, items)

    def test_high_nullity_false_roots_and_reuse_after_failure(self):
        self.compare(2, 4, 1, [(3, 1), (4|8, 1)])
        self.compare(1, 2, 3, [(2, 1), (4, 2), (6, 4), (0, 4)])
        with Producer(4, 5, 1, backend='metal') as gpu:
            with self.assertRaises(Inconclusive):
                gpu.produce(packed(9, 1, []))
            with self.assertRaises(Unsupported):
                gpu.produce(packed(9, 1, [(16|32|64, 1)]))
            self.assertEqual(gpu.produce(packed(9, 1, [(0, 1)]))['roots'], [])

    def test_serialized_concurrent_calls(self):
        items = [[(1, 1), (0, i&1), (2, 2)] for i in range(16)]
        with Producer(2, 3, 2, backend='metal') as gpu:
            with ThreadPoolExecutor(max_workers=4) as pool:
                actual = list(pool.map(gpu.produce, [packed(5, 2, p) for p in items]))
            self.assertEqual([a['roots'] for a in actual], [roots(5, p) for p in items])


if __name__ == '__main__':
    unittest.main()
