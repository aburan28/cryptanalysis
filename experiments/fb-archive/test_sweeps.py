"""Sweep archives rebuild from the experiments' inputs and recount to their recorded cells."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sweeps  # noqa: E402
from purepy import PyField, PyKoblitz  # noqa: E402


class CounterTest(unittest.TestCase):
    def test_matches_direct_trace_count(self):
        K = PyField(19, sweeps.VIC_MOD)
        ctr = sweeps.Counter(19, sweeps.VIC_MOD)
        basis = [0x5A5A5, 0x1234, 0x7F00F, 0x0F0F1, 0x30303, 0x4C0C3, 0x11111]
        for b in (1, 0x2B, 0x7FFFF, 0x40001):
            got = ctr.counts(b, basis, [3, 5, 7])
            for k in (3, 5, 7):
                xs = ctr.span(tuple(basis[:k]), k)[0]
                want = sum(1 for x in xs[1:] if K.trace(x ^ K.mul(b, K.inv(K.sqr(x)))) == 0)
                self.assertEqual(got[k], want, (b, k))

    def test_m83_e0_polynomial_counts(self):
        ctr = sweeps.Counter(83, sweeps.M83_MOD)
        self.assertEqual(ctr.counts(1, [1 << i for i in range(10)], [8, 9, 10]), {8: 131, 9: 270, 10: 524})


class ArchiveTest(unittest.TestCase):
    def test_committed_sweeps_verify(self):
        rows = sweeps.read_index()
        self.assertEqual({r["name"] for r in rows}, set(sweeps.BUILDERS))
        for r in rows:
            self.assertEqual(sweeps.verify_sweep(r, 25), [], r["name"])

    def test_cell_and_curve_counts(self):
        want = {"volcano-m83": (6475, 1_243_200), "ecc2k130-isogeny-class": (789, 97_836), "volcano-ic": (457, 457)}
        for name, (curves, cells) in want.items():
            doc = sweeps.load(name)
            self.assertEqual(len(doc["curves"]), curves)
            self.assertEqual(doc["cells"]["count"], cells)
            self.assertIsNone(doc["points"])
            self.assertIsNone(doc["factor_base"]["actual_usable_point_count"])

    def test_ecc2k130_e0_has_the_archive_curve_id(self):
        e0 = sweeps.load("ecc2k130-isogeny-class")["curves"][0]
        self.assertEqual(e0["label"], "E0")
        self.assertEqual(e0["curve_id"], PyKoblitz.ecc2k130().curve_id)

    def test_wrong_recorded_count_is_reported(self):
        row = next(r for r in sweeps.read_index() if r["name"] == "volcano-ic")
        real = sweeps.vic_recorded
        bad = lambda: {k: v + (k[0] == "E0") for k, v in real().items()}  # noqa: E731
        with mock.patch.dict(sweeps.BUILDERS, {"volcano-ic": (sweeps.build_vic, bad)}):
            errors = sweeps.verify_sweep(row, None)
        self.assertEqual(len(errors), 1)
        self.assertIn("'E0'", errors[0])

    def test_changed_input_is_reported(self):
        row = next(r for r in sweeps.read_index() if r["name"] == "volcano-ic")
        real = sweeps.build_vic

        def shifted():
            doc = real()
            doc["curves"][1]["b"] ^= 1
            return doc

        with mock.patch.dict(sweeps.BUILDERS, {"volcano-ic": (shifted, sweeps.vic_recorded)}):
            errors = sweeps.verify_sweep(row, 5)
        self.assertTrue(any("different content" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
