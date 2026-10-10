"""Tests for the residual-structure ablations (ablation.py)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ablation  # noqa: E402
from residual import FactorBase, HalfTraceSolver, ToyCurve, residual_systems  # noqa: E402

N, L = 19, 8


def _evaluate(mono: dict[int, int], a: int, t: int) -> int:
    x = a | (t << L)
    out = 0
    for m, c in mono.items():
        if m & x == m:
            out ^= c
    return out


def _systems(count: int) -> list[dict]:
    C = ToyCurve(N)
    sv = HalfTraceSolver(FactorBase(C, "prefix", L, 1))
    rng = random.Random("test-ablation")
    out: list[dict] = []
    while len(out) < count:
        _, R = C.random_subgroup_point(rng)
        out += [rs for rs in residual_systems(sv, R[0]) if rs["d"] >= 2]
    return out[:count]


class AblationTest(unittest.TestCase):
    def test_swap_symmetry_holds_exactly_for_S_and_A5(self):
        rng = random.Random(7)
        for rs in _systems(3):
            d = rs["d"]
            for kind in ("S", "A3", "A5", "A6"):
                mono = ablation.variant_mono(rs, L, kind, random.Random(f"{kind}|{rs['eps']}"))
                u0, fs = ablation.LAST_D
                symmetric = True
                for _ in range(64):
                    a, t = rng.getrandbits(L), rng.getrandbits(d)
                    D = u0
                    for k in range(d):
                        if (t >> k) & 1:
                            D ^= fs[k]
                    if _evaluate(mono, a, t) != _evaluate(mono, a ^ D, t):
                        symmetric = False
                        break
                self.assertEqual(symmetric, kind in ("S", "A5"), kind)

    def test_swap_map_squares_on_span_only(self):
        rng = random.Random(3)
        span = [rng.getrandbits(L) for _ in range(4)]
        img = ablation._swap_symmetric_map(L, span, rng)

        def apply(v: int) -> int:
            r = 0
            for i in range(L):
                if (v >> i) & 1:
                    r ^= img[i]
            return r

        for f in span:
            self.assertEqual(apply(f), ablation._sq(f))
        self.assertTrue(any(apply(1 << i) != ablation._sq(1 << i) for i in range(L)))


if __name__ == "__main__":
    unittest.main()
