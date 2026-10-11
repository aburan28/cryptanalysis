#!/usr/bin/env python3
"""Packing tests for GPU → RDS records (no database)."""

import struct
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import rds_gpu
import unittest

from rds_gpu import RECORD_BYTES, coeffBytes, iterGpuRecords, parseGpuRecord


class GpuRecordTests(unittest.TestCase):
    def test_parse_keeps_starting_seed_and_orbit_key(self):
        seed = 0x0123456789ABCDEF
        key = (0x1111111111111111, 0x2222222222222222, 0x3333333333333333)
        blob = struct.pack("<4Q", seed, *key)
        got_seed, point_key = parseGpuRecord(blob)
        self.assertEqual(got_seed, seed)
        self.assertEqual(point_key, struct.pack("<3Q", *key))
        self.assertEqual(len(point_key), 24)

    def test_iter_skips_trailing_partial_record(self):
        rec = struct.pack("<4Q", 7, 1, 2, 3)
        rows = list(iterGpuRecords(rec + b"\x00\x01"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 7)

    def test_walk_seed_encoding_is_big_endian_integer(self):
        self.assertEqual(coeffBytes(0), b"\x00")
        self.assertEqual(coeffBytes(1), b"\x01")
        self.assertEqual(coeffBytes(0x4F09), b"\x4f\x09")
        # a/b width used by the Type-II ingest (17 bytes mod 2^131)
        a = coeffBytes(0x0123456789ABCDEF, 1 << 131)
        self.assertEqual(len(a), 17)
        self.assertEqual(int.from_bytes(a, "big"), 0x0123456789ABCDEF)

    def test_record_size(self):
        self.assertEqual(RECORD_BYTES, 32)


class ReportTests(unittest.TestCase):
    def test_streamed_delta_reports_whole_records_and_renews_lease(self):
        store = MagicMock()
        store.report_many.side_effect = lambda rows, **kw: [{"is_new": True, "is_collision": False} for _ in rows]
        progress = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dp.bin'
            path.write_bytes(struct.pack('<4Q', 7, 1, 2, 3) * 3 + b'partial')
            with patch.object(rds_gpu, 'Store', return_value=store):
                result = rds_gpu.reportGpuDelta(path, worker_id='test', start=32,
                                               progress=progress, dp_weight=32)
        self.assertEqual(result['reported'], 2)
        store.register.assert_called_once_with(rds_gpu.CAMPAIGN, dp_weight=32, walk_id=None)
        self.assertGreaterEqual(progress.call_count, 2)
        self.assertEqual(store.report_many.call_args.args[0], [(struct.pack('<3Q', 1, 2, 3), 7)] * 2)
        store.close.assert_called_once()

    def test_lease_loss_aborts_reporting_and_closes_database(self):
        store = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dp.bin'
            path.write_bytes(struct.pack('<4Q', 7, 1, 2, 3))
            with patch.object(rds_gpu, 'Store', return_value=store):
                with self.assertRaisesRegex(RuntimeError, 'lease lost'):
                    rds_gpu.reportGpuDelta(path, worker_id='test',
                        progress=MagicMock(side_effect=RuntimeError('lease lost')))
        store.report.assert_not_called()
        store.report_many.assert_not_called()
        store.close.assert_called_once()

    def test_pipeline_failure_propagates_and_closes_pending_cursors(self):
        store = rds_gpu.Store.__new__(rds_gpu.Store)
        store._conn = MagicMock()
        cur = store._conn.execute.return_value
        store._conn.pipeline.return_value.__enter__.return_value.sync.side_effect = OSError('database failed')
        with self.assertRaisesRegex(OSError, 'database failed'):
            store.report_many([(b'key', 7)], campaign='isolated')
        cur.close.assert_called_once()
        cur.fetchone.assert_not_called()

    def test_campaign_identity_conflict_is_rejected(self):
        store = rds_gpu.Store.__new__(rds_gpu.Store)
        store._conn = MagicMock()
        store._conn.cursor.return_value.__enter__.return_value.fetchone.return_value = None
        with self.assertRaisesRegex(ValueError, 'walk identity differs'):
            store.register('old-campaign', walk_id='table8-v1')

    def test_legacy_registration_is_read_only_and_requires_known_identity(self):
        store = rds_gpu.Store.__new__(rds_gpu.Store)
        store._conn = MagicMock()
        cur = store._conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = (rds_gpu.CURVE, rds_gpu.ORDER_N, None,
            {'format': 'ecc2k130-gpu-packed32',
             'point_key': '3xuint64-le orbit representative (x only)'})
        store.register('ecc2k-130', dp_weight=32, walk_id=rds_gpu.LEGACY_WALK)
        self.assertTrue(cur.execute.call_args.args[0].startswith('SELECT'))
        for weight, walk in [(34, rds_gpu.LEGACY_WALK), (32, 'table8'), (32, None)]:
            with self.subTest(weight=weight, walk=walk), self.assertRaises(ValueError):
                store.register('ecc2k-130', dp_weight=weight, walk_id=walk)
        cur.fetchone.return_value = (rds_gpu.CURVE, rds_gpu.ORDER_N, None,
            {'format': 'ecc2k130-gpu-packed32', 'walk_id': 'table8',
             'point_key': '3xuint64-le orbit representative (x only)'})
        with self.assertRaises(ValueError):
            store.register('ecc2k-130', dp_weight=32, walk_id=rds_gpu.LEGACY_WALK)

    def test_large_delta_batches_preserve_all_seeds_and_accounting(self):
        store = MagicMock()
        seen = []
        def batch(rows, **kw):
            self.assertLessEqual(len(rows), 256)
            seen.extend(seed for _, seed in rows)
            return [{'is_new': seed % 2 == 0, 'is_collision': seed == 512} for _, seed in rows]
        store.report_many.side_effect = batch
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dp.bin'
            path.write_bytes(b''.join(struct.pack('<4Q', i, 1, 2, 3) for i in range(513)) + b'partial')
            with patch.object(rds_gpu, 'Store', return_value=store):
                result = rds_gpu.reportGpuDelta(path, worker_id='test')
        self.assertEqual(seen, list(range(513)))
        self.assertEqual((result['reported'], result['new'], result['collisions']), (513,257,1))


if __name__ == "__main__":
    unittest.main()
