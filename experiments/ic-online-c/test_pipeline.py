"""The gain-graph solver and a complete small pipeline run (collection, logs, every online oracle, rho)."""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline  # noqa: E402
from pipeline import GainGraph, Setup, fixture_scalar, online_ic, online_rho, prepare, rerandomizer, rho_prepare  # noqa: E402

R = 1_000_003


class GainGraphTest(unittest.TestCase):
    def test_recovers_fixed_components_and_cancels_free_ones(self):
        rng = random.Random(5)
        x = [rng.randrange(R) for _ in range(12)]
        rows = []
        # component {0..5}: a tree plus one unbalanced cycle (x0 + x1 and x0 - x1 fix x0)
        for a, b, ca, cb in ((0, 1, 1, 1), (1, 2, 1, -1), (2, 3, 1, 1), (3, 4, -1, 1), (4, 5, 1, 1), (0, 1, 1, -1)):
            rows.append(([(a, ca % R), (b, cb % R)], (ca * x[a] + cb * x[b]) % R))
        # component {6, 7, 8}: a tree with only balanced information
        for a, b in ((6, 7), (7, 8)):
            rows.append(([(a, 1), (b, 1)], (x[a] + x[b]) % R))
        # column 9 fixed by a one-term row; 10, 11 untouched
        rows.append(([(9, 2)], 2 * x[9] % R))
        g = GainGraph(12, R, rows)
        for j in (0, 1, 2, 3, 4, 5, 9):
            self.assertEqual(g.log[j], x[j])
        for j in (6, 7, 8, 10, 11):
            self.assertIsNone(g.log[j])
        self.assertEqual(g.evaluate([(6, 1), (7, 1)]), (x[6] + x[7]) % R)
        self.assertEqual(g.evaluate([(6, 1), (8, R - 1)]), (x[6] - x[8]) % R)
        self.assertIsNone(g.evaluate([(6, 1), (8, 1)]))
        self.assertEqual(g.summary()["inconsistent_rows"], 0)


class PipelineTest(unittest.TestCase):
    def test_small_pipeline_end_to_end(self):
        st = Setup(23, "geomtraceu", 8, 1)
        g, pre = prepare(st, 1, 2.0, verbose=False)
        self.assertEqual(pre["graph"]["inconsistent_rows"], 0)
        self.assertGreater(pre["graph"]["solved_columns"], 0.8 * st.fb.effective_columns)
        C = st.C
        for index in range(3):
            s = fixture_scalar(C, index)
            Q = st.k.smul(C.G, s)[:2]
            a0 = rerandomizer(C, index)
            got = {v: online_ic(st, g, Q, a0, v, 100_000) for v in ("v1", "v0", "py")}
            for v, res in got.items():
                self.assertTrue(res["verified"], v)
                self.assertEqual(res["scalar"], s, v)
                self.assertEqual(sum(res["phases_ns"].values()), res["online_ns"], v)
            self.assertEqual(got["v1"]["attempt_index"], got["v0"]["attempt_index"])
            self.assertEqual(got["v1"]["attempt_index"], got["py"]["attempt_index"])
            rho = online_rho(st, Q, rho_prepare(st, f"test-rho|{index}"), 1 << 30)
            self.assertTrue(rho["verified"])
            self.assertEqual(rho["scalar"], s)

    def test_candidate_ids_follow_the_convention(self):
        st = Setup(19, "geomtraceu", 6, 1)
        ids = {v: pipeline.candidate_record(st, v, 1, 2.0)[0] for v in pipeline.VARIANTS}
        self.assertEqual(len(set(ids.values())), len(ids))
        for cid in ids.values():
            self.assertRegex(cid, rf"^IC1N19Ckb1fb{st.fb.usable_points}PDP2htRCwalkLAgraphTDpdpISO0h[0-9a-f]{{12}}$")


if __name__ == "__main__":
    unittest.main()
