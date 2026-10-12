"""Test for the common-factor cover (gcdcover.py)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gcdcover  # noqa: E402
import online  # noqa: E402
from gcdcover import FactorBase, ToyCurve  # noqa: E402


class GcdCoverTest(unittest.TestCase):
    def test_cover_bases_lie_in_V_and_yield_about_2_to_minus_delta(self):
        C = ToyCurve(19)
        V = FactorBase(C, "prefix", 9, 1)
        DV = {tuple(map(int, p)) for p in online.decomposable_points(V).tolist()}
        for delta in (1, 2):
            union = set()
            for W in gcdcover.cover_bases(C, 9, delta):
                pts = {tuple(map(int, p)) for p in online.decomposable_points(W).tolist()}
                self.assertTrue(pts <= DV)
                union |= pts
            frac = len(union) / len(DV)
            self.assertGreater(frac, 0.6 * 2 ** -delta)
            self.assertLess(frac, 2.0 * 2 ** -delta)


if __name__ == "__main__":
    unittest.main()
