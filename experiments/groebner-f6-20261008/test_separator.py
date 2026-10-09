import random
import unittest

from separator import WidthCap, canonical, satisfies, solve


class SeparatorTests(unittest.TestCase):
    def test_random_exactness_against_exhaustive(self):
        rng = random.Random(87109)
        for n in range(1, 8):
            for _ in range(35):
                equations = [[rng.randrange(1 << n) for _ in range(rng.randrange(1, 6))]
                             for _ in range(rng.randrange(1, 6))]
                expected = any(all(satisfies(canonical(eq), x) for eq in equations)
                               for x in range(1 << n))
                result = solve(n, equations, max_bag=n)
                self.assertEqual(result['status'] == 'satisfiable', expected)
                if expected:
                    self.assertTrue(all(satisfies(canonical(eq), result['assignment'])
                                        for eq in equations))

    def test_long_local_degree_four_chain(self):
        n = 48
        equations = []
        for i in range(n-3):
            quartic = sum(1 << j for j in range(i, i+4))
            equations.append([quartic, (1 << i) | (1 << (i+1))])
        result = solve(n, equations, max_bag=4)
        self.assertEqual(result['status'], 'satisfiable')
        self.assertEqual(result['width'], 4)
        self.assertLess(result['enumerated_states'], 16*n)

    def test_global_constraint_reaches_width_cap(self):
        with self.assertRaises(WidthCap):
            solve(12, [[1 << i for i in range(12)]], max_bag=6)

    def test_cancellation_before_support_graph(self):
        result = solve(24, [[(1 << 24)-1, (1 << 24)-1]], max_bag=1)
        self.assertEqual(result['status'], 'satisfiable')
        self.assertEqual(result['width'], 1)

    def test_caps_keep_unknown_status(self):
        result = solve(10, [[(1 << 10)-1]], max_bag=10, max_states=100)
        self.assertEqual(result['status'], 'state-cap')
        self.assertIsNone(result['assignment'])


if __name__ == '__main__':
    unittest.main()
