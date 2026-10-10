"""Tests for the non-subspace two-point check (nonsubspace.py)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import nonsubspace  # noqa: E402
from nonsubspace import ToyCurve  # noqa: E402


class NonSubspaceTest(unittest.TestCase):
    def test_progression_meets_the_bound_and_no_family_beats_it(self):
        C = ToyCurve(19)
        for fam in nonsubspace.FAMILIES:
            p = nonsubspace.profile(C, nonsubspace.family_set(C, fam, 8, random.Random(fam)))
            self.assertGreaterEqual(p["excess"], 0, fam)
            self.assertGreaterEqual(p["dim_span_sq"], min(19, 2 * p["dim_span"] - 1), fam)
            if fam == "progression":
                self.assertEqual((p["dim_span"], p["dim_span_sq"], p["excess"]), (8, 15, 0))
            else:
                self.assertGreater(p["excess"], 0, fam)


if __name__ == "__main__":
    unittest.main()
