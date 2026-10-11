import json
import os
from pathlib import Path
import struct
import queue
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'aws'))
import cloud
import rds_gpu
from worker import Worker, LocalStore, S3Slots, S3Store


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.worker = Worker.__new__(Worker)
        w = self.worker
        w.work = str(root / 'work')
        Path(w.work).mkdir()
        w.store = LocalStore(str(root / 'store'))
        w.statePath = str(root / 'state.json')
        w.state = {'slot': 0, 'dpOffset': 0, 'ckptIter': -1}
        w.owner = 'test-worker'
        w.cfg = {'dpWeight': 32}
        w.renewLease = lambda slot, force=False: None
        self.record = struct.pack('<4Q', 10, 20, 30, 40)
        Path(w.dpPath).write_bytes(self.record + b'partial')
        Path(w.ckptPath).write_bytes(b'ECC2K130' + b'\0' * 24 + struct.pack('<Q', 123))

    def test_rds_failure_retries_before_checkpoint_and_offset_advance(self):
        w = self.worker
        with patch.dict(os.environ, {'RHO_DP_DSN': 'test-only'}), \
             patch.object(rds_gpu, 'reportGpuDelta', side_effect=OSError('offline')):
            with self.assertRaisesRegex(RuntimeError, 'RDS reporting failed'):
                w.uploadCycle(0)
        self.assertEqual(w.state['dpOffset'], 0)
        self.assertFalse(w.store.exists(w.ckptKey(0)))
        # The S3 copy already exists and contains only full records.
        parts = list(Path(w.store.root).glob('dp/**/*.bin'))
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].read_bytes(), self.record)
        stats = {'reported': 1, 'new': 1, 'collisions': 0}
        with patch.dict(os.environ, {'RHO_DP_DSN': 'test-only'}), \
             patch.object(rds_gpu, 'reportGpuDelta', return_value=stats) as report:
            w.uploadCycle(0)
            report.assert_called_once()
        self.assertEqual(w.state['dpOffset'], 32)
        self.assertEqual(w.state['ckptIter'], 123)
        self.assertTrue(w.store.exists(w.ckptKey(0)))
        self.assertEqual(len(list(Path(w.store.root).glob('dp/**/*.bin'))), 1)
        # A second cycle does not re-report acknowledged records.
        with patch.object(rds_gpu, 'reportGpuDelta') as report:
            w.uploadCycle(0)
            report.assert_not_called()

    def test_rotated_deltas_cannot_overwrite_earlier_objects(self):
        w = self.worker
        with patch.object(w, 'reportRds'):
            w.uploadCycle(0)
            w.rotateDpFile()
            second = struct.pack('<4Q', 11, 20, 30, 40)
            Path(w.dpPath).write_bytes(second)
            w.uploadCycle(0)
        parts = list(Path(w.store.root).glob('dp/**/*.bin'))
        self.assertEqual({p.read_bytes() for p in parts}, {self.record, second})

    def test_s3_failure_does_not_report_rds(self):
        with patch.object(self.worker.store, 'put', side_effect=OSError('offline')), \
             patch.object(self.worker, 'reportRds') as report:
            with self.assertRaises(OSError):
                self.worker.uploadCycle(0)
            report.assert_not_called()
        self.assertEqual(self.worker.state['dpOffset'], 0)

    def test_snapshot_precedes_dp_read_even_if_client_checkpoints_again(self):
        w = self.worker
        original = Path(w.ckptPath).read_bytes()
        def report(delta, slot):
            replacement = Path(w.ckptPath + '.next')
            replacement.write_bytes(b'ECC2K130' + b'\0' * 24 + struct.pack('<Q', 456))
            replacement.replace(w.ckptPath)
        with patch.object(w, 'reportRds', side_effect=report):
            w.uploadCycle(0)
        self.assertEqual((Path(w.store.root) / w.ckptKey(0)).read_bytes(), original)

    def test_s3_claim_lost_race_can_allocate_next_slot(self):
        slots = S3Slots('test-bucket')
        items = [{'slot': 4, '_etag': 'old', 'state': 'idle', 'leaseUntil': 0}]
        with patch.object(slots, 'scan', return_value=items), \
             patch.object(slots, '_put', side_effect=[False, True]):
            self.assertEqual(slots.claim('worker', {}), 5)
        self.assertEqual(items[0]['slot'], 4)

    def test_lost_lease_stops_publication(self):
        from unittest.mock import Mock
        import time
        w = self.worker
        del w.renewLease
        w.lastLeaseRenewal = time.monotonic()
        w.leaseLost = False
        w.stopping = False
        w.slots = Mock()
        w.slots.heartbeat.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'publication stopped'):
            w.uploadCycle(0)
        self.assertTrue(w.stopping)
        self.assertTrue(w.leaseLost)
        self.assertFalse(w.store.exists(w.ckptKey(0)))
        self.assertEqual(w.state['dpOffset'], 0)

    def test_s3_forbidden_is_not_treated_as_missing(self):
        import subprocess
        response = subprocess.CompletedProcess([], 1, '', '403 AccessDenied')
        with patch('worker.subprocess.run', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'head-object failed'):
                S3Store('test-bucket').exists('campaign.json')


class ConfigTests(unittest.TestCase):
    def test_campaign_matches_container_geometry(self):
        cfg = json.loads((ROOT / 'aws/campaign.json').read_text())
        manifest = json.loads((ROOT / 'build.json').read_text())
        cloud.validate_config(cfg, manifest)
        for key, value in [('batch', 8), ('workers', 1), ('dpWeight', -1),
                           ('extraArgs', ['--run-id', '1']), ('uploadEvery', 0)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                cloud.validate_config({**cfg, key: value}, manifest)

    def test_invalid_record_offset_is_rejected_before_database_open(self):
        for offset in (-32, -1, 1, 33):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                rds_gpu.reportGpuDelta('unused', worker_id='test', start=offset)

    def test_smoke_uses_s3_bytes_and_rolls_back_database_reports(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            w = Worker.__new__(Worker)
            w.work = tmp
            w.cfg = {'dpWeight': 32}
            w.store = LocalStore(str(Path(tmp) / 'store'))
            store = MagicMock()
            store.report_many.return_value = [
                {'is_new': True, 'is_collision': False},
                {'is_new': False, 'is_collision': False},
                {'is_new': False, 'is_collision': True},
            ]
            with patch.object(cloud, 'Store', return_value=store):
                result = cloud.smoke(w)
            store._conn.transaction.assert_called_once_with(force_rollback=True)
            store.close.assert_called_once()
            self.assertTrue(w.store.exists(result['s3_key']))
            self.assertFalse((Path(tmp) / 'smoke.bin').exists())

    def test_missing_walk_identity_cannot_reuse_legacy_campaign(self):
        cfg = json.loads((ROOT / 'aws/campaign.json').read_text())
        manifest = json.loads((ROOT / 'build.json').read_text())
        del cfg['walkId']
        with self.assertRaisesRegex(cloud.ConfigurationError, 'walkId'):
            cloud.validate_config(cfg, manifest)

    def test_legacy_campaign_rejects_dp34_and_table_walk(self):
        cfg = json.loads((ROOT / 'aws/campaign.json').read_text())
        manifest = json.loads((ROOT / 'build.json').read_text())
        for key, value in [('dpWeight', 34), ('walkId', 'certicom-ecc2k130-table8-v1')]:
            with self.subTest(key=key), self.assertRaises(cloud.ConfigurationError):
                cloud.validate_config({**cfg, key: value}, {**manifest, key: value})

    def test_campaign_creation_never_overwrites_existing_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Worker.__new__(Worker)
            w.store = LocalStore(tmp)
            path = Path(tmp) / 'campaign.json'
            original = b'{"existing":true}'
            path.write_bytes(original)
            with patch.dict(os.environ, {'ECC_PREFIX':'campaigns/test'}):
                cloud.initialize_campaign(w)
            self.assertEqual(path.read_bytes(), original)

    def test_namespace_covers_objects_and_slot_leases(self):
        prefix = 'campaigns/new-walk'
        store = S3Store('bucket', prefix)
        slots = S3Slots('bucket', prefix)
        self.assertEqual(store.key('ckpt/slot-00001.ck'), prefix + '/ckpt/slot-00001.ck')
        self.assertEqual(slots._key(1), prefix + '/slots/slot-00001.json')
        import subprocess
        with patch('worker.subprocess.run', return_value=subprocess.CompletedProcess([],0,'[]','')) as run:
            self.assertEqual(slots.scan(), [])
        args = run.call_args.args[0]
        self.assertEqual(args[args.index('--prefix') + 1], prefix + '/slots/')

    def test_run_id_base_keeps_new_workers_out_of_legacy_seed_ranges(self):
        w = Worker.__new__(Worker)
        w.cfg = {'runIdBase':10000}
        self.assertEqual([w.runId(i) for i in range(4)], [10000,10001,10002,10003])
        with self.assertRaisesRegex(ValueError, 'exhausted'):
            w.runId(60000)


class ClientLoopTests(unittest.TestCase):
    def worker(self):
        from unittest.mock import Mock
        w = Worker.__new__(Worker)
        w.work = '/unused'
        w.gpu = 0
        w.cfg = {'checkpointEvery': 60, 'uploadEvery': 60}
        w.state = {}
        w.owner = 'fixture'
        w.deadline = None
        w.stopping = False
        w.slots = Mock()
        w.renewLease = Mock()
        w.clientCommand = Mock(return_value=['fixture'])
        return w

    def test_progress_backlog_is_drained_before_cloud_work(self):
        from unittest.mock import Mock
        w = self.worker()
        messages = queue.Queue()
        for iteration in range(1, 201):
            messages.put('1.0 s 21000.000 M it/s %d iterations 0 dp 0 stored 0 dropped' % iteration)
        messages.put(None)
        proc = Mock()
        proc.poll.return_value = proc.wait.return_value = 0
        with patch('worker.queue.Queue', return_value=messages), \
             patch('worker.threading.Thread'), patch('worker.subprocess.Popen', return_value=proc), \
             patch.object(w, 'uploadCycle'), patch('worker.log'):
            self.assertEqual(w.runClient(0), (0, None, False))
        fields = w.slots.heartbeat.call_args.args[2]
        self.assertEqual(fields['iters'], 200)

    def test_slow_upload_does_not_immediately_repeat(self):
        from unittest.mock import Mock
        w = self.worker()
        messages = Mock()
        messages.get.side_effect = ['1.0 s 21000.000 M it/s 1 iterations 0 dp 0 stored 0 dropped',
                                    queue.Empty(), None]
        messages.get_nowait.side_effect = queue.Empty()
        proc = Mock()
        proc.poll.return_value = proc.wait.return_value = 0
        current = [100.0]
        def now():
            value = current[0]
            if value == 100.0:
                current[0] = 200.0
            return value
        def upload(slot):
            current[0] += 80.0
        with patch('worker.queue.Queue', return_value=messages), \
             patch('worker.threading.Thread'), patch('worker.subprocess.Popen', return_value=proc), \
             patch('worker.time.time', side_effect=now), patch('worker.log'), \
             patch.object(w, 'uploadCycle', side_effect=upload) as publish:
            w.runClient(0)
        # One periodic publish plus the final flush, despite a >60s publish.
        self.assertEqual(publish.call_count, 2)


if __name__ == '__main__':
    unittest.main()
