"""Real toy receipts and corruption checks; test durations are not benchmarks."""
import copy
import time
import unittest
from unittest.mock import patch

from ic_query import ARMS, PreparedIC, Point
from identity import candidate, fixture, source_snapshot
from receipts import receipt, validate_run


class ReceiptTests(unittest.TestCase):
    def test_complete_real_receipts_and_corrupt_recovery(self):
        snapshot = source_snapshot()
        for arm in ARMS:
            started = time.perf_counter_ns()
            with PreparedIC(arm=arm) as q:
                wid, frozen, expected = fixture(q, 401)
                cid, manifest = candidate(q, snapshot)
                Q = Point(**frozen['target'])
                result = q.recover(Q, frozen['rerandomization_seed'])
                rho = q.rho(Q)
                row = receipt(q, cid, manifest, wid, frozen, result, rho, 1, time.perf_counter_ns()-started)
                self.assertEqual(row['status'], 'complete')
                self.assertIsNone(row['total_operations'])
                self.assertEqual(row['scalar_certificate']['scalar'], expected)
                self.assertEqual(sum(row['online']['phase_wall_ns'].values()), row['online']['ic_online_ns'])
                bad = copy.deepcopy(row)
                bad['rho_measured']['scalar'] = (expected+1) % q.curve.r
                with self.assertRaises(ValueError): validate_run(bad)

    def test_error_attempts_remain_charged_and_visible(self):
        with PreparedIC() as q:
            _, frozen, _ = fixture(q, 401)
            with patch.object(q.backend, 'decompose', side_effect=RuntimeError('injected PDP failure')):
                result = q.recover(Point(**frozen['target']), frozen['rerandomization_seed'])
            self.assertEqual(result['status'], 'error')
            self.assertEqual(len(result['attempts']), 1)
            self.assertEqual(result['attempts'][0]['status'], 'error')
            self.assertIn('injected PDP failure', result['attempts'][0]['detail'])
            self.assertEqual(sum(result['phase_wall_ns'].values()), result['online_wall_ns'])


if __name__ == '__main__': unittest.main()
