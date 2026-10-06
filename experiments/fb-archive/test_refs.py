"""refs.py check: every drift from index.csv + unarchived.csv fails, in both directions."""

from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import refs  # noqa: E402

A, B, C = ("a" * 64), ("b" * 64), ("c" * 64)


def run_check(cited, have, debt) -> int:
    with mock.patch.object(refs, "citations", return_value=cited), \
         mock.patch.object(refs, "archived", return_value=set(have)), \
         mock.patch.object(refs, "read_debt", return_value=dict(debt)), \
         mock.patch.object(sys, "argv", ["refs.py", "check"]):
        return refs.main()


class CheckTests(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(run_check({A: {"x"}, B: {"y"}}, {A}, {B: "e"}), 0)

    def test_new_unarchived_citation_fails(self):
        self.assertEqual(run_check({A: {"x"}, C: {"z"}}, {A}, {}), 1)

    def test_debt_that_is_now_archived_fails(self):
        self.assertEqual(run_check({A: {"x"}}, {A}, {A: "e"}), 1)

    def test_debt_no_longer_cited_fails(self):
        self.assertEqual(run_check({A: {"x"}}, {A}, {B: "e"}), 1)


class ScanTests(unittest.TestCase):
    def test_finds_nested_digests_in_json_jsonl_and_gzip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.json").write_text(json.dumps({"rows": [{"factor_base_sha256": A}]}))
            (root / "b.jsonl").write_text(json.dumps({"x": {"factor_base_sha256": B}}) + "\n")
            (root / "c.jsonl.gz").write_bytes(gzip.compress((json.dumps({"factor_base_sha256": C}) + "\n").encode()))
            (root / "d.json").write_text(json.dumps({"factor_base_sha256": "not-a-digest"}))
            self.assertEqual(refs.digests_in(root / "a.json"), {A})
            self.assertEqual(refs.digests_in(root / "b.jsonl"), {B})
            self.assertEqual(refs.digests_in(root / "c.jsonl.gz"), {C})
            self.assertEqual(refs.digests_in(root / "d.json"), set())

    def test_finds_point_set_digests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.json").write_text(json.dumps({"factor_base": {"point_set_sha256": A}, "base_digest": B}))
            (root / "b.jsonl").write_text(json.dumps({"enumerated_set_sha256": C}) + "\n")
            (root / "c.json").write_text(json.dumps({"base_sha256": A}))
            self.assertEqual(refs.digests_in(root / "a.json"), {A, B})
            self.assertEqual(refs.digests_in(root / "b.jsonl"), {C})
            self.assertEqual(refs.digests_in(root / "c.json"), set())

    def test_enumerated_set_digests_count_as_archived(self):
        import csv

        with open(refs.INDEX, newline="") as fh:
            row = next(csv.DictReader(fh))
        have = refs.archived()
        self.assertIn(row["factor_base_sha256"], have)
        self.assertIn(row["enumerated_set_sha256"], have)


if __name__ == "__main__":
    unittest.main()
