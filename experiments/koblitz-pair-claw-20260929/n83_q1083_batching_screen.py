#!/usr/bin/env python3
"""Compare two measured R29 jobs with a projected one-table R30 job."""

import hashlib
import json
from pathlib import Path

from n83_full_spill_screen import field_calls

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
OUTPUT = HERE / "n83_q1083_batching_screen.json"
M = 1 << 32
R = 1 << 29
TIMEOUT = 360 * 60
STARTS = (
    18253611008, 18790481920, 19327352832, 19864223744,
    20401094656, 20937965568, 21474836480, 22011707392,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for start in STARTS:
        path = RUNS / (
            "n83_zero_run_q1079_M32_R29_ci_36784663720_"
            f"qstart{start}/full.json")
        receipt = json.loads(path.read_text())
        native = receipt["native_result"]
        assert receipt["curve_id"] == "EC1N83Ckb1h876c2921cb64"
        assert receipt["isogeny"] == "none"
        assert receipt["candidate_id"] is None
        assert receipt["factor_base"]["enumerated_set_sha256"] == (
            "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02")
        assert receipt["factor_base"]["actual_usable_points_B_before_folding"] == (
            8000204)
        assert receipt["query_start"] == start
        assert receipt["table_descriptors"] == M
        assert receipt["query_representatives"] == R
        assert native["exact_hit_queries"] == 0
        assert receipt["native_field_add_mul_sqr_call_model"] == str(
            field_calls(M, R))
        projection = (native["build_seconds"] +
                      2 * native["query_seconds"] +
                      2 * native["exact_replay_seconds"])
        rows.append({
            "query_start": start,
            "receipt": str(path.relative_to(HERE)),
            "receipt_sha256": sha(path),
            "measured_build_seconds": native["build_seconds"],
            "measured_query_seconds": native["query_seconds"],
            "measured_exact_replay_seconds": native["exact_replay_seconds"],
            "projected_R30_native_seconds_if_query_and_replay_double":
                projection,
            "projected_native_margin_to_360_minute_job_limit_seconds":
                TIMEOUT - projection,
        })
    pair_calls = 2 * field_calls(M, R)
    combined_calls = field_calls(M, 2 * R)
    result = {
        "kind": "n83_q1083_R29_vs_R30_source_bound_batching_screen",
        "proposal_id": "Q1083", "candidate_id": None, "run_id": None,
        "curve_id": "EC1N83Ckb1h876c2921cb64", "isogeny": "none",
        "factor_base_enumerated_set_sha256":
            "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02",
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "Q1079_measured_R29_phase_rows": rows,
        "two_separate_M32_R29_modeled_field_calls": str(pair_calls),
        "one_M32_R30_modeled_field_calls": str(combined_calls),
        "one_R30_vs_two_R29_modeled_field_call_saving_fraction":
            1 - combined_calls / pair_calls,
        "CI_timeout_seconds_per_job": TIMEOUT,
        "smallest_projected_R30_native_margin_seconds": min(
            row["projected_native_margin_to_360_minute_job_limit_seconds"]
            for row in rows),
        "Q1083_dispatch_design_choice": "sixteen_M32_R29_jobs_max_eight_parallel",
        "limits": [
            "R30 durations are linear extrapolations from measured R29 phases, not R30 measurements.",
            "Projected native durations omit wrapper, control, setup, upload, host variance, and failure recovery.",
            "The narrowest projected native margin does not justify a 360-minute R30 CI job.",
            "Field calls omit keying, Bloom, memory, disk, setup, failed work, and scalar replay.",
            "This is a stage comparison; complete-solve work remains unknown."
        ],
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "savings_fraction": result[
            "one_R30_vs_two_R29_modeled_field_call_saving_fraction"],
        "smallest_R30_native_margin_seconds": result[
            "smallest_projected_R30_native_margin_seconds"],
    }))


if __name__ == "__main__":
    main()
