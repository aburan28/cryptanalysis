"""Tests for the factor-base search: the exact replay, the rank-process law, the trace identity
behind the trace-zero trade-off, and the naming of scored bases."""

from __future__ import annotations

import random
import re
import statistics
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import search  # noqa: E402
from search import FactorBase, ToyCurve, achievable_rank, bench, rank_process, replay_workload  # noqa: E402

IC1 = re.compile(r"^IC1N\d+Ckb1fb[1-9]\d*PDP2xlRCsampleLAgaussTDpdpISO0h[0-9a-f]{12}$")


class ReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bench._warm_process()
        cls.C = ToyCurve(13)

    def test_replay_matches_collection_run(self):
        import monitor

        for fam in ("prefix", "geomtraceu", "random"):
            wid, w = bench.workload(self.C, 1, 2)
            args = SimpleNamespace(n=13, m=2, l=4, family=fam, seed=1, mode="mxl", abort_degree=0,
                                   max_attempts=200_000, workload_seed=1, descent_targets=2, report_every=0,
                                   out="", trace="", **bench.LIMITS)
            res = monitor.collect(args, workload=w)
            rp = replay_workload(FactorBase(self.C, fam, 4, 1), w)
            self.assertEqual(rp["collection_queries"], res["monitor"]["attempts"], fam)
            self.assertEqual(rp["final_rank"], res["final_rank"], fam)
            self.assertEqual(rp["descent_attempts"], [d["attempts"] for d in res["descents"]], fam)

    def test_rank_process_mean_matches_replays(self):
        fb = FactorBase(self.C, "prefix", 4, 1)
        target = achievable_rank(fb, 2)
        law = rank_process(fb, target, runs=2000)
        reps = [replay_workload(fb, bench.workload(self.C, s, 0)[1])["collection_queries"] for s in range(1, 301)]
        se = law["sd"] / len(reps) ** 0.5
        self.assertLess(abs(statistics.fmean(reps) - law["mean"]), 4 * se + 0.02 * law["mean"])


class TraceIdentityTest(unittest.TestCase):
    """Tr(S_3(x1, x2, x3) / x3^2) = Tr(x1) + Tr(x2) + Tr(1/x3) on y^2 + xy = x^3 + 1, and Tr(1/x) = 0
    for every subgroup point, so a trace-zero base loses the one linear equation it implies."""

    def test_identity(self):
        C = ToyCurve(19)
        K = C.K
        rng = random.Random(7)
        for _ in range(200):
            x1, x2, x3 = (rng.randrange(1, 1 << 19) for _ in range(3))
            e = K.mul(x1, x2) ^ K.mul(x1, x3) ^ K.mul(x2, x3)
            s3 = K.sqr(e) ^ K.mul(K.mul(x1, x2), x3) ^ 1
            lhs = K.trace(K.mul(s3, K.inv(K.sqr(x3))))
            self.assertEqual(lhs, K.trace(x1) ^ K.trace(x2) ^ K.trace(K.inv(x3)))
        for _ in range(50):
            _, R = C.random_subgroup_point(rng)
            self.assertEqual(K.trace(K.inv(R[0])), 0)

    def test_trace_zero_base_loses_an_equation(self):
        from descent import Pieces
        from factor_base import reduce_basis

        C = ToyCurve(19)
        rng = random.Random(3)
        for fam in ("geomtraceu", "kertrace"):
            P = Pieces(FactorBase(C, fam, 6, 1), 2)
            for _ in range(20):
                _, R = C.random_subgroup_point(rng)
                s = P.system(R[0])
                idx = {int(m): i for i, m in enumerate(s.masks.tolist())}
                rank = len(reduce_basis(sum(1 << idx[int(m)] for m in eq.tolist()) for eq in s.equations))
                self.assertLessEqual(rank, C.n - 1, fam)


class NamingTest(unittest.TestCase):
    def test_score_is_labelled_with_the_bench_candidate(self):
        C = ToyCurve(13)
        rec = search.score(C, "geomtraceu", 4, 2, runs=50)
        self.assertRegex(rec["candidate_id"], IC1)
        fb = FactorBase(C, "geomtraceu", 4, 2)
        cid, manifest = bench.candidate_manifest(C, fb, {"m": 2, "mode": "mxl"})
        self.assertEqual(rec["candidate_id"], cid)
        self.assertEqual(manifest["factor_base"]["construction"]["params"]["seed"], 2)
        self.assertEqual(rec["kind"], "prediction")
        self.assertTrue(rec["curve_id"].startswith("EC1N13Ckb1h"))
        self.assertTrue(rec["stage"]["trace_zero"])

    def test_search_cells_carry_the_seed(self):
        import json
        import tempfile

        doc = {"picks": [{"cell": {"n": 19, "m": 2, "l": 6, "family": "geomtraceu", "seed": 4, "mode": "mxl",
                                   "targets": 3}}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(doc, fh)
        cells = bench.search_cells(Path(fh.name))
        self.assertEqual([c["seed"] for c in cells], [4, 4, 4])
        self.assertEqual({bench.cell_label(c) for c in cells},
                         {f"n19m2l6-geomtraceu-s4-mxl-w{w}" for w in (1, 2, 3)})


if __name__ == "__main__":
    unittest.main()
