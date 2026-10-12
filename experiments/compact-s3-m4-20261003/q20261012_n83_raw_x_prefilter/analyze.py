#!/usr/bin/env python3
"""Account for Q1512 filter work without merging unlike operation units."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = HERE / "analysis.json"
    assert not out.exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    control = json.loads((HERE / "deep_control.json").read_text())
    q1505 = json.loads((PARENT / "q20261012_n83_deferred_y_scan/analysis.json").read_text())
    assert result["proposal_id"] == protocol["proposal_id"] == "Q1512"
    assert result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert control["base_sha256"] == protocol["base_point_file_sha256"]
    assert len(result["rows"]) == len(protocol["screen_modes"]) + len(protocol["full_modes_in_run_order"])
    screen = []
    full = []
    selected_baseline = next(row for row in result["rows"] if row["panel"] == "screen" and row["bloom_log2_bits"] == 0)
    for row in result["rows"]:
        assert row["status"] == "COMPLETE"
        native = row["native"]
        if row["panel"] == "screen":
            assert native["scanned"] == 2 * protocol["screen_pair_count"]
            assert native["hits"] == selected_baseline["native"]["hits"] == 0
            assert native["raw_x_checksum_hex"] == selected_baseline["native"]["raw_x_checksum_hex"]
            screen.append({"bits": row["bloom_log2_bits"], "hashes": row["bloom_hashes"],
                           "bloom_bytes": native["bloom_bytes"],
                           "canonical_calls": native["canonical_calls"],
                           "bloom_build_bit_sets": native["bloom_build_bit_sets"],
                           "bloom_scan_bit_probes": native["bloom_scan_bit_probes"],
                           "scan_seconds_exploratory": native["scan_seconds"]})
    for label in ("selected", "holdout"):
        rows = [row for row in result["rows"] if row["panel"] == "full" and row["input"] == label]
        baseline = next(row for row in rows if row["bloom_log2_bits"] == 0)["native"]
        for row in rows:
            native = row["native"]
            assert native["scanned"] == protocol["factor_base_actual_B"]
            assert native["hits"] == baseline["hits"] == 0
            assert native["raw_x_checksum_hex"] == baseline["raw_x_checksum_hex"]
            if row["bloom_log2_bits"] == 0:
                continue
            full.append({"input": label, "workload_id": row["workload_id"],
                         "bits": row["bloom_log2_bits"], "hashes": row["bloom_hashes"],
                         "bloom_bytes": native["bloom_bytes"],
                         "canonical_calls": native["canonical_calls"],
                         "canonical_calls_avoided": baseline["canonical_calls"] - native["canonical_calls"],
                         "canonical_call_reduction_log2": math.log2(baseline["canonical_calls"] / native["canonical_calls"]),
                         "bloom_build_bit_sets": native["bloom_build_bit_sets"],
                         "bloom_scan_bit_probes": native["bloom_scan_bit_probes"],
                         "scan_wall_ratio_exploratory": baseline["scan_seconds"] / native["scan_seconds"],
                         "setup_plus_scan_wall_ratio_exploratory":
                            (baseline["setup_seconds"] + baseline["scan_seconds"]) /
                            (native["setup_seconds"] + native["scan_seconds"]),
                         "peak_rss_extra_bytes": native["peak_rss_raw"] - baseline["peak_rss_raw"],
                         "verified_relation_count": native["hits"]})
    assert len(full) == 4
    n131_k = q1505["n131_exact_weight6_K"]
    assert n131_k == 25036774
    n131_unique_x = n131_k * 131
    n83_unique_x = protocol["factor_base_folded_columns_K"] * 83
    bloom_bits_28_per_x = (1 << 28) / n83_unique_x
    n131_bloom_bits = math.ceil(n131_unique_x * bloom_bits_28_per_x)
    n131_power_two_bits = 1 << (n131_bloom_bits - 1).bit_length()
    analysis = {
        "proposal_id": "Q1512", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": protocol["factor_base_enumerated_set_sha256"],
        "protocol_sha256": sha(HERE / "protocol.json"),
        "result_sha256": sha(HERE / "result.json"),
        "deep_control_sha256": sha(HERE / "deep_control.json"),
        "q1505_analysis_sha256": sha(PARENT / "q20261012_n83_deferred_y_scan/analysis.json"),
        "source_sha256": sha(Path(__file__)),
        "screen": screen, "full": full,
        "n83_unique_raw_x": n83_unique_x,
        "n131_w6_unique_raw_x_if_all_orbits_materialized": n131_unique_x,
        "n131_w6_bloom_bits_at_n83_bits_per_x": n131_bloom_bits,
        "n131_w6_power_two_bloom_bytes": n131_power_two_bits // 8,
        "n131_w6_four_sign_zero_hit_batch_mul_calls_unchanged":
            q1505["n131_four_sign_scan_batch_mul_calls_zero_hits"],
        "n131_w6_independent_uniform_first_pair_relation_supply_batch_mul_log2_unchanged":
            q1505["independent_uniform_first_pair_model"]["expected_batch_mul_calls_for_K_hits_lower_log2"],
        "complete_n131_solve_operation_log2": None,
        "wall_isolation": "unavailable; wall ratios exploratory",
        "operation_units": ["canonical_x calls", "Bloom bit sets/probes", "batch field multiplication calls"],
    }
    out.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    print("Q1512", [(r["input"], r["bits"], round(r["scan_wall_ratio_exploratory"], 3))
                    for r in full])


if __name__ == "__main__":
    main()
