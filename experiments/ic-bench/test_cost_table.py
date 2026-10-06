"""Accounting checks for the Table 1 style IC report."""

import copy
import json
import unittest
from pathlib import Path

import cost_table

HERE = Path(__file__).resolve().parent


class CostTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads((HERE / "baseline" / "primary.jsonl").read_text().splitlines()[0])

    def test_binary_costs_come_from_exclusive_charged_phases(self):
        rec = self.receipt
        out = cost_table.measure(rec)
        ops = rec["phase_operations"]
        self.assertEqual(out["queries"], rec["counts"]["ordinary_queries"])
        self.assertEqual(out["collection_ops"], sum(ops[k] for k in cost_table.COLLECTION))
        self.assertEqual(out["matrix_ops"], sum(ops[k] for k in cost_table.MATRIX))
        self.assertAlmostEqual(out["mean_H_ops"], ops["pdp"] / rec["counts"]["pdp_attempts"])
        self.assertEqual(out["collection_ops_per_novel_row"], out["collection_ops"] / out["novel_rows"])
        self.assertAlmostEqual(out["online_rho_over_ic"],
                               rec["online"]["rho_online_ns"] / rec["online"]["ic_online_ns"])
        self.assertEqual(sum(rec["phase_operations"].values()), rec["total_operations"])

    def test_failed_zero_rank_run_keeps_work_and_cannot_claim_speedup(self):
        rec = copy.deepcopy(self.receipt)
        rec["status"] = "budget"
        rec["verified_scalar"] = False
        rec["total_operations"] = None
        rec["counts"]["novel_rows"] = rec["counts"]["final_rank"] = 0
        rec["counts"]["targets_verified"] = 0
        out = cost_table.measure(rec)
        self.assertEqual(out["collection_ops"], cost_table.measure(self.receipt)["collection_ops"])
        self.assertIsNone(out["collection_ops_per_novel_row"])
        self.assertIsNone(out["queries_per_novel_row"])
        self.assertIsNone(out["online_rho_over_ic"])
        self.assertIsNone(out["total_ops"])

    def test_prime_bridge_zero_placeholders_do_not_claim_free_la(self):
        rec = copy.deepcopy(self.receipt)
        rec["source_curve_ref"] = "EC1P20Cgenh123456789abc"
        rec["native_prime_report"] = {"factor_base": {"points": 12}}
        rec["counts"].update(targets=2, targets_verified=2, pdp_attempts=0)
        rec["phase_operations"]["precompute"] = 100
        rec["total_operations"] = sum(rec["phase_operations"].values())
        out = cost_table.measure(rec)
        self.assertEqual(out["collection_ops"], 100)
        self.assertEqual(out["factor_base_points"], 12)
        self.assertIsNone(out["matrix_ops"])
        self.assertIsNone(out["matrix_wall_ns"])
        self.assertIsNone(out["mean_H_ops"])
        self.assertIsNone(out["online_rho_over_ic"])

    def test_theory_checks_linear_invariant_dimension(self):
        self.assertIsNone(cost_table.invariant_dimension_check(2, 31, 5))
        note = cost_table.invariant_dimension_check(2, 131, 32)
        self.assertIn("ord_131(2)=130", note)
        models = cost_table.paper_models(2, 131, 32, 4)
        self.assertEqual(models[0][1] / models[-1][1], 131 * 6)
        self.assertEqual(models[0][2] / models[3][2], 131 * 131)

    def test_missing_phase_does_not_become_free_work(self):
        rec = copy.deepcopy(self.receipt)
        rec["phase_operations"].pop("relation_la")
        out = cost_table.measure(rec)
        self.assertIsNone(out["matrix_ops"])


if __name__ == "__main__":
    unittest.main()
