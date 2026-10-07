"""Exactness of the C kernels against the Python half-trace solver, and the curve helpers."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import htfast  # noqa: E402
from htfast import FactorBase, Kernel, Walk, WalkV0, curve  # noqa: E402

CASES = [(19, "prefix", 6), (19, "geomtraceu", 7), (19, "random", 8), (23, "geomtraceu", 9), (23, "prefix", 10),
         (23, "kertrace", 11)]


def _pairs(hits) -> dict[int, set]:
    out: dict[int, set] = {}
    for h in hits.tolist():
        out.setdefault(int(h[0]), set()).add(frozenset({(h[3], h[4]), (h[5], h[6])}))
    return out


class HtFastTest(unittest.TestCase):
    def test_v1_and_v0_find_exactly_the_python_decompositions(self):
        for n, fam, l in CASES:
            C = curve(n)
            fb = FactorBase(C, fam, l, 1)
            k = Kernel(fb)
            rng = random.Random(f"htfast|{n}|{fam}|{l}")
            P0 = C.random_subgroup_point(rng)[1]
            step = C.random_subgroup_point(rng)[1]
            W, rounds = 16, 40
            walk = Walk(k, P0, step, W)
            v1 = _pairs(walk.run(rounds, False))
            v0w = WalkV0(k, P0, step)
            v0 = _pairs(v0w.run(W * rounds, False))
            R, py = P0, {}
            for i in range(1, W * rounds + 1):
                R = C.K.add(R, step)
                pairs = k.sv.decompose(R)
                if pairs:
                    py[i] = {frozenset(p) for p in pairs}
            with self.subTest(n=n, family=fam, l=l):
                self.assertTrue(py, "no decomposition in the walk")
                self.assertEqual(set(v1), set(py))
                self.assertEqual(set(v0), set(py))
                for i, got in v1.items():
                    self.assertLessEqual(got, py[i])
                    self.assertEqual(got, v0[i])
                self.assertEqual(int(walk.stats[4]), W * rounds)

    def test_curve_helpers(self):
        C = curve(23)
        k = Kernel(FactorBase(C, "prefix", 8, 1))
        rng = random.Random(1)
        for _ in range(5):
            s = rng.randrange(1, C.r)
            self.assertEqual(k.smul(C.G, s)[:2], C.K.smul(C.G, s))
            A, B = C.random_subgroup_point(rng)[1], C.random_subgroup_point(rng)[1]
            self.assertEqual(k.add(A, B)[:2], C.K.add(A, B))
        self.assertEqual(k.smul(C.G, C.r)[2], 1)


if __name__ == "__main__":
    unittest.main()
