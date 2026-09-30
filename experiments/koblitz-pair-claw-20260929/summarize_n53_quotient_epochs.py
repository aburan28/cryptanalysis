#!/usr/bin/env python3
"""Check and summarize the frozen Q1067 one-versus-four-epoch receipts."""

import hashlib
import json
import math
from pathlib import Path

from run_n23 import frozen, sha

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PLAN = HERE / "n53_quotient_epoch_plan.json"
OUTPUT = HERE / "n53_quotient_epoch_comparison.json"


def main():
    plan = json.loads(PLAN.read_text())
    assert plan["proposal_id"] == "Q1067"
    assert plan["candidate_id"] is None and plan["run_id"] is None
    assert plan["isogeny"] == "none"
    rows = {}
    for variant in ("single", "four"):
        path = RUNS / f"n53_quotient_epoch_{variant}.json"
        receipt = json.loads(path.read_text())
        assert receipt["proposal_id"] == "Q1067"
        assert receipt["candidate_id"] is None and receipt["run_id"] is None
        assert receipt["curve_id"] == plan["curve_id"]
        assert receipt["isogeny"] == "none"
        assert receipt["variant"] == variant
        assert receipt["plan_sha256"] == sha(PLAN)
        assert receipt["source_sha256"] == sha(
            HERE / "probe_n53_quotient_epochs.py")
        assert receipt["epoch_walk_source_sha256"] == sha(
            HERE / "quotient_epoch_walk.py")
        assert receipt["sage_runtime_info_sha256"] == sha(
            RUNS / "n53_quotient_epoch_runtime_info.json")
        assert receipt["workload_id"] == hashlib.sha256(
            frozen(receipt["workload"])).hexdigest()[:12]
        assert receipt["factor_base"]["enumerated_set_sha256"] == plan[
            "factor_base"]["enumerated_set_sha256"]
        assert receipt["factor_base"]["actual_usable_points_B_before_folding"] == plan[
            "factor_base"]["actual_usable_points_B_before_folding"]
        assert receipt["factor_base"]["signed_frobenius_columns"] == plan[
            "factor_base"]["signed_frobenius_columns"]
        query = receipt["ordinary_query"]
        assert query["status"] == "budget" and query["relation"] is None
        assert query["main_step_evaluations_excluding_replay"] == plan[
            "max_main_step_evaluations"]
        assert query["epochs_completed"] == plan["variants"][variant]["epochs"]
        assert sum(epoch["main_step_evaluations_excluding_replay"]
                   for epoch in query["epochs"]) == query[
                       "main_step_evaluations_excluding_replay"]
        assert sum(epoch["replay_step_evaluations"]
                   for epoch in query["epochs"]) == query[
                       "replay_step_evaluations"]
        total_steps = (query["main_step_evaluations_excluding_replay"] +
                       query["replay_step_evaluations"])
        rows[variant] = {
            "receipt": str(path.relative_to(HERE)), "receipt_sha256": sha(path),
            "epochs": query["epochs_completed"],
            "main_step_evaluations": query[
                "main_step_evaluations_excluding_replay"],
            "replay_step_evaluations": query["replay_step_evaluations"],
            "total_step_evaluations_including_replay": total_steps,
            "total_step_evaluations_log2": math.log2(total_steps),
            "per_epoch_distinct_output_key_count_sum": sum(
                epoch["distinct_output_keys"] for epoch in query["epochs"]),
            "endpoint_rows_sum": sum(epoch["endpoint_rows"]
                                     for epoch in query["epochs"]),
            "endpoint_replays_sum": sum(epoch["endpoint_replays"]
                                        for epoch in query["epochs"]),
            "wall_seconds": query["wall_ns"] / 1e9,
            "peak_parent_rss_bytes": receipt["peak_parent_rss_bytes"],
            "ordinary_relations": 0,
        }
    first = json.loads((RUNS / "n53_quotient_epoch_single.json").read_text())
    second = json.loads((RUNS / "n53_quotient_epoch_four.json").read_text())
    assert first["workload_id"] == second["workload_id"]
    assert first["workload"] == second["workload"]
    comparison = {
        "kind": "n53_q1067_paired_salted_quotient_claw_epoch_screen",
        "proposal_id": "Q1067", "candidate_id": None, "run_id": None,
        "curve_id": plan["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": plan["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": plan["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": plan["factor_base"][
            "signed_frobenius_columns"],
        "workload_id": first["workload_id"], "workload": first["workload"],
        "variants": rows,
        "four_vs_single_wall_speedup": (rows["single"]["wall_seconds"] /
                                        rows["four"]["wall_seconds"]),
        "four_vs_single_total_step_reduction_fraction": (
            1 - rows["four"]["total_step_evaluations_including_replay"] /
            rows["single"]["total_step_evaluations_including_replay"]),
        "verified_n53_relation_count": 0,
        "verified_single_target_dlp": False,
        "complete_solve_work_log2": None,
        "uncertainty": "One frozen target and one paired seed; the count and wall ratios are descriptive, with no independent replication or relation-yield confidence interval.",
        "limits": [
            "Step evaluations are pair-map calls, not field operations or complete DLP work.",
            "Distinct output counts are summed within separate epoch maps, not deduplicated across them.",
            "Both variants exhausted the cap without a natural relation; no n83 speedup is inferred.",
        ],
        "plan_sha256": sha(PLAN),
        "n23_control_sha256": sha(RUNS / "n23_quotient_epoch_control.json"),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(comparison, indent=2) + "\n")
    print(json.dumps({"workload_id": comparison["workload_id"],
                      "wall_speedup": comparison["four_vs_single_wall_speedup"],
                      "relations": 0,
                      "complete_solve_work_log2": None}))


if __name__ == "__main__":
    main()
