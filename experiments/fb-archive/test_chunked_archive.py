"""Chunked storage retains compressed bytes and fails on incomplete or altered parts."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import chunked_archive
import fbarchive


class ChunksTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make(self, codec='xz'):
        payload = fbarchive.compress(b'preserve the complete compressed bytes\n'*50, codec)
        path = self.root/('test.json.'+codec+chunked_archive.SUFFIX)
        record = chunked_archive.write(path, payload, codec, 17)
        return path, payload, record

    def test_exact_reassembly_idempotent_write_and_codecs(self):
        for codec in ('gz', 'xz'):
            path, blob, record = self.make(codec)
            self.assertEqual(chunked_archive.read(path), blob)
            self.assertEqual(chunked_archive.write(path, blob, codec, 17), record)
            self.assertEqual(fbarchive.decompress(path), b'preserve the complete compressed bytes\n'*50)
            self.assertEqual(len(fbarchive.archive_paths(path)), len(record['parts'])+1)

    def test_bad_manifest_fields_order_and_paths(self):
        path, _, original = self.make()
        mutations = (
            lambda r: r.update(schema='unknown'),
            lambda r: r.update(codec='gz'),
            lambda r: r.update(bytes=0),
            lambda r: r.update(bytes=True),
            lambda r: r.update(bytes=chunked_archive.MAX_PAYLOAD+1),
            lambda r: r.update(sha256='0'*64),
            lambda r: r.update(parts=[]),
            lambda r: r['parts'].reverse(),
            lambda r: r['parts'][0].update(name='../outside'),
            lambda r: r['parts'][0].update(bytes=1),
            lambda r: r['parts'][0].update(sha256='0'*64),
            lambda r: r.update(extra=1),
        )
        for mutate in mutations:
            candidate = copy.deepcopy(original)
            mutate(candidate)
            path.write_text(json.dumps(candidate))
            with self.assertRaises(ValueError):
                chunked_archive.read(path)

    def test_missing_truncated_altered_and_symlink_parts(self):
        path, _, record = self.make()
        part = path.parent/record['parts'][0]['name']
        content = part.read_bytes()
        part.unlink()
        with self.assertRaises(OSError): chunked_archive.read(path)
        part.write_bytes(content[:-1])
        with self.assertRaises(ValueError): chunked_archive.read(path)
        part.write_bytes(bytes([content[0]^1])+content[1:])
        with self.assertRaises(ValueError): chunked_archive.read(path)
        other = self.root/'other'
        other.write_bytes(content)
        part.unlink()
        part.symlink_to(other)
        with self.assertRaises(ValueError): chunked_archive.read(path)
        with self.assertRaises(ValueError): chunked_archive.write(path, b'changed', 'xz', 17)

    def test_index_roundtrip_rebuild_and_archive_inventory(self):
        with mock.patch.object(fbarchive, 'HERE', self.root), \
                mock.patch.object(fbarchive, 'INDEX', self.root/'index.csv'), \
                mock.patch.object(fbarchive, 'verify_aliases', return_value=[]):
            doc = fbarchive.build(13, 'prefix', 3, 1)
            row = fbarchive.store(doc, codec='xz', max_git_bytes=0, chunk_bytes=73)
            self.assertEqual(row['storage'], 'git-chunks')
            self.assertEqual(fbarchive.archive_bytes(self.root/row['path']),
                             fbarchive.compress(fbarchive.canonical(doc).encode(), 'xz'))
            self.assertEqual(fbarchive.verify_row(row, True, 1000), [])
            with mock.patch('sys.argv', ['fbarchive.py', 'verify']), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as result: fbarchive.main()
                self.assertEqual(result.exception.code, 0)
            bad = {**row, 'bytes': row['bytes']+1}
            self.assertTrue(fbarchive.verify_row(bad, False, 0))
            part = fbarchive.archive_paths(self.root/row['path'])[1]
            part.unlink()
            self.assertTrue(fbarchive.verify_row(row, False, 0))

    def test_upload_plan_includes_manifest_and_every_part(self):
        with mock.patch.object(fbarchive, 'HERE', self.root), \
                mock.patch.object(fbarchive, 'INDEX', self.root/'index.csv'), \
                mock.patch.dict(os.environ, {'IC_ARCHIVE_S3_URI':'s3://example/archive'}):
            row = fbarchive.store(fbarchive.build(13, 'prefix', 3, 1), max_git_bytes=0, chunk_bytes=73)
            paths = fbarchive.archive_paths(self.root/row['path'])
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                self.assertEqual(fbarchive.upload(True, True), 0)
            lines = capture.getvalue().splitlines()
            self.assertEqual(len(lines), len(paths)+1)
            for p in paths:
                self.assertTrue(any(str(p.relative_to(self.root)) in line for line in lines))


if __name__ == '__main__':
    unittest.main()
