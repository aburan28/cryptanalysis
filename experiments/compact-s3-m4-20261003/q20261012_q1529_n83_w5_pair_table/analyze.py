#!/usr/bin/env python3
"""Charge Q1529 quotient pair additions and compare the separate Q1526 screen."""
import json
import math
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1526 = HERE.parent / "q20261012_q1526_pair_hyperparams/analysis.json"


def main():
    measured = json.loads((HERE / "result.json").read_text())
    prior = json.loads(Q1526.read_text())
    w7 = [x for x in prior["cells"] if x["weight_bound"] == 7 and
          x["table_fraction"] == "1/1"][0]
    n83_target = json.loads((HERE.parent / "q20261011_wdsat_phase_restart/target.json").read_text())
    assert n83_target["curve_id"] == measured["curve_id"]
    r83 = int(n83_target["workload_record"]["subgroup_order_r"])
    b83, k83, t83 = measured["base_B"], measured["folded_K"], 1 << 18
    domain83 = 83 * k83 * (k83 - 1)
    # Q1462 counts lifted query points. One native representative searches
    # 2n=166 signed/Frobenius lifts using one shared base-pair sum.
    rep_num83 = 2 * r83 * domain83
    rep_den83 = b83 * b83 * t83 * 166
    rep_log83 = math.log2(rep_num83) - math.log2(rep_den83)
    b7, k7, r131 = w7["B"], w7["K"], int(prior["subgroup_order_r"])
    table7 = 131 * k7 * k7
    # A native N131 analogue would use 262 complements per representative:
    # T + Q_lifted + Q_lifted/262, versus Q1526's T + 2 Q_lifted.
    native_num7 = table7 * 262 * b7 * b7 + 263 * k7 * 2 * r131
    native_den7 = 262 * b7 * b7
    native_log7 = math.log2(native_num7) - math.log2(native_den7)
    rows = []
    for cell in measured["rows"]:
        n = cell["native"]
        table = n["table_descriptors"]
        reps = n["query_representatives"]
        # One pair addition per table descriptor, one per query representative,
        # 166 target-complement additions per representative, and a full exact
        # table replay whenever the Bloom filter has a positive.
        additions = table + 167 * reps + (table if n["bloom_positive_queries"] else 0)
        rows.append({"label": cell["label"], "workload_id":
                     ("2eb250a29072" if cell["label"] == "selected" else
                      "394256b9f901" if cell["label"] == "holdout" else None),
                     "table_descriptors": table, "query_representatives": reps,
                     "workers": n["query_workers"], "bits_per_key": n["bloom_bits_per_key"],
                     "bloom_hashes": n["bloom_hashes"],
                     "bloom_positive_queries": n["bloom_positive_queries"],
                     "exact_hit_queries": n["exact_hit_queries"],
                     "charged_pair_addition_attempts": additions,
                     "charged_pair_addition_attempts_log2": math.log2(additions),
                     "native_build_seconds_exploratory": n["build_seconds"],
                     "native_query_seconds_exploratory": n["query_seconds"],
                     "native_replay_seconds_exploratory": n["exact_replay_seconds"],
                     "native_target_phase_seconds_exploratory":
                     n["query_seconds"] + n["exact_replay_seconds"],
                     "native_peak_rss_bytes": n["peak_rss_bytes"]})
    output = {"proposal_id": "Q1529", "candidate_id": None, "run_id": None,
              "curve_id": measured["curve_id"], "isogeny": "none",
              "analysis_kind": "exact_N83_W5_stage_diagnostic",
              "rows": rows, "ordinary_exact_hit_queries": 0,
              "q1526_conditional_N131_W7_pair_additions_log2":
                  w7["counted_pair_add_attempts_log2"],
              "q1526_conditional_gap_above_2pow61_bits":
                  w7["counted_pair_add_attempts_log2"] - 61,
              "q1526_analysis_sha256": hashlib.sha256(Q1526.read_bytes()).hexdigest(),
              "conditional_N83_W5_pair_domain": domain83,
              "conditional_N83_W5_table_fraction": f"{t83}/{domain83}",
              "conditional_N83_W5_expected_representatives_per_relation_numerator": rep_num83,
              "conditional_N83_W5_expected_representatives_per_relation_denominator": rep_den83,
              "conditional_N83_W5_expected_representatives_per_relation_log2": rep_log83,
              "conditional_N83_W5_long_prefix_exposure_log2": 20 - rep_log83,
              "conditional_N131_W7_quotient_reuse_pair_additions_numerator": native_num7,
              "conditional_N131_W7_quotient_reuse_pair_additions_denominator": native_den7,
              "conditional_N131_W7_quotient_reuse_pair_additions_log2": native_log7,
              "conditional_N131_W7_quotient_reuse_gap_above_2pow61_bits": native_log7 - 61,
              "conditional_quotient_reuse_improvement_bits":
                  w7["counted_pair_add_attempts_log2"] - native_log7,
              "complete_N131_solve_work_log2": None,
              "single_target_online_speedup": None,
              "CPU_isolation_receipt": None}
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1529", len(rows), "cells; long-run pair additions",
          rows[-1]["charged_pair_addition_attempts_log2"],
          "Q1526 conditional N131 W7", w7["counted_pair_add_attempts_log2"])


if __name__ == "__main__":
    main()
