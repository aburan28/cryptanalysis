"""Tests for the half-trace projection solver (halftrace.py)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import halftrace  # noqa: E402
from halftrace import FactorBase, HalfTraceSolver, ToyCurve  # noqa: E402
from search import decomposition_lookup  # noqa: E402


class HalfTraceTest(unittest.TestCase):
    def test_artin_schreier_identity_on_genuine_zeros(self):
        """p = XY satisfies (p/S)^2 + p/S = (u + 1/S)^2 with u = X + Y whenever P1 + P2 = R."""
        import kernel

        C = ToyCurve(19)
        K = C.K
        rng = random.Random(5)
        checked = 0
        while checked < 200:
            P1, P2 = K.lift(rng.getrandbits(19)), K.lift(rng.getrandbits(19))
            if P1 is None or P2 is None:
                continue
            R = K.add(P1, P2)
            if R[0] in (kernel.INF_X, 0):
                continue
            X, Y, S = P1[0], P2[0], R[0]
            F = K.mul(K.mul(X, Y), K.inv(S))
            g = (X ^ Y) ^ K.inv(S)
            self.assertEqual(K.sqr(F) ^ F, K.sqr(g))
            checked += 1

    def test_finds_exactly_the_true_decompositions(self):
        """Against the exact pair table: same set of {P1, P2} for decomposable and random targets."""
        for n, l, fam, seed in ((19, 6, "geomtraceu", 4), (19, 7, "prefix", 1), (19, 6, "random", 2),
                                (23, 8, "geometric", 1)):
            C = ToyCurve(n)
            fb = FactorBase(C, fam, l, seed)
            sv = HalfTraceSolver(fb)
            truth = decomposition_lookup(fb)
            rng = random.Random(f"t|{n}|{l}|{fam}")
            pts = list(truth)
            targets = [pts[rng.randrange(len(pts))] for _ in range(25)]
            for _ in range(25):
                targets.append(C.random_subgroup_point(rng)[1])
            for R in targets:
                self.assertEqual(bool(sv.decompose(R)), R in truth, (n, l, fam, R))

    def test_residual_dimension_law(self):
        """mean residual dim = max(0, dim V + dim V^(2) - n - 1 + [V in ker Tr]) at negative excess."""
        C = ToyCurve(19)
        for fam, l in (("prefix", 8), ("geometric", 8), ("geomtraceu", 8), ("prefix", 9)):
            fb = FactorBase(C, fam, l, 1)
            sv = HalfTraceSolver(fb)
            tz = all(C.K.trace(b) == 0 for b in fb.basis)
            pred = max(0, l + sv.dim_V2 - C.n - 1 + int(tz))
            rng = random.Random(fam)
            dims = [sv.candidates(C.random_subgroup_point(rng)[1][0])[1] for _ in range(60)]
            self.assertAlmostEqual(sum(dims) / len(dims), pred, delta=0.25, msg=(fam, l))

    def test_residual_system_solvable_iff_decomposable(self):
        import macaulay
        from residual import residual_systems

        C = ToyCurve(19)
        fb = FactorBase(C, "geomtraceu", 8, 1)
        sv = HalfTraceSolver(fb)
        truth = decomposition_lookup(fb)
        rng = random.Random("residual-test")
        pts = list(truth)
        targets = [pts[rng.randrange(len(pts))] for _ in range(6)] + [C.random_subgroup_point(rng)[1] for _ in range(6)]
        for R in targets:
            solved = False
            for rs in residual_systems(sv, R[0]):
                s = rs["system"]
                scan = macaulay.degree_scan(s, lambda s=s: s.solutions()[0], macaulay.Limits(d_max=6), mode="mxl")
                solved |= scan["status"] == "solved"
            self.assertEqual(solved, R in truth)

    def test_plain_certificate_refutes_iff_no_decomposition(self):
        """A plain t-Macaulay identity sum m g_m = 1 exists at D = 4 only on branches without a solution."""
        from certificate import certificate
        from residual import boolean_equations, residual_systems

        C = ToyCurve(19)
        fb = FactorBase(C, "geomtraceu", 8, 1)
        sv = HalfTraceSolver(fb)
        truth = decomposition_lookup(fb)
        rng = random.Random("certificate-test")
        pts = list(truth)
        targets = [pts[rng.randrange(len(pts))] for _ in range(5)] + [C.random_subgroup_point(rng)[1] for _ in range(5)]
        for R in targets:
            refuted_all = True
            for rs in residual_systems(sv, R[0]):
                res = certificate(rs["N"], fb.l, boolean_equations(sv.n, rs["mono"]), "t", 4)
                refuted_all &= res["refuted"]
            self.assertEqual(refuted_all, R not in truth, R)

    def test_cheaper_than_macaulay_per_attempt(self):
        import json

        import online
        from calibrate import weights_for

        cal = json.loads(online.bench.CALIBRATION.read_text())
        fb = FactorBase(ToyCurve(19), "geomtraceu", 6, 4)
        w = weights_for(cal, 19)
        ht = halftrace.probe(fb, w, fails=40, successes=15)
        mac = online.probe(fb, w, 20, 8, planted=True)
        self.assertLess(ht["c_fail_ops"] * 5, mac["c_fail_ops"])


if __name__ == "__main__":
    unittest.main()
