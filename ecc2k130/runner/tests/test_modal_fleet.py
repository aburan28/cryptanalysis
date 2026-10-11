"""Exercise fleet dispatch without contacting Modal or requiring its SDK."""
import ast
import json
import os
from pathlib import Path
import time
import unittest
import uuid
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch


class FleetTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'modal_worker.py'
        tree = ast.parse(path.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('main', 'fleet')]
        for fn in functions:
            fn.decorator_list = []
        self.worker = Mock()
        self.readiness = Mock()
        self.readiness.remote.return_value = {'ok': True}
        self.cleanup = Mock(return_value=[])
        modules = patch.dict(sys.modules, {'rds_network': SimpleNamespace(cleanup=self.cleanup)})
        modules.start()
        self.addCleanup(modules.stop)
        names = {'worker': self.worker, 'readiness': self.readiness, 'json': json, 'time': time,
                 'uuid': uuid, 'print': Mock()}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), names)
        self.fleet = Mock()
        self.fleet.remote.side_effect = names['fleet']
        names['fleet'] = self.fleet
        self.main = names['main']

    def test_four_long_calls_are_submitted_before_waiting(self):
        calls = [Mock(object_id=f'call-{n}') for n in range(4)]
        for call in calls:
            call.get.side_effect = lambda: self.assertEqual(self.worker.spawn.call_count, 4)
        self.worker.spawn.side_effect = calls
        self.main(command='run')
        self.readiness.remote.assert_called_once_with(True, False, True)
        self.assertEqual(self.worker.spawn.call_count, 4)
        for call in self.worker.spawn.call_args_list:
            self.assertEqual(call.args[:3], ('run', 82800, False))
        rollouts = {call.args[3] for call in self.worker.spawn.call_args_list}
        self.assertEqual(len(rollouts), 1)
        for call in calls:
            call.get.assert_called_once()
        self.cleanup.assert_called_once_with(next(iter(rollouts)))

    def test_every_worker_shares_one_rollout_deadline(self):
        self.worker.spawn.side_effect = [Mock(object_id=f'call-{n}') for n in range(4)]
        before = time.time()
        self.main(command='run')
        after = time.time()
        deadlines = {call.args[4] for call in self.worker.spawn.call_args_list}
        self.assertEqual(len(deadlines), 1)
        self.assertTrue(before + 82800 <= next(iter(deadlines)) <= after + 82800)

    def test_failed_readiness_starts_no_workers(self):
        self.readiness.remote.side_effect = RuntimeError('database unavailable')
        with self.assertRaises(RuntimeError):
            self.main(command='run')
        self.worker.spawn.assert_not_called()

    def test_invalid_count_does_not_contact_modal(self):
        for count in (0, 5):
            with self.assertRaises(ValueError):
                self.main(command='run', count=count)
        self.readiness.remote.assert_not_called()

    def test_preflight_starts_no_gpu_workers(self):
        self.main(command='preflight')
        self.readiness.remote.assert_called_once_with(False, False, False)
        self.worker.spawn.assert_not_called()

    def test_failure_does_not_skip_sibling_results(self):
        calls = [Mock(object_id=f'call-{n}') for n in range(4)]
        calls[0].get.side_effect = RuntimeError('worker failed')
        self.worker.spawn.side_effect = calls
        with self.assertRaisesRegex(RuntimeError, 'call-0'):
            self.main(command='run')
        for call in calls:
            call.get.assert_called_once()
        self.cleanup.assert_called_once()

    def test_partial_submission_joins_existing_workers_before_cleanup(self):
        call = Mock(object_id='first')
        call.get.side_effect = lambda: self.cleanup.assert_not_called()
        self.worker.spawn.side_effect = [call, RuntimeError('submission failed')]
        with self.assertRaisesRegex(RuntimeError, 'submission failed'):
            self.main(command='run')
        call.get.assert_called_once()
        self.cleanup.assert_called_once()


class WorkerDeadlineTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'modal_worker.py'
        tree = ast.parse(path.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'worker']
        for fn in functions:
            fn.decorator_list = []
        self.ensure_access = Mock(return_value={'managed': False})
        modules = patch.dict(sys.modules, {'rds_network': SimpleNamespace(ensure_access=self.ensure_access)})
        modules.start()
        self.addCleanup(modules.stop)
        self.subprocess = Mock()
        names = {'json': json, 'os': os, 'time': SimpleNamespace(time=Mock(return_value=1000.0)),
                 'subprocess': self.subprocess, 'print': Mock()}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), names)
        self.worker = names['worker']

    def seconds(self):
        args = self.subprocess.run.call_args.args[0]
        return int(args[args.index('--seconds') + 1])

    def test_restarted_worker_runs_only_until_the_rollout_deadline(self):
        self.worker('run', 82800, False, 'a' * 32, 1000.0 + 3600.5)
        self.assertEqual(self.seconds(), 3600)
        self.ensure_access.assert_called_once_with('a' * 32)

    def test_worker_after_the_deadline_starts_nothing(self):
        self.worker('run', 82800, False, 'a' * 32, 1000.5)
        self.subprocess.run.assert_not_called()
        self.ensure_access.assert_not_called()

    def test_first_attempt_keeps_the_requested_duration(self):
        self.worker('run', 82800, True, '', 1000.0 + 82800)
        self.assertEqual(self.seconds(), 82800)

    def test_call_without_a_deadline_keeps_its_duration(self):
        self.worker('run', 600, True)
        self.assertEqual(self.seconds(), 600)

    def test_client_keeps_four_openmp_threads_under_a_smaller_cpu_request(self):
        with patch.dict(os.environ, {'OMP_NUM_THREADS': '2', 'ECC_BUCKET': 'bucket'}):
            self.worker('run', 600, True)
        env = self.subprocess.run.call_args.kwargs['env']
        self.assertEqual(env['OMP_NUM_THREADS'], '4')
        self.assertEqual(env['ECC_BUCKET'], 'bucket')


if __name__ == '__main__':
    unittest.main()
