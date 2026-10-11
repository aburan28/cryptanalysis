"""Checks of the factor-base archive: builders, round trip, tamper detection, S3 skipping.

    python3 -m pytest experiments/fb-archive -q
"""

from __future__ import annotations

import gzip
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fbarchive  # noqa: E402
from purepy import ECC2K130, PyKoblitz  # noqa: E402

from factor_base import FactorBase  # noqa: E402
from toycurve import ToyCurve, canonical, sha256_hex  # noqa: E402


class TempArchive:
    """Point fbarchive at an empty directory for the duration of a test."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [mock.patch.object(fbarchive, "HERE", root),
                        mock.patch.object(fbarchive, "INDEX", root / "index.csv")]
        for p in self.patches:
            p.start()
        return root

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()


class BuilderTest(unittest.TestCase):
    def test_pure_python_builder_matches_the_kernel_builder(self):
        for n, family, l in ((13, "prefix", 3), (13, "geomtrace", 3), (19, "random", 5), (19, "geomtraceu", 5)):
            C = ToyCurve(n)
            P = PyKoblitz(n, C.a2, (int(C.G[0]), int(C.G[1])), C.r, C.mod)
            self.assertEqual(P.curve_id, C.curve_id)
            doc = fbarchive.py_factor_base(P, family, l, 1, True, 10_000)
            self.assertEqual(doc["factor_base"], FactorBase(C, family, l, 1).record(), (n, family, l))

    def test_ecc2k130_curve(self):
        C = PyKoblitz.ecc2k130()
        self.assertEqual(C.h, 4)
        self.assertEqual(C.r, ECC2K130["r"])
        self.assertTrue(C.curve_id.startswith("EC1N131Ckb1h"))
        self.assertEqual(len(C.cofactor_torsion()), 4)
        self.assertTrue(all(C.smul(T, 4) is None for T in C.cofactor_torsion()))

    def test_ecc2k130_small_base(self):
        doc = fbarchive.build(131, "geomtraceu", 4, 1)
        rec = doc["factor_base"]
        self.assertEqual(rec["actual_usable_point_count"], len(doc["points"]))
        self.assertEqual(rec["enumerated_set_sha256"], sha256_hex(doc["points"]))
        C = PyKoblitz.ecc2k130()
        self.assertTrue(all(C.on_curve(tuple(p)) for p in doc["points"]))
        self.assertTrue(all(C.K.trace(b) == 0 for b in rec["construction"]["basis"]))

    def test_recipe_only_leaves_counts_unknown(self):
        rec = fbarchive.build(131, "prefix", 20, 1, points=False)["factor_base"]
        self.assertIsNone(rec["actual_usable_point_count"])
        self.assertIsNone(rec["effective_columns"])
        self.assertIsNone(rec["enumerated_set_sha256"])


class StoreVerifyTest(unittest.TestCase):
    def test_round_trip_and_tampering(self):
        with TempArchive() as root:
            doc = fbarchive.build(13, "prefix", 3, 1)
            row = fbarchive.store(doc)
            rows = fbarchive.read_index()
            self.assertEqual(len(rows), 1)
            self.assertEqual(fbarchive.verify_row(rows[0], True, 10_000), [])
            again = fbarchive.store(fbarchive.build(13, "prefix", 3, 1))
            self.assertEqual(again["file_sha256"], row["file_sha256"], "compression is not deterministic")
            path = root / row["path"]
            other = canonical(fbarchive.build(13, "random", 3, 1)).encode()
            path.write_bytes(gzip.compress(other, mtime=0))
            errors = fbarchive.verify_row(fbarchive.read_index()[0], False, 0)
            self.assertTrue(any("file SHA-256" in e for e in errors))
            self.assertTrue(any("record digest" in e for e in errors))

    def test_oversized_archives_go_to_large(self):
        with TempArchive():
            row = fbarchive.store(fbarchive.build(13, "random", 3, 1), max_git_bytes=10)
            self.assertEqual(row["storage"], "s3")
            self.assertTrue(row["path"].startswith("large/"))

    def test_committed_index_verifies(self):
        rows = fbarchive.read_index()
        self.assertTrue(rows)
        errors = [e for r in rows for e in fbarchive.verify_row(r, False, 0)]
        self.assertEqual(errors, [])


class UploadTest(unittest.TestCase):
    def test_skips_without_a_target(self):
        with mock.patch.dict(os.environ, {"IC_ARCHIVE_S3_URI": ""}):
            self.assertEqual(fbarchive.upload(dry_run=False, require=False), 0)
            self.assertEqual(fbarchive.upload(dry_run=False, require=True), 1)

    def test_skips_without_credentials(self):
        with mock.patch.dict(os.environ, {"IC_ARCHIVE_S3_URI": "s3://bucket/prefix"}), \
                mock.patch.object(fbarchive, "s3_client", return_value=(None, "no credentials")):
            self.assertEqual(fbarchive.upload(dry_run=False, require=False), 0)
            self.assertEqual(fbarchive.upload(dry_run=False, require=True), 1)

    def test_dry_run_plans_every_archive(self):
        with mock.patch.dict(os.environ, {"IC_ARCHIVE_S3_URI": "s3://bucket/prefix/"}), \
                mock.patch("builtins.print") as out:
            self.assertEqual(fbarchive.upload(dry_run=True, require=True), 0)
        lines = [c.args[0] for c in out.call_args_list]
        present = [r for r in fbarchive.read_index() if (HERE / r["path"]).exists()]
        self.assertEqual(len(lines), len(present) + 1)
        self.assertTrue(all("s3://bucket/prefix/factor-bases/" in s for s in lines))

    def test_rejects_a_non_s3_uri(self):
        with mock.patch.dict(os.environ, {"IC_ARCHIVE_S3_URI": "https://example.com"}):
            with self.assertRaises(ValueError):
                fbarchive.upload(dry_run=True, require=False)


if __name__ == "__main__":
    unittest.main()
