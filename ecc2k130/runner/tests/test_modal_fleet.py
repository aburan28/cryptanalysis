"""Exercise fleet dispatch without contacting Modal or requiring its SDK."""
import ast
import json
from pathlib import Path
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
        names = {'worker': self.worker, 'readiness': self.readiness, 'json': json, 'uuid': uuid, 'print': Mock()}
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


if __name__ == '__main__':
    unittest.main()
