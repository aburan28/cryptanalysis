import unittest

from p256_isogeny_search.interleaved import (
    benchmark_candidates_interleaved,
    execution_order,
)
from p256_isogeny_search.registry import load_candidates


class InterleavedBenchmarkTests(unittest.TestCase):
    def test_rotation_balances_positions_over_full_block(self):
        orders = [execution_order(4, trial) for trial in range(4)]
        for candidate in range(4):
            positions = [order.index(candidate) for order in orders]
            self.assertEqual(sorted(positions), [0, 1, 2, 3])

    def test_single_candidate_smoke(self):
        candidate = load_candidates("data/candidates/p256-root.json")
        report = benchmark_candidates_interleaved(
            candidate,
            seconds=0.001,
            trials=2,
            warmup_seconds=0,
        )
        result = report["results"][0]
        self.assertEqual(result["paired_relative_iteration_speed"], 1.0)
        self.assertEqual(result["paired_log2_speedup_95_percent_ci"], [0.0, 0.0])
        self.assertFalse(result["paired_speedup_significant_at_95_percent"])


if __name__ == "__main__":
    unittest.main()
