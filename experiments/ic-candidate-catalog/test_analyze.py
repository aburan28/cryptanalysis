"""Check that comparison claims fail closed on missing work or completions."""

import copy
import unittest

import analyze


def receipt(config, block, cost, status="complete"):
    phases = {phase: 0 for phase in analyze.CONTRACT["phase_operations"]}
    phases["pdp"] = cost
    phase_wall = {phase: 0 for phase in analyze.CONTRACT["phase_operations"]}
    phase_wall["pdp"] = 1000
    return {
        "schema_version": 1,
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
        "total_operations": cost if status == "complete" else None,
        "rho_operations": 500,
        "verified_scalar": status == "complete",
        "scalar_certificate_ref": "synthetic-test-certificate" if status == "complete" else None,
        "peak_rss_bytes": 100,
        "wall_ns": 1000,
    }


class AnalyzeTests(unittest.TestCase):
    @staticmethod
    def wall_receipt(config="IC1wall", block=1, online_ns=2000):
        run = receipt(config, block, 200)
        target = {"x": 5, "y": 9, "inf": False}
        run.update(accounting_mode="verified_online_wall", operation_unit=None,
                   unknown_operation_reason="Synthetic contract fixture; no operation counts",
                   phase_operations={p: None for p in analyze.CONTRACT["phase_operations"]},
                   total_operations=None, rho_operations=None,
                   scalar_certificate={"target": target, "replayed_point": target, "scalar": 17},
                   rho_measured={"verified": True, "scalar": 17, "target": target,
                                 "replayed_point": target, "online_wall_ns": 10000})
        phases = {"target_query": 10, "target_pdp": online_ns-40, "target_relation_check": 10,
                  "target_descent": 10, "target_recovery_check": 10}
        run["online"] = {"ic_online_ns": online_ns, "rho_online_ns": 10000,
                         "speedup": 10000/online_ns, "phase_wall_ns": phases, "public_target": target}
        run["counts"].update(targets=1, targets_verified=1)
        run["phase_wall_ns"].update(target_descent=online_ns-10, recovery_check=10)
        run["wall_ns"] = 1000 + online_ns
        return run

    def test_verified_online_wall_keeps_operation_costs_unknown(self):
        runs = [analyze.validate_run(self.wall_receipt(config, block, cost))
                for block in range(1, 4)
                for config, cost in (("IC1wallbase", 2000), ("IC1wallcandidate", 1000))]
        summary = analyze.summarize(runs)["IC1wallcandidate"]["Wtest"]
        self.assertIsNone(summary["median_complete_total_operations"])
        self.assertEqual(summary["median_verified_ic_online_ns"], 1000)
        paired = analyze.paired_compare(runs, "IC1wallbase", "IC1wallcandidate")
        self.assertEqual(paired["metric"], "one_target_online_wall_ns")
        self.assertEqual(paired["speedup"], 2)

    def test_wall_mode_rejects_missing_work_and_mismatched_recovery(self):
        original = self.wall_receipt()
        mutations = (
            lambda r: r.update(accounting_mode="anything"),
            lambda r: r.update(unknown_operation_reason=""),
            lambda r: r.update(total_operations=0),
            lambda r: r["phase_operations"].update(pdp=0),
            lambda r: r.update(S_rps=0),
            lambda r: r.update(online=None),
            lambda r: r["online"]["phase_wall_ns"].update(target_pdp=1),
            lambda r: r["counts"].update(targets=2),
            lambda r: r["rho_measured"].update(verified=False),
            lambda r: r["rho_measured"].update(target={"x": 6, "y": 9, "inf": False}),
            lambda r: r["rho_measured"].update(scalar=18),
            lambda r: r["scalar_certificate"].update(replayed_point={"x": 6, "y": 9, "inf": False}),
            lambda r: r["phase_wall_ns"].update(matrix_build=None),
        )
        for mutate in mutations:
            run = copy.deepcopy(original)
            mutate(run)
            with self.assertRaises(ValueError):
                analyze.validate_run(run)

    def test_paired_complete_and_multiple_witnesses(self):
        runs = [analyze.validate_run(receipt(config, block, cost))
                for block in range(1, 4)
                for config, cost in (("IC1base", 200), ("IC1candidate", 100))]
        result = analyze.paired_compare(runs, "IC1base", "IC1candidate")
        self.assertEqual(result["speedup"], 2.0)
        self.assertEqual(result["speedup_ci95"], [2.0, 2.0])

    def test_one_censored_pair_blocks_full_speedup(self):
        runs = [analyze.validate_run(receipt("IC1base", 1, 200)),
                analyze.validate_run(receipt("IC1candidate", 1, 100)),
                analyze.validate_run(receipt("IC1base", 2, 200)),
                analyze.validate_run(receipt("IC1candidate", 2, 100, "timeout"))]
        result = analyze.paired_compare(runs, "IC1base", "IC1candidate")
        self.assertIsNone(result["speedup"])
        self.assertEqual(result["complete_pairs"], 1)
        self.assertEqual(result["incomplete_pairs"][0]["reason"], "incomplete_dlp")

    def test_missing_phase_and_mismatched_total_are_rejected(self):
        run = receipt("IC1base", 1, 200)
        run["phase_operations"]["matrix_build"] = None
        with self.assertRaisesRegex(ValueError, "total operations"):
            analyze.validate_run(run)
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
        self.assertEqual(result["speedup"], 2.0)
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
        rate = summary["Wtest"]["observed_decomposition_rate"]
        low, high = summary["Wtest"]["observed_decomposition_wilson95"]
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
