import copy
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

import seed_registry as sr


class MemoryStore:
    def __init__(self):
        self.rows = {sr.CONFIG_KEY: ({'version': 1, 'state': 'ready'}, '1')}
        self.lock = threading.Lock()

    def read(self, key):
        with self.lock:
            return copy.deepcopy(self.rows.get(key, (None, None)))

    def cas(self, key, value, etag=None):
        with self.lock:
            old, version = self.rows.get(key, (None, None))
            if version != etag:
                return False
            self.rows[key] = (copy.deepcopy(value), str(int(version or 0) + 1))
            return True


class SeedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.checkpoint = str(Path(self.tmp.name) / 'walk.ck')
        self.store = MemoryStore()
        self.registry = sr.SeedRegistry(self.store)

    def save_checkpoint(self, run_id=8000, iteration=10, lanes=1, threads=32, batch=16):
        Path(self.checkpoint).write_bytes(b'ECC2K130' + struct.pack(
            '<6IQ', 2, 131, threads, batch, lanes, run_id, iteration) + b'x' * 64)

    def acquire(self, stream='modal:8000'):
        return self.registry.acquire(8000, stream, self.checkpoint)

    def test_only_one_of_many_simultaneous_first_claims_can_start(self):
        def attempt(i):
            try:
                return self.acquire('provider:%d' % i)
            except sr.SeedConflict:
                return None
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(attempt, range(32)))
        self.assertEqual(sum(x is not None for x in results), 1)

    def test_same_stream_is_not_permission_for_two_live_owners(self):
        self.acquire()
        self.save_checkpoint()
        with self.assertRaisesRegex(sr.SeedConflict, 'already has an owner'):
            self.acquire()

    def test_stale_owner_does_not_expire_into_a_second_running_gpu(self):
        self.acquire()
        self.save_checkpoint()
        self.registry.clock = lambda: 10 ** 20
        with self.assertRaisesRegex(sr.SeedConflict, 'already has an owner'):
            self.acquire()

    def test_clean_stop_can_resume_only_the_same_stream(self):
        token = self.acquire()
        self.save_checkpoint()
        self.registry.release(8000, token, self.checkpoint)
        with self.assertRaisesRegex(sr.SeedConflict, 'another stream'):
            self.acquire('another-provider:slot0')
        self.assertTrue(self.acquire())

    def test_lost_checkpoint_cannot_restart_used_seeds_from_zero(self):
        token = self.acquire()
        self.registry.release(8000, token, self.checkpoint)
        with self.assertRaisesRegex(sr.SeedConflict, 'from zero'):
            self.acquire()

    def test_checkpoint_cannot_move_backwards(self):
        token = self.acquire()
        self.save_checkpoint(iteration=20)
        self.registry.release(8000, token, self.checkpoint)
        self.save_checkpoint(iteration=19)
        with self.assertRaisesRegex(sr.SeedConflict, 'older'):
            self.acquire()

    def test_other_run_checkpoint_is_refused_before_ownership_changes(self):
        self.save_checkpoint(run_id=8001)
        with self.assertRaisesRegex(sr.SeedConflict, 'identity'):
            self.acquire()
        self.assertIsNone(self.store.read(sr.run_key(8000))[0])

    def test_header_sidecar_is_not_a_resumable_checkpoint(self):
        self.save_checkpoint()
        Path(self.checkpoint).write_bytes(Path(self.checkpoint).read_bytes()[:40])
        with self.assertRaisesRegex(sr.SeedConflict, 'full resumable'):
            self.acquire()

    def test_lane_index_must_not_wrap_32_bits(self):
        self.save_checkpoint(threads=2 ** 31, batch=16)
        with self.assertRaisesRegex(sr.SeedConflict, '32-bit'):
            self.acquire()

    def test_invalid_run_ids_do_not_alias_through_the_16_bit_field(self):
        for bad in (0, -1, 65536, True, '8000'):
            with self.assertRaises(sr.SeedConflict):
                self.registry.acquire(bad, 'stream', self.checkpoint)

    def test_registry_must_be_initialized_after_history_inventory(self):
        self.store.rows.clear()
        with self.assertRaisesRegex(sr.SeedConflict, 'audited'):
            self.acquire()

    def test_stale_or_foreign_owner_cannot_unlock_a_run(self):
        token = self.acquire()
        with self.assertRaisesRegex(sr.SeedConflict, 'ownership changed'):
            self.registry.release(8000, 'other', self.checkpoint)
        self.assertEqual(self.store.read(sr.run_key(8000))[0]['active_owner'], token)

    def test_retired_run_ids_are_never_recycled(self):
        self.store.cas(sr.run_key(8000), dict(version=1, run_id=8000, stream='modal:8000', blocked=True))
        with self.assertRaisesRegex(sr.SeedConflict, 'retired'):
            self.acquire()

    def test_storage_failure_does_not_allow_a_launch(self):
        with patch.object(self.store, 'read', side_effect=sr.SeedConflict('unavailable')):
            with self.assertRaises(sr.SeedConflict):
                self.acquire()

    def test_global_identity_does_not_depend_on_storage_prefix(self):
        self.assertNotEqual(sr.slot_stream('', 0), sr.slot_stream('campaigns/new', 0))
        self.assertNotEqual(sr.slot_stream('', 0), sr.slot_stream('', 0, 'rds:campaign'))
        self.assertTrue(sr.run_key(12000).startswith(sr.PREFIX))

    def test_next_pair_includes_registry_only_ids_and_cpu_reservations(self):
        self.store.cas(sr.run_key(8000), {'started': True})
        self.store.cas(sr.run_key(9001), {'started': True})
        self.assertEqual(self.registry.next_modal_run({8002}), 8003)


    def test_worker_exception_does_not_release_a_still_running_child(self):
        worker = Mock()
        worker.cfg = {'curve': 131}
        worker.store.bucket = 'bucket'
        worker.store.prefix = ''
        worker.slots = type('S3Slots', (), {})()
        worker.ckptPath = self.checkpoint
        worker.proc.poll.return_value = None
        with patch.object(sr, 'S3Json', return_value=self.store):
            with self.assertRaisesRegex(RuntimeError, 'supervisor failed'):
                with sr.worker_guard(worker, 7999, 8000):
                    raise RuntimeError('supervisor failed')
        self.assertTrue(self.store.read(sr.run_key(8000))[0]['active_owner'])

    def test_worker_releases_only_after_the_child_exits(self):
        worker = Mock()
        worker.cfg = {'curve': 131}
        worker.store.bucket = 'bucket'
        worker.store.prefix = ''
        worker.slots = type('S3Slots', (), {})()
        worker.ckptPath = self.checkpoint
        worker.proc = None
        with patch.object(sr, 'S3Json', return_value=self.store):
            with sr.worker_guard(worker, 7999, 8000):
                self.save_checkpoint(iteration=30)
        row = self.store.read(sr.run_key(8000))[0]
        self.assertIsNone(row['active_owner'])
        self.assertEqual(row['checkpoint_floor'], 30)


if __name__ == '__main__':
    unittest.main()
