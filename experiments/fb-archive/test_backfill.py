"""backfill.py collects every digest key refs.py guards, with its recipe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import backfill  # noqa: E402

A, B, C, D, E = ("a" * 64), ("b" * 64), ("c" * 64), ("d" * 64), ("e" * 64)
R = (19, "prefix", 4, 1)
CELL = {"n": 19, "family": "prefix", "l": 4, "seed": 1}


def collected(obj) -> dict:
    out: dict = {}
    backfill.collect(obj, None, out)
    return out


class CollectTests(unittest.TestCase):
    def test_records_all_digest_keys_beside_a_recipe(self):
        row = {"cell": CELL, "factor_base_sha256": A,
               "factor_base": {"enumerated_set_sha256": B, "point_set_sha256": C},
               "base_digest": D, "factor_base_point_set_sha256": E}
        self.assertEqual(collected(row), {A: {R}, B: {R}, C: {R}, D: {R}, E: {R}})

    def test_inherits_recipe_from_ancestors_and_recipe_key(self):
        nested = {"cell": CELL, "child": {"factor_base": {"enumerated_set_sha256": A}}}
        self.assertEqual(collected(nested), {A: {R}})
        legacy = {"recipe": CELL, "factor_base_sha256": B}
        self.assertEqual(collected(legacy), {B: {R}})

    def test_ignores_nondigests_missing_keys_and_recipeless_rows(self):
        self.assertEqual(collected({"cell": CELL, "factor_base_sha256": "not-a-digest"}), {})
        self.assertEqual(collected({"cell": CELL, "base_sha256": A}), {})
        self.assertEqual(collected({"factor_base_sha256": A}), {})
        self.assertEqual(collected({"cell": {"n": 19}, "factor_base_sha256": A}), {})


class DocDigestsTests(unittest.TestCase):
    def test_record_and_enumerated_digests(self):
        doc = {"factor_base_sha256": A, "factor_base": {"enumerated_set_sha256": B}}
        self.assertEqual(backfill.doc_digests(doc), {A, B})

    def test_tolerates_recipe_only_rows(self):
        doc = {"factor_base_sha256": A, "factor_base": {"enumerated_set_sha256": None}}
        self.assertEqual(backfill.doc_digests(doc), {A})
        self.assertEqual(backfill.doc_digests({"factor_base_sha256": A}), {A})


if __name__ == "__main__":
    unittest.main()
