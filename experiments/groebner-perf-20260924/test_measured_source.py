import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import measured_source


class SourceTests(unittest.TestCase):
    def test_exact_live_historical_missing_and_corrupt_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.py'
            old, new = b'old measured bytes\n', b'current source\n'
            digest = hashlib.sha256(old).hexdigest()
            source.write_bytes(old)
            with patch.object(measured_source, 'ARCHIVE', root):
                self.assertEqual(measured_source.measured_bytes(source, digest), old)
                source.write_bytes(new)
                with self.assertRaises(FileNotFoundError):
                    measured_source.measured_bytes(source, digest)
                archive = root / (digest + '.gz')
                archive.write_bytes(gzip.compress(old))
                self.assertEqual(measured_source.measured_bytes(source, digest), old)
                self.assertEqual(source.read_bytes(), new)
                archive.write_bytes(gzip.compress(new))
                with self.assertRaises(ValueError):
                    measured_source.measured_bytes(source, digest)
                with self.assertRaises(ValueError):
                    measured_source.measured_bytes(source, '../not-a-digest')


if __name__ == '__main__':
    unittest.main()
