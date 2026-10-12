#!/usr/bin/env python3
"""Charge Q1529 quotient pair additions and compare the separate Q1526 screen."""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1526 = HERE.parent / "q20261012_q1526_pair_hyperparams/analysis.json"


def main():
    measured = json.loads((HERE / "result.json").read_text())
    prior = json.loads(Q1526.read_text())
    w7 = [x for x in prior["cells"] if x["weight_bound"] == 7 and
          x["table_fraction"] == "1/1"][0]
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
              "complete_N131_solve_work_log2": None,
              "single_target_online_speedup": None,
              "CPU_isolation_receipt": None}
    (HERE / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1529", len(rows), "cells; long-run pair additions",
          rows[-1]["charged_pair_addition_attempts_log2"],
          "Q1526 conditional N131 W7", w7["counted_pair_add_attempts_log2"])


if __name__ == "__main__":
    main()
