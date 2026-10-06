"""The external.py archives are the bases the complete-DLP results used, digest for digest."""

from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))

import external  # noqa: E402
import fbarchive  # noqa: E402
from toycurve import sha256_hex  # noqa: E402

F4 = EXP / "f4-gpu-20260925"
HAMMING = EXP / "hamming-ic-e2e-20260929" / "runs"
CATALOG_N13 = EXP / "ic-candidate-catalog" / "measurements" / "2026-09-25" / "complete_n13_sat_candidate.json"


def archive(curve_id: str, family: str) -> dict:
    rows = [r for r in fbarchive.read_index() if r["curve_id"] == curve_id and r["family"] == family]
    assert len(rows) == 1, (curve_id, family, len(rows))
    return json.loads(fbarchive.decompress(HERE / rows[0]["path"]))


class F4GpuTest(unittest.TestCase):
    def test_archives_reproduce_the_cited_digests(self):
        aliases = {a["cited_sha256"]: a for a in fbarchive.read_aliases()}
        index = {r["factor_base_sha256"] for r in fbarchive.read_index()}
        for a2 in (0, 1):
            receipt = json.loads((F4 / "receipts" / "batch" / f"k{a2}-n23" / "f4_batch.json").read_text())
            manifests = [json.loads(p.read_text()) for p in sorted((F4 / "manifests").glob(f"IC1N23Cka{a2}*.json"))]
            self.assertEqual(len(manifests), 2)
            curve_id = manifests[0]["curve"]["curve_id"]
            doc = archive(curve_id, external.KERFROB)
            rec = doc["factor_base"]
            cited = receipt["factor_base_sha256"]
            self.assertEqual(external.rust_points_digest(doc["points"]), cited)
            self.assertEqual(rec["rust_points_sha256"], cited)
            self.assertEqual(len(doc["points"]), receipt["factor_base_points"])
            self.assertIn(aliases[cited]["factor_base_sha256"], index)
            self.assertEqual(aliases[cited]["factor_base_sha256"], doc["factor_base_sha256"])
            for m in manifests:
                fb = m["factor_base"]
                self.assertEqual(fb["enumerated_set_sha256"], cited)
                self.assertEqual(fb["usable_points_B"], rec["actual_usable_point_count"])
                self.assertEqual(fb["effective_columns"], rec["effective_columns"])
                self.assertEqual(fb["nominal_dimension"], rec["nominal_dimension"])
                self.assertEqual(fb["abscissae"], rec["abscissae"])
                self.assertEqual({k: v for k, v in m["curve"].items() if k != "curve_id"},
                                 {k: v for k, v in doc["curve"].items() if k != "curve_id"})
                self.assertEqual(m["field"], doc["field"])


class HammingN9Test(unittest.TestCase):
    def test_every_n9_run_used_the_archived_points(self):
        runs = sorted(HAMMING.glob("n9_*/candidate.json"))
        self.assertEqual(len(runs), 6)
        for path in runs:
            rec = json.loads(path.read_text())["record"]
            doc = archive(rec["curve"]["curve_id"], external.NBEXACT)
            fb = rec["factor_base"]
            self.assertEqual(doc["points"], fb["encoded_points"], path)
            self.assertEqual(doc["factor_base"]["enumerated_set_sha256"], fb["point_set_sha256"])
            self.assertEqual(doc["factor_base"]["effective_columns"], fb["effective_columns"])
            self.assertEqual(doc["factor_base"]["construction"]["params"]["normal_element"], fb["normal_element"])
            self.assertEqual(doc["field"], rec["field"])


class CatalogN13Test(unittest.TestCase):
    def test_complete_n13_candidate_used_the_archived_points(self):
        rec = json.loads(CATALOG_N13.read_text())["record"]
        doc = archive(rec["curve"]["curve_id"], external.NBSTRIDE)
        fb = rec["factor_base"]
        self.assertEqual(doc["points"], fb["encoded_points"])
        self.assertEqual(doc["factor_base"]["enumerated_set_sha256"], fb["point_set_sha256"])
        self.assertEqual(doc["factor_base"]["nominal_dimension"], fb["nominal_dimension"])
        self.assertEqual(doc["factor_base"]["effective_columns"], fb["effective_columns"])
        self.assertLessEqual({x for x, _ in doc["points"]}, set(fb["subspace_x_values"]))


class AliasTest(unittest.TestCase):
    def test_committed_aliases_verify(self):
        self.assertEqual(fbarchive.verify_aliases(fbarchive.read_index()), [])

    def test_wrong_alias_is_reported(self):
        rows = fbarchive.read_aliases()
        bad = [{**rows[0], "cited_sha256": "0" * 64}]
        with mock.patch.object(fbarchive, "read_aliases", return_value=bad):
            self.assertEqual(len(fbarchive.verify_aliases(fbarchive.read_index())), 1)

    def test_alias_counts_as_archived_only_when_its_archive_is_indexed(self):
        import refs

        with open(refs.ALIASES, newline="") as fh:
            cited = {r["cited_sha256"] for r in csv.DictReader(fh)}
        self.assertTrue(cited <= refs.archived())


class RebuildTest(unittest.TestCase):
    def test_external_rows_rebuild_exactly(self):
        rows = [r for r in fbarchive.read_index() if r["family"] in external.FAMILIES]
        self.assertEqual(len(rows), 4)
        for r in rows:
            self.assertEqual(fbarchive.verify_row(r, True, 20_000), [], r["path"])

    def test_points_are_on_curve_and_digest_matches(self):
        doc = fbarchive.build(9, external.NBEXACT, 2, 1)
        self.assertEqual(doc["factor_base"]["enumerated_set_sha256"], sha256_hex(doc["points"]))
        with self.assertRaises(ValueError):
            fbarchive.build(9, "prefix", 3, 1, extra={"a2": 0})


if __name__ == "__main__":
    unittest.main()
