"""Exercise the Modal-hosted dashboard ingester without contacting Modal, S3 or RDS."""
import ast
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

PATH = Path(__file__).resolve().parents[1] / 'modal_ingest.py'


def load(names, *wanted):
    tree = ast.parse(PATH.read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    for fn in functions:
        fn.decorator_list = []
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(PATH), 'exec'), names)
    return names


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.call = Mock(object_id='ingest-call')
        self.ingest = Mock()
        self.ingest.spawn.return_value = self.call
        self.names = load({'ingest': self.ingest, 'json': json, 'os': os, 'time': time, 'uuid': uuid,
                           'print': Mock(), 'STATUS_BUCKET': 'status-bucket'}, 'main')
        self.main = self.names['main']

    def test_the_ingester_is_spawned_with_an_absolute_deadline_and_its_own_rollout(self):
        before = time.time()
        with patch.dict(os.environ, {'ECC_RDS_SECURITY_GROUP': 'sg-test'}):
            self.main(seconds=3600)
        after = time.time()
        seconds, deadline, rollout, bucket = self.ingest.spawn.call_args.args
        self.assertEqual((seconds, bucket), (3600, 'status-bucket'))
        self.assertTrue(before + 3600 <= deadline <= after + 3600)
        self.assertRegex(rollout, r'^[a-f0-9]{32}$')
        self.ingest.remote.assert_not_called()
        self.call.get.assert_called_once()

    def test_invalid_duration_or_missing_network_starts_nothing(self):
        with patch.dict(os.environ, {'ECC_RDS_SECURITY_GROUP': 'sg-test'}):
            for seconds in (0, 82801):
                with self.assertRaises(ValueError):
                    self.main(seconds=seconds)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                self.main()
        self.ingest.spawn.assert_not_called()


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.ensure_access = Mock(return_value={'managed': True})
        self.cleanup = Mock(return_value=['sgr-1'])
        body = SimpleNamespace(read=Mock(return_value=b'print("ingest")\n'))
        self.s3 = Mock()
        self.s3.get_object.return_value = {'Body': body}
        modules = patch.dict(sys.modules, {
            'rds_network': SimpleNamespace(ensure_access=self.ensure_access, cleanup=self.cleanup),
            'boto3': SimpleNamespace(client=Mock(return_value=self.s3))})
        modules.start()
        self.addCleanup(modules.stop)
        self.supervise = Mock()
        self.names = load({'json': json, 'os': os, 'sys': sys, 'Path': Mock(), 'supervise': self.supervise,
                           'time': SimpleNamespace(time=Mock(return_value=1000.0)), 'print': Mock()}, 'ingest')
        self.ingest = self.names['ingest']

    def run_ingest(self, deadline):
        with patch.dict(os.environ, {'ECC_BUCKET': 'bucket', 'RHO_DP_DSN': 'host=db user=rho'}):
            self.ingest(82800, deadline, 'a' * 32, 'status-bucket')

    def test_runs_the_deployed_ingester_with_the_pod_arguments_until_the_deadline(self):
        self.run_ingest(1000.0 + 3600.5)
        self.s3.get_object.assert_called_once_with(Bucket='bucket', Key='aws/dp_ingest.py')
        self.ensure_access.assert_called_once_with('a' * 32)
        command, env, stop_at = self.supervise.call_args.args
        self.assertEqual(command[command.index('--bucket') + 1], 'bucket')
        self.assertEqual(command[command.index('--status-bucket') + 1], 'status-bucket')
        self.assertEqual(command[command.index('--status-every') + 1], '180')
        self.assertEqual(env['DATABASE_URL'], 'host=db user=rho')
        self.assertEqual(stop_at, 1000.0 + 3600)
        self.cleanup.assert_called_once_with('a' * 32)

    def test_a_restart_after_the_deadline_opens_nothing(self):
        self.run_ingest(1000.5)
        self.s3.get_object.assert_not_called()
        self.ensure_access.assert_not_called()
        self.supervise.assert_not_called()

    def test_network_rules_are_removed_when_the_ingester_fails(self):
        self.supervise.side_effect = RuntimeError('ingester failed')
        with self.assertRaises(RuntimeError):
            self.run_ingest(1000.0 + 3600)
        self.cleanup.assert_called_once_with('a' * 32)


class SuperviseTests(unittest.TestCase):
    def setUp(self):
        self.clock = [1000.0]
        self.sleep = Mock(side_effect=lambda s: self.clock.__setitem__(0, self.clock[0] + s))
        self.popen = Mock()
        fake = SimpleNamespace(Popen=self.popen, TimeoutExpired=subprocess.TimeoutExpired)
        names = load({'json': json, 'signal': signal, 'subprocess': fake, 'print': Mock(),
                      'time': SimpleNamespace(time=lambda: self.clock[0], sleep=self.sleep)}, 'supervise')
        self.supervise = names['supervise']

    def test_stops_the_ingester_with_sigint_at_the_deadline(self):
        process = Mock()
        process.wait.side_effect = [subprocess.TimeoutExpired('ingest', 3600), 0]
        self.popen.return_value = process
        self.supervise(['ingest'], {}, 1000.0 + 3600)
        self.assertEqual(process.wait.call_args_list[0].kwargs['timeout'], 3600)
        process.send_signal.assert_called_once_with(signal.SIGINT)
        process.kill.assert_not_called()

    def test_kills_an_ingester_that_ignores_sigint(self):
        process = Mock()
        process.wait.side_effect = [subprocess.TimeoutExpired('ingest', 1), subprocess.TimeoutExpired('ingest', 60), 0]
        self.popen.return_value = process
        self.supervise(['ingest'], {}, 1000.0 + 1)
        process.kill.assert_called_once()

    def test_restarts_an_ingester_that_exits_before_the_deadline(self):
        crashed, second = Mock(), Mock()
        crashed.wait.return_value = 1
        second.wait.side_effect = [subprocess.TimeoutExpired('ingest', 1), 0]
        self.popen.side_effect = [crashed, second]
        self.supervise(['ingest'], {'K': 'V'}, 1000.0 + 600)
        self.assertEqual(self.popen.call_count, 2)
        self.sleep.assert_called_once_with(15)
        self.assertEqual(self.popen.call_args.kwargs['env'], {'K': 'V'})
        second.send_signal.assert_called_once_with(signal.SIGINT)


if __name__ == '__main__':
    unittest.main()
