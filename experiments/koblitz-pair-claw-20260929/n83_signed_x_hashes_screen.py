#!/usr/bin/env python3
"""Keep Bloom probe counts separate from n=83 field-call work."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRED = HERE / "runs" / "n83_signed_x_hashes_paired.json"
Q1054 = HERE / "n83_signed_x_screen.json"
FIRST = HERE / "runs" / "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json"
OUTPUT = HERE / "n83_signed_x_hashes_screen.json"
M, R, N, CHUNKS = 1 << 31, 1 << 30, 83, 118


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paired = json.loads(PAIRED.read_text())
    q1054 = json.loads(Q1054.read_text())
    first = json.loads(FIRST.read_text())
    assert paired["proposal_id"] == "Q1055"
    assert q1054["proposal_id"] == "Q1054"
    assert first["proposal_id"] == "Q1051"
    assert paired["curve_id"] == q1054["curve_id"] == first["curve_id"]
    assert paired["isogeny"] == q1054["isogeny"] == first["isogeny"] == "none"
    assert paired["candidate_id"] is q1054["candidate_id"] is None
    assert paired["actual_usable_points_B_before_folding"] == q1054[
        "actual_usable_points_B_before_folding"] == 8000204
    assert paired["factor_base_enumerated_set_sha256"] == q1054[
        "factor_base_enumerated_set_sha256"]
    assert paired["public_target"] == q1054["public_target"]
    baseline = paired["summaries"]["14"]
    first_positive = first["native_result"]["bloom_positive_queries"]
    report = {
        "kind": "n83_signed_x_hash_count_conditional_stage_screen",
        "proposal_id": "Q1055", "candidate_id": None,
        "curve_id": paired["curve_id"], "isogeny": "none",
        "public_target": paired["public_target"],
        "factor_base_enumerated_set_sha256": paired[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "full_rectangle_table_descriptors": M,
        "full_rectangle_query_representatives": R,
        "conditional_p95_rectangles": CHUNKS,
        "full_rectangle_bloom_key_insertions": M,
        "full_rectangle_bloom_key_lookups": 2 * N * R,
        "bloom_probe_boundary": "one tested/inserted Bloom bit per hash; excludes keying, group/field arithmetic, memory latency, exact replay and scalar recovery",
        "native_field_call_model_log2_unchanged_from_Q1054": q1054[
            "standalone_95pct_prefix_modeled_field_calls_log2"],
        "complete_solve_work_log2": None,
        "ordinary_n83_relation_measured": False,
        "hash_variants": {},
        "limits": [
            "The 118-rectangle first-hit probability is the Q1051 finite-support heuristic, not measured natural-target yield.",
            "The bounded 2^20-descriptor filter has different cache and candidate-memory behavior from the planned 2^31-descriptor filter.",
            "Bounded wall times are sensitive to concurrent host load; process CPU includes startup and all stages, not just the query.",
            "Scaling Bloom-positive counts by the Q1051 full-size ratio is only a filter-shape proxy; full-size counts and memory are unmeasured.",
            "Bloom bit probes and native field API calls are distinct units and cannot be added as equivalent field operations without calibration.",
        ],
        "paired_receipt_sha256": sha(PAIRED),
        "Q1054_screen_sha256": sha(Q1054),
        "first_completed_Q1051_receipt_sha256": sha(FIRST),
        "source_sha256": sha(Path(__file__)),
    }
    for key, row in paired["summaries"].items():
        hashes = int(key)
        positives = row["bloom_positive_queries"]
        assert len(positives) == 2 and positives[0] == positives[1]
        queries = row["median_query_seconds"]
        cpu = row["median_process_cpu_seconds_including_startup"]
        projected_positive = first_positive * positives[0] / baseline[
            "bloom_positive_queries"][0]
        bit_probes = hashes * (M + 2 * N * R)
        report["hash_variants"][key] = {
            "measured_bounded_query_median_seconds": queries,
            "measured_bounded_process_cpu_median_seconds": cpu,
            "measured_bounded_bloom_positive_queries": positives[0],
            "measured_bounded_peak_rss_bytes": row["peak_rss_bytes"],
            "bounded_query_speedup_vs_14_hashes": baseline[
                "median_query_seconds"] / queries,
            "bounded_process_cpu_speedup_vs_14_hashes": baseline[
                "median_process_cpu_seconds_including_startup"] / cpu,
            "bounded_bloom_positive_ratio_vs_14_hashes": positives[0] /
                baseline["bloom_positive_queries"][0],
            "modeled_bloom_bit_probes_per_full_rectangle": str(bit_probes),
            "modeled_bloom_bit_probes_p95_prefix_log2": math.log2(
                CHUNKS * bit_probes),
            "projected_full_rectangle_bloom_positives_if_bounded_ratio_transfers":
                round(projected_positive),
        }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: {
        "query_speedup": v["bounded_query_speedup_vs_14_hashes"],
        "cpu_speedup": v["bounded_process_cpu_speedup_vs_14_hashes"],
        "p95_bloom_probe_log2": v["modeled_bloom_bit_probes_p95_prefix_log2"]}
        for k, v in report["hash_variants"].items()}))


if __name__ == "__main__":
    main()
