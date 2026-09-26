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

import amortize  # noqa: E402
import bench  # noqa: E402
import compare  # noqa: E402
import opcount  # noqa: E402
import prime_bridge  # noqa: E402
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

    def test_history_migrates_pre_batch_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.csv"
            old_fields = bench.CSV_FIELDS[:bench.CSV_FIELDS.index("workload_series_id")]
            with path.open("w", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=old_fields, lineterminator="\n")
                writer.writeheader()
                writer.writerow({"bench_cell": "old", "ic_online_ns": "100",
                                 "rho_online_ns": "200", "online_speedup": "2"})
            bench.write_csv(path, [{"bench_cell": "new", "workload_series_id": "ICBW1h123"}], append=True)
            with path.open(newline="") as fh:
                reader = csv.DictReader(fh)
                self.assertEqual(reader.fieldnames, bench.CSV_FIELDS)
                rows = list(reader)
            self.assertEqual([row["bench_cell"] for row in rows], ["old", "new"])
            self.assertEqual(rows[0]["rho_online_ns"], "200")
            self.assertEqual(rows[0]["workload_series_id"], "")
            self.assertEqual(rows[1]["workload_series_id"], "ICBW1h123")

    def test_batch_rho_reference_and_prefixes(self):
        r, n = 130873, 19
        single = round((bench.math.pi * r / 2) ** 0.5)
        folded = round((bench.math.pi * r / (4 * n)) ** 0.5)
        self.assertEqual(bench.batch_rho_group_operations(r, 1), single)
        self.assertEqual(bench.batch_rho_group_operations(r, 1, 2 * n), folded)
        self.assertLess(bench.batch_rho_group_operations(r, 4), 4 * single)
        self.assertEqual(bench.batch_prefix_sizes(16), [1, 2, 4, 8, 16])
        self.assertEqual(bench.batch_prefix_sizes(13), [1, 2, 4, 8, 13])

    def test_workload_series_pairs_target_prefixes(self):
        curve = bench.ToyCurve(13)
        wid1, w1 = bench.workload(curve, 7, 1)
        wid4, w4 = bench.workload(curve, 7, 4)
        self.assertNotEqual(wid1, wid4)
        self.assertEqual(w1["targets"], w4["targets"][:1])
        self.assertEqual(bench.workload_series_id(curve, 7, "cold"),
                         bench.workload_series_id(curve, 7, "cold"))
        self.assertNotEqual(bench.workload_series_id(curve, 7, "cold"),
                            bench.workload_series_id(curve, 8, "cold"))


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
        self.assertEqual(rec["warm"]["shared_operations"] + rec["warm"]["target_operations"],
                         rec["total_operations"])
        self.assertEqual([p["targets"] for p in rec["warm"]["prefixes"]], [1, 2])
        self.assertEqual(rec["warm"]["prefixes"][-1]["ic_operations"], rec["total_operations"])
        self.assertEqual(rec["rho_batch"]["folded_shared_dp_expected_operations"],
                         rec["warm"]["folded_batch_rho_operations"])
        amortize.validate_receipt(rec)

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



class PrimeBridgeTest(unittest.TestCase):
    def report(self):
        ds = [
            {"expected": str(11+i), "target": {"x": str(20+i), "y": str(30+i)},
             "recovered": str(11+i), "verified": True, "ops": 40+i,
             "oracle_ops": 30+i, "probe_ops": 10, "trials": 2+i,
             "through_large_prime": True, "learned": 3, "restarts": 0, "seconds": 0.001}
            for i in range(4)
        ]
        return {
            "schema_version": 1, "operation": "prime", "status": "complete", "solver": "orbit",
            "curve_type": "j0",
            "instance": {"field_bits": 18, "p": "262147", "a": "0", "b": "7",
                "group_order": "262148", "cofactor": 4, "subgroup_order": "65537",
                "generator": {"x": "1", "y": "2"},
                "order_certificate": {"method": "test", "hasse_interval": ["1","2"], "bsgs_steps": 1},
                "endomorphism": {"automorphism_order": 6}},
            "configuration": {"solver": "orbit", "orbits_requested": 0, "width": 2.0,
                "orbits_per_target": 0.5, "relations_per_orbit": 1.5, "large_primes": True,
                "learn": True, "max_ops": 100000, "max_descent_ops": 10000,
                "rho_max_steps": 0, "skip_rho": False, "seed": 1},
            "factor_base": {"orbits": 8, "points": 48, "automorphism_order": 6,
                "certified_orbits": 8, "draws": 20, "sizing": "batch",
                "orbits_per_target": 0.5, "width": 2.0},
            "logs": {"collection": "large_primes", "trials": 20, "relations": 12,
                "rank": 8, "oracle_ops": 900, "probe_ops": 100, "seconds": 0.01},
            "descent": {"verified": 4, "mean_ops": 41.5, "total_ops": 166, "per_target": ds},
            "rho": {"verified": 4, "precompute_ops": 100, "mean_steps": 300.0,
                "mean_setup_ops": 55.0, "mean_ops": 355.0, "expected_steps": 321.0,
                "expected_steps_folded": 131.0, "per_target": []},
            "vs_rho": {"whole_process_vs_batch_rho": {"rho_ops_expected": 1000.0,
                "rho_ops_expected_folded": 500.0}},
            "elapsed_seconds": 0.02, "resources": {"peak_rss_bytes": 12345},
            "software": {"version": "0.1.0", "binary_blake3": "a"*64, "git_commit": "b"*40},
        }

    def test_prime_receipt_satisfies_common_contract(self):
        import analyze
        out = prime_bridge.normalize(self.report(), host="test")
        rec = out["receipt"]
        analyze.validate_run(copy.deepcopy(rec))
        self.assertTrue(rec["candidate_id"].startswith("IC1P18Cj0fb48PDP2orbitRClpLAgraphTDlearnISO0h"))
        self.assertEqual(rec["operation_unit"], "prime_group_operation")
        self.assertEqual(rec["total_operations"], 1166)
        self.assertEqual(rec["counts"]["final_rank"], 8)
        self.assertEqual(rec["warm"]["prefixes"][-1]["targets"], 4)
        self.assertEqual(rec["warm"]["prefixes"][-1]["ic_operations"], 1166)
        self.assertEqual(rec["descents"][0]["target"], {"x": "20", "y": "30"})
        def no_float(value):
            if isinstance(value, dict): return all(no_float(v) for v in value.values())
            if isinstance(value, list): return all(no_float(v) for v in value)
            return not isinstance(value, float)
        self.assertTrue(no_float(out["manifest"][1]))

    def test_prime_candidate_and_workload_are_deterministic(self):
        a = prime_bridge.normalize(self.report(), host="a")
        b = prime_bridge.normalize(self.report(), host="b")
        self.assertEqual(a["manifest"], b["manifest"])
        self.assertEqual(a["workload"], b["workload"])
        self.assertEqual(a["receipt"]["candidate_id"], b["receipt"]["candidate_id"])
        self.assertEqual(a["receipt"]["workload_id"], b["receipt"]["workload_id"])
        self.assertNotEqual(a["receipt"]["provenance"]["host_id"], b["receipt"]["provenance"]["host_id"])


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
