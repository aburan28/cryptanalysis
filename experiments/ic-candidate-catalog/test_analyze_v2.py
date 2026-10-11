"""Check that comparison claims fail closed on missing work or completions."""

import copy
import unittest

import analyze_v2 as analyze


def receipt(config, block, cost, status="complete"):
    phases = {phase: 0 for phase in analyze.CONTRACT["phase_operations"]}
    phases["pdp"] = cost
    phase_wall = {phase: 0 for phase in analyze.CONTRACT["phase_operations"]}
    phase_wall["pdp"] = 1000
    online_phases = {phase: 0 for phase in analyze.CONTRACT["online_target_phases"]}
    online_phases["target_pdp"] = cost
    return {
        "schema_version": analyze.CONTRACT["schema_version"],
        "kind": "full_dlp",
        "status": status,
        "candidate_id": config,
        "proposal_id": None,
        "run_id": f"{config}WtestR{block}",
        "workload_id": "Wtest",
        "pair_block_id": str(block),
        "source_curve_ref": "toy/source",
        "isogeny_route_ref": "none",
        "profile_id": "toy",
        "subgroup_order": "101",
        "provenance": {
            "workload_fixture_sha256": "same-targets",
            "source_sha256": "separate-implementation",
            "host_id": "test-host",
            "resource_envelope_id": "same-limit",
            "calibration_id": "same-operations",
        },
        "counts": {"ordinary_queries": 5, "solved_queries": 2,
                   "verified_decompositions": 4, "verified_relations": 3,
                   "novel_rows": 2, "effective_columns": 2, "final_rank": 2,
                   "pdp_attempts": 5, "pdp_verified": 2, "pdp_proved_unsat": 1,
                   "pdp_timeout": 1, "pdp_budget": 1, "pdp_error": 0,
                   "pdp_lift_rejected": 0},
        "phase_operations": phases,
        "phase_wall_ns": phase_wall,
        "online_phase_wall_ns": online_phases,
        "online_wall_ns": cost,
        "rho_online_wall_ns": 500,
        "rho_verified": True,
        "target_count": 1,
        "target_point_sha256": "a" * 64,
        "precomputation_ready": True,
        "total_operations": cost if status == "complete" else None,
        "rho_operations": 500,
        "verified_scalar": status == "complete",
        "scalar_certificate_ref": "synthetic-test-certificate" if status == "complete" else None,
        "peak_rss_bytes": 100,
        "wall_ns": 1000,
    }


class AnalyzeTests(unittest.TestCase):
    def test_paired_complete_and_multiple_witnesses(self):
        runs = [analyze.validate_run(receipt(config, block, cost))
                for block in range(1, 4)
                for config, cost in (("IC1base", 200), ("IC1candidate", 100))]
        result = analyze.paired_compare(runs, "IC1base", "IC1candidate")
        self.assertEqual(result["online_speedup"], 2.0)
        self.assertEqual(result["online_speedup_ci95"], [2.0, 2.0])
        self.assertAlmostEqual(result["rho_over_candidate_online_speedup"], 5.0)
        self.assertEqual(result["cold_operations_speedup_supplementary"], 2.0)

    def test_one_censored_pair_blocks_full_speedup(self):
        runs = [analyze.validate_run(receipt("IC1base", 1, 200)),
                analyze.validate_run(receipt("IC1candidate", 1, 100)),
                analyze.validate_run(receipt("IC1base", 2, 200)),
                analyze.validate_run(receipt("IC1candidate", 2, 100, "timeout"))]
        result = analyze.paired_compare(runs, "IC1base", "IC1candidate")
        self.assertIsNone(result["online_speedup"])
        self.assertEqual(result["complete_pairs"], 1)
        self.assertEqual(result["incomplete_pairs"][0]["reason"], "incomplete_dlp")

    def test_missing_phase_and_mismatched_total_are_rejected(self):
        run = receipt("IC1base", 1, 200)
        run["phase_operations"]["matrix_build"] = None
        with self.assertRaisesRegex(ValueError, "total operations"):
            analyze.validate_run(run)

    def test_online_boundary_is_required_even_when_cold_cost_is_priced(self):
        run = receipt("IC1base", 1, 200)
        run["online_phase_wall_ns"]["target_pdp"] = 199
        with self.assertRaisesRegex(ValueError, "exclusive online timing"):
            analyze.validate_run(run)
        run = receipt("IC1base", 1, 200)
        run["target_count"] = 2
        with self.assertRaisesRegex(ValueError, "one unseen target"):
            analyze.validate_run(run)

    def test_online_comparison_survives_unpriced_cold_setup(self):
        a, b = receipt("IC1base", 1, 200), receipt("IC1candidate", 1, 100)
        for run in (a, b):
            run["phase_operations"]["factor_base"] = None
            run["total_operations"] = None
        result = analyze.paired_compare([analyze.validate_run(a), analyze.validate_run(b)],
                                        "IC1base", "IC1candidate")
        self.assertEqual(result["online_speedup"], 2.0)
        self.assertIsNone(result["cold_operations_speedup_supplementary"])
        b["target_point_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "mismatched target point"):
            analyze.paired_compare([a, b], "IC1base", "IC1candidate")
        run = receipt("IC1base", 1, 200)
        run["total_operations"] = 199
        with self.assertRaisesRegex(ValueError, "total operations"):
            analyze.validate_run(run)

    def test_candidate_specific_base_may_differ_on_same_workload(self):
        a, b = receipt("IC1base", 1, 200), receipt("IC1candidate", 1, 100)
        a["provenance"]["source_sha256"] = "base-implementation"
        b["provenance"]["source_sha256"] = "candidate-implementation"
        a["profile_id"] = "base-a"
        b["profile_id"] = "base-b"
        result = analyze.paired_compare([analyze.validate_run(a), analyze.validate_run(b)],
                                        "IC1base", "IC1candidate")
        self.assertEqual(result["online_speedup"], 2.0)
        bad = copy.deepcopy(b)
        bad["provenance"]["workload_fixture_sha256"] = "different-targets"
        with self.assertRaisesRegex(ValueError, "mismatched provenance"):
            analyze.paired_compare([a, bad], "IC1base", "IC1candidate")

    def test_stage_summary_keeps_workloads_separate_and_reports_rate_interval(self):
        a = analyze.validate_run(receipt("IC1base", 1, 200))
        b = analyze.validate_run(receipt("IC1base", 2, 200))
        b["workload_id"] = "Wother"
        summary = analyze.summarize([a, b])["IC1base"]
        self.assertEqual(set(summary), {"Wtest", "Wother"})
        rate = summary["Wtest"]["verified_within_budget_query_rate"]
        low, high = summary["Wtest"]["verified_within_budget_query_wilson95"]
        self.assertLess(low, rate)
        self.assertLess(rate, high)
        with self.assertRaisesRegex(ValueError, "one frozen workload"):
            analyze.paired_compare([a, b], "IC1base", "IC1candidate")

    def test_search_only_isogeny_cannot_claim_complete_dlp(self):
        run = receipt("IC1routeISO1habcdef012345", 1, 200)
        run["isogeny_route_ref"] = "search_l2_ecc2k130"
        with self.assertRaisesRegex(ValueError, "unverified isogeny route"):
            analyze.validate_run(run)


if __name__ == "__main__":
    unittest.main()
