import unittest

from p256_isogeny_search.registry import load_candidates
from p256_isogeny_search.rho import benchmark_candidates, solve_toy_log


class RhoTests(unittest.TestCase):
    def test_toy_collision_recovers_log(self):
        candidate = load_candidates("data/candidates/toy.json")[0]
        for secret in (1, 4242, 9850):
            result = solve_toy_log(candidate, secret)
            self.assertTrue(result["verified"])
            self.assertEqual(result["recovered"], secret)

    def test_reference_benchmark_preserves_relation(self):
        candidates = load_candidates("data/candidates/p256-root.json")
        report = benchmark_candidates(candidates, seconds=0.01, trials=2)
        result = report["results"][0]
        self.assertTrue(result["linear_relation_verified"])
        self.assertGreater(result["iterations_per_second"], 0)
        self.assertEqual(result["path_degree_product"], "1")
        self.assertEqual(result["trials"], 2)


if __name__ == "__main__":
    unittest.main()
