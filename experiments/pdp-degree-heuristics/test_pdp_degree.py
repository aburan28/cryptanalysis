"""Checks of the kernel, the degree definitions and the yield machinery against
independent pure-Python implementations.

    python3 -m pytest experiments/pdp-degree-heuristics -q
"""

from __future__ import annotations

import itertools
import random
import sys
import unittest
from math import comb
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))

import descend as reference_descent  # noqa: E402
import gf2n  # noqa: E402

import kernel  # noqa: E402
import macaulay  # noqa: E402
from descent import BooleanSystem, Pieces, xs_to_assignment  # noqa: E402
from factor_base import FactorBase, minimal_profile, product_profile, rank  # noqa: E402
from profile import predictions, workload  # noqa: E402
from relations import Oracle, classify_solution, exact_subgroup_yield, predicted_yield  # noqa: E402
from toycurve import ToyCurve  # noqa: E402


# ---------------------------------------------------------------- reference algebra
def ref_mul(p: set[int], a: int) -> set[int]:
    out: set[int] = set()
    for m in p:
        out ^= {m | a}
    return out


def ref_degree(p: set[int]) -> int:
    return max((bin(m).count("1") for m in p), default=-1)


def ref_key(m: int, N: int) -> tuple[int, int]:
    """Sort key making larger grevlex monomials larger (degree, then smaller integer)."""
    return (bin(m).count("1"), -m)


def ref_echelon(polys: list[set[int]], N: int) -> dict[int, set[int]]:
    """Leading monomial -> polynomial, by elimination on leading monomials."""
    basis: dict[int, set[int]] = {}
    for p in polys:
        p = set(p)
        while p:
            lm = max(p, key=lambda m: ref_key(m, N))
            if lm in basis:
                p ^= basis[lm]
            else:
                basis[lm] = p
                break
    return basis


def ref_standard(lms, N: int) -> int:
    return sum(1 for t in range(1 << N) if not any(lm & ~t == 0 for lm in lms))


def ref_scan(eqs: list[set[int]], N: int, S: int, mode: str, d_max: int) -> int | None:
    degs = [ref_degree(e) for e in eqs]
    for D in range(min(degs), d_max + 1):
        rows = []
        for e, d in zip(eqs, degs):
            for k in range(D - d + 1):
                for a in itertools.combinations(range(N), k):
                    rows.append(ref_mul(e, sum(1 << i for i in a)))
        basis = ref_echelon(rows, N)
        if mode == "mxl":
            while True:
                new = []
                for lm, p in basis.items():
                    if ref_degree(p) <= D - 1:
                        new += [ref_mul(p, 1 << j) for j in range(N)]
                grown = ref_echelon(list(basis.values()) + new, N)
                if len(grown) == len(basis):
                    break
                basis = grown
        if 0 in basis:
            return D if S == 0 else -1
        if S and ref_standard(basis, N) == S:
            return D
    return None


def random_system(rng: random.Random, N: int, n: int, d: int, density: int) -> BooleanSystem:
    masks: dict[int, int] = {}
    for _ in range(density):
        k = rng.randrange(0, d + 1)
        m = sum(1 << i for i in rng.sample(range(N), k))
        masks[m] = masks.get(m, 0) ^ rng.getrandbits(n)
    items = sorted((m, c) for m, c in masks.items() if c)
    return BooleanSystem(N, n, np.array([m for m, _ in items], dtype=np.uint32), np.array([c for _, c in items], dtype=np.uint64))


class KernelTests(unittest.TestCase):
    def test_field_and_curve_match_reference(self):
        for n in (13, 19, 31, 47):
            F = gf2n.GF2n(n)
            E = gf2n.Curve(F, 1)
            K = kernel.Field(n, F.mod)
            rng = random.Random(n)
            for _ in range(60):
                a, b = rng.getrandbits(n), rng.getrandbits(n) or 1
                self.assertEqual(K.mul(a, b), F.mul(a, b))
                self.assertEqual(K.inv(b), F.inv(b))
                self.assertEqual(K.trace(a), F.trace(a))
                P, Q = E.random_point(rng), E.random_point(rng)
                R = E.add(P, Q)
                got = K.add((P.x, P.y), (Q.x, Q.y))
                self.assertEqual(got, (kernel.INF_X, 0) if R.inf else (R.x, R.y))
                lifted = K.lift(P.x)
                self.assertIn(lifted, {(P.x, P.y), (P.x, P.x ^ P.y)})

    def test_echelon_rank_and_pivots(self):
        rng = random.Random(3)
        for cols in (7, 64, 65, 200):
            rows = [rng.getrandbits(cols) for _ in range(rng.randrange(1, 2 * cols))]
            ech = kernel.Echelon(cols)
            packed = np.zeros((len(rows), ech.words), dtype=np.uint64)
            for i, r in enumerate(rows):
                for w in range(ech.words):
                    packed[i, w] = (r >> (64 * w)) & ((1 << 64) - 1)
            ech.add(packed)
            basis: dict[int, int] = {}
            for v in rows:
                while v:
                    h = v.bit_length() - 1
                    if h in basis:
                        v ^= basis[h]
                    else:
                        basis[h] = v
                        break
            self.assertEqual(ech.rank, len(basis))
            self.assertEqual(sorted(ech.pivots().tolist()), sorted(basis))

    def test_moebius_and_standard_monomials(self):
        rng = random.Random(9)
        N = 7
        table = np.array([rng.getrandbits(5) for _ in range(1 << N)], dtype=np.uint64)
        values = [0] * (1 << N)
        for x in range(1 << N):
            for mono in range(1 << N):
                if mono & ~x == 0:
                    values[x] ^= int(table[mono])
        z, zeros = kernel.anf_zeros(table.copy(), N)
        self.assertEqual(z, values.count(0))
        self.assertEqual(sorted(zeros.tolist()), [x for x in range(1 << N) if values[x] == 0])
        lms = [rng.randrange(1, 1 << N) for _ in range(5)]
        self.assertEqual(kernel.count_standard(np.array(lms), N), ref_standard(lms, N))


class DegreeTests(unittest.TestCase):
    def test_scan_matches_reference_on_random_systems(self):
        rng = random.Random(11)
        checked = 0
        for trial in range(40):
            N = rng.randrange(3, 7)
            s = random_system(rng, N, rng.randrange(N, N + 5), 2 + trial % 2, 3 * N)
            if not s.equations:
                continue
            S, _ = s.solutions()
            eqs = [set(e.tolist()) for e in s.equations]
            for mode in macaulay.MODES:
                got = macaulay.degree_scan(s, S, macaulay.Limits(d_max=N + 1), mode=mode)
                want = ref_scan(eqs, N, S, mode, N + 1)
                self.assertEqual(got["D_solve"], want, (trial, mode, S))
                if got["status"] == "refuted":
                    self.assertEqual(S, 0)
                checked += 1
        self.assertGreater(checked, 40)

    def test_closure_never_exceeds_macaulay_degree(self):
        rng = random.Random(4)
        for _ in range(20):
            s = random_system(rng, 6, 8, 2, 20)
            if not s.equations:
                continue
            S, _ = s.solutions()
            a = macaulay.degree_scan(s, S, macaulay.Limits(d_max=7), mode="xl")["D_solve"]
            b = macaulay.degree_scan(s, S, macaulay.Limits(d_max=7), mode="mxl")["D_solve"]
            self.assertLessEqual(b, a)

    def test_semi_regular_series(self):
        # (1+t)^4 / (1+t^2)^2 = 1 + 4t + 4t^2 - 4t^3 + ...
        self.assertEqual(macaulay.semi_regular_series(4, [2, 2], 3), [1, 4, 4, -4])
        self.assertEqual(macaulay.semi_regular_dreg(4, [2, 2]), 3)
        self.assertEqual(macaulay.semi_regular_hilbert(4, [2, 2], 4), [1, 4, 4, 0, 0])
        self.assertEqual(macaulay.semi_regular_hilbert(10, [2] * 19, 4)[3:], [0, 0])
        rows, cols = macaulay.macaulay_shape(10, [2] * 3, 3)
        self.assertEqual((rows, cols), (3 * 11, sum(comb(10, k) for k in range(4))))

    def test_homogeneous_regularity_is_block_limited_for_two_summands(self):
        C = ToyCurve(19)
        fb = FactorBase(C, "random", 4, 1)
        s = Pieces(fb, 2).system(C.random_subgroup_point(random.Random(2))[1][0])
        # the m = 2 top parts are bilinear across the two blocks, so pure-block monomials
        # of degree <= l never enter the ideal: D_reg > l
        self.assertGreater(macaulay.homogeneous_regularity(s)["D_reg"], fb.l)


class FactorBaseTests(unittest.TestCase):
    def test_geometric_progressions_attain_the_product_bound(self):
        C = ToyCurve(23)
        for fam in ("prefix", "geometric"):
            fb = FactorBase(C, fam, 5, 1)
            self.assertEqual(product_profile(C.K, fb.basis, 3), minimal_profile(23, 5, 3))
        fb = FactorBase(C, "random", 5, 1)
        self.assertGreater(product_profile(C.K, fb.basis, 2)[1], 9)

    def test_frobenius_stable_subspace_and_folded_columns(self):
        C = ToyCurve(31)
        fb = FactorBase(C, "invariant", 5, 1)
        self.assertTrue(fb.frobenius_stable)
        self.assertEqual(rank(fb.basis + [C.K.sqr(v) for v in fb.basis]), 5)
        self.assertEqual(fb.effective_columns, fb.usable_points // (2 * 31))

    def test_columns_are_consistent_logs(self):
        C = ToyCurve(19)
        fb = FactorBase(C, "prefix", 5)
        rng = random.Random(1)
        for i in rng.sample(range(len(fb.xs)), 8):
            if fb.col_of[i] < 0:
                continue
            rep = fb.column_reps[fb.col_of[i]]
            Q = C.K.smul((int(fb.xs[i]), int(fb.ys[i])), C.proj_scalar)
            self.assertEqual(C.K.smul(rep, int(fb.col_coeff[i]) % C.r), Q)

    def test_record_digest_is_deterministic(self):
        C = ToyCurve(19)
        a, b = FactorBase(C, "random", 5, 7), FactorBase(C, "random", 5, 7)
        self.assertEqual(a.digest, b.digest)
        self.assertTrue(C.curve_id.startswith("EC1N19Ckb1h"))
        wid, rec, _ = workload(C, 1, 5)
        self.assertEqual(len(wid), 12)
        self.assertEqual(wid, workload(C, 1, 5)[0])


class DescentAndYieldTests(unittest.TestCase):
    def test_prefix_descent_matches_pdp_scaling(self):
        C = ToyCurve(19)
        for m, l in ((2, 5), (3, 3)):
            inst = reference_descent.make_instance(19, m, l, seed=4)
            s = Pieces(FactorBase(C, "prefix", l), m).system(inst.xR)
            self.assertEqual({int(a): int(c) for a, c in zip(s.masks, s.coeffs)}, inst.anf)

    def test_planted_decompositions_are_found_and_verified(self):
        C = ToyCurve(19)
        rng = random.Random(8)
        for fam in ("geometric", "random", "normal", "kertrace"):
            fb = FactorBase(C, fam, 5, 2)
            P = Pieces(fb, 2)
            idx = rng.sample(range(len(fb.xs)), 2)
            pts = [(int(fb.xs[i]), int(fb.ys[i])) for i in idx]
            if pts[0][0] == pts[1][0]:
                continue
            R = C.K.add(*pts)
            S, sols = P.system(R[0]).solutions()
            v = xs_to_assignment(fb, [p[0] for p in pts])
            self.assertIn(v, set(sols.tolist()))
            self.assertEqual(classify_solution(fb, 2, R, v)["status"], "verified")

    def test_oracle_and_exact_yield_over_every_subgroup_target(self):
        C = ToyCurve(13)
        for fam, m, l in (("prefix", 2, 4), ("kertrace", 2, 4), ("random", 3, 3)):
            fb = FactorBase(C, fam, l, 1)
            O = Oracle(fb, m)
            P = Pieces(fb, m)
            decomposable = 0
            R = C.G
            for k in range(1, C.r):
                if k > 1:
                    R = C.K.add(R, C.G)
                hit = O.ordered_count(R) > 0
                decomposable += hit
                if k % 97 == 0:
                    S, sols = P.system(R[0]).solutions()
                    alg = any(classify_solution(fb, m, R, v)["status"] in ("verified", "improper") for v in sols.tolist())
                    self.assertEqual(alg, hit)
            ex = exact_subgroup_yield(fb, m)
            self.assertEqual(ex["decomposable_targets"], decomposable)
            pr = predicted_yield(fb, m)
            self.assertLess(abs(pr["p_decomposable"] - ex["p_decomposable"]), 0.5 * ex["p_decomposable"] + 0.01)

    def test_linearization_rank_for_two_summands(self):
        C = ToyCurve(23)
        for fam in ("prefix", "random"):
            fb = FactorBase(C, fam, 6, 1)
            prof = product_profile(C.K, fb.basis, 2)
            st = Pieces(fb, 2).structure()
            self.assertEqual(st["omega"], 1 + prof[0] + prof[1])
            self.assertEqual(st["fallen_degree"], 1)
            pred = predictions(23, 2, 6, st)
            self.assertEqual(pred["linearization_excess"], 23 - prof[0] - prof[1])


if __name__ == "__main__":
    unittest.main()
