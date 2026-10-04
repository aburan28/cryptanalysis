"""The interface crypto's ICMS uses to run one cell of this harness.

    python3 -m pytest experiments/ic-bench/test_icms_interface.py -q

ICMS (aburan28/crypto, docs/ic/measurement/README.md) runs a single cell as a
pinned, recorded measurement.  Its runner, tools/icms/adapters/cryptanalysis_cell.py,
imports bench.py, reads CALIBRATION, checks LIMITS against the spec, and calls
run_cell(cell, calibration) once in a fresh interpreter; its adapter,
tools/icms/adapters/cryptanalysis_ic_bench.py, reads the receipt fields listed
below.  A change here that renames or drops one of them breaks those
measurements silently on the crypto side, so this test fails first.  If the
change is intended, update both repositories together.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench  # noqa: E402

# The one-target cell the ICMS demonstration specs run (crypto
# docs/ic/measurement/specs/ca-k0n13-prefix-l3-m3.yaml); "run" is set by the runner.
CELL = {"n": 13, "m": 3, "l": 3, "family": "prefix", "seed": 1, "mode": "mxl", "workload_seed": 1,
        "targets": 1, "max_attempts": 200_000, "run": 1}

# The solver limits the ICMS specs pin as decomposition.solver.options.
LIMITS = {"d_max": 10, "max_cols": 40_000, "max_rows": 200_000}

PHASES = ("setup", "isogeny", "factor_base", "precompute", "queries", "pdp", "relation_check",
          "matrix_build", "relation_la", "target_descent", "recovery_check")

RECEIPT_KEYS = {
    "status", "verified_scalar", "subgroup_order", "total_operations", "S_rps",
    "phase_operations", "phase_wall_ns", "phase_counters", "counts", "stage", "cell",
    "rho_operations", "rho_floor_operations", "ratio_to_rho", "ratio_to_floor",
    "run_id", "candidate_id", "workload_id", "source_curve_ref", "schema_version", "kind",
    "operation_unit", "provenance", "resource_envelope", "instrument", "warm", "wall_ns", "peak_rss_bytes",
}
STAGE_KEYS = {"fb_points", "geometric_points", "effective_columns", "nominal_dimension", "factor_base_sha256",
              "exact_p_decomposable", "achievable_rank", "yield_per_query", "pdp_mac_ops_per_query"}
COUNT_KEYS = {"targets", "targets_verified", "ordinary_queries", "verified_relations", "pdp_attempts",
              "novel_rows", "final_rank"}
CELL_KEYS = {"family", "m", "mode"}

# What the runner does, verbatim in substance: a fresh interpreter, bench.py
# imported from this directory, the frozen calibration, one run_cell call.
RUNNER = """
import json, sys
sys.path.insert(0, sys.argv[1])
import bench
with open(bench.CALIBRATION, encoding="utf-8") as fh:
    calibration = json.load(fh)
out = bench.run_cell(json.loads(sys.argv[2]), calibration)
print(json.dumps(out, sort_keys=True, default=str))
"""


class IcmsInterfaceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([sys.executable, "-c", RUNNER, str(HERE), json.dumps(CELL)],
                              capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise AssertionError(f"the ICMS-style runner failed (exit {proc.returncode}):\n{proc.stderr}")
        cls.out = json.loads(proc.stdout)

    def test_module_attributes_the_runner_reads(self):
        self.assertEqual(dict(bench.LIMITS), LIMITS,
                         "the ICMS specs pin these solver limits; a change refuses every ICMS run of this harness")
        self.assertEqual(tuple(bench.PHASES), PHASES)
        calibration = json.loads(Path(bench.CALIBRATION).read_text())
        self.assertRegex(calibration["calibration_id"], r"^ICBCAL1h[0-9a-f]{12}$")
        self.assertTrue(callable(bench.run_cell))

    def test_run_cell_returns_the_receipt_the_adapter_reads(self):
        self.assertIn("receipt", self.out)
        rec = self.out["receipt"]
        self.assertEqual(RECEIPT_KEYS - set(rec), set())
        self.assertEqual(STAGE_KEYS - set(rec["stage"]), set())
        self.assertEqual(COUNT_KEYS - set(rec["counts"]), set())
        self.assertEqual(CELL_KEYS - set(rec["cell"]), set())
        for table in ("phase_operations", "phase_wall_ns", "phase_counters"):
            self.assertEqual(set(rec[table]), set(PHASES), table)
        # The two counter names the adapter reads: ec_add summed over the
        # phases is ICMS's count.group_additions, and the pdp phase's mac_op
        # is its metrics.solver.ops.
        counters = rec["phase_counters"]
        self.assertGreater(sum((c or {}).get("ec_add", 0) for c in counters.values()), 0)
        self.assertIn("mac_op", counters["pdp"])

    def test_one_target_cell_is_complete_and_its_phases_sum_to_the_total(self):
        rec = self.out["receipt"]
        self.assertEqual(rec["status"], "complete")
        self.assertTrue(rec["verified_scalar"])
        self.assertEqual(rec["counts"]["targets"], 1)
        self.assertEqual(rec["total_operations"], sum(rec["phase_operations"].values()))
        self.assertEqual(rec["run_id"], f'{rec["candidate_id"]}W{rec["workload_id"]}R1')

    def test_usable_and_geometric_points_are_reported_separately(self):
        # ICMS records fb_points as usable_points (B, subgroup-usable) and
        # geometric_points as signed_points; they differ on this base.
        stage = self.out["receipt"]["stage"]
        self.assertLess(stage["fb_points"], stage["geometric_points"])
        self.assertEqual(stage["fb_points"] % stage["effective_columns"], 0)


if __name__ == "__main__":
    unittest.main()
