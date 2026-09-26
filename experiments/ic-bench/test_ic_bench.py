"""Checks of the metering, the receipts and the regression gate.

    python3 -m pytest experiments/ic-bench -q
"""

from __future__ import annotations

import copy
import csv
import json
import multiprocessing
import sys
import tempfile
import unittest
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "ic-candidate-catalog"))

import bench  # noqa: E402
import compare  # noqa: E402
import opcount  # noqa: E402
from calibrate import weights_for  # noqa: E402

CALIBRATION = json.loads(bench.CALIBRATION.read_text())
CELL = {"n": 13, "m": 3, "l": 3, "family": "prefix", "seed": 1, "mode": "mxl", "workload_seed": 1,
        "targets": 2, "max_attempts": 200_000, "suite": "test"}


def run_fresh(cells: list[dict]) -> list[dict]:
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=2, mp_context=ctx, initializer=bench._warm_process,
                             max_tasks_per_child=1) as pool:
        return list(pool.map(bench._worker, [(c, CALIBRATION) for c in cells]))


class MeterTest(unittest.TestCase):
    def test_phases_are_exclusive(self):
        meter = opcount.Meter()
        with meter.phase("pdp"):
            opcount.charge("mac_op", 5)
            with self.assertRaises(AssertionError):
                with meter.phase("queries"):
                    pass
        opcount.charge("mac_op", 7)
        self.assertEqual(meter.ops["pdp"], Counter({"mac_op": 5}))
        self.assertIsNone(opcount.COUNTS)

    def test_move_and_price(self):
        meter = opcount.Meter()
        with meter.phase("instrument"):
            opcount.charge("anf_op", 10)
            opcount.charge("gf_mul", 2)
        meter.move("instrument", "pdp", Counter({"anf_op": 4}), 0)
        self.assertEqual(meter.ops["instrument"], Counter({"anf_op": 6, "gf_mul": 2}))
        self.assertEqual(meter.priced({"anf_op": 3, "gf_mul": 100}), {"instrument": 218, "pdp": 12})
        with self.assertRaises(ValueError):
            meter.priced({"anf_op": 1})

    def test_smul_cost_matches_double_and_add(self):
        self.assertEqual([opcount.smul_cost(k) for k in (0, 1, 2, 3, 255)], [0, 2, 3, 4, 16])

    def test_calibration_prices_every_class(self):
        for n in (13, 19, 23):
            self.assertEqual(set(weights_for(CALIBRATION, n)), set(opcount.CLASSES))
            self.assertTrue(all(isinstance(w, int) and w > 0 for w in weights_for(CALIBRATION, n).values()))

    def test_history_migrates_existing_online_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.csv"
            old_fields = bench.CSV_FIELDS[:-3]
            with path.open("w", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(old_fields)
                writer.writerow(["old" if field == "bench_cell" else "" for field in old_fields])
                writer.writerow(["extended" if field == "bench_cell" else "" for field in old_fields] +
                                ["100", "200", "2"])
            bench.write_csv(path, [{"bench_cell": "new", "ic_online_ns": "300"}], append=True)
            with path.open(newline="") as fh:
                reader = csv.DictReader(fh)
                self.assertEqual(reader.fieldnames, bench.CSV_FIELDS)
                rows = list(reader)
            self.assertEqual([row["bench_cell"] for row in rows], ["old", "extended", "new"])
            self.assertEqual(rows[1]["rho_online_ns"], "200")
            self.assertEqual(rows[2]["ic_online_ns"], "300")


class ReceiptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outs = run_fresh([CELL, CELL])

    def test_receipt_satisfies_the_measurement_contract(self):
        import analyze

        rec = self.outs[0]["receipt"]
        analyze.validate_run(copy.deepcopy(rec))
        self.assertEqual(rec["status"], "complete")
        self.assertTrue(rec["verified_scalar"])
        self.assertEqual(rec["total_operations"], sum(rec["phase_operations"].values()))
        self.assertEqual(set(rec["phase_operations"]), set(bench.PHASES))
        self.assertEqual(rec["counts"]["targets_verified"], CELL["targets"])

    def test_identifiers_follow_the_convention(self):
        rec = self.outs[0]["receipt"]
        cid, manifest = self.outs[0]["manifest"]
        wid, wrec = self.outs[0]["workload"]
        self.assertRegex(cid, r"^IC1N13Ckb1fb[1-9][0-9]*PDP3xlRCsampleLAgaussTDpdpISO0h[0-9a-f]{12}$")
        self.assertEqual(cid[-12:], bench.sha256_hex(manifest)[:12])
        self.assertEqual(wid, bench.sha256_hex(wrec)[:12])
        self.assertEqual(rec["run_id"], f"{cid}W{wid}R1")
        self.assertEqual(int(cid.split("fb")[1].split("PDP")[0]),
                         manifest["factor_base"]["actual_usable_point_count"])
        self.assertNotIn("candidate_id", json.dumps(manifest))

    def test_counters_reproduce_in_a_fresh_process(self):
        a, b = (bench.csv_row(o["receipt"], "x", "t") for o in self.outs)
        self.assertEqual({k: a[k] for k in bench.DETERMINISTIC}, {k: b[k] for k in bench.DETERMINISTIC})
        self.assertEqual(self.outs[0]["manifest"], self.outs[1]["manifest"])

    def test_one_target_online_pair_is_verified_and_exclusive(self):
        import analyze

        cell = dict(bench.SUITES["primary"][0], suite="primary")
        rec = run_fresh([cell])[0]["receipt"]
        analyze.validate_run(copy.deepcopy(rec))
        self.assertEqual(rec["counts"]["targets"], 1)
        self.assertEqual(rec["counts"]["targets_verified"], 1)
        self.assertTrue(rec["rho_measured"]["verified"])
        self.assertEqual(rec["descents"][0]["scalar"], rec["rho_measured"]["scalar"])
        self.assertEqual(sum(rec["online"]["phase_wall_ns"].values()), rec["online"]["ic_online_ns"])
        self.assertAlmostEqual(rec["online"]["speedup"],
                               rec["online"]["rho_online_ns"] / rec["online"]["ic_online_ns"])


def row(cell="c1", total=1000, cid="IC1a", status="complete", verified="True", **kw):
    r = {"bench_cell": cell, "workload_id": "w1", "candidate_id": cid, "run_id": f"{cid}Ww1R1", "status": status,
         "verified": verified, "total_operations": str(total), "ordinary_queries": "10", "wall_ns": "1000000",
         "ops_pdp": str(total), "calibration_id": "ICBCAL1hx"}
    r.update(kw)
    return r


class CompareTest(unittest.TestCase):
    def test_identical_rows_pass(self):
        failures, _, _ = compare.compare([row()], [row()], 0.05)
        self.assertEqual(failures, [])

    def test_regression_beyond_tolerance_fails(self):
        failures, _, _ = compare.compare([row()], [row(total=1100, cid="IC1b", ops_pdp="1100")], 0.05)
        self.assertTrue(any("exceeds tolerance" in f for f in failures))

    def test_change_within_tolerance_passes_with_a_note(self):
        failures, notes, _ = compare.compare([row()], [row(total=1030, cid="IC1b", ops_pdp="1030")], 0.05)
        self.assertEqual(failures, [])
        self.assertTrue(any("candidate changed" in n for n in notes))

    def test_same_candidate_with_different_counters_is_nondeterminism(self):
        failures, _, _ = compare.compare([row()], [row(total=1001, ops_pdp="1001")], 0.05)
        self.assertTrue(any("nondeterminism" in f for f in failures))

    def test_unverified_or_missing_runs_fail(self):
        failures, _, _ = compare.compare([row()], [row(status="error", verified="False", total="")], 0.05)
        self.assertTrue(any("status error" in f for f in failures))
        failures, _, _ = compare.compare([row(), row(cell="c2")], [row()], 0.05)
        self.assertTrue(any("c2: missing" in f for f in failures))
        failures, _, _ = compare.compare([row()], [row(workload_id="w2")], 0.05)
        self.assertTrue(any("workload changed" in f for f in failures))


class BaselineTest(unittest.TestCase):
    def test_committed_baseline_is_complete_and_named(self):
        path = HERE / "baseline" / "ci.csv"
        if not path.exists():
            self.skipTest("no recorded baseline")
        rows = compare.read(path)
        self.assertEqual({r["bench_cell"] for r in rows}, {bench.cell_label(c) for c in bench.SUITES["ci"]})
        for r in rows:
            self.assertEqual((r["status"], r["verified"]), ("complete", "True"))
            self.assertTrue(r["run_id"].startswith(f"{r['candidate_id']}W{r['workload_id']}R"))
            self.assertTrue((HERE / "candidates" / f"{r['candidate_id']}.json").exists())
            self.assertTrue((HERE / "workloads" / f"{r['workload_id']}.json").exists())


if __name__ == "__main__":
    unittest.main()
