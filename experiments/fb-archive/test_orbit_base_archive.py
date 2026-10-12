"""The compressed n83 base must survive index verification and reject changed keys."""

import base64
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fbarchive  # noqa: E402
import orbit_base_archive  # noqa: E402


class OrbitBaseArchiveTest(unittest.TestCase):
    def test_index_round_trip_and_key_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(fbarchive, "HERE", root), \
                 mock.patch.object(fbarchive, "INDEX", root / "index.csv"):
                doc = orbit_base_archive.build_doc()
                row = orbit_base_archive.store_doc(doc)
                indexed = fbarchive.read_index()
                self.assertEqual(len(indexed), 1)
                self.assertEqual(indexed[0]["path"], row["path"])
                self.assertEqual(fbarchive.verify_row(indexed[0], True, 0), [])
                changed = dict(doc)
                keys = bytearray(base64.b64decode(doc[
                    "orbit_representatives_b64"]))
                keys[0] ^= 1
                changed["orbit_representatives_b64"] = base64.b64encode(
                    keys).decode("ascii")
                self.assertTrue(orbit_base_archive.verify_doc(
                    changed, indexed[0]))


if __name__ == "__main__":
    unittest.main()
