"""Tests for the single-target online model (online.py)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import online  # noqa: E402
from online import FactorBase, ToyCurve, bench, replay_workload, weights_for  # noqa: E402


def collect(curve, family, l, targets, seed=1, workload_seed=1):
    import monitor
    import opcount

    _, w = bench.workload(curve, workload_seed, targets)
    args = SimpleNamespace(n=curve.n, m=2, l=l, family=family, seed=seed, mode="mxl", abort_degree=0,
                           max_attempts=200_000, workload_seed=workload_seed, descent_targets=targets,
                           report_every=0, out="", trace="", **bench.LIMITS)
    meter = opcount.Meter()
    return monitor.collect(args, workload=w, meter=meter), meter, w


class OnlineModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bench._warm_process()
        cls.cal = json.loads(bench.CALIBRATION.read_text())

    def test_per_target_cost_matches_collect(self):
        C = ToyCurve(13)
        weights = weights_for(self.cal, 13)
        for family, l in (("geomtraceu", 5), ("prefix", 5)):
            res, meter, w = collect(C, family, l, targets=12)
            fb = FactorBase(C, family, l, 1)
            pb = online.probe(fb, weights, fails=80, successes=30)
            attempts = replay_workload(fb, w)["descent_attempts"]
            self.assertEqual(attempts, [d["attempts"] for d in res["descents"]])
            measured = sum(sum(k * weights[c] for c, k in d["ops"].items()) for d in res["descents"])
            predicted = sum((a - 1) * pb["c_fail_ops"] + pb["c_success_ops"] + pb["c_recovery_ops"] for a in attempts)
            self.assertAlmostEqual(measured / predicted, 1.0, delta=0.1, msg=family)

    def test_lazy_target_path_skips_enumeration(self):
        C = ToyCurve(13)
        res, meter, _ = collect(C, "prefix", 5, targets=12)
        attempts = sum(d["attempts"] for d in res["descents"])
        N = 10
        full = (N + 2) * 2 ** (N - 1)
        self.assertLess(meter.ops["target_pdp"]["anf_op"], 0.5 * attempts * full)

    def test_psi_class_yield_and_planted_successes(self):
        from relations import predicted_yield

        C = ToyCurve(23)
        fb = FactorBase(C, "geomtraceu", 8, 5)
        exact = len(online.decomposable_points(fb)) / (C.r - 1)
        self.assertAlmostEqual(predicted_yield(fb, 2)["p_decomposable"] / exact, 1.0, delta=0.03)
        weights = weights_for(self.cal, 23)
        a = online.probe(fb, weights, fails=30, successes=20)
        b = online.probe(fb, weights, fails=30, successes=20, planted=True)
        self.assertAlmostEqual(b["c_success_ops"] / a["c_success_ops"], 1.0, delta=0.05)
        self.assertAlmostEqual(b["c_fail_ops"] / a["c_fail_ops"], 1.0, delta=0.05)

    def test_score_names_the_bench_candidate(self):
        C = ToyCurve(19)
        rec = online.score(C, "geomtraceu", 6, 4, weights_for(self.cal, 19), fails=20, successes=8, setup=False)
        fb = FactorBase(C, "geomtraceu", 6, 4)
        self.assertEqual(rec["candidate_id"], bench.candidate_manifest(C, fb, {"m": 2, "mode": "mxl"})[0])
        self.assertEqual(rec["kind"], "prediction")
        self.assertEqual(rec["cell"]["targets"], 1)
        self.assertGreater(rec["predicted"]["online_ratio_to_rho"], 1)


if __name__ == "__main__":
    unittest.main()
